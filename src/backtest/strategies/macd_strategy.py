"""MACD-based trading strategy."""

from typing import Tuple

import pandas as pd

from .base import BaseStrategy


class MACDStrategy(BaseStrategy):
    """MACD Signal Line Crossover Strategy."""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Initialize MACD strategy.

        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD, signal line, and histogram.

        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = prices.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=self.slow_period, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd - signal
        return (macd, signal, histogram)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on MACD crossovers.

        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        macd, signal, histogram = self.calculate_macd(data["Close"])
        signals = pd.Series(0, index=data.index)
        signals[(macd > signal) & (macd.shift(1) <= signal.shift(1))] = 1
        signals[(macd < signal) & (macd.shift(1) >= signal.shift(1))] = -1
        return signals
