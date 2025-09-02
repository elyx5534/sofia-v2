"""
Sofia V2 Ultimate Dashboard - Purple Template with Advanced Features
Combines the beautiful purple UI with all new AI/Trading capabilities
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.data.real_time_fetcher import fetcher
from src.ml.real_time_predictor import prediction_engine
from src.scanner.advanced_market_scanner import market_scanner
from src.trading.paper_trading_engine import paper_engine
from src.trading.unified_execution_engine import execution_engine

logger = logging.getLogger(__name__)

app = FastAPI(title="Sofia V2 Ultimate Dashboard", version="2.0.0")
templates = Jinja2Templates(directory="src/web_ui/templates")
app.mount("/static", StaticFiles(directory="src/web_ui/static"), name="static")


class UltimateConnectionManager:
    """Enhanced WebSocket manager for ultimate dashboard"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_data: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str = "demo"):
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # Initialize user data
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "portfolio": {"total_value": 100000, "daily_pnl": 0, "daily_pnl_percent": 0},
                "positions": [],
                "recent_trades": [],
                "ai_predictions": {},
                "scanner_signals": [],
                "market_data": {},
            }

        logger.info(f"Ultimate client {client_id} connected for user {user_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        logger.info(f"Ultimate client {client_id} disconnected")

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


ultimate_manager = UltimateConnectionManager()


@app.on_event("startup")
async def startup_ultimate():
    """Start all Sofia V2 engines for ultimate dashboard"""
    logger.info("Starting Sofia V2 Ultimate Dashboard...")

    # Start all engines
    await execution_engine.start()

    # Start enhanced data broadcasting
    asyncio.create_task(broadcast_ultimate_data())

    logger.info("Sofia V2 Ultimate Dashboard fully operational! 🚀")


@app.on_event("shutdown")
async def shutdown_ultimate():
    """Cleanup on shutdown"""
    await execution_engine.stop()
    logger.info("Sofia V2 Ultimate Dashboard shutdown complete")


@app.get("/", response_class=HTMLResponse)
async def ultimate_dashboard():
    """Ultimate Sofia V2 dashboard with purple template"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sofia V2 Ultimate - AI Trading Platform</title>

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
                            warning: '#f59e0b',
                        },
                        animation: {
                            'float': 'float 6s ease-in-out infinite',
                            'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                            'trade-flash': 'tradeFlash 2s ease-in-out',
                            'glow': 'glow 2s ease-in-out infinite alternate',
                            'particles': 'particles 20s linear infinite',
                        }
                    }
                }
            }
        </script>

        <!-- Chart.js -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
        <!-- Alpine.js -->
        <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
        <!-- Font Awesome -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

        <style>
            @keyframes float {
                0%, 100% { transform: translateY(0px) rotate(0deg); }
                50% { transform: translateY(-20px) rotate(180deg); }
            }

            @keyframes tradeFlash {
                0% { background-color: rgba(16, 185, 129, 0.2); }
                50% { background-color: rgba(16, 185, 129, 0.5); }
                100% { background-color: transparent; }
            }

            @keyframes glow {
                from { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
                to { box-shadow: 0 0 30px rgba(139, 92, 246, 0.6); }
            }

            @keyframes particles {
                0% { transform: translateY(100vh) rotate(0deg); opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { transform: translateY(-100vh) rotate(720deg); opacity: 0; }
            }

            .glass {
                background: rgba(15, 23, 42, 0.4);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(139, 92, 246, 0.2);
            }

            .glass-hover:hover {
                background: rgba(15, 23, 42, 0.6);
                border-color: rgba(139, 92, 246, 0.4);
                transform: translateY(-4px) scale(1.02);
                box-shadow: 0 20px 40px rgba(139, 92, 246, 0.2);
            }

            .gradient-border {
                position: relative;
                background: linear-gradient(135deg, #1e293b, #0f172a);
                border-radius: 16px;
                overflow: hidden;
            }

            .gradient-border::before {
                content: '';
                position: absolute;
                inset: 0;
                border-radius: 16px;
                padding: 2px;
                background: linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899);
                -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                -webkit-mask-composite: xor;
                mask-composite: exclude;
                opacity: 0.6;
                animation: glow 3s ease-in-out infinite alternate;
            }

            .particle {
                position: absolute;
                width: 4px;
                height: 4px;
                background: rgba(139, 92, 246, 0.6);
                border-radius: 50%;
                pointer-events: none;
                animation: particles 20s linear infinite;
            }

            .ai-glow {
                position: relative;
                overflow: hidden;
            }

            .ai-glow::after {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: conic-gradient(transparent, rgba(139, 92, 246, 0.3), transparent);
                animation: spin 4s linear infinite;
            }

            .ai-glow .content {
                position: relative;
                z-index: 1;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .trading-active {
                animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            }

            .signal-alert {
                position: fixed;
                top: 100px;
                right: 20px;
                background: linear-gradient(135deg, #8b5cf6, #ec4899);
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 20px 40px rgba(139, 92, 246, 0.4);
                transform: translateX(400px);
                opacity: 0;
                transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 1000;
                max-width: 320px;
            }

            .signal-alert.show {
                transform: translateX(0);
                opacity: 1;
            }

            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }

            ::-webkit-scrollbar-track {
                background: rgba(15, 23, 42, 0.5);
            }

            ::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                border-radius: 4px;
            }
        </style>
    </head>

    <body class="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-purple-950"
          x-data="sofiaUltimate()" x-init="init()">

        <!-- Animated background particles -->
        <div class="fixed inset-0 overflow-hidden pointer-events-none">
            <div class="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse-slow"></div>
            <div class="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse-slow" style="animation-delay: 2s;"></div>
            <div class="absolute top-1/2 left-1/2 w-64 h-64 bg-pink-500/10 rounded-full blur-3xl animate-pulse-slow" style="animation-delay: 4s;"></div>

            <!-- Floating particles -->
            <div class="particle" style="left: 10%; animation-delay: 0s;"></div>
            <div class="particle" style="left: 20%; animation-delay: 2s;"></div>
            <div class="particle" style="left: 30%; animation-delay: 4s;"></div>
            <div class="particle" style="left: 40%; animation-delay: 6s;"></div>
            <div class="particle" style="left: 50%; animation-delay: 8s;"></div>
            <div class="particle" style="left: 60%; animation-delay: 10s;"></div>
            <div class="particle" style="left: 70%; animation-delay: 12s;"></div>
            <div class="particle" style="left: 80%; animation-delay: 14s;"></div>
            <div class="particle" style="left: 90%; animation-delay: 16s;"></div>
        </div>

        <div class="relative flex h-screen">
            <!-- Sidebar -->
            <aside class="fixed lg:relative w-64 h-full glass border-r border-slate-800 z-50 transform transition-all duration-500 lg:translate-x-0"
                   :class="{'translate-x-0': sidebarOpen, '-translate-x-full': !sidebarOpen}">
                <div class="p-6 border-b border-slate-800">
                    <div class="flex items-center space-x-3">
                        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-lg animate-glow">
                            <i class="fas fa-robot text-white text-lg"></i>
                        </div>
                        <div>
                            <h1 class="text-xl font-bold text-white">Sofia V2 Ultimate</h1>
                            <p class="text-xs text-slate-400">AI Trading Platform</p>
                        </div>
                    </div>
                </div>

                <nav class="p-4 space-y-2">
                    <a href="#" @click="activeTab = 'dashboard'" :class="activeTab === 'dashboard' ? 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 border border-purple-500/40 text-purple-400' : 'text-slate-400 hover:bg-slate-800/50'"
                       class="flex items-center px-4 py-3 rounded-lg transition-all">
                        <i class="fas fa-th-large w-5"></i>
                        <span class="ml-3">Dashboard</span>
                        <span x-show="activeTab === 'dashboard'" class="ml-auto w-2 h-2 bg-purple-400 rounded-full animate-pulse"></span>
                    </a>
                    <a href="#" @click="activeTab = 'portfolio'" :class="activeTab === 'portfolio' ? 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 border border-purple-500/40 text-purple-400' : 'text-slate-400 hover:bg-slate-800/50'"
                       class="flex items-center px-4 py-3 rounded-lg transition-all">
                        <i class="fas fa-briefcase w-5"></i>
                        <span class="ml-3">Portfolio</span>
                        <span x-show="activeTab === 'portfolio'" class="ml-auto w-2 h-2 bg-purple-400 rounded-full animate-pulse"></span>
                    </a>
                    <a href="#" @click="activeTab = 'ai_predictions'" :class="activeTab === 'ai_predictions' ? 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 border border-purple-500/40 text-purple-400' : 'text-slate-400 hover:bg-slate-800/50'"
                       class="flex items-center px-4 py-3 rounded-lg transition-all">
                        <i class="fas fa-brain w-5"></i>
                        <span class="ml-3">AI Predictions</span>
                        <span x-show="activeTab === 'ai_predictions'" class="ml-auto w-2 h-2 bg-purple-400 rounded-full animate-pulse"></span>
                    </a>
                    <a href="#" @click="activeTab = 'market_scanner'" :class="activeTab === 'market_scanner' ? 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 border border-purple-500/40 text-purple-400' : 'text-slate-400 hover:bg-slate-800/50'"
                       class="flex items-center px-4 py-3 rounded-lg transition-all">
                        <i class="fas fa-radar-dish w-5"></i>
                        <span class="ml-3">Market Scanner</span>
                        <span x-show="activeTab === 'market_scanner'" class="ml-auto w-2 h-2 bg-purple-400 rounded-full animate-pulse"></span>
                    </a>
                    <a href="#" @click="activeTab = 'trading'" :class="activeTab === 'trading' ? 'bg-gradient-to-r from-purple-600/30 to-pink-600/30 border border-purple-500/40 text-purple-400' : 'text-slate-400 hover:bg-slate-800/50'"
                       class="flex items-center px-4 py-3 rounded-lg transition-all">
                        <i class="fas fa-chart-line w-5"></i>
                        <span class="ml-3">Trading</span>
                        <span x-show="activeTab === 'trading'" class="ml-auto w-2 h-2 bg-purple-400 rounded-full animate-pulse"></span>
                    </a>
                </nav>
            </aside>

            <!-- Main Content -->
            <div class="flex-1 flex flex-col lg:ml-0">
                <!-- Header -->
                <header class="glass border-b border-slate-800 px-6 py-4">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-4">
                            <button @click="sidebarOpen = !sidebarOpen" class="text-slate-400 hover:text-white lg:hidden">
                                <i class="fas fa-bars"></i>
                            </button>
                            <h2 class="text-xl font-semibold text-white" x-text="getTabTitle()">Sofia V2 Ultimate</h2>
                            <div class="hidden sm:flex items-center space-x-2">
                                <div class="w-2 h-2 rounded-full bg-green-500 trading-active"></div>
                                <span class="text-xs text-green-400">Trading Active</span>
                                <span class="text-xs text-slate-500">•</span>
                                <span class="text-xs text-purple-400" x-text="'AI Models: ' + ai_models_active + '/5'">AI Models: 5/5</span>
                            </div>
                        </div>
                        <div class="flex items-center space-x-4">
                            <div class="text-sm text-slate-400">
                                <span x-text="'Last Update: ' + last_update">Last Update: --:--</span>
                            </div>
                            <button @click="refreshData()" class="text-slate-400 hover:text-white transition-colors">
                                <i class="fas fa-sync-alt" :class="{'animate-spin': isRefreshing}"></i>
                            </button>
                        </div>
                    </div>
                </header>

                <!-- Tab Content -->
                <div class="flex-1 p-6 overflow-y-auto">

                    <!-- Dashboard Tab -->
                    <div x-show="activeTab === 'dashboard'" class="space-y-6">
                        <!-- Real-time Stats Cards -->
                        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                            <!-- Portfolio Value -->
                            <div class="gradient-border glass-hover transition-all cursor-pointer">
                                <div class="content p-6">
                                    <div class="flex items-center justify-between mb-3">
                                        <span class="text-sm text-slate-400">Portfolio Value</span>
                                        <i class="fas fa-wallet text-purple-400 text-lg"></i>
                                    </div>
                                    <div class="text-2xl font-bold text-white mb-2" x-text="formatCurrency(portfolio.total_value)">$100,000</div>
                                    <div class="flex items-center space-x-2">
                                        <span class="text-sm font-medium" :class="portfolio.daily_pnl_percent >= 0 ? 'text-green-400' : 'text-red-400'"
                                              x-text="formatPercentage(portfolio.daily_pnl_percent)">+0.00%</span>
                                        <span class="text-xs text-slate-500">today</span>
                                    </div>
                                </div>
                            </div>

                            <!-- Active Trades -->
                            <div class="gradient-border glass-hover transition-all cursor-pointer">
                                <div class="content p-6">
                                    <div class="flex items-center justify-between mb-3">
                                        <span class="text-sm text-slate-400">Active Trades</span>
                                        <i class="fas fa-chart-line text-blue-400 text-lg"></i>
                                    </div>
                                    <div class="text-2xl font-bold text-white mb-2" x-text="positions.length">0</div>
                                    <div class="text-xs text-slate-400">Live positions</div>
                                </div>
                            </div>

                            <!-- AI Predictions -->
                            <div class="gradient-border glass-hover transition-all cursor-pointer ai-glow">
                                <div class="content p-6">
                                    <div class="flex items-center justify-between mb-3">
                                        <span class="text-sm text-slate-400">AI Signals</span>
                                        <i class="fas fa-brain text-pink-400 text-lg"></i>
                                    </div>
                                    <div class="text-2xl font-bold text-white mb-2" x-text="ai_signals_count">0</div>
                                    <div class="text-xs text-pink-400">ML Predictions</div>
                                </div>
                            </div>

                            <!-- Win Rate -->
                            <div class="gradient-border glass-hover transition-all cursor-pointer">
                                <div class="content p-6">
                                    <div class="flex items-center justify-between mb-3">
                                        <span class="text-sm text-slate-400">Win Rate</span>
                                        <i class="fas fa-trophy text-yellow-400 text-lg"></i>
                                    </div>
                                    <div class="text-2xl font-bold text-white mb-2" x-text="formatPercentage(win_rate)">0%</div>
                                    <div class="text-xs text-slate-400" x-text="total_trades + ' trades'">0 trades</div>
                                </div>
                            </div>
                        </div>

                        <!-- Live Charts -->
                        <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
                            <!-- Market Chart -->
                            <div class="gradient-border glass-hover transition-all">
                                <div class="content p-6">
                                    <h3 class="text-lg font-semibold text-white mb-4">Live Market Data</h3>
                                    <div class="h-80">
                                        <canvas id="market-chart"></canvas>
                                    </div>
                                </div>
                            </div>

                            <!-- Portfolio Performance -->
                            <div class="gradient-border glass-hover transition-all">
                                <div class="content p-6">
                                    <h3 class="text-lg font-semibold text-white mb-4">Portfolio Performance</h3>
                                    <div class="h-80">
                                        <canvas id="portfolio-chart"></canvas>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Portfolio Tab -->
                    <div x-show="activeTab === 'portfolio'" class="space-y-6">
                        <div class="gradient-border glass-hover transition-all">
                            <div class="content p-6">
                                <h3 class="text-lg font-semibold text-white mb-4">Current Positions</h3>
                                <div x-show="positions.length === 0" class="text-center py-12">
                                    <i class="fas fa-chart-pie text-6xl text-slate-600 mb-4"></i>
                                    <p class="text-slate-400 text-lg mb-2">No active positions</p>
                                    <p class="text-slate-500">AI trading system is running, positions will appear here</p>
                                </div>

                                <div x-show="positions.length > 0" class="overflow-x-auto">
                                    <table class="w-full">
                                        <thead>
                                            <tr class="border-b border-slate-700">
                                                <th class="text-left py-3 text-sm text-slate-400">Symbol</th>
                                                <th class="text-right py-3 text-sm text-slate-400">Side</th>
                                                <th class="text-right py-3 text-sm text-slate-400">Size</th>
                                                <th class="text-right py-3 text-sm text-slate-400">Entry</th>
                                                <th class="text-right py-3 text-sm text-slate-400">Current</th>
                                                <th class="text-right py-3 text-sm text-slate-400">P&L</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <template x-for="position in positions" :key="position.symbol">
                                                <tr class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-all">
                                                    <td class="py-3 font-medium text-white" x-text="position.symbol"></td>
                                                    <td class="py-3 text-right">
                                                        <span :class="position.side === 'buy' ? 'text-green-400' : 'text-red-400'"
                                                              class="text-sm font-medium" x-text="position.side.toUpperCase()"></span>
                                                    </td>
                                                    <td class="py-3 text-right text-white" x-text="position.size.toFixed(4)"></td>
                                                    <td class="py-3 text-right text-white" x-text="'$' + position.entry_price.toFixed(2)"></td>
                                                    <td class="py-3 text-right text-white" x-text="'$' + position.current_price.toFixed(2)"></td>
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

                        <!-- Recent Trades -->
                        <div class="gradient-border glass-hover transition-all">
                            <div class="content p-6">
                                <h3 class="text-lg font-semibold text-white mb-4">Recent Trades</h3>
                                <div x-show="recent_trades.length === 0" class="text-center py-8">
                                    <i class="fas fa-exchange-alt text-4xl text-slate-600 mb-3"></i>
                                    <p class="text-slate-400">No trades yet</p>
                                </div>

                                <div x-show="recent_trades.length > 0" class="space-y-3">
                                    <template x-for="(trade, index) in recent_trades.slice(0, 10)" :key="index">
                                        <div class="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg hover:bg-slate-800/50 transition-all">
                                            <div class="flex items-center space-x-3">
                                                <div class="w-8 h-8 rounded-full flex items-center justify-center"
                                                     :class="trade.side === 'buy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'">
                                                    <i :class="trade.side === 'buy' ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
                                                </div>
                                                <div>
                                                    <p class="font-medium text-white" x-text="trade.symbol"></p>
                                                    <p class="text-xs text-slate-400" x-text="trade.time"></p>
                                                </div>
                                            </div>
                                            <div class="text-right">
                                                <p class="font-medium" :class="trade.side === 'buy' ? 'text-green-400' : 'text-red-400'"
                                                   x-text="trade.side.toUpperCase()"></p>
                                                <p class="text-xs text-slate-400" x-text="trade.size + ' @ $' + trade.price"></p>
                                            </div>
                                        </div>
                                    </template>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- AI Predictions Tab -->
                    <div x-show="activeTab === 'ai_predictions'" class="space-y-6">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <template x-for="(prediction, symbol) in ai_predictions" :key="symbol">
                                <div class="gradient-border glass-hover transition-all ai-glow">
                                    <div class="content p-6">
                                        <div class="flex items-center justify-between mb-4">
                                            <h3 class="text-lg font-semibold text-white" x-text="symbol"></h3>
                                            <span class="text-sm text-slate-400" x-text="'Updated: ' + formatTime(prediction.timestamp)"></span>
                                        </div>

                                        <div class="space-y-4">
                                            <div class="flex justify-between items-center">
                                                <span class="text-slate-400">Current Price:</span>
                                                <span class="text-white font-medium" x-text="formatCurrency(prediction.current_price)"></span>
                                            </div>

                                            <div class="grid grid-cols-3 gap-4 text-sm">
                                                <div class="text-center">
                                                    <div class="text-slate-400 mb-1">1H</div>
                                                    <div class="font-medium" :class="prediction.predictions['1h'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                         x-text="formatCurrency(prediction.predictions['1h'].price)"></div>
                                                    <div class="text-xs text-slate-500" x-text="prediction.predictions['1h'].confidence.toFixed(1) + '%'"></div>
                                                </div>
                                                <div class="text-center">
                                                    <div class="text-slate-400 mb-1">24H</div>
                                                    <div class="font-medium" :class="prediction.predictions['24h'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                         x-text="formatCurrency(prediction.predictions['24h'].price)"></div>
                                                    <div class="text-xs text-slate-500" x-text="prediction.predictions['24h'].confidence.toFixed(1) + '%'"></div>
                                                </div>
                                                <div class="text-center">
                                                    <div class="text-slate-400 mb-1">7D</div>
                                                    <div class="font-medium" :class="prediction.predictions['7d'].price > prediction.current_price ? 'text-green-400' : 'text-red-400'"
                                                         x-text="formatCurrency(prediction.predictions['7d'].price)"></div>
                                                    <div class="text-xs text-slate-500" x-text="prediction.predictions['7d'].confidence.toFixed(1) + '%'"></div>
                                                </div>
                                            </div>

                                            <div class="flex items-center justify-between pt-3 border-t border-slate-700">
                                                <span class="text-slate-400">Trend:</span>
                                                <span class="px-2 py-1 rounded text-xs font-medium"
                                                      :class="{
                                                          'bg-green-500/20 text-green-400': prediction.trend_direction === 'up',
                                                          'bg-red-500/20 text-red-400': prediction.trend_direction === 'down',
                                                          'bg-yellow-500/20 text-yellow-400': prediction.trend_direction === 'sideways'
                                                      }"
                                                      x-text="prediction.trend_direction.toUpperCase()"></span>
                                            </div>

                                            <div class="flex items-center justify-between">
                                                <span class="text-slate-400">Signal Strength:</span>
                                                <div class="flex items-center space-x-2">
                                                    <div class="w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
                                                        <div class="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all"
                                                             :style="'width: ' + prediction.signal_strength + '%'"></div>
                                                    </div>
                                                    <span class="text-xs text-slate-400" x-text="prediction.signal_strength.toFixed(0) + '%'"></span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- Market Scanner Tab -->
                    <div x-show="activeTab === 'market_scanner'" class="space-y-6">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <!-- Top Opportunities -->
                            <div class="gradient-border glass-hover transition-all">
                                <div class="content p-6">
                                    <h3 class="text-lg font-semibold text-white mb-4">🎯 Top Opportunities</h3>
                                    <div x-show="scanner_signals.length === 0" class="text-center py-8">
                                        <i class="fas fa-search text-4xl text-slate-600 mb-3"></i>
                                        <p class="text-slate-400">Scanning markets...</p>
                                    </div>

                                    <div x-show="scanner_signals.length > 0" class="space-y-3">
                                        <template x-for="signal in scanner_signals.slice(0, 5)" :key="signal.id">
                                            <div class="p-4 bg-slate-800/30 rounded-lg hover:bg-slate-800/50 transition-all">
                                                <div class="flex items-center justify-between mb-2">
                                                    <div class="flex items-center space-x-2">
                                                        <span class="font-medium text-white" x-text="signal.symbol"></span>
                                                        <span class="px-2 py-1 rounded text-xs font-medium"
                                                              :class="{
                                                                  'bg-green-500/20 text-green-400': signal.signal_type.includes('buy'),
                                                                  'bg-red-500/20 text-red-400': signal.signal_type.includes('sell'),
                                                                  'bg-yellow-500/20 text-yellow-400': signal.signal_type === 'neutral'
                                                              }"
                                                              x-text="signal.signal_type.toUpperCase()"></span>
                                                    </div>
                                                    <div class="text-right">
                                                        <div class="text-sm text-white" x-text="'$' + signal.price.toFixed(4)"></div>
                                                        <div class="text-xs text-slate-400" x-text="signal.strength.toFixed(0) + '% strength'"></div>
                                                    </div>
                                                </div>
                                                <p class="text-sm text-slate-300" x-text="signal.message"></p>
                                                <div class="flex items-center justify-between mt-2 text-xs text-slate-400">
                                                    <span x-text="signal.strategy"></span>
                                                    <span x-text="formatTime(signal.timestamp)"></span>
                                                </div>
                                            </div>
                                        </template>
                                    </div>
                                </div>
                            </div>

                            <!-- Market Sentiment -->
                            <div class="gradient-border glass-hover transition-all">
                                <div class="content p-6">
                                    <h3 class="text-lg font-semibold text-white mb-4">📊 Market Sentiment</h3>
                                    <div class="space-y-4">
                                        <div class="text-center">
                                            <div class="text-3xl font-bold mb-2"
                                                 :class="{
                                                     'text-green-400': market_sentiment.overall_sentiment > 20,
                                                     'text-red-400': market_sentiment.overall_sentiment < -20,
                                                     'text-yellow-400': Math.abs(market_sentiment.overall_sentiment) <= 20
                                                 }"
                                                 x-text="market_sentiment.sentiment_label || 'Neutral'">Neutral</div>
                                            <div class="text-sm text-slate-400">Overall Market Sentiment</div>
                                        </div>

                                        <div class="grid grid-cols-2 gap-4 text-sm">
                                            <div class="text-center">
                                                <div class="text-xl font-bold text-blue-400" x-text="(market_sentiment.average_volatility * 100).toFixed(1) + '%'">15.0%</div>
                                                <div class="text-slate-400">Avg Volatility</div>
                                            </div>
                                            <div class="text-center">
                                                <div class="text-xl font-bold text-purple-400" x-text="market_sentiment.active_signals || 0">0</div>
                                                <div class="text-slate-400">Active Signals</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Trading Tab -->
                    <div x-show="activeTab === 'trading'" class="space-y-6">
                        <div class="gradient-border glass-hover transition-all">
                            <div class="content p-6">
                                <h3 class="text-lg font-semibold text-white mb-4">🤖 AI Trading Console</h3>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    <div class="text-center">
                                        <div class="text-2xl font-bold text-green-400 mb-1">ACTIVE</div>
                                        <div class="text-sm text-slate-400">Trading Status</div>
                                    </div>
                                    <div class="text-center">
                                        <div class="text-2xl font-bold text-blue-400 mb-1" x-text="ai_models_active">5</div>
                                        <div class="text-sm text-slate-400">AI Models Running</div>
                                    </div>
                                    <div class="text-center">
                                        <div class="text-2xl font-bold text-purple-400 mb-1" x-text="'$' + (portfolio.total_value - 100000).toFixed(0)">$0</div>
                                        <div class="text-sm text-slate-400">Total P&L</div>
                                    </div>
                                </div>

                                <div class="mt-6 p-4 bg-slate-800/30 rounded-lg">
                                    <p class="text-sm text-slate-300 text-center">
                                        🚀 AI trading system is running with real market data. All trades are simulated with paper money.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Signal Alert -->
        <div id="signal-alert" class="signal-alert">
            <div class="flex items-start space-x-3">
                <i class="fas fa-robot text-white text-lg mt-1"></i>
                <div>
                    <div class="font-bold text-white mb-1" id="alert-title">New Trading Signal</div>
                    <div class="text-sm text-white/80" id="alert-message">Signal details...</div>
                </div>
            </div>
        </div>

        <!-- Real-time Status -->
        <div class="fixed bottom-6 right-6 glass rounded-xl p-4 max-w-sm">
            <div class="flex items-center space-x-3">
                <div class="w-3 h-3 rounded-full bg-green-500 trading-active"></div>
                <div>
                    <p class="text-sm font-medium text-white">Sofia V2 Ultimate</p>
                    <p class="text-xs text-slate-400" x-text="'5 AI models • ' + positions.length + ' positions • Real-time'">5 AI models • 0 positions • Real-time</p>
                </div>
            </div>
        </div>

        <script>
            function sofiaUltimate() {
                return {
                    // UI State
                    sidebarOpen: false,
                    activeTab: 'dashboard',
                    isRefreshing: false,
                    last_update: new Date().toLocaleTimeString(),

                    // Data State
                    portfolio: {
                        total_value: 100000,
                        daily_pnl: 0,
                        daily_pnl_percent: 0
                    },
                    positions: [],
                    recent_trades: [],
                    ai_predictions: {},
                    scanner_signals: [],
                    market_data: {},
                    market_sentiment: {
                        overall_sentiment: 0,
                        sentiment_label: 'Neutral',
                        average_volatility: 0.15,
                        active_signals: 0
                    },

                    // Stats
                    ai_models_active: 5,
                    ai_signals_count: 0,
                    win_rate: 0,
                    total_trades: 0,

                    // WebSocket
                    websocket: null,

                    // Charts
                    marketChart: null,
                    portfolioChart: null,

                    init() {
                        this.connectWebSocket();
                        this.initCharts();
                        this.startUpdateLoop();
                    },

                    connectWebSocket() {
                        try {
                            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                            const wsUrl = `${protocol}//${window.location.host}/ws/ultimate`;

                            this.websocket = new WebSocket(wsUrl);

                            this.websocket.onopen = () => {
                                console.log('Sofia Ultimate WebSocket connected');
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
                            console.log('WebSocket failed, using fallback data');
                            this.startSimulation();
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
                            case 'market_data':
                                this.market_data = data.data;
                                this.updateCharts();
                                break;
                            case 'trading_signal':
                                this.showSignalAlert(data.data);
                                break;
                            case 'market_sentiment':
                                this.market_sentiment = data.data;
                                break;
                        }
                        this.last_update = new Date().toLocaleTimeString();
                    },

                    startSimulation() {
                        // Simulate real data for demo
                        setInterval(() => {
                            this.portfolio.total_value += (Math.random() - 0.5) * 200;
                            this.portfolio.daily_pnl += (Math.random() - 0.5) * 50;
                            this.portfolio.daily_pnl_percent = (this.portfolio.daily_pnl / 100000) * 100;

                            if (Math.random() < 0.1) { // 10% chance of new signal
                                this.addRandomSignal();
                            }

                            this.last_update = new Date().toLocaleTimeString();
                        }, 5000);
                    },

                    addRandomSignal() {
                        const symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'ADA'];
                        const signals = ['buy', 'sell', 'strong_buy', 'strong_sell'];
                        const strategies = ['momentum', 'breakout', 'rsi_oversold', 'volume_surge'];

                        const signal = {
                            id: Date.now(),
                            symbol: symbols[Math.floor(Math.random() * symbols.length)],
                            signal_type: signals[Math.floor(Math.random() * signals.length)],
                            strategy: strategies[Math.floor(Math.random() * strategies.length)],
                            strength: Math.random() * 100,
                            price: 30000 + Math.random() * 40000,
                            message: 'AI detected trading opportunity',
                            timestamp: new Date().toISOString()
                        };

                        this.scanner_signals.unshift(signal);
                        if (this.scanner_signals.length > 20) {
                            this.scanner_signals.pop();
                        }

                        this.showSignalAlert(signal);
                    },

                    showSignalAlert(signal) {
                        const alertEl = document.getElementById('signal-alert');
                        const titleEl = document.getElementById('alert-title');
                        const messageEl = document.getElementById('alert-message');

                        titleEl.textContent = `${signal.symbol} ${signal.signal_type.toUpperCase()}`;
                        messageEl.textContent = signal.message;

                        alertEl.classList.add('show');

                        setTimeout(() => {
                            alertEl.classList.remove('show');
                        }, 5000);
                    },

                    initCharts() {
                        // Market Chart
                        const marketCtx = document.getElementById('market-chart').getContext('2d');
                        this.marketChart = new Chart(marketCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'BTC',
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

                        // Portfolio Chart
                        const portfolioCtx = document.getElementById('portfolio-chart').getContext('2d');
                        this.portfolioChart = new Chart(portfolioCtx, {
                            type: 'line',
                            data: {
                                labels: [],
                                datasets: [{
                                    label: 'Portfolio Value',
                                    data: [],
                                    borderColor: '#ec4899',
                                    backgroundColor: 'rgba(236, 72, 153, 0.1)',
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
                    },

                    updateCharts() {
                        const now = new Date().toLocaleTimeString();

                        // Update market chart
                        if (this.market_data.BTC) {
                            this.marketChart.data.labels.push(now);
                            this.marketChart.data.datasets[0].data.push(this.market_data.BTC.price);

                            if (this.marketChart.data.labels.length > 20) {
                                this.marketChart.data.labels.shift();
                                this.marketChart.data.datasets[0].data.shift();
                            }

                            this.marketChart.update('none');
                        }

                        // Update portfolio chart
                        this.portfolioChart.data.labels.push(now);
                        this.portfolioChart.data.datasets[0].data.push(this.portfolio.total_value);

                        if (this.portfolioChart.data.labels.length > 20) {
                            this.portfolioChart.data.labels.shift();
                            this.portfolioChart.data.datasets[0].data.shift();
                        }

                        this.portfolioChart.update('none');
                    },

                    startUpdateLoop() {
                        setInterval(() => {
                            this.updateCharts();
                        }, 10000); // Update charts every 10 seconds
                    },

                    refreshData() {
                        this.isRefreshing = true;
                        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                            this.websocket.send(JSON.stringify({type: 'refresh_all'}));
                        }
                        setTimeout(() => {
                            this.isRefreshing = false;
                        }, 2000);
                    },

                    getTabTitle() {
                        const titles = {
                            dashboard: 'Sofia V2 Ultimate Dashboard',
                            portfolio: 'Portfolio Management',
                            ai_predictions: 'AI Predictions',
                            market_scanner: 'Market Scanner',
                            trading: 'AI Trading Console'
                        };
                        return titles[this.activeTab] || 'Sofia V2 Ultimate';
                    },

                    formatCurrency(amount) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD',
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
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


@app.websocket("/ws/ultimate")
async def ultimate_websocket(websocket: WebSocket):
    """Ultimate WebSocket endpoint"""
    client_id = str(uuid.uuid4())
    user_id = "demo"

    await ultimate_manager.connect(websocket, client_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "refresh_all":
                await send_all_data(user_id)

    except WebSocketDisconnect:
        ultimate_manager.disconnect(client_id)


async def send_all_data(user_id: str):
    """Send all data to user"""
    try:
        # Portfolio data
        portfolio = paper_engine.get_portfolio_summary(user_id)
        if portfolio:
            await ultimate_manager.broadcast_to_all({"type": "portfolio_update", "data": portfolio})

        # AI predictions
        predictions = prediction_engine.get_all_predictions()
        if predictions:
            await ultimate_manager.broadcast_to_all({"type": "ai_predictions", "data": predictions})

        # Market data
        market_data = await fetcher.get_market_data(["bitcoin", "ethereum", "solana"])
        if market_data:
            await ultimate_manager.broadcast_to_all({"type": "market_data", "data": market_data})

        # Scanner signals
        overview = await market_scanner.get_market_overview()
        if overview.get("recent_signals"):
            await ultimate_manager.broadcast_to_all(
                {"type": "scanner_signals", "data": overview["recent_signals"]}
            )

        if overview.get("market_sentiment"):
            await ultimate_manager.broadcast_to_all(
                {"type": "market_sentiment", "data": overview["market_sentiment"]}
            )

    except Exception as e:
        logger.error(f"Error sending all data: {e}")


async def broadcast_ultimate_data():
    """Enhanced data broadcasting for ultimate dashboard"""
    while True:
        try:
            await send_all_data("demo")
            await asyncio.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logger.error(f"Error in ultimate broadcasting: {e}")
            await asyncio.sleep(10)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007, log_level="info")
