"""
Main Sofia V2 Application with All Features
Beautiful unified interface with cool animations and real-time data
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

    # Start all engines
    await execution_engine.start()  # This starts all other engines too

    # Start data broadcasting
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
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sofia V2 - AI Trading Platform</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #16213e 100%);
                color: #ffffff;
                min-height: 100vh;
                overflow-x: hidden;
            }

            /* Animated background particles */
            .bg-particles {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
                overflow: hidden;
            }

            .particle {
                position: absolute;
                background: rgba(0, 212, 170, 0.1);
                border-radius: 50%;
                animation: float 6s ease-in-out infinite;
            }

            @keyframes float {
                0%, 100% { transform: translateY(0px) rotate(0deg); }
                50% { transform: translateY(-20px) rotate(180deg); }
            }

            .particle:nth-child(1) { width: 4px; height: 4px; top: 10%; left: 10%; animation-delay: 0s; }
            .particle:nth-child(2) { width: 6px; height: 6px; top: 20%; left: 80%; animation-delay: 1s; }
            .particle:nth-child(3) { width: 3px; height: 3px; top: 60%; left: 20%; animation-delay: 2s; }
            .particle:nth-child(4) { width: 5px; height: 5px; top: 80%; left: 90%; animation-delay: 3s; }
            .particle:nth-child(5) { width: 4px; height: 4px; top: 30%; left: 60%; animation-delay: 4s; }

            /* Header */
            .header {
                background: rgba(10, 10, 15, 0.95);
                backdrop-filter: blur(20px);
                border-bottom: 1px solid rgba(0, 212, 170, 0.2);
                padding: 1rem 2rem;
                position: sticky;
                top: 0;
                z-index: 100;
                transition: all 0.3s ease;
            }

            .header-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                max-width: 1400px;
                margin: 0 auto;
            }

            .logo {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .logo-icon {
                width: 40px;
                height: 40px;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                font-weight: bold;
                animation: glow 2s ease-in-out infinite alternate;
            }

            @keyframes glow {
                from { box-shadow: 0 0 10px rgba(0, 212, 170, 0.3); }
                to { box-shadow: 0 0 20px rgba(0, 212, 170, 0.6); }
            }

            .logo-text {
                font-size: 1.8rem;
                font-weight: 700;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }

            .nav-tabs {
                display: flex;
                gap: 8px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 6px;
            }

            .nav-tab {
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 500;
                border: none;
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
            }

            .nav-tab:hover {
                color: #ffffff;
                background: rgba(255, 255, 255, 0.1);
            }

            .nav-tab.active {
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                color: #ffffff;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0, 212, 170, 0.3);
            }

            .status-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.9rem;
                color: #00ff88;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                background: #00ff88;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.6; transform: scale(1.3); }
                100% { opacity: 1; transform: scale(1); }
            }

            /* Main content */
            .main-container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 2rem;
            }

            .tab-content {
                display: none;
                animation: fadeIn 0.5s ease-in-out;
            }

            .tab-content.active {
                display: block;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* Dashboard Grid */
            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 2rem;
                margin-bottom: 2rem;
            }

            .card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }

            .card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(0, 212, 170, 0.1), transparent);
                transition: left 0.5s;
            }

            .card:hover {
                transform: translateY(-8px) scale(1.02);
                border-color: rgba(0, 212, 170, 0.4);
                box-shadow: 0 20px 40px rgba(0, 212, 170, 0.1);
            }

            .card:hover::before {
                left: 100%;
            }

            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }

            .card-title {
                font-size: 1.1rem;
                font-weight: 600;
                color: #ffffff;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .card-icon {
                font-size: 1.2rem;
            }

            .card-value {
                font-size: 2rem;
                font-weight: 700;
                margin: 0.5rem 0;
            }

            .card-change {
                font-size: 0.9rem;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 4px;
            }

            .positive {
                color: #00ff88;
            }

            .negative {
                color: #ff4757;
            }

            .neutral {
                color: #ffa502;
            }

            /* Trading interface */
            .trading-interface {
                display: grid;
                grid-template-columns: 350px 1fr 300px;
                gap: 2rem;
                height: 80vh;
            }

            .trading-panel {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 16px;
                padding: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }

            .chart-container {
                height: 400px;
                margin-top: 1rem;
                position: relative;
            }

            /* Live data animations */
            .price-update {
                animation: priceFlash 0.5s ease-in-out;
            }

            @keyframes priceFlash {
                0% { background-color: rgba(0, 212, 170, 0.3); }
                100% { background-color: transparent; }
            }

            .signal-alert {
                position: fixed;
                top: 100px;
                right: 2rem;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                color: white;
                padding: 1rem 1.5rem;
                border-radius: 12px;
                box-shadow: 0 8px 25px rgba(0, 212, 170, 0.3);
                transform: translateX(400px);
                opacity: 0;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 1000;
                max-width: 300px;
            }

            .signal-alert.show {
                transform: translateX(0);
                opacity: 1;
            }

            .signal-alert .alert-title {
                font-weight: bold;
                margin-bottom: 0.5rem;
            }

            .signal-alert .alert-message {
                font-size: 0.9rem;
            }

            /* Loading states */
            .skeleton {
                background: linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);
                background-size: 200% 100%;
                animation: skeleton-loading 1.5s infinite;
                border-radius: 4px;
                height: 20px;
                margin: 8px 0;
            }

            @keyframes skeleton-loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }

            /* Buttons */
            .btn {
                padding: 12px 24px;
                border-radius: 10px;
                border: none;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                text-decoration: none;
            }

            .btn-primary {
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                color: white;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0, 212, 170, 0.4);
            }

            .btn-danger {
                background: linear-gradient(45deg, #ff4757, #ff6b7d);
                color: white;
            }

            .btn-danger:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(255, 71, 87, 0.4);
            }

            /* Responsive */
            @media (max-width: 1200px) {
                .trading-interface {
                    grid-template-columns: 1fr;
                    height: auto;
                }
            }

            @media (max-width: 768px) {
                .header-content {
                    flex-direction: column;
                    gap: 1rem;
                }

                .nav-tabs {
                    order: -1;
                }

                .main-container {
                    padding: 1rem;
                }

                .dashboard-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <!-- Animated background -->
        <div class="bg-particles">
            <div class="particle"></div>
            <div class="particle"></div>
            <div class="particle"></div>
            <div class="particle"></div>
            <div class="particle"></div>
        </div>

        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <div class="logo">
                    <div class="logo-icon">S</div>
                    <div class="logo-text">Sofia V2</div>
                </div>

                <nav class="nav-tabs">
                    <button class="nav-tab active" onclick="switchTab('dashboard')">Dashboard</button>
                    <button class="nav-tab" onclick="switchTab('trading')">Trading</button>
                    <button class="nav-tab" onclick="switchTab('portfolio')">Portfolio</button>
                    <button class="nav-tab" onclick="switchTab('scanner')">Scanner</button>
                    <button class="nav-tab" onclick="switchTab('ai')">AI Predictions</button>
                </nav>

                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span id="connection-status">Connected</span>
                </div>
            </div>
        </header>

        <!-- Main content -->
        <main class="main-container">

            <!-- Dashboard Tab -->
            <div id="dashboard" class="tab-content active">
                <div class="dashboard-grid">
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="card-icon">💰</span>
                                Portfolio Value
                            </div>
                        </div>
                        <div class="card-value positive" id="portfolio-value">$10,000.00</div>
                        <div class="card-change" id="portfolio-change">
                            <span>↗️ +0.00%</span>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="card-icon">📈</span>
                                P&L Today
                            </div>
                        </div>
                        <div class="card-value neutral" id="pnl-today">$0.00</div>
                        <div class="card-change" id="pnl-change">
                            <span>0.00%</span>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="card-icon">🎯</span>
                                Win Rate
                            </div>
                        </div>
                        <div class="card-value neutral" id="win-rate">0%</div>
                        <div class="card-change">
                            <span id="total-trades">0 trades</span>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="card-icon">🔥</span>
                                Active Signals
                            </div>
                        </div>
                        <div class="card-value positive" id="active-signals">0</div>
                        <div class="card-change">
                            <span>Scanner active</span>
                        </div>
                    </div>
                </div>

                <!-- Market overview -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <span class="card-icon">📊</span>
                            Market Overview
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="market-chart"></canvas>
                    </div>
                </div>

                <!-- Recent signals -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">
                            <span class="card-icon">🚨</span>
                            Recent Trading Signals
                        </div>
                    </div>
                    <div id="recent-signals">
                        <div class="skeleton"></div>
                        <div class="skeleton"></div>
                        <div class="skeleton"></div>
                    </div>
                </div>
            </div>

            <!-- Trading Tab -->
            <div id="trading" class="tab-content">
                <div class="trading-interface">
                    <div class="trading-panel">
                        <h3>Quick Trade</h3>
                        <p>Trading interface will be loaded here...</p>
                    </div>

                    <div class="trading-panel">
                        <div class="card-title">Live Price Chart</div>
                        <div class="chart-container">
                            <canvas id="trading-chart"></canvas>
                        </div>
                    </div>

                    <div class="trading-panel">
                        <h3>Order Book</h3>
                        <p>Order book will be loaded here...</p>
                    </div>
                </div>
            </div>

            <!-- Portfolio Tab -->
            <div id="portfolio" class="tab-content">
                <div class="card">
                    <div class="card-title">Portfolio Analysis</div>
                    <p>Detailed portfolio analytics will be loaded here...</p>
                </div>
            </div>

            <!-- Scanner Tab -->
            <div id="scanner" class="tab-content">
                <div class="card">
                    <div class="card-title">Market Scanner</div>
                    <p>Market scanning results will be loaded here...</p>
                </div>
            </div>

            <!-- AI Predictions Tab -->
            <div id="ai" class="tab-content">
                <div class="card">
                    <div class="card-title">AI Predictions</div>
                    <div id="ai-predictions">
                        <div class="skeleton"></div>
                        <div class="skeleton"></div>
                        <div class="skeleton"></div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Signal alert template -->
        <div id="signal-alert" class="signal-alert">
            <div class="alert-title"></div>
            <div class="alert-message"></div>
        </div>

        <script>
            // Global state
            let ws;
            let marketChart;
            let tradingChart;
            let currentTab = 'dashboard';
            let portfolioData = null;

            // Initialize application
            document.addEventListener('DOMContentLoaded', function() {
                initializeCharts();
                connectWebSocket();
                loadInitialData();
            });

            // Tab switching
            function switchTab(tabName) {
                // Update nav tabs
                document.querySelectorAll('.nav-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                event.target.classList.add('active');

                // Update content
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                document.getElementById(tabName).classList.add('active');

                currentTab = tabName;

                // Load tab-specific data
                loadTabData(tabName);
            }

            // WebSocket connection
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws/main`;

                ws = new WebSocket(wsUrl);

                ws.onopen = function() {
                    console.log('Connected to Sofia V2');
                    document.getElementById('connection-status').textContent = 'Connected';
                };

                ws.onmessage = function(event) {
                    const message = JSON.parse(event.data);
                    handleWebSocketMessage(message);
                };

                ws.onclose = function() {
                    console.log('Connection lost, reconnecting...');
                    document.getElementById('connection-status').textContent = 'Reconnecting...';
                    setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    document.getElementById('connection-status').textContent = 'Connection Error';
                };
            }

            // Handle WebSocket messages
            function handleWebSocketMessage(message) {
                switch(message.type) {
                    case 'market_data':
                        updateMarketData(message.data);
                        break;
                    case 'portfolio_update':
                        updatePortfolioData(message.data);
                        break;
                    case 'trading_signal':
                        showTradingSignal(message.data);
                        break;
                    case 'ai_prediction':
                        updateAIPredictions(message.data);
                        break;
                    case 'scanner_results':
                        updateScannerResults(message.data);
                        break;
                }
            }

            // Initialize charts
            function initializeCharts() {
                // Market overview chart
                const marketCtx = document.getElementById('market-chart').getContext('2d');
                marketChart = new Chart(marketCtx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'BTC',
                            data: [],
                            borderColor: '#00d4aa',
                            backgroundColor: 'rgba(0, 212, 170, 0.1)',
                            tension: 0.4,
                            fill: true
                        }, {
                            label: 'ETH',
                            data: [],
                            borderColor: '#00b4d8',
                            backgroundColor: 'rgba(0, 180, 216, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: { color: '#ffffff' }
                            }
                        },
                        scales: {
                            x: {
                                ticks: { color: '#888888' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            },
                            y: {
                                ticks: { color: '#888888' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            }
                        }
                    }
                });

                // Trading chart
                const tradingCtx = document.getElementById('trading-chart')?.getContext('2d');
                if (tradingCtx) {
                    tradingChart = new Chart(tradingCtx, {
                        type: 'candlestick',
                        data: { datasets: [] },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { labels: { color: '#ffffff' } }
                            }
                        }
                    });
                }
            }

            // Update market data
            function updateMarketData(data) {
                // Update dashboard cards with animation
                Object.keys(data).forEach(symbol => {
                    const symbolData = data[symbol];
                    const element = document.getElementById(`${symbol.toLowerCase()}-price`);
                    if (element) {
                        element.classList.add('price-update');
                        element.textContent = `$${symbolData.price.toLocaleString()}`;
                        setTimeout(() => element.classList.remove('price-update'), 500);
                    }
                });

                // Update chart
                if (marketChart && data.BTC && data.ETH) {
                    const now = new Date().toLocaleTimeString();
                    marketChart.data.labels.push(now);
                    marketChart.data.datasets[0].data.push(data.BTC.price);
                    marketChart.data.datasets[1].data.push(data.ETH.price);

                    // Keep only last 20 data points
                    if (marketChart.data.labels.length > 20) {
                        marketChart.data.labels.shift();
                        marketChart.data.datasets[0].data.shift();
                        marketChart.data.datasets[1].data.shift();
                    }

                    marketChart.update('none');
                }
            }

            // Update portfolio data
            function updatePortfolioData(data) {
                portfolioData = data;

                // Update dashboard cards
                document.getElementById('portfolio-value').textContent = `$${data.total_value.toLocaleString()}`;
                document.getElementById('pnl-today').textContent = `$${data.total_pnl.toFixed(2)}`;
                document.getElementById('win-rate').textContent = `${(data.win_rate * 100).toFixed(1)}%`;
                document.getElementById('total-trades').textContent = `${data.total_trades} trades`;

                // Update change indicators
                const pnlPercent = data.total_pnl_percent;
                const changeEl = document.getElementById('portfolio-change');
                const pnlEl = document.getElementById('pnl-today');

                if (pnlPercent > 0) {
                    changeEl.innerHTML = `<span>↗️ +${pnlPercent.toFixed(2)}%</span>`;
                    changeEl.className = 'card-change positive';
                    pnlEl.className = 'card-value positive';
                } else if (pnlPercent < 0) {
                    changeEl.innerHTML = `<span>↘️ ${pnlPercent.toFixed(2)}%</span>`;
                    changeEl.className = 'card-change negative';
                    pnlEl.className = 'card-value negative';
                } else {
                    changeEl.innerHTML = `<span>→ 0.00%</span>`;
                    changeEl.className = 'card-change neutral';
                    pnlEl.className = 'card-value neutral';
                }
            }

            // Show trading signal alert
            function showTradingSignal(signal) {
                const alertEl = document.getElementById('signal-alert');
                const titleEl = alertEl.querySelector('.alert-title');
                const messageEl = alertEl.querySelector('.alert-message');

                titleEl.textContent = `${signal.symbol} ${signal.signal_type.toUpperCase()}`;
                messageEl.textContent = signal.message;

                alertEl.classList.add('show');

                // Update active signals count
                const currentCount = parseInt(document.getElementById('active-signals').textContent);
                document.getElementById('active-signals').textContent = currentCount + 1;

                // Auto hide after 5 seconds
                setTimeout(() => {
                    alertEl.classList.remove('show');
                }, 5000);
            }

            // Update AI predictions
            function updateAIPredictions(predictions) {
                const container = document.getElementById('ai-predictions');
                container.innerHTML = '';

                Object.keys(predictions).forEach(symbol => {
                    const pred = predictions[symbol];
                    const predEl = document.createElement('div');
                    predEl.className = 'prediction-item';
                    predEl.innerHTML = `
                        <div class="prediction-header">
                            <strong>${symbol}</strong>
                            <span class="confidence">Confidence: ${pred.predictions['24h'].confidence.toFixed(1)}%</span>
                        </div>
                        <div class="prediction-details">
                            24h: $${pred.predictions['24h'].price.toFixed(2)}
                            (${pred.trend_direction})
                        </div>
                    `;
                    container.appendChild(predEl);
                });
            }

            // Load initial data
            function loadInitialData() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'get_dashboard_data'}));
                }
            }

            // Load tab-specific data
            function loadTabData(tabName) {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'load_tab', tab: tabName}));
                }
            }
        </script>
    </body>
    </html>
    """


