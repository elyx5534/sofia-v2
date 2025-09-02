"""
Sofia V2 Quick Demo - Docker olmadan çalışan basit demo
"""

import asyncio
import random
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sofia V2 Demo")

# Mock data storage
positions = {
    "BTCUSDT": {"quantity": 0.0015, "avg_price": 51234, "pnl": 399.00},
    "ETHUSDT": {"quantity": 0.234, "avg_price": 3234, "pnl": 37.44},
}

orders = []

# HTML Dashboard
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Sofia V2 Demo Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        h1 {
            color: #00d4ff;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .metric {
            display: inline-block;
            margin: 10px 20px;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
        }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .ticker {
            display: inline-block;
            margin: 10px;
            padding: 15px;
            background: rgba(0,212,255,0.1);
            border-radius: 5px;
            min-width: 150px;
        }
    </style>
</head>
<body>
    <h1>🚀 Sofia V2 Trading Platform - Demo Mode</h1>

    <div class="card">
        <h2>📊 Portfolio Metrics</h2>
        <div class="metric">
            <div>Total Equity</div>
            <div class="metric-value">$10,436.44</div>
        </div>
        <div class="metric">
            <div>Total P&L</div>
            <div class="metric-value positive">+$436.44</div>
        </div>
        <div class="metric">
            <div>Win Rate</div>
            <div class="metric-value">67.5%</div>
        </div>
        <div class="metric">
            <div>Active Trades</div>
            <div class="metric-value">2</div>
        </div>
    </div>

    <div class="card">
        <h2>💹 Live Tickers</h2>
        <div id="tickers">
            <div class="ticker">
                <strong>BTCUSDT</strong><br>
                <span id="btc-price">$51,500</span><br>
                <span class="positive">+2.4%</span>
            </div>
            <div class="ticker">
                <strong>ETHUSDT</strong><br>
                <span id="eth-price">$3,250</span><br>
                <span class="positive">+1.8%</span>
            </div>
            <div class="ticker">
                <strong>BNBUSDT</strong><br>
                <span id="bnb-price">$425</span><br>
                <span class="negative">-0.5%</span>
            </div>
            <div class="ticker">
                <strong>SOLUSDT</strong><br>
                <span id="sol-price">$105</span><br>
                <span class="positive">+3.2%</span>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>📈 Open Positions</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Avg Price</th>
                    <th>Current Price</th>
                    <th>P&L</th>
                </tr>
            </thead>
            <tbody id="positions">
                <tr>
                    <td>BTCUSDT</td>
                    <td>0.0015</td>
                    <td>$51,234</td>
                    <td id="btc-current">$51,500</td>
                    <td class="positive">+$399.00</td>
                </tr>
                <tr>
                    <td>ETHUSDT</td>
                    <td>0.234</td>
                    <td>$3,234</td>
                    <td id="eth-current">$3,250</td>
                    <td class="positive">+$37.44</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>📝 Recent Orders</h2>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="orders">
                <tr>
                    <td>12:45:23</td>
                    <td>BTCUSDT</td>
                    <td class="positive">BUY</td>
                    <td>0.0015</td>
                    <td>$51,234</td>
                    <td>✅ Filled</td>
                </tr>
                <tr>
                    <td>12:43:15</td>
                    <td>ETHUSDT</td>
                    <td class="positive">BUY</td>
                    <td>0.234</td>
                    <td>$3,234</td>
                    <td>✅ Filled</td>
                </tr>
            </tbody>
        </table>
    </div>

    <script>
        // Simulate live price updates
        setInterval(() => {
            // Update BTC price
            const btcPrice = 51000 + Math.random() * 1000;
            document.getElementById('btc-price').textContent = '$' + btcPrice.toFixed(0);
            document.getElementById('btc-current').textContent = '$' + btcPrice.toFixed(0);

            // Update ETH price
            const ethPrice = 3200 + Math.random() * 100;
            document.getElementById('eth-price').textContent = '$' + ethPrice.toFixed(0);
            document.getElementById('eth-current').textContent = '$' + ethPrice.toFixed(0);

            // Update BNB price
            const bnbPrice = 420 + Math.random() * 10;
            document.getElementById('bnb-price').textContent = '$' + bnbPrice.toFixed(0);

            // Update SOL price
            const solPrice = 100 + Math.random() * 10;
            document.getElementById('sol-price').textContent = '$' + solPrice.toFixed(0);
        }, 2000);

        // Add new orders periodically
        let orderCount = 2;
        setInterval(() => {
            const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'];
            const sides = ['BUY', 'SELL'];
            const symbol = symbols[Math.floor(Math.random() * symbols.length)];
            const side = sides[Math.floor(Math.random() * sides.length)];

            const newRow = document.getElementById('orders').insertRow(0);
            const time = new Date().toLocaleTimeString();

            newRow.innerHTML = `
                <td>${time}</td>
                <td>${symbol}</td>
                <td class="${side === 'BUY' ? 'positive' : 'negative'}">${side}</td>
                <td>${(Math.random() * 0.5).toFixed(4)}</td>
                <td>$${(50000 + Math.random() * 5000).toFixed(0)}</td>
                <td>✅ Filled</td>
            `;

            // Keep only last 5 orders
            if (document.getElementById('orders').rows.length > 5) {
                document.getElementById('orders').deleteRow(5);
            }
        }, 10000);
    </script>
</body>
</html>
"""


@app.get("/")
async def home():
    """Home page with dashboard"""
    return HTMLResponse(content=dashboard_html)


@app.get("/api/positions")
async def get_positions():
    """Get current positions"""
    return positions


@app.get("/api/orders")
async def get_orders():
    """Get recent orders"""
    # Generate some mock orders
    mock_orders = []
    for i in range(5):
        mock_orders.append(
            {
                "time": datetime.now(UTC).isoformat(),
                "symbol": random.choice(["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]),
                "side": random.choice(["buy", "sell"]),
                "quantity": round(random.random() * 0.5, 4),
                "price": round(50000 + random.random() * 5000, 2),
                "status": "filled",
            }
        )
    return mock_orders


@app.get("/api/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "mode": "demo",
        "message": "Sofia V2 Demo Mode - No Docker Required",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time data"""
    await websocket.accept()
    try:
        while True:
            # Send mock tick data
            data = {
                "type": "tick",
                "symbol": random.choice(["BTCUSDT", "ETHUSDT"]),
                "price": round(50000 + random.random() * 5000, 2),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await websocket.send_json(data)
            await asyncio.sleep(1)
    except:
        pass


def main():
    """Run the demo server"""
    print("=" * 60)
    print("Sofia V2 Quick Demo - Docker Olmadan Çalışan Demo")
    print("=" * 60)
    print("\n[INFO] Starting demo server...")
    print("[INFO] No Docker required!")
    print("\n[SUCCESS] Server starting at: http://localhost:8000")
    print("\n[INFO] Features:")
    print("  • Live dashboard with real-time updates")
    print("  • Mock trading data")
    print("  • WebSocket streaming")
    print("  • REST API endpoints")
    print("\n[INFO] Press Ctrl+C to stop")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
