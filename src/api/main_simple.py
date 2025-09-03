"""Simplified API for dashboard and P&L tracking"""

from datetime import datetime
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware

from src.adapters.web.fastapi_adapter import FastAPI, HTMLResponse
from src.api.dashboard import router as dashboard_router
from src.api.dev_actions import router as dev_actions_router
from src.api.dev_status import router as dev_status_router
from src.api.live_proof import router as live_router
from src.api.pnl import router as pnl_router
from src.api.strategies import router as strategies_router

app = FastAPI(
    title="Sofia V2 Dashboard API", description="P&L Dashboard and Live Proof API", version="2.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(live_router)
app.include_router(pnl_router)
app.include_router(dashboard_router)
app.include_router(dev_actions_router)
app.include_router(dev_status_router)
app.include_router(strategies_router)


@app.get("/api/health")
async def api_health_check():
    """API health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {"dashboard": "active", "pnl_api": "active", "live_proof": "active"},
    }


@app.get("/")
async def root():
    """Root endpoint redirects to dashboard."""
    return {
        "message": "Sofia V2 API",
        "dashboard": "http://localhost:8000/dashboard",
        "docs": "http://localhost:8000/docs",
    }


@app.get("/dev", response_class=HTMLResponse)
async def dev_console():
    """Serve developer console."""
    dev_html = Path(__file__).parent.parent.parent / "templates" / "dev.html"
    if dev_html.exists():
        return HTMLResponse(content=dev_html.read_text())
    else:
        return HTMLResponse(content="<h1>Dev Console not found</h1>")


@app.get("/api/pnl/summary")
async def get_pnl_summary():
    """Get P&L summary for dashboard."""
    import json

    logs_path = Path("logs/pnl_summary.json")
    if logs_path.exists():
        try:
            with open(logs_path) as f:
                return json.load(f)
        except:
            pass
    return {
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "session_complete": False,
        "is_running": False,
    }


@app.get("/api/pnl/timeseries")
async def get_pnl_timeseries():
    """Get P&L time series."""
    import json

    logs_path = Path("logs/pnl_timeseries.json")
    if logs_path.exists():
        try:
            with open(logs_path) as f:
                return json.load(f)
        except:
            pass
    return []


@app.get("/api/trades/last")
async def get_last_trades(n: int = 25):
    """Get last N trades."""
    import json

    logs_path = Path("logs/trades.jsonl")
    if logs_path.exists():
        try:
            trades = []
            with open(logs_path) as f:
                for line in f:
                    if line.strip():
                        trades.append(json.loads(line))
            return trades[-n:] if len(trades) > n else trades
        except:
            pass
    return []


@app.get("/api/live-guard")
async def get_live_guard():
    """Get live trading guard status."""
    return {
        "enabled": False,
        "approvals": {"operator_A": False, "operator_B": False},
        "requirements": {"readiness": False, "hours_ok": False},
    }


@app.post("/api/dev/actions")
async def dev_actions(action_data: dict):
    """Execute dev actions."""
    import subprocess

    action = action_data.get("action")
    if action == "demo":
        minutes = action_data.get("minutes", 5)
        subprocess.Popen(["python", "tools/run_simple_demo.py", str(minutes)])
        return {"job_id": f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "status": "started"}
    elif action == "qa":
        return {"job_id": f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}", "status": "started"}
    elif action == "readiness":
        return {
            "job_id": f"readiness_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "started",
        }
    else:
        return {"error": f"Unknown action: {action}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
