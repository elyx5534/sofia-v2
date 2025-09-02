"""
Sofia V2 Live UI Server with FastAPI and WebSocket support.
Real-time dashboard for paper trading monitoring.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import List

import orjson
import redis.asyncio as redis
from clickhouse_driver import Client as CHClient
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nats.aio.client import Client as NATS
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Templates directory
templates = Jinja2Templates(directory="sofia_ui/templates")

# Global connections
app_state = {
    "nats": None,
    "redis": None,
    "clickhouse": None,
    "websockets": set(),
    "subscriptions": {},
}


class Position(BaseModel):
    """Position model"""

    symbol: str
    quantity: float
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    last_price: float = 0.0


class Order(BaseModel):
    """Order model"""

    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    status: str
    timestamp: str
    pnl: float = 0.0


class PnLMetrics(BaseModel):
    """PnL metrics model"""

    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float = 0.0
    trades_count: int = 0


class TickData(BaseModel):
    """Tick data for WebSocket"""

    symbol: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    change_24h: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    await initialize_connections()
    asyncio.create_task(websocket_broadcaster())
    asyncio.create_task(metrics_updater())

    yield

    # Shutdown
    await cleanup_connections()


app = FastAPI(title="Sofia V2 Trading Platform", version="2.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="sofia_ui/static"), name="static")


async def initialize_connections():
    """Initialize external connections"""
    try:
        # NATS connection
        app_state["nats"] = NATS()
        await app_state["nats"].connect(os.getenv("NATS_URL", "nats://localhost:4222"))
        logger.info("Connected to NATS")

        # Redis connection
        app_state["redis"] = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False,
        )
        await app_state["redis"].ping()
        logger.info("Connected to Redis")

        # ClickHouse connection
        app_state["clickhouse"] = CHClient(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", 9000)),
            user=os.getenv("CLICKHOUSE_USER", "sofia"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "sofia2024"),
            database=os.getenv("CLICKHOUSE_DB", "sofia"),
        )
        logger.info("Connected to ClickHouse")

    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise


async def cleanup_connections():
    """Cleanup connections on shutdown"""
    if app_state["nats"]:
        await app_state["nats"].close()
    if app_state["redis"]:
        await app_state["redis"].close()
    if app_state["clickhouse"]:
        app_state["clickhouse"].disconnect()
    logger.info("Connections cleaned up")


async def websocket_broadcaster():
    """Broadcast market data to WebSocket clients"""
    if not app_state["nats"]:
        return

    async def process_tick(msg):
        """Process and broadcast tick data"""
        try:
            data = orjson.loads(msg.data)
            tick = TickData(
                symbol=data["symbol"],
                price=data["price"],
                bid=data.get("bid", 0),
                ask=data.get("ask", 0),
                volume=data.get("volume", 0),
            )

            # Calculate 24h change (simplified)
            # In production, would query historical data
            tick.change_24h = 0.0

            # Broadcast to all connected WebSocket clients
            message = {"type": "tick", "data": tick.model_dump()}

            disconnected = set()
            for websocket in app_state["websockets"]:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.add(websocket)

            # Clean up disconnected clients
            app_state["websockets"] -= disconnected

        except Exception as e:
            logger.error(f"Error broadcasting tick: {e}")

    # Subscribe to tick data
    await app_state["nats"].subscribe("ticks.*", cb=process_tick)
    logger.info("WebSocket broadcaster started")


async def metrics_updater():
    """Periodically update metrics from Redis/ClickHouse"""
    while True:
        try:
            await asyncio.sleep(5)  # Update every 5 seconds

            # Get current state from Redis
            state_data = await app_state["redis"].get("paper:state")
            if state_data:
                state = orjson.loads(state_data)

                # Broadcast portfolio update
                message = {"type": "portfolio_update", "data": state}

                disconnected = set()
                for websocket in app_state["websockets"]:
                    try:
                        await websocket.send_json(message)
                    except:
                        disconnected.add(websocket)

                app_state["websockets"] -= disconnected

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")


# API Routes


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page redirect to dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "title": "Sofia V2 Dashboard"}
    )


@app.get("/analysis/{symbol}", response_class=HTMLResponse)
async def analysis(request: Request, symbol: str):
    """Symbol analysis page"""
    return templates.TemplateResponse(
        "analysis.html",
        {"request": request, "symbol": symbol.upper(), "title": f"{symbol.upper()} Analysis"},
    )


@app.get("/api/positions")
async def get_positions() -> List[Position]:
    """Get current positions"""
    try:
        positions_data = await app_state["redis"].hgetall("paper:positions")
        positions = []

        for symbol, data in positions_data.items():
            pos_data = orjson.loads(data)
            positions.append(
                Position(
                    symbol=symbol.decode() if isinstance(symbol, bytes) else symbol,
                    quantity=pos_data["quantity"],
                    avg_price=pos_data["avg_price"],
                    unrealized_pnl=pos_data.get("unrealized_pnl", 0),
                    realized_pnl=pos_data.get("realized_pnl", 0),
                )
            )

        return positions

    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/recent")
async def get_recent_orders(limit: int = 20) -> List[Order]:
    """Get recent orders"""
    try:
        # Query ClickHouse for recent orders
        query = f"""
        SELECT order_id, ts, symbol, side, price, quantity, status, pnl
        FROM paper_orders
        ORDER BY ts DESC
        LIMIT {limit}
        """

        result = app_state["clickhouse"].execute(query)
        orders = []

        for row in result:
            orders.append(
                Order(
                    order_id=row[0],
                    timestamp=row[1].isoformat(),
                    symbol=row[2],
                    side=row[3],
                    price=row[4],
                    quantity=row[5],
                    status=row[6],
                    pnl=row[7] or 0.0,
                )
            )

        return orders

    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pnl")
async def get_pnl() -> PnLMetrics:
    """Get PnL metrics"""
    try:
        # Get state from Redis
        state_data = await app_state["redis"].get("paper:state")
        if not state_data:
            return PnLMetrics(
                total_pnl=0.0, realized_pnl=0.0, unrealized_pnl=0.0, win_rate=0.0, max_drawdown=0.0
            )

        state = orjson.loads(state_data)

        # Calculate total trades from ClickHouse
        trades_query = "SELECT count(*) FROM paper_orders WHERE status = 'filled'"
        trades_result = app_state["clickhouse"].execute(trades_query)
        trades_count = trades_result[0][0] if trades_result else 0

        return PnLMetrics(
            total_pnl=state.get("realized_pnl", 0) + state.get("unrealized_pnl", 0),
            realized_pnl=state.get("realized_pnl", 0),
            unrealized_pnl=state.get("unrealized_pnl", 0),
            win_rate=state.get("win_rate", 0),
            max_drawdown=state.get("max_drawdown", 0),
            trades_count=trades_count,
        )

    except Exception as e:
        logger.error(f"Error fetching PnL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ohlcv/{symbol}")
async def get_ohlcv(symbol: str, timeframe: str = "1m", limit: int = 100):
    """Get OHLCV data for charting"""
    try:
        table = "ohlcv_1m" if timeframe == "1m" else "ohlcv_1s"

        query = f"""
        SELECT ts, open, high, low, close, volume
        FROM {table}
        WHERE symbol = '{symbol.upper()}'
        ORDER BY ts DESC
        LIMIT {limit}
        """

        result = app_state["clickhouse"].execute(query)

        ohlcv = []
        for row in result:
            ohlcv.append(
                {
                    "time": row[0].isoformat(),
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                }
            )

        # Reverse to get chronological order
        ohlcv.reverse()

        return JSONResponse(content={"data": ohlcv})

    except Exception as e:
        logger.error(f"Error fetching OHLCV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/{symbol}/toggle")
async def toggle_paper_trading(symbol: str, enabled: bool = True):
    """Enable/disable paper trading for a symbol"""
    try:
        key = f"trading:enabled:{symbol.upper()}"
        await app_state["redis"].set(key, str(enabled))

        return JSONResponse(
            content={
                "symbol": symbol.upper(),
                "trading_enabled": enabled,
                "message": f"Paper trading {'enabled' if enabled else 'disabled'} for {symbol.upper()}",
            }
        )

    except Exception as e:
        logger.error(f"Error toggling trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/quotes")
async def websocket_quotes(websocket: WebSocket):
    """WebSocket endpoint for real-time quotes"""
    await websocket.accept()
    app_state["websockets"].add(websocket)

    try:
        # Send initial state
        state_data = await app_state["redis"].get("paper:state")
        if state_data:
            await websocket.send_json({"type": "initial_state", "data": orjson.loads(state_data)})

        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong or subscription requests)
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")
            elif data.startswith("subscribe:"):
                symbols = data.replace("subscribe:", "").split(",")
                # Track subscriptions per client
                app_state["subscriptions"][websocket] = symbols
                await websocket.send_json({"type": "subscribed", "symbols": symbols})

    except WebSocketDisconnect:
        app_state["websockets"].discard(websocket)
        app_state["subscriptions"].pop(websocket, None)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        app_state["websockets"].discard(websocket)


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check connections
        nats_ok = app_state["nats"] and app_state["nats"].is_connected
        redis_ok = await app_state["redis"].ping() if app_state["redis"] else False
        ch_ok = bool(app_state["clickhouse"])

        return JSONResponse(
            content={
                "status": "healthy" if all([nats_ok, redis_ok, ch_ok]) else "degraded",
                "services": {
                    "nats": "connected" if nats_ok else "disconnected",
                    "redis": "connected" if redis_ok else "disconnected",
                    "clickhouse": "connected" if ch_ok else "disconnected",
                },
                "websocket_clients": len(app_state["websockets"]),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv(".env.paper")

    uvicorn.run("sofia_ui.server_v2:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
