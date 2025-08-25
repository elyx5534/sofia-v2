"""
Sofia V2 Realtime DataHub - Main FastAPI Application
Production-grade real-time data aggregation with WebSocket broadcast
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .config import get_settings, Settings
from .bus import EventBus, EventType
from .news.cryptopanic_rss import CryptoPanicRSSIngestor
from .ingestors.binance import BinanceIngestor
from .ingestors.okx import OKXIngestor
from .ingestors.bybit import BybitIngestor
from .ingestors.coinbase import CoinbaseIngestor
from .features.detectors import DetectorManager
from .store.parquet import ParquetStore
from .store.timescale import TimescaleStore
from .trading.manager import TradingManager

logger = structlog.get_logger(__name__)

# Prometheus metrics
WEBSOCKET_CONNECTIONS = Gauge('websocket_connections_total', 'Total WebSocket connections')
EVENTS_PROCESSED = Counter('events_processed_total', 'Total events processed', ['event_type', 'source'])
EVENT_PROCESSING_TIME = Histogram('event_processing_seconds', 'Event processing time')
RSS_FETCH_COUNT = Counter('rss_fetch_total', 'RSS fetch attempts', ['status'])

class ConnectionManager:
    """WebSocket connection manager with broadcast capabilities"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_count = 0
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_count += 1
        WEBSOCKET_CONNECTIONS.set(self.connection_count)
        logger.info("WebSocket connected", total_connections=self.connection_count)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_count -= 1
            WEBSOCKET_CONNECTIONS.set(self.connection_count)
            logger.info("WebSocket disconnected", total_connections=self.connection_count)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning("Failed to send to WebSocket", error=str(e))
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Global instances
manager = ConnectionManager()
event_bus = EventBus()
ingestors = {}
detector_manager = None
parquet_store = None
timescale_store = None
trading_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    settings = get_settings()
    
    logger.info("Starting Sofia V2 DataHub", 
                version="0.1.0",
                enabled_exchanges=settings.get_enabled_exchanges(),
                symbols=settings.symbols_list)
    
    # Validate configuration
    if not settings.validate_config():
        raise RuntimeError("Configuration validation failed")
    
    # Initialize storage systems
    global detector_manager, parquet_store, timescale_store, trading_manager
    
    # Initialize trading system with 100,000 TL balance
    trading_manager = TradingManager(event_bus, settings)
    logger.info("Trading system initialized", initial_balance="100,000 TL")
    
    # Initialize anomaly detectors
    detector_manager = DetectorManager(event_bus, settings)
    
    # Initialize storage
    parquet_store = ParquetStore(event_bus, settings)
    if settings.use_timescale:
        timescale_store = TimescaleStore(event_bus, settings)
        await timescale_store.initialize()
    
    # Setup event handlers
    event_bus.subscribe(EventType.TRADE, handle_trade_event)
    event_bus.subscribe(EventType.ORDERBOOK, handle_orderbook_event)
    event_bus.subscribe(EventType.LIQUIDATION, handle_liquidation_event)
    event_bus.subscribe(EventType.NEWS, handle_news_event)
    event_bus.subscribe(EventType.BIG_TRADE, handle_big_trade_event)
    event_bus.subscribe(EventType.LIQ_SPIKE, handle_liq_spike_event)
    
    # Start background tasks
    tasks = []
    
    # Start storage periodic tasks
    if parquet_store.enabled:
        tasks.append(asyncio.create_task(parquet_store.periodic_flush()))
    
    if timescale_store and timescale_store.enabled:
        tasks.append(asyncio.create_task(timescale_store.periodic_flush()))
    
    # News ingestor
    if settings.cryptopanic_enabled:
        news_ingestor = CryptoPanicRSSIngestor(event_bus, settings)
        tasks.append(asyncio.create_task(news_ingestor.start()))
        logger.info("Started CryptoPanic RSS ingestor")
    
    # Exchange ingestors
    for exchange in settings.get_enabled_exchanges():
        if exchange == 'binance':
            ingestor = BinanceIngestor(event_bus, settings)
        elif exchange == 'okx':
            ingestor = OKXIngestor(event_bus, settings)
        elif exchange == 'bybit':
            ingestor = BybitIngestor(event_bus, settings)
        elif exchange == 'coinbase':
            ingestor = CoinbaseIngestor(event_bus, settings)
        else:
            continue
        
        ingestors[exchange] = ingestor
        tasks.append(asyncio.create_task(ingestor.start()))
        logger.info("Started ingestor", exchange=exchange)
    
    # Start trading system
    if trading_manager:
        await trading_manager.start_trading()
        logger.info("Trading system started - ready for autonomous operations")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sofia V2 DataHub")
    
    # Cancel all background tasks
    for task in tasks:
        task.cancel()
    
    # Stop trading system
    if trading_manager:
        await trading_manager.stop_trading()
        logger.info("Trading system stopped")
    
    # Stop ingestors
    for ingestor in ingestors.values():
        await ingestor.stop()
    
    # Flush and close storage systems
    if parquet_store:
        await parquet_store.flush_all_buffers()
    
    if timescale_store:
        await timescale_store.flush_all_buffers()
        await timescale_store.close()
    
    logger.info("Sofia V2 DataHub shutdown complete")

