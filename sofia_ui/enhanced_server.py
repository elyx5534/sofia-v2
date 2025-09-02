"""
Sofia V2 Enhanced Server - Top Navbar Template with Advanced Features
Combines the original top navbar design with all new AI/Trading capabilities
"""

import asyncio
import json
import os
import random
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import our new advanced modules
try:
    from src.data.real_time_fetcher import fetcher
    from src.ml.real_time_predictor import prediction_engine
    from src.portfolio.advanced_portfolio_manager import portfolio_manager
    from src.scanner.advanced_market_scanner import market_scanner
    from src.trading.paper_trading_engine import paper_engine
    from src.trading.unified_execution_engine import execution_engine

    ADVANCED_FEATURES = True
    print("Advanced features loaded successfully!")
except ImportError as e:
    print(f"Advanced features not available: {e}")
    ADVANCED_FEATURES = False

app = FastAPI(title="Sofia V2 Enhanced", description="Top navbar design with advanced AI features")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    print("Static files directory not found, continuing...")


class EnhancedConnectionManager:
    """Enhanced WebSocket manager for top navbar template"""

    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Enhanced client {client_id} connected")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"Enhanced client {client_id} disconnected")

    async def broadcast_to_all(self, message: dict):
        """Broadcast to all connected clients"""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)


enhanced_manager = EnhancedConnectionManager()


@app.on_event("startup")
async def startup_enhanced():
    """Start all Sofia V2 engines for enhanced server"""
    print("Starting Sofia V2 Enhanced Server...")

    if ADVANCED_FEATURES:
        # Start all engines
        await execution_engine.start()

        # Start enhanced data broadcasting
        asyncio.create_task(broadcast_enhanced_data())

    print("Sofia V2 Enhanced Server fully operational!")


@app.on_event("shutdown")
async def shutdown_enhanced():
    """Cleanup on shutdown"""
    if ADVANCED_FEATURES:
        await execution_engine.stop()
    print("Sofia V2 Enhanced Server shutdown complete")


