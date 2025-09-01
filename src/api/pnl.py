"""
P&L API endpoints for dashboard
"""

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/api/pnl", tags=["P&L"])

@router.get("/summary")
async def get_pnl_summary() -> Dict[str, Any]:
    """
    Get P&L summary from logs
    Priority: 
    1. logs/pnl_summary.json if exists
    2. logs/pnl_timeseries.json for rough P&L from last two points
    3. Parse logs/paper_audit.log for approximate P&L
    """
    
    # Try to read pnl_summary.json first
    summary_path = Path("logs/pnl_summary.json")
    if summary_path.exists():
        try:
            with open(summary_path, 'r') as f:
                data = json.load(f)
                result = {
                    "initial_capital": data.get("initial_capital", 1000),
                    "final_capital": data.get("final_capital", 1000),
                    "realized_pnl": data.get("realized_pnl", 0),
                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                    "total_pnl": data.get("total_pnl", 0),
                    "pnl_percentage": data.get("pnl_percentage", 0),
                    "total_trades": data.get("total_trades", 0),
                    "win_rate": data.get("win_rate", 0),
                    "start_timestamp": data.get("start_timestamp", datetime.now().isoformat()),
                    "end_timestamp": data.get("end_timestamp", datetime.now().isoformat()),
                    "is_running": data.get("is_running", False),
                    "session_complete": data.get("session_complete", False),
                    "source": "summary"
                }
                
                # If session is running, also include timeseries
                if data.get("is_running", False):
                    timeseries_path = Path("logs/pnl_timeseries.json")
                    if timeseries_path.exists():
                        try:
                            with open(timeseries_path, 'r') as f:
                                timeseries = json.load(f)
                                result["timeseries"] = timeseries
                        except:
                            pass
                
                return result
        except Exception as e:
            pass  # Fall through to timeseries
    
    # Try to read timeseries for rough P&L
    timeseries_path = Path("logs/pnl_timeseries.json")
    if timeseries_path.exists():
        try:
            with open(timeseries_path, 'r') as f:
                timeseries = json.load(f)
                
            if len(timeseries) >= 2:
                first_point = timeseries[0]
                last_point = timeseries[-1]
                
                initial_capital = first_point.get("equity", 1000)
                final_capital = last_point.get("equity", 1000)
                total_pnl = final_capital - initial_capital
                pnl_percentage = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
                
                return {
                    "initial_capital": initial_capital,
                    "final_capital": final_capital,
                    "realized_pnl": total_pnl,  # Assume all realized for simplicity
                    "unrealized_pnl": 0,
                    "total_pnl": total_pnl,
                    "pnl_percentage": pnl_percentage,
                    "total_trades": 0,  # Unknown from timeseries
                    "win_rate": 0,  # Unknown from timeseries
                    "start_timestamp": datetime.fromtimestamp(first_point.get("ts_ms", 0) / 1000).isoformat(),
                    "end_timestamp": datetime.fromtimestamp(last_point.get("ts_ms", 0) / 1000).isoformat(),
                    "is_running": True,  # Assume running if no summary
                    "session_complete": False,
                    "source": "timeseries",
                    "timeseries": timeseries
                }
        except Exception as e:
            pass  # Fall through to audit log parsing
    
    # Try to parse paper_audit.log
    audit_log = Path("logs/paper_audit.log")
    if audit_log.exists():
        try:
            trades = []
            start_ts = None
            end_ts = None
            
            with open(audit_log, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("message") == "paper_exec":
                            trades.append({
                                "symbol": entry.get("symbol"),
                                "side": entry.get("side"),
                                "qty": entry.get("qty", 0),
                                "price": entry.get("price_used", 0),
                                "timestamp": entry.get("timestamp")
                            })
                            
                            if not start_ts:
                                start_ts = entry.get("timestamp")
                            end_ts = entry.get("timestamp")
                    except:
                        continue
            
            # Calculate approximate P&L from trades
            realized_pnl = 0
            buy_value = 0
            sell_value = 0
            
            for trade in trades:
                value = trade["qty"] * trade["price"]
                if trade["side"] == "buy":
                    buy_value += value
                else:
                    sell_value += value
            
            # Very rough P&L estimate
            if sell_value > 0:
                realized_pnl = sell_value - buy_value
            
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t["side"] == "sell")  # Simplified
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return {
                "initial_capital": 1000,
                "final_capital": 1000 + realized_pnl,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": 0,
                "total_pnl": realized_pnl,
                "pnl_percentage": (realized_pnl / 1000 * 100) if realized_pnl else 0,
                "total_trades": total_trades,
                "win_rate": win_rate,
                "start_timestamp": start_ts or datetime.now().isoformat(),
                "end_timestamp": end_ts or datetime.now().isoformat(),
                "is_running": False,
                "session_complete": False,
                "source": "audit_log"
            }
        except Exception as e:
            pass  # Fall through to default
    
    # Return default values if no data
    return {
        "initial_capital": 1000,
        "final_capital": 1000,
        "realized_pnl": 0,
        "unrealized_pnl": 0,
        "total_pnl": 0,
        "pnl_percentage": 0,
        "total_trades": 0,
        "win_rate": 0,
        "start_timestamp": datetime.now().isoformat(),
        "end_timestamp": datetime.now().isoformat(),
        "is_running": False,
        "session_complete": False,
        "source": "default"
    }


@router.get("/logs/tail")
async def get_log_tail(n: int = Query(200, ge=1, le=1000)) -> Dict[str, Any]:
    """
    Get last n lines from paper_audit.log
    """
    audit_log = Path("logs/paper_audit.log")
    
    if not audit_log.exists():
        return {
            "lines": [],
            "count": 0,
            "message": "No audit log found"
        }
    
    try:
        with open(audit_log, 'r') as f:
            lines = f.readlines()
            
        # Get last n lines
        tail_lines = lines[-n:] if len(lines) > n else lines
        
        # Parse each line if JSON, otherwise return raw
        parsed_lines = []
        for line in tail_lines:
            try:
                entry = json.loads(line.strip())
                if entry.get("message") == "paper_exec":
                    parsed_lines.append({
                        "timestamp": entry.get("timestamp", ""),
                        "symbol": entry.get("symbol", ""),
                        "side": entry.get("side", ""),
                        "qty": entry.get("qty", 0),
                        "price": entry.get("price_used", 0),
                        "type": "trade"
                    })
                else:
                    parsed_lines.append({
                        "raw": line.strip(),
                        "type": "log"
                    })
            except:
                parsed_lines.append({
                    "raw": line.strip(),
                    "type": "raw"
                })
        
        return {
            "lines": parsed_lines,
            "count": len(parsed_lines),
            "total_lines": len(lines)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log: {str(e)}")