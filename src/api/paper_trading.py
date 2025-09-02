"""
Paper Trading API Endpoints
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from scripts.paper_replay import PaperReplay
from src.paper.runner import PaperTradingRunner
from src.reports.paper_report import PaperTradingReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paper", tags=["paper_trading"])

# Global paper trading runner instance
paper_runner = None
paper_report = None


class TradingModeRequest(BaseModel):
    mode: str  # 'paper' or 'off'


class PaperTradingState(BaseModel):
    status: str
    mode: str
    balance: str
    total_pnl: str
    daily_pnl: str
    unrealized_pnl: str
    positions_count: int
    trade_count: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    k_factor: str
    timestamp: str


class ReplayRequest(BaseModel):
    hours: int = 24


@router.post("/settings/trading_mode")
async def set_trading_mode(request: TradingModeRequest, background_tasks: BackgroundTasks):
    """Set paper trading mode ON/OFF"""
    global paper_runner, paper_report

    try:
        if request.mode == "paper":
            if paper_runner and paper_runner.running:
                return {"status": "already_running", "message": "Paper trading is already running"}

            # Start paper trading
            paper_runner = PaperTradingRunner()
            paper_report = PaperTradingReport(runner=paper_runner)

            # Start in background
            background_tasks.add_task(paper_runner.run)

            # Wait a moment for initialization
            await asyncio.sleep(2)

            return {"status": "success", "message": "Paper trading started", "mode": "paper"}

        elif request.mode == "off":
            if paper_runner:
                await paper_runner.stop()
                paper_runner = None
                paper_report = None

            return {"status": "success", "message": "Paper trading stopped", "mode": "off"}
        else:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'paper' or 'off'")

    except Exception as e:
        logger.error(f"Failed to set trading mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state")
async def get_paper_trading_state() -> PaperTradingState:
    """Get current paper trading state"""
    global paper_runner, paper_report

    if not paper_runner:
        return PaperTradingState(
            status="not_started",
            mode="off",
            balance=os.getenv("PAPER_INITIAL_BALANCE", "10000"),
            total_pnl="0",
            daily_pnl="0",
            unrealized_pnl="0",
            positions_count=0,
            trade_count=0,
            win_rate=0,
            sharpe_ratio=0,
            max_drawdown=0,
            k_factor=os.getenv("K_FACTOR", "0.25"),
            timestamp=datetime.now().isoformat(),
        )

    # Get live metrics from report
    if paper_report:
        metrics = paper_report.get_live_metrics()
    else:
        state = paper_runner.get_state()
        metrics = {
            "status": "running" if state.get("running", False) else "stopped",
            "balance": state["balance"],
            "cumulative_pnl": state["total_pnl"],
            "daily_pnl": state["daily_pnl"],
            "unrealized_pnl": state.get("unrealized_pnl", "0"),
            "positions_count": len(state["positions"]),
            "trade_count": state["trade_count"],
            "win_rate": state.get("win_rate", 0),
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "k_factor": state.get("k_factor", "0.25"),
        }

    return PaperTradingState(
        status=metrics["status"],
        mode="paper" if metrics["status"] == "running" else "off",
        balance=metrics["balance"],
        total_pnl=metrics["cumulative_pnl"],
        daily_pnl=metrics["daily_pnl"],
        unrealized_pnl=metrics.get("unrealized_pnl", "0"),
        positions_count=metrics["positions_count"],
        trade_count=metrics["trade_count"],
        win_rate=metrics["win_rate"],
        sharpe_ratio=metrics.get("sharpe_ratio", 0),
        max_drawdown=metrics.get("max_drawdown", 0),
        k_factor=metrics.get("k_factor", "0.25"),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/metrics")
async def get_paper_trading_metrics() -> Dict[str, Any]:
    """Get detailed paper trading metrics"""
    global paper_report

    if not paper_report:
        return {"error": "Paper trading not running"}

    return paper_report.get_live_metrics()


@router.get("/positions")
async def get_positions() -> List[Dict[str, Any]]:
    """Get current open positions"""
    global paper_runner

    if not paper_runner:
        return []

    state = paper_runner.get_state()
    return list(state["positions"].values())


@router.get("/trades")
async def get_trades(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent trades"""
    global paper_runner

    if not paper_runner:
        return []

    trades = []
    for order in paper_runner.orders[-limit:]:
        trades.append(
            {
                "timestamp": order.timestamp.isoformat(),
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": str(order.quantity),
                "price": str(order.price),
                "filled_price": str(order.filled_price),
                "fees": str(order.fees),
                "slippage": str(order.slippage),
                "status": order.status,
            }
        )

    return trades


