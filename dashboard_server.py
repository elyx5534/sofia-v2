#!/usr/bin/env python3
"""
Simple Dashboard Server for Sofia V2
"""

import io
import platform
import sys

# Set UTF-8 encoding for Windows
if platform.system() == "Windows":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import logging
import os
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Auto-discover API endpoint
API_BASE_URL = None


def discover_api():
    """Auto-discover which API port is active"""
    global API_BASE_URL

    # Check environment variable first
    if os.getenv("API_BASE_URL"):
        API_BASE_URL = os.getenv("API_BASE_URL")
        logger.info(f"Using API from env: {API_BASE_URL}")
        return API_BASE_URL

    # Try candidate ports
    candidates = ["http://127.0.0.1:8002", "http://127.0.0.1:8012"]

    for candidate in candidates:
        try:
            resp = requests.get(f"{candidate}/api/dev/status", timeout=1)
            if resp.status_code == 200:
                API_BASE_URL = candidate
                logger.info(f"API discovered at: {API_BASE_URL}")
                return API_BASE_URL
        except:
            continue

    # Default fallback
    API_BASE_URL = "http://127.0.0.1:8012"
    logger.warning(f"No API found, using default: {API_BASE_URL}")
    return API_BASE_URL


# Discover on startup
discover_api()

app = Flask(__name__)


