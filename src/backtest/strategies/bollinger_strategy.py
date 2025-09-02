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
        # Middle Band (SMA)
        middle = prices.rolling(window=self.bb_period).mean()

        # Standard deviation
        std = prices.rolling(window=self.bb_period).std()

        # Upper and Lower Bands
        upper = middle + (std * self.bb_std)
        lower = middle - (std * self.bb_std)

        return upper, middle, lower

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on Bollinger Bands.

        Strategy:
        - Buy when price touches lower band (oversold)
        - Sell when price touches upper band (overbought)

        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        # Calculate Bollinger Bands
        upper, middle, lower = self.calculate_bollinger_bands(data["Close"])

        # Generate signals
        signals = pd.Series(0, index=data.index)

        # Buy when price crosses below lower band
        signals[(data["Close"] <= lower) & (data["Close"].shift(1) > lower.shift(1))] = 1

        # Sell when price crosses above upper band
        signals[(data["Close"] >= upper) & (data["Close"].shift(1) < upper.shift(1))] = -1

        # Alternative: Mean reversion signals
        # Buy at lower band, sell at middle band
        # signals[data['Close'] <= lower] = 1
        # signals[data['Close'] >= middle] = -1

        return signals
