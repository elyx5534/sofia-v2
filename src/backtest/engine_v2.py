"""
Advanced Backtesting Engine v2 with Alert Signal Integration
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    """Backtest result container"""

    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    recovery_factor: float
    calmar_ratio: float
    sortino_ratio: float
    equity_curve: List[float]
    trade_history: List[Dict]
    daily_returns: List[float]
    monthly_returns: Dict[str, float]


class BacktestEngine:
    """Advanced backtesting engine with multiple strategy support"""

    def __init__(self, initial_capital: float = 100000, commission: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.equity = initial_capital
        self.positions = {}
        self.trade_history = []
        self.equity_curve = [initial_capital]
        self.daily_returns = []

    def run_backtest(
        self, data: pd.DataFrame, strategy: "BaseStrategy", alerts: Optional[List[Dict]] = None
    ) -> BacktestResult:
        """Run backtest with strategy and optional alert signals"""

        self.reset()

        for i in range(len(data)):
            current_bar = data.iloc[i]

            # Get strategy signals
            signal = strategy.generate_signal(data.iloc[: i + 1])

            # Check alert signals if provided
            if alerts:
                alert_signal = self._check_alerts(current_bar["timestamp"], alerts)
                if alert_signal:
                    signal = self._merge_signals(signal, alert_signal)

            # Execute trades based on signals
            if signal:
                self._execute_trade(signal, current_bar)

            # Update positions
            self._update_positions(current_bar)

            # Record equity
            self.equity_curve.append(self.equity)

            # Calculate daily returns
            if i > 0:
                daily_return = (self.equity_curve[-1] - self.equity_curve[-2]) / self.equity_curve[
                    -2
                ]
                self.daily_returns.append(daily_return)

        # Close all positions at end
        self._close_all_positions(data.iloc[-1])

        # Calculate metrics
        return self._calculate_metrics()

    def _check_alerts(self, timestamp: datetime, alerts: List[Dict]) -> Optional[Dict]:
        """Check if there's an alert signal at this timestamp"""
        for alert in alerts:
            alert_time = datetime.fromisoformat(alert["timestamp"])
            if abs((alert_time - timestamp).total_seconds()) < 3600:  # Within 1 hour
                return {
                    "action": alert.get("action"),
                    "severity": alert.get("severity"),
                    "confidence": 0.7 if alert["severity"] == "high" else 0.5,
                }
        return None

    def _merge_signals(self, strategy_signal: Dict, alert_signal: Dict) -> Dict:
        """Merge strategy and alert signals"""
        # Combine signals with weights
        merged = strategy_signal.copy()

        if alert_signal["action"] == "hedge":
            merged["action"] = "sell" if merged.get("position") > 0 else "hold"
            merged["size"] *= 0.5  # Reduce position size

        elif alert_signal["action"] == "momentum_long":
            if merged.get("action") == "buy":
                merged["size"] *= 1.5  # Increase position size
                merged["confidence"] = min(1.0, merged.get("confidence", 0.5) + 0.2)

        return merged

    def _execute_trade(self, signal: Dict, bar: pd.Series):
        """Execute trade based on signal"""
        symbol = signal.get("symbol", "BTC/USDT")
        action = signal.get("action")
        size = signal.get("size", 0)
        price = bar["close"]

        if action == "buy" and size > 0:
            cost = size * price * (1 + self.commission)
            if cost <= self.equity:
                self.positions[symbol] = {
                    "size": size,
                    "entry_price": price,
                    "entry_time": bar["timestamp"],
                    "value": size * price,
                }
                self.equity -= cost

                self.trade_history.append(
                    {
                        "timestamp": bar["timestamp"],
                        "action": "buy",
                        "symbol": symbol,
                        "size": size,
                        "price": price,
                        "cost": cost,
                        "type": "entry",
                    }
                )

        elif action == "sell" and symbol in self.positions:
            position = self.positions[symbol]
            proceeds = position["size"] * price * (1 - self.commission)
            self.equity += proceeds

            # Calculate PnL
            pnl = proceeds - position["value"]
            pnl_pct = pnl / position["value"]

            self.trade_history.append(
                {
                    "timestamp": bar["timestamp"],
                    "action": "sell",
                    "symbol": symbol,
                    "size": position["size"],
                    "price": price,
                    "proceeds": proceeds,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "type": "exit",
                }
            )

            del self.positions[symbol]

    def _update_positions(self, bar: pd.Series):
        """Update position values with current prices"""
        for symbol, position in self.positions.items():
            # Simulate price for position (in real backtest, get from data)
            current_price = bar["close"]
            position["value"] = position["size"] * current_price
            position["unrealized_pnl"] = position["value"] - (
                position["size"] * position["entry_price"]
            )

    def _close_all_positions(self, final_bar: pd.Series):
        """Close all open positions at end of backtest"""
        for symbol in list(self.positions.keys()):
            self._execute_trade({"action": "sell", "symbol": symbol}, final_bar)

    def _calculate_metrics(self) -> BacktestResult:
        """Calculate comprehensive backtest metrics"""

        # Basic metrics
        total_return = (self.equity_curve[-1] - self.initial_capital) / self.initial_capital

        # Trade analysis
        trades = [t for t in self.trade_history if t.get("type") == "exit"]
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]

        total_trades = len(trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        # PnL metrics
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t["pnl"]) for t in losing_trades]) if losing_trades else 0
        profit_factor = (
            abs(sum(t["pnl"] for t in winning_trades) / sum(t["pnl"] for t in losing_trades))
            if losing_trades
            else float("inf")
        )

        best_trade = max(trades, key=lambda x: x.get("pnl", 0))["pnl"] if trades else 0
        worst_trade = min(trades, key=lambda x: x.get("pnl", 0))["pnl"] if trades else 0

        # Risk metrics
        returns = np.array(self.daily_returns) if self.daily_returns else np.array([0])

        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        max_drawdown = self._calculate_max_drawdown()
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        recovery_factor = total_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Monthly returns
        monthly_returns = self._calculate_monthly_returns()

        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=best_trade,
            worst_trade=worst_trade,
            recovery_factor=recovery_factor,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            equity_curve=self.equity_curve,
            trade_history=self.trade_history,
            daily_returns=self.daily_returns,
            monthly_returns=monthly_returns,
        )

    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0:
            return 0

        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate

        if np.std(excess_returns) == 0:
            return 0

        return np.sqrt(252) * np.mean(excess_returns) / np.std(excess_returns)

    def _calculate_sortino_ratio(self, returns: np.ndarray, target_return: float = 0) -> float:
        """Calculate Sortino ratio"""
        if len(returns) == 0:
            return 0

        downside_returns = returns[returns < target_return]

        if len(downside_returns) == 0:
            return float("inf")

        downside_std = np.std(downside_returns)

        if downside_std == 0:
            return 0

        return np.sqrt(252) * (np.mean(returns) - target_return) / downside_std

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.equity_curve:
            return 0

        peak = self.equity_curve[0]
        max_dd = 0

        for value in self.equity_curve:
            peak = max(value, peak)

            drawdown = (peak - value) / peak
            max_dd = max(drawdown, max_dd)

        return -max_dd  # Return as negative

    def _calculate_monthly_returns(self) -> Dict[str, float]:
        """Calculate returns by month"""
        monthly_returns = {}

        if not self.trade_history:
            return monthly_returns

        for trade in self.trade_history:
            if trade.get("type") == "exit":
                month_key = trade["timestamp"].strftime("%Y-%m")

                if month_key not in monthly_returns:
                    monthly_returns[month_key] = 0

                monthly_returns[month_key] += trade.get("pnl", 0)

        return monthly_returns

    def reset(self):
        """Reset backtest state"""
        self.equity = self.initial_capital
        self.positions = {}
        self.trade_history = []
        self.equity_curve = [self.initial_capital]
        self.daily_returns = []

    def get_performance_report(self, result: BacktestResult) -> str:
        """Generate detailed performance report"""

        report = f"""
╔═══════════════════════════════════════════════════════════╗
║           BACKTEST PERFORMANCE REPORT                     ║
╚═══════════════════════════════════════════════════════════╝

📊 RETURNS & PROFITABILITY
─────────────────────────────────
Total Return:        {result.total_return:.2%}
Profit Factor:       {result.profit_factor:.2f}
Win Rate:            {result.win_rate:.2%}
Total Trades:        {result.total_trades}

📈 RISK METRICS
─────────────────────────────────
Sharpe Ratio:        {result.sharpe_ratio:.2f}
Sortino Ratio:       {result.sortino_ratio:.2f}
Max Drawdown:        {result.max_drawdown:.2%}
Calmar Ratio:        {result.calmar_ratio:.2f}
Recovery Factor:     {result.recovery_factor:.2f}

💰 TRADE ANALYSIS
─────────────────────────────────
Winning Trades:      {result.winning_trades}
Losing Trades:       {result.losing_trades}
Average Win:         ${result.avg_win:.2f}
Average Loss:        ${result.avg_loss:.2f}
Best Trade:          ${result.best_trade:.2f}
Worst Trade:         ${result.worst_trade:.2f}

📅 MONTHLY PERFORMANCE
─────────────────────────────────"""

        for month, return_val in result.monthly_returns.items():
            report += f"\n{month}:           ${return_val:,.2f}"

        report += "\n" + "═" * 60

        return report


