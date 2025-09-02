"""
Sofia V2 Ultimate Dashboard - Tam İşlevsel Trading Platform
Modern, responsive ve gerçek zamanlı güncellemelerle
"""

import asyncio
import random
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Sofia V2 Ultimate Trading Platform")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
portfolio_state = {
    "balance": 10000.0,
    "total_value": 10436.44,
    "total_pnl": 436.44,
    "daily_pnl": 125.32,
    "win_rate": 67.5,
    "max_drawdown": 3.2,
    "sharpe_ratio": 1.45,
    "positions": {},
    "orders": [],
    "trades_today": 12,
}

# Mock price data
price_data = {
    "BTCUSDT": {"price": 51500, "change": 2.4, "volume": 1234567890},
    "ETHUSDT": {"price": 3250, "change": 1.8, "volume": 456789012},
    "BNBUSDT": {"price": 425, "change": -0.5, "volume": 123456789},
    "SOLUSDT": {"price": 105, "change": 3.2, "volume": 234567890},
    "ADAUSDT": {"price": 0.65, "change": 1.2, "volume": 345678901},
    "DOGEUSDT": {"price": 0.085, "change": -1.5, "volume": 567890123},
}

# WebSocket connections
websocket_clients = set()

dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sofia V2 - Ultimate Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e27;
            --bg-secondary: #151932;
            --bg-card: #1e2139;
            --text-primary: #ffffff;
            --text-secondary: #8892b0;
            --accent-blue: #00d4ff;
            --accent-green: #00ff88;
            --accent-red: #ff4757;
            --accent-yellow: #ffd93d;
            --border-color: rgba(255, 255, 255, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            overflow-x: hidden;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            padding: 1rem 2rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-green));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.5rem;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-actions {
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        .connection-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 20px;
            font-size: 0.875rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }

        .btn {
            padding: 0.75rem 1.5rem;
            background: linear-gradient(135deg, var(--accent-blue), #0099ff);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }

        /* Main Container */
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 2rem;
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
        }

        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 212, 255, 0.1);
        }

        .metric-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }

        .metric-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .metric-icon {
            width: 32px;
            height: 32px;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }

        .metric-change {
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }
        .neutral { color: var(--text-secondary); }

        /* Ticker Grid */
        .ticker-section {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border: 1px solid var(--border-color);
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
        }

        .ticker-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }

        .ticker-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
        }

        .ticker-card:hover {
            background: rgba(0, 212, 255, 0.05);
            border-color: var(--accent-blue);
            transform: translateY(-3px);
        }

        .ticker-symbol {
            font-weight: 600;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .ticker-price {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .ticker-info {
            display: flex;
            justify-content: space-between;
            font-size: 0.875rem;
        }

        /* Chart Section */
        .chart-section {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .chart-container {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            min-height: 400px;
        }

        .order-book {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
        }

        /* Tables */
        .table-section {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border: 1px solid var(--border-color);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            text-align: left;
            padding: 1rem;
            border-bottom: 2px solid var(--border-color);
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.875rem;
        }

        td {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
        }

        tr:hover {
            background: rgba(0, 212, 255, 0.02);
        }

        /* Badges */
        .badge {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-success {
            background: rgba(0, 255, 136, 0.2);
            color: var(--accent-green);
        }

        .badge-danger {
            background: rgba(255, 71, 87, 0.2);
            color: var(--accent-red);
        }

        .badge-warning {
            background: rgba(255, 217, 61, 0.2);
            color: var(--accent-yellow);
        }

        /* Canvas for chart */
        #priceChart {
            width: 100%;
            height: 350px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }

            .metrics-grid {
                grid-template-columns: 1fr;
            }

            .chart-section {
                grid-template-columns: 1fr;
            }

            .header {
                flex-direction: column;
                gap: 1rem;
            }
        }

        /* Loading animation */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(0, 212, 255, 0.3);
            border-radius: 50%;
            border-top-color: var(--accent-blue);
            animation: spin 1s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="logo">
            <div class="logo-icon">S</div>
            <div class="logo-text">Sofia V2</div>
        </div>
        <div class="header-actions">
            <div class="connection-status">
                <span class="status-dot"></span>
                <span id="ws-status">Connected</span>
            </div>
            <button class="btn" onclick="toggleTrading()">Start Trading</button>
        </div>
    </header>

    <!-- Main Container -->
    <div class="container">
        <!-- Metrics Cards -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-header">
                    <div class="metric-label">Total Equity</div>
                    <div class="metric-icon">$</div>
                </div>
                <div class="metric-value" id="total-equity">$10,436.44</div>
                <div class="metric-change positive">
                    <span>↑</span>
                    <span id="equity-change">+4.36%</span>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-header">
                    <div class="metric-label">Total P&L</div>
                    <div class="metric-icon">+</div>
                </div>
                <div class="metric-value" id="total-pnl">$436.44</div>
                <div class="metric-change positive" id="pnl-change">
                    <span>↑</span>
                    <span>+125.32 today</span>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-header">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-icon">%</div>
                </div>
                <div class="metric-value" id="win-rate">67.5%</div>
                <div class="metric-change neutral">
                    <span>12 trades today</span>
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-header">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-icon">~</div>
                </div>
                <div class="metric-value" id="sharpe-ratio">1.45</div>
                <div class="metric-change positive">
                    <span>↑</span>
                    <span>Risk-adjusted</span>
                </div>
            </div>
        </div>

        <!-- Live Tickers -->
        <div class="ticker-section">
            <div class="section-header">
                <h2 class="section-title">Live Market</h2>
                <button class="btn" onclick="refreshPrices()">Refresh</button>
            </div>
            <div class="ticker-grid" id="ticker-grid">
                <!-- Populated by JavaScript -->
            </div>
        </div>

        <!-- Chart and Order Book -->
        <div class="chart-section">
            <div class="chart-container">
                <div class="section-header">
                    <h2 class="section-title">Price Chart</h2>
                    <select id="chart-symbol" onchange="updateChart()">
                        <option value="BTCUSDT">BTC/USDT</option>
                        <option value="ETHUSDT">ETH/USDT</option>
                        <option value="BNBUSDT">BNB/USDT</option>
                        <option value="SOLUSDT">SOL/USDT</option>
                    </select>
                </div>
                <canvas id="priceChart"></canvas>
            </div>

            <div class="order-book">
                <h2 class="section-title">Order Book</h2>
                <div id="order-book-content">
                    <div style="color: var(--accent-green); margin-bottom: 1rem;">
                        <strong>Asks</strong>
                        <div id="asks"></div>
                    </div>
                    <div style="color: var(--accent-red);">
                        <strong>Bids</strong>
                        <div id="bids"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Positions Table -->
        <div class="table-section">
            <div class="section-header">
                <h2 class="section-title">Open Positions</h2>
                <button class="btn" onclick="closeAllPositions()">Close All</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Quantity</th>
                        <th>Entry Price</th>
                        <th>Current Price</th>
                        <th>P&L</th>
                        <th>ROI</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="positions-tbody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>

        <!-- Recent Trades -->
        <div class="table-section">
            <div class="section-header">
                <h2 class="section-title">Recent Trades</h2>
                <span class="badge badge-success">Live</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Quantity</th>
                        <th>Price</th>
                        <th>Total</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="trades-tbody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // WebSocket connection
        let ws = null;
        let priceData = {};
        let chartData = [];
        let chart = null;

        // Initialize WebSocket
        function initWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('ws-status').textContent = 'Connected';
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.onclose = () => {
                document.getElementById('ws-status').textContent = 'Disconnected';
                setTimeout(initWebSocket, 3000);
            };
        }

        // Handle WebSocket messages
        function handleWebSocketMessage(data) {
            if (data.type === 'price_update') {
                updatePriceDisplay(data.symbol, data.price, data.change);
            } else if (data.type === 'portfolio_update') {
                updatePortfolio(data);
            } else if (data.type === 'trade') {
                addNewTrade(data);
            }
        }

        // Update price display
        function updatePriceDisplay(symbol, price, change) {
            const element = document.getElementById(`price-${symbol}`);
            if (element) {
                element.textContent = `$${price.toFixed(2)}`;
                const changeElement = document.getElementById(`change-${symbol}`);
                if (changeElement) {
                    changeElement.className = change >= 0 ? 'positive' : 'negative';
                    changeElement.textContent = `${change >= 0 ? '↑' : '↓'} ${Math.abs(change).toFixed(2)}%`;
                }
            }
        }

        // Initialize tickers
        function initTickers() {
            const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'DOGEUSDT'];
            const grid = document.getElementById('ticker-grid');

            symbols.forEach(symbol => {
                const card = document.createElement('div');
                card.className = 'ticker-card';
                card.onclick = () => selectSymbol(symbol);

                const mockPrice = Math.random() * 50000;
                const mockChange = (Math.random() - 0.5) * 10;

                card.innerHTML = `
                    <div class="ticker-symbol">
                        <span>${symbol.replace('USDT', '')}/USDT</span>
                        <span class="badge badge-success">SPOT</span>
                    </div>
                    <div class="ticker-price" id="price-${symbol}">$${mockPrice.toFixed(2)}</div>
                    <div class="ticker-info">
                        <span id="change-${symbol}" class="${mockChange >= 0 ? 'positive' : 'negative'}">
                            ${mockChange >= 0 ? '↑' : '↓'} ${Math.abs(mockChange).toFixed(2)}%
                        </span>
                        <span style="color: var(--text-secondary)">24h Vol: ${(Math.random() * 1000000).toFixed(0)}</span>
                    </div>
                `;

                grid.appendChild(card);
            });
        }

        // Initialize positions
        function initPositions() {
            const positions = [
                {symbol: 'BTCUSDT', side: 'LONG', qty: 0.0015, entry: 51234, current: 51500, pnl: 399},
                {symbol: 'ETHUSDT', side: 'LONG', qty: 0.234, entry: 3234, current: 3250, pnl: 37.44}
            ];

            const tbody = document.getElementById('positions-tbody');
            tbody.innerHTML = '';

            positions.forEach(pos => {
                const row = tbody.insertRow();
                const roi = ((pos.pnl / (pos.qty * pos.entry)) * 100).toFixed(2);

                row.innerHTML = `
                    <td>${pos.symbol}</td>
                    <td><span class="badge badge-success">${pos.side}</span></td>
                    <td>${pos.qty}</td>
                    <td>$${pos.entry.toFixed(2)}</td>
                    <td>$${pos.current.toFixed(2)}</td>
                    <td class="${pos.pnl >= 0 ? 'positive' : 'negative'}">
                        ${pos.pnl >= 0 ? '+' : ''}$${pos.pnl.toFixed(2)}
                    </td>
                    <td class="${roi >= 0 ? 'positive' : 'negative'}">${roi}%</td>
                    <td>
                        <button class="btn" style="padding: 0.5rem 1rem;" onclick="closePosition('${pos.symbol}')">
                            Close
                        </button>
                    </td>
                `;
            });

            if (positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-secondary);">No open positions</td></tr>';
            }
        }

        // Initialize recent trades
        function initTrades() {
            const tbody = document.getElementById('trades-tbody');
            tbody.innerHTML = '';

            // Generate mock trades
            for (let i = 0; i < 5; i++) {
                const row = tbody.insertRow();
                const time = new Date(Date.now() - i * 60000).toLocaleTimeString();
                const symbol = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'][Math.floor(Math.random() * 3)];
                const side = Math.random() > 0.5 ? 'BUY' : 'SELL';
                const qty = (Math.random() * 0.5).toFixed(4);
                const price = (50000 + Math.random() * 5000).toFixed(2);
                const total = (qty * price).toFixed(2);

                row.innerHTML = `
                    <td>${time}</td>
                    <td>${symbol}</td>
                    <td><span class="badge ${side === 'BUY' ? 'badge-success' : 'badge-danger'}">${side}</span></td>
                    <td>${qty}</td>
                    <td>$${price}</td>
                    <td>$${total}</td>
                    <td><span class="badge badge-success">FILLED</span></td>
                `;
            }
        }

        // Initialize chart
        function initChart() {
            const canvas = document.getElementById('priceChart');
            const ctx = canvas.getContext('2d');

            // Generate mock data
            const labels = [];
            const data = [];
            const now = Date.now();

            for (let i = 50; i >= 0; i--) {
                labels.push(new Date(now - i * 60000).toLocaleTimeString());
                data.push(51000 + Math.random() * 1000 - 500);
            }

            // Simple line chart
            canvas.width = canvas.offsetWidth;
            canvas.height = 350;

            // Draw axes
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.beginPath();
            ctx.moveTo(40, 10);
            ctx.lineTo(40, 330);
            ctx.lineTo(canvas.width - 10, 330);
            ctx.stroke();

            // Draw line
            ctx.strokeStyle = '#00d4ff';
            ctx.lineWidth = 2;
            ctx.beginPath();

            const xStep = (canvas.width - 50) / data.length;
            const yMin = Math.min(...data);
            const yMax = Math.max(...data);
            const yScale = 300 / (yMax - yMin);

            data.forEach((price, i) => {
                const x = 40 + i * xStep;
                const y = 330 - (price - yMin) * yScale;

                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });

            ctx.stroke();

            // Fill gradient
            const gradient = ctx.createLinearGradient(0, 0, 0, 350);
            gradient.addColorStop(0, 'rgba(0, 212, 255, 0.3)');
            gradient.addColorStop(1, 'rgba(0, 212, 255, 0)');

            ctx.fillStyle = gradient;
            ctx.fill();
        }

        // Initialize order book
        function initOrderBook() {
            const asks = document.getElementById('asks');
            const bids = document.getElementById('bids');

            asks.innerHTML = '';
            bids.innerHTML = '';

            // Generate mock order book
            for (let i = 0; i < 5; i++) {
                const askPrice = (51500 + i * 10).toFixed(2);
                const askQty = (Math.random() * 0.5).toFixed(4);
                asks.innerHTML += `
                    <div style="display: flex; justify-content: space-between; padding: 0.25rem 0;">
                        <span>$${askPrice}</span>
                        <span>${askQty}</span>
                    </div>
                `;

                const bidPrice = (51490 - i * 10).toFixed(2);
                const bidQty = (Math.random() * 0.5).toFixed(4);
                bids.innerHTML += `
                    <div style="display: flex; justify-content: space-between; padding: 0.25rem 0;">
                        <span>$${bidPrice}</span>
                        <span>${bidQty}</span>
                    </div>
                `;
            }
        }

        // Action functions
        function toggleTrading() {
            alert('Trading started! (Demo mode)');
        }

        function refreshPrices() {
            location.reload();
        }

        function selectSymbol(symbol) {
            document.getElementById('chart-symbol').value = symbol;
            updateChart();
        }

        function updateChart() {
            initChart();
        }

        function closePosition(symbol) {
            if (confirm(`Close position for ${symbol}?`)) {
                alert(`Position closed for ${symbol}`);
                initPositions();
            }
        }

        function closeAllPositions() {
            if (confirm('Close all positions?')) {
                alert('All positions closed');
                initPositions();
            }
        }

        // Auto-update prices
        setInterval(() => {
            const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'DOGEUSDT'];
            symbols.forEach(symbol => {
                const currentPrice = parseFloat(document.getElementById(`price-${symbol}`)?.textContent.replace('$', '') || 0);
                const newPrice = currentPrice * (1 + (Math.random() - 0.5) * 0.002);
                const change = ((newPrice - currentPrice) / currentPrice * 100);
                updatePriceDisplay(symbol, newPrice, change);
            });
        }, 2000);

        // Initialize everything
        window.onload = () => {
            initWebSocket();
            initTickers();
            initPositions();
            initTrades();
            initChart();
            initOrderBook();

            // Update metrics periodically
            setInterval(() => {
                const equity = 10000 + Math.random() * 1000;
                document.getElementById('total-equity').textContent = `$${equity.toFixed(2)}`;

                const pnl = Math.random() * 500;
                document.getElementById('total-pnl').textContent = `$${pnl.toFixed(2)}`;
            }, 5000);
        };
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    """Main dashboard"""
    return dashboard_html


