"""
Main Sofia V2 Application with All Features
Beautiful unified interface with cool animations and real-time data
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.adapters.web.fastapi_adapter import FastAPI, HTMLResponse, WebSocket, WebSocketDisconnect

from ..data.real_time_fetcher import fetcher
from ..ml.real_time_predictor import prediction_engine
from ..portfolio.advanced_portfolio_manager import portfolio_manager
from ..scanner.advanced_market_scanner import market_scanner
from ..trading.paper_trading_engine import paper_engine
from ..trading.unified_execution_engine import execution_engine

logger = logging.getLogger(__name__)
app = FastAPI(title="Sofia V2 - AI Trading Platform", version="2.0.0")
templates = Jinja2Templates(directory="src/web_ui/templates")
app.mount("/static", StaticFiles(directory="src/web_ui/static"), name="static")


class SofiaConnectionManager:
    """Manages all WebSocket connections for the main app"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str = "demo"):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(client_id)
        logger.info(f"Sofia client {client_id} connected for user {user_id}")

    def disconnect(self, client_id: str, user_id: str = "demo"):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if user_id in self.user_connections:
            if client_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(client_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        logger.info(f"Sofia client {client_id} disconnected")

    async def broadcast_to_all(self, message: dict):
        """Broadcast to all connected clients"""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_to_user(self, message: dict, user_id: str):
        """Send message to specific user"""
        if user_id in self.user_connections:
            disconnected = []
            for client_id in self.user_connections[user_id]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error sending to {client_id}: {e}")
                        disconnected.append(client_id)
            for client_id in disconnected:
                self.disconnect(client_id, user_id)


sofia_manager = SofiaConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Start all Sofia V2 engines on startup"""
    logger.info("Starting Sofia V2 Trading Platform...")
    await execution_engine.start()
    asyncio.create_task(broadcast_market_data())
    asyncio.create_task(broadcast_predictions())
    asyncio.create_task(broadcast_scanner_signals())
    logger.info("Sofia V2 Trading Platform fully operational! 🚀")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await execution_engine.stop()
    logger.info("Sofia V2 Trading Platform shutdown complete")


@app.get("/", response_class=HTMLResponse)
async def sofia_main():
    """Main Sofia V2 application page"""
    return '\n    <!DOCTYPE html>\n    <html lang="en">\n    <head>\n        <meta charset="UTF-8">\n        <meta name="viewport" content="width=device-width, initial-scale=1.0">\n        <title>Sofia V2 - AI Trading Platform</title>\n        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>\n        <style>\n            * {\n                margin: 0;\n                padding: 0;\n                box-sizing: border-box;\n            }\n\n            body {\n                font-family: \'Inter\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;\n                background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #16213e 100%);\n                color: #ffffff;\n                min-height: 100vh;\n                overflow-x: hidden;\n            }\n\n            /* Animated background particles */\n            .bg-particles {\n                position: fixed;\n                top: 0;\n                left: 0;\n                width: 100%;\n                height: 100%;\n                z-index: -1;\n                overflow: hidden;\n            }\n\n            .particle {\n                position: absolute;\n                background: rgba(0, 212, 170, 0.1);\n                border-radius: 50%;\n                animation: float 6s ease-in-out infinite;\n            }\n\n            @keyframes float {\n                0%, 100% { transform: translateY(0px) rotate(0deg); }\n                50% { transform: translateY(-20px) rotate(180deg); }\n            }\n\n            .particle:nth-child(1) { width: 4px; height: 4px; top: 10%; left: 10%; animation-delay: 0s; }\n            .particle:nth-child(2) { width: 6px; height: 6px; top: 20%; left: 80%; animation-delay: 1s; }\n            .particle:nth-child(3) { width: 3px; height: 3px; top: 60%; left: 20%; animation-delay: 2s; }\n            .particle:nth-child(4) { width: 5px; height: 5px; top: 80%; left: 90%; animation-delay: 3s; }\n            .particle:nth-child(5) { width: 4px; height: 4px; top: 30%; left: 60%; animation-delay: 4s; }\n\n            /* Header */\n            .header {\n                background: rgba(10, 10, 15, 0.95);\n                backdrop-filter: blur(20px);\n                border-bottom: 1px solid rgba(0, 212, 170, 0.2);\n                padding: 1rem 2rem;\n                position: sticky;\n                top: 0;\n                z-index: 100;\n                transition: all 0.3s ease;\n            }\n\n            .header-content {\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n                max-width: 1400px;\n                margin: 0 auto;\n            }\n\n            .logo {\n                display: flex;\n                align-items: center;\n                gap: 12px;\n            }\n\n            .logo-icon {\n                width: 40px;\n                height: 40px;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                border-radius: 10px;\n                display: flex;\n                align-items: center;\n                justify-content: center;\n                font-size: 18px;\n                font-weight: bold;\n                animation: glow 2s ease-in-out infinite alternate;\n            }\n\n            @keyframes glow {\n                from { box-shadow: 0 0 10px rgba(0, 212, 170, 0.3); }\n                to { box-shadow: 0 0 20px rgba(0, 212, 170, 0.6); }\n            }\n\n            .logo-text {\n                font-size: 1.8rem;\n                font-weight: 700;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                -webkit-background-clip: text;\n                -webkit-text-fill-color: transparent;\n                background-clip: text;\n            }\n\n            .nav-tabs {\n                display: flex;\n                gap: 8px;\n                background: rgba(255, 255, 255, 0.05);\n                border-radius: 12px;\n                padding: 6px;\n            }\n\n            .nav-tab {\n                padding: 10px 20px;\n                border-radius: 8px;\n                cursor: pointer;\n                transition: all 0.3s ease;\n                font-weight: 500;\n                border: none;\n                background: transparent;\n                color: rgba(255, 255, 255, 0.7);\n            }\n\n            .nav-tab:hover {\n                color: #ffffff;\n                background: rgba(255, 255, 255, 0.1);\n            }\n\n            .nav-tab.active {\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                color: #ffffff;\n                transform: translateY(-1px);\n                box-shadow: 0 4px 12px rgba(0, 212, 170, 0.3);\n            }\n\n            .status-indicator {\n                display: flex;\n                align-items: center;\n                gap: 8px;\n                font-size: 0.9rem;\n                color: #00ff88;\n            }\n\n            .status-dot {\n                width: 8px;\n                height: 8px;\n                background: #00ff88;\n                border-radius: 50%;\n                animation: pulse 2s infinite;\n            }\n\n            @keyframes pulse {\n                0% { opacity: 1; transform: scale(1); }\n                50% { opacity: 0.6; transform: scale(1.3); }\n                100% { opacity: 1; transform: scale(1); }\n            }\n\n            /* Main content */\n            .main-container {\n                max-width: 1400px;\n                margin: 0 auto;\n                padding: 2rem;\n            }\n\n            .tab-content {\n                display: none;\n                animation: fadeIn 0.5s ease-in-out;\n            }\n\n            .tab-content.active {\n                display: block;\n            }\n\n            @keyframes fadeIn {\n                from { opacity: 0; transform: translateY(20px); }\n                to { opacity: 1; transform: translateY(0); }\n            }\n\n            /* Dashboard Grid */\n            .dashboard-grid {\n                display: grid;\n                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));\n                gap: 2rem;\n                margin-bottom: 2rem;\n            }\n\n            .card {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                border-radius: 16px;\n                padding: 1.5rem;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);\n                position: relative;\n                overflow: hidden;\n            }\n\n            .card::before {\n                content: \'\';\n                position: absolute;\n                top: 0;\n                left: -100%;\n                width: 100%;\n                height: 100%;\n                background: linear-gradient(90deg, transparent, rgba(0, 212, 170, 0.1), transparent);\n                transition: left 0.5s;\n            }\n\n            .card:hover {\n                transform: translateY(-8px) scale(1.02);\n                border-color: rgba(0, 212, 170, 0.4);\n                box-shadow: 0 20px 40px rgba(0, 212, 170, 0.1);\n            }\n\n            .card:hover::before {\n                left: 100%;\n            }\n\n            .card-header {\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n                margin-bottom: 1rem;\n            }\n\n            .card-title {\n                font-size: 1.1rem;\n                font-weight: 600;\n                color: #ffffff;\n                display: flex;\n                align-items: center;\n                gap: 8px;\n            }\n\n            .card-icon {\n                font-size: 1.2rem;\n            }\n\n            .card-value {\n                font-size: 2rem;\n                font-weight: 700;\n                margin: 0.5rem 0;\n            }\n\n            .card-change {\n                font-size: 0.9rem;\n                font-weight: 500;\n                display: flex;\n                align-items: center;\n                gap: 4px;\n            }\n\n            .positive {\n                color: #00ff88;\n            }\n\n            .negative {\n                color: #ff4757;\n            }\n\n            .neutral {\n                color: #ffa502;\n            }\n\n            /* Trading interface */\n            .trading-interface {\n                display: grid;\n                grid-template-columns: 350px 1fr 300px;\n                gap: 2rem;\n                height: 80vh;\n            }\n\n            .trading-panel {\n                background: rgba(255, 255, 255, 0.05);\n                border-radius: 16px;\n                padding: 1.5rem;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n            }\n\n            .chart-container {\n                height: 400px;\n                margin-top: 1rem;\n                position: relative;\n            }\n\n            /* Live data animations */\n            .price-update {\n                animation: priceFlash 0.5s ease-in-out;\n            }\n\n            @keyframes priceFlash {\n                0% { background-color: rgba(0, 212, 170, 0.3); }\n                100% { background-color: transparent; }\n            }\n\n            .signal-alert {\n                position: fixed;\n                top: 100px;\n                right: 2rem;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                color: white;\n                padding: 1rem 1.5rem;\n                border-radius: 12px;\n                box-shadow: 0 8px 25px rgba(0, 212, 170, 0.3);\n                transform: translateX(400px);\n                opacity: 0;\n                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);\n                z-index: 1000;\n                max-width: 300px;\n            }\n\n            .signal-alert.show {\n                transform: translateX(0);\n                opacity: 1;\n            }\n\n            .signal-alert .alert-title {\n                font-weight: bold;\n                margin-bottom: 0.5rem;\n            }\n\n            .signal-alert .alert-message {\n                font-size: 0.9rem;\n            }\n\n            /* Loading states */\n            .skeleton {\n                background: linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);\n                background-size: 200% 100%;\n                animation: skeleton-loading 1.5s infinite;\n                border-radius: 4px;\n                height: 20px;\n                margin: 8px 0;\n            }\n\n            @keyframes skeleton-loading {\n                0% { background-position: 200% 0; }\n                100% { background-position: -200% 0; }\n            }\n\n            /* Buttons */\n            .btn {\n                padding: 12px 24px;\n                border-radius: 10px;\n                border: none;\n                font-weight: 600;\n                cursor: pointer;\n                transition: all 0.3s ease;\n                display: inline-flex;\n                align-items: center;\n                gap: 8px;\n                text-decoration: none;\n            }\n\n            .btn-primary {\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                color: white;\n            }\n\n            .btn-primary:hover {\n                transform: translateY(-2px);\n                box-shadow: 0 8px 20px rgba(0, 212, 170, 0.4);\n            }\n\n            .btn-danger {\n                background: linear-gradient(45deg, #ff4757, #ff6b7d);\n                color: white;\n            }\n\n            .btn-danger:hover {\n                transform: translateY(-2px);\n                box-shadow: 0 8px 20px rgba(255, 71, 87, 0.4);\n            }\n\n            /* Responsive */\n            @media (max-width: 1200px) {\n                .trading-interface {\n                    grid-template-columns: 1fr;\n                    height: auto;\n                }\n            }\n\n            @media (max-width: 768px) {\n                .header-content {\n                    flex-direction: column;\n                    gap: 1rem;\n                }\n\n                .nav-tabs {\n                    order: -1;\n                }\n\n                .main-container {\n                    padding: 1rem;\n                }\n\n                .dashboard-grid {\n                    grid-template-columns: 1fr;\n                }\n            }\n        </style>\n    </head>\n    <body>\n        <!-- Animated background -->\n        <div class="bg-particles">\n            <div class="particle"></div>\n            <div class="particle"></div>\n            <div class="particle"></div>\n            <div class="particle"></div>\n            <div class="particle"></div>\n        </div>\n\n        <!-- Header -->\n        <header class="header">\n            <div class="header-content">\n                <div class="logo">\n                    <div class="logo-icon">S</div>\n                    <div class="logo-text">Sofia V2</div>\n                </div>\n\n                <nav class="nav-tabs">\n                    <button class="nav-tab active" onclick="switchTab(\'dashboard\')">Dashboard</button>\n                    <button class="nav-tab" onclick="switchTab(\'trading\')">Trading</button>\n                    <button class="nav-tab" onclick="switchTab(\'portfolio\')">Portfolio</button>\n                    <button class="nav-tab" onclick="switchTab(\'scanner\')">Scanner</button>\n                    <button class="nav-tab" onclick="switchTab(\'ai\')">AI Predictions</button>\n                </nav>\n\n                <div class="status-indicator">\n                    <div class="status-dot"></div>\n                    <span id="connection-status">Connected</span>\n                </div>\n            </div>\n        </header>\n\n        <!-- Main content -->\n        <main class="main-container">\n\n            <!-- Dashboard Tab -->\n            <div id="dashboard" class="tab-content active">\n                <div class="dashboard-grid">\n                    <div class="card">\n                        <div class="card-header">\n                            <div class="card-title">\n                                <span class="card-icon">💰</span>\n                                Portfolio Value\n                            </div>\n                        </div>\n                        <div class="card-value positive" id="portfolio-value">$10,000.00</div>\n                        <div class="card-change" id="portfolio-change">\n                            <span>↗️ +0.00%</span>\n                        </div>\n                    </div>\n\n                    <div class="card">\n                        <div class="card-header">\n                            <div class="card-title">\n                                <span class="card-icon">📈</span>\n                                P&L Today\n                            </div>\n                        </div>\n                        <div class="card-value neutral" id="pnl-today">$0.00</div>\n                        <div class="card-change" id="pnl-change">\n                            <span>0.00%</span>\n                        </div>\n                    </div>\n\n                    <div class="card">\n                        <div class="card-header">\n                            <div class="card-title">\n                                <span class="card-icon">🎯</span>\n                                Win Rate\n                            </div>\n                        </div>\n                        <div class="card-value neutral" id="win-rate">0%</div>\n                        <div class="card-change">\n                            <span id="total-trades">0 trades</span>\n                        </div>\n                    </div>\n\n                    <div class="card">\n                        <div class="card-header">\n                            <div class="card-title">\n                                <span class="card-icon">🔥</span>\n                                Active Signals\n                            </div>\n                        </div>\n                        <div class="card-value positive" id="active-signals">0</div>\n                        <div class="card-change">\n                            <span>Scanner active</span>\n                        </div>\n                    </div>\n                </div>\n\n                <!-- Market overview -->\n                <div class="card">\n                    <div class="card-header">\n                        <div class="card-title">\n                            <span class="card-icon">📊</span>\n                            Market Overview\n                        </div>\n                    </div>\n                    <div class="chart-container">\n                        <canvas id="market-chart"></canvas>\n                    </div>\n                </div>\n\n                <!-- Recent signals -->\n                <div class="card">\n                    <div class="card-header">\n                        <div class="card-title">\n                            <span class="card-icon">🚨</span>\n                            Recent Trading Signals\n                        </div>\n                    </div>\n                    <div id="recent-signals">\n                        <div class="skeleton"></div>\n                        <div class="skeleton"></div>\n                        <div class="skeleton"></div>\n                    </div>\n                </div>\n            </div>\n\n            <!-- Trading Tab -->\n            <div id="trading" class="tab-content">\n                <div class="trading-interface">\n                    <div class="trading-panel">\n                        <h3>Quick Trade</h3>\n                        <p>Trading interface will be loaded here...</p>\n                    </div>\n\n                    <div class="trading-panel">\n                        <div class="card-title">Live Price Chart</div>\n                        <div class="chart-container">\n                            <canvas id="trading-chart"></canvas>\n                        </div>\n                    </div>\n\n                    <div class="trading-panel">\n                        <h3>Order Book</h3>\n                        <p>Order book will be loaded here...</p>\n                    </div>\n                </div>\n            </div>\n\n            <!-- Portfolio Tab -->\n            <div id="portfolio" class="tab-content">\n                <div class="card">\n                    <div class="card-title">Portfolio Analysis</div>\n                    <p>Detailed portfolio analytics will be loaded here...</p>\n                </div>\n            </div>\n\n            <!-- Scanner Tab -->\n            <div id="scanner" class="tab-content">\n                <div class="card">\n                    <div class="card-title">Market Scanner</div>\n                    <p>Market scanning results will be loaded here...</p>\n                </div>\n            </div>\n\n            <!-- AI Predictions Tab -->\n            <div id="ai" class="tab-content">\n                <div class="card">\n                    <div class="card-title">AI Predictions</div>\n                    <div id="ai-predictions">\n                        <div class="skeleton"></div>\n                        <div class="skeleton"></div>\n                        <div class="skeleton"></div>\n                    </div>\n                </div>\n            </div>\n        </main>\n\n        <!-- Signal alert template -->\n        <div id="signal-alert" class="signal-alert">\n            <div class="alert-title"></div>\n            <div class="alert-message"></div>\n        </div>\n\n        <script>\n            // Global state\n            let ws;\n            let marketChart;\n            let tradingChart;\n            let currentTab = \'dashboard\';\n            let portfolioData = null;\n\n            // Initialize application\n            document.addEventListener(\'DOMContentLoaded\', function() {\n                initializeCharts();\n                connectWebSocket();\n                loadInitialData();\n            });\n\n            // Tab switching\n            function switchTab(tabName) {\n                // Update nav tabs\n                document.querySelectorAll(\'.nav-tab\').forEach(tab => {\n                    tab.classList.remove(\'active\');\n                });\n                event.target.classList.add(\'active\');\n\n                // Update content\n                document.querySelectorAll(\'.tab-content\').forEach(content => {\n                    content.classList.remove(\'active\');\n                });\n                document.getElementById(tabName).classList.add(\'active\');\n\n                currentTab = tabName;\n\n                // Load tab-specific data\n                loadTabData(tabName);\n            }\n\n            // WebSocket connection\n            function connectWebSocket() {\n                const protocol = window.location.protocol === \'https:\' ? \'wss:\' : \'ws:\';\n                const wsUrl = `${protocol}//${window.location.host}/ws/main`;\n\n                ws = new WebSocket(wsUrl);\n\n                ws.onopen = function() {\n                    console.log(\'Connected to Sofia V2\');\n                    document.getElementById(\'connection-status\').textContent = \'Connected\';\n                };\n\n                ws.onmessage = function(event) {\n                    const message = JSON.parse(event.data);\n                    handleWebSocketMessage(message);\n                };\n\n                ws.onclose = function() {\n                    console.log(\'Connection lost, reconnecting...\');\n                    document.getElementById(\'connection-status\').textContent = \'Reconnecting...\';\n                    setTimeout(connectWebSocket, 3000);\n                };\n\n                ws.onerror = function(error) {\n                    console.error(\'WebSocket error:\', error);\n                    document.getElementById(\'connection-status\').textContent = \'Connection Error\';\n                };\n            }\n\n            // Handle WebSocket messages\n            function handleWebSocketMessage(message) {\n                switch(message.type) {\n                    case \'market_data\':\n                        updateMarketData(message.data);\n                        break;\n                    case \'portfolio_update\':\n                        updatePortfolioData(message.data);\n                        break;\n                    case \'trading_signal\':\n                        showTradingSignal(message.data);\n                        break;\n                    case \'ai_prediction\':\n                        updateAIPredictions(message.data);\n                        break;\n                    case \'scanner_results\':\n                        updateScannerResults(message.data);\n                        break;\n                }\n            }\n\n            // Initialize charts\n            function initializeCharts() {\n                // Market overview chart\n                const marketCtx = document.getElementById(\'market-chart\').getContext(\'2d\');\n                marketChart = new Chart(marketCtx, {\n                    type: \'line\',\n                    data: {\n                        labels: [],\n                        datasets: [{\n                            label: \'BTC\',\n                            data: [],\n                            borderColor: \'#00d4aa\',\n                            backgroundColor: \'rgba(0, 212, 170, 0.1)\',\n                            tension: 0.4,\n                            fill: true\n                        }, {\n                            label: \'ETH\',\n                            data: [],\n                            borderColor: \'#00b4d8\',\n                            backgroundColor: \'rgba(0, 180, 216, 0.1)\',\n                            tension: 0.4,\n                            fill: true\n                        }]\n                    },\n                    options: {\n                        responsive: true,\n                        maintainAspectRatio: false,\n                        plugins: {\n                            legend: {\n                                labels: { color: \'#ffffff\' }\n                            }\n                        },\n                        scales: {\n                            x: {\n                                ticks: { color: \'#888888\' },\n                                grid: { color: \'rgba(255, 255, 255, 0.1)\' }\n                            },\n                            y: {\n                                ticks: { color: \'#888888\' },\n                                grid: { color: \'rgba(255, 255, 255, 0.1)\' }\n                            }\n                        }\n                    }\n                });\n\n                // Trading chart\n                const tradingCtx = document.getElementById(\'trading-chart\')?.getContext(\'2d\');\n                if (tradingCtx) {\n                    tradingChart = new Chart(tradingCtx, {\n                        type: \'candlestick\',\n                        data: { datasets: [] },\n                        options: {\n                            responsive: true,\n                            maintainAspectRatio: false,\n                            plugins: {\n                                legend: { labels: { color: \'#ffffff\' } }\n                            }\n                        }\n                    });\n                }\n            }\n\n            // Update market data\n            function updateMarketData(data) {\n                // Update dashboard cards with animation\n                Object.keys(data).forEach(symbol => {\n                    const symbolData = data[symbol];\n                    const element = document.getElementById(`${symbol.toLowerCase()}-price`);\n                    if (element) {\n                        element.classList.add(\'price-update\');\n                        element.textContent = `$${symbolData.price.toLocaleString()}`;\n                        setTimeout(() => element.classList.remove(\'price-update\'), 500);\n                    }\n                });\n\n                // Update chart\n                if (marketChart && data.BTC && data.ETH) {\n                    const now = new Date().toLocaleTimeString();\n                    marketChart.data.labels.push(now);\n                    marketChart.data.datasets[0].data.push(data.BTC.price);\n                    marketChart.data.datasets[1].data.push(data.ETH.price);\n\n                    // Keep only last 20 data points\n                    if (marketChart.data.labels.length > 20) {\n                        marketChart.data.labels.shift();\n                        marketChart.data.datasets[0].data.shift();\n                        marketChart.data.datasets[1].data.shift();\n                    }\n\n                    marketChart.update(\'none\');\n                }\n            }\n\n            // Update portfolio data\n            function updatePortfolioData(data) {\n                portfolioData = data;\n\n                // Update dashboard cards\n                document.getElementById(\'portfolio-value\').textContent = `$${data.total_value.toLocaleString()}`;\n                document.getElementById(\'pnl-today\').textContent = `$${data.total_pnl.toFixed(2)}`;\n                document.getElementById(\'win-rate\').textContent = `${(data.win_rate * 100).toFixed(1)}%`;\n                document.getElementById(\'total-trades\').textContent = `${data.total_trades} trades`;\n\n                // Update change indicators\n                const pnlPercent = data.total_pnl_percent;\n                const changeEl = document.getElementById(\'portfolio-change\');\n                const pnlEl = document.getElementById(\'pnl-today\');\n\n                if (pnlPercent > 0) {\n                    changeEl.innerHTML = `<span>↗️ +${pnlPercent.toFixed(2)}%</span>`;\n                    changeEl.className = \'card-change positive\';\n                    pnlEl.className = \'card-value positive\';\n                } else if (pnlPercent < 0) {\n                    changeEl.innerHTML = `<span>↘️ ${pnlPercent.toFixed(2)}%</span>`;\n                    changeEl.className = \'card-change negative\';\n                    pnlEl.className = \'card-value negative\';\n                } else {\n                    changeEl.innerHTML = `<span>→ 0.00%</span>`;\n                    changeEl.className = \'card-change neutral\';\n                    pnlEl.className = \'card-value neutral\';\n                }\n            }\n\n            // Show trading signal alert\n            function showTradingSignal(signal) {\n                const alertEl = document.getElementById(\'signal-alert\');\n                const titleEl = alertEl.querySelector(\'.alert-title\');\n                const messageEl = alertEl.querySelector(\'.alert-message\');\n\n                titleEl.textContent = `${signal.symbol} ${signal.signal_type.toUpperCase()}`;\n                messageEl.textContent = signal.message;\n\n                alertEl.classList.add(\'show\');\n\n                // Update active signals count\n                const currentCount = parseInt(document.getElementById(\'active-signals\').textContent);\n                document.getElementById(\'active-signals\').textContent = currentCount + 1;\n\n                // Auto hide after 5 seconds\n                setTimeout(() => {\n                    alertEl.classList.remove(\'show\');\n                }, 5000);\n            }\n\n            // Update AI predictions\n            function updateAIPredictions(predictions) {\n                const container = document.getElementById(\'ai-predictions\');\n                container.innerHTML = \'\';\n\n                Object.keys(predictions).forEach(symbol => {\n                    const pred = predictions[symbol];\n                    const predEl = document.createElement(\'div\');\n                    predEl.className = \'prediction-item\';\n                    predEl.innerHTML = `\n                        <div class="prediction-header">\n                            <strong>${symbol}</strong>\n                            <span class="confidence">Confidence: ${pred.predictions[\'24h\'].confidence.toFixed(1)}%</span>\n                        </div>\n                        <div class="prediction-details">\n                            24h: $${pred.predictions[\'24h\'].price.toFixed(2)}\n                            (${pred.trend_direction})\n                        </div>\n                    `;\n                    container.appendChild(predEl);\n                });\n            }\n\n            // Load initial data\n            function loadInitialData() {\n                if (ws && ws.readyState === WebSocket.OPEN) {\n                    ws.send(JSON.stringify({type: \'get_dashboard_data\'}));\n                }\n            }\n\n            // Load tab-specific data\n            function loadTabData(tabName) {\n                if (ws && ws.readyState === WebSocket.OPEN) {\n                    ws.send(JSON.stringify({type: \'load_tab\', tab: tabName}));\n                }\n            }\n        </script>\n    </body>\n    </html>\n    '


@app.websocket("/ws/main")
async def main_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for the Sofia V2 app"""
    client_id = str(uuid.uuid4())
    user_id = "demo"
    await sofia_manager.connect(websocket, client_id, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "get_dashboard_data":
                await send_dashboard_data(user_id)
            elif message.get("type") == "load_tab":
                await send_tab_data(user_id, message.get("tab"))
    except WebSocketDisconnect:
        sofia_manager.disconnect(client_id, user_id)


async def send_dashboard_data(user_id: str):
    """Send initial dashboard data"""
    try:
        portfolio = paper_engine.get_portfolio_summary(user_id)
        if portfolio:
            await sofia_manager.send_to_user(
                {"type": "portfolio_update", "data": portfolio}, user_id
            )
        predictions = prediction_engine.get_all_predictions()
        if predictions:
            await sofia_manager.send_to_user(
                {"type": "ai_prediction", "data": predictions}, user_id
            )
    except Exception as e:
        logger.error(f"Error sending dashboard data: {e}")


async def send_tab_data(user_id: str, tab_name: str):
    """Send tab-specific data"""
    try:
        if tab_name == "scanner":
            overview = await market_scanner.get_market_overview()
            await sofia_manager.send_to_user({"type": "scanner_results", "data": overview}, user_id)
    except Exception as e:
        logger.error(f"Error sending tab data for {tab_name}: {e}")


async def broadcast_market_data():
    """Broadcast real-time market data to all clients"""
    symbols = ["bitcoin", "ethereum", "solana", "binancecoin", "cardano"]
    while True:
        try:
            market_data = await fetcher.get_market_data(symbols)
            if market_data:
                await sofia_manager.broadcast_to_all({"type": "market_data", "data": market_data})
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error broadcasting market data: {e}")
            await asyncio.sleep(10)


async def broadcast_predictions():
    """Broadcast AI predictions to all clients"""
    while True:
        try:
            predictions = prediction_engine.get_all_predictions()
            if predictions:
                await sofia_manager.broadcast_to_all({"type": "ai_prediction", "data": predictions})
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Error broadcasting predictions: {e}")
            await asyncio.sleep(60)


async def broadcast_scanner_signals():
    """Broadcast scanner signals to all clients"""
    while True:
        try:
            signals = []
            for symbol in ["BTC", "ETH", "SOL", "BNB", "ADA"]:
                symbol_signals = market_scanner.get_symbol_signals(symbol, 1)
                if symbol_signals:
                    signals.extend(symbol_signals)
            for signal in signals:
                await sofia_manager.broadcast_to_all({"type": "trading_signal", "data": signal})
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error broadcasting signals: {e}")
            await asyncio.sleep(30)


@app.get("/api/portfolio/{user_id}")
async def get_portfolio(user_id: str):
    """Get portfolio data"""
    return await portfolio_manager.get_portfolio_analytics(user_id)


@app.get("/api/market/overview")
async def get_market_overview():
    """Get market overview"""
    return await market_scanner.get_market_overview()


@app.get("/api/predictions")
async def get_predictions():
    """Get AI predictions"""
    return prediction_engine.get_all_predictions()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