app = FastAPI(
    title="Sofia V2 Realtime DataHub",
    description="Production-grade real-time crypto data aggregation",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Event handlers
async def handle_trade_event(event_data: Dict[str, Any]):
    """Handle trade events"""
    EVENTS_PROCESSED.labels(event_type='trade', source=event_data.get('exchange', 'unknown')).inc()
    await manager.broadcast({
        'type': 'trade',
        'data': event_data
    })

async def handle_orderbook_event(event_data: Dict[str, Any]):
    """Handle orderbook events"""
    EVENTS_PROCESSED.labels(event_type='orderbook', source=event_data.get('exchange', 'unknown')).inc()
    await manager.broadcast({
        'type': 'orderbook',
        'data': event_data
    })

async def handle_liquidation_event(event_data: Dict[str, Any]):
    """Handle liquidation events"""
    EVENTS_PROCESSED.labels(event_type='liquidation', source=event_data.get('exchange', 'unknown')).inc()
    await manager.broadcast({
        'type': 'liquidation',
        'data': event_data
    })

async def handle_news_event(event_data: Dict[str, Any]):
    """Handle news events"""
    EVENTS_PROCESSED.labels(event_type='news', source='cryptopanic').inc()
    await manager.broadcast({
        'type': 'news',
        'data': event_data
    })

async def handle_big_trade_event(event_data: Dict[str, Any]):
    """Handle big trade detection events"""
    EVENTS_PROCESSED.labels(event_type='big_trade', source=event_data.get('exchange', 'unknown')).inc()
    await manager.broadcast({
        'type': 'alert',
        'alert_type': 'big_trade',
        'data': event_data
    })

async def handle_liq_spike_event(event_data: Dict[str, Any]):
    """Handle liquidation spike detection events"""
    EVENTS_PROCESSED.labels(event_type='liq_spike', source=event_data.get('exchange', 'unknown')).inc()
    await manager.broadcast({
        'type': 'alert',
        'alert_type': 'liq_spike',
        'data': event_data
    })

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time data"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive with ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        manager.disconnect(websocket)

# REST API endpoints
@app.get("/health")
async def health_check():
    """Basic health check"""
    from datetime import datetime, timezone
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health/detailed")
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """Detailed health check with component status"""
    from datetime import datetime, timezone
    status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "event_bus": "healthy",
            "websocket_connections": manager.connection_count,
            "enabled_exchanges": settings.get_enabled_exchanges(),
            "ingestors": {}
        }
    }
    
    # Check ingestor status
    for exchange, ingestor in ingestors.items():
        status["components"]["ingestors"][exchange] = "connected" if ingestor.is_connected_status() else "disconnected"
    
    return status

@app.get("/symbols")
async def get_symbols(settings: Settings = Depends(get_settings)):
    """Get configured symbols"""
    return {"symbols": settings.symbols_list}

@app.get("/exchanges")
async def get_exchanges(settings: Settings = Depends(get_settings)):
    """Get enabled exchanges"""
    return {"exchanges": settings.get_enabled_exchanges()}

@app.get("/config")
async def get_config_info(settings: Settings = Depends(get_settings)):
    """Get configuration summary"""
    return {
        "symbols": settings.symbols_list,
        "exchanges": settings.get_enabled_exchanges(),
        "news_enabled": settings.cryptopanic_enabled,
        "timescale_enabled": settings.use_timescale,
        "metrics_enabled": settings.enable_metrics
    }

@app.get("/detectors")
async def get_detector_status():
    """Get anomaly detector status"""
    if detector_manager:
        return detector_manager.get_status()
    return {"detectors": "not_initialized"}

@app.get("/storage")
async def get_storage_status():
    """Get storage system status"""
    status = {}
    
    if parquet_store:
        status["parquet"] = parquet_store.get_status()
    
    if timescale_store:
        status["timescale"] = timescale_store.get_status()
    
    return status

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Trading API endpoints
@app.get("/trading/status")
async def get_trading_status():
    """Get comprehensive trading system status"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    return trading_manager.get_trading_status()

@app.post("/trading/enable")
async def enable_trading():
    """Enable trading system"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    trading_manager.enable_trading()
    return {"message": "Trading system enabled"}

@app.post("/trading/disable")
async def disable_trading():
    """Disable trading system"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    trading_manager.disable_trading()
    return {"message": "Trading system disabled"}

@app.post("/trading/strategies/{strategy_name}/enable")
async def enable_strategy(strategy_name: str):
    """Enable specific strategy"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    success = trading_manager.enable_strategy(strategy_name)
    if success:
        return {"message": f"Strategy {strategy_name} enabled"}
    else:
        return {"error": f"Strategy {strategy_name} not found"}

@app.post("/trading/strategies/{strategy_name}/disable")
async def disable_strategy(strategy_name: str):
    """Disable specific strategy"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    success = trading_manager.disable_strategy(strategy_name)
    if success:
        return {"message": f"Strategy {strategy_name} disabled"}
    else:
        return {"error": f"Strategy {strategy_name} not found"}

@app.get("/trading/performance")
async def get_trading_performance():
    """Get trading performance report"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    return trading_manager._generate_performance_report()

@app.get("/trading/portfolio")
async def get_portfolio():
    """Get current portfolio status"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    import math
    def sanitize_json(obj):
        if isinstance(obj, dict):
            return {k: sanitize_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_json(v) for v in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return obj
    
    portfolio_metrics = trading_manager.portfolio.get_metrics()
    return sanitize_json(portfolio_metrics)

@app.get("/trading/positions")
async def get_positions():
    """Get current trading positions"""
    if not trading_manager:
        return {"error": "Trading system not initialized"}
    
    positions = {}
    for symbol, position in trading_manager.portfolio.positions.items():
        positions[symbol] = {
            "symbol": position.symbol,
            "side": position.side.value,
            "size": position.size,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "unrealized_pnl": position.unrealized_pnl,
            "entry_time": position.entry_time.isoformat(),
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit
        }
    
    return {"positions": positions}

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )