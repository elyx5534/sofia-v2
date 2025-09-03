"""Backtest engine for running strategy simulations."""

from typing import Any, Dict

import pandas as pd

from .strategies.base import BaseStrategy


class BacktestEngine:
    """Engine for running backtests on trading strategies."""

    def __init__(
        self, initial_capital: float = 10000.0, commission: float = 0.001, slippage: float = 0.0
    ):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital for backtest
            commission: Commission rate (0.001 = 0.1%)
            slippage: Slippage rate for market orders
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(self, data: pd.DataFrame, strategy: BaseStrategy, **strategy_params) -> Dict[str, Any]:
        """
        Run backtest with given data and strategy.

        Args:
            data: OHLCV DataFrame with columns: open, high, low, close, volume
            strategy: Strategy instance to test
            **strategy_params: Additional parameters for strategy

        Returns:
            Dictionary containing:
                - equity_curve: List of {timestamp, equity} dicts
                - trades: List of trade records
                - final_equity: Final portfolio value
                - return: Total return percentage
        """
        if data.empty:
            raise ValueError("Data cannot be empty")
        positions = strategy.generate_signals(data, **strategy_params)
        equity = self.initial_capital
        cash = self.initial_capital
        position = 0
        trades = []
        equity_curve = []
        for i in range(len(data)):
            timestamp = data.index[i]
            price = data.iloc[i]["close"]
            signal = positions[i] if i < len(positions) else 0
            if signal != position:
                if position != 0:
                    trade_value = position * price
                    commission_cost = abs(trade_value) * self.commission
                    slippage_cost = abs(trade_value) * self.slippage
                    cash += trade_value - commission_cost - slippage_cost
                    trades.append(
                        {
                            "timestamp": timestamp,
                            "type": "sell" if position > 0 else "cover",
                            "price": price,
                            "quantity": abs(position),
                            "value": trade_value,
                            "commission": commission_cost,
                        }
                    )
                if signal != 0:
                    max_position = int(cash / (price * (1 + self.commission + self.slippage)))
                    position = min(abs(signal), max_position) * (1 if signal > 0 else -1)
                    if position != 0:
                        trade_value = abs(position) * price
                        commission_cost = trade_value * self.commission
                        slippage_cost = trade_value * self.slippage
                        cash -= trade_value + commission_cost + slippage_cost
                        trades.append(
                            {
                                "timestamp": timestamp,
                                "type": "buy" if position > 0 else "short",
                                "price": price,
                                "quantity": abs(position),
                                "value": trade_value,
                                "commission": commission_cost,
                            }
                        )
                else:
                    position = 0
            if position != 0:
                equity = cash + position * price
            else:
                equity = cash
            equity_curve.append(
                {
                    "timestamp": (
                        timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
                    ),
                    "equity": round(equity, 2),
                }
            )
        if position != 0:
            final_price = data.iloc[-1]["close"]
            trade_value = position * final_price
            commission_cost = abs(trade_value) * self.commission
            cash += trade_value - commission_cost
            equity = cash
            trades.append(
                {
                    "timestamp": data.index[-1],
                    "type": "sell" if position > 0 else "cover",
                    "price": final_price,
                    "quantity": abs(position),
                    "value": trade_value,
                    "commission": commission_cost,
                }
            )
        final_equity = equity
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "final_equity": round(final_equity, 2),
            "return": round(total_return, 2),
        }
