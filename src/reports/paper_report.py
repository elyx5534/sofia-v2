"""
Paper Trading Reports - Real-time P&L and EOD Reports
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from jinja2 import Template
import asyncio

logger = logging.getLogger(__name__)


class PaperTradingReport:
    """Generate paper trading reports"""
    
    def __init__(self, runner=None):
        self.runner = runner
        self.report_dir = "reports/paper"
        os.makedirs(self.report_dir, exist_ok=True)
        
    def get_live_metrics(self) -> Dict[str, Any]:
        """Get real-time trading metrics"""
        if not self.runner:
            return self._get_empty_metrics()
        
        state = self.runner.get_state()
        
        # Calculate metrics
        total_value = Decimal(state['balance'])
        for pos in state['positions'].values():
            total_value += Decimal(pos['position_value'])
        
        initial_balance = Decimal(os.getenv('PAPER_INITIAL_BALANCE', '10000'))
        total_return = ((total_value - initial_balance) / initial_balance) * 100
        
        # Calculate Sharpe ratio (simplified - intraday)
        returns = self._calculate_returns()
        sharpe = self._calculate_sharpe(returns) if returns else 0
        
        # Calculate max drawdown
        max_dd = self._calculate_max_drawdown()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cumulative_pnl': state['total_pnl'],
            'daily_pnl': state['daily_pnl'],
            'unrealized_pnl': state.get('unrealized_pnl', '0'),
            'balance': state['balance'],
            'total_value': str(total_value),
            'total_return_pct': float(total_return),
            'positions_count': len(state['positions']),
            'trade_count': state['trade_count'],
            'win_rate': state.get('win_rate', 0) * 100,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'exposure': str(sum(Decimal(p['position_value']) for p in state['positions'].values())),
            'k_factor': state.get('k_factor', '0.25'),
            'status': 'running' if state.get('running', False) else 'stopped'
        }
    
    def _get_empty_metrics(self) -> Dict[str, Any]:
        """Get empty metrics when runner not available"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cumulative_pnl': '0',
            'daily_pnl': '0',
            'unrealized_pnl': '0',
            'balance': os.getenv('PAPER_INITIAL_BALANCE', '10000'),
            'total_value': os.getenv('PAPER_INITIAL_BALANCE', '10000'),
            'total_return_pct': 0,
            'positions_count': 0,
            'trade_count': 0,
            'win_rate': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'exposure': '0',
            'k_factor': '0.25',
            'status': 'not_started'
        }
    
    def _calculate_returns(self) -> List[float]:
        """Calculate returns series"""
        if not self.runner or not self.runner.orders:
            return []
        
        # Group orders by time buckets (hourly)
        df = pd.DataFrame([
            {
                'timestamp': order.timestamp,
                'pnl': float(order.filled_price - order.price) * float(order.quantity) 
                       if order.side == 'sell' else 0
            }
            for order in self.runner.orders
        ])
        
        if df.empty:
            return []
        
        df['hour'] = pd.to_datetime(df['timestamp']).dt.floor('H')
        hourly_returns = df.groupby('hour')['pnl'].sum().tolist()
        
        return hourly_returns
    
    def _calculate_sharpe(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        
        # Annualized (assuming hourly returns, 24*365 hours per year)
        mean_return = np.mean(returns_array) * 24 * 365
        std_return = np.std(returns_array) * np.sqrt(24 * 365)
        
        if std_return == 0:
            return 0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return round(sharpe, 2)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.runner or not self.runner.orders:
            return 0
        
        # Build equity curve
        initial_balance = float(os.getenv('PAPER_INITIAL_BALANCE', '10000'))
        equity = [initial_balance]
        
        for order in sorted(self.runner.orders, key=lambda x: x.timestamp):
            if order.side == 'buy':
                equity.append(equity[-1] - float(order.filled_price * order.quantity + order.fees))
            else:
                equity.append(equity[-1] + float(order.filled_price * order.quantity - order.fees))
        
        # Calculate drawdown
        equity_array = np.array(equity)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        
        return round(min(drawdown) * 100, 2)
    
    def generate_eod_report(self) -> str:
        """Generate end-of-day HTML report"""
        metrics = self.get_live_metrics()
        
        # Get trades for the day
        today_trades = []
        if self.runner:
            today = date.today()
            today_trades = [
                {
                    'time': order.timestamp.strftime('%H:%M:%S'),
                    'symbol': order.symbol,
                    'side': order.side,
                    'quantity': str(order.quantity),
                    'price': str(order.filled_price),
                    'fees': str(order.fees),
                    'slippage': str(order.slippage)
                }
                for order in self.runner.orders
                if order.timestamp.date() == today
            ]
        
        # HTML template
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Paper Trading Report - {{ date }}</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }
        .metric-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .metric-value { font-size: 28px; font-weight: bold; color: #2c3e50; margin: 10px 0; }
        .metric-label { color: #7f8c8d; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .positive { color: #27ae60; }
        .negative { color: #e74c3c; }
        .neutral { color: #3498db; }
        table { width: 100%; background: white; border-radius: 10px; overflow: hidden; margin: 20px 0; border-collapse: collapse; }
        th { background: #34495e; color: white; padding: 12px; text-align: left; font-weight: 500; }
        td { padding: 12px; border-bottom: 1px solid #ecf0f1; }
        tr:hover { background: #f8f9fa; }
        .chart-container { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .status { display: inline-block; padding: 5px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .status.running { background: #d4edda; color: #155724; }
        .status.stopped { background: #f8d7da; color: #721c24; }
        .footer { text-align: center; color: #7f8c8d; margin-top: 40px; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Paper Trading Report</h1>
        <p>{{ date }} | Status: <span class="status {{ status }}">{{ status|upper }}</span></p>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">Daily P&L</div>
            <div class="metric-value {% if daily_pnl|float >= 0 %}positive{% else %}negative{% endif %}">
                ${{ "%.2f"|format(daily_pnl|float) }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Total P&L</div>
            <div class="metric-value {% if cumulative_pnl|float >= 0 %}positive{% else %}negative{% endif %}">
                ${{ "%.2f"|format(cumulative_pnl|float) }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Total Return</div>
            <div class="metric-value {% if total_return_pct >= 0 %}positive{% else %}negative{% endif %}">
                {{ "%.2f"|format(total_return_pct) }}%
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value neutral">
                {{ "%.1f"|format(win_rate) }}%
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value neutral">
                {{ "%.2f"|format(sharpe_ratio) }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-value negative">
                {{ "%.2f"|format(max_drawdown) }}%
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Open Positions</div>
            <div class="metric-value neutral">
                {{ positions_count }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value neutral">
                {{ trade_count }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Current Exposure</div>
            <div class="metric-value neutral">
                ${{ "%.2f"|format(exposure|float) }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">K-Factor</div>
            <div class="metric-value neutral">
                {{ k_factor }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Balance</div>
            <div class="metric-value neutral">
                ${{ "%.2f"|format(balance|float) }}
            </div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">Total Value</div>
            <div class="metric-value neutral">
                ${{ "%.2f"|format(total_value|float) }}
            </div>
        </div>
    </div>
    
    {% if trades %}
    <h2>Today's Trades</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Quantity</th>
                <th>Price</th>
                <th>Fees</th>
                <th>Slippage</th>
            </tr>
        </thead>
        <tbody>
            {% for trade in trades %}
            <tr>
                <td>{{ trade.time }}</td>
                <td>{{ trade.symbol }}</td>
                <td class="{% if trade.side == 'buy' %}positive{% else %}negative{% endif %}">
                    {{ trade.side|upper }}
                </td>
                <td>{{ trade.quantity }}</td>
                <td>${{ trade.price }}</td>
                <td>${{ trade.fees }}</td>
                <td>${{ trade.slippage }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
    
    <div class="footer">
        <p>Generated at {{ timestamp }}</p>
        <p>Sofia Paper Trading System v1.0</p>
    </div>
</body>
</html>
        """
        
        template = Template(template_str)
        html = template.render(
            date=date.today(),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            trades=today_trades,
            **metrics
        )
        
        # Save report
        report_date = date.today().strftime('%Y-%m-%d')
        report_path = os.path.join(self.report_dir, report_date)
        os.makedirs(report_path, exist_ok=True)
        
        html_file = os.path.join(report_path, 'eod_report.html')
        with open(html_file, 'w') as f:
            f.write(html)
        
        logger.info(f"EOD report generated: {html_file}")
        
        return html_file
    
    def generate_csv_report(self) -> str:
        """Generate CSV report of trades"""
        if not self.runner or not self.runner.orders:
            return None
        
        # Create DataFrame from orders
        df = pd.DataFrame([
            {
                'timestamp': order.timestamp,
                'order_id': order.order_id,
                'symbol': order.symbol,
                'side': order.side,
                'type': order.order_type,
                'quantity': float(order.quantity),
                'price': float(order.price),
                'filled_price': float(order.filled_price),
                'fees': float(order.fees),
                'slippage': float(order.slippage),
                'status': order.status
            }
            for order in self.runner.orders
        ])
        
        # Save CSV
        report_date = date.today().strftime('%Y-%m-%d')
        report_path = os.path.join(self.report_dir, report_date)
        os.makedirs(report_path, exist_ok=True)
        
        csv_file = os.path.join(report_path, 'trades.csv')
        df.to_csv(csv_file, index=False)
        
        logger.info(f"CSV report generated: {csv_file}")
        
        return csv_file
    
    def check_profitability_alert(self) -> Optional[Dict[str, Any]]:
        """Check if profitability alerts should be triggered"""
        metrics = self.get_live_metrics()
        
        alerts = []
        
        # Check daily loss limit
        daily_pnl = float(metrics['daily_pnl'])
        max_daily_loss = float(os.getenv('MAX_DAILY_LOSS', '200'))
        
        if daily_pnl < -max_daily_loss:
            alerts.append({
                'type': 'critical',
                'message': f"Daily loss limit breached: ${daily_pnl:.2f}",
                'action': 'kill_switch_activate'
            })
        elif daily_pnl < -max_daily_loss * 0.8:
            alerts.append({
                'type': 'warning',
                'message': f"Approaching daily loss limit: ${daily_pnl:.2f}",
                'action': 'reduce_exposure'
            })
        
        # Check drawdown
        max_dd = metrics['max_drawdown']
        if max_dd < -20:
            alerts.append({
                'type': 'warning',
                'message': f"High drawdown detected: {max_dd:.2f}%",
                'action': 'review_strategy'
            })
        
        # Check win rate
        win_rate = metrics['win_rate']
        if metrics['trade_count'] > 10 and win_rate < 40:
            alerts.append({
                'type': 'warning',
                'message': f"Low win rate: {win_rate:.1f}%",
                'action': 'review_signals'
            })
        
        if alerts:
            return {
                'timestamp': datetime.now().isoformat(),
                'alerts': alerts,
                'metrics': metrics
            }
        
        return None