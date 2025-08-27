"""
Advanced Trading Interface with Real-Time Paper Trading
Beautiful UI for executing trades with real crypto prices
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging
import uuid

from ..trading.paper_trading_engine import paper_engine, OrderSide, OrderType
from ..data.real_time_fetcher import fetcher
from ..auth.dependencies import get_current_active_user

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
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sofia V2 - Paper Trading Interface</title>
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
                padding: 1rem 2rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .logo {
                font-size: 1.5rem;
                font-weight: bold;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .portfolio-summary {
                display: flex;
                gap: 20px;
                align-items: center;
            }
            
            .balance {
                font-size: 1.2rem;
                font-weight: bold;
            }
            
            .pnl {
                font-weight: bold;
            }
            
            .pnl.positive {
                color: #00ff88;
            }
            
            .pnl.negative {
                color: #ff4757;
            }
            
            .trading-grid {
                display: grid;
                grid-template-columns: 300px 1fr 350px;
                gap: 20px;
                padding: 20px;
                height: calc(100vh - 80px);
            }
            
            .left-panel, .right-panel {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .main-chart {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 15px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.3s ease;
            }
            
            .card:hover {
                border-color: rgba(0, 212, 170, 0.3);
                box-shadow: 0 5px 15px rgba(0, 212, 170, 0.1);
            }
            
            .card-title {
                font-size: 1rem;
                font-weight: bold;
                margin-bottom: 10px;
                color: #00d4aa;
                text-align: center;
            }
            
            .symbol-selector {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 15px;
            }
            
            .symbol-btn {
                padding: 8px 12px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                font-size: 0.85rem;
                font-weight: bold;
            }
            
            .symbol-btn:hover {
                background: rgba(0, 212, 170, 0.2);
                border-color: #00d4aa;
            }
            
            .symbol-btn.active {
                background: #00d4aa;
                color: #000;
            }
            
            .current-price {
                text-align: center;
                margin-bottom: 15px;
            }
            
            .price-display {
                font-size: 1.8rem;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .price-change {
                font-size: 0.9rem;
                font-weight: bold;
            }
            
            .trade-form {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .trade-tabs {
                display: flex;
                margin-bottom: 10px;
            }
            
            .tab-btn {
                flex: 1;
                padding: 10px;
                background: rgba(255, 255, 255, 0.1);
                border: none;
                color: white;
                cursor: pointer;
                transition: all 0.2s ease;
                font-weight: bold;
            }
            
            .tab-btn:first-child {
                border-radius: 8px 0 0 8px;
            }
            
            .tab-btn:last-child {
                border-radius: 0 8px 8px 0;
            }
            
            .tab-btn.active {
                background: #00d4aa;
                color: #000;
            }
            
            .tab-btn.sell.active {
                background: #ff4757;
                color: white;
            }
            
            .form-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            
            .form-label {
                font-size: 0.85rem;
                color: #ccc;
                font-weight: bold;
            }
            
            .form-input {
                padding: 12px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: white;
                font-size: 0.95rem;
            }
            
            .form-input:focus {
                outline: none;
                border-color: #00d4aa;
                box-shadow: 0 0 0 2px rgba(0, 212, 170, 0.2);
            }
            
            .order-type-select {
                display: flex;
                gap: 5px;
                margin-bottom: 10px;
            }
            
            .order-type-btn {
                flex: 1;
                padding: 8px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.8rem;
                text-align: center;
                transition: all 0.2s ease;
            }
            
            .order-type-btn.active {
                background: #00d4aa;
                color: #000;
            }
            
            .submit-btn {
                padding: 15px;
                background: linear-gradient(45deg, #00d4aa, #00b4d8);
                border: none;
                border-radius: 10px;
                color: white;
                font-size: 1rem;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 10px;
            }
            
            .submit-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 212, 170, 0.4);
            }
            
            .submit-btn.sell {
                background: linear-gradient(45deg, #ff4757, #ff6b7d);
            }
            
            .submit-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            
            .positions-list, .orders-list {
                max-height: 300px;
                overflow-y: auto;
            }
            
            .position-item, .order-item {
                background: rgba(255, 255, 255, 0.03);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
                border-left: 3px solid #00d4aa;
            }
            
            .position-item.negative {
                border-left-color: #ff4757;
            }
            
            .item-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 5px;
            }
            
            .symbol-name {
                font-weight: bold;
                font-size: 0.95rem;
            }
            
            .item-details {
                font-size: 0.8rem;
                color: #ccc;
                line-height: 1.4;
            }
            
            .pnl-value {
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .chart-container {
                height: 400px;
                margin-top: 10px;
            }
            
            .trade-history {
                max-height: 200px;
                overflow-y: auto;
            }
            
            .trade-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px;
                margin-bottom: 5px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                font-size: 0.8rem;
            }
            
            .trade-buy {
                border-left: 2px solid #00ff88;
            }
            
            .trade-sell {
                border-left: 2px solid #ff4757;
            }
            
            @media (max-width: 1200px) {
                .trading-grid {
                    grid-template-columns: 1fr;
                    grid-template-rows: auto auto auto;
                }
            }
        </style>
    </head>
    <body>
        <header class="header">
            <div class="logo">Sofia V2 Paper Trading</div>
            <div class="portfolio-summary">
                <div class="balance">Balance: $<span id="balance">10,000.00</span></div>
                <div class="pnl" id="total-pnl">P&L: $0.00 (0.00%)</div>
            </div>
        </header>
        
        <div class="trading-grid">
            <!-- Left Panel - Trading Controls -->
            <div class="left-panel">
                <div class="card">
                    <div class="card-title">Select Asset</div>
                    <div class="symbol-selector">
                        <div class="symbol-btn active" data-symbol="BTC">BTC</div>
                        <div class="symbol-btn" data-symbol="ETH">ETH</div>
                        <div class="symbol-btn" data-symbol="SOL">SOL</div>
                        <div class="symbol-btn" data-symbol="BNB">BNB</div>
                        <div class="symbol-btn" data-symbol="ADA">ADA</div>
                        <div class="symbol-btn" data-symbol="DOT">DOT</div>
                        <div class="symbol-btn" data-symbol="LINK">LINK</div>
                        <div class="symbol-btn" data-symbol="LTC">LTC</div>
                    </div>
                    
                    <div class="current-price">
                        <div class="price-display" id="current-price">$0.00</div>
                        <div class="price-change" id="price-change">+0.00%</div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Place Order</div>
                    <div class="trade-tabs">
                        <button class="tab-btn active" id="buy-tab">BUY</button>
                        <button class="tab-btn sell" id="sell-tab">SELL</button>
                    </div>
                    
                    <div class="order-type-select">
                        <div class="order-type-btn active" data-type="market">Market</div>
                        <div class="order-type-btn" data-type="limit">Limit</div>
                        <div class="order-type-btn" data-type="stop">Stop</div>
                    </div>
                    
                    <div class="trade-form">
                        <div class="form-group">
                            <label class="form-label">Quantity</label>
                            <input type="number" class="form-input" id="quantity" placeholder="0.00" step="0.01">
                        </div>
                        
                        <div class="form-group" id="price-group" style="display: none;">
                            <label class="form-label">Price</label>
                            <input type="number" class="form-input" id="order-price" placeholder="0.00" step="0.01">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Est. Total</label>
                            <input type="text" class="form-input" id="total-cost" readonly>
                        </div>
                        
                        <button class="submit-btn" id="submit-order">Place Buy Order</button>
                    </div>
                </div>
            </div>
            
            <!-- Center Panel - Chart -->
            <div class="main-chart">
                <div class="card-title">Price Chart</div>
                <div class="chart-container">
                    <canvas id="price-chart"></canvas>
                </div>
            </div>
            
            <!-- Right Panel - Portfolio & Orders -->
            <div class="right-panel">
                <div class="card">
                    <div class="card-title">Open Positions</div>
                    <div class="positions-list" id="positions-list">
                        <div style="text-align: center; color: #888; padding: 20px;">
                            No open positions
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Open Orders</div>
                    <div class="orders-list" id="orders-list">
                        <div style="text-align: center; color: #888; padding: 20px;">
                            No open orders
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Recent Trades</div>
                    <div class="trade-history" id="trade-history">
                        <div style="text-align: center; color: #888; padding: 20px;">
                            No trades yet
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Trading interface state
            let ws;
            let chart;
            let currentSymbol = 'BTC';
            let currentSide = 'buy';
            let currentOrderType = 'market';
            let currentPrice = 0;
            let portfolio = null;
            let chartData = [];
            
            // Initialize
            document.addEventListener('DOMContentLoaded', function() {
                initializeInterface();
                connectWebSocket();
                setupEventListeners();
            });
            
            function initializeInterface() {
                // Initialize chart
                const ctx = document.getElementById('price-chart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: currentSymbol + ' Price',
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
                                labels: { color: '#ffffff' }
                            }
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: { displayFormats: { minute: 'HH:mm' } },
                                ticks: { color: '#888888' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            },
                            y: {
                                ticks: { 
                                    color: '#888888',
                                    callback: function(value) { return '$' + value.toLocaleString(); }
                                },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            }
                        }
                    }
                });
            }
            
            function setupEventListeners() {
                // Symbol selection
                document.querySelectorAll('.symbol-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        currentSymbol = this.dataset.symbol;
                        updateSymbol();
                    });
                });
                
                // Buy/Sell tabs
                document.getElementById('buy-tab').addEventListener('click', function() {
                    document.getElementById('sell-tab').classList.remove('active');
                    this.classList.add('active');
                    currentSide = 'buy';
                    updateTradeForm();
                });
                
                document.getElementById('sell-tab').addEventListener('click', function() {
                    document.getElementById('buy-tab').classList.remove('active');
                    this.classList.add('active');
                    currentSide = 'sell';
                    updateTradeForm();
                });
                
                // Order type selection
                document.querySelectorAll('.order-type-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        document.querySelectorAll('.order-type-btn').forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        currentOrderType = this.dataset.type;
                        updateOrderType();
                    });
                });
                
                // Form inputs
                document.getElementById('quantity').addEventListener('input', updateTotalCost);
                document.getElementById('order-price').addEventListener('input', updateTotalCost);
                
                // Submit order
                document.getElementById('submit-order').addEventListener('click', submitOrder);
            }
            
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws/trading`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    console.log('Connected to trading WebSocket');
                    // Request portfolio update
                    ws.send(JSON.stringify({type: 'get_portfolio'}));
                };
                
                ws.onmessage = function(event) {
                    const message = JSON.parse(event.data);
                    handleWebSocketMessage(message);
                };
                
                ws.onclose = function() {
                    console.log('Trading WebSocket connection closed');
                    setTimeout(connectWebSocket, 3000);
                };
            }
            
            function handleWebSocketMessage(message) {
                switch(message.type) {
                    case 'price_update':
                        updatePrice(message.data);
                        break;
                    case 'portfolio_update':
                        updatePortfolio(message.data);
                        break;
                    case 'order_update':
                        updateOrders(message.data);
                        break;
                    case 'trade_update':
                        updateTradeHistory(message.data);
                        break;
                }
            }
            
            function updatePrice(priceData) {
                if (priceData[currentSymbol]) {
                    const data = priceData[currentSymbol];
                    currentPrice = data.price;
                    
                    document.getElementById('current-price').textContent = '$' + currentPrice.toLocaleString();
                    
                    const changeEl = document.getElementById('price-change');
                    const change = data.change_24h;
                    changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                    changeEl.className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');
                    
                    // Update chart
                    const now = new Date();
                    chartData.push({x: now, y: currentPrice});
                    if (chartData.length > 50) chartData.shift();
                    
                    chart.data.datasets[0].data = chartData;
                    chart.data.datasets[0].label = currentSymbol + ' Price';
                    chart.update('none');
                    
                    updateTotalCost();
                }
            }
            
            function updatePortfolio(portfolioData) {
                portfolio = portfolioData;
                
                // Update header
                document.getElementById('balance').textContent = portfolioData.balance.toLocaleString('en-US', {minimumFractionDigits: 2});
                
                const pnlEl = document.getElementById('total-pnl');
                const pnl = portfolioData.total_pnl;
                const pnlPercent = portfolioData.total_pnl_percent;
                pnlEl.textContent = `P&L: $${pnl.toFixed(2)} (${pnlPercent.toFixed(2)}%)`;
                pnlEl.className = 'pnl ' + (pnl >= 0 ? 'positive' : 'negative');
                
                // Update positions
                updatePositions(portfolioData.positions);
                updateOrders(portfolioData.open_orders);
            }
            
            function updatePositions(positions) {
                const container = document.getElementById('positions-list');
                
                if (positions.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">No open positions</div>';
                    return;
                }
                
                container.innerHTML = '';
                positions.forEach(pos => {
                    const isProfit = pos.unrealized_pnl >= 0;
                    const item = document.createElement('div');
                    item.className = `position-item ${isProfit ? '' : 'negative'}`;
                    
                    item.innerHTML = `
                        <div class="item-header">
                            <span class="symbol-name">${pos.symbol}</span>
                            <span class="pnl-value ${isProfit ? 'positive' : 'negative'}">
                                $${pos.unrealized_pnl.toFixed(2)}
                            </span>
                        </div>
                        <div class="item-details">
                            Qty: ${pos.quantity} | Avg: $${pos.avg_price.toFixed(2)}<br>
                            Current: $${pos.current_price.toFixed(2)}
                        </div>
                    `;
                    
                    container.appendChild(item);
                });
            }
            
            function updateOrders(orders) {
                const container = document.getElementById('orders-list');
                
                if (orders.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">No open orders</div>';
                    return;
                }
                
                container.innerHTML = '';
                orders.forEach(order => {
                    const item = document.createElement('div');
                    item.className = 'order-item';
                    
                    item.innerHTML = `
                        <div class="item-header">
                            <span class="symbol-name">${order.symbol}</span>
                            <button onclick="cancelOrder('${order.id}')" style="background: #ff4757; border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.7rem;">Cancel</button>
                        </div>
                        <div class="item-details">
                            ${order.side.toUpperCase()} ${order.quantity} @ $${order.price || 'Market'}<br>
                            ${order.order_type}
                        </div>
                    `;
                    
                    container.appendChild(item);
                });
            }
            
            function updateTradeHistory(trades) {
                const container = document.getElementById('trade-history');
                
                if (trades.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">No trades yet</div>';
                    return;
                }
                
                container.innerHTML = '';
                trades.slice(0, 10).forEach(trade => {
                    const item = document.createElement('div');
                    item.className = `trade-item trade-${trade.side}`;
                    
                    const time = new Date(trade.timestamp).toLocaleTimeString();
                    item.innerHTML = `
                        <div>
                            <div style="font-weight: bold;">${trade.symbol} ${trade.side.toUpperCase()}</div>
                            <div style="font-size: 0.7rem; color: #888;">${time}</div>
                        </div>
                        <div style="text-align: right;">
                            <div>${trade.quantity} @ $${trade.price.toFixed(2)}</div>
                            ${trade.pnl !== 0 ? `<div class="${trade.pnl >= 0 ? 'positive' : 'negative'}">$${trade.pnl.toFixed(2)}</div>` : ''}
                        </div>
                    `;
                    
                    container.appendChild(item);
                });
            }
            
            function updateSymbol() {
                chartData = [];
                chart.data.datasets[0].data = chartData;
                chart.data.datasets[0].label = currentSymbol + ' Price';
                chart.update();
                
                // Request price for new symbol
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'get_price', symbol: currentSymbol}));
                }
            }
            
            function updateTradeForm() {
                const submitBtn = document.getElementById('submit-order');
                submitBtn.textContent = currentSide === 'buy' ? 'Place Buy Order' : 'Place Sell Order';
                submitBtn.className = `submit-btn ${currentSide}`;
                updateTotalCost();
            }
            
            function updateOrderType() {
                const priceGroup = document.getElementById('price-group');
                priceGroup.style.display = currentOrderType === 'market' ? 'none' : 'block';
                updateTotalCost();
            }
            
            function updateTotalCost() {
                const quantity = parseFloat(document.getElementById('quantity').value) || 0;
                const price = currentOrderType === 'market' ? currentPrice : (parseFloat(document.getElementById('order-price').value) || currentPrice);
                const total = quantity * price;
                const fee = total * 0.0015; // 0.15% fee
                const totalWithFee = total + fee;
                
                document.getElementById('total-cost').value = totalWithFee > 0 ? `$${totalWithFee.toFixed(2)} (inc. fee)` : '';
                
                // Enable/disable submit button
                const submitBtn = document.getElementById('submit-order');
                const canTrade = quantity > 0 && (currentOrderType === 'market' || price > 0);
                submitBtn.disabled = !canTrade;
            }
            
            function submitOrder() {
                const quantity = parseFloat(document.getElementById('quantity').value);
                const price = currentOrderType === 'market' ? null : parseFloat(document.getElementById('order-price').value);
                
                if (!quantity || quantity <= 0) {
                    alert('Please enter a valid quantity');
                    return;
                }
                
                if (currentOrderType !== 'market' && (!price || price <= 0)) {
                    alert('Please enter a valid price');
                    return;
                }
                
                const order = {
                    type: 'place_order',
                    symbol: currentSymbol,
                    side: currentSide,
                    order_type: currentOrderType,
                    quantity: quantity,
                    price: price
                };
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(order));
                    
                    // Clear form
                    document.getElementById('quantity').value = '';
                    document.getElementById('order-price').value = '';
                    updateTotalCost();
                }
            }
            
            function cancelOrder(orderId) {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'cancel_order',
                        order_id: orderId
                    }));
                }
            }
        </script>
    </body>
    </html>
    """

