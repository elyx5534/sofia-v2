"""Bollinger Bands trading strategy."""

from typing import Tuple

import pandas as pd

from .base import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands Breakout Strategy."""

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0):
        """
        Initialize Bollinger Bands strategy.

        Args:
            bb_period: Period for moving average and standard deviation
            bb_std: Number of standard deviations for bands
        """
        self.bb_period = bb_period
        self.bb_std = bb_std

    def calculate_bollinger_bands(
        self, prices: pd.Series
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.

        Returns:
            Tuple of (Upper band, Middle band (SMA), Lower band)
        """
        middle = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        upper = middle + std * self.bb_std
        lower = middle - std * self.bb_std
        return (upper, middle, lower)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on Bollinger Bands.

        Strategy:
        - Buy when price touches lower band (oversold)
        - Sell when price touches upper band (overbought)

        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        upper, middle, lower = self.calculate_bollinger_bands(data["Close"])
        signals = pd.Series(0, index=data.index)
        signals[(data["Close"] <= lower) & (data["Close"].shift(1) > lower.shift(1))] = 1
        signals[(data["Close"] >= upper) & (data["Close"].shift(1) < upper.shift(1))] = -1
        return signals
