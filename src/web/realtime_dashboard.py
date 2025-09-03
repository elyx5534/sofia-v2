"""
Real-time Dashboard with WebSocket Support
Live price updates, portfolio tracking, and alerts
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel

from src.adapters.web.fastapi_adapter import FastAPI, HTMLResponse, WebSocket, WebSocketDisconnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DashboardUpdate(BaseModel):
    """Dashboard update message"""

    type: str
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
        self.update_interval = 1

    async def start_price_updates(self):
        """Start streaming price updates"""
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
        while True:
            try:
                import random

                for symbol in symbols:
                    base_price = self.price_cache.get(
                        symbol,
                        {"BTC/USDT": 68000, "ETH/USDT": 2500, "SOL/USDT": 180, "BNB/USDT": 600}.get(
                            symbol, 100
                        ),
                    )
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
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Portfolio update error: {e}")
                await asyncio.sleep(5)

    async def check_alerts(self):
        """Check and broadcast alerts"""
        while True:
            try:
                for symbol, price in self.price_cache.items():
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
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Alert check error: {e}")
                await asyncio.sleep(10)


dashboard_html = "\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Real-Time Trading Dashboard</title>\n    <style>\n        * { margin: 0; padding: 0; box-sizing: border-box; }\n        body {\n            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\n            background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%);\n            color: #e0e0e0;\n            padding: 20px;\n        }\n        .container { max-width: 1400px; margin: 0 auto; }\n        .header {\n            background: rgba(255,255,255,0.05);\n            border-radius: 12px;\n            padding: 20px;\n            margin-bottom: 20px;\n            backdrop-filter: blur(10px);\n        }\n        .grid {\n            display: grid;\n            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));\n            gap: 20px;\n        }\n        .card {\n            background: rgba(255,255,255,0.05);\n            border-radius: 12px;\n            padding: 20px;\n            backdrop-filter: blur(10px);\n            border: 1px solid rgba(255,255,255,0.1);\n        }\n        .price-card {\n            display: flex;\n            justify-content: space-between;\n            align-items: center;\n            padding: 15px;\n            margin: 10px 0;\n            background: rgba(255,255,255,0.03);\n            border-radius: 8px;\n        }\n        .price { font-size: 24px; font-weight: bold; }\n        .positive { color: #4ade80; }\n        .negative { color: #f87171; }\n        .status {\n            display: inline-block;\n            padding: 4px 8px;\n            border-radius: 4px;\n            font-size: 12px;\n            margin-left: 10px;\n        }\n        .connected { background: #4ade80; color: #000; }\n        .disconnected { background: #f87171; color: #fff; }\n        .alert {\n            padding: 15px;\n            margin: 10px 0;\n            border-radius: 8px;\n            background: rgba(248,113,113,0.2);\n            border-left: 4px solid #f87171;\n        }\n        #chart { height: 400px; background: rgba(255,255,255,0.03); border-radius: 8px; }\n    </style>\n</head>\n<body>\n    <div class=\"container\">\n        <div class=\"header\">\n            <h1>🚀 Real-Time Trading Dashboard</h1>\n            <span id=\"status\" class=\"status disconnected\">Disconnected</span>\n        </div>\n\n        <div class=\"grid\">\n            <div class=\"card\">\n                <h2>📊 Live Prices</h2>\n                <div id=\"prices\"></div>\n            </div>\n\n            <div class=\"card\">\n                <h2>💼 Portfolio</h2>\n                <div id=\"portfolio\">\n                    <p>Total Value: $<span id=\"totalValue\">0.00</span></p>\n                    <p>Daily P&L: <span id=\"dailyPnl\">$0.00</span></p>\n                </div>\n            </div>\n\n            <div class=\"card\">\n                <h2>🔔 Alerts</h2>\n                <div id=\"alerts\"></div>\n            </div>\n        </div>\n\n        <div class=\"card\" style=\"margin-top: 20px;\">\n            <h2>📈 Price Chart</h2>\n            <div id=\"chart\"></div>\n        </div>\n    </div>\n\n    <script>\n        const ws = new WebSocket('ws://localhost:8000/ws/dashboard');\n        const statusEl = document.getElementById('status');\n        const pricesEl = document.getElementById('prices');\n        const alertsEl = document.getElementById('alerts');\n        const priceData = {};\n\n        ws.onopen = () => {\n            statusEl.textContent = 'Connected';\n            statusEl.className = 'status connected';\n\n            // Subscribe to channels\n            ws.send(JSON.stringify({\n                action: 'subscribe',\n                channels: ['prices', 'portfolio', 'alerts']\n            }));\n        };\n\n        ws.onmessage = (event) => {\n            const data = JSON.parse(event.data);\n\n            if (data.type === 'price') {\n                updatePrice(data.data);\n            } else if (data.type === 'portfolio') {\n                updatePortfolio(data.data);\n            } else if (data.type === 'alert') {\n                showAlert(data.data);\n            }\n        };\n\n        ws.onclose = () => {\n            statusEl.textContent = 'Disconnected';\n            statusEl.className = 'status disconnected';\n        };\n\n        function updatePrice(data) {\n            if (!priceData[data.symbol]) {\n                priceData[data.symbol] = document.createElement('div');\n                priceData[data.symbol].className = 'price-card';\n                pricesEl.appendChild(priceData[data.symbol]);\n            }\n\n            const changeClass = data.change_24h >= 0 ? 'positive' : 'negative';\n            priceData[data.symbol].innerHTML = `\n                <div>\n                    <strong>${data.symbol}</strong>\n                    <div class=\"price\">$${data.price.toFixed(2)}</div>\n                </div>\n                <div class=\"${changeClass}\">\n                    ${data.change_24h >= 0 ? '+' : ''}${data.change_24h.toFixed(2)}%\n                </div>\n            `;\n        }\n\n        function updatePortfolio(data) {\n            document.getElementById('totalValue').textContent = data.total_value.toFixed(2);\n            document.getElementById('dailyPnl').textContent =\n                (data.daily_pnl >= 0 ? '+' : '') + '$' + data.daily_pnl.toFixed(2);\n            document.getElementById('dailyPnl').className =\n                data.daily_pnl >= 0 ? 'positive' : 'negative';\n        }\n\n        function showAlert(data) {\n            const alert = document.createElement('div');\n            alert.className = 'alert';\n            alert.innerHTML = `\n                <strong>${data.symbol}</strong>: ${data.message}\n                <small style=\"float: right\">${new Date(data.timestamp).toLocaleTimeString()}</small>\n            `;\n            alertsEl.insertBefore(alert, alertsEl.firstChild);\n\n            // Keep only last 5 alerts\n            while (alertsEl.children.length > 5) {\n                alertsEl.removeChild(alertsEl.lastChild);\n            }\n        }\n    </script>\n</body>\n</html>\n"
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
