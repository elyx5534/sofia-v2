"""
Advanced Trading Interface with Real-Time Paper Trading
Beautiful UI for executing trades with real crypto prices
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.adapters.web.fastapi_adapter import (
    FastAPI,
    Form,
    HTMLResponse,
    JSONResponse,
    WebSocket,
    WebSocketDisconnect,
)

from ..data.real_time_fetcher import fetcher
from ..trading.paper_trading_engine import OrderSide, OrderType, paper_engine

logger = logging.getLogger(__name__)
app = FastAPI(title="Sofia V2 Trading Interface")
templates = Jinja2Templates(directory="src/web_ui/templates")
app.mount("/static", StaticFiles(directory="src/web_ui/static"), name="static")


class TradingConnectionManager:
    """Manages WebSocket connections for trading interface"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(client_id)
        logger.info(f"Trading client {client_id} connected for user {user_id}")

    def disconnect(self, client_id: str, user_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if user_id in self.user_connections:
            if client_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(client_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        logger.info(f"Trading client {client_id} disconnected")

    async def send_to_user(self, message: dict, user_id: str):
        """Send message to all connections of a specific user"""
        if user_id in self.user_connections:
            disconnected = []
            for client_id in self.user_connections[user_id]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error sending message to {client_id}: {e}")
                        disconnected.append(client_id)
            for client_id in disconnected:
                self.disconnect(client_id, user_id)


trading_manager = TradingConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Start paper trading engine on startup"""
    await paper_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await paper_engine.stop()


@app.get("/trading", response_class=HTMLResponse)
async def trading_interface():
    """Advanced trading interface page"""
    return "\n    <!DOCTYPE html>\n    <html lang=\"en\">\n    <head>\n        <meta charset=\"UTF-8\">\n        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n        <title>Sofia V2 - Paper Trading Interface</title>\n        <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>\n        <script src=\"https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js\"></script>\n        <style>\n            * {\n                margin: 0;\n                padding: 0;\n                box-sizing: border-box;\n            }\n\n            body {\n                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;\n                background: linear-gradient(135deg, #0f0f23, #1a1a3a);\n                color: #ffffff;\n                min-height: 100vh;\n                overflow-x: hidden;\n            }\n\n            .header {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                padding: 1rem 2rem;\n                border-bottom: 1px solid rgba(255, 255, 255, 0.1);\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n            }\n\n            .logo {\n                font-size: 1.5rem;\n                font-weight: bold;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                -webkit-background-clip: text;\n                -webkit-text-fill-color: transparent;\n            }\n\n            .portfolio-summary {\n                display: flex;\n                gap: 20px;\n                align-items: center;\n            }\n\n            .balance {\n                font-size: 1.2rem;\n                font-weight: bold;\n            }\n\n            .pnl {\n                font-weight: bold;\n            }\n\n            .pnl.positive {\n                color: #00ff88;\n            }\n\n            .pnl.negative {\n                color: #ff4757;\n            }\n\n            .trading-grid {\n                display: grid;\n                grid-template-columns: 300px 1fr 350px;\n                gap: 20px;\n                padding: 20px;\n                height: calc(100vh - 80px);\n            }\n\n            .left-panel, .right-panel {\n                display: flex;\n                flex-direction: column;\n                gap: 15px;\n            }\n\n            .main-chart {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                border-radius: 15px;\n                padding: 20px;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n            }\n\n            .card {\n                background: rgba(255, 255, 255, 0.05);\n                backdrop-filter: blur(10px);\n                border-radius: 15px;\n                padding: 15px;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                transition: all 0.3s ease;\n            }\n\n            .card:hover {\n                border-color: rgba(0, 212, 170, 0.3);\n                box-shadow: 0 5px 15px rgba(0, 212, 170, 0.1);\n            }\n\n            .card-title {\n                font-size: 1rem;\n                font-weight: bold;\n                margin-bottom: 10px;\n                color: #00d4aa;\n                text-align: center;\n            }\n\n            .symbol-selector {\n                display: flex;\n                flex-wrap: wrap;\n                gap: 8px;\n                margin-bottom: 15px;\n            }\n\n            .symbol-btn {\n                padding: 8px 12px;\n                background: rgba(255, 255, 255, 0.1);\n                border: 1px solid rgba(255, 255, 255, 0.2);\n                color: white;\n                border-radius: 8px;\n                cursor: pointer;\n                transition: all 0.2s ease;\n                font-size: 0.85rem;\n                font-weight: bold;\n            }\n\n            .symbol-btn:hover {\n                background: rgba(0, 212, 170, 0.2);\n                border-color: #00d4aa;\n            }\n\n            .symbol-btn.active {\n                background: #00d4aa;\n                color: #000;\n            }\n\n            .current-price {\n                text-align: center;\n                margin-bottom: 15px;\n            }\n\n            .price-display {\n                font-size: 1.8rem;\n                font-weight: bold;\n                margin-bottom: 5px;\n            }\n\n            .price-change {\n                font-size: 0.9rem;\n                font-weight: bold;\n            }\n\n            .trade-form {\n                display: flex;\n                flex-direction: column;\n                gap: 10px;\n            }\n\n            .trade-tabs {\n                display: flex;\n                margin-bottom: 10px;\n            }\n\n            .tab-btn {\n                flex: 1;\n                padding: 10px;\n                background: rgba(255, 255, 255, 0.1);\n                border: none;\n                color: white;\n                cursor: pointer;\n                transition: all 0.2s ease;\n                font-weight: bold;\n            }\n\n            .tab-btn:first-child {\n                border-radius: 8px 0 0 8px;\n            }\n\n            .tab-btn:last-child {\n                border-radius: 0 8px 8px 0;\n            }\n\n            .tab-btn.active {\n                background: #00d4aa;\n                color: #000;\n            }\n\n            .tab-btn.sell.active {\n                background: #ff4757;\n                color: white;\n            }\n\n            .form-group {\n                display: flex;\n                flex-direction: column;\n                gap: 5px;\n            }\n\n            .form-label {\n                font-size: 0.85rem;\n                color: #ccc;\n                font-weight: bold;\n            }\n\n            .form-input {\n                padding: 12px;\n                background: rgba(255, 255, 255, 0.1);\n                border: 1px solid rgba(255, 255, 255, 0.2);\n                border-radius: 8px;\n                color: white;\n                font-size: 0.95rem;\n            }\n\n            .form-input:focus {\n                outline: none;\n                border-color: #00d4aa;\n                box-shadow: 0 0 0 2px rgba(0, 212, 170, 0.2);\n            }\n\n            .order-type-select {\n                display: flex;\n                gap: 5px;\n                margin-bottom: 10px;\n            }\n\n            .order-type-btn {\n                flex: 1;\n                padding: 8px;\n                background: rgba(255, 255, 255, 0.1);\n                border: 1px solid rgba(255, 255, 255, 0.2);\n                color: white;\n                border-radius: 6px;\n                cursor: pointer;\n                font-size: 0.8rem;\n                text-align: center;\n                transition: all 0.2s ease;\n            }\n\n            .order-type-btn.active {\n                background: #00d4aa;\n                color: #000;\n            }\n\n            .submit-btn {\n                padding: 15px;\n                background: linear-gradient(45deg, #00d4aa, #00b4d8);\n                border: none;\n                border-radius: 10px;\n                color: white;\n                font-size: 1rem;\n                font-weight: bold;\n                cursor: pointer;\n                transition: all 0.3s ease;\n                margin-top: 10px;\n            }\n\n            .submit-btn:hover {\n                transform: translateY(-2px);\n                box-shadow: 0 5px 15px rgba(0, 212, 170, 0.4);\n            }\n\n            .submit-btn.sell {\n                background: linear-gradient(45deg, #ff4757, #ff6b7d);\n            }\n\n            .submit-btn:disabled {\n                opacity: 0.5;\n                cursor: not-allowed;\n                transform: none;\n                box-shadow: none;\n            }\n\n            .positions-list, .orders-list {\n                max-height: 300px;\n                overflow-y: auto;\n            }\n\n            .position-item, .order-item {\n                background: rgba(255, 255, 255, 0.03);\n                border-radius: 8px;\n                padding: 12px;\n                margin-bottom: 8px;\n                border-left: 3px solid #00d4aa;\n            }\n\n            .position-item.negative {\n                border-left-color: #ff4757;\n            }\n\n            .item-header {\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n                margin-bottom: 5px;\n            }\n\n            .symbol-name {\n                font-weight: bold;\n                font-size: 0.95rem;\n            }\n\n            .item-details {\n                font-size: 0.8rem;\n                color: #ccc;\n                line-height: 1.4;\n            }\n\n            .pnl-value {\n                font-weight: bold;\n                font-size: 0.9rem;\n            }\n\n            .chart-container {\n                height: 400px;\n                margin-top: 10px;\n            }\n\n            .trade-history {\n                max-height: 200px;\n                overflow-y: auto;\n            }\n\n            .trade-item {\n                display: flex;\n                justify-content: space-between;\n                align-items: center;\n                padding: 8px;\n                margin-bottom: 5px;\n                background: rgba(255, 255, 255, 0.03);\n                border-radius: 6px;\n                font-size: 0.8rem;\n            }\n\n            .trade-buy {\n                border-left: 2px solid #00ff88;\n            }\n\n            .trade-sell {\n                border-left: 2px solid #ff4757;\n            }\n\n            @media (max-width: 1200px) {\n                .trading-grid {\n                    grid-template-columns: 1fr;\n                    grid-template-rows: auto auto auto;\n                }\n            }\n        </style>\n    </head>\n    <body>\n        <header class=\"header\">\n            <div class=\"logo\">Sofia V2 Paper Trading</div>\n            <div class=\"portfolio-summary\">\n                <div class=\"balance\">Balance: $<span id=\"balance\">10,000.00</span></div>\n                <div class=\"pnl\" id=\"total-pnl\">P&L: $0.00 (0.00%)</div>\n            </div>\n        </header>\n\n        <div class=\"trading-grid\">\n            <!-- Left Panel - Trading Controls -->\n            <div class=\"left-panel\">\n                <div class=\"card\">\n                    <div class=\"card-title\">Select Asset</div>\n                    <div class=\"symbol-selector\">\n                        <div class=\"symbol-btn active\" data-symbol=\"BTC\">BTC</div>\n                        <div class=\"symbol-btn\" data-symbol=\"ETH\">ETH</div>\n                        <div class=\"symbol-btn\" data-symbol=\"SOL\">SOL</div>\n                        <div class=\"symbol-btn\" data-symbol=\"BNB\">BNB</div>\n                        <div class=\"symbol-btn\" data-symbol=\"ADA\">ADA</div>\n                        <div class=\"symbol-btn\" data-symbol=\"DOT\">DOT</div>\n                        <div class=\"symbol-btn\" data-symbol=\"LINK\">LINK</div>\n                        <div class=\"symbol-btn\" data-symbol=\"LTC\">LTC</div>\n                    </div>\n\n                    <div class=\"current-price\">\n                        <div class=\"price-display\" id=\"current-price\">$0.00</div>\n                        <div class=\"price-change\" id=\"price-change\">+0.00%</div>\n                    </div>\n                </div>\n\n                <div class=\"card\">\n                    <div class=\"card-title\">Place Order</div>\n                    <div class=\"trade-tabs\">\n                        <button class=\"tab-btn active\" id=\"buy-tab\">BUY</button>\n                        <button class=\"tab-btn sell\" id=\"sell-tab\">SELL</button>\n                    </div>\n\n                    <div class=\"order-type-select\">\n                        <div class=\"order-type-btn active\" data-type=\"market\">Market</div>\n                        <div class=\"order-type-btn\" data-type=\"limit\">Limit</div>\n                        <div class=\"order-type-btn\" data-type=\"stop\">Stop</div>\n                    </div>\n\n                    <div class=\"trade-form\">\n                        <div class=\"form-group\">\n                            <label class=\"form-label\">Quantity</label>\n                            <input type=\"number\" class=\"form-input\" id=\"quantity\" placeholder=\"0.00\" step=\"0.01\">\n                        </div>\n\n                        <div class=\"form-group\" id=\"price-group\" style=\"display: none;\">\n                            <label class=\"form-label\">Price</label>\n                            <input type=\"number\" class=\"form-input\" id=\"order-price\" placeholder=\"0.00\" step=\"0.01\">\n                        </div>\n\n                        <div class=\"form-group\">\n                            <label class=\"form-label\">Est. Total</label>\n                            <input type=\"text\" class=\"form-input\" id=\"total-cost\" readonly>\n                        </div>\n\n                        <button class=\"submit-btn\" id=\"submit-order\">Place Buy Order</button>\n                    </div>\n                </div>\n            </div>\n\n            <!-- Center Panel - Chart -->\n            <div class=\"main-chart\">\n                <div class=\"card-title\">Price Chart</div>\n                <div class=\"chart-container\">\n                    <canvas id=\"price-chart\"></canvas>\n                </div>\n            </div>\n\n            <!-- Right Panel - Portfolio & Orders -->\n            <div class=\"right-panel\">\n                <div class=\"card\">\n                    <div class=\"card-title\">Open Positions</div>\n                    <div class=\"positions-list\" id=\"positions-list\">\n                        <div style=\"text-align: center; color: #888; padding: 20px;\">\n                            No open positions\n                        </div>\n                    </div>\n                </div>\n\n                <div class=\"card\">\n                    <div class=\"card-title\">Open Orders</div>\n                    <div class=\"orders-list\" id=\"orders-list\">\n                        <div style=\"text-align: center; color: #888; padding: 20px;\">\n                            No open orders\n                        </div>\n                    </div>\n                </div>\n\n                <div class=\"card\">\n                    <div class=\"card-title\">Recent Trades</div>\n                    <div class=\"trade-history\" id=\"trade-history\">\n                        <div style=\"text-align: center; color: #888; padding: 20px;\">\n                            No trades yet\n                        </div>\n                    </div>\n                </div>\n            </div>\n        </div>\n\n        <script>\n            // Trading interface state\n            let ws;\n            let chart;\n            let currentSymbol = 'BTC';\n            let currentSide = 'buy';\n            let currentOrderType = 'market';\n            let currentPrice = 0;\n            let portfolio = null;\n            let chartData = [];\n\n            // Initialize\n            document.addEventListener('DOMContentLoaded', function() {\n                initializeInterface();\n                connectWebSocket();\n                setupEventListeners();\n            });\n\n            function initializeInterface() {\n                // Initialize chart\n                const ctx = document.getElementById('price-chart').getContext('2d');\n                chart = new Chart(ctx, {\n                    type: 'line',\n                    data: {\n                        datasets: [{\n                            label: currentSymbol + ' Price',\n                            data: chartData,\n                            borderColor: '#00d4aa',\n                            backgroundColor: 'rgba(0, 212, 170, 0.1)',\n                            tension: 0.4,\n                            fill: true\n                        }]\n                    },\n                    options: {\n                        responsive: true,\n                        maintainAspectRatio: false,\n                        plugins: {\n                            legend: {\n                                labels: { color: '#ffffff' }\n                            }\n                        },\n                        scales: {\n                            x: {\n                                type: 'time',\n                                time: { displayFormats: { minute: 'HH:mm' } },\n                                ticks: { color: '#888888' },\n                                grid: { color: 'rgba(255, 255, 255, 0.1)' }\n                            },\n                            y: {\n                                ticks: {\n                                    color: '#888888',\n                                    callback: function(value) { return '$' + value.toLocaleString(); }\n                                },\n                                grid: { color: 'rgba(255, 255, 255, 0.1)' }\n                            }\n                        }\n                    }\n                });\n            }\n\n            function setupEventListeners() {\n                // Symbol selection\n                document.querySelectorAll('.symbol-btn').forEach(btn => {\n                    btn.addEventListener('click', function() {\n                        document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('active'));\n                        this.classList.add('active');\n                        currentSymbol = this.dataset.symbol;\n                        updateSymbol();\n                    });\n                });\n\n                // Buy/Sell tabs\n                document.getElementById('buy-tab').addEventListener('click', function() {\n                    document.getElementById('sell-tab').classList.remove('active');\n                    this.classList.add('active');\n                    currentSide = 'buy';\n                    updateTradeForm();\n                });\n\n                document.getElementById('sell-tab').addEventListener('click', function() {\n                    document.getElementById('buy-tab').classList.remove('active');\n                    this.classList.add('active');\n                    currentSide = 'sell';\n                    updateTradeForm();\n                });\n\n                // Order type selection\n                document.querySelectorAll('.order-type-btn').forEach(btn => {\n                    btn.addEventListener('click', function() {\n                        document.querySelectorAll('.order-type-btn').forEach(b => b.classList.remove('active'));\n                        this.classList.add('active');\n                        currentOrderType = this.dataset.type;\n                        updateOrderType();\n                    });\n                });\n\n                // Form inputs\n                document.getElementById('quantity').addEventListener('input', updateTotalCost);\n                document.getElementById('order-price').addEventListener('input', updateTotalCost);\n\n                // Submit order\n                document.getElementById('submit-order').addEventListener('click', submitOrder);\n            }\n\n            function connectWebSocket() {\n                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';\n                const wsUrl = `${protocol}//${window.location.host}/ws/trading`;\n\n                ws = new WebSocket(wsUrl);\n\n                ws.onopen = function() {\n                    console.log('Connected to trading WebSocket');\n                    // Request portfolio update\n                    ws.send(JSON.stringify({type: 'get_portfolio'}));\n                };\n\n                ws.onmessage = function(event) {\n                    const message = JSON.parse(event.data);\n                    handleWebSocketMessage(message);\n                };\n\n                ws.onclose = function() {\n                    console.log('Trading WebSocket connection closed');\n                    setTimeout(connectWebSocket, 3000);\n                };\n            }\n\n            function handleWebSocketMessage(message) {\n                switch(message.type) {\n                    case 'price_update':\n                        updatePrice(message.data);\n                        break;\n                    case 'portfolio_update':\n                        updatePortfolio(message.data);\n                        break;\n                    case 'order_update':\n                        updateOrders(message.data);\n                        break;\n                    case 'trade_update':\n                        updateTradeHistory(message.data);\n                        break;\n                }\n            }\n\n            function updatePrice(priceData) {\n                if (priceData[currentSymbol]) {\n                    const data = priceData[currentSymbol];\n                    currentPrice = data.price;\n\n                    document.getElementById('current-price').textContent = '$' + currentPrice.toLocaleString();\n\n                    const changeEl = document.getElementById('price-change');\n                    const change = data.change_24h;\n                    changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';\n                    changeEl.className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');\n\n                    // Update chart\n                    const now = new Date();\n                    chartData.push({x: now, y: currentPrice});\n                    if (chartData.length > 50) chartData.shift();\n\n                    chart.data.datasets[0].data = chartData;\n                    chart.data.datasets[0].label = currentSymbol + ' Price';\n                    chart.update('none');\n\n                    updateTotalCost();\n                }\n            }\n\n            function updatePortfolio(portfolioData) {\n                portfolio = portfolioData;\n\n                // Update header\n                document.getElementById('balance').textContent = portfolioData.balance.toLocaleString('en-US', {minimumFractionDigits: 2});\n\n                const pnlEl = document.getElementById('total-pnl');\n                const pnl = portfolioData.total_pnl;\n                const pnlPercent = portfolioData.total_pnl_percent;\n                pnlEl.textContent = `P&L: $${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)`;\n                pnlEl.className = 'pnl ' + (pnl >= 0 ? 'positive' : 'negative');\n\n                // Update positions\n                updatePositions(portfolioData.positions);\n                updateOrders(portfolioData.open_orders);\n            }\n\n            function updatePositions(positions) {\n                const container = document.getElementById('positions-list');\n\n                if (positions.length === 0) {\n                    container.innerHTML = '<div style=\"text-align: center; color: #888; padding: 20px;\">No open positions</div>';\n                    return;\n                }\n\n                container.innerHTML = '';\n                positions.forEach(pos => {\n                    const isProfit = pos.unrealized_pnl >= 0;\n                    const item = document.createElement('div');\n                    item.className = `position-item ${isProfit ? '' : 'negative'}`;\n\n                    item.innerHTML = `\n                        <div class=\"item-header\">\n                            <span class=\"symbol-name\">${pos.symbol}</span>\n                            <span class=\"pnl-value ${isProfit ? 'positive' : 'negative'}\">\n                                $${pos.unrealized_pnl.toFixed(2)}\n                            </span>\n                        </div>\n                        <div class=\"item-details\">\n                            Qty: ${pos.quantity} | Avg: $${pos.avg_price.toFixed(2)}<br>\n                            Current: $${pos.current_price.toFixed(2)}\n                        </div>\n                    `;\n\n                    container.appendChild(item);\n                });\n            }\n\n            function updateOrders(orders) {\n                const container = document.getElementById('orders-list');\n\n                if (orders.length === 0) {\n                    container.innerHTML = '<div style=\"text-align: center; color: #888; padding: 20px;\">No open orders</div>';\n                    return;\n                }\n\n                container.innerHTML = '';\n                orders.forEach(order => {\n                    const item = document.createElement('div');\n                    item.className = 'order-item';\n\n                    item.innerHTML = `\n                        <div class=\"item-header\">\n                            <span class=\"symbol-name\">${order.symbol}</span>\n                            <button onclick=\"cancelOrder('${order.id}')\" style=\"background: #ff4757; border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.7rem;\">Cancel</button>\n                        </div>\n                        <div class=\"item-details\">\n                            ${order.side.toUpperCase()} ${order.quantity} @ $${order.price || 'Market'}<br>\n                            ${order.order_type}\n                        </div>\n                    `;\n\n                    container.appendChild(item);\n                });\n            }\n\n            function updateTradeHistory(trades) {\n                const container = document.getElementById('trade-history');\n\n                if (trades.length === 0) {\n                    container.innerHTML = '<div style=\"text-align: center; color: #888; padding: 20px;\">No trades yet</div>';\n                    return;\n                }\n\n                container.innerHTML = '';\n                trades.slice(0, 10).forEach(trade => {\n                    const item = document.createElement('div');\n                    item.className = `trade-item trade-${trade.side}`;\n\n                    const time = new Date(trade.timestamp).toLocaleTimeString();\n                    item.innerHTML = `\n                        <div>\n                            <div style=\"font-weight: bold;\">${trade.symbol} ${trade.side.toUpperCase()}</div>\n                            <div style=\"font-size: 0.7rem; color: #888;\">${time}</div>\n                        </div>\n                        <div style=\"text-align: right;\">\n                            <div>${trade.quantity} @ $${trade.price.toFixed(2)}</div>\n                            ${trade.pnl !== 0 ? `<div class=\"${trade.pnl >= 0 ? 'positive' : 'negative'}\">$${trade.pnl.toFixed(2)}</div>` : ''}\n                        </div>\n                    `;\n\n                    container.appendChild(item);\n                });\n            }\n\n            function updateSymbol() {\n                chartData = [];\n                chart.data.datasets[0].data = chartData;\n                chart.data.datasets[0].label = currentSymbol + ' Price';\n                chart.update();\n\n                // Request price for new symbol\n                if (ws && ws.readyState === WebSocket.OPEN) {\n                    ws.send(JSON.stringify({type: 'get_price', symbol: currentSymbol}));\n                }\n            }\n\n            function updateTradeForm() {\n                const submitBtn = document.getElementById('submit-order');\n                submitBtn.textContent = currentSide === 'buy' ? 'Place Buy Order' : 'Place Sell Order';\n                submitBtn.className = `submit-btn ${currentSide}`;\n                updateTotalCost();\n            }\n\n            function updateOrderType() {\n                const priceGroup = document.getElementById('price-group');\n                priceGroup.style.display = currentOrderType === 'market' ? 'none' : 'block';\n                updateTotalCost();\n            }\n\n            function updateTotalCost() {\n                const quantity = parseFloat(document.getElementById('quantity').value) || 0;\n                const price = currentOrderType === 'market' ? currentPrice : (parseFloat(document.getElementById('order-price').value) || currentPrice);\n                const total = quantity * price;\n                const fee = total * 0.0015; // 0.15% fee\n                const totalWithFee = total + fee;\n\n                document.getElementById('total-cost').value = totalWithFee > 0 ? `$${totalWithFee.toFixed(2)} (inc. fee)` : '';\n\n                // Enable/disable submit button\n                const submitBtn = document.getElementById('submit-order');\n                const canTrade = quantity > 0 && (currentOrderType === 'market' || price > 0);\n                submitBtn.disabled = !canTrade;\n            }\n\n            function submitOrder() {\n                const quantity = parseFloat(document.getElementById('quantity').value);\n                const price = currentOrderType === 'market' ? null : parseFloat(document.getElementById('order-price').value);\n\n                if (!quantity || quantity <= 0) {\n                    alert('Please enter a valid quantity');\n                    return;\n                }\n\n                if (currentOrderType !== 'market' && (!price || price <= 0)) {\n                    alert('Please enter a valid price');\n                    return;\n                }\n\n                const order = {\n                    type: 'place_order',\n                    symbol: currentSymbol,\n                    side: currentSide,\n                    order_type: currentOrderType,\n                    quantity: quantity,\n                    price: price\n                };\n\n                if (ws && ws.readyState === WebSocket.OPEN) {\n                    ws.send(JSON.stringify(order));\n\n                    // Clear form\n                    document.getElementById('quantity').value = '';\n                    document.getElementById('order-price').value = '';\n                    updateTotalCost();\n                }\n            }\n\n            function cancelOrder(orderId) {\n                if (ws && ws.readyState === WebSocket.OPEN) {\n                    ws.send(JSON.stringify({\n                        type: 'cancel_order',\n                        order_id: orderId\n                    }));\n                }\n            }\n        </script>\n    </body>\n    </html>\n    "


@app.websocket("/ws/trading")
async def trading_websocket(websocket: WebSocket):
    """WebSocket endpoint for trading interface"""
    client_id = str(uuid.uuid4())
    user_id = "demo_user"
    await trading_manager.connect(websocket, client_id, user_id)
    if not paper_engine.get_portfolio(user_id):
        paper_engine.create_portfolio(user_id, 10000.0)
    asyncio.create_task(stream_prices_to_user(user_id))
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            await handle_trading_message(message, user_id)
    except WebSocketDisconnect:
        trading_manager.disconnect(client_id, user_id)


async def handle_trading_message(message: dict, user_id: str):
    """Handle trading WebSocket messages"""
    try:
        if message["type"] == "place_order":
            order = await paper_engine.place_order(
                user_id=user_id,
                symbol=message["symbol"],
                side=OrderSide(message["side"]),
                order_type=OrderType(message["order_type"]),
                quantity=message["quantity"],
                price=message.get("price"),
            )
            await trading_manager.send_to_user(
                {"type": "order_placed", "order": order.to_dict()}, user_id
            )
            portfolio = paper_engine.get_portfolio_summary(user_id)
            await trading_manager.send_to_user(
                {"type": "portfolio_update", "data": portfolio}, user_id
            )
        elif message["type"] == "cancel_order":
            success = await paper_engine.cancel_order(user_id, message["order_id"])
            if success:
                portfolio = paper_engine.get_portfolio_summary(user_id)
                await trading_manager.send_to_user(
                    {"type": "portfolio_update", "data": portfolio}, user_id
                )
        elif message["type"] == "get_portfolio":
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if portfolio:
                await trading_manager.send_to_user(
                    {"type": "portfolio_update", "data": portfolio}, user_id
                )
                trades = paper_engine.get_trade_history(user_id, 20)
                await trading_manager.send_to_user(
                    {"type": "trade_update", "data": trades}, user_id
                )
    except Exception as e:
        logger.error(f"Error handling trading message: {e}")
        await trading_manager.send_to_user({"type": "error", "message": str(e)}, user_id)


async def stream_prices_to_user(user_id: str):
    """Stream real-time prices to a specific user"""
    symbols = [
        "bitcoin",
        "ethereum",
        "solana",
        "binancecoin",
        "cardano",
        "polkadot",
        "chainlink",
        "litecoin",
    ]
    while user_id in trading_manager.user_connections:
        try:
            market_data = await fetcher.get_market_data(symbols)
            if market_data:
                await trading_manager.send_to_user(
                    {"type": "price_update", "data": market_data}, user_id
                )
                portfolio = paper_engine.get_portfolio_summary(user_id)
                if portfolio:
                    await trading_manager.send_to_user(
                        {"type": "portfolio_update", "data": portfolio}, user_id
                    )
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Error streaming prices to user {user_id}: {e}")
            await asyncio.sleep(5)


@app.get("/api/portfolio/{user_id}")
async def get_portfolio_api(user_id: str):
    """API endpoint to get portfolio summary"""
    portfolio = paper_engine.get_portfolio_summary(user_id)
    if not portfolio:
        return JSONResponse({"error": "Portfolio not found"}, status_code=404)
    return portfolio


@app.post("/api/order")
async def place_order_api(
    symbol: str = Form(...),
    side: str = Form(...),
    order_type: str = Form(...),
    quantity: float = Form(...),
    price: Optional[float] = Form(None),
    user_id: str = "demo_user",
):
    """API endpoint to place an order"""
    try:
        order = await paper_engine.place_order(
            user_id=user_id,
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=quantity,
            price=price,
        )
        return {"success": True, "order": order.to_dict()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
