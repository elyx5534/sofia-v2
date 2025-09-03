"""
Developer Status API
System health and live guard status
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.adapters.web.fastapi_adapter import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.core.live_switch import live_switch

router = APIRouter(prefix="/api", tags=["status"])


def get_git_sha():
    """Get current git SHA"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"


def check_service_health(url: str) -> str:
    """Check if a service is healthy"""
    try:
        import requests

        response = requests.get(url, timeout=2)
        return "ACTIVE" if response.status_code == 200 else "DOWN"
    except:
        return "DOWN"


@router.get("/dev/status")
async def get_system_status():
    """Get overall system status"""
    api_status = check_service_health("http://localhost:8001/health")
    dashboard_status = check_service_health("http://localhost:5000/api/status")
    watchdog_status = "RUNNING"
    paper_status = "IDLE"
    return {
        "api": api_status,
        "watchdog": watchdog_status,
        "paper": paper_status,
        "dashboard": dashboard_status,
        "git_sha": get_git_sha(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/live-guard")
async def get_live_guard_status():
    """Get live trading guard status"""
    guard_status = live_switch.get_guard_status()
    if not guard_status["main_switch"]:
        mode = "PAPER"
    elif not guard_status["approvals"].get("operator_A") or not guard_status["approvals"].get(
        "operator_B"
    ):
        mode = "SHADOW"
    elif guard_status["live_enabled"]:
        mode = "LIVE"
    else:
        mode = "PILOT"
    blockers = guard_status.get("reasons", [])
    requirements = {
        "readiness": guard_status.get("requirements_met", False),
        "two_man": guard_status["approvals"].get("operator_A", False)
        and guard_status["approvals"].get("operator_B", False),
        "caps_ok": True,
        "hours_ok": guard_status.get("in_trading_hours", False),
    }
    return {
        "enabled": guard_status["live_enabled"],
        "approvals": guard_status["approvals"],
        "requirements": requirements,
        "blockers": blockers,
        "mode": mode,
        "limits": guard_status["limits"],
        "whitelisted_symbols": guard_status["whitelisted_symbols"],
        "timestamp": guard_status["timestamp"],
    }
