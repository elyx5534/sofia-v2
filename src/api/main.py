"""
Main API application with real-data endpoints.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.services.price_service_real import get_price_service
from src.trading.paper_engine import get_paper_engine
from src.strategies.micro_momo import get_micro_momentum_strategy
from src.strategies.advanced_momentum import get_advanced_momentum_strategy
from src.indicators.technical_analysis import get_technical_indicators
from src.dashboard.realtime_monitor import get_realtime_monitor
from src.database.models import get_database

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sofia V2 Real-Data Trading API",
    description="Production API with real Binance data",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class PaperOrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    usd_amount: float

class StrategyToggleRequest(BaseModel):
    enabled: bool

# Startup/shutdown
@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    logger.info("Starting Sofia V2 API with real-data support")
    
    # Initialize database
    db = get_database()
    account = db.get_account_state()
    if not account:
        db.seed_initial_balance(100000.0)
        logger.info("Database seeded with $100k")
    
    # Start price service with WebSocket
    price_service = await get_price_service()
    logger.info("Price service started")
    
    # Start real-time monitor
    try:
        monitor = get_realtime_monitor()
        await monitor.start()
        logger.info("Real-time monitor started")
    except Exception as e:
        logger.warning(f"Real-time monitor failed to start: {e}")
    
    logger.info("Sofia V2 API startup complete")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    try:
        price_service = await get_price_service()
        await price_service.stop()
    except:
        pass
    
    logger.info("Sofia V2 API shutdown complete")

# Core endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - startup_time if 'startup_time' in globals() else 0
    
    return {
        "status": "ok",
        "version": "1.0.0-real-data",
        "git_sha": os.getenv("GIT_SHA", "unknown"),
        "uptime_seconds": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/metrics")
async def metrics():
    """Metrics endpoint - JSON format for simplicity."""
    try:
        price_service = await get_price_service()
        metrics_data = price_service.get_metrics()
        
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price_freshness_seconds": metrics_data.get("freshness_seconds", {}),
            "tick_counts": metrics_data.get("tick_counts", {}),
            "data_errors_total": metrics_data.get("error_count", 0),
            "service_running": metrics_data.get("service_running", False),
            "websocket_connected": metrics_data.get("websocket_connected", False),
            "websocket_enabled": metrics_data.get("websocket_enabled", False)
        }
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {
            "status": "error", 
            "message": "Metrics unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Trading endpoints
@app.get("/api/trading/portfolio")
async def get_portfolio():
    """Get current portfolio with live P&L."""
    try:
        engine = get_paper_engine()
        portfolio = await engine.get_portfolio_summary()
        
        # Add base currency for consistency
        portfolio["base_currency"] = "USD"
        
        return {
            "status": "success",
            "data": portfolio,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Portfolio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/positions")
async def get_positions():
    """Get current positions."""
    try:
        engine = get_paper_engine()
        portfolio = await engine.get_portfolio_summary()
        
        return {
            "status": "success",
            "data": portfolio["positions"],
            "summary": {
                "total_pnl": portfolio["total_pnl"],
                "unrealized_pnl": portfolio["unrealized_pnl"],
                "realized_pnl": portfolio["realized_pnl"]
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trading/paper-order")
async def place_paper_order(order: PaperOrderRequest):
    """Place manual paper trading order."""
    try:
        engine = get_paper_engine()
        
        result = await engine.place_order(
            symbol=order.symbol,
            side=order.side,
            usd_amount=order.usd_amount,
            strategy="manual"
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "status": "success",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Paper order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Strategy endpoints
@app.post("/api/strategy/micro-momo/enable")
async def toggle_micro_momentum(request: StrategyToggleRequest):
    """Enable/disable micro momentum strategy."""
    try:
        strategy = get_micro_momentum_strategy()
        
        if request.enabled:
            result = await strategy.start()
        else:
            result = strategy.stop()
        
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Strategy toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategy/micro-momo/status")
async def get_micro_momentum_status():
    """Get micro momentum strategy status."""
    try:
        strategy = get_micro_momentum_strategy()
        status = strategy.get_status()
        
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"Strategy status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Advanced strategy endpoints
@app.post("/api/strategy/advanced/enable")
async def toggle_advanced_momentum(request: StrategyToggleRequest):
    """Enable/disable advanced momentum strategy."""
    try:
        strategy = get_advanced_momentum_strategy()
        
        if request.enabled:
            result = await strategy.start()
        else:
            result = strategy.stop()
        
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Advanced strategy toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategy/advanced/status")
async def get_advanced_momentum_status():
    """Get advanced momentum strategy status."""
    try:
        strategy = get_advanced_momentum_strategy()
        return {"status": "success", "data": strategy.get_status()}
    except Exception as e:
        logger.error(f"Advanced strategy status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Technical analysis endpoints
@app.get("/api/indicators/{symbol}")
async def get_technical_indicators_for_symbol(symbol: str):
    """Get technical indicators for symbol."""
    try:
        indicators = get_technical_indicators()
        tech_data = indicators.get_all_indicators(symbol)
        
        return {"status": "success", "data": tech_data}
    except Exception as e:
        logger.error(f"Technical indicators error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Dashboard endpoints  
@app.get("/api/dashboard/live")
async def get_live_dashboard():
    """Get live dashboard data."""
    try:
        monitor = get_realtime_monitor()
        dashboard_data = monitor.get_dashboard_data()
        
        return {"status": "success", "data": dashboard_data}
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/performance")
async def get_performance_chart():
    """Get performance chart data."""
    try:
        monitor = get_realtime_monitor()
        chart_data = monitor.get_performance_chart_data(hours=24)
        
        return {"status": "success", "data": chart_data}
    except Exception as e:
        logger.error(f"Performance chart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Price endpoints
@app.get("/api/prices/{symbol}")
async def get_symbol_price(symbol: str):
    """Get live price for symbol."""
    try:
        price_service = await get_price_service()
        price_data = await price_service.get_price(symbol)
        
        if not price_data:
            raise HTTPException(status_code=404, detail=f"Price not available for {symbol}")
        
        return {
            "status": "success",
            "data": price_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Set startup time
startup_time = time.time()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)