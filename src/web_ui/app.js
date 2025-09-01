// Sofia Trading Platform - Main Application JavaScript

// Global variables
let ws = null;
let chart = null;
let portfolioChart = null;
let currentSymbol = 'AAPL';
let positions = [];
let marketData = {};

// Sample data for demo
const samplePositions = [
    { symbol: 'AAPL', quantity: 100, entryPrice: 170.50, currentPrice: 175.50 },
    { symbol: 'GOOGL', quantity: 50, entryPrice: 142.30, currentPrice: 140.25 },
    { symbol: 'BTC/USDT', quantity: 0.5, entryPrice: 43500, currentPrice: 45000 },
    { symbol: 'MSFT', quantity: 75, entryPrice: 375.20, currentPrice: 380.75 },
    { symbol: 'ETH/USDT', quantity: 2, entryPrice: 2400, currentPrice: 2500 },
    { symbol: 'TSLA', quantity: 30, entryPrice: 245.80, currentPrice: 240.60 },
    { symbol: 'AMZN', quantity: 40, entryPrice: 152.40, currentPrice: 155.30 }
];

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Sofia Trading Platform...');
    
    createParticles();
    initializeChart();
    initializePortfolioChart();
    initializeEventHandlers();
    connectWebSocket();
    startDataSimulation();
    updatePositionsTable();
    updateOrderBook();
});

// Create floating particles
function createParticles() {
    const particlesContainer = document.getElementById('particles');
    const icons = ['📊', '📈', '📉', '💹', '💱', '💰', '🎯', '⚡'];
    
    for (let i = 0; i < 15; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 20 + 's';
        particle.style.animationDuration = (15 + Math.random() * 10) + 's';
        particle.innerHTML = icons[Math.floor(Math.random() * icons.length)];
        particlesContainer.appendChild(particle);
    }
}

// Initialize main chart
function initializeChart() {
    const chartContainer = document.getElementById('main-chart');
    
    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.offsetWidth,
        height: 350,
        layout: {
            background: { color: 'transparent' },
            textColor: '#8892b0',
        },
        grid: {
            vertLines: { color: 'rgba(100, 150, 255, 0.1)' },
            horzLines: { color: 'rgba(100, 150, 255, 0.1)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: 'rgba(100, 150, 255, 0.2)',
        },
        timeScale: {
            borderColor: 'rgba(100, 150, 255, 0.2)',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#64ffda',
        downColor: '#ff6b6b',
        borderDownColor: '#ff6b6b',
        borderUpColor: '#64ffda',
        wickDownColor: '#ff6b6b',
        wickUpColor: '#64ffda',
    });

    // Generate and set data
    const data = generateCandlestickData();
    candlestickSeries.setData(data);

    // Add volume
    const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
    });

    volumeSeries.setData(data.map(d => ({
        time: d.time,
        value: Math.random() * 10000000,
        color: d.close > d.open ? 'rgba(100, 255, 218, 0.3)' : 'rgba(255, 107, 107, 0.3)',
    })));

    // Handle resize
    window.addEventListener('resize', () => {
        chart.applyOptions({ width: chartContainer.offsetWidth });
    });
}

// Generate candlestick data
function generateCandlestickData() {
    const data = [];
    let time = new Date();
    let price = 175;

    for (let i = 100; i >= 0; i--) {
        const date = new Date(time.getTime() - i * 60000);
        const volatility = 0.02;
        const noise = (Math.random() - 0.5) * volatility;
        const trend = Math.sin(i / 10) * 2;
        
        price = price * (1 + noise) + trend;
        
        const open = price;
        const close = price + (Math.random() - 0.5) * 2;
        const high = Math.max(open, close) + Math.random();
        const low = Math.min(open, close) - Math.random();

        data.push({
            time: Math.floor(date.getTime() / 1000),
            open: open,
            high: high,
            low: low,
            close: close,
        });

        price = close;
    }

    return data;
}

// Initialize portfolio chart
function initializePortfolioChart() {
    const ctx = document.getElementById('portfolio-chart');
    if (!ctx) return;

    portfolioChart = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['AAPL', 'GOOGL', 'MSFT', 'BTC', 'ETH', 'Cash'],
            datasets: [{
                data: [20, 15, 18, 12, 10, 25],
                backgroundColor: [
                    'rgba(102, 126, 234, 0.8)',
                    'rgba(118, 75, 162, 0.8)',
                    'rgba(100, 255, 218, 0.8)',
                    'rgba(255, 107, 107, 0.8)',
                    'rgba(255, 215, 61, 0.8)',
                    'rgba(136, 146, 176, 0.8)',
                ],
                borderColor: 'rgba(100, 150, 255, 0.2)',
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#8892b0',
                        padding: 10,
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            },
        },
    });
}

// WebSocket connection
function connectWebSocket() {
    const wsUrl = 'ws://localhost:8000/ws';
    
    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('Connected to trading platform');
            showNotification('Connected to trading platform', 'success');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            showNotification('Connection error', 'error');
        };

        ws.onclose = () => {
            console.log('Disconnected from trading platform');
            showNotification('Disconnected - Reconnecting...', 'warning');
            setTimeout(connectWebSocket, 3000);
        };
    } catch (error) {
        console.error('Failed to connect:', error);
        // Continue with simulation mode
        startDataSimulation();
    }
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    if (data.type === 'market_data') {
        updateMarketData(data.data);
    } else if (data.type === 'position_update') {
        updatePositions(data.data);
    } else if (data.type === 'order_update') {
        updateOrderBook(data.data);
    }
}

// Start data simulation (fallback when WebSocket is not available)
function startDataSimulation() {
    // Simulate market data updates
    setInterval(() => {
        const symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'BTC/USDT', 'ETH/USDT'];
        const simulatedData = symbols.map(symbol => {
            const basePrice = marketData[symbol]?.price || (100 + Math.random() * 400);
            const change = (Math.random() - 0.5) * 4;
            const price = basePrice * (1 + change / 100);
            
            return {
                symbol: symbol,
                price: price,
                change: change,
                change_percent: change,
                volume: Math.floor(Math.random() * 10000000),
                high: price * 1.02,
                low: price * 0.98,
            };
        });
        
        updateMarketData(simulatedData);
    }, 2000);

    // Simulate position updates
    setInterval(() => {
        updatePositionsTable();
        updatePortfolioStats();
    }, 3000);

    // Simulate order book updates
    setInterval(() => {
        updateOrderBook();
    }, 2500);
}

// Update market data
function updateMarketData(data) {
    const tickerGrid = document.getElementById('ticker-grid');
    if (!tickerGrid) return;

    tickerGrid.innerHTML = '';
    
    data.forEach(ticker => {
        marketData[ticker.symbol] = ticker;
        
        const changeClass = ticker.change >= 0 ? 'positive' : 'negative';
        const tickerElement = document.createElement('div');
        tickerElement.className = 'ticker-item';
        tickerElement.onclick = () => selectTicker(ticker.symbol);
        
        tickerElement.innerHTML = `
            <div class="ticker-symbol">${ticker.symbol}</div>
            <div class="ticker-price">$${ticker.price.toFixed(2)}</div>
            <div class="ticker-change ${changeClass}">
                ${ticker.change >= 0 ? '+' : ''}${ticker.change.toFixed(2)}%
            </div>
            <div class="ticker-volume">Vol: ${(ticker.volume / 1000000).toFixed(2)}M</div>
        `;
        
        tickerGrid.appendChild(tickerElement);
    });
}

