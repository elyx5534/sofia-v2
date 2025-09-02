"""
Live Pilot Status Monitor
Real-time status of micro live pilot
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict


def get_pilot_status() -> Dict:
    """Get comprehensive pilot status"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "mode": "UNKNOWN",
        "live_enabled": False,
        "strategy": None,
        "caps": {},
        "usage": {},
        "pnl": {},
        "watchdog": "UNKNOWN",
        "positions": [],
        "alerts": []
    }
    
    # Check live config
    config_file = Path("config/live.yaml")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        status["live_enabled"] = config.get("enable_real_trading", False)
        status["mode"] = "LIVE" if status["live_enabled"] else "PAPER"
        status["strategy"] = config.get("whitelisted_strategies", [])
        status["caps"] = {
            "per_trade_tl": config.get("per_trade_tl_cap", 0),
            "max_notional_tl": config.get("max_notional_tl", 0),
            "max_daily_loss_tl": config.get("safety", {}).get("max_daily_loss_tl", 0)
        }
        
        # Check approvals
        approvals = config.get("approvals", {})
        if not all(approvals.values()):
            status["alerts"].append("MISSING OPERATOR APPROVALS")
    
    # Check current usage
    try:
        usage_file = Path("logs/live_usage.json")
        if usage_file.exists():
            with open(usage_file, 'r') as f:
                usage = json.load(f)
            
            status["usage"] = {
                "trades_today": usage.get("trades_today", 0),
                "notional_used_tl": usage.get("notional_used_tl", 0),
                "notional_remaining_tl": status["caps"]["max_notional_tl"] - usage.get("notional_used_tl", 0),
                "daily_loss_tl": usage.get("daily_loss_tl", 0)
            }
    except:
        status["usage"] = {
            "trades_today": 0,
            "notional_used_tl": 0,
            "notional_remaining_tl": status["caps"].get("max_notional_tl", 0),
            "daily_loss_tl": 0
        }
    
    # Check P&L
    try:
        pnl_file = Path("logs/live_pnl.json")
        if pnl_file.exists():
            with open(pnl_file, 'r') as f:
                pnl = json.load(f)
            
            status["pnl"] = {
                "today_tl": pnl.get("today_tl", 0),
                "total_tl": pnl.get("total_tl", 0),
                "win_rate": pnl.get("win_rate", 0),
                "trades_won": pnl.get("trades_won", 0),
                "trades_lost": pnl.get("trades_lost", 0)
            }
    except:
        status["pnl"] = {
            "today_tl": 0,
            "total_tl": 0,
            "win_rate": 0,
            "trades_won": 0,
            "trades_lost": 0
        }
    
    # Check watchdog
    try:
        watchdog_file = Path("logs/watchdog_status.json")
        if watchdog_file.exists():
            with open(watchdog_file, 'r') as f:
                watchdog = json.load(f)
            
            status["watchdog"] = watchdog.get("status", "UNKNOWN")
            
            if watchdog.get("alerts"):
                status["alerts"].extend(watchdog["alerts"])
    except:
        status["watchdog"] = "OFFLINE"
        status["alerts"].append("WATCHDOG OFFLINE")
    
    # Check open positions
    try:
        positions_file = Path("logs/open_positions.json")
        if positions_file.exists():
            with open(positions_file, 'r') as f:
                positions = json.load(f)
            
            status["positions"] = positions
    except:
        status["positions"] = []
    
    # Check for critical alerts
    if status["usage"].get("daily_loss_tl", 0) < -status["caps"].get("max_daily_loss_tl", 100):
        status["alerts"].append("DAILY LOSS LIMIT EXCEEDED")
    
    if status["usage"].get("notional_remaining_tl", 0) < 100:
        status["alerts"].append("LOW NOTIONAL REMAINING")
    
    if len(status["positions"]) > 2:
        status["alerts"].append("TOO MANY OPEN POSITIONS")
    
    return status


def print_status(status: Dict):
    """Print formatted status"""
    print("="*60)
    print(" LIVE PILOT STATUS")
    print("="*60)
    print(f"Timestamp: {status['timestamp']}")
    print(f"Mode: {status['mode']}")
    
    if status["mode"] == "LIVE":
        print("\n" + "⚠️"*20)
        print(" LIVE TRADING ACTIVE")
        print("⚠️"*20)
    
    print("\nCONFIGURATION:")
    print(f"  Strategy: {status['strategy']}")
    print(f"  Per Trade Cap: {status['caps']['per_trade_tl']} TL")
    print(f"  Max Notional: {status['caps']['max_notional_tl']} TL")
    print(f"  Max Daily Loss: {status['caps']['max_daily_loss_tl']} TL")
    
    print("\nUSAGE:")
    print(f"  Trades Today: {status['usage']['trades_today']}")
    print(f"  Notional Used: {status['usage']['notional_used_tl']} TL")
    print(f"  Notional Remaining: {status['usage']['notional_remaining_tl']} TL")
    print(f"  Daily Loss: {status['usage']['daily_loss_tl']} TL")
    
    print("\nP&L:")
    print(f"  Today: {status['pnl']['today_tl']} TL")
    print(f"  Total: {status['pnl']['total_tl']} TL")
    print(f"  Win Rate: {status['pnl']['win_rate']:.1f}%")
    print(f"  Wins/Losses: {status['pnl']['trades_won']}/{status['pnl']['trades_lost']}")
    
    print(f"\nWATCHDOG: {status['watchdog']}")
    
    print(f"\nOPEN POSITIONS: {len(status['positions'])}")
    for pos in status['positions']:
        print(f"  - {pos.get('symbol')}: {pos.get('side')} {pos.get('size')} @ {pos.get('price')}")
    
    if status["alerts"]:
        print("\n" + "🔴"*20)
        print(" ALERTS")
        print("🔴"*20)
        for alert in status["alerts"]:
            print(f"  ! {alert}")
    else:
        print("\n✅ No alerts")
    
    print("="*60)


def save_status(status: Dict):
    """Save status to file"""
    status_file = Path("logs/pilot_status.json")
    status_file.parent.mkdir(exist_ok=True)
    
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)
    
    print(f"\nStatus saved: {status_file}")


def main():
    """Main entry point"""
    status = get_pilot_status()
    print_status(status)
    save_status(status)
    
    # Return non-zero if alerts
    if status["alerts"]:
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())