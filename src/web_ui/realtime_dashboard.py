"""
Real-Time Trading Dashboard with WebSocket
Advanced live trading interface with real crypto prices
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict
import logging
from decimal import Decimal
import uuid

from ..data.real_time_fetcher import fetcher
from ..auth.dependencies import get_current_active_user

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

# Watched symbols for dashboard
WATCHED_SYMBOLS = ["bitcoin", "ethereum", "solana", "binancecoin", "cardano", "polkadot", "chainlink", "litecoin"]

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
                # Get market data
                market_data = await fetcher.get_market_data(WATCHED_SYMBOLS)
                
                if market_data:
                    # Calculate price changes since last update
                    for symbol, data in market_data.items():
                        if symbol in self.last_prices:
                            data["price_direction"] = "up" if data["price"] > self.last_prices[symbol] else "down"
                        else:
                            data["price_direction"] = "neutral"
                        self.last_prices[symbol] = data["price"]
                    
                    # Broadcast to all connected clients
                    await manager.broadcast({
                        "type": "market_update",
                        "data": market_data,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                # Get top gainers/losers
                gainers_losers = await fetcher.get_top_gainers_losers(5)
                if gainers_losers:
                    await manager.broadcast({
                        "type": "gainers_losers",
                        "data": gainers_losers,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                await asyncio.sleep(3)  # Update every 3 seconds
                
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
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sofia V2 - Real-Time Trading Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0f0f23, #1a1a3a);
                color: #ffffff;
                min-height: 100vh;
                overflow-x: hidden;
            }
            
            .header {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                padding: 1rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .logo {
                font-size: 1.5rem;
                font-weight: bold;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                display: inline-block;
            }
            
            .status {
                float: right;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .status-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #00d4aa;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(1.2); }
                100% { opacity: 1; transform: scale(1); }
            }
            
            .main-grid {
                display: grid;
                grid-template-columns: 1fr 300px;
                gap: 20px;
                padding: 20px;
                min-height: calc(100vh - 80px);
            }
            
            .left-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            
            .right-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            
            .card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.3s ease;
            }
            
            .card:hover {
                transform: translateY(-5px);
                border-color: rgba(0, 212, 170, 0.3);
                box-shadow: 0 10px 30px rgba(0, 212, 170, 0.1);
            }
            
            .card-title {
                font-size: 1.2rem;
                font-weight: bold;
                margin-bottom: 15px;
                color: #00d4aa;
            }
            
            .price-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 15px;
            }
            
            .price-item {
                background: rgba(255, 255, 255, 0.03);
                border-radius: 10px;
                padding: 15px;
                border-left: 3px solid #00d4aa;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .price-item:hover {
                background: rgba(255, 255, 255, 0.08);
                transform: translateX(5px);
            }
            
            .price-item.price-up {
                border-left-color: #00ff88;
                background: rgba(0, 255, 136, 0.05);
            }
            
            .price-item.price-down {
                border-left-color: #ff4757;
                background: rgba(255, 71, 87, 0.05);
            }
            
            .symbol {
                font-weight: bold;
                font-size: 0.9rem;
                color: #ccc;
                text-transform: uppercase;
            }
            
            .price {
                font-size: 1.3rem;
                font-weight: bold;
                margin: 5px 0;
            }
            
            .change {
                font-size: 0.85rem;
                font-weight: bold;
            }
            
            .positive {
                color: #00ff88;
            }
            
            .negative {
                color: #ff4757;
            }
            
            .chart-container {
                height: 300px;
                margin-top: 10px;
            }
            
            .gainers-losers {
                max-height: 400px;
                overflow-y: auto;
            }
            
            .gainer-item, .loser-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                margin: 5px 0;
                border-radius: 8px;
                transition: background 0.2s ease;
            }
            
            .gainer-item {
                background: rgba(0, 255, 136, 0.1);
                border-left: 3px solid #00ff88;
            }
            
            .loser-item {
                background: rgba(255, 71, 87, 0.1);
                border-left: 3px solid #ff4757;
            }
            
            .gainer-item:hover, .loser-item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .volume {
                font-size: 0.8rem;
                color: #888;
            }
            
            .loading {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100px;
            }
            
            .spinner {
                width: 40px;
                height: 40px;
                border: 4px solid rgba(0, 212, 170, 0.3);
                border-top: 4px solid #00d4aa;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            @media (max-width: 768px) {
                .main-grid {
                    grid-template-columns: 1fr;
                }
                
                .price-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <header class="header">
            <div class="logo">Sofia V2 Trading Dashboard</div>
            <div class="status">
                <div class="status-dot"></div>
                <span id="connection-status">Connecting...</span>
            </div>
        </header>
        
        <div class="main-grid">
            <div class="left-panel">
                <div class="card">
                    <div class="card-title">Live Market Prices</div>
                    <div id="market-prices" class="price-grid">
                        <div class="loading">
                            <div class="spinner"></div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Price Chart</div>
                    <div class="chart-container">
                        <canvas id="price-chart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="right-panel">
                <div class="card">
                    <div class="card-title">🚀 Top Gainers</div>
                    <div id="top-gainers" class="gainers-losers">
                        <div class="loading">
                            <div class="spinner"></div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">📉 Top Losers</div>
                    <div id="top-losers" class="gainers-losers">
                        <div class="loading">
                            <div class="spinner"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // WebSocket connection
            let ws;
            let chart;
            let chartData = [];
            
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    console.log('Connected to WebSocket');
                    document.getElementById('connection-status').textContent = 'Connected';
                };
                
                ws.onmessage = function(event) {
                    const message = JSON.parse(event.data);
                    handleWebSocketMessage(message);
                };
                
                ws.onclose = function() {
                    console.log('WebSocket connection closed');
                    document.getElementById('connection-status').textContent = 'Reconnecting...';
                    setTimeout(connectWebSocket, 3000);
                };
                
                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    document.getElementById('connection-status').textContent = 'Connection Error';
                };
            }
            
            function handleWebSocketMessage(message) {
                switch(message.type) {
                    case 'market_update':
                        updateMarketPrices(message.data);
                        updateChart(message.data);
                        break;
                    case 'gainers_losers':
                        updateGainersLosers(message.data);
                        break;
                }
            }
            
            function updateMarketPrices(data) {
                const container = document.getElementById('market-prices');
                container.innerHTML = '';
                
                for (const [symbol, info] of Object.entries(data)) {
                    const priceItem = document.createElement('div');
                    priceItem.className = `price-item price-${info.price_direction}`;
                    
                    const changeClass = info.change_24h >= 0 ? 'positive' : 'negative';
                    const changeIcon = info.change_24h >= 0 ? '▲' : '▼';
                    
                    priceItem.innerHTML = `
                        <div class="symbol">${symbol}</div>
                        <div class="price">$${info.price.toLocaleString()}</div>
                        <div class="change ${changeClass}">
                            ${changeIcon} ${Math.abs(info.change_24h).toFixed(2)}%
                        </div>
                        <div class="volume">Vol: $${(info.volume_24h / 1000000).toFixed(1)}M</div>
                    `;
                    
                    container.appendChild(priceItem);
                }
            }
            
            function updateChart(data) {
                if (!chart) {
                    initChart();
                }
                
                const btcData = data['BTC'];
                if (btcData) {
                    const now = new Date();
                    chartData.push({
                        x: now,
                        y: btcData.price
                    });
                    
                    // Keep only last 50 points
                    if (chartData.length > 50) {
                        chartData.shift();
                    }
                    
                    chart.data.datasets[0].data = chartData;
                    chart.update('none');
                }
            }
            
            function initChart() {
                const ctx = document.getElementById('price-chart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'BTC Price',
                            data: chartData,
                            borderColor: '#00d4aa',
                            backgroundColor: 'rgba(0, 212, 170, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#ffffff'
                                }
                            }
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    displayFormats: {
                                        minute: 'HH:mm'
                                    }
                                },
                                ticks: {
                                    color: '#888888'
                                },
                                grid: {
                                    color: 'rgba(255, 255, 255, 0.1)'
                                }
                            },
                            y: {
                                ticks: {
                                    color: '#888888',
                                    callback: function(value) {
                                        return '$' + value.toLocaleString();
                                    }
                                },
                                grid: {
                                    color: 'rgba(255, 255, 255, 0.1)'
                                }
                            }
                        },
                        interaction: {
                            intersect: false
                        }
                    }
                });
            }
            
            function updateGainersLosers(data) {
                // Update gainers
                const gainersContainer = document.getElementById('top-gainers');
                gainersContainer.innerHTML = '';
                
                data.gainers.forEach(coin => {
                    const item = document.createElement('div');
                    item.className = 'gainer-item';
                    item.innerHTML = `
                        <div>
                            <div style="font-weight: bold;">${coin.symbol}</div>
                            <div style="font-size: 0.8rem; color: #ccc;">${coin.name}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-weight: bold;">$${coin.price.toFixed(4)}</div>
                            <div class="positive">+${coin.change_24h.toFixed(2)}%</div>
                        </div>
                    `;
                    gainersContainer.appendChild(item);
                });
                
                // Update losers
                const losersContainer = document.getElementById('top-losers');
                losersContainer.innerHTML = '';
                
                data.losers.forEach(coin => {
                    const item = document.createElement('div');
                    item.className = 'loser-item';
                    item.innerHTML = `
                        <div>
                            <div style="font-weight: bold;">${coin.symbol}</div>
                            <div style="font-size: 0.8rem; color: #ccc;">${coin.name}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-weight: bold;">$${coin.price.toFixed(4)}</div>
                            <div class="negative">${coin.change_24h.toFixed(2)}%</div>
                        </div>
                    `;
                    losersContainer.appendChild(item);
                });
            }
            
            // Start connection
            connectWebSocket();
        </script>
    </body>
    </html>
    """

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data"""
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Handle client messages if needed
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
    
    # Get current price
    price_data = await fetcher.get_market_data([symbol])
    
    # Get order book
    orderbook = await fetcher.get_orderbook(symbol)
    
    # Get recent trades
    trades = await fetcher.get_trades(symbol)
    
    # Get candlestick data
    klines = await fetcher.get_klines(symbol, "1h", 24)
    
    return {
        "symbol": symbol.upper(),
        "price_data": price_data.get(symbol.upper(), {}),
        "orderbook": orderbook,
        "recent_trades": trades,
        "candlesticks": klines,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)