// Update positions table
function updatePositionsTable() {
    const tbody = document.getElementById('positions-tbody');
    if (!tbody) return;

    tbody.innerHTML = '';
    
    samplePositions.forEach(position => {
        // Add some random price movement
        position.currentPrice = position.currentPrice * (1 + (Math.random() - 0.5) * 0.01);
        
        const pnl = (position.currentPrice - position.entryPrice) * position.quantity;
        const pnlPercent = ((position.currentPrice - position.entryPrice) / position.entryPrice) * 100;
        const value = position.currentPrice * position.quantity;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="position-symbol">${position.symbol}</td>
            <td>${position.quantity}</td>
            <td>$${position.entryPrice.toFixed(2)}</td>
            <td>$${position.currentPrice.toFixed(2)}</td>
            <td class="position-pnl ${pnl >= 0 ? 'positive' : 'negative'}">
                ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
            </td>
            <td class="position-pnl ${pnlPercent >= 0 ? 'positive' : 'negative'}">
                ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
            </td>
            <td>$${value.toFixed(2)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// Update order book
function updateOrderBook() {
    const buyOrders = document.getElementById('buy-orders');
    const sellOrders = document.getElementById('sell-orders');
    
    if (!buyOrders || !sellOrders) return;

    const basePrice = marketData[currentSymbol]?.price || 175.50;
    
    // Generate buy orders
    buyOrders.innerHTML = '';
    for (let i = 0; i < 5; i++) {
        const price = basePrice - (i * 0.05);
        const amount = Math.floor(Math.random() * 3000) + 500;
        const total = price * amount;
        
        const orderRow = document.createElement('div');
        orderRow.className = 'order-row';
        orderRow.innerHTML = `
            <span class="order-price">$${price.toFixed(2)}</span>
            <span class="order-amount">${amount.toLocaleString()}</span>
            <span class="order-total">$${total.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}</span>
        `;
        buyOrders.appendChild(orderRow);
    }
    
    // Generate sell orders
    sellOrders.innerHTML = '';
    for (let i = 0; i < 5; i++) {
        const price = basePrice + (i * 0.05);
        const amount = Math.floor(Math.random() * 3000) + 500;
        const total = price * amount;
        
        const orderRow = document.createElement('div');
        orderRow.className = 'order-row';
        orderRow.innerHTML = `
            <span class="order-price">$${price.toFixed(2)}</span>
            <span class="order-amount">${amount.toLocaleString()}</span>
            <span class="order-total">$${total.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}</span>
        `;
        sellOrders.appendChild(orderRow);
    }
}

// Update portfolio statistics
function updatePortfolioStats() {
    const portfolioValue = 125430.50 + (Math.random() - 0.5) * 2000;
    const dailyPnl = 2345.67 + (Math.random() - 0.5) * 1000;
    const totalReturn = 18.5 + (Math.random() - 0.5) * 2;

    const portfolioValueEl = document.getElementById('portfolio-value');
    const dailyPnlEl = document.getElementById('daily-pnl');
    const totalReturnEl = document.getElementById('total-return');

    if (portfolioValueEl) {
        portfolioValueEl.textContent = `$${portfolioValue.toFixed(2)}`;
    }
    
    if (dailyPnlEl) {
        dailyPnlEl.textContent = `${dailyPnl >= 0 ? '+' : ''}$${Math.abs(dailyPnl).toFixed(2)}`;
        dailyPnlEl.className = `stat-value ${dailyPnl >= 0 ? 'positive' : 'negative'}`;
    }
    
    if (totalReturnEl) {
        totalReturnEl.textContent = `${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(1)}%`;
        totalReturnEl.className = `stat-value ${totalReturn >= 0 ? 'positive' : 'negative'}`;
    }
}

// Select ticker
function selectTicker(symbol) {
    currentSymbol = symbol;
    
    const tradeSymbol = document.getElementById('trade-symbol');
    if (tradeSymbol) {
        tradeSymbol.value = symbol;
    }
    
    // Update order book title
    const orderBookTitle = document.querySelector('.order-book .card-title');
    if (orderBookTitle) {
        orderBookTitle.textContent = `Order Book - ${symbol}`;
    }
    
    // Update price input
    const priceInput = document.getElementById('trade-price');
    if (priceInput && marketData[symbol]) {
        priceInput.value = marketData[symbol].price.toFixed(2);
    }
    
    updateOrderBook();
}

// Execute trade
function executeTrade(side) {
    const symbol = document.getElementById('trade-symbol').value;
    const quantity = document.getElementById('trade-quantity').value;
    const price = document.getElementById('trade-price').value;
    const orderType = document.getElementById('order-type').value;

    if (!quantity || quantity <= 0) {
        showNotification('Please enter a valid quantity', 'error');
        return;
    }

    // Send trade via WebSocket if connected
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'place_order',
            data: {
                symbol: symbol,
                side: side,
                quantity: parseFloat(quantity),
                price: parseFloat(price),
                orderType: orderType
            }
        }));
    }

    // Add to activity feed
    addActivity(side, symbol, quantity, price);
    
    // Show notification
    showNotification(
        `${side.toUpperCase()} order placed: ${quantity} ${symbol} @ $${price}`,
        'success'
    );
}

