"""Simple Moving Average (SMA) crossover strategy."""

from typing import List

import pandas as pd

from .base import BaseStrategy


class SMAStrategy(BaseStrategy):
    """SMA crossover trading strategy."""

    def generate_signals(
        self, data: pd.DataFrame, fast_period: int = 20, slow_period: int = 50, **params
    ) -> List[int]:
        """
        Generate signals based on SMA crossover.

        Args:
            data: OHLCV DataFrame
            fast_period: Period for fast SMA (default 20)
            slow_period: Period for slow SMA (default 50)
            **params: Additional parameters (unused)

        Returns:
            List of position signals (1=long, 0=flat, -1=short)
        """
        if len(data) < slow_period:
            return [0] * len(data)
        fast_sma = data["close"].rolling(window=fast_period).mean()
        slow_sma = data["close"].rolling(window=slow_period).mean()
        signals = []
        for i in range(len(data)):
            if pd.isna(fast_sma.iloc[i]) or pd.isna(slow_sma.iloc[i]):
                signals.append(0)
            elif fast_sma.iloc[i] > slow_sma.iloc[i]:
                signals.append(1)
            elif fast_sma.iloc[i] < slow_sma.iloc[i]:
                signals.append(-1)
            else:
                signals.append(0)
        return signals
