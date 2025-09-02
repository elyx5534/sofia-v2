"""
Strategy Lab API
Test runners and status endpoints for strategies
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import yaml
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.dev.jobs import job_runner

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyRunRequest(BaseModel):
    name: str
    mins: int = 15


def load_strategy_config():
    """Load strategy configuration"""
    config_file = Path("config/strategy_lab.yaml")
    if config_file.exists():
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    return {"strategies": {}}


def get_strategy_status(name: str) -> Dict:
    """Get status for a specific strategy"""
    # Load last run results
    report_file = Path(f"logs/{name}_last_run.json")
    
    if report_file.exists():
        with open(report_file, 'r') as f:
            last_run = json.load(f)
    else:
        last_run = {}
    
    # Load config
    config = load_strategy_config()
    strategy_config = config.get("strategies", {}).get(name, {})
    
    # Check PASS/FAIL
    passed = True
    fail_reasons = []
    
    if last_run and strategy_config.get("pass_rules"):
        rules = strategy_config["pass_rules"]
        metrics = last_run.get("metrics", {})
        
        for rule, threshold in rules.items():
            value = metrics.get(rule, 0)
            
            # Check rule
            if rule in ["maker_fill_rate", "success_rate", "win_rate"]:
                # Percentage rules (>=)
                if value < threshold:
                    passed = False
                    fail_reasons.append(f"{rule}: {value:.2f} < {threshold}")
            elif rule in ["avg_time_to_fill_ms", "avg_latency_ms"]:
                # Time rules (<)
                if value > threshold:
                    passed = False
                    fail_reasons.append(f"{rule}: {value:.0f}ms > {threshold}ms")
            elif rule in ["pnl_pct", "tl_pnl", "pnl_usdt"]:
                # P&L rules (>)
                if value <= threshold:
                    passed = False
                    fail_reasons.append(f"{rule}: {value:.2f} <= {threshold}")
            elif rule == "exposure_ratio":
                # Exposure rule (<=)
                if value > threshold:
                    passed = False
                    fail_reasons.append(f"{rule}: {value:.2f} > {threshold}")
            elif rule == "dd_pct":
                # Drawdown rule (>=, negative value)
                if value < threshold:
                    passed = False
                    fail_reasons.append(f"{rule}: {value:.2f}% < {threshold}%")
    
    return {
        "name": name,
        "enabled": strategy_config.get("enabled", False),
        "last_run_ts": last_run.get("timestamp"),
        "last_pnl": last_run.get("metrics", {}).get("pnl_pct", 0),
        "last_winrate": last_run.get("metrics", {}).get("win_rate", 0),
        "last_pass": passed,
        "reason": " | ".join(fail_reasons) if fail_reasons else "All rules passed"
    }


@router.post("/run")
async def run_strategy(request: StrategyRunRequest):
    """Run a strategy test"""
    config = load_strategy_config()
    
    if request.name not in config.get("strategies", {}):
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.name}")
    
    strategy_config = config["strategies"][request.name]
    
    if not strategy_config.get("enabled", False):
        raise HTTPException(status_code=400, detail=f"Strategy {request.name} is disabled")
    
    # Build command
    cmd = strategy_config["command"].copy()
    
    # Replace duration if specified
    for i, arg in enumerate(cmd):
        if arg == "15":
            cmd[i] = str(request.mins)
    
    # Spawn job
    try:
        job_id = await job_runner.spawn_job(cmd, family=f"strategy_{request.name}")
        
        return {
            "job_id": job_id,
            "strategy": request.name,
            "duration_mins": request.mins,
            "status": "started"
        }
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start strategy: {e}")


@router.get("/status")
async def get_all_strategies_status():
    """Get status for all strategies"""
    config = load_strategy_config()
    strategies = config.get("strategies", {})
    
    status_list = []
    for name in strategies.keys():
        status_list.append(get_strategy_status(name))
    
    return {
        "strategies": status_list,
        "timestamp": datetime.now().isoformat()
    }