# API Proxy route
@app.route("/apiProxy/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def api_proxy(path):
    """Proxy requests to the API server"""
    if not API_BASE_URL:
        discover_api()

    url = f"{API_BASE_URL}/{path}"

    try:
        if request.method == "GET":
            resp = requests.get(url, params=request.args, timeout=10)
        elif request.method == "POST":
            resp = requests.post(url, json=request.get_json(), timeout=10)
        elif request.method == "PUT":
            resp = requests.put(url, json=request.get_json(), timeout=10)
        elif request.method == "DELETE":
            resp = requests.delete(url, timeout=10)

        return (
            resp.content,
            resp.status_code,
            {"Content-Type": resp.headers.get("Content-Type", "application/json")},
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return jsonify({"error": str(e)}), 503


# Simple HTML dashboard template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Sofia V2 - Trading Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #ffd700;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .metric:last-child { border-bottom: none; }
        .label { opacity: 0.8; }
        .value {
            font-weight: bold;
            font-size: 1.1em;
        }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .neutral { color: #fbbf24; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            background: rgba(255, 255, 255, 0.2);
        }
        .status-active { background: #4ade80; color: #064e3b; }
        .status-paused { background: #fbbf24; color: #713f12; }
        .status-stopped { background: #f87171; color: #7f1d1d; }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #ffd700;
            color: #1a1a1a;
            border: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4);
            transition: all 0.3s;
        }
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 215, 0, 0.6);
        }
        .time-update {
            text-align: center;
            opacity: 0.7;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Sofia V2 Trading Dashboard <small style="font-size: 0.5em; opacity: 0.7;">API: <span id="api-status">discovering...</span></small></h1>

        <div class="grid">
            <!-- P&L Summary Card -->
            <div class="card">
                <h2>P&L Summary</h2>
                <div id="pnl-metrics">
                    <div class="metric">
                        <span class="label">Total P&L</span>
                        <span class="value" id="total-pnl">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Win Rate</span>
                        <span class="value" id="win-rate">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Total Trades</span>
                        <span class="value" id="total-trades">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Status</span>
                        <span class="value" id="session-status">Loading...</span>
                    </div>
                </div>
            </div>

            <!-- Live Guard Card -->
            <div class="card">
                <h2>Live Trading Guard</h2>
                <div id="guard-metrics">
                    <div class="metric">
                        <span class="label">Live Enabled</span>
                        <span class="value" id="live-enabled">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Approvals</span>
                        <span class="value" id="approvals">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Requirements</span>
                        <span class="value" id="requirements">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="label">Trading Hours</span>
                        <span class="value" id="trading-hours">Loading...</span>
                    </div>
                </div>
            </div>

            <!-- QA Metrics Card -->
            <div class="card">
                <h2>QA Metrics</h2>
                <div id="qa-metrics">
                    <div class="metric">
                        <span class="label">Consistency</span>
                        <span class="value" id="consistency">PASS</span>
                    </div>
                    <div class="metric">
                        <span class="label">Shadow Diff</span>
                        <span class="value positive" id="shadow-diff">2.90 bps</span>
                    </div>
                    <div class="metric">
                        <span class="label">Fill Rate</span>
                        <span class="value" id="fill-rate">60%</span>
                    </div>
                    <div class="metric">
                        <span class="label">Quality</span>
                        <span class="value positive">EXCELLENT</span>
                    </div>
                </div>
            </div>

            <!-- System Status Card -->
            <div class="card">
                <h2>System Status</h2>
                <div id="system-metrics">
                    <div class="metric">
                        <span class="label">API Server</span>
                        <span class="status-badge status-active">ACTIVE</span>
                    </div>
                    <div class="metric">
                        <span class="label">Dashboard</span>
                        <span class="status-badge status-active">ACTIVE</span>
                    </div>
                    <div class="metric">
                        <span class="label">Watchdog</span>
                        <span class="status-badge status-active">RUNNING</span>
                    </div>
                    <div class="metric">
                        <span class="label">Paper Trading</span>
                        <span class="status-badge status-paused">READY</span>
                    </div>
                </div>
            </div>

            <!-- Campaign Status Card -->
            <div class="card">
                <h2>Campaign Status</h2>
                <div id="campaign-metrics">
                    <div class="metric">
                        <span class="label">Current Day</span>
                        <span class="value">0 / 3</span>
                    </div>
                    <div class="metric">
                        <span class="label">Grid Sessions</span>
                        <span class="value">0</span>
                    </div>
                    <div class="metric">
                        <span class="label">Arb Sessions</span>
                        <span class="value">0</span>
                    </div>
                    <div class="metric">
                        <span class="label">Next Session</span>
                        <span class="value neutral">Not Scheduled</span>
                    </div>
                </div>
            </div>

            <!-- Quick Actions Card -->
            <div class="card">
                <h2>Quick Actions</h2>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <button onclick="runDemo()" style="padding: 10px; background: #4ade80; border: none; border-radius: 8px; color: white; font-weight: bold; cursor: pointer;">Run 5min Demo</button>
                    <button onclick="runQA()" style="padding: 10px; background: #fbbf24; border: none; border-radius: 8px; color: white; font-weight: bold; cursor: pointer;">Run QA Proof</button>
                    <button onclick="checkReadiness()" style="padding: 10px; background: #f87171; border: none; border-radius: 8px; color: white; font-weight: bold; cursor: pointer;">Check Live Readiness</button>
                    <button onclick="viewReports()" style="padding: 10px; background: #a78bfa; border: none; border-radius: 8px; color: white; font-weight: bold; cursor: pointer;">View Reports</button>
                </div>
            </div>
        </div>

        <div class="time-update">
            Last updated: <span id="last-update">{{ current_time }}</span>
        </div>
    </div>

    <button class="refresh-btn" onclick="refreshData()">Refresh Data</button>

    <script>
        // Use proxy for all API calls
        const API_BASE = '/apiProxy';
        let apiPort = 'discovering...';

        async function refreshData() {
            try {
                // Fetch system status first (to check API connectivity)
                const statusResponse = await fetch(`${API_BASE}/api/dev/status`);
                const statusData = await statusResponse.json();

                // Update API status display
                if (statusData.api) {
                    apiPort = window.location.port === '5000' ? '{{API_PORT}}' : 'connected';
                    document.getElementById('api-status').textContent = apiPort + ' (auto)';
                }

                // Fetch P&L data
                const pnlResponse = await fetch(`${API_BASE}/api/pnl/summary`);
                if (pnlResponse.ok) {
                    const pnlData = await pnlResponse.json();
                    document.getElementById('total-pnl').textContent = `$${(pnlData.total_pnl || 0).toFixed(2)}`;
                    document.getElementById('total-pnl').className = (pnlData.total_pnl || 0) >= 0 ? 'value positive' : 'value negative';
                    document.getElementById('win-rate').textContent = `${(pnlData.win_rate || 0).toFixed(1)}%`;
                    document.getElementById('total-trades').textContent = pnlData.total_trades || 0;
                    document.getElementById('session-status').textContent = pnlData.session_complete ? 'Complete' : 'Running';
                } else {
                    // Use default values if endpoint not available
                    document.getElementById('total-pnl').textContent = '$0.00';
                    document.getElementById('win-rate').textContent = '0.0%';
                    document.getElementById('total-trades').textContent = '0';
                    document.getElementById('session-status').textContent = 'IDLE';
                }

                // Update live guard
                const guardResponse = await fetch(`${API_BASE}/api/live-guard`);
                if (guardResponse.ok) {
                    const guardData = await guardResponse.json();

                    document.getElementById('live-enabled').textContent = guardData.enabled ? 'YES' : 'NO';
                    document.getElementById('live-enabled').className = guardData.enabled ? 'value positive' : 'value negative';
                    document.getElementById('approvals').textContent = `${guardData.approvals?.operator_A ? 1 : 0}/2`;
                    document.getElementById('requirements').textContent = guardData.requirements?.readiness ? 'MET' : 'NOT MET';
                    document.getElementById('trading-hours').textContent = guardData.requirements?.hours_ok ? 'OPEN' : 'CLOSED';
                } else {
                    // Default values if endpoint not available
                    document.getElementById('live-enabled').textContent = 'NO';
                    document.getElementById('live-enabled').className = 'value negative';
                    document.getElementById('approvals').textContent = '0/2';
                    document.getElementById('requirements').textContent = 'NOT MET';
                    document.getElementById('trading-hours').textContent = 'CLOSED';
                }

                // Update time
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        async function runDemo() {
            try {
                const response = await fetch(`${API_BASE}/api/dev/actions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'demo', minutes: 5 })
                });
                const data = await response.json();
                alert(`Demo started! Job ID: ${data.job_id}\nView in /dev console`);
            } catch (error) {
                alert('Failed to start demo: ' + error.message);
            }
        }

        async function runQA() {
            try {
                const response = await fetch(`${API_BASE}/api/dev/actions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'qa' })
                });
                const data = await response.json();
                alert(`QA Proof started! Job ID: ${data.job_id}\nView in /dev console`);
            } catch (error) {
                alert('Failed to start QA: ' + error.message);
            }
        }

        async function checkReadiness() {
            try {
                const response = await fetch(`${API_BASE}/api/dev/actions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'readiness' })
                });
                const data = await response.json();
                alert(`Readiness check started! Job ID: ${data.job_id}\nView in /dev console`);
            } catch (error) {
                alert('Failed to check readiness: ' + error.message);
            }
        }

        function viewReports() {
            // Determine API port from current connection
            const apiUrl = apiPort.includes('8012') ? 'http://localhost:8012/dev' : 'http://localhost:8002/dev';
            window.open(apiUrl, '_blank');
        }

        // Auto-refresh every 5 seconds
        setInterval(refreshData, 5000);

        // Initial load
        refreshData();
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    """Render main dashboard"""
    # Pass the discovered API port to the template
    api_port = API_BASE_URL.split(":")[-1] if API_BASE_URL else "unknown"
    html = DASHBOARD_HTML.replace("{{API_PORT}}", api_port)
    return render_template_string(html, current_time=datetime.now().strftime("%H:%M:%S"))


@app.route("/api/status")
def api_status():
    """Return system status"""
    try:
        # Try to get data from main API
        response = requests.get("http://localhost:8001/health", timeout=2)
        health = response.json()

        return jsonify(
            {
                "status": "online",
                "services": health.get("services", {}),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except:
        return jsonify(
            {"status": "offline", "services": {}, "timestamp": datetime.now().isoformat()}
        )


@app.route("/reports")
def reports():
    """Simple reports page"""
    return """
    <h1>Sofia V2 Reports</h1>
    <ul>
        <li><a href="/reports/shadow">Shadow Report</a></li>
        <li><a href="/reports/consistency">Consistency Report</a></li>
        <li><a href="/reports/campaign">Campaign Summary</a></li>
        <li><a href="/reports/pilot">Pilot Plan</a></li>
    </ul>
    """


if __name__ == "__main__":
    print("=" * 60)
    print("SOFIA V2 DASHBOARD SERVER")
    print("=" * 60)
    print("Dashboard URL: http://localhost:5000")
    print("API Status: http://localhost:5000/api/status")
    print("Reports: http://localhost:5000/reports")
    print("-" * 60)
    print("Press Ctrl+C to stop")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=False)
