"""
Sofia V2 Developer Dashboard
Real-time monitoring and control interface
"""

import asyncio
import datetime
import random
from typing import Dict, List, Set

import psutil
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Sofia V2 Developer Dashboard")

# Setup templates and static files
templates = Jinja2Templates(directory="src/monitoring/templates")
app.mount("/static", StaticFiles(directory="src/monitoring/static"), name="static")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, data: dict):
        """Broadcast data to all connected clients"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except:
                disconnected.add(connection)

        # Clean up disconnected clients
        self.active_connections -= disconnected


manager = ConnectionManager()

# Mock data for strategies
STRATEGIES = {
    "grid_btc": {
        "name": "Grid Trading BTC",
        "status": "active",
        "pnl": 125.50,
        "positions": 3,
        "win_rate": 68.5,
        "last_trades": [random.uniform(-10, 20) for _ in range(10)],
    },
    "trend_eth": {
        "name": "Trend Following ETH",
        "status": "active",
        "pnl": -45.20,
        "positions": 1,
        "win_rate": 55.2,
        "last_trades": [random.uniform(-15, 25) for _ in range(10)],
    },
    "scalping_bnb": {
        "name": "Scalping BNB",
        "status": "paused",
        "pnl": 89.30,
        "positions": 0,
        "win_rate": 72.1,
        "last_trades": [random.uniform(-5, 10) for _ in range(10)],
    },
    "arbitrage_multi": {
        "name": "Multi-Exchange Arbitrage",
        "status": "active",
        "pnl": 312.80,
        "positions": 5,
        "win_rate": 82.3,
        "last_trades": [random.uniform(0, 15) for _ in range(10)],
    },
}

# Exchange connections
EXCHANGES = {
    "binance": {"status": "connected", "balance_usd": 10000, "api_limit": 1180},
    "btcturk": {"status": "connected", "balance_try": 50000, "api_limit": 980},
    "paribu": {"status": "connecting", "balance_try": 0, "api_limit": 1000},
    "bybit": {"status": "error", "balance_usd": 0, "api_limit": 0},
}

# Log storage
LOGS: List[Dict] = []


def add_log(level: str, source: str, message: str):
    """Add a log entry"""
    global LOGS
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "source": source,
        "message": message,
    }
    LOGS.append(log_entry)
    # Keep only last 100 logs
    if len(LOGS) > 100:
        LOGS.pop(0)
    return log_entry


async def get_system_stats():
    """Get real-time system statistics"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    network = psutil.net_io_counters()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "network_sent_mb": round(network.bytes_sent / (1024**2), 2),
        "network_recv_mb": round(network.bytes_recv / (1024**2), 2),
        "disk_percent": disk.percent,
        "active_strategies": sum(1 for s in STRATEGIES.values() if s["status"] == "active"),
        "websocket_connections": len(manager.active_connections),
    }


async def get_pnl_data():
    """Get P&L data for different timeframes"""
    # Mock data - in production, fetch from database
    return {
        "paper": {
            "today": random.uniform(-100, 300),
            "week": random.uniform(-500, 1500),
            "month": random.uniform(-1000, 5000),
            "all_time": random.uniform(1000, 15000),
        },
        "real": {
            "today": random.uniform(-50, 150),
            "week": random.uniform(-200, 800),
            "month": random.uniform(-500, 2500),
            "all_time": random.uniform(500, 8000),
        },
        "chart_data": {
            "labels": [f"Day {i}" for i in range(1, 31)],
            "paper": [random.uniform(-100, 300) for _ in range(30)],
            "real": [random.uniform(-50, 150) for _ in range(30)],
        },
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard page"""
    return templates.TemplateResponse(
        "dev_dashboard.html", {"request": request, "strategies": STRATEGIES, "exchanges": EXCHANGES}
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        while True:
            # Send updates every second
            system_stats = await get_system_stats()
            pnl_data = await get_pnl_data()

            # Update strategy data with some randomness
            for strategy_id, strategy in STRATEGIES.items():
                if strategy["status"] == "active":
                    # Simulate P&L changes
                    strategy["pnl"] += random.uniform(-5, 10)
                    # Add new trade to history
                    strategy["last_trades"].append(random.uniform(-10, 20))
                    strategy["last_trades"] = strategy["last_trades"][-10:]  # Keep last 10
                    # Update win rate
                    strategy["win_rate"] = min(
                        100, max(0, strategy["win_rate"] + random.uniform(-2, 2))
                    )

            # Update exchange API limits
            for exchange in EXCHANGES.values():
                if exchange["status"] == "connected":
                    exchange["api_limit"] = max(0, exchange["api_limit"] - random.randint(0, 5))

            # Generate some random logs
            if random.random() > 0.7:
                levels = ["info", "warning", "error"]
                sources = list(STRATEGIES.keys()) + list(EXCHANGES.keys())
                messages = [
                    "Order placed successfully",
                    "Position closed with profit",
                    "API rate limit warning",
                    "Connection timeout",
                    "Strategy rebalancing",
                    "New signal detected",
                ]

                log = add_log(
                    random.choice(levels), random.choice(sources), random.choice(messages)
                )

            # Prepare update message
            update = {
                "system": system_stats,
                "pnl": pnl_data,
                "strategies": STRATEGIES,
                "exchanges": EXCHANGES,
                "logs": LOGS[-20:],  # Send last 20 logs
            }

            await manager.broadcast(update)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/strategy/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str):
    """Toggle strategy on/off"""
    if strategy_id in STRATEGIES:
        current_status = STRATEGIES[strategy_id]["status"]
        STRATEGIES[strategy_id]["status"] = "paused" if current_status == "active" else "active"

        # Log the action
        add_log(
            "info",
            "system",
            f"Strategy {strategy_id} {'activated' if STRATEGIES[strategy_id]['status'] == 'active' else 'paused'}",
        )

        return {"success": True, "new_status": STRATEGIES[strategy_id]["status"]}
    return {"success": False, "error": "Strategy not found"}


@app.post("/api/strategy/{strategy_id}/config")
async def update_strategy_config(strategy_id: str, config: dict):
    """Update strategy configuration"""
    if strategy_id in STRATEGIES:
        # In production, update actual strategy config
        add_log("info", "system", f"Strategy {strategy_id} configuration updated")
        return {"success": True}
    return {"success": False, "error": "Strategy not found"}


@app.get("/api/logs")
async def get_logs(source: str = None, level: str = None):
    """Get filtered logs"""
    filtered_logs = LOGS

    if source:
        filtered_logs = [log for log in filtered_logs if log["source"] == source]
    if level:
        filtered_logs = [log for log in filtered_logs if log["level"] == level]

    return {"logs": filtered_logs[-50:]}  # Return last 50 filtered logs


if __name__ == "__main__":
    import uvicorn

    print("[INFO] Starting Sofia V2 Developer Dashboard...")
    print("[INFO] Open http://localhost:8000 in your browser")

    uvicorn.run(app, host="0.0.0.0", port=8000)
