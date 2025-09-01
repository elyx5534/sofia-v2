"""
Dashboard route for P&L visualization
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Dashboard"])

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sofia V2 - P&L Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { 
            text-align: center; 
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
        }
        .header h1 { 
            font-size: 2.5rem; 
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00f260, #0575e6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .error-banner {
            display: none;
            background: #ff4444;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s;
        }
        .card:hover { transform: translateY(-5px); }
        .card h2 {
            font-size: 1rem;
            color: #888;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .pnl-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .pnl-positive { color: #00ff88; }
        .pnl-negative { color: #ff4444; }
        .pnl-neutral { color: #ffaa00; }
        .pnl-percent {
            font-size: 1.2rem;
            opacity: 0.8;
        }
        .chart-container {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            height: 400px;
            position: relative;
        }
        .live-proof {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            font-size: 0.9rem;
        }
        .live-proof-item {
            text-align: center;
            padding: 10px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
        }
        .live-proof-label {
            color: #888;
            font-size: 0.8rem;
            margin-bottom: 5px;
        }
        .live-proof-value {
            font-size: 1.2rem;
            font-weight: bold;
            color: #00f260;
        }
        .trades-table {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            overflow-x: auto;
        }
        .trades-table h2 {
            margin-bottom: 20px;
            color: #00f260;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid rgba(255,255,255,0.1);
            color: #888;
            font-size: 0.9rem;
            text-transform: uppercase;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .trade-buy { color: #00ff88; }
        .trade-sell { color: #ff4444; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .stat-item {
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
        }
        .stat-label { color: #888; }
        .stat-value { font-weight: bold; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .updating { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Sofia V2 P&L Dashboard</h1>
            <p style="opacity: 0.6">Real-time Paper Trading Performance</p>
        </div>
        
        <div id="errorBanner" class="error-banner">
            Backend connection lost. Retrying...
        </div>
        
        <div class="grid">
            <!-- Today's P&L Card -->
            <div class="card">
                <h2>Today's P&L</h2>
                <div id="todayPnl" class="pnl-value pnl-neutral">$0.00</div>
                <div id="todayPnlPercent" class="pnl-percent">0.00%</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-label">Realized</span>
                        <span id="realizedPnl" class="stat-value">$0.00</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Unrealized</span>
                        <span id="unrealizedPnl" class="stat-value">$0.00</span>
                    </div>
                </div>
            </div>
            
            <!-- Trading Stats Card -->
            <div class="card">
                <h2>Trading Stats</h2>
                <div style="font-size: 2rem; font-weight: bold; margin-bottom: 10px;">
                    <span id="totalTrades">0</span> Trades
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-label">Win Rate</span>
                        <span id="winRate" class="stat-value">0%</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Equity</span>
                        <span id="currentEquity" class="stat-value">$1000</span>
                    </div>
                </div>
            </div>
            
            <!-- Live Proof Card -->
            <div class="card">
                <h2>Live Market (BTC/USDT)</h2>
                <div class="live-proof">
                    <div class="live-proof-item">
                        <div class="live-proof-label">BID</div>
                        <div id="liveBid" class="live-proof-value">-</div>
                    </div>
                    <div class="live-proof-item">
                        <div class="live-proof-label">ASK</div>
                        <div id="liveAsk" class="live-proof-value">-</div>
                    </div>
                    <div class="live-proof-item">
                        <div class="live-proof-label">LAST</div>
                        <div id="liveLast" class="live-proof-value">-</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 10px; opacity: 0.5; font-size: 0.8rem;">
                    Exchange: <span id="exchangeName">Binance</span> | 
                    <span id="lastUpdate">Never</span>
                </div>
            </div>
        </div>
        
        <!-- Equity Chart -->
        <div class="chart-container">
            <h2 style="margin-bottom: 20px; color: #00f260;">Equity Curve</h2>
            <canvas id="equityChart"></canvas>
        </div>
        
        <!-- Last Trades Table -->
        <div class="trades-table">
            <h2>Last Trades</h2>
            <table id="tradesTable">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Quantity</th>
                        <th>Price</th>
                    </tr>
                </thead>
                <tbody id="tradesBody">
                    <tr>
                        <td colspan="5" style="text-align: center; opacity: 0.5;">No trades yet</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Initialize Chart.js
        const ctx = document.getElementById('equityChart').getContext('2d');
        const equityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Equity',
                    data: [],
                    borderColor: '#00f260',
                    backgroundColor: 'rgba(0, 242, 96, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#888' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { 
                            color: '#888',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
        
        let equityHistory = [];
        let errorCount = 0;
        let sessionRunning = false;
        
        // Update P&L Summary
        async function updatePnlSummary() {
            try {
                const response = await fetch('/api/pnl/summary');
                if (!response.ok) throw new Error('Failed to fetch P&L');
                
                const data = await response.json();
                
                // Update P&L values
                const totalPnl = data.total_pnl || 0;
                const pnlPercent = data.pnl_percentage || 0;
                
                document.getElementById('todayPnl').textContent = '$' + totalPnl.toFixed(2);
                document.getElementById('todayPnl').className = 'pnl-value ' + 
                    (totalPnl > 0 ? 'pnl-positive' : totalPnl < 0 ? 'pnl-negative' : 'pnl-neutral');
                
                document.getElementById('todayPnlPercent').textContent = 
                    (pnlPercent >= 0 ? '+' : '') + pnlPercent.toFixed(2) + '%';
                document.getElementById('todayPnlPercent').className = 'pnl-percent ' +
                    (pnlPercent > 0 ? 'pnl-positive' : pnlPercent < 0 ? 'pnl-negative' : '');
                
                document.getElementById('realizedPnl').textContent = '$' + (data.realized_pnl || 0).toFixed(2);
                document.getElementById('unrealizedPnl').textContent = '$' + (data.unrealized_pnl || 0).toFixed(2);
                document.getElementById('totalTrades').textContent = data.total_trades || 0;
                document.getElementById('winRate').textContent = (data.win_rate || 0).toFixed(1) + '%';
                document.getElementById('currentEquity').textContent = '$' + (data.final_capital || 1000).toFixed(2);
                
                // Update session status indicator
                sessionRunning = data.is_running || false;
                const statusText = sessionRunning ? '🟢 LIVE' : (data.session_complete ? '✅ COMPLETE' : '⭕ IDLE');
                document.querySelector('.header p').innerHTML = 'Real-time Paper Trading Performance | Status: ' + statusText + ' | Source: ' + (data.source || 'default');
                
                // Update equity chart based on source
                if (data.source === 'timeseries' && data.timeseries) {
                    // Use timeseries data for chart
                    updateChartFromTimeseries(data.timeseries);
                } else if (data.source === 'summary' && data.timeseries) {
                    // Session running with timeseries
                    updateChartFromTimeseries(data.timeseries);
                } else {
                    // Single point update
                    const now = new Date().toLocaleTimeString();
                    equityHistory.push(data.final_capital || 1000);
                    
                    // Keep only last 50 points
                    if (equityHistory.length > 50) {
                        equityHistory.shift();
                        equityChart.data.labels.shift();
                    }
                    
                    equityChart.data.labels.push(now);
                    equityChart.data.datasets[0].data = [...equityHistory];
                    equityChart.update('none');
                }
                
                // Reset error state
                errorCount = 0;
                document.getElementById('errorBanner').style.display = 'none';
                
            } catch (error) {
                console.error('Error updating P&L:', error);
                handleError();
            }
        }
        
        // Update chart from timeseries data
        function updateChartFromTimeseries(timeseries) {
            if (!timeseries || timeseries.length === 0) return;
            
            // Clear and rebuild chart data
            const labels = [];
            const data = [];
            
            // Use last 50 points or all if less
            const points = timeseries.slice(-50);
            
            points.forEach(point => {
                const date = new Date(point.ts_ms);
                labels.push(date.toLocaleTimeString());
                data.push(point.equity);
            });
            
            equityChart.data.labels = labels;
            equityChart.data.datasets[0].data = data;
            equityChart.update('none');
            
            // Store for future updates
            equityHistory = [...data];
        }
        
        // Update Live Proof
        async function updateLiveProof() {
            try {
                const response = await fetch('/live-proof?symbol=BTC/USDT');
                if (!response.ok) throw new Error('Failed to fetch live proof');
                
                const data = await response.json();
                
                document.getElementById('liveBid').textContent = '$' + (data.bid || 0).toFixed(2);
                document.getElementById('liveAsk').textContent = '$' + (data.ask || 0).toFixed(2);
                document.getElementById('liveLast').textContent = '$' + (data.last || 0).toFixed(2);
                document.getElementById('exchangeName').textContent = data.exchange || 'Unknown';
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
            } catch (error) {
                console.error('Error updating live proof:', error);
                document.getElementById('liveBid').textContent = '-';
                document.getElementById('liveAsk').textContent = '-';
                document.getElementById('liveLast').textContent = '-';
            }
        }
        
        // Update Trades Table
        async function updateTrades() {
            try {
                const response = await fetch('/api/pnl/logs/trades?n=10');
                if (!response.ok) throw new Error('Failed to fetch trades');
                
                const data = await response.json();
                const tbody = document.getElementById('tradesBody');
                
                if (data.items && data.items.length > 0) {
                    tbody.innerHTML = '';
                    
                    // Display trades (already sorted by most recent)
                    data.items.slice(0, 10).forEach(trade => {
                        const row = tbody.insertRow();
                        
                        // Time
                        const time = trade.ts_ms ? new Date(trade.ts_ms).toLocaleTimeString() : '-';
                        row.insertCell(0).textContent = time;
                        
                        // Symbol
                        row.insertCell(1).textContent = trade.symbol || 'BTC/USDT';
                        
                        // Side
                        const sideCell = row.insertCell(2);
                        sideCell.textContent = (trade.side || '-').toUpperCase();
                        sideCell.className = trade.side === 'buy' ? 'trade-buy' : 'trade-sell';
                        
                        // Quantity
                        row.insertCell(3).textContent = (trade.qty || 0).toFixed(8);
                        
                        // Price
                        row.insertCell(4).textContent = '$' + (trade.price || 0).toFixed(2);
                    });
                    
                    // Update trade count indicator
                    const tradeCountEl = document.getElementById('totalTrades');
                    if (tradeCountEl && data.total_trades) {
                        tradeCountEl.textContent = data.total_trades;
                    }
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; opacity: 0.5;">No trades yet</td></tr>';
                }
                
            } catch (error) {
                console.error('Error updating trades:', error);
                const tbody = document.getElementById('tradesBody');
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; opacity: 0.5; color: #ff4444;">Error loading trades</td></tr>';
            }
        }
        
        // Handle errors
        function handleError() {
            errorCount++;
            if (errorCount > 2) {
                document.getElementById('errorBanner').style.display = 'block';
            }
        }
        
        // Initial load
        updatePnlSummary();
        updateLiveProof();
        updateTrades();
        
        // Set up polling (every 5 seconds)
        setInterval(() => {
            updatePnlSummary();
            updateLiveProof();
            updateTrades();
        }, 5000);
    </script>
</body>
</html>
"""

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the P&L dashboard"""
    return HTMLResponse(content=DASHBOARD_HTML)