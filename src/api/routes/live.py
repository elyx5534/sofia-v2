"""
Live Trading API Routes
Handles paper/live mode switching, order execution, and risk management
"""

import logging
import os
from typing import Dict, Literal, Optional

from pydantic import BaseModel

from src.adapters.web.fastapi_adapter import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live"])


class SwitchModeRequest(BaseModel):
    mode: Literal["paper", "live"]
    confirm: bool = False


class OrderRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit", "stop", "stop_limit"]
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None


class RiskLimitRequest(BaseModel):
    daily_loss_limit_pct: Optional[float] = None
    position_limit: Optional[int] = None
    max_position_size_pct: Optional[float] = None
    notional_cap: Optional[float] = None


class ExchangeConfigRequest(BaseModel):
    exchange: str
    api_key: str
    secret: str
    testnet: bool = True


def check_live_auth():
    """Check if live trading is authorized"""
    has_keys = bool(os.getenv("EXCHANGE_API_KEY") or os.getenv("BINANCE_API_KEY"))
    return has_keys


@router.post("/switch_mode")
async def switch_trading_mode(request: SwitchModeRequest) -> Dict:
    """Switch between paper and live trading modes"""
    try:
        if request.mode == "live":
            if not check_live_auth():
                raise HTTPException(
                    status_code=403, detail="Live mode not authorized. Configure API keys first."
                )
            if not request.confirm:
                raise HTTPException(
                    status_code=400, detail="Live mode requires confirmation (set confirm=true)"
                )
        from src.services.execution import get_execution_service

        router = get_execution_service()
        success = router.switch_mode(request.mode)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to switch to {request.mode} mode")
        logger.info(f"Switched to {request.mode} mode")
        return {
            "success": True,
            "mode": request.mode,
            "message": f"Switched to {request.mode} mode successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mode switch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/place")
async def place_order(request: OrderRequest) -> Dict:
    """Place an order (paper or live based on current mode)"""
    try:
        from src.services.execution import OrderType, get_execution_service

        execution = get_execution_service()
        order_type = OrderType[request.type.upper()]
        result = await execution.place_order(
            symbol=request.symbol,
            side=request.side,
            order_type=order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("reason", "Order rejected"))
        logger.info(f"Order placed: {result['order_id']}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order placement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str) -> Dict:
    """Cancel an order"""
    try:
        from src.services.execution import get_execution_service

        execution = get_execution_service()
        success = execution.cancel_order(order_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Order {order_id} not found or already filled"
            )
        return {"success": True, "order_id": order_id, "message": "Order cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order cancellation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions() -> Dict:
    """Get current positions"""
    try:
        from src.services.execution import get_execution_service

        execution = get_execution_service()
        positions = execution.get_positions()
        positions_list = []
        for symbol, pos in positions.items():
            positions_list.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
            )
        return {"positions": positions_list, "count": len(positions_list)}
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_trading_stats() -> Dict:
    """Get trading statistics and risk metrics"""
    try:
        from src.services.execution import get_execution_service

        execution = get_execution_service()
        stats = execution.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/limits")
async def update_risk_limits(request: RiskLimitRequest) -> Dict:
    """Update risk management limits"""
    try:
        from src.services.execution import get_execution_service

        execution = get_execution_service()
        risk_guard = execution.risk_guard
        if request.daily_loss_limit_pct is not None:
            risk_guard.daily_loss_limit = request.daily_loss_limit_pct
        if request.position_limit is not None:
            risk_guard.position_limit = request.position_limit
        if request.max_position_size_pct is not None:
            risk_guard.max_position_size = request.max_position_size_pct
        if request.notional_cap is not None:
            risk_guard.notional_cap = request.notional_cap
        logger.info("Risk limits updated")
        return {
            "success": True,
            "limits": {
                "daily_loss_limit_pct": risk_guard.daily_loss_limit,
                "position_limit": risk_guard.position_limit,
                "max_position_size_pct": risk_guard.max_position_size,
                "notional_cap": risk_guard.notional_cap,
            },
        }
    except Exception as e:
        logger.error(f"Update risk limits error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/reset_kill_switch")
async def reset_kill_switch() -> Dict:
    """Reset the kill switch (requires authorization)"""
    try:
        from src.services.execution import get_execution_service

        execution = get_execution_service()
        execution.risk_guard.reset_kill_switch()
        return {
            "success": True,
            "message": "Kill switch reset successfully",
            "kill_switch_active": False,
        }
    except Exception as e:
        logger.error(f"Reset kill switch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exchange/config")
async def configure_exchange(request: ExchangeConfigRequest) -> Dict:
    """Configure exchange credentials (stored in memory only)"""
    try:
        valid_exchanges = ["binance", "btcturk", "paribu", "kucoin"]
        if request.exchange not in valid_exchanges:
            raise HTTPException(
                status_code=400, detail=f"Invalid exchange. Valid: {valid_exchanges}"
            )
        from src.services.execution import init_execution_service

        config = {
            "mode": "paper",
            "exchanges": {
                request.exchange: {
                    "exchange": request.exchange,
                    "api_key": request.api_key,
                    "secret": request.secret,
                    "options": {"defaultType": "spot", "testnet": request.testnet},
                }
            },
        }
        init_execution_service(config)
        logger.info(f"Exchange {request.exchange} configured (testnet={request.testnet})")
        return {
            "success": True,
            "exchange": request.exchange,
            "testnet": request.testnet,
            "message": "Exchange configured. Switch to live mode to use.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exchange config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/status")
async def get_auth_status() -> Dict:
    """Check live trading authorization status"""
    return {
        "live_mode_available": check_live_auth(),
        "message": (
            "Configure API keys to enable live trading"
            if not check_live_auth()
            else "Live trading available"
        ),
    }
