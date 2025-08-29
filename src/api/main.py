"""
Sofia V2 API Server
Real-time trading API with WebSocket price feeds
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.price_service_real import price_service
from src.models.portfolio import portfolio_manager
from src.sofia.data.realtime import ReliabilityFeed
from src.sofia.config import SYMBOLS, STALE_TTL_SEC
from src.sofia.symbols import to_ui

# Import routers
from src.api import ai_endpoints, trade_endpoints
from src.api.metrics_enhanced import metrics_collector
from src.data.equities_fallback import equities_fallback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
API_VERSION = "2.0.0"
GIT_SHA = os.getenv("GIT_SHA", "dev")

# Request models
class PaperOrderRequest(BaseModel):
    symbol: str
    side: str
    usd_amount: float

# Create FastAPI app
app = FastAPI(
    title="Sofia V2 Trading API",
    description="Real-time trading with WebSocket price feeds",
    version=API_VERSION
)

# Initialize reliability feed
FEED = ReliabilityFeed()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8002",
        "http://localhost:8003",
        "http://localhost:8004",
        "http://localhost:8010",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8002",
        "http://127.0.0.1:8003",
        "http://127.0.0.1:8004",
        "http://127.0.0.1:8010",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ai_endpoints.router)
app.include_router(trade_endpoints.router)

# Import and include portfolio router
from src.api import portfolio_endpoints
app.include_router(portfolio_endpoints.router)

# Import and include paper trading router
from src.api import paper_trading
app.include_router(paper_trading.router)


@app.on_event("startup")
async def startup_event():
    """Start price service on API startup"""
    logger.info("[INFO] Starting Sofia V2 Trading API")
    # Price service will start WebSocket automatically
    FEED.start()  # Start reliability feed


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("[INFO] Shutting down Sofia V2 Trading API")
    FEED.stop()  # Stop reliability feed
    await price_service.shutdown()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": API_VERSION,
        "git_sha": GIT_SHA
    }


@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Enhanced system metrics endpoint"""
    # Get enhanced metrics
    enhanced_metrics = metrics_collector.calculate_metrics()
    
    # Get fallback stats
    fallback_stats = equities_fallback.get_fallback_stats()
    
    # Get basic metrics
    try:
        basic_metrics = price_service.get_metrics()
    except:
        basic_metrics = {}
    
    # Combine all metrics
    return {
        "status": "running",
        "timestamp": time.time(),
        **enhanced_metrics,
        "fallback_stats": fallback_stats,
        "basic_metrics": basic_metrics,
        "service_running": True,
        "websocket_connected": len(manager.active_connections) > 0,
        "websocket_connections": len(manager.active_connections)
    }


@app.get("/api/trading/portfolio")
async def get_portfolio() -> Dict[str, Any]:
    """Get current portfolio state"""
    portfolio = portfolio_manager.get_portfolio()
    portfolio["base_currency"] = "USD"  # Inject base currency
    return portfolio


@app.get("/api/trading/positions")
async def get_positions() -> list:
    """Get open positions"""
    portfolio = portfolio_manager.get_portfolio()
    return portfolio.get("positions", [])


# New reliability pack endpoints
class PriceResp(BaseModel):
    symbol: str
    price: float
    ts: float
    stale: bool
    source: str

@app.get("/symbols")
async def get_symbols() -> Dict[str, List[str]]:
    """Get supported symbols"""
    return {"symbols": SYMBOLS}

@app.get("/price/{symbol}", response_model=PriceResp)
async def get_symbol_price(symbol: str) -> PriceResp:
    """Get price for a specific symbol with freshness info"""
    tick = FEED.get_price(symbol)
    
    if not tick:
        raise HTTPException(status_code=503, detail="No fresh data available")
    
    stale = (time.time() - tick.ts) > STALE_TTL_SEC
    
    return PriceResp(
        symbol=to_ui(symbol),
        price=tick.price,
        ts=tick.ts,
        stale=stale,
        source=tick.source
    )

@app.get("/data/debug")
async def debug_data() -> Dict[str, Any]:
    """Debug endpoint for data reliability"""
    metrics = FEED.get_metrics()
    cache_keys = list(FEED.cache.store.keys()) if hasattr(FEED.cache, 'store') else []
    
    return {
        "cache_keys": cache_keys,
        "metrics": metrics,
        "ws_enabled": price_service.websocket_enabled if hasattr(price_service, 'websocket_enabled') else False,
        "stale_ttl": STALE_TTL_SEC
    }

@app.post("/api/trading/paper-order")
async def execute_paper_order(order: PaperOrderRequest) -> Dict[str, Any]:
    """Execute paper trade with USD notional amount"""
    # Map UI symbol to exchange symbol
    from src.services.symbols import get_rest_sym
    exchange_symbol = get_rest_sym(order.symbol) or order.symbol
    
    # Get current price
    price_data = await price_service.get_price(order.symbol)
    
    if not price_data or not price_data.get("price"):
        raise HTTPException(status_code=400, detail=f"No price available for {order.symbol}")
    
    current_price = price_data["price"]
    
    # Apply fee (0.05%)
    fee_rate = 0.0005
    effective_amount = order.usd_amount * (1 - fee_rate) if order.side == "buy" else order.usd_amount
    
    # Execute order
    result = portfolio_manager.execute_order(
        symbol=order.symbol,
        side=order.side,
        usd_amount=effective_amount,
        price=current_price
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Order failed"))
    
    return {
        "success": True,
        "symbol": order.symbol,
        "side": order.side,
        "usd_amount": order.usd_amount,
        "price": current_price,
        "quantity": result.get("quantity"),
        "fee": order.usd_amount * fee_rate,
        "timestamp": result.get("timestamp")
    }


@app.get("/price/{symbol}")
async def get_equity_price(symbol: str) -> Dict[str, Any]:
    """Get equity price with fallback chain"""
    start_time = time.time()
    
    # Record API call
    price_data = await equities_fallback.get_price(symbol.upper())
    
    # Record metrics
    latency_ms = (time.time() - start_time) * 1000
    metrics_collector.record_api_latency(latency_ms)
    metrics_collector.record_provider_latency(price_data.provider, price_data.latency_ms)
    
    if price_data.provider != "primary":
        metrics_collector.record_fallback(price_data.provider)
    
    return {
        "symbol": price_data.symbol,
        "price": price_data.price,
        "provider": price_data.provider,
        "latency_ms": latency_ms,
        "timestamp": price_data.timestamp
    }


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
        
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
        
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming"""
    await manager.connect(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected to Sofia V2",
            "timestamp": time.time()
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                
                # Echo back for now (can be enhanced with actual logic)
                await websocket.send_json({
                    "type": "echo",
                    "data": data,
                    "timestamp": time.time()
                })
                
                # Simulate price updates (replace with real data)
                await asyncio.sleep(5)
                for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                    await websocket.send_json({
                        "type": "price",
                        "symbol": symbol,
                        "price": 50000 + (hash(symbol + str(time.time())) % 10000),
                        "timestamp": time.time()
                    })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        manager.disconnect(websocket)




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)