@router.post("/replay")
async def run_replay_simulation(request: ReplayRequest, background_tasks: BackgroundTasks):
    """Run accelerated replay simulation for quick profitability check"""
    try:
        replay = PaperReplay(hours=request.hours)

        # Run replay asynchronously
        async def run_replay_task():
            report = await replay.run_replay()
            return report

        # Start in background
        background_tasks.add_task(run_replay_task)

        return {
            "status": "started",
            "message": f"Replay simulation started for {request.hours} hours",
            "report_path": "reports/paper/replay_report.json",
            "quickcheck_path": "reports/paper/quickcheck.html",
        }

    except Exception as e:
        logger.error(f"Failed to start replay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/status")
async def get_replay_status():
    """Get status of replay simulation"""
    import json
    import os

    report_file = "reports/paper/replay_report.json"

    if not os.path.exists(report_file):
        return {"status": "not_found", "message": "No replay report found"}

    try:
        with open(report_file) as f:
            report = json.load(f)

        return {
            "status": "completed",
            "timestamp": report["timestamp"],
            "is_profitable": report["profitability"]["is_profitable"],
            "total_pnl": report["results"]["total_pnl"],
            "return_pct": report["results"]["return_pct"],
            "win_rate": report["results"]["win_rate"],
            "trades_executed": report["results"]["trades_executed"],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/report/generate")
async def generate_report(background_tasks: BackgroundTasks):
    """Generate EOD report"""
    global paper_report

    if not paper_report:
        raise HTTPException(status_code=400, detail="Paper trading not running")

    try:
        # Generate in background
        background_tasks.add_task(paper_report.generate_eod_report)
        background_tasks.add_task(paper_report.generate_csv_report)

        return {"status": "generating", "message": "Report generation started"}
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_profitability_alerts() -> Optional[Dict[str, Any]]:
    """Get profitability alerts if any"""
    global paper_report

    if not paper_report:
        return None

    return paper_report.check_profitability_alert()


@router.post("/kill-switch")
async def activate_kill_switch():
    """Emergency stop for paper trading"""
    global paper_runner

    if not paper_runner:
        return {"status": "not_running", "message": "Paper trading is not running"}

    try:
        # Immediate stop
        paper_runner.kill_switch = True
        await paper_runner.stop()

        return {"status": "success", "message": "Kill switch activated - paper trading stopped"}
    except Exception as e:
        logger.error(f"Failed to activate kill switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard widget endpoints for auto-refresh
@router.get("/widgets/pnl-total")
async def get_widget_pnl_total():
    """Widget: Total P&L"""
    state = await get_paper_trading_state()
    return {
        "value": state.total_pnl,
        "label": "Total P&L",
        "change_pct": (
            (float(state.total_pnl) / float(state.balance) * 100) if float(state.balance) > 0 else 0
        ),
        "data_testid": "paper-pnl-total",
    }


@router.get("/widgets/pnl-daily")
async def get_widget_pnl_daily():
    """Widget: Daily P&L"""
    state = await get_paper_trading_state()
    return {"value": state.daily_pnl, "label": "Daily P&L", "data_testid": "paper-pnl-daily"}


@router.get("/widgets/positions-count")
async def get_widget_positions_count():
    """Widget: Open Positions"""
    state = await get_paper_trading_state()
    return {
        "value": state.positions_count,
        "label": "Open Positions",
        "data_testid": "paper-positions-count",
    }


@router.get("/widgets/trades-today")
async def get_widget_trades_today():
    """Widget: Trades Today"""
    global paper_runner

    if not paper_runner:
        return {"value": 0, "label": "Trades Today", "data_testid": "paper-trades-today"}

    # Count today's trades
    from datetime import date

    today = date.today()
    today_trades = sum(1 for order in paper_runner.orders if order.timestamp.date() == today)

    return {"value": today_trades, "label": "Trades Today", "data_testid": "paper-trades-today"}
