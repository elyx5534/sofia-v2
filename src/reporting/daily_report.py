"""
Daily Trading Report Generator with Telegram/Discord Integration
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """Generate and send daily trading reports"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DailyReport")
        self.report_time = "16:00"
        self._scheduler_task = None

    async def start_scheduler(self):
        """Start daily report scheduler"""
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info(f"Daily report scheduler started - reports at {self.report_time} UTC")

    async def stop_scheduler(self):
        """Stop daily report scheduler"""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Daily report scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while True:
            try:
                now = datetime.utcnow()
                report_hour, report_minute = map(int, self.report_time.split(":"))
                next_report = now.replace(
                    hour=report_hour, minute=report_minute, second=0, microsecond=0
                )
                if now >= next_report:
                    next_report += timedelta(days=1)
                wait_seconds = (next_report - now).total_seconds()
                self.logger.info(f"Next report in {wait_seconds / 3600:.1f} hours")
                await asyncio.sleep(wait_seconds)
                await self.generate_and_send_report()
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(3600)

    async def generate_and_send_report(self):
        """Generate and send daily report"""
        try:
            report_data = await self._collect_report_data()
            text_report = self._generate_text_report(report_data)
            html_report = self._generate_html_report(report_data)
            await self._save_report(report_data, text_report, html_report)
            await self._send_telegram_report(text_report, report_data)
            await self._send_discord_report(report_data)
            self.logger.info("Daily report generated and sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")

    async def _collect_report_data(self) -> Dict:
        """Collect data for daily report"""
        data = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            pnl_file = Path("logs/pnl_summary.json")
            if pnl_file.exists():
                with open(pnl_file) as f:
                    pnl_data = json.load(f)
                    data["pnl"] = {
                        "daily_pnl": pnl_data.get("daily_pnl", 0),
                        "daily_pnl_pct": pnl_data.get("pnl_percentage", 0),
                        "realized_pnl": pnl_data.get("realized_pnl", 0),
                        "unrealized_pnl": pnl_data.get("unrealized_pnl", 0),
                        "initial_capital": pnl_data.get("initial_capital", 10000),
                        "final_capital": pnl_data.get("final_capital", 10000),
                    }
        except Exception as e:
            self.logger.warning(f"Failed to load P&L data: {e}")
            data["pnl"] = self._default_pnl_data()
        try:
            trades_file = Path("logs/trades.jsonl")
            if trades_file.exists():
                trades = []
                with open(trades_file) as f:
                    for line in f:
                        trades.append(json.loads(line))
                today_trades = [
                    t for t in trades if t.get("timestamp", "").startswith(data["date"])
                ]
                winning_trades = [t for t in today_trades if t.get("pnl", 0) > 0]
                data["trades"] = {
                    "total_trades": len(today_trades),
                    "winning_trades": len(winning_trades),
                    "losing_trades": len(today_trades) - len(winning_trades),
                    "win_rate": (
                        len(winning_trades) / len(today_trades) * 100 if today_trades else 0
                    ),
                    "largest_win": max([t.get("pnl", 0) for t in winning_trades], default=0),
                    "largest_loss": min([t.get("pnl", 0) for t in today_trades], default=0),
                    "average_pnl": (
                        sum(t.get("pnl", 0) for t in today_trades) / len(today_trades)
                        if today_trades
                        else 0
                    ),
                }
        except Exception as e:
            self.logger.warning(f"Failed to load trade data: {e}")
            data["trades"] = self._default_trade_data()
        try:
            watchdog_file = Path("logs/system_state.json")
            if watchdog_file.exists():
                with open(watchdog_file) as f:
                    watchdog_data = json.load(f)
                    data["system"] = {
                        "status": watchdog_data.get("status", "UNKNOWN"),
                        "error_count": watchdog_data.get("error_count", 0),
                        "clock_skew_ms": watchdog_data.get("clock_skew_ms", 0),
                        "rate_limit_hits": watchdog_data.get("rate_limit_hits", 0),
                    }
            else:
                data["system"] = self._default_system_data()
            fill_metrics_file = Path("logs/fill_metrics.json")
            if fill_metrics_file.exists():
                with open(fill_metrics_file) as f:
                    fill_data = json.load(f)
                    data["fills"] = {
                        "maker_fill_rate": fill_data.get("maker_fill_rate", 0),
                        "avg_fill_time_ms": fill_data.get("avg_time_to_fill_ms", 0),
                        "partial_fills": fill_data.get("partial_fill_count", 0),
                        "cancelled_orders": fill_data.get("cancelled_orders", 0),
                    }
            else:
                data["fills"] = self._default_fill_data()
        except Exception as e:
            self.logger.warning(f"Failed to load system data: {e}")
            data["system"] = self._default_system_data()
            data["fills"] = self._default_fill_data()
        try:
            data["risk"] = {
                "max_drawdown": self._calculate_max_drawdown(data.get("pnl", {})),
                "sharpe_ratio": self._calculate_sharpe_ratio(
                    trades if "trades" in locals() else []
                ),
                "risk_status": "NORMAL",
            }
        except Exception as e:
            self.logger.warning(f"Failed to calculate risk metrics: {e}")
            data["risk"] = self._default_risk_data()
        return data

    def _generate_text_report(self, data: Dict) -> str:
        """Generate text format report"""
        report = []
        report.append("📊 DAILY TRADING REPORT")
        report.append(f"📅 Date: {data['date']}")
        report.append("=" * 40)
        pnl = data.get("pnl", {})
        report.append("\n💰 P&L SUMMARY")
        report.append(f"Initial Capital: ${pnl.get('initial_capital', 0):,.2f}")
        report.append(f"Final Capital: ${pnl.get('final_capital', 0):,.2f}")
        report.append(
            f"Daily P&L: ${pnl.get('daily_pnl', 0):,.2f} ({pnl.get('daily_pnl_pct', 0):.2f}%)"
        )
        report.append(f"Realized: ${pnl.get('realized_pnl', 0):,.2f}")
        report.append(f"Unrealized: ${pnl.get('unrealized_pnl', 0):,.2f}")
        trades = data.get("trades", {})
        report.append("\n📈 TRADING METRICS")
        report.append(f"Total Trades: {trades.get('total_trades', 0)}")
        report.append(f"Win Rate: {trades.get('win_rate', 0):.1f}%")
        report.append(
            f"Winning/Losing: {trades.get('winning_trades', 0)}/{trades.get('losing_trades', 0)}"
        )
        report.append(f"Largest Win: ${trades.get('largest_win', 0):,.2f}")
        report.append(f"Largest Loss: ${trades.get('largest_loss', 0):,.2f}")
        report.append(f"Average P&L: ${trades.get('average_pnl', 0):,.2f}")
        fills = data.get("fills", {})
        report.append("\n⚡ EXECUTION QUALITY")
        report.append(f"Maker Fill Rate: {fills.get('maker_fill_rate', 0):.1f}%")
        report.append(f"Avg Fill Time: {fills.get('avg_fill_time_ms', 0):.0f}ms")
        report.append(f"Partial Fills: {fills.get('partial_fills', 0)}")
        report.append(f"Cancelled Orders: {fills.get('cancelled_orders', 0)}")
        risk = data.get("risk", {})
        report.append("\n🎯 RISK METRICS")
        report.append(f"Max Drawdown: {risk.get('max_drawdown', 0):.2f}%")
        report.append(f"Sharpe Ratio: {risk.get('sharpe_ratio', 0):.2f}")
        report.append(f"Risk Status: {risk.get('risk_status', 'UNKNOWN')}")
        system = data.get("system", {})
        report.append("\n🔧 SYSTEM HEALTH")
        report.append(f"Status: {system.get('status', 'UNKNOWN')}")
        report.append(f"Errors: {system.get('error_count', 0)}")
        report.append(f"Clock Skew: {system.get('clock_skew_ms', 0)}ms")
        report.append(f"Rate Limits: {system.get('rate_limit_hits', 0)}")
        report.append("\n" + "=" * 40)
        report.append("Generated by Sofia V2 Trading Bot")
        return "\n".join(report)

    def _generate_html_report(self, data: Dict) -> str:
        """Generate HTML format report"""
        html = f"""\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Daily Trading Report - {data['date']}</title>\n            <style>\n                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}\n                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}\n                h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}\n                h2 {{ color: #666; margin-top: 30px; }}\n                .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}\n                .metric-label {{ color: #888; font-size: 12px; }}\n                .metric-value {{ font-size: 24px; font-weight: bold; color: #333; }}\n                .positive {{ color: #4CAF50; }}\n                .negative {{ color: #f44336; }}\n                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}\n                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}\n                th {{ background: #f0f0f0; font-weight: bold; }}\n            </style>\n        </head>\n        <body>\n            <div class="container">\n                <h1>📊 Daily Trading Report</h1>\n                <p>Date: {data['date']}</p>\n\n                <h2>💰 P&L Summary</h2>\n                <div class="metrics">\n                    <div class="metric">\n                        <div class="metric-label">Daily P&L</div>\n                        <div class="metric-value {self._get_color_class(data['pnl']['daily_pnl'])}">${data['pnl']['daily_pnl']:,.2f}</div>\n                    </div>\n                    <div class="metric">\n                        <div class="metric-label">Percentage</div>\n                        <div class="metric-value {self._get_color_class(data['pnl']['daily_pnl_pct'])}">{data['pnl']['daily_pnl_pct']:.2f}%</div>\n                    </div>\n                </div>\n\n                <h2>📈 Trading Performance</h2>\n                <table>\n                    <tr><th>Metric</th><th>Value</th></tr>\n                    <tr><td>Total Trades</td><td>{data['trades']['total_trades']}</td></tr>\n                    <tr><td>Win Rate</td><td>{data['trades']['win_rate']:.1f}%</td></tr>\n                    <tr><td>Winning Trades</td><td>{data['trades']['winning_trades']}</td></tr>\n                    <tr><td>Losing Trades</td><td>{data['trades']['losing_trades']}</td></tr>\n                    <tr><td>Average P&L</td><td>${data['trades']['average_pnl']:,.2f}</td></tr>\n                </table>\n\n                <h2>⚡ Execution Quality</h2>\n                <table>\n                    <tr><th>Metric</th><th>Value</th></tr>\n                    <tr><td>Maker Fill Rate</td><td>{data['fills']['maker_fill_rate']:.1f}%</td></tr>\n                    <tr><td>Avg Fill Time</td><td>{data['fills']['avg_fill_time_ms']:.0f}ms</td></tr>\n                    <tr><td>Partial Fills</td><td>{data['fills']['partial_fills']}</td></tr>\n                    <tr><td>Cancelled Orders</td><td>{data['fills']['cancelled_orders']}</td></tr>\n                </table>\n\n                <p style="margin-top: 40px; color: #888; font-size: 12px;">\n                    Generated by Sofia V2 Trading Bot at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n                </p>\n            </div>\n        </body>\n        </html>\n        """
        return html

    def _get_color_class(self, value: float) -> str:
        """Get CSS color class based on value"""
        return "positive" if value >= 0 else "negative"

    async def _save_report(self, data: Dict, text: str, html: str):
        """Save report to files"""
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        date_str = data["date"]
        with open(report_dir / f"report_{date_str}.json", "w") as f:
            json.dump(data, f, indent=2)
        with open(report_dir / f"report_{date_str}.txt", "w") as f:
            f.write(text)
        with open(report_dir / f"report_{date_str}.html", "w") as f:
            f.write(html)
        self.logger.info(f"Reports saved to reports/report_{date_str}.*")

    async def _send_telegram_report(self, text_report: str, data: Dict):
        """Send report via Telegram"""
        try:
            from src.integrations.notify import send_telegram

            max_length = 4000
            if len(text_report) > max_length:
                chunks = [
                    text_report[i : i + max_length] for i in range(0, len(text_report), max_length)
                ]
                for chunk in chunks:
                    await send_telegram(chunk)
                    await asyncio.sleep(1)
            else:
                await send_telegram(text_report)
            self.logger.info("Report sent via Telegram")
        except Exception as e:
            self.logger.error(f"Failed to send Telegram report: {e}")

    async def _send_discord_report(self, data: Dict):
        """Send report via Discord"""
        try:
            from src.integrations.notify import send_discord

            pnl = data.get("pnl", {})
            trades = data.get("trades", {})
            message = f"\n**📊 Daily Trading Report - {data['date']}**\n\n**💰 P&L Summary**\n• Daily P&L: ${pnl.get('daily_pnl', 0):,.2f} ({pnl.get('daily_pnl_pct', 0):.2f}%)\n• Realized: ${pnl.get('realized_pnl', 0):,.2f}\n• Unrealized: ${pnl.get('unrealized_pnl', 0):,.2f}\n\n**📈 Trading Metrics**\n• Total Trades: {trades.get('total_trades', 0)}\n• Win Rate: {trades.get('win_rate', 0):.1f}%\n• Average P&L: ${trades.get('average_pnl', 0):,.2f}\n\n**🔧 System Status: {data.get('system', {}).get('status', 'UNKNOWN')}**\n            "
            await send_discord(message)
            self.logger.info("Report sent via Discord")
        except Exception as e:
            self.logger.error(f"Failed to send Discord report: {e}")

    def _calculate_max_drawdown(self, pnl_data: Dict) -> float:
        """Calculate maximum drawdown"""
        return (
            abs(min(pnl_data.get("daily_pnl", 0), 0))
            / max(pnl_data.get("initial_capital", 10000), 1)
            * 100
        )

    def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio"""
        if not trades:
            return 0
        returns = [t.get("pnl", 0) / 10000 for t in trades]
        if len(returns) < 2:
            return 0
        import statistics

        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        if std_return == 0:
            return 0
        return avg_return * 252 / (std_return * 252**0.5)

    def _default_pnl_data(self) -> Dict:
        """Default P&L data"""
        return {
            "daily_pnl": 0,
            "daily_pnl_pct": 0,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "initial_capital": 10000,
            "final_capital": 10000,
        }

    def _default_trade_data(self) -> Dict:
        """Default trade data"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "average_pnl": 0,
        }

    def _default_system_data(self) -> Dict:
        """Default system data"""
        return {"status": "UNKNOWN", "error_count": 0, "clock_skew_ms": 0, "rate_limit_hits": 0}

    def _default_fill_data(self) -> Dict:
        """Default fill data"""
        return {
            "maker_fill_rate": 0,
            "avg_fill_time_ms": 0,
            "partial_fills": 0,
            "cancelled_orders": 0,
        }

    def _default_risk_data(self) -> Dict:
        """Default risk data"""
        return {"max_drawdown": 0, "sharpe_ratio": 0, "risk_status": "UNKNOWN"}


daily_report = DailyReportGenerator()