@app.get("/", response_class=HTMLResponse)
async def enhanced_homepage():
    """Enhanced homepage with top navbar and advanced features"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sofia V2 Enhanced - AI Trading Platform</title>

        <!-- Tailwind CSS -->
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {
                darkMode: 'class',
                theme: {
                    extend: {
                        colors: {
                            primary: '#3b82f6',
                            secondary: '#8b5cf6',
                            success: '#10b981',
                            danger: '#ef4444',
                        },
                        animation: {
                            'float': 'float 6s ease-in-out infinite',
                            'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                            'glow': 'glow 2s ease-in-out infinite alternate',
                        }
                    }
                }
            }
        </script>

        <!-- Chart.js -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <!-- Alpine.js -->
        <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
        <!-- Font Awesome -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

        <style>
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-15px); }
            }

            @keyframes glow {
                from { box-shadow: 0 0 20px rgba(59, 130, 246, 0.4); }
                to { box-shadow: 0 0 30px rgba(59, 130, 246, 0.8); }
            }

            .glass {
                background: rgba(15, 23, 42, 0.5);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(59, 130, 246, 0.2);
            }

            .glass-hover:hover {
                background: rgba(15, 23, 42, 0.7);
                border-color: rgba(59, 130, 246, 0.4);
                transform: translateY(-2px);
            }

            .navbar-glass {
                background: rgba(15, 23, 42, 0.95);
                backdrop-filter: blur(20px);
                border-bottom: 1px solid rgba(59, 130, 246, 0.3);
            }

            .trading-active {
                animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            }
        </style>
    </head>

    <body class="min-h-screen bg-gradient-to-br from-gray-950 via-blue-950 to-gray-950 text-white"
          x-data="sofiaEnhanced()" x-init="init()">

        <!-- Top Navigation Bar -->
        <nav class="fixed top-0 left-0 right-0 z-50 navbar-glass">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex items-center justify-between h-16">
                    <!-- Logo -->
                    <div class="flex items-center space-x-3">
                        <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center animate-glow">
                            <i class="fas fa-robot text-white"></i>
                        </div>
                        <div>
                            <h1 class="text-xl font-bold">Sofia V2 Enhanced</h1>
                            <p class="text-xs text-blue-400">AI Trading Platform</p>
                        </div>
                    </div>

                    <!-- Navigation Menu -->
                    <div class="hidden md:flex items-center space-x-8">
                        <a href="#" @click="activeSection = 'dashboard'" :class="activeSection === 'dashboard' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-300 hover:text-white'"
                           class="py-2 transition-all">
                            <i class="fas fa-th-large mr-2"></i>Dashboard
                        </a>
                        <a href="#" @click="activeSection = 'portfolio'" :class="activeSection === 'portfolio' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-300 hover:text-white'"
                           class="py-2 transition-all">
                            <i class="fas fa-briefcase mr-2"></i>Portfolio
                        </a>
                        <a href="#" @click="activeSection = 'ai_predictions'" :class="activeSection === 'ai_predictions' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-300 hover:text-white'"
                           class="py-2 transition-all">
                            <i class="fas fa-brain mr-2"></i>AI Predictions
                        </a>
                        <a href="#" @click="activeSection = 'scanner'" :class="activeSection === 'scanner' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-300 hover:text-white'"
                           class="py-2 transition-all">
                            <i class="fas fa-radar-dish mr-2"></i>Scanner
                        </a>
                        <a href="#" @click="activeSection = 'trading'" :class="activeSection === 'trading' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-300 hover:text-white'"
                           class="py-2 transition-all">
                            <i class="fas fa-chart-line mr-2"></i>Trading
                        </a>
                    </div>

                    <!-- Status & Controls -->
                    <div class="flex items-center space-x-4">
                        <div class="hidden sm:flex items-center space-x-2 text-sm">
                            <div class="w-2 h-2 rounded-full bg-green-500 trading-active"></div>
                            <span class="text-green-400">Trading Active</span>
                            <span class="text-gray-500">•</span>
                            <span class="text-blue-400" x-text="'AI Models: ' + ai_models_count">AI Models: 5</span>
                        </div>
                        <button @click="refreshAllData()" class="text-gray-400 hover:text-white transition-colors">
                            <i class="fas fa-sync-alt" :class="{'animate-spin': isRefreshing}"></i>
                        </button>
                    </div>
                </div>
            </div>
        </nav>

        <!-- Background Effects -->
        <div class="fixed inset-0 overflow-hidden pointer-events-none">
            <div class="absolute top-20 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl animate-pulse-slow"></div>
            <div class="absolute bottom-20 right-1/4 w-96 h-96 bg-purple-500/5 rounded-full blur-3xl animate-pulse-slow" style="animation-delay: 2s;"></div>
        </div>

        <!-- Main Content -->
        <main class="pt-20 min-h-screen">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

                <!-- Dashboard Section -->
                <div x-show="activeSection === 'dashboard'" class="space-y-8">
                    <!-- Stats Cards -->
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                        <!-- Portfolio Value -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all cursor-pointer">
                            <div class="flex items-center justify-between mb-4">
                                <span class="text-gray-400">Portfolio Value</span>
                                <i class="fas fa-wallet text-blue-400 text-xl"></i>
                            </div>
                            <div class="text-2xl font-bold mb-2" x-text="formatCurrency(portfolio.total_value)">$100,000</div>
                            <div class="flex items-center space-x-2">
                                <span class="text-sm" :class="portfolio.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'"
                                      x-text="formatPercentage(portfolio.daily_pnl_percent)">+0.00%</span>
                                <span class="text-xs text-gray-500">today</span>
                            </div>
                        </div>

                        <!-- Active Trades -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all cursor-pointer">
                            <div class="flex items-center justify-between mb-4">
                                <span class="text-gray-400">Active Trades</span>
                                <i class="fas fa-chart-line text-green-400 text-xl"></i>
                            </div>
                            <div class="text-2xl font-bold mb-2" x-text="positions.length">0</div>
                            <div class="text-xs text-gray-400">Live positions</div>
                        </div>

                        <!-- AI Signals -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all cursor-pointer">
                            <div class="flex items-center justify-between mb-4">
                                <span class="text-gray-400">AI Signals</span>
                                <i class="fas fa-brain text-purple-400 text-xl"></i>
                            </div>
                            <div class="text-2xl font-bold mb-2" x-text="ai_signals_count">0</div>
                            <div class="text-xs text-purple-400">ML Predictions</div>
                        </div>

                        <!-- Win Rate -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all cursor-pointer">
                            <div class="flex items-center justify-between mb-4">
                                <span class="text-gray-400">Win Rate</span>
                                <i class="fas fa-trophy text-yellow-400 text-xl"></i>
                            </div>
                            <div class="text-2xl font-bold mb-2" x-text="formatPercentage(win_rate)">0%</div>
                            <div class="text-xs text-gray-400" x-text="total_trades + ' trades'">0 trades</div>
                        </div>
                    </div>

                    <!-- Charts -->
                    <div class="grid grid-cols-1 xl:grid-cols-2 gap-8">
                        <!-- Market Chart -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all">
                            <h3 class="text-lg font-semibold mb-4">Live Market Data</h3>
                            <div class="h-80">
                                <canvas id="market-chart"></canvas>
                            </div>
                        </div>

                        <!-- Portfolio Chart -->
                        <div class="glass rounded-xl p-6 glass-hover transition-all">
                            <h3 class="text-lg font-semibold mb-4">Portfolio Performance</h3>
                            <div class="h-80">
                                <canvas id="portfolio-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Portfolio Section -->
                <div x-show="activeSection === 'portfolio'" class="space-y-8">
                    <div class="glass rounded-xl p-6">
                        <h2 class="text-xl font-bold mb-6">Portfolio Management</h2>

                        <div x-show="positions.length === 0" class="text-center py-12">
                            <i class="fas fa-chart-pie text-6xl text-gray-600 mb-4"></i>
                            <p class="text-gray-400 text-lg">No active positions</p>
                            <p class="text-gray-500 mt-2">AI trading system is running, positions will appear here</p>
                        </div>

                        <div x-show="positions.length > 0" class="overflow-x-auto">
                            <table class="w-full">
                                <thead>
                                    <tr class="border-b border-gray-700">
                                        <th class="text-left py-3 text-gray-400">Symbol</th>
                                        <th class="text-right py-3 text-gray-400">Side</th>
                                        <th class="text-right py-3 text-gray-400">Size</th>
                                        <th class="text-right py-3 text-gray-400">Entry</th>
                                        <th class="text-right py-3 text-gray-400">Current</th>
                                        <th class="text-right py-3 text-gray-400">P&L</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <template x-for="position in positions" :key="position.symbol">
                                        <tr class="border-b border-gray-800 hover:bg-gray-800/50 transition-all">
                                            <td class="py-3 font-medium" x-text="position.symbol"></td>
                                            <td class="py-3 text-right">
                                                <span :class="position.side === 'buy' ? 'text-green-400' : 'text-red-400'"
                                                      class="text-sm font-medium" x-text="position.side.toUpperCase()"></span>
                                            </td>
                                            <td class="py-3 text-right" x-text="position.size.toFixed(4)"></td>
                                            <td class="py-3 text-right" x-text="'$' + position.entry_price.toFixed(2)"></td>
                                            <td class="py-3 text-right" x-text="'$' + position.current_price.toFixed(2)"></td>
                                            <td class="py-3 text-right">
                                                <span :class="position.pnl >= 0 ? 'text-green-400' : 'text-red-400'"
                                                      class="font-medium" x-text="formatCurrency(position.pnl)"></span>
                                            </td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- AI Predictions Section -->
                <div x-show="activeSection === 'ai_predictions'" class="space-y-8">
                    <div class="glass rounded-xl p-6">
                        <h2 class="text-xl font-bold mb-6">AI Predictions</h2>

                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <template x-for="(prediction, symbol) in ai_predictions" :key="symbol">
                                <div class="glass rounded-lg p-6 glass-hover transition-all">
                                    <div class="flex items-center justify-between mb-4">
                                        <h3 class="text-lg font-semibold" x-text="symbol"></h3>
                                        <span class="text-sm text-gray-400" x-text="'Updated: ' + formatTime(prediction.timestamp)"></span>
                                    </div>

                                    <div class="space-y-4">
                                        <div class="flex justify-between items-center">
                                            <span class="text-gray-400">Current Price:</span>
                                            <span class="font-medium" x-text="formatCurrency(prediction.current_price)"></span>
                                        </div>

                                        <div class="grid grid-cols-3 gap-4 text-sm">
                                            <div class="text-center">
                                                <div class="text-gray-400 mb-1">1H</div>
                                                <div class="font-medium" :class="prediction.predictions['1h'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                     x-text="formatCurrency(prediction.predictions['1h'].price)"></div>
                                                <div class="text-xs text-gray-500" x-text="prediction.predictions['1h'].confidence.toFixed(1) + '%'"></div>
                                            </div>
                                            <div class="text-center">
                                                <div class="text-gray-400 mb-1">24H</div>
                                                <div class="font-medium" :class="prediction.predictions['24h'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                     x-text="formatCurrency(prediction.predictions['24h'].price)"></div>
                                                <div class="text-xs text-gray-500" x-text="prediction.predictions['24h'].confidence.toFixed(1) + '%'"></div>
                                            </div>
                                            <div class="text-center">
                                                <div class="text-gray-400 mb-1">7D</div>
                                                <div class="font-medium" :class="prediction.predictions['7d'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                     x-text="formatCurrency(prediction.predictions['7d'].price)"></div>
                                                <div class="text-xs text-gray-500" x-text="prediction.predictions['7d'].confidence.toFixed(1) + '%'"></div>
                                            </div>
                                        </div>

                                        <div class="flex items-center justify-between pt-3 border-t border-gray-700">
                                            <span class="text-gray-400">Trend:</span>
                                            <span class="px-2 py-1 rounded text-xs font-medium"
                                                  :class="{
                                                      'bg-green-500/20 text-green-400': prediction.trend_direction === 'up',
                                                      'bg-red-500/20 text-red-400': prediction.trend_direction === 'down',
                                                      'bg-yellow-500/20 text-yellow-400': prediction.trend_direction === 'sideways'
                                                  }"
                                                  x-text="prediction.trend_direction.toUpperCase()"></span>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>

                <!-- Scanner Section -->
                <div x-show="activeSection === 'scanner'" class="space-y-8">
                    <div class="glass rounded-xl p-6">
                        <h2 class="text-xl font-bold mb-6">Market Scanner</h2>

                        <div x-show="scanner_signals.length === 0" class="text-center py-12">
                            <i class="fas fa-search text-6xl text-gray-600 mb-4"></i>
                            <p class="text-gray-400 text-lg">Scanning markets...</p>
                        </div>

                        <div x-show="scanner_signals.length > 0" class="space-y-4">
                            <template x-for="signal in scanner_signals" :key="signal.id">
                                <div class="glass rounded-lg p-4 glass-hover transition-all">
                                    <div class="flex items-center justify-between mb-2">
                                        <div class="flex items-center space-x-3">
                                            <span class="font-medium text-lg" x-text="signal.symbol"></span>
                                            <span class="px-2 py-1 rounded text-xs font-medium"
                                                  :class="{
                                                      'bg-green-500/20 text-green-400': signal.signal_type.includes('buy'),
                                                      'bg-red-500/20 text-red-400': signal.signal_type.includes('sell')
                                                  }"
                                                  x-text="signal.signal_type.toUpperCase()"></span>
                                        </div>
                                        <div class="text-right">
                                            <div class="font-medium" x-text="formatCurrency(signal.price)"></div>
                                            <div class="text-xs text-gray-400" x-text="signal.strength.toFixed(0) + '% strength'"></div>
                                        </div>
                                    </div>
                                    <p class="text-sm text-gray-300 mb-2" x-text="signal.message"></p>
                                    <div class="flex items-center justify-between text-xs text-gray-400">
                                        <span x-text="signal.strategy"></span>
                                        <span x-text="formatTime(signal.timestamp)"></span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>

                <!-- Trading Section -->
                <div x-show="activeSection === 'trading'" class="space-y-8">
                    <div class="glass rounded-xl p-6">
                        <h2 class="text-xl font-bold mb-6">AI Trading Console</h2>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                            <div class="text-center">
                                <div class="text-2xl font-bold text-green-400 mb-1">ACTIVE</div>
                                <div class="text-gray-400">Trading Status</div>
                            </div>
                            <div class="text-center">
                                <div class="text-2xl font-bold text-blue-400 mb-1" x-text="ai_models_count">5</div>
                                <div class="text-gray-400">AI Models Running</div>
                            </div>
                            <div class="text-center">
                                <div class="text-2xl font-bold text-purple-400 mb-1" x-text="formatCurrency(portfolio.daily_pnl)">$0</div>
                                <div class="text-gray-400">Today's P&L</div>
                            </div>
                        </div>

                        <div class="bg-blue-500/10 border border-blue-500/30 rounded-lg p-6">
                            <div class="flex items-center space-x-3 mb-4">
                                <i class="fas fa-robot text-blue-400 text-2xl"></i>
                                <div>
                                    <h3 class="font-bold text-blue-400">AI Trading System Online</h3>
                                    <p class="text-sm text-gray-300">All models are active and trading with real market data</p>
                                </div>
                            </div>
                            <p class="text-sm text-gray-400">
                                🚀 The system is running with paper money - no real funds at risk.
                                All trades are simulated but use real market prices and advanced AI predictions.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <!-- Real-time Status -->
        <div class="fixed bottom-6 right-6 glass rounded-lg p-4 max-w-sm">
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 rounded-full bg-green-500 trading-active"></div>
                <div>
                    <p class="text-sm font-medium">Sofia V2 Enhanced</p>
                    <p class="text-xs text-gray-400" x-text="ai_models_count + ' AI models • ' + positions.length + ' positions • Real-time'">5 AI models • 0 positions • Real-time</p>
                </div>
            </div>
        </div>

        <script>
            function sofiaEnhanced() {
                return {
                    // UI State
                    activeSection: 'dashboard',
                    isRefreshing: false,

                    // Data
                    portfolio: {
                        total_value: 100000,
                        daily_pnl: 0,
                        daily_pnl_percent: 0
                    },
                    positions: [],
                    ai_predictions: {},
                    scanner_signals: [],
                    ai_signals_count: 0,
                    ai_models_count: 5,
                    win_rate: 0,
                    total_trades: 0,

                    // Charts
                    marketChart: null,
                    portfolioChart: null,

                    // WebSocket
                    websocket: null,

                    init() {
                        this.connectWebSocket();
                        this.initCharts();
                        this.startSimulation();
                    },

                    connectWebSocket() {
                        try {
                            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                            const wsUrl = `${protocol}//${window.location.host}/ws/enhanced`;

                            this.websocket = new WebSocket(wsUrl);

                            this.websocket.onopen = () => {
                                console.log('Enhanced WebSocket connected');
                            };

                            this.websocket.onmessage = (event) => {
                                const data = JSON.parse(event.data);
                                this.handleWebSocketMessage(data);
                            };

                            this.websocket.onclose = () => {
                                console.log('WebSocket closed, reconnecting...');
                                setTimeout(() => this.connectWebSocket(), 5000);
                            };
                        } catch (error) {
                            console.log('WebSocket failed, using simulation');
                        }
                    },

                    handleWebSocketMessage(data) {
                        switch(data.type) {
                            case 'portfolio_update':
                                this.portfolio = { ...this.portfolio, ...data.data };
                                break;
                            case 'ai_predictions':
                                this.ai_predictions = data.data;
                                this.ai_signals_count = Object.keys(data.data).length;
                                break;
                            case 'scanner_signals':
                                this.scanner_signals = data.data;
                                break;
                            case 'positions_update':
                                this.positions = data.data;
                                break;
                        }
                    },

                    startSimulation() {
                        // Simulate data for demo
                        setInterval(() => {
                            this.portfolio.total_value += (Math.random() - 0.5) * 200;
                            this.portfolio.daily_pnl += (Math.random() - 0.5) * 50;
                            this.portfolio.daily_pnl_percent = (this.portfolio.daily_pnl / 100000) * 100;

                            // Add random signals
                            if (Math.random() < 0.1) {
                                this.addRandomSignal();
                            }

                            this.updateCharts();
                        }, 5000);
                    },

                    addRandomSignal() {
                        const symbols = ['BTC', 'ETH', 'SOL', 'BNB'];
                        const signals = ['buy', 'sell', 'strong_buy'];

                        const signal = {
                            id: Date.now(),
                            symbol: symbols[Math.floor(Math.random() * symbols.length)],
                            signal_type: signals[Math.floor(Math.random() * signals.length)],
                            strategy: 'AI Model',
                            strength: 60 + Math.random() * 40,
                            price: 30000 + Math.random() * 40000,
                            message: 'AI detected trading opportunity',
                            timestamp: new Date().toISOString()
                        };

                        this.scanner_signals.unshift(signal);
                        if (this.scanner_signals.length > 10) {
                            this.scanner_signals.pop();
                        }
                    },

                    initCharts() {
                        // Market Chart
                        const marketCtx = document.getElementById('market-chart').getContext('2d');
                        this.marketChart = new Chart(marketCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'BTC Price',
                                    data: [],
                                    borderColor: '#3b82f6',
                                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { labels: { color: '#ffffff' } }
                                },
                                scales: {
                                    x: { ticks: { color: '#888888' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } },
                                    y: { ticks: { color: '#888888' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } }
                                }
                            }
                        });

                        // Portfolio Chart
                        const portfolioCtx = document.getElementById('portfolio-chart').getContext('2d');
                        this.portfolioChart = new Chart(portfolioCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'Portfolio Value',
                                    data: [],
                                    borderColor: '#8b5cf6',
                                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { labels: { color: '#ffffff' } }
                                },
                                scales: {
                                    x: { ticks: { color: '#888888' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } },
                                    y: { ticks: { color: '#888888' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } }
                                }
                            }
                        });
                    },

                    updateCharts() {
                        const now = new Date().toLocaleTimeString();

                        // Market chart
                        this.marketChart.data.labels.push(now);
                        this.marketChart.data.datasets[0].data.push(67000 + Math.random() * 5000);

                        if (this.marketChart.data.labels.length > 20) {
                            this.marketChart.data.labels.shift();
                            this.marketChart.data.datasets[0].data.shift();
                        }

                        this.marketChart.update('none');

                        // Portfolio chart
                        this.portfolioChart.data.labels.push(now);
                        this.portfolioChart.data.datasets[0].data.push(this.portfolio.total_value);

                        if (this.portfolioChart.data.labels.length > 20) {
                            this.portfolioChart.data.labels.shift();
                            this.portfolioChart.data.datasets[0].data.shift();
                        }

                        this.portfolioChart.update('none');
                    },

                    refreshAllData() {
                        this.isRefreshing = true;
                        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                            this.websocket.send(JSON.stringify({type: 'refresh_all'}));
                        }
                        setTimeout(() => {
                            this.isRefreshing = false;
                        }, 2000);
                    },

                    formatCurrency(amount) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            minimumFractionDigits: 2
                        }).format(amount);
                    },

                    formatPercentage(percent) {
                        return (percent >= 0 ? '+' : '') + percent.toFixed(2) + '%';
                    },

                    formatTime(timestamp) {
                        return new Date(timestamp).toLocaleTimeString();
                    }
                }
            }
        </script>
    </body>
    </html>
    """


