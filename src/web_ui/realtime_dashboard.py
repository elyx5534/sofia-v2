"""
Real-Time Trading Dashboard with WebSocket
Advanced live trading interface with real crypto prices
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.adapters.web.fastapi_adapter import FastAPI, HTMLResponse, WebSocket, WebSocketDisconnect

from ..data.real_time_fetcher import fetcher

logger = logging.getLogger(__name__)
app = FastAPI(title="Sofia V2 Real-Time Dashboard")
templates = Jinja2Templates(directory="src/web_ui/templates")
app.mount("/static", StaticFiles(directory="src/web_ui/static"), name="static")


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str = None):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(client_id)
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str, user_id: str = None):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if user_id and user_id in self.user_connections:
            if client_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(client_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)


manager = ConnectionManager()
WATCHED_SYMBOLS = [
    "bitcoin",
    "ethereum",
    "solana",
    "binancecoin",
    "cardano",
    "polkadot",
    "chainlink",
    "litecoin",
]


class LiveDataStreamer:
    """Streams live market data"""

    def __init__(self):
        self.is_running = False
        self.last_prices = {}

    async def start_streaming(self):
        """Start the data streaming loop"""
        if self.is_running:
            return
        self.is_running = True
        logger.info("Starting live data stream")
        await fetcher.start()
        while self.is_running:
            try:
                market_data = await fetcher.get_market_data(WATCHED_SYMBOLS)
                if market_data:
                    for symbol, data in market_data.items():
                        if symbol in self.last_prices:
                            data["price_direction"] = (
                                "up" if data["price"] > self.last_prices[symbol] else "down"
                            )
                        else:
                            data["price_direction"] = "neutral"
                        self.last_prices[symbol] = data["price"]
                    await manager.broadcast(
                        {
                            "type": "market_update",
                            "data": market_data,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                gainers_losers = await fetcher.get_top_gainers_losers(5)
                if gainers_losers:
                    await manager.broadcast(
                        {
                            "type": "gainers_losers",
                            "data": gainers_losers,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error in data stream: {e}")
                await asyncio.sleep(5)

    def stop_streaming(self):
        """Stop the data streaming loop"""
        self.is_running = False
        logger.info("Stopped live data stream")


streamer = LiveDataStreamer()


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup"""
    asyncio.create_task(streamer.start_streaming())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    streamer.stop_streaming()
    await fetcher.stop()


