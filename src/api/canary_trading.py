"""
Canary Trading API Endpoints
"""

import logging
from datetime import datetime

from pydantic import BaseModel

from src.adapters.web.fastapi_adapter import APIRouter, BackgroundTasks, HTTPException
from src.canary.orchestrator import CanaryOrchestrator, TradingMode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/canary", tags=["canary_trading"])
canary_orchestrator = CanaryOrchestrator()


class TradingModeRequest(BaseModel):
    mode: str


class CapitalAdjustment(BaseModel):
    capital_pct: float
    reason: str


@router.post("/settings/trading_mode")
async def set_canary_mode(request: TradingModeRequest, background_tasks: BackgroundTasks):
    """Set canary trading mode"""
    global canary_orchestrator
    try:
        if request.mode not in ["shadow", "canary", "live", "off"]:
            raise HTTPException(
                status_code=400, detail="Invalid mode. Use 'shadow', 'canary', 'live', or 'off'"
            )
        if request.mode == "off":
            result = await canary_orchestrator.stop_canary()
            return {"status": "success", "message": "Canary trading stopped", "mode": "off"}
        mode_enum = TradingMode(request.mode)
        background_tasks.add_task(canary_orchestrator.start_canary, mode_enum)
        return {
            "status": "starting",
            "message": f"Canary trading starting in {request.mode} mode",
            "mode": request.mode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to set canary mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_canary_status():
    """Get canary trading status"""
    global canary_orchestrator
    try:
        status = canary_orchestrator.get_canary_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get canary status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gates")
async def get_gates_status():
    """Get detailed gates status"""
    global canary_orchestrator
    try:
        performance = await canary_orchestrator._evaluate_canary_performance()
        gates = canary_orchestrator._check_gates(performance)
        gates_detail = {}
        for gate_name, passed in gates.items():
            gates_detail[gate_name] = {
                "passed": passed,
                "current_value": performance.get(
                    gate_name.replace("_acceptable", "")
                    .replace("_positive", "")
                    .replace("_low", "")
                ),
                "threshold": None,
            }
        return {
            "gates": gates_detail,
            "overall_status": "pass" if all(gates.values()) else "fail",
            "failed_gates": [name for name, passed in gates.items() if not passed],
            "evaluation_period_hours": canary_orchestrator.config["EVALUATION_HOURS"],
        }
    except Exception as e:
        logger.error(f"Failed to get gates status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capital/adjust")
async def adjust_capital(request: CapitalAdjustment):
    """Manually adjust capital allocation"""
    global canary_orchestrator
    try:
        if not 0 <= request.capital_pct <= 100:
            raise HTTPException(status_code=400, detail="Capital percentage must be between 0-100")
        old_capital = canary_orchestrator.state.capital_pct
        canary_orchestrator.state.capital_pct = request.capital_pct
        canary_orchestrator.state.auto_ramp_enabled = False
        logger.info(
            f"Manual capital adjustment: {old_capital:.1f}% → {request.capital_pct:.1f}% ({request.reason})"
        )
        return {
            "status": "success",
            "message": f"Capital adjusted from {old_capital:.1f}% to {request.capital_pct:.1f}%",
            "old_capital_pct": old_capital,
            "new_capital_pct": request.capital_pct,
            "auto_ramp_disabled": True,
            "reason": request.reason,
        }
    except Exception as e:
        logger.error(f"Failed to adjust capital: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ramp/enable")
async def enable_auto_ramp():
    """Re-enable automatic ramping"""
    global canary_orchestrator
    canary_orchestrator.state.auto_ramp_enabled = True
    return {"status": "success", "message": "Automatic capital ramping re-enabled"}


@router.get("/performance")
async def get_performance_metrics(hours: int = 24):
    """Get detailed performance metrics"""
    global canary_orchestrator
    try:
        performance = await canary_orchestrator._evaluate_canary_performance()
        execution_metrics = canary_orchestrator.execution_engine.get_execution_report(hours)
        return {
            "period_hours": hours,
            "trading_performance": performance,
            "execution_quality": execution_metrics,
            "capital_utilization": canary_orchestrator.state.capital_pct,
            "mode": canary_orchestrator.state.mode.value,
        }
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/weights")
async def get_current_portfolio_weights():
    """Get current portfolio weights"""
    global canary_orchestrator
    try:
        weights = await canary_orchestrator._load_portfolio_weights()
        if weights:
            return {
                "weights": weights,
                "n_positions": len([w for w in weights.values() if w > 0.001]),
                "last_update": datetime.now().isoformat(),
                "method": canary_orchestrator.portfolio_constructor.method,
            }
        else:
            return {
                "error": "No portfolio weights available",
                "message": "Run portfolio construction first",
            }
    except Exception as e:
        logger.error(f"Failed to get portfolio weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/report")
async def get_execution_report(hours: int = 24):
    """Get execution quality report"""
    global canary_orchestrator
    try:
        report = canary_orchestrator.execution_engine.get_execution_report(hours)
        return report
    except Exception as e:
        logger.error(f"Failed to get execution report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kill-switch")
async def activate_canary_kill_switch():
    """Activate emergency kill switch"""
    global canary_orchestrator
    try:
        canary_orchestrator.state.kill_switch_active = True
        result = await canary_orchestrator.stop_canary()
        return {
            "status": "success",
            "message": "Canary kill switch activated - all trading stopped",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to activate kill switch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/widgets/capital-allocation")
async def get_widget_capital_allocation():
    """Widget: Current capital allocation"""
    status = canary_orchestrator.get_canary_status()
    return {
        "value": f"{status['capital_pct']:.1f}%",
        "label": "Capital Allocation",
        "mode": status["mode"],
        "day": status["days_running"],
        "data_testid": "canary-capital-allocation",
    }


@router.get("/widgets/gates-status")
async def get_widget_gates_status():
    """Widget: Gates status overview"""
    status = canary_orchestrator.get_canary_status()
    gates = status.get("gates_status", {})
    passed_gates = sum(1 for passed in gates.values() if passed)
    total_gates = len(gates)
    return {
        "value": f"{passed_gates}/{total_gates}",
        "label": "Gates Passing",
        "status": "healthy" if passed_gates == total_gates else "warning",
        "data_testid": "canary-gates-status",
    }


@router.get("/widgets/execution-quality")
async def get_widget_execution_quality():
    """Widget: Execution quality summary"""
    try:
        report = canary_orchestrator.execution_engine.get_execution_report(6)
        slippage_ok = report.get("gate_status", {}).get("slippage_p95_ok", True)
        return {
            "value": f"{report.get('p95_slippage_bps', 0):.1f}bps",
            "label": "P95 Slippage",
            "status": "healthy" if slippage_ok else "warning",
            "executions": report.get("total_executions", 0),
            "data_testid": "canary-execution-quality",
        }
    except Exception as e:
        return {
            "value": "N/A",
            "label": "P95 Slippage",
            "status": "error",
            "error": str(e),
            "data_testid": "canary-execution-quality",
        }
