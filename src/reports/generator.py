"""
HTML report generator for backtests using Jinja2
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime
from jinja2 import Template


class ReportGenerator:
    """Generate HTML reports for backtest results"""
    
    def __init__(self):
        self.template = self._load_template()
        self.reports_dir = Path('outputs/reports')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_template(self) -> Template:
        """Load HTML template"""
        template_str = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report #{{ job_id }} - {{ strategy_name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
        }
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        .header .meta {
            opacity: 0.9;
            font-size: 0.9rem;
        }
        .content {
            padding: 2rem;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: #f7f9fc;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .metric-card .label {
            color: #718096;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .metric-card .value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2d3748;
        }
        .metric-card.positive .value { color: #48bb78; }
        .metric-card.negative .value { color: #f56565; }
        .section {
            margin-bottom: 2rem;
        }
        .section h2 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 0.5rem;
        }
        .chart-container {
            background: #f7f9fc;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }
        #equityChart, #drawdownChart {
            width: 100%;
            height: 300px;
        }
        .trades-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .trades-table th {
            background: #f7f9fc;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
        }
        .trades-table td {
            padding: 0.75rem;
            border-bottom: 1px solid #e2e8f0;
        }
        .trades-table tr:hover {
            background: #f7f9fc;
        }
        .win { color: #48bb78; font-weight: 600; }
        .loss { color: #f56565; font-weight: 600; }
        .params-box {
            background: #f7f9fc;
            padding: 1rem;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }
        .footer {
            background: #f7f9fc;
            padding: 1.5rem 2rem;
            text-align: center;
            color: #718096;
            font-size: 0.875rem;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Backtest Report #{{ job_id }}</h1>
            <div class="meta">
                <div>Strategy: {{ strategy_name }} | Symbol: {{ symbol }}</div>
                <div>Generated: {{ generated_at }}</div>
            </div>
        </div>
        
        <div class="content">
            <!-- Key Metrics -->
            <div class="metrics-grid">
                <div class="metric-card {{ 'positive' if metrics.total_return > 0 else 'negative' }}">
                    <div class="label">Total Return</div>
                    <div class="value">{{ "%.2f"|format(metrics.total_return) }}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">CAGR</div>
                    <div class="value">{{ "%.2f"|format(metrics.cagr) }}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">Sharpe Ratio</div>
                    <div class="value">{{ "%.2f"|format(metrics.sharpe_ratio) }}</div>
                </div>
                <div class="metric-card negative">
                    <div class="label">Max Drawdown</div>
                    <div class="value">-{{ "%.2f"|format(metrics.max_drawdown) }}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">Win Rate</div>
                    <div class="value">{{ "%.1f"|format(metrics.win_rate) }}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">Total Trades</div>
                    <div class="value">{{ metrics.total_trades }}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Avg Trade</div>
                    <div class="value">{{ "%.2f"|format(metrics.avg_trade) }}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">MAR Ratio</div>
                    <div class="value">{{ "%.2f"|format(metrics.mar_ratio) }}</div>
                </div>
            </div>
            
            <!-- Strategy Parameters -->
            <div class="section">
                <h2>Strategy Parameters</h2>
                <div class="params-box">{{ params_json }}</div>
            </div>
            
            <!-- Equity Curve -->
            <div class="section">
                <h2>Equity Curve</h2>
                <div class="chart-container">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>
            
            <!-- Drawdown Chart -->
            <div class="section">
                <h2>Drawdown</h2>
                <div class="chart-container">
                    <canvas id="drawdownChart"></canvas>
                </div>
            </div>
            
            <!-- Recent Trades -->
            {% if trades_data %}
            <div class="section">
                <h2>Recent Trades</h2>
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Type</th>
                            <th>Price</th>
                            <th>Quantity</th>
                            <th>P&L</th>
                            <th>P&L %</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for trade in trades_data[-20:] %}
                        <tr>
                            <td>{{ trade.timestamp }}</td>
                            <td>{{ trade.type }}</td>
                            <td>${{ "%.2f"|format(trade.price) }}</td>
                            <td>{{ "%.4f"|format(trade.quantity) }}</td>
                            <td class="{{ 'win' if trade.pnl > 0 else 'loss' if trade.pnl < 0 else '' }}">
                                {% if trade.pnl is defined %}
                                    ${{ "%.2f"|format(trade.pnl) }}
                                {% else %}
                                    -
                                {% endif %}
                            </td>
                            <td class="{{ 'win' if trade.pnl_pct > 0 else 'loss' if trade.pnl_pct < 0 else '' }}">
                                {% if trade.pnl_pct is defined %}
                                    {{ "%.2f"|format(trade.pnl_pct) }}%
                                {% else %}
                                    -
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            
            <!-- Performance Summary -->
            <div class="section">
                <h2>Performance Summary</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="label">Initial Capital</div>
                        <div class="value">${{ "%.2f"|format(metrics.initial_capital) }}</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">Final Capital</div>
                        <div class="value">${{ "%.2f"|format(metrics.final_capital) }}</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">Avg Win</div>
                        <div class="value">{{ "%.2f"|format(metrics.avg_win) }}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">Avg Loss</div>
                        <div class="value">{{ "%.2f"|format(metrics.avg_loss) }}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">Profit Factor</div>
                        <div class="value">{{ "%.2f"|format(metrics.profit_factor) }}</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">Exposure Time</div>
                        <div class="value">{{ "%.1f"|format(metrics.exposure_time) }}%</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Sofia V2 Backtest Report | Generated {{ generated_at }}
        </div>
    </div>
    
    <script>
        // Equity Chart
        const equityCtx = document.getElementById('equityChart').getContext('2d');
        new Chart(equityCtx, {
            type: 'line',
            data: {
                labels: {{ equity_labels | safe }},
                datasets: [{
                    label: 'Equity',
                    data: {{ equity_values | safe }},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(0);
                            }
                        }
                    }
                }
            }
        });
        
        // Drawdown Chart
        const drawdownCtx = document.getElementById('drawdownChart').getContext('2d');
        new Chart(drawdownCtx, {
            type: 'line',
            data: {
                labels: {{ equity_labels | safe }},
                datasets: [{
                    label: 'Drawdown',
                    data: {{ drawdown_values | safe }},
                    borderColor: '#f56565',
                    backgroundColor: 'rgba(245, 101, 101, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value.toFixed(1) + '%';
                            }
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
        '''
        return Template(template_str)
    
    def generate(
        self,
        job_id: int,
        strategy_name: str,
        params: Dict[str, Any],
        metrics: Dict[str, Any],
        equity_df: pd.DataFrame,
        trades_df: Optional[pd.DataFrame],
        symbol: str
    ) -> Path:
        """
        Generate HTML report for backtest
        
        Returns:
            Path to generated HTML file
        """
        
        # Prepare equity data for charts
        equity_labels = []
        equity_values = []
        drawdown_values = []
        
        if not equity_df.empty:
            # Sample data for performance (max 500 points)
            sample_rate = max(1, len(equity_df) // 500)
            sampled_df = equity_df.iloc[::sample_rate]
            
            equity_labels = [str(idx)[:19] for idx in sampled_df.index]  # Truncate timestamp
            equity_values = sampled_df['equity'].tolist()
            
            # Calculate drawdown
            rolling_max = sampled_df['equity'].cummax()
            drawdown = ((sampled_df['equity'] - rolling_max) / rolling_max * 100).fillna(0)
            drawdown_values = drawdown.tolist()
        
        # Prepare trades data
        trades_data = []
        if trades_df is not None and not trades_df.empty:
            trades_data = trades_df.to_dict('records')
            # Format timestamps
            for trade in trades_data:
                if 'timestamp' in trade:
                    trade['timestamp'] = str(trade['timestamp'])[:19]
        
        # Render template
        html = self.template.render(
            job_id=job_id,
            strategy_name=strategy_name,
            symbol=symbol,
            params_json=json.dumps(params, indent=2),
            metrics=metrics,
            equity_labels=json.dumps(equity_labels),
            equity_values=json.dumps(equity_values),
            drawdown_values=json.dumps(drawdown_values),
            trades_data=trades_data,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Save report
        report_path = self.reports_dir / f'{job_id}_report.html'
        with open(report_path, 'w') as f:
            f.write(html)
        
        return report_path