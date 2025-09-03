"""
Paper Trading Reports - Real-time P&L and EOD Reports
"""

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from jinja2 import Template

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
        total_value = Decimal(state["balance"])
        for pos in state["positions"].values():
            total_value += Decimal(pos["position_value"])
        initial_balance = Decimal(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
        total_return = (total_value - initial_balance) / initial_balance * 100
        returns = self._calculate_returns()
        sharpe = self._calculate_sharpe(returns) if returns else 0
        max_dd = self._calculate_max_drawdown()
        return {
            "timestamp": datetime.now().isoformat(),
            "cumulative_pnl": state["total_pnl"],
            "daily_pnl": state["daily_pnl"],
            "unrealized_pnl": state.get("unrealized_pnl", "0"),
            "balance": state["balance"],
            "total_value": str(total_value),
            "total_return_pct": float(total_return),
            "positions_count": len(state["positions"]),
            "trade_count": state["trade_count"],
            "win_rate": state.get("win_rate", 0) * 100,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "exposure": str(sum(Decimal(p["position_value"]) for p in state["positions"].values())),
            "k_factor": state.get("k_factor", "0.25"),
            "status": "running" if state.get("running", False) else "stopped",
        }

    def _get_empty_metrics(self) -> Dict[str, Any]:
        """Get empty metrics when runner not available"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cumulative_pnl": "0",
            "daily_pnl": "0",
            "unrealized_pnl": "0",
            "balance": os.getenv("PAPER_INITIAL_BALANCE", "10000"),
            "total_value": os.getenv("PAPER_INITIAL_BALANCE", "10000"),
            "total_return_pct": 0,
            "positions_count": 0,
            "trade_count": 0,
            "win_rate": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "exposure": "0",
            "k_factor": "0.25",
            "status": "not_started",
        }

    def _calculate_returns(self) -> List[float]:
        """Calculate returns series"""
        if not self.runner or not self.runner.orders:
            return []
        df = pd.DataFrame(
            [
                {
                    "timestamp": order.timestamp,
                    "pnl": (
                        float(order.filled_price - order.price) * float(order.quantity)
                        if order.side == "sell"
                        else 0
                    ),
                }
                for order in self.runner.orders
            ]
        )
        if df.empty:
            return []
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.floor("H")
        hourly_returns = df.groupby("hour")["pnl"].sum().tolist()
        return hourly_returns

    def _calculate_sharpe(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0
        returns_array = np.array(returns)
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
        initial_balance = float(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
        equity = [initial_balance]
        for order in sorted(self.runner.orders, key=lambda x: x.timestamp):
            if order.side == "buy":
                equity.append(equity[-1] - float(order.filled_price * order.quantity + order.fees))
            else:
                equity.append(equity[-1] + float(order.filled_price * order.quantity - order.fees))
        equity_array = np.array(equity)
        peak = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - peak) / peak
        return round(min(drawdown) * 100, 2)

    def generate_eod_report(self) -> str:
        """Generate end-of-day HTML report"""
        metrics = self.get_live_metrics()
        today_trades = []
        if self.runner:
            today = date.today()
            today_trades = [
                {
                    "time": order.timestamp.strftime("%H:%M:%S"),
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": str(order.quantity),
                    "price": str(order.filled_price),
                    "fees": str(order.fees),
                    "slippage": str(order.slippage),
                }
                for order in self.runner.orders
                if order.timestamp.date() == today
            ]
        template_str = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Paper Trading Report - {{ date }}</title>\n    <style>\n        body { font-family: \'Segoe UI\', Arial, sans-serif; margin: 20px; background: #f5f5f5; }\n        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; }\n        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }\n        .metric-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }\n        .metric-value { font-size: 28px; font-weight: bold; color: #2c3e50; margin: 10px 0; }\n        .metric-label { color: #7f8c8d; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }\n        .positive { color: #27ae60; }\n        .negative { color: #e74c3c; }\n        .neutral { color: #3498db; }\n        table { width: 100%; background: white; border-radius: 10px; overflow: hidden; margin: 20px 0; border-collapse: collapse; }\n        th { background: #34495e; color: white; padding: 12px; text-align: left; font-weight: 500; }\n        td { padding: 12px; border-bottom: 1px solid #ecf0f1; }\n        tr:hover { background: #f8f9fa; }\n        .chart-container { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; }\n        .status { display: inline-block; padding: 5px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }\n        .status.running { background: #d4edda; color: #155724; }\n        .status.stopped { background: #f8d7da; color: #721c24; }\n        .footer { text-align: center; color: #7f8c8d; margin-top: 40px; padding: 20px; }\n    </style>\n</head>\n<body>\n    <div class="header">\n        <h1>Paper Trading Report</h1>\n        <p>{{ date }} | Status: <span class="status {{ status }}">{{ status|upper }}</span></p>\n    </div>\n    \n    <div class="metrics-grid">\n        <div class="metric-card">\n            <div class="metric-label">Daily P&L</div>\n            <div class="metric-value {% if daily_pnl|float >= 0 %}positive{% else %}negative{% endif %}">\n                ${{ "%.2f"|format(daily_pnl|float) }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Total P&L</div>\n            <div class="metric-value {% if cumulative_pnl|float >= 0 %}positive{% else %}negative{% endif %}">\n                ${{ "%.2f"|format(cumulative_pnl|float) }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Total Return</div>\n            <div class="metric-value {% if total_return_pct >= 0 %}positive{% else %}negative{% endif %}">\n                {{ "%.2f"|format(total_return_pct) }}%\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Win Rate</div>\n            <div class="metric-value neutral">\n                {{ "%.1f"|format(win_rate) }}%\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Sharpe Ratio</div>\n            <div class="metric-value neutral">\n                {{ "%.2f"|format(sharpe_ratio) }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Max Drawdown</div>\n            <div class="metric-value negative">\n                {{ "%.2f"|format(max_drawdown) }}%\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Open Positions</div>\n            <div class="metric-value neutral">\n                {{ positions_count }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Total Trades</div>\n            <div class="metric-value neutral">\n                {{ trade_count }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Current Exposure</div>\n            <div class="metric-value neutral">\n                ${{ "%.2f"|format(exposure|float) }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">K-Factor</div>\n            <div class="metric-value neutral">\n                {{ k_factor }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Balance</div>\n            <div class="metric-value neutral">\n                ${{ "%.2f"|format(balance|float) }}\n            </div>\n        </div>\n        \n        <div class="metric-card">\n            <div class="metric-label">Total Value</div>\n            <div class="metric-value neutral">\n                ${{ "%.2f"|format(total_value|float) }}\n            </div>\n        </div>\n    </div>\n    \n    {% if trades %}\n    <h2>Today\'s Trades</h2>\n    <table>\n        <thead>\n            <tr>\n                <th>Time</th>\n                <th>Symbol</th>\n                <th>Side</th>\n                <th>Quantity</th>\n                <th>Price</th>\n                <th>Fees</th>\n                <th>Slippage</th>\n            </tr>\n        </thead>\n        <tbody>\n            {% for trade in trades %}\n            <tr>\n                <td>{{ trade.time }}</td>\n                <td>{{ trade.symbol }}</td>\n                <td class="{% if trade.side == \'buy\' %}positive{% else %}negative{% endif %}">\n                    {{ trade.side|upper }}\n                </td>\n                <td>{{ trade.quantity }}</td>\n                <td>${{ trade.price }}</td>\n                <td>${{ trade.fees }}</td>\n                <td>${{ trade.slippage }}</td>\n            </tr>\n            {% endfor %}\n        </tbody>\n    </table>\n    {% endif %}\n    \n    <div class="footer">\n        <p>Generated at {{ timestamp }}</p>\n        <p>Sofia Paper Trading System v1.0</p>\n    </div>\n</body>\n</html>\n        '
        template = Template(template_str)
        html = template.render(
            date=date.today(),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trades=today_trades,
            **metrics,
        )
        report_date = date.today().strftime("%Y-%m-%d")
        report_path = os.path.join(self.report_dir, report_date)
        os.makedirs(report_path, exist_ok=True)
        html_file = os.path.join(report_path, "eod_report.html")
        with open(html_file, "w") as f:
            f.write(html)
        logger.info(f"EOD report generated: {html_file}")
        return html_file

    def generate_csv_report(self) -> str:
        """Generate CSV report of trades"""
        if not self.runner or not self.runner.orders:
            return None
        df = pd.DataFrame(
            [
                {
                    "timestamp": order.timestamp,
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "type": order.order_type,
                    "quantity": float(order.quantity),
                    "price": float(order.price),
                    "filled_price": float(order.filled_price),
                    "fees": float(order.fees),
                    "slippage": float(order.slippage),
                    "status": order.status,
                }
                for order in self.runner.orders
            ]
        )
        report_date = date.today().strftime("%Y-%m-%d")
        report_path = os.path.join(self.report_dir, report_date)
        os.makedirs(report_path, exist_ok=True)
        csv_file = os.path.join(report_path, "trades.csv")
        df.to_csv(csv_file, index=False)
        logger.info(f"CSV report generated: {csv_file}")
        return csv_file

    def check_profitability_alert(self) -> Optional[Dict[str, Any]]:
        """Check if profitability alerts should be triggered"""
        metrics = self.get_live_metrics()
        alerts = []
        daily_pnl = float(metrics["daily_pnl"])
        max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "200"))
        if daily_pnl < -max_daily_loss:
            alerts.append(
                {
                    "type": "critical",
                    "message": f"Daily loss limit breached: ${daily_pnl:.2f}",
                    "action": "kill_switch_activate",
                }
            )
        elif daily_pnl < -max_daily_loss * 0.8:
            alerts.append(
                {
                    "type": "warning",
                    "message": f"Approaching daily loss limit: ${daily_pnl:.2f}",
                    "action": "reduce_exposure",
                }
            )
        max_dd = metrics["max_drawdown"]
        if max_dd < -20:
            alerts.append(
                {
                    "type": "warning",
                    "message": f"High drawdown detected: {max_dd:.2f}%",
                    "action": "review_strategy",
                }
            )
        win_rate = metrics["win_rate"]
        if metrics["trade_count"] > 10 and win_rate < 40:
            alerts.append(
                {
                    "type": "warning",
                    "message": f"Low win rate: {win_rate:.1f}%",
                    "action": "review_signals",
                }
            )
        if alerts:
            return {"timestamp": datetime.now().isoformat(), "alerts": alerts, "metrics": metrics}
        return None