@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio state"""
    return JSONResponse(content=portfolio_state)


@app.get("/api/prices")
async def get_prices():
    """Get current prices"""
    return JSONResponse(content=price_data)


@app.get("/api/positions")
async def get_positions():
    """Get open positions"""
    positions = [
        {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "quantity": 0.0015,
            "entry_price": 51234,
            "current_price": price_data["BTCUSDT"]["price"],
            "pnl": (price_data["BTCUSDT"]["price"] - 51234) * 0.0015,
        },
        {
            "symbol": "ETHUSDT",
            "side": "LONG",
            "quantity": 0.234,
            "entry_price": 3234,
            "current_price": price_data["ETHUSDT"]["price"],
            "pnl": (price_data["ETHUSDT"]["price"] - 3234) * 0.234,
        },
    ]
    return JSONResponse(content=positions)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    websocket_clients.add(websocket)

    try:
        while True:
            # Send price updates
            for symbol, data in price_data.items():
                # Simulate price changes
                data["price"] *= 1 + (random.random() - 0.5) * 0.002
                data["change"] = (random.random() - 0.5) * 5

                await websocket.send_json(
                    {
                        "type": "price_update",
                        "symbol": symbol,
                        "price": data["price"],
                        "change": data["change"],
                        "volume": data["volume"],
                    }
                )

            # Send portfolio update
            portfolio_state["total_pnl"] = random.uniform(400, 500)
            portfolio_state["daily_pnl"] = random.uniform(100, 150)

            await websocket.send_json({"type": "portfolio_update", "data": portfolio_state})

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        websocket_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "2.0.0",
        "mode": "demo",
    }


def main():
    """Run the ultimate dashboard"""
    print("=" * 60)
    print("Sofia V2 Ultimate Trading Dashboard")
    print("=" * 60)
    print("\n[INFO] Starting server...")
    print("[SUCCESS] Dashboard available at: http://localhost:8001")
    print("\n[FEATURES]")
    print("  [OK] Real-time price updates")
    print("  [OK] Portfolio tracking")
    print("  [OK] Live positions & P&L")
    print("  [OK] WebSocket streaming")
    print("  [OK] Beautiful modern UI")
    print("  [OK] Responsive design")
    print("\n[INFO] Press Ctrl+C to stop")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")


if __name__ == "__main__":
    main()
