"""
Advanced Portfolio Manager with Real-Time P&L Tracking
Professional portfolio management system with advanced analytics
"""

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data.real_time_fetcher import fetcher
from ..trading.paper_trading_engine import paper_engine

logger = logging.getLogger(__name__)


class AlertType(Enum):
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    PORTFOLIO_LIMIT = "portfolio_limit"
    VOLATILITY_WARNING = "volatility_warning"
    CORRELATION_ALERT = "correlation_alert"


@dataclass
class PortfolioAlert:
    id: str
    user_id: str
    alert_type: AlertType
    symbol: str
    message: str
    trigger_value: float
    current_value: float
    timestamp: datetime
    acknowledged: bool = False

    def to_dict(self):
        return {
            **asdict(self),
            "alert_type": self.alert_type.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceMetrics:
    user_id: str
    total_return: float
    total_return_percent: float
    daily_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    calmar_ratio: float
    sortino_ratio: float
    beta: float
    alpha: float
    var_95: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {**asdict(self), "timestamp": self.timestamp.isoformat()}


@dataclass
class RiskMetrics:
    portfolio_var: float
    expected_shortfall: float
    portfolio_volatility: float
    correlation_risk: float
    concentration_risk: float
    leverage_ratio: float
    margin_ratio: float
    risk_score: float


class AdvancedPortfolioManager:
    """Professional portfolio management with real-time analytics"""

    def __init__(self):
        self.user_portfolios: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[Dict]] = {}
        self.performance_history: Dict[str, List[PerformanceMetrics]] = {}
        self.alerts: Dict[str, List[PortfolioAlert]] = {}
        self.is_running = False
        self.max_position_size = 0.2
        self.max_portfolio_risk = 0.02
        self.correlation_threshold = 0.7

    async def start(self):
        """Start the portfolio manager"""
        if self.is_running:
            return
        self.is_running = True
        await fetcher.start()
        asyncio.create_task(self._price_monitoring_loop())
        asyncio.create_task(self._performance_calculation_loop())
        asyncio.create_task(self._risk_monitoring_loop())
        asyncio.create_task(self._alert_checking_loop())
        logger.info("Advanced Portfolio Manager started")

    async def stop(self):
        """Stop the portfolio manager"""
        self.is_running = False
        await fetcher.stop()
        logger.info("Advanced Portfolio Manager stopped")

    async def get_portfolio_analytics(self, user_id: str) -> Dict:
        """Get comprehensive portfolio analytics"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return {"error": "Portfolio not found"}
            performance = await self._calculate_performance_metrics(user_id)
            risk_metrics = await self._calculate_risk_metrics(user_id)
            position_analytics = await self._get_position_analytics(user_id)
            market_comparison = await self._get_market_comparison(user_id)
            user_alerts = self.alerts.get(user_id, [])
            active_alerts = [alert.to_dict() for alert in user_alerts if not alert.acknowledged]
            return {
                "portfolio": portfolio,
                "performance": performance.to_dict() if performance else None,
                "risk_metrics": asdict(risk_metrics) if risk_metrics else None,
                "position_analytics": position_analytics,
                "market_comparison": market_comparison,
                "alerts": active_alerts,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting portfolio analytics for {user_id}: {e}")
            return {"error": str(e)}

    async def _calculate_performance_metrics(self, user_id: str) -> Optional[PerformanceMetrics]:
        """Calculate comprehensive performance metrics"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return None
            history = self.performance_history.get(user_id, [])
            if len(history) < 2:
                return PerformanceMetrics(
                    user_id=user_id,
                    total_return=portfolio["total_pnl"],
                    total_return_percent=portfolio["total_pnl_percent"],
                    daily_return=0.0,
                    volatility=0.0,
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    win_rate=portfolio["win_rate"] * 100,
                    avg_win=0.0,
                    avg_loss=0.0,
                    profit_factor=0.0,
                    calmar_ratio=0.0,
                    sortino_ratio=0.0,
                    beta=1.0,
                    alpha=0.0,
                    var_95=0.0,
                )
            values = [h.total_return for h in history]
            returns = pd.Series(values).pct_change().dropna()
            total_return = portfolio["total_pnl"]
            total_return_percent = portfolio["total_pnl_percent"]
            daily_return = returns.mean() if len(returns) > 0 else 0.0
            volatility = returns.std() * np.sqrt(365) if len(returns) > 1 else 0.0
            sharpe_ratio = daily_return / volatility if volatility > 0 else 0.0
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
            trades = paper_engine.get_trade_history(user_id, 1000)
            winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
            losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
            win_rate = len(winning_trades) / len(trades) * 100 if trades else 0.0
            avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
            avg_loss = abs(np.mean([t["pnl"] for t in losing_trades])) if losing_trades else 0.0
            profit_factor = (
                avg_win * len(winning_trades) / (avg_loss * len(losing_trades))
                if avg_loss > 0
                else 0.0
            )
            calmar_ratio = total_return_percent / (max_drawdown * 100) if max_drawdown > 0 else 0.0
            negative_returns = returns[returns < 0]
            downside_deviation = (
                negative_returns.std() * np.sqrt(365) if len(negative_returns) > 1 else volatility
            )
            sortino_ratio = daily_return / downside_deviation if downside_deviation > 0 else 0.0
            btc_prices = self.price_history.get("BTC", [])
            if len(btc_prices) >= len(history):
                btc_returns = (
                    pd.Series([p["price"] for p in btc_prices[-len(history) :]])
                    .pct_change()
                    .dropna()
                )
                portfolio_returns = returns
                if len(btc_returns) == len(portfolio_returns) and len(btc_returns) > 10:
                    covariance = np.cov(portfolio_returns, btc_returns)[0, 1]
                    btc_variance = np.var(btc_returns)
                    beta = covariance / btc_variance if btc_variance > 0 else 1.0
                    alpha = daily_return - beta * btc_returns.mean()
                else:
                    beta, alpha = (1.0, 0.0)
            else:
                beta, alpha = (1.0, 0.0)
            var_95 = abs(np.percentile(returns, 5)) if len(returns) > 20 else 0.0
            return PerformanceMetrics(
                user_id=user_id,
                total_return=total_return,
                total_return_percent=total_return_percent,
                daily_return=daily_return * 100,
                volatility=volatility * 100,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown * 100,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                calmar_ratio=calmar_ratio,
                sortino_ratio=sortino_ratio,
                beta=beta,
                alpha=alpha * 100,
                var_95=var_95 * 100,
            )
        except Exception as e:
            logger.error(f"Error calculating performance metrics for {user_id}: {e}")
            return None

    async def _calculate_risk_metrics(self, user_id: str) -> Optional[RiskMetrics]:
        """Calculate portfolio risk metrics"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio or not portfolio["positions"]:
                return None
            positions = portfolio["positions"]
            total_value = portfolio["total_value"]
            position_sizes = [
                pos["quantity"] * pos["current_price"] / total_value for pos in positions
            ]
            concentration_risk = sum([size**2 for size in position_sizes])
            avg_volatility = 0.15
            portfolio_volatility = avg_volatility * np.sqrt(concentration_risk)
            portfolio_var = total_value * 0.05 * 1.645
            expected_shortfall = portfolio_var * 1.3
            total_position_value = sum(
                [pos["quantity"] * pos["current_price"] for pos in positions]
            )
            leverage_ratio = total_position_value / total_value
            margin_ratio = portfolio["balance"] / total_value
            risk_score = min(
                100, concentration_risk * 50 + (leverage_ratio - 1) * 30 + (1 - margin_ratio) * 20
            )
            return RiskMetrics(
                portfolio_var=portfolio_var,
                expected_shortfall=expected_shortfall,
                portfolio_volatility=portfolio_volatility * 100,
                correlation_risk=50.0,
                concentration_risk=concentration_risk * 100,
                leverage_ratio=leverage_ratio,
                margin_ratio=margin_ratio,
                risk_score=max(0, risk_score),
            )
        except Exception as e:
            logger.error(f"Error calculating risk metrics for {user_id}: {e}")
            return None

    async def _get_position_analytics(self, user_id: str) -> Dict:
        """Get detailed analytics for each position"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return {}
            analytics = {}
            total_value = portfolio["total_value"]
            for position in portfolio["positions"]:
                symbol = position["symbol"]
                symbol_history = self.price_history.get(symbol, [])
                if len(symbol_history) > 10:
                    prices = [p["price"] for p in symbol_history[-30:]]
                    returns = pd.Series(prices).pct_change().dropna()
                    volatility = returns.std() * np.sqrt(365) * 100 if len(returns) > 1 else 15.0
                    var_95 = abs(np.percentile(returns, 5)) * 100 if len(returns) > 20 else 5.0
                    recent_prices = prices[-20:] if len(prices) >= 20 else prices
                    support = min(recent_prices) * 0.98
                    resistance = max(recent_prices) * 1.02
                    position_value = position["quantity"] * position["current_price"]
                    position_weight = position_value / total_value * 100
                    analytics[symbol] = {
                        "volatility": volatility,
                        "var_95": var_95,
                        "support_level": support,
                        "resistance_level": resistance,
                        "position_weight": position_weight,
                        "days_held": (
                            datetime.now(timezone.utc)
                            - datetime.fromisoformat(position["entry_time"].replace("Z", "+00:00"))
                        ).days,
                        "risk_contribution": position_weight * (volatility / 100),
                        "sharpe_estimate": (
                            position["unrealized_pnl"] / position_value / (volatility / 100)
                            if position_value > 0
                            else 0.0
                        ),
                    }
            return analytics
        except Exception as e:
            logger.error(f"Error getting position analytics for {user_id}: {e}")
            return {}

    async def _get_market_comparison(self, user_id: str) -> Dict:
        """Compare portfolio performance to market benchmarks"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return {}
            btc_history = self.price_history.get("BTC", [])
            if len(btc_history) < 2:
                return {"error": "Insufficient market data"}
            btc_start = btc_history[0]["price"] if btc_history else portfolio["total_value"]
            btc_current = btc_history[-1]["price"] if btc_history else btc_start
            btc_return = (btc_current - btc_start) / btc_start * 100
            portfolio_return = portfolio["total_pnl_percent"]
            outperformance = portfolio_return - btc_return
            return {
                "btc_return": btc_return,
                "portfolio_return": portfolio_return,
                "outperformance": outperformance,
                "market_correlation": 0.75,
                "tracking_error": abs(outperformance) * 0.1,
                "information_ratio": outperformance / max(0.1, abs(outperformance) * 0.1),
            }
        except Exception as e:
            logger.error(f"Error getting market comparison for {user_id}: {e}")
            return {}

    async def _price_monitoring_loop(self):
        """Monitor prices and store history"""
        symbols = ["BTC", "ETH", "SOL", "BNB", "ADA", "DOT", "LINK", "LTC"]
        while self.is_running:
            try:
                market_data = await fetcher.get_market_data([s.lower() for s in symbols])
                if market_data:
                    timestamp = datetime.now(timezone.utc)
                    for symbol, data in market_data.items():
                        symbol = symbol.upper()
                        if symbol not in self.price_history:
                            self.price_history[symbol] = []
                        self.price_history[symbol].append(
                            {
                                "price": data["price"],
                                "volume": data.get("volume_24h", 0),
                                "timestamp": timestamp.isoformat(),
                            }
                        )
                        if len(self.price_history[symbol]) > 1000:
                            self.price_history[symbol] = self.price_history[symbol][-1000:]
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {e}")
                await asyncio.sleep(30)

    async def _performance_calculation_loop(self):
        """Calculate and store performance metrics"""
        while self.is_running:
            try:
                for user_id in paper_engine.portfolios.keys():
                    performance = await self._calculate_performance_metrics(user_id)
                    if performance:
                        if user_id not in self.performance_history:
                            self.performance_history[user_id] = []
                        self.performance_history[user_id].append(performance)
                        if len(self.performance_history[user_id]) > 500:
                            self.performance_history[user_id] = self.performance_history[user_id][
                                -500:
                            ]
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in performance calculation loop: {e}")
                await asyncio.sleep(1800)

    async def _risk_monitoring_loop(self):
        """Monitor portfolio risks and generate alerts"""
        while self.is_running:
            try:
                for user_id in paper_engine.portfolios.keys():
                    await self._check_risk_limits(user_id)
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _alert_checking_loop(self):
        """Check for alert conditions"""
        while self.is_running:
            try:
                for user_id in paper_engine.portfolios.keys():
                    await self._check_alerts(user_id)
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in alert checking loop: {e}")
                await asyncio.sleep(60)

    async def _check_risk_limits(self, user_id: str):
        """Check if user is exceeding risk limits"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio or not portfolio["positions"]:
                return
            total_value = portfolio["total_value"]
            for position in portfolio["positions"]:
                position_value = position["quantity"] * position["current_price"]
                position_weight = position_value / total_value
                if position_weight > self.max_position_size:
                    await self._create_alert(
                        user_id=user_id,
                        alert_type=AlertType.PORTFOLIO_LIMIT,
                        symbol=position["symbol"],
                        message=f"Position size ({position_weight:.1%}) exceeds maximum allowed ({self.max_position_size:.1%})",
                        trigger_value=self.max_position_size,
                        current_value=position_weight,
                    )
        except Exception as e:
            logger.error(f"Error checking risk limits for {user_id}: {e}")

    async def _check_alerts(self, user_id: str):
        """Check for various alert conditions"""
        try:
            portfolio = paper_engine.get_portfolio_summary(user_id)
            if not portfolio:
                return
            if abs(portfolio["total_pnl_percent"]) > 10:
                await self._create_alert(
                    user_id=user_id,
                    alert_type=AlertType.VOLATILITY_WARNING,
                    symbol="PORTFOLIO",
                    message=f"Large portfolio movement: {portfolio['total_pnl_percent']:.2f}%",
                    trigger_value=10.0,
                    current_value=abs(portfolio["total_pnl_percent"]),
                )
        except Exception as e:
            logger.error(f"Error checking alerts for {user_id}: {e}")

    async def _create_alert(
        self,
        user_id: str,
        alert_type: AlertType,
        symbol: str,
        message: str,
        trigger_value: float,
        current_value: float,
    ):
        """Create a new alert"""
        try:
            alert = PortfolioAlert(
                id=str(uuid.uuid4()),
                user_id=user_id,
                alert_type=alert_type,
                symbol=symbol,
                message=message,
                trigger_value=trigger_value,
                current_value=current_value,
                timestamp=datetime.now(timezone.utc),
            )
            if user_id not in self.alerts:
                self.alerts[user_id] = []
            existing = [
                a
                for a in self.alerts[user_id]
                if a.alert_type == alert_type and a.symbol == symbol and (not a.acknowledged)
            ]
            if not existing:
                self.alerts[user_id].append(alert)
                logger.info(f"Alert created for {user_id}: {message}")
        except Exception as e:
            logger.error(f"Error creating alert: {e}")

    def acknowledge_alert(self, user_id: str, alert_id: str) -> bool:
        """Acknowledge an alert"""
        try:
            if user_id in self.alerts:
                for alert in self.alerts[user_id]:
                    if alert.id == alert_id:
                        alert.acknowledged = True
                        return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False


portfolio_manager = AdvancedPortfolioManager()