@app.websocket("/ws/main")
async def main_websocket(websocket: WebSocket):
    """Main WebSocket endpoint for the Sofia V2 app"""
    client_id = str(uuid.uuid4())
    user_id = "demo"  # In real app, get from auth

    await sofia_manager.connect(websocket, client_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle client requests
            if message.get("type") == "get_dashboard_data":
                await send_dashboard_data(user_id)
            elif message.get("type") == "load_tab":
                await send_tab_data(user_id, message.get("tab"))

    except WebSocketDisconnect:
        sofia_manager.disconnect(client_id, user_id)


async def send_dashboard_data(user_id: str):
    """Send initial dashboard data"""
    try:
        # Get portfolio data
        portfolio = paper_engine.get_portfolio_summary(user_id)
        if portfolio:
            await sofia_manager.send_to_user(
                {"type": "portfolio_update", "data": portfolio}, user_id
            )

        # Get AI predictions
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

            await asyncio.sleep(5)  # Update every 5 seconds

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

            await asyncio.sleep(300)  # Update every 5 minutes

        except Exception as e:
            logger.error(f"Error broadcasting predictions: {e}")
            await asyncio.sleep(60)


async def broadcast_scanner_signals():
    """Broadcast scanner signals to all clients"""
    while True:
        try:
            # Get recent signals
            signals = []
            for symbol in ["BTC", "ETH", "SOL", "BNB", "ADA"]:
                symbol_signals = market_scanner.get_symbol_signals(symbol, 1)
                if symbol_signals:
                    signals.extend(symbol_signals)

            # Send new signals
            for signal in signals:
                await sofia_manager.broadcast_to_all({"type": "trading_signal", "data": signal})

            await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            logger.error(f"Error broadcasting signals: {e}")
            await asyncio.sleep(30)


# API endpoints
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
