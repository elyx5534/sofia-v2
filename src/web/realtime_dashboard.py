"""
Real-time Dashboard with WebSocket Support
Live price updates, portfolio tracking, and alerts
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DashboardUpdate(BaseModel):
    """Dashboard update message"""

    type: str  # price, portfolio, alert, trade
    data: Dict[str, Any]
    timestamp: datetime


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept new connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific client"""
        await websocket.send_text(message)

    async def broadcast(self, message: str, channel: Optional[str] = None):
        """Broadcast message to all or subscribed clients"""
        for connection in self.active_connections:
            if channel is None or channel in self.subscriptions.get(connection, set()):
                try:
                    await connection.send_text(message)
                except:
                    # Connection might be closed
                    pass

    def subscribe(self, websocket: WebSocket, channels: List[str]):
        """Subscribe client to channels"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(channels)


manager = ConnectionManager()


class RealTimeDashboard:
    """Real-time dashboard service"""

    def __init__(self):
        self.price_cache: Dict[str, float] = {}
        self.portfolio_cache: Dict[str, Any] = {}
        self.alerts: List[Dict] = []
        self.update_interval = 1  # seconds

    async def start_price_updates(self):
        """Start streaming price updates"""
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]

        while True:
            try:
                # Simulate price updates (replace with real data source)
                import random

                for symbol in symbols:
                    base_price = self.price_cache.get(
                        symbol,
                        {"BTC/USDT": 68000, "ETH/USDT": 2500, "SOL/USDT": 180, "BNB/USDT": 600}.get(
                            symbol, 100
                        ),
                    )

                    # Random walk
                    change = random.uniform(-0.5, 0.5) / 100
                    new_price = base_price * (1 + change)
                    self.price_cache[symbol] = new_price

                    update = DashboardUpdate(
                        type="price",
                        data={
                            "symbol": symbol,
                            "price": new_price,
                            "change_24h": random.uniform(-5, 5),
                            "volume_24h": random.uniform(1000000, 10000000),
                        },
                        timestamp=datetime.now(timezone.utc),
                    )

                    await manager.broadcast(update.model_dump_json(), channel="prices")

                await asyncio.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(5)

    async def start_portfolio_updates(self):
        """Start streaming portfolio updates"""
        while True:
            try:
                # Simulate portfolio updates
                portfolio_value = sum(self.price_cache.values()) * 0.1

                update = DashboardUpdate(
                    type="portfolio",
                    data={
                        "total_value": portfolio_value,
                        "daily_pnl": portfolio_value * 0.02,
                        "daily_pnl_percent": 2.0,
                        "positions": [
                            {
                                "symbol": symbol,
                                "quantity": 0.1,
                                "value": price * 0.1,
                                "pnl": price * 0.1 * 0.02,
                            }
                            for symbol, price in self.price_cache.items()
                        ],
                    },
                    timestamp=datetime.now(timezone.utc),
                )

                await manager.broadcast(update.model_dump_json(), channel="portfolio")

                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                logger.error(f"Portfolio update error: {e}")
                await asyncio.sleep(5)

    async def check_alerts(self):
        """Check and broadcast alerts"""
        while True:
            try:
                # Check price alerts
                for symbol, price in self.price_cache.items():
                    # Example alert conditions
                    if symbol == "BTC/USDT" and price > 69000:
                        alert = {
                            "type": "price_alert",
                            "symbol": symbol,
                            "message": f"{symbol} exceeded $69,000!",
                            "severity": "high",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }

                        await manager.broadcast(
                            json.dumps({"type": "alert", "data": alert}), channel="alerts"
                        )

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Alert check error: {e}")
                await asyncio.sleep(10)


# Dashboard HTML template
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Real-Time Trading Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%);
            color: #e0e0e0;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .price-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin: 10px 0;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
        }
        .price { font-size: 24px; font-weight: bold; }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 10px;
        }
        .connected { background: #4ade80; color: #000; }
        .disconnected { background: #f87171; color: #fff; }
        .alert {
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            background: rgba(248,113,113,0.2);
            border-left: 4px solid #f87171;
        }
        #chart { height: 400px; background: rgba(255,255,255,0.03); border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Real-Time Trading Dashboard</h1>
            <span id="status" class="status disconnected">Disconnected</span>
        </div>

        <div class="grid">
            <div class="card">
                <h2>📊 Live Prices</h2>
                <div id="prices"></div>
            </div>

            <div class="card">
                <h2>💼 Portfolio</h2>
                <div id="portfolio">
                    <p>Total Value: $<span id="totalValue">0.00</span></p>
                    <p>Daily P&L: <span id="dailyPnl">$0.00</span></p>
                </div>
            </div>

            <div class="card">
                <h2>🔔 Alerts</h2>
                <div id="alerts"></div>
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <h2>📈 Price Chart</h2>
            <div id="chart"></div>
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://localhost:8000/ws/dashboard');
        const statusEl = document.getElementById('status');
        const pricesEl = document.getElementById('prices');
        const alertsEl = document.getElementById('alerts');
        const priceData = {};

        ws.onopen = () => {
            statusEl.textContent = 'Connected';
            statusEl.className = 'status connected';

            // Subscribe to channels
            ws.send(JSON.stringify({
                action: 'subscribe',
                channels: ['prices', 'portfolio', 'alerts']
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'price') {
                updatePrice(data.data);
            } else if (data.type === 'portfolio') {
                updatePortfolio(data.data);
            } else if (data.type === 'alert') {
                showAlert(data.data);
            }
        };

        ws.onclose = () => {
            statusEl.textContent = 'Disconnected';
            statusEl.className = 'status disconnected';
        };

        function updatePrice(data) {
            if (!priceData[data.symbol]) {
                priceData[data.symbol] = document.createElement('div');
                priceData[data.symbol].className = 'price-card';
                pricesEl.appendChild(priceData[data.symbol]);
            }

            const changeClass = data.change_24h >= 0 ? 'positive' : 'negative';
            priceData[data.symbol].innerHTML = `
                <div>
                    <strong>${data.symbol}</strong>
                    <div class="price">$${data.price.toFixed(2)}</div>
                </div>
                <div class="${changeClass}">
                    ${data.change_24h >= 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                </div>
            `;
        }

        function updatePortfolio(data) {
            document.getElementById('totalValue').textContent = data.total_value.toFixed(2);
            document.getElementById('dailyPnl').textContent =
                (data.daily_pnl >= 0 ? '+' : '') + '$' + data.daily_pnl.toFixed(2);
            document.getElementById('dailyPnl').className =
                data.daily_pnl >= 0 ? 'positive' : 'negative';
        }

        function showAlert(data) {
            const alert = document.createElement('div');
            alert.className = 'alert';
            alert.innerHTML = `
                <strong>${data.symbol}</strong>: ${data.message}
                <small style="float: right">${new Date(data.timestamp).toLocaleTimeString()}</small>
            `;
            alertsEl.insertBefore(alert, alertsEl.firstChild);

            // Keep only last 5 alerts
            while (alertsEl.children.length > 5) {
                alertsEl.removeChild(alertsEl.lastChild);
            }
        }
    </script>
</body>
</html>
"""


# FastAPI app
app = FastAPI(title="Real-Time Dashboard")
dashboard = RealTimeDashboard()


@app.get("/")
async def get_dashboard():
    """Serve dashboard HTML"""
    return HTMLResponse(dashboard_html)


@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "subscribe":
                channels = message.get("channels", [])
                manager.subscribe(websocket, channels)
                await manager.send_personal_message(
                    json.dumps({"status": "subscribed", "channels": channels}), websocket
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(dashboard.start_price_updates())
    asyncio.create_task(dashboard.start_portfolio_updates())
    asyncio.create_task(dashboard.check_alerts())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