@app.websocket("/ws/trading")
async def trading_websocket(websocket: WebSocket):
    """WebSocket endpoint for trading interface"""
    client_id = str(uuid.uuid4())
    user_id = "demo_user"  # In real app, get from auth
    
    await trading_manager.connect(websocket, client_id, user_id)
    
    # Create demo portfolio if doesn't exist
    if not paper_engine.get_portfolio(user_id):
        paper_engine.create_portfolio(user_id, 10000.0)
    
    # Start price streaming for this user
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
            # Place order
            order = await paper_engine.place_order(
                user_id=user_id,
                symbol=message["symbol"],
                side=OrderSide(message["side"]),
                order_type=OrderType(message["order_type"]),
                quantity=message["quantity"],
                price=message.get("price")
            )
            
            # Send order confirmation
            await trading_manager.send_to_user({
                "type": "order_placed",
                "order": order.to_dict()
            }, user_id)
            
            # Send updated portfolio
            portfolio = paper_engine.get_portfolio_summary(user_id)
            await trading_manager.send_to_user({
                "type": "portfolio_update",
                "data": portfolio
            }, user_id)
            
        elif message["type"] == "cancel_order":
            # Cancel order
            success = await paper_engine.cancel_order(user_id, message["order_id"])
            
            if success:
                # Send updated portfolio
                portfolio = paper_engine.get_portfolio_summary(user_id)
                await trading_manager.send_to_user({
                    "type": "portfolio_update", 
                    "data": portfolio
                }, user_id)
                
        elif message["type"] == "get_portfolio":
            # Send portfolio data
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if portfolio:
                await trading_manager.send_to_user({
                    "type": "portfolio_update",
                    "data": portfolio
                }, user_id)
                
                # Send trade history
                trades = paper_engine.get_trade_history(user_id, 20)
                await trading_manager.send_to_user({
                    "type": "trade_update", 
                    "data": trades
                }, user_id)
                
    except Exception as e:
        logger.error(f"Error handling trading message: {e}")
        await trading_manager.send_to_user({
            "type": "error",
            "message": str(e)
        }, user_id)

async def stream_prices_to_user(user_id: str):
    """Stream real-time prices to a specific user"""
    symbols = ["bitcoin", "ethereum", "solana", "binancecoin", "cardano", "polkadot", "chainlink", "litecoin"]
    
    while user_id in trading_manager.user_connections:
        try:
            # Get market data
            market_data = await fetcher.get_market_data(symbols)
            
            if market_data:
                await trading_manager.send_to_user({
                    "type": "price_update",
                    "data": market_data
                }, user_id)
                
                # Update portfolio with new prices
                portfolio = paper_engine.get_portfolio_summary(user_id)
                if portfolio:
                    await trading_manager.send_to_user({
                        "type": "portfolio_update",
                        "data": portfolio
                    }, user_id)
                    
            await asyncio.sleep(3)  # Update every 3 seconds
            
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
    user_id: str = "demo_user"  # In real app, get from auth
):
    """API endpoint to place an order"""
    try:
        order = await paper_engine.place_order(
            user_id=user_id,
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=quantity,
            price=price
        )
        
        return {"success": True, "order": order.to_dict()}
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)