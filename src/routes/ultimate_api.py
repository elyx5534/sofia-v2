"""
Ultimate Trading System API Routes
En iyi özellikleri birleştiren süper sistem
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from src.trading.ultimate_trading_system import (
    ExecutionMode,
    UltimateConfig,
    UltimateTradingSystem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ultimate", tags=["Ultimate Trading"])

# Global system instance
system: Optional[UltimateTradingSystem] = None


@router.post("/start")
async def start_ultimate_system(config: Optional[Dict] = None):
    """Start the ultimate trading system"""
    global system

    try:
        # Create config from params if provided
        if config:
            ultimate_config = UltimateConfig(**config)
        else:
            # Default config with Turkish Lira
            ultimate_config = UltimateConfig(
                initial_balance_try=100000.0,
                use_turkish_lira=True,
                use_real_binance_data=True,
                use_aggressive_strategies=True,
                execution_mode=ExecutionMode.FULL_AUTO,
                active_coins=[
                    "BTC/USDT",
                    "ETH/USDT",
                    "BNB/USDT",
                    "SOL/USDT",
                    "XRP/USDT",
                    "ADA/USDT",
                    "AVAX/USDT",
                    "DOGE/USDT",
                    "DOT/USDT",
                    "MATIC/USDT",
                    "SHIB/USDT",
                    "PEPE/USDT",
                    "FLOKI/USDT",
                    "BONK/USDT",
                    "WIF/USDT",
                    "MEME/USDT",
                    "ARB/USDT",
                    "OP/USDT",
                    "INJ/USDT",
                    "SEI/USDT",
                ],
            )

        system = UltimateTradingSystem(ultimate_config)
        result = await system.start()

        return {
            "message": "Ultimate Trading System started! 🚀",
            "status": "running",
            "config": {
                "currency": "TRY" if ultimate_config.use_turkish_lira else "USD",
                "balance": (
                    ultimate_config.initial_balance_try
                    if ultimate_config.use_turkish_lira
                    else ultimate_config.initial_balance_usd
                ),
                "coins": len(ultimate_config.active_coins),
                "mode": ultimate_config.execution_mode.value,
                "real_data": ultimate_config.use_real_binance_data,
                "aggressive": ultimate_config.use_aggressive_strategies,
            },
        }

    except Exception as e:
        logger.error(f"Failed to start ultimate system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_ultimate_status():
    """Get current system status"""
    global system

    if not system:
        return {"status": "stopped", "message": "System not running"}

    try:
        status = system.get_status()

        # Add real-time prices
        if system.price_cache:
            status["live_prices"] = {
                symbol: price for symbol, price in list(system.price_cache.items())[:10]
            }

        # Add market stats
        if system.market_stats:
            status["market_stats"] = system.market_stats

        return status

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_ultimate_system():
    """Stop the trading system"""
    global system

    if not system:
        return {"message": "System not running"}

    try:
        await system.stop()
        system = None

        return {"message": "Ultimate Trading System stopped", "status": "stopped"}

    except Exception as e:
        logger.error(f"Error stopping system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    """Get current positions"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    positions = []
    for symbol, pos in system.positions.items():
        current_price = system.price_cache.get(symbol, pos.avg_price)
        positions.append(
            {
                "symbol": symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_percent": ((current_price - pos.avg_price) / pos.avg_price) * 100,
            }
        )

    return {
        "positions": positions,
        "count": len(positions),
        "total_value": sum(p["quantity"] * p["current_price"] for p in positions),
    }


@router.get("/trades")
async def get_trades(limit: int = 50):
    """Get trade history"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    trades = []
    for order in system.portfolio.orders[-limit:]:
        trades.append(
            {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "price": order.filled_price or order.price,
                "status": order.status.value,
                "timestamp": order.created_at.isoformat(),
            }
        )

    return {"trades": trades, "total": len(system.portfolio.orders), "displayed": len(trades)}


@router.get("/performance")
async def get_performance():
    """Get performance metrics"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    currency = "TRY" if system.config.use_turkish_lira else "USD"
    symbol = "₺" if system.config.use_turkish_lira else "$"

    return {
        "currency": currency,
        "total_trades": system.total_trades,
        "winning_trades": system.winning_trades,
        "losing_trades": system.losing_trades,
        "win_rate": f"{system.portfolio.win_rate:.1%}",
        "total_pnl": f"{symbol}{system.total_pnl:+,.2f}",
        "best_trade": system.best_trade,
        "worst_trade": system.worst_trade,
        "current_balance": f"{symbol}{system.portfolio.balance:,.2f}",
        "total_value": f"{symbol}{system.portfolio.total_value:,.2f}",
        "roi": (
            f"{((system.portfolio.total_value - system.config.initial_balance_try) / system.config.initial_balance_try * 100):.2f}%"
            if system.config.use_turkish_lira
            else f"{((system.portfolio.total_value - system.config.initial_balance_usd) / system.config.initial_balance_usd * 100):.2f}%"
        ),
    }


@router.get("/signals")
async def get_current_signals():
    """Get current trading signals"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    # Get latest signals
    signals = await system._analyze_all_coins()

    # Sort by confidence
    sorted_signals = sorted(signals.items(), key=lambda x: x[1].get("confidence", 0), reverse=True)

    return {
        "signals": [
            {
                "symbol": symbol,
                "action": signal.get("action"),
                "confidence": signal.get("confidence"),
                "reasoning": signal.get("reasoning"),
                "price": signal.get("current_price"),
            }
            for symbol, signal in sorted_signals[:20]
        ],
        "total": len(signals),
    }


@router.post("/config/update")
async def update_config(updates: Dict):
    """Update system configuration"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    try:
        # Update config
        for key, value in updates.items():
            if hasattr(system.config, key):
                setattr(system.config, key, value)

        return {
            "message": "Configuration updated",
            "config": {
                "max_positions": system.config.max_positions,
                "risk_per_trade": system.config.risk_per_trade,
                "min_confidence": system.config.min_confidence,
                "execution_mode": system.config.execution_mode.value,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/live-prices")
async def get_live_prices():
    """Get real-time Binance prices"""
    global system

    if not system:
        raise HTTPException(status_code=400, detail="System not running")

    return {
        "prices": system.price_cache,
        "stats": system.market_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
