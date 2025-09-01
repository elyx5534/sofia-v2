// Sofia V2 Developer Dashboard - Real-time Updates

let ws = null;
let pnlChart = null;
let strategyCharts = {};
let currentPnlType = 'paper';

// Initialize WebSocket connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        // Reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connection-status');
    if (connected) {
        statusElement.textContent = 'Connected';
        statusElement.className = 'status-badge connected';
    } else {
        statusElement.textContent = 'Disconnected';
        statusElement.className = 'status-badge disconnected';
    }
}

// Update current time
function updateTime() {
    const timeElement = document.getElementById('current-time');
    const now = new Date();
    timeElement.textContent = now.toLocaleTimeString();
}

// Main dashboard update function
function updateDashboard(data) {
    if (data.system) updateSystemMonitor(data.system);
    if (data.pnl) updatePnlTracker(data.pnl);
    if (data.strategies) updateStrategies(data.strategies);
    if (data.exchanges) updateExchanges(data.exchanges);
    if (data.logs) updateLogs(data.logs);
}

// Update system monitor
function updateSystemMonitor(system) {
    // CPU
    document.getElementById('cpu-bar').style.width = `${system.cpu_percent}%`;
    document.getElementById('cpu-value').textContent = `${system.cpu_percent.toFixed(1)}%`;
    
    // Memory
    document.getElementById('memory-bar').style.width = `${system.memory_percent}%`;
    document.getElementById('memory-value').textContent = 
        `${system.memory_used_gb} GB / ${system.memory_total_gb} GB`;
    
    // Network
    document.getElementById('network-value').textContent = 
        `↓ ${system.network_recv_mb.toFixed(1)} MB ↑ ${system.network_sent_mb.toFixed(1)} MB`;
    
    // Active strategies
    document.getElementById('active-strategies').textContent = system.active_strategies;
    
    // WebSocket connections
    document.getElementById('ws-connections').textContent = system.websocket_connections;
}

// Update P&L tracker
function updatePnlTracker(pnl) {
    const data = pnl[currentPnlType];
    
    // Update values
    updatePnlValue('pnl-today', data.today);
    updatePnlValue('pnl-week', data.week);
    updatePnlValue('pnl-month', data.month);
    updatePnlValue('pnl-all-time', data.all_time);
    
    // Update chart
    if (!pnlChart) {
        initPnlChart(pnl.chart_data);
    } else {
        updatePnlChart(pnl.chart_data);
    }
}

function updatePnlValue(elementId, value) {
    const element = document.getElementById(elementId);
    element.textContent = `$${value.toFixed(2)}`;
    element.className = value >= 0 ? 'pnl-value positive' : 'pnl-value negative';
}

// Initialize P&L chart
function initPnlChart(chartData) {
    const ctx = document.getElementById('pnl-chart').getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'P&L',
                data: chartData[currentPnlType],
                borderColor: '#00a6fb',
                backgroundColor: 'rgba(0, 166, 251, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#a0a0a0',
                        maxTicksLimit: 10
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#a0a0a0',
                        callback: function(value) {
                            return '$' + value;
                        }
                    }
                }
            }
        }
    });
}

function updatePnlChart(chartData) {
    if (pnlChart) {
        pnlChart.data.datasets[0].data = chartData[currentPnlType];
        pnlChart.update('none');
    }
}

// Update strategy cards
function updateStrategies(strategies) {
    const container = document.getElementById('strategy-cards');
    
    Object.entries(strategies).forEach(([id, strategy]) => {
        let card = document.getElementById(`strategy-${id}`);
        
        if (!card) {
            card = createStrategyCard(id, strategy);
            container.appendChild(card);
        } else {
            updateStrategyCard(card, strategy);
        }
        
        // Update mini chart
        updateMiniChart(id, strategy.last_trades);
    });
}

function createStrategyCard(id, strategy) {
    const card = document.createElement('div');
    card.id = `strategy-${id}`;
    card.className = 'strategy-card';
    
    card.innerHTML = `
        <div class="strategy-header">
            <span class="strategy-name">${strategy.name}</span>
            <div class="toggle-switch ${strategy.status === 'active' ? 'active' : ''}" 
                 onclick="toggleStrategy('${id}')"></div>
        </div>
        <div class="strategy-stats">
            <div class="strategy-stat">
                <label>P&L:</label>
                <span class="strategy-pnl ${strategy.pnl >= 0 ? 'positive' : 'negative'}">
                    $${strategy.pnl.toFixed(2)}
                </span>
            </div>
            <div class="strategy-stat">
                <label>Positions:</label>
                <span>${strategy.positions}</span>
            </div>
            <div class="strategy-stat">
                <label>Win Rate:</label>
                <span>${strategy.win_rate.toFixed(1)}%</span>
            </div>
            <div class="strategy-stat">
                <label>Status:</label>
                <span class="${strategy.status}">${strategy.status}</span>
            </div>
        </div>
        <canvas id="chart-${id}" class="mini-chart" width="250" height="60"></canvas>
    `;
    
    return card;
}