// Add activity to feed
function addActivity(type, symbol, quantity, price) {
    const activityList = document.getElementById('activity-list');
    if (!activityList) return;

    const activityItem = document.createElement('div');
    activityItem.className = `activity-item ${type}`;
    
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    
    activityItem.innerHTML = `
        <div class="activity-content">
            <span class="activity-icon">${type === 'buy' ? '📈' : '📉'}</span>
            <span class="activity-text">
                ${type === 'buy' ? 'Bought' : 'Sold'} ${quantity} shares of ${symbol} at $${price}
            </span>
        </div>
        <span class="activity-time">${timeString}</span>
    `;
    
    // Add to top of list
    activityList.insertBefore(activityItem, activityList.firstChild);
    
    // Keep only last 10 activities
    while (activityList.children.length > 10) {
        activityList.removeChild(activityList.lastChild);
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = 'notification';
    
    // Add type-specific styling
    if (type === 'error') {
        notification.style.background = 'linear-gradient(135deg, rgba(255, 107, 107, 0.9), rgba(255, 135, 135, 0.9))';
    } else if (type === 'success') {
        notification.style.background = 'linear-gradient(135deg, rgba(100, 255, 218, 0.9), rgba(72, 202, 228, 0.9))';
        notification.style.color = '#0a0e27';
    } else if (type === 'warning') {
        notification.style.background = 'linear-gradient(135deg, rgba(255, 215, 61, 0.9), rgba(255, 193, 7, 0.9))';
        notification.style.color = '#0a0e27';
    }
    
    notification.textContent = message;
    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Initialize event handlers
function initializeEventHandlers() {
    // Chart timeframe buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            const timeframe = e.target.dataset.timeframe;
            console.log('Switching to timeframe:', timeframe);
            
            // Regenerate chart data for new timeframe
            if (chart) {
                const data = generateCandlestickData();
                chart.applyOptions({
                    timeScale: {
                        timeVisible: timeframe !== '1d',
                    }
                });
            }
        });
    });

    // Order type change handler
    const orderTypeSelect = document.getElementById('order-type');
    if (orderTypeSelect) {
        orderTypeSelect.addEventListener('change', (e) => {
            const priceInput = document.getElementById('trade-price');
            if (priceInput) {
                priceInput.disabled = e.target.value === 'Market';
                if (e.target.value === 'Market') {
                    priceInput.value = 'Market Price';
                } else if (marketData[currentSymbol]) {
                    priceInput.value = marketData[currentSymbol].price.toFixed(2);
                }
            }
        });
    }

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+B for Buy
        if (e.ctrlKey && e.key === 'b') {
            e.preventDefault();
            executeTrade('buy');
        }
        // Ctrl+S for Sell
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            executeTrade('sell');
        }
    });
}

// Add some initial activities
setTimeout(() => {
    addActivity('info', 'System', 0, 0);
    const infoItem = document.querySelector('.activity-item:first-child');
    if (infoItem) {
        infoItem.innerHTML = `
            <div class="activity-content">
                <span class="activity-icon">🚀</span>
                <span class="activity-text">Trading platform initialized successfully</span>
            </div>
            <span class="activity-time">Just now</span>
        `;
    }
}, 1000);