@app.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Main dashboard page"""
    return '\n    <!DOCTYPE html>\n    <html lang="en">\n    <head>\n        <meta charset="UTF-8">\n        <meta name="viewport" content="width=device-width, initial-scale=1.0">\n        <title>Sofia V2 - Real-Time Trading Dashboard</title>\n        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>\n        <style>\n            * {\n                margin: 0;\n                padding: 0;\n                box-sizing: border-box;\n            }\n\n            body {\n                font-family: \'Segoe UI\', Tahoma, Geneva, Verdana, sans-serif;\n                background: linear-gradient(135deg, #0f0f23, #1a1a3a);\n                color: #ffffff;\n                min-height: 100vh;\n                overflow-x: hidden;\n            }\n\n            .header {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                padding: 1rem;\n                border-bottom: 1px solid rgba(255, 255, 255, 0.1);\n            }\n\n            .logo {\n                font-size: 1.5rem;\n                font-weight: bold;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                -webkit-background-clip: text;\n                -webkit-text-fill-color: transparent;\n                display: inline-block;\n            }\n\n            .status {\n                float: right;\n                display: flex;\n                align-items: center;\n                gap: 10px;\n            }\n\n            .status-dot {\n                width: 12px;\n                height: 12px;\n                border-radius: 50%;\n                background: #00d4aa;\n                animation: pulse 2s infinite;\n            }\n\n            @keyframes pulse {\n                0% { opacity: 1; transform: scale(1); }\n                50% { opacity: 0.5; transform: scale(1.2); }\n                100% { opacity: 1; transform: scale(1); }\n            }\n\n            .main-grid {\n                display: grid;\n                grid-template-columns: 1fr 300px;\n                gap: 20px;\n                padding: 20px;\n                min-height: calc(100vh - 80px);\n            }\n\n            .left-panel {\n                display: flex;\n                flex-direction: column;\n                gap: 20px;\n            }\n\n            .right-panel {\n                display: flex;\n                flex-direction: column;\n                gap: 20px;\n            }\n\n            .card {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                border-radius: 15px;\n                padding: 20px;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                transition: all 0.3s ease;\n            }\n\n            .card:hover {\n                transform: translateY(-5px);\n                border-color: rgba(0, 212, 170, 0.3);\n                box-shadow: 0 10px 30px rgba(0, 212, 170, 0.1);\n            }\n\n            .card-title {\n                font-size: 1.2rem;\n                font-weight: bold;\n                margin-bottom: 15px;\n                color: #00d4aa;\n            }\n\n            .price-grid {\n                display: grid;\n                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));\n                gap: 15px;\n            }\n\n            .price-item {\n                background: rgba(255, 255, 255, 0.03);\n                border-radius: 10px;\n                padding: 15px;\n                border-left: 3px solid #00d4aa;\n                transition: all 0.3s ease;\n                cursor: pointer;\n            }\n\n            .price-item:hover {\n                background: rgba(255, 255, 255, 0.08);\n                transform: translateX(5px);\n            }\n\n            .price-item.price-up {\n                border-left-color: #00ff88;\n                background: rgba(0, 255, 136, 0.05);\n            }\n\n            .price-item.price-down {\n                border-left-color: #ff4757;\n                background: rgba(255, 71, 87, 0.05);\n            }\n\n            .symbol {\n                font-weight: bold;\n                font-size: 0.9rem;\n                color: #ccc;\n                text-transform: uppercase;\n            }\n\n            .price {\n                font-size: 1.3rem;\n                font-weight: bold;\n                margin: 5px 0;\n            }\n\n            .change {\n                font-size: 0.85rem;\n                font-weight: bold;\n            }\n\n            .positive {\n                color: #00ff88;\n            }\n\n            .negative {\n                color: #ff4757;\n            }\n\n            .chart-container {\n                height: 300px;\n                margin-top: 10px;\n            }\n\n            .gainers-losers {\n                max-height: 400px;\n                overflow-y: auto;\n            }\n\n            .gainer-item, .loser-item {\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n                padding: 10px;\n                margin: 5px 0;\n                border-radius: 8px;\n                transition: background 0.2s ease;\n            }\n\n            .gainer-item {\n                background: rgba(0, 255, 136, 0.1);\n                border-left: 3px solid #00ff88;\n            }\n\n            .loser-item {\n                background: rgba(255, 71, 87, 0.1);\n                border-left: 3px solid #ff4757;\n            }\n\n            .gainer-item:hover, .loser-item:hover {\n                background: rgba(255, 255, 255, 0.1);\n            }\n\n            .volume {\n                font-size: 0.8rem;\n                color: #888;\n            }\n\n            .loading {\n                display: flex;\n                justify-content: center;\n                align-items: center;\n                height: 100px;\n            }\n\n            .spinner {\n                width: 40px;\n                height: 40px;\n                border: 4px solid rgba(0, 212, 170, 0.3);\n                border-top: 4px solid #00d4aa;\n                border-radius: 50%;\n                animation: spin 1s linear infinite;\n            }\n\n            @keyframes spin {\n                0% { transform: rotate(0deg); }\n                100% { transform: rotate(360deg); }\n            }\n\n            @media (max-width: 768px) {\n                .main-grid {\n                    grid-template-columns: 1fr;\n                }\n\n                .price-grid {\n                    grid-template-columns: 1fr;\n                }\n            }\n        </style>\n    </head>\n    <body>\n        <header class="header">\n            <div class="logo">Sofia V2 Trading Dashboard</div>\n            <div class="status">\n                <div class="status-dot"></div>\n                <span id="connection-status">Connecting...</span>\n            </div>\n        </header>\n\n        <div class="main-grid">\n            <div class="left-panel">\n                <div class="card">\n                    <div class="card-title">Live Market Prices</div>\n                    <div id="market-prices" class="price-grid">\n                        <div class="loading">\n                            <div class="spinner"></div>\n                        </div>\n                    </div>\n                </div>\n\n                <div class="card">\n                    <div class="card-title">Price Chart</div>\n                    <div class="chart-container">\n                        <canvas id="price-chart"></canvas>\n                    </div>\n                </div>\n            </div>\n\n            <div class="right-panel">\n                <div class="card">\n                    <div class="card-title">🚀 Top Gainers</div>\n                    <div id="top-gainers" class="gainers-losers">\n                        <div class="loading">\n                            <div class="spinner"></div>\n                        </div>\n                    </div>\n                </div>\n\n                <div class="card">\n                    <div class="card-title">📉 Top Losers</div>\n                    <div id="top-losers" class="gainers-losers">\n                        <div class="loading">\n                            <div class="spinner"></div>\n                        </div>\n                    </div>\n                </div>\n            </div>\n        </div>\n\n        <script>\n            // WebSocket connection\n            let ws;\n            let chart;\n            let chartData = [];\n\n            function connectWebSocket() {\n                const protocol = window.location.protocol === \'https:\' ? \'wss:\' : \'ws:\';\n                const wsUrl = `${protocol}//${window.location.host}/ws`;\n\n                ws = new WebSocket(wsUrl);\n\n                ws.onopen = function() {\n                    console.log(\'Connected to WebSocket\');\n                    document.getElementById(\'connection-status\').textContent = \'Connected\';\n                };\n\n                ws.onmessage = function(event) {\n                    const message = JSON.parse(event.data);\n                    handleWebSocketMessage(message);\n                };\n\n                ws.onclose = function() {\n                    console.log(\'WebSocket connection closed\');\n                    document.getElementById(\'connection-status\').textContent = \'Reconnecting...\';\n                    setTimeout(connectWebSocket, 3000);\n                };\n\n                ws.onerror = function(error) {\n                    console.error(\'WebSocket error:\', error);\n                    document.getElementById(\'connection-status\').textContent = \'Connection Error\';\n                };\n            }\n\n            function handleWebSocketMessage(message) {\n                switch(message.type) {\n                    case \'market_update\':\n                        updateMarketPrices(message.data);\n                        updateChart(message.data);\n                        break;\n                    case \'gainers_losers\':\n                        updateGainersLosers(message.data);\n                        break;\n                }\n            }\n\n            function updateMarketPrices(data) {\n                const container = document.getElementById(\'market-prices\');\n                container.innerHTML = \'\';\n\n                for (const [symbol, info] of Object.entries(data)) {\n                    const priceItem = document.createElement(\'div\');\n                    priceItem.className = `price-item price-${info.price_direction}`;\n\n                    const changeClass = info.change_24h >= 0 ? \'positive\' : \'negative\';\n                    const changeIcon = info.change_24h >= 0 ? \'▲\' : \'▼\';\n\n                    priceItem.innerHTML = `\n                        <div class="symbol">${symbol}</div>\n                        <div class="price">$${info.price.toLocaleString()}</div>\n                        <div class="change ${changeClass}">\n                            ${changeIcon} ${Math.abs(info.change_24h).toFixed(2)}%\n                        </div>\n                        <div class="volume">Vol: $${(info.volume_24h / 1000000).toFixed(1)}M</div>\n                    `;\n\n                    container.appendChild(priceItem);\n                }\n            }\n\n            function updateChart(data) {\n                if (!chart) {\n                    initChart();\n                }\n\n                const btcData = data[\'BTC\'];\n                if (btcData) {\n                    const now = new Date();\n                    chartData.push({\n                        x: now,\n                        y: btcData.price\n                    });\n\n                    // Keep only last 50 points\n                    if (chartData.length > 50) {\n                        chartData.shift();\n                    }\n\n                    chart.data.datasets[0].data = chartData;\n                    chart.update(\'none\');\n                }\n            }\n\n            function initChart() {\n                const ctx = document.getElementById(\'price-chart\').getContext(\'2d\');\n                chart = new Chart(ctx, {\n                    type: \'line\',\n                    data: {\n                        datasets: [{\n                            label: \'BTC Price\',\n                            data: chartData,\n                            borderColor: \'#00d4aa\',\n                            backgroundColor: \'rgba(0, 212, 170, 0.1)\',\n                            tension: 0.4,\n                            fill: true\n                        }]\n                    },\n                    options: {\n                        responsive: true,\n                        maintainAspectRatio: false,\n                        plugins: {\n                            legend: {\n                                labels: {\n                                    color: \'#ffffff\'\n                                }\n                            }\n                        },\n                        scales: {\n                            x: {\n                                type: \'time\',\n                                time: {\n                                    displayFormats: {\n                                        minute: \'HH:mm\'\n                                    }\n                                },\n                                ticks: {\n                                    color: \'#888888\'\n                                },\n                                grid: {\n                                    color: \'rgba(255, 255, 255, 0.1)\'\n                                }\n                            },\n                            y: {\n                                ticks: {\n                                    color: \'#888888\',\n                                    callback: function(value) {\n                                        return \'$\' + value.toLocaleString();\n                                    }\n                                },\n                                grid: {\n                                    color: \'rgba(255, 255, 255, 0.1)\'\n                                }\n                            }\n                        },\n                        interaction: {\n                            intersect: false\n                        }\n                    }\n                });\n            }\n\n            function updateGainersLosers(data) {\n                // Update gainers\n                const gainersContainer = document.getElementById(\'top-gainers\');\n                gainersContainer.innerHTML = \'\';\n\n                data.gainers.forEach(coin => {\n                    const item = document.createElement(\'div\');\n                    item.className = \'gainer-item\';\n                    item.innerHTML = `\n                        <div>\n                            <div style="font-weight: bold;">${coin.symbol}</div>\n                            <div style="font-size: 0.8rem; color: #ccc;">${coin.name}</div>\n                        </div>\n                        <div style="text-align: right;">\n                            <div style="font-weight: bold;">$${coin.price.toFixed(4)}</div>\n                            <div class="positive">+${coin.change_24h.toFixed(2)}%</div>\n                        </div>\n                    `;\n                    gainersContainer.appendChild(item);\n                });\n\n                // Update losers\n                const losersContainer = document.getElementById(\'top-losers\');\n                losersContainer.innerHTML = \'\';\n\n                data.losers.forEach(coin => {\n                    const item = document.createElement(\'div\');\n                    item.className = \'loser-item\';\n                    item.innerHTML = `\n                        <div>\n                            <div style="font-weight: bold;">${coin.symbol}</div>\n                            <div style="font-size: 0.8rem; color: #ccc;">${coin.name}</div>\n                        </div>\n                        <div style="text-align: right;">\n                            <div style="font-weight: bold;">$${coin.price.toFixed(4)}</div>\n                            <div class="negative">${coin.change_24h.toFixed(2)}%</div>\n                        </div>\n                    `;\n                    losersContainer.appendChild(item);\n                });\n            }\n\n            // Start connection\n            connectWebSocket();\n        </script>\n    </body>\n    </html>\n    '


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data"""
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal_message({"type": "pong"}, client_id)
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(client_id)


@app.get("/api/market/{symbol}")
async def get_symbol_data(symbol: str):
    """Get detailed data for a specific symbol"""
    await fetcher.start()
    price_data = await fetcher.get_market_data([symbol])
    orderbook = await fetcher.get_orderbook(symbol)
    trades = await fetcher.get_trades(symbol)
    klines = await fetcher.get_klines(symbol, "1h", 24)
    return {
        "symbol": symbol.upper(),
        "price_data": price_data.get(symbol.upper(), {}),
        "orderbook": orderbook,
        "recent_trades": trades,
        "candlesticks": klines,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