function updateStrategyCard(card, strategy) {
    // Update toggle
    const toggle = card.querySelector('.toggle-switch');
    toggle.className = `toggle-switch ${strategy.status === 'active' ? 'active' : ''}`;
    
    // Update stats
    const pnlElement = card.querySelector('.strategy-pnl');
    pnlElement.textContent = `$${strategy.pnl.toFixed(2)}`;
    pnlElement.className = `strategy-pnl ${strategy.pnl >= 0 ? 'positive' : 'negative'}`;
    
    card.querySelector('.strategy-stat:nth-child(2) span').textContent = strategy.positions;
    card.querySelector('.strategy-stat:nth-child(3) span').textContent = `${strategy.win_rate.toFixed(1)}%`;
    card.querySelector('.strategy-stat:nth-child(4) span').textContent = strategy.status;
}

function updateMiniChart(strategyId, trades) {
    const canvasId = `chart-${strategyId}`;
    const canvas = document.getElementById(canvasId);
    
    if (!canvas) return;
    
    if (!strategyCharts[strategyId]) {
        const ctx = canvas.getContext('2d');
        strategyCharts[strategyId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: trades.map((_, i) => i + 1),
                datasets: [{
                    data: trades,
                    backgroundColor: trades.map(t => t >= 0 ? 'rgba(0, 255, 136, 0.6)' : 'rgba(255, 51, 102, 0.6)'),
                    borderWidth: 0
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false
                    }
                }
            }
        });
    } else {
        strategyCharts[strategyId].data.datasets[0].data = trades;
        strategyCharts[strategyId].data.datasets[0].backgroundColor = 
            trades.map(t => t >= 0 ? 'rgba(0, 255, 136, 0.6)' : 'rgba(255, 51, 102, 0.6)');
        strategyCharts[strategyId].update('none');
    }
}

// Update exchange status
function updateExchanges(exchanges) {
    const container = document.getElementById('exchange-list');
    container.innerHTML = '';
    
    Object.entries(exchanges).forEach(([name, exchange]) => {
        const item = document.createElement('div');
        item.className = 'exchange-item';
        
        const statusClass = exchange.status === 'connected' ? 'connected' : 
                          exchange.status === 'connecting' ? 'connecting' : 'error';
        
        const balance = exchange.balance_usd ? 
            `$${exchange.balance_usd.toLocaleString()}` : 
            `₺${(exchange.balance_try || 0).toLocaleString()}`;
        
        item.innerHTML = `
            <div class="exchange-icon">${name.substring(0, 2).toUpperCase()}</div>
            <div class="exchange-info">
                <div class="exchange-name">${name.charAt(0).toUpperCase() + name.slice(1)}</div>
                <div class="exchange-details">
                    Balance: ${balance} | API: ${exchange.api_limit}/1200
                </div>
            </div>
            <div class="exchange-status-dot ${statusClass}"></div>
        `;
        
        container.appendChild(item);
    });
}

// Update logs
function updateLogs(logs) {
    const container = document.getElementById('logs-container');
    const searchTerm = document.getElementById('log-search').value.toLowerCase();
    const levelFilter = document.getElementById('log-filter-level').value;
    const sourceFilter = document.getElementById('log-filter-source').value;
    
    // Clear existing logs
    container.innerHTML = '';
    
    // Filter and display logs
    logs.reverse().forEach(log => {
        if (levelFilter && log.level !== levelFilter) return;
        if (sourceFilter && log.source !== sourceFilter) return;
        if (searchTerm && !log.message.toLowerCase().includes(searchTerm)) return;
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${log.level}`;
        
        const time = new Date(log.timestamp).toLocaleTimeString();
        
        entry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-source">[${log.source}]</span>
            <span class="log-message">${log.message}</span>
        `;
        
        container.appendChild(entry);
    });
    
    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Toggle strategy
async function toggleStrategy(strategyId) {
    try {
        const response = await fetch(`/api/strategy/${strategyId}/toggle`, {
            method: 'POST'
        });
        const result = await response.json();
        console.log('Strategy toggled:', result);
    } catch (error) {
        console.error('Error toggling strategy:', error);
    }
}

// P&L tab switching
document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket
    initWebSocket();
    
    // Update time every second
    setInterval(updateTime, 1000);
    updateTime();
    
    // P&L tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentPnlType = e.target.dataset.type;
        });
    });
    
    // Log filters
    document.getElementById('log-filter-level').addEventListener('change', () => {
        // Logs will be updated on next WebSocket message
    });
    
    document.getElementById('log-search').addEventListener('input', () => {
        // Logs will be updated on next WebSocket message
    });
});