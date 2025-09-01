// Sofia Trading Platform - Real-time Dashboard
class TradingDashboard {
    constructor() {
        this.ws = null;
        this.chart = null;
        this.positions = new Map();
        this.marketData = new Map();
        this.tradingActivity = [];
        this.selectedSymbol = 'AAPL';
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.initChart();
        this.startRealTimeUpdates();
        this.updateTime();
        this.loadInitialPositions();
    }
    
    connectWebSocket() {
        // Connect to backend WebSocket for real data
        this.ws = new WebSocket('ws://localhost:8001/ws');
        
        this.ws.onopen = () => {
            console.log('Connected to Sofia Trading Engine');
            this.addTradingActivity('SYSTEM', 'Connected to trading engine', 'info');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            // Fallback to simulation mode
            this.startSimulation();
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected, switching to simulation mode');
            this.startSimulation();
        };
    }
    
    handleWebSocketMessage(data) {
        switch(data.type) {
            case 'market_data':
                this.updateMarketWatch(data.symbols);
                break;
            case 'trade':
                this.addTradingActivity(data.symbol, data.message, data.side);
                break;
            case 'position_update':
                this.updatePositions(data.positions);
                break;
            case 'chart_data':
                this.updateChart(data.candles);
                break;
        }
    }
    
    startSimulation() {
        // Simulated real-time data when WebSocket is not available
        this.simulateMarketData();
        this.simulateTradingActivity();
        setInterval(() => this.simulateMarketData(), 2000);
        setInterval(() => this.simulateTradingActivity(), 5000);
    }
    
    simulateMarketData() {
        const symbols = [
            { symbol: 'AAPL', name: 'Apple', price: 178.23, change: 2.34, changePercent: 1.33 },
            { symbol: 'GOOGL', name: 'Google', price: 142.56, change: -1.23, changePercent: -0.86 },
            { symbol: 'MSFT', name: 'Microsoft', price: 385.92, change: 4.56, changePercent: 1.19 },
            { symbol: 'TSLA', name: 'Tesla', price: 245.78, change: 8.91, changePercent: 3.76 },
            { symbol: 'BTC/USDT', name: 'Bitcoin', price: 43567.89, change: 1234.56, changePercent: 2.92 },
            { symbol: 'ETH/USDT', name: 'Ethereum', price: 2456.78, change: -45.67, changePercent: -1.82 }
        ];
        
        // Add random fluctuation
        symbols.forEach(s => {
            const fluctuation = (Math.random() - 0.5) * 2;
            s.price += fluctuation;
            s.change += fluctuation;
            this.marketData.set(s.symbol, s);
        });
        
        this.updateMarketWatch(symbols);
        this.updatePortfolioValue();
    }
    
    updateMarketWatch(symbols) {
        const container = document.getElementById('marketWatch');
        container.innerHTML = symbols.map(s => `
            <div class="p-2 bg-gray-800/50 rounded cursor-pointer hover:bg-gray-700/50 transition-all"
                 onclick="dashboard.selectSymbol('${s.symbol}')">
                <div class="flex justify-between items-center">
                    <div>
                        <p class="font-semibold text-sm">${s.symbol}</p>
                        <p class="text-xs text-gray-400">${s.name}</p>
                    </div>
                    <div class="text-right">
                        <p class="font-bold text-sm">$${s.price.toFixed(2)}</p>
                        <p class="text-xs ${s.change >= 0 ? 'text-green-400' : 'text-red-400'}">
                            ${s.change >= 0 ? '+' : ''}${s.change.toFixed(2)} (${s.changePercent.toFixed(2)}%)
                        </p>
                    </div>
                </div>
            </div>
        `).join('');
    }
    
    simulateTradingActivity() {
        const actions = [
            { symbol: 'AAPL', action: 'BUY', quantity: 100, price: 178.23 },
            { symbol: 'GOOGL', action: 'SELL', quantity: 50, price: 142.56 },
            { symbol: 'BTC/USDT', action: 'BUY', quantity: 0.05, price: 43567.89 },
            { symbol: 'TSLA', action: 'BUY', quantity: 25, price: 245.78 },
            { symbol: 'ETH/USDT', action: 'SELL', quantity: 1.5, price: 2456.78 }
        ];
        
        const randomAction = actions[Math.floor(Math.random() * actions.length)];
        const message = `${randomAction.action} ${randomAction.quantity} @ $${randomAction.price.toFixed(2)}`;
        this.addTradingActivity(randomAction.symbol, message, randomAction.action.toLowerCase());
    }
    