# Strategy Base Class
class BaseStrategy:
    """Base class for trading strategies"""

    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """Generate trading signal from data"""
        raise NotImplementedError


# Example strategies
class GridTradingStrategy(BaseStrategy):
    """Grid trading strategy"""

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        if len(data) < 2:
            return None

        current_price = data.iloc[-1]["close"]
        prev_price = data.iloc[-2]["close"]

        grid_size = self.parameters.get("grid_size", 0.02)  # 2% grid

        # Buy signal if price drops by grid size
        if (prev_price - current_price) / prev_price >= grid_size:
            return {
                "action": "buy",
                "symbol": "BTC/USDT",
                "size": self.parameters.get("position_size", 0.1),
                "confidence": 0.7,
            }

        # Sell signal if price rises by grid size
        elif (current_price - prev_price) / prev_price >= grid_size:
            return {
                "action": "sell",
                "symbol": "BTC/USDT",
                "size": self.parameters.get("position_size", 0.1),
                "confidence": 0.7,
            }

        return None


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy"""

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        if len(data) < 20:
            return None

        # Calculate 20-period moving average
        ma20 = data["close"].rolling(20).mean().iloc[-1]
        current_price = data.iloc[-1]["close"]

        # Calculate z-score
        std = data["close"].rolling(20).std().iloc[-1]
        z_score = (current_price - ma20) / std if std > 0 else 0

        # Buy if oversold (z-score < -2)
        if z_score < -2:
            return {
                "action": "buy",
                "symbol": "BTC/USDT",
                "size": self.parameters.get("position_size", 0.1),
                "confidence": min(0.9, abs(z_score) / 3),
            }

        # Sell if overbought (z-score > 2)
        elif z_score > 2:
            return {
                "action": "sell",
                "symbol": "BTC/USDT",
                "size": self.parameters.get("position_size", 0.1),
                "confidence": min(0.9, z_score / 3),
            }

        return None