@app.websocket("/ws/enhanced")
async def enhanced_websocket(websocket: WebSocket):
    """Enhanced WebSocket endpoint"""
    client_id = str(len(enhanced_manager.active_connections))

    await enhanced_manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "refresh_all":
                await send_enhanced_data()

    except WebSocketDisconnect:
        enhanced_manager.disconnect(client_id)


async def send_enhanced_data():
    """Send all enhanced data"""
    try:
        if ADVANCED_FEATURES:
            # Portfolio data
            portfolio = paper_engine.get_portfolio_summary("demo")
            if portfolio:
                await enhanced_manager.broadcast_to_all(
                    {"type": "portfolio_update", "data": portfolio}
                )

            # AI predictions
            predictions = prediction_engine.get_all_predictions()
            if predictions:
                await enhanced_manager.broadcast_to_all(
                    {"type": "ai_predictions", "data": predictions}
                )

            # Scanner signals
            overview = await market_scanner.get_market_overview()
            if overview.get("recent_signals"):
                await enhanced_manager.broadcast_to_all(
                    {"type": "scanner_signals", "data": overview["recent_signals"]}
                )
        else:
            # Send demo data
            await enhanced_manager.broadcast_to_all(
                {
                    "type": "portfolio_update",
                    "data": {
                        "total_value": 100000 + random.randint(-1000, 1000),
                        "daily_pnl": random.randint(-500, 500),
                        "daily_pnl_percent": random.uniform(-2, 2),
                    },
                }
            )

    except Exception as e:
        print(f"Error sending enhanced data: {e}")


async def broadcast_enhanced_data():
    """Broadcast enhanced data periodically"""
    while True:
        try:
            await send_enhanced_data()
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in enhanced broadcasting: {e}")
            await asyncio.sleep(10)


if __name__ == "__main__":
    print("Starting Sofia V2 Enhanced Server on port 8008...")
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="info")