    addTradingActivity(symbol, message, type) {
        const container = document.getElementById('tradingActivity');
        const time = new Date().toLocaleTimeString();
        
        const iconMap = {
            'buy': '📈',
            'sell': '📉',
            'info': 'ℹ️',
            'warning': '⚠️'
        };
        
        const colorMap = {
            'buy': 'text-green-400',
            'sell': 'text-red-400',
            'info': 'text-blue-400',
            'warning': 'text-yellow-400'
        };
        
        const activityHtml = `
            <div class="trade-item p-2 bg-gray-800/30 rounded border-l-2 ${type === 'buy' ? 'border-green-500' : 'border-red-500'}">
                <div class="flex justify-between items-start">
                    <div class="flex items-start space-x-2">
                        <span class="text-lg">${iconMap[type] || '📊'}</span>
                        <div>
                            <p class="text-xs ${colorMap[type]} font-semibold">${symbol}</p>
                            <p class="text-xs text-gray-300">${message}</p>
                        </div>
                    </div>
                    <span class="text-xs text-gray-500">${time}</span>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('afterbegin', activityHtml);
        
        // Keep only last 10 activities
        while (container.children.length > 10) {
            container.removeChild(container.lastChild);
        }
    }
    
    loadInitialPositions() {
        const positions = [
            { symbol: 'AAPL', quantity: 100, avgPrice: 175.50, currentPrice: 178.23, pnl: 273.00 },
            { symbol: 'GOOGL', quantity: 50, avgPrice: 145.00, currentPrice: 142.56, pnl: -122.00 },
            { symbol: 'BTC/USDT', quantity: 0.5, avgPrice: 42000, currentPrice: 43567.89, pnl: 783.95 },
            { symbol: 'TSLA', quantity: 25, avgPrice: 240.00, currentPrice: 245.78, pnl: 144.50 },
            { symbol: 'MSFT', quantity: 75, avgPrice: 380.00, currentPrice: 385.92, pnl: 444.00 }
        ];
        
        this.updatePositions(positions);
    }
    
    updatePositions(positions) {
        const container = document.getElementById('openPositions');
        container.innerHTML = positions.map(p => {
            const pnlPercent = ((p.currentPrice - p.avgPrice) / p.avgPrice * 100).toFixed(2);
            const pnlColor = p.pnl >= 0 ? 'text-green-400' : 'text-red-400';
            
            return `
                <div class="p-2 bg-gray-800/30 rounded">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-sm font-semibold">${p.symbol}</span>
                        <span class="text-xs ${pnlColor}">
                            ${p.pnl >= 0 ? '+' : ''}$${p.pnl.toFixed(2)} (${pnlPercent}%)
                        </span>
                    </div>
                    <div class="flex justify-between text-xs text-gray-400">
                        <span>${p.quantity} units</span>
                        <span>Avg: $${p.avgPrice.toFixed(2)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    initChart() {
        const options = {
            series: [{
                name: 'Price',
                data: this.generateChartData()
            }],
            chart: {
                type: 'candlestick',
                height: '100%',
                background: 'transparent',
                toolbar: {
                    show: false
                },
                animations: {
                    enabled: true,
                    easing: 'linear',
                    dynamicAnimation: {
                        speed: 1000
                    }
                }
            },
            theme: {
                mode: 'dark'
            },
            grid: {
                borderColor: '#1f2937',
                strokeDashArray: 4
            },
            xaxis: {
                type: 'datetime',
                labels: {
                    style: {
                        colors: '#9ca3af'
                    }
                }
            },
            yaxis: {
                labels: {
                    style: {
                        colors: '#9ca3af'
                    },
                    formatter: (val) => '$' + val.toFixed(2)
                }
            },
            plotOptions: {
                candlestick: {
                    colors: {
                        upward: '#10b981',
                        downward: '#ef4444'
                    }
                }
            }
        };
        
        this.chart = new ApexCharts(document.getElementById('tradingChart'), options);
        this.chart.render();
        
        // Update chart every 5 seconds
        setInterval(() => this.updateChartData(), 5000);
    }
    
    generateChartData() {
        const data = [];
        const basePrice = 178;
        let currentDate = new Date();
        
        for (let i = 0; i < 50; i++) {
            const open = basePrice + (Math.random() - 0.5) * 5;
            const close = open + (Math.random() - 0.5) * 3;
            const high = Math.max(open, close) + Math.random() * 2;
            const low = Math.min(open, close) - Math.random() * 2;
            
            data.push({
                x: new Date(currentDate.getTime() - (50 - i) * 60000),
                y: [open, high, low, close]
            });
        }
        
        return data;
    }
    
    updateChartData() {
        const newData = this.generateChartData();
        this.chart.updateSeries([{
            name: 'Price',
            data: newData
        }]);
    }
    
    selectSymbol(symbol) {
        this.selectedSymbol = symbol;
        document.getElementById('selectedSymbol').textContent = symbol;
        this.updateChartData();
        this.addTradingActivity('CHART', `Switched to ${symbol}`, 'info');
    }
    
    updatePortfolioValue() {
        const baseValue = 125342.67;
        const fluctuation = (Math.random() - 0.5) * 1000;
        const newValue = baseValue + fluctuation;
        document.getElementById('portfolioValue').textContent = `$${newValue.toFixed(2)}`;
    }
    
    updateTime() {
        const updateClock = () => {
            const now = new Date();
            document.getElementById('currentTime').textContent = now.toLocaleString();
        };
        
        updateClock();
        setInterval(updateClock, 1000);
    }
    
    startRealTimeUpdates() {
        // Update various metrics periodically
        setInterval(() => {
            // Update P&L
            const pnl = 2341.50 + (Math.random() - 0.5) * 200;
            const pnlElement = document.querySelector('.neon-green');
            if (pnlElement) {
                pnlElement.textContent = `+$${pnl.toFixed(2)}`;
            }
        }, 3000);
    }
}

// Initialize dashboard when DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new TradingDashboard();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Emergency stop trading
            dashboard.addTradingActivity('SYSTEM', 'Emergency stop triggered', 'warning');
        }
    });
});

// Prevent console errors when WebSocket fails
window.addEventListener('error', (e) => {
    if (e.message && e.message.includes('WebSocket')) {
        e.preventDefault();
        console.log('WebSocket connection failed, using simulation mode');
    }
});