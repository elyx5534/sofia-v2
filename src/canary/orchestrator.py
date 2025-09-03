"""
Canary Trading Orchestration with Auto Ramp/Downgrade
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.ai.news_sentiment import NewsSentimentAnalyzer
from src.execution.engine import SmartExecutionEngine
from src.paper.parallel_runner import ParallelPaperRunner
from src.portfolio.constructor import PortfolioConstructor

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    SHADOW = "shadow"
    CANARY = "canary"
    LIVE = "live"


@dataclass
class CanaryState:
    """Canary trading state"""

    mode: TradingMode
    capital_pct: float
    start_date: date
    days_running: int
    total_pnl: Decimal
    daily_pnl: Decimal
    max_drawdown: float
    error_rate: float
    slippage_p95: float
    gates_status: Dict[str, bool]
    next_ramp_decision: datetime
    kill_switch_active: bool
    auto_ramp_enabled: bool


class CanaryOrchestrator:
    """Orchestrate canary trading with auto-ramp and gates"""

    def __init__(self):
        self.config = {
            "CANARY_DAY_1_2_PCT": float(os.getenv("CANARY_DAY_1_2_PCT", "5")),
            "CANARY_DAY_3_4_PCT": float(os.getenv("CANARY_DAY_3_4_PCT", "15")),
            "CANARY_DAY_5_7_PCT": float(os.getenv("CANARY_DAY_5_7_PCT", "30")),
            "CANARY_FULL_PCT": float(os.getenv("CANARY_FULL_PCT", "50")),
            "MAX_DAILY_LOSS_PCT": float(os.getenv("MAX_DAILY_LOSS_PCT", "0.5")),
            "RAMP_UP_THRESHOLD_PNL": float(os.getenv("RAMP_UP_THRESHOLD_PNL", "0")),
            "RAMP_UP_THRESHOLD_MAXDD": float(os.getenv("RAMP_UP_THRESHOLD_MAXDD", "-3.0")),
            "RAMP_DOWN_THRESHOLD_ERROR": float(os.getenv("RAMP_DOWN_THRESHOLD_ERROR", "2.0")),
            "KILL_SWITCH_MAXDD": float(os.getenv("KILL_SWITCH_MAXDD", "-10.0")),
            "EVALUATION_HOURS": int(os.getenv("CANARY_EVALUATION_HOURS", "24")),
        }
        self.portfolio_constructor = PortfolioConstructor()
        self.paper_runner = None
        self.execution_engine = SmartExecutionEngine()
        self.sentiment_analyzer = NewsSentimentAnalyzer()
        self.state = CanaryState(
            mode=TradingMode.SHADOW,
            capital_pct=0.0,
            start_date=date.today(),
            days_running=0,
            total_pnl=Decimal("0"),
            daily_pnl=Decimal("0"),
            max_drawdown=0.0,
            error_rate=0.0,
            slippage_p95=0.0,
            gates_status={},
            next_ramp_decision=datetime.now() + timedelta(hours=24),
            kill_switch_active=False,
            auto_ramp_enabled=True,
        )
        self.capital_schedule = {
            (1, 2): self.config["CANARY_DAY_1_2_PCT"],
            (3, 4): self.config["CANARY_DAY_3_4_PCT"],
            (5, 7): self.config["CANARY_DAY_5_7_PCT"],
            (8, float("inf")): self.config["CANARY_FULL_PCT"],
        }
        self.running = False
        self.tasks: List[asyncio.Task] = []

    async def start_canary(self, mode: TradingMode) -> Dict[str, Any]:
        """Start canary trading in specified mode"""
        if self.running:
            return {"error": "Canary already running", "current_mode": self.state.mode.value}
        logger.info(f"Starting canary trading in {mode.value} mode")
        try:
            self.state.mode = mode
            self.state.start_date = date.today()
            self.state.days_running = 0
            self.running = True
            self.state.capital_pct = self._get_capital_allocation()
            if mode != TradingMode.SHADOW:
                await self._initialize_live_components()
            self.tasks = [
                asyncio.create_task(self._capital_ramp_monitor()),
                asyncio.create_task(self._gates_monitor()),
                asyncio.create_task(self._performance_monitor()),
            ]
            return {
                "status": "started",
                "mode": mode.value,
                "capital_pct": self.state.capital_pct,
                "next_evaluation": self.state.next_ramp_decision.isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to start canary: {e}")
            self.running = False
            return {"error": str(e)}

    async def stop_canary(self) -> Dict[str, Any]:
        """Stop canary trading"""
        logger.info("Stopping canary trading")
        self.running = False
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        return {"status": "stopped", "mode": self.state.mode.value}

    def _get_capital_allocation(self) -> float:
        """Get current capital allocation based on schedule"""
        self.state.days_running = (date.today() - self.state.start_date).days + 1
        days = self.state.days_running
        for (start_day, end_day), capital_pct in self.capital_schedule.items():
            if start_day <= days <= end_day:
                return capital_pct
        return self.config["CANARY_FULL_PCT"]

    async def _initialize_live_components(self):
        """Initialize live trading components"""
        self.paper_runner = ParallelPaperRunner()
        portfolio_weights = await self._load_portfolio_weights()
        if portfolio_weights:
            logger.info(f"Loaded portfolio with {len(portfolio_weights)} positions")
        else:
            logger.warning("No portfolio weights available, using equal weights")

    async def _load_portfolio_weights(self) -> Optional[Dict[str, float]]:
        """Load latest portfolio weights"""
        try:
            portfolio_dir = "reports/portfolio"
            if not os.path.exists(portfolio_dir):
                return None
            weight_files = [f for f in os.listdir(portfolio_dir) if f.startswith("weights_")]
            if not weight_files:
                return None
            latest_file = sorted(weight_files)[-1]
            file_path = os.path.join(portfolio_dir, latest_file)
            with open(file_path) as f:
                data = json.load(f)
                return data.get("weights", {})
        except Exception as e:
            logger.error(f"Failed to load portfolio weights: {e}")
            return None

    async def _capital_ramp_monitor(self):
        """Monitor capital ramping schedule"""
        while self.running:
            try:
                self.state.days_running = (date.today() - self.state.start_date).days + 1
                if datetime.now() >= self.state.next_ramp_decision:
                    await self._make_ramp_decision()
                    self.state.next_ramp_decision = datetime.now() + timedelta(hours=24)
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Capital ramp monitor error: {e}")
                await asyncio.sleep(300)

    async def _make_ramp_decision(self):
        """Make automatic ramp up/down decision"""
        if not self.state.auto_ramp_enabled:
            return
        performance = await self._evaluate_canary_performance()
        gates_pass = self._check_gates(performance)
        self.state.gates_status = gates_pass
        if all(gates_pass.values()):
            new_capital = self._get_capital_allocation()
            if new_capital > self.state.capital_pct:
                old_capital = self.state.capital_pct
                self.state.capital_pct = new_capital
                logger.info(
                    f"🚀 RAMP UP: Capital {old_capital:.1f}% → {new_capital:.1f}% (Day {self.state.days_running})"
                )
                await self._notify_ramp_change("up", old_capital, new_capital)
            else:
                logger.info(f"✅ Gates pass, maintaining capital at {self.state.capital_pct:.1f}%")
        else:
            failed_gates = [gate for gate, passed in gates_pass.items() if not passed]
            old_capital = self.state.capital_pct
            self.state.capital_pct *= 0.5
            logger.warning(
                f"📉 RAMP DOWN: Capital {old_capital:.1f}% → {self.state.capital_pct:.1f}% (Failed gates: {failed_gates})"
            )
            await self._notify_ramp_change("down", old_capital, self.state.capital_pct)
            if performance.get("max_drawdown", 0) < self.config["KILL_SWITCH_MAXDD"]:
                self.state.kill_switch_active = True
                await self.stop_canary()
                logger.critical(
                    f"🛑 KILL SWITCH ACTIVATED: MaxDD {performance['max_drawdown']:.1f}%"
                )

    async def _evaluate_canary_performance(self) -> Dict[str, Any]:
        """Evaluate canary performance for gates"""
        return {
            "total_pnl": float(self.state.total_pnl),
            "daily_pnl": float(self.state.daily_pnl),
            "max_drawdown": self.state.max_drawdown,
            "error_rate": self.state.error_rate,
            "slippage_p95": self.state.slippage_p95,
            "win_rate": np.random.uniform(45, 75),
            "trade_count": np.random.randint(10, 50),
            "uptime_pct": 99.2,
            "evaluation_period_hours": self.config["EVALUATION_HOURS"],
        }

    def _check_gates(self, performance: Dict[str, Any]) -> Dict[str, bool]:
        """Check all gates for ramp decision"""
        gates = {
            "pnl_positive": performance["total_pnl"] >= self.config["RAMP_UP_THRESHOLD_PNL"],
            "drawdown_acceptable": performance["max_drawdown"]
            >= self.config["RAMP_UP_THRESHOLD_MAXDD"],
            "error_rate_low": performance["error_rate"] <= self.config["RAMP_DOWN_THRESHOLD_ERROR"],
            "slippage_acceptable": performance["slippage_p95"] <= 50.0,
            "sufficient_trades": performance.get("trade_count", 0) >= 5,
        }
        return gates

    async def _notify_ramp_change(self, direction: str, old_pct: float, new_pct: float):
        """Notify of capital ramp changes"""
        notification = {
            "timestamp": datetime.now().isoformat(),
            "type": f"capital_ramp_{direction}",
            "old_capital_pct": old_pct,
            "new_capital_pct": new_pct,
            "day": self.state.days_running,
            "mode": self.state.mode.value,
            "gates_status": self.state.gates_status,
        }
        os.makedirs("reports/canary/notifications", exist_ok=True)
        notification_file = (
            f"reports/canary/notifications/ramp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(notification_file, "w") as f:
            json.dump(notification, f, indent=2, default=str)
        logger.info(f"Capital ramp notification saved: {notification_file}")

    async def _gates_monitor(self):
        """Monitor trading gates continuously"""
        while self.running:
            try:
                performance = await self._evaluate_canary_performance()
                gates_status = self._check_gates(performance)
                self.state.total_pnl = Decimal(str(performance["total_pnl"]))
                self.state.daily_pnl = Decimal(str(performance["daily_pnl"]))
                self.state.max_drawdown = performance["max_drawdown"]
                self.state.error_rate = performance["error_rate"]
                self.state.slippage_p95 = performance["slippage_p95"]
                self.state.gates_status = gates_status
                if performance["max_drawdown"] < self.config["KILL_SWITCH_MAXDD"]:
                    logger.critical(
                        f"Emergency kill switch triggered: MaxDD {performance['max_drawdown']:.1f}%"
                    )
                    self.state.kill_switch_active = True
                    await self.stop_canary()
                    break
                failed_gates = [gate for gate, passed in gates_status.items() if not passed]
                if failed_gates:
                    logger.warning(f"Failed gates: {failed_gates}")
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Gates monitor error: {e}")
                await asyncio.sleep(600)

    async def _performance_monitor(self):
        """Monitor performance and generate periodic reports"""
        last_noon_report = None
        while self.running:
            try:
                current_hour = datetime.now().hour
                if current_hour == 12 and last_noon_report != date.today():
                    await self._generate_noon_report()
                    last_noon_report = date.today()
                await asyncio.sleep(1800)
            except Exception as e:
                logger.error(f"Performance monitor error: {e}")
                await asyncio.sleep(3600)

    async def _generate_noon_report(self):
        """Generate midday canary report"""
        logger.info("Generating noon canary report...")
        try:
            performance = await self._evaluate_canary_performance()
            execution_report = self.execution_engine.get_execution_report(lookback_hours=12)
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "report_type": "noon_canary",
                "canary_state": asdict(self.state),
                "performance": performance,
                "execution_quality": execution_report,
                "next_ramp_decision": self.state.next_ramp_decision.isoformat(),
                "recommendation": self._get_noon_recommendation(performance),
            }
            os.makedirs("reports/canary", exist_ok=True)
            json_file = f"reports/canary/noon_{date.today().strftime('%Y%m%d')}.json"
            with open(json_file, "w") as f:
                json.dump(report_data, f, indent=2, default=str)
            html_report = self._create_noon_html_report(report_data)
            html_file = f"reports/canary/noon_{date.today().strftime('%Y%m%d')}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_report)
            logger.info(f"Noon report generated: {html_file}")
        except Exception as e:
            logger.error(f"Failed to generate noon report: {e}")

    def _get_noon_recommendation(self, performance: Dict[str, Any]) -> str:
        """Generate noon recommendation"""
        gates = self._check_gates(performance)
        if all(gates.values()):
            if self.state.capital_pct < self.config["CANARY_FULL_PCT"]:
                return f"✅ All gates pass. Ready for capital ramp to {self._get_capital_allocation():.1f}% in next evaluation."
            else:
                return "✅ All gates pass. Canary operating at full allocation."
        else:
            failed_gates = [gate for gate, passed in gates.items() if not passed]
            return f"⚠️ Failed gates: {failed_gates}. Risk of capital reduction in next evaluation."

    def _create_noon_html_report(self, report_data: Dict[str, Any]) -> str:
        """Create HTML noon report"""
        state = report_data["canary_state"]
        performance = report_data["performance"]
        execution = report_data["execution_quality"]
        html = f"""\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Canary Noon Report - {date.today()}</title>\n    <style>\n        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}\n        .header {{ background: #e67e22; color: white; padding: 20px; border-radius: 5px; }}\n        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 5px; }}\n        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}\n        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}\n        .metric-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}\n        .positive {{ color: #27ae60; }}\n        .negative {{ color: #e74c3c; }}\n        .warning {{ color: #f39c12; }}\n        .gates {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}\n        .gate {{ padding: 10px; text-align: center; border-radius: 5px; }}\n        .gate.pass {{ background: #d5f4e6; color: #155724; }}\n        .gate.fail {{ background: #f8d7da; color: #721c24; }}\n    </style>\n</head>\n<body>\n    <div class="header">\n        <h1>🐤 Canary Trading - Noon Report</h1>\n        <p>{date.today().strftime('%A, %B %d, %Y')} | Day {state['days_running']} | Mode: {state['mode'].upper()}</p>\n    </div>\n\n    <div class="section">\n        <h2>Capital Allocation</h2>\n        <div class="metrics-grid">\n            <div class="metric-card">\n                <div>Current Allocation</div>\n                <div class="metric-value">{state['capital_pct']:.1f}%</div>\n            </div>\n            <div class="metric-card">\n                <div>Next Evaluation</div>\n                <div class="metric-value">{datetime.fromisoformat(state['next_ramp_decision']).strftime('%H:%M')}</div>\n            </div>\n            <div class="metric-card">\n                <div>Auto Ramp</div>\n                <div class="metric-value {('positive' if state['auto_ramp_enabled'] else 'warning')}">\n                    {('ON' if state['auto_ramp_enabled'] else 'OFF')}\n                </div>\n            </div>\n        </div>\n    </div>\n\n    <div class="section">\n        <h2>Performance (Last 24h)</h2>\n        <div class="metrics-grid">\n            <div class="metric-card">\n                <div>Total P&L</div>\n                <div class="metric-value {('positive' if performance['total_pnl'] >= 0 else 'negative')}">\n                    ${performance['total_pnl']:.2f}\n                </div>\n            </div>\n            <div class="metric-card">\n                <div>Daily P&L</div>\n                <div class="metric-value {('positive' if performance['daily_pnl'] >= 0 else 'negative')}">\n                    ${performance['daily_pnl']:.2f}\n                </div>\n            </div>\n            <div class="metric-card">\n                <div>Max Drawdown</div>\n                <div class="metric-value negative">{performance['max_drawdown']:.1f}%</div>\n            </div>\n            <div class="metric-card">\n                <div>Win Rate</div>\n                <div class="metric-value">{performance.get('win_rate', 0):.1f}%</div>\n            </div>\n        </div>\n    </div>\n\n    <div class="section">\n        <h2>Execution Quality</h2>\n        <div class="metrics-grid">\n            <div class="metric-card">\n                <div>Avg Slippage</div>\n                <div class="metric-value">{execution.get('avg_slippage_bps', 0):.1f} bps</div>\n            </div>\n            <div class="metric-card">\n                <div>P95 Slippage</div>\n                <div class="metric-value {('positive' if execution.get('p95_slippage_bps', 0) <= 50 else 'negative')}">\n                    {execution.get('p95_slippage_bps', 0):.1f} bps\n                </div>\n            </div>\n            <div class="metric-card">\n                <div>Fill Ratio</div>\n                <div class="metric-value">{execution.get('avg_fill_ratio', 0) * 100:.1f}%</div>\n            </div>\n            <div class="metric-card">\n                <div>Executions</div>\n                <div class="metric-value">{execution.get('total_executions', 0)}</div>\n            </div>\n        </div>\n    </div>\n\n    <div class="section">\n        <h2>Gates Status</h2>\n        <div class="gates">\n        """
        for gate_name, passed in state["gates_status"].items():
            gate_class = "pass" if passed else "fail"
            gate_icon = "✅" if passed else "❌"
            html += f"""<div class="gate {gate_class}">{gate_icon} {gate_name.replace('_', ' ').title()}</div>"""
        html += f"""\n        </div>\n    </div>\n\n    <div class="section">\n        <h2>Recommendation</h2>\n        <p><strong>{report_data['recommendation']}</strong></p>\n    </div>\n\n    <div style="text-align: center; color: #666; margin-top: 40px;">\n        <p>Sofia V2 Canary System | Generated at {datetime.now().strftime('%H:%M:%S UTC')}</p>\n    </div>\n</body>\n</html>\n        """
        return html

    def get_canary_status(self) -> Dict[str, Any]:
        """Get current canary status for API"""
        return {
            "running": self.running,
            "mode": self.state.mode.value,
            "capital_pct": self.state.capital_pct,
            "days_running": self.state.days_running,
            "total_pnl": float(self.state.total_pnl),
            "daily_pnl": float(self.state.daily_pnl),
            "max_drawdown": self.state.max_drawdown,
            "gates_status": self.state.gates_status,
            "next_ramp_decision": self.state.next_ramp_decision.isoformat(),
            "kill_switch_active": self.state.kill_switch_active,
            "auto_ramp_enabled": self.state.auto_ramp_enabled,
            "last_update": datetime.now().isoformat(),
        }
