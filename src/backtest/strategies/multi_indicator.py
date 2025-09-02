"""Multi-indicator confluence trading strategy."""

import pandas as pd

from .base import BaseStrategy
from .bollinger_strategy import BollingerBandsStrategy
from .macd_strategy import MACDStrategy
from .rsi_strategy import RSIStrategy


class MultiIndicatorStrategy(BaseStrategy):
    """Advanced strategy combining multiple indicators for high-probability trades."""

    def __init__(
        self,
        rsi_weight: float = 0.33,
        macd_weight: float = 0.33,
        bb_weight: float = 0.34,
        signal_threshold: float = 0.6,
    ):
        """
        Initialize multi-indicator strategy.

        Args:
            rsi_weight: Weight for RSI signal (0-1)
            macd_weight: Weight for MACD signal (0-1)
            bb_weight: Weight for Bollinger Bands signal (0-1)
            signal_threshold: Minimum combined signal strength to trade (0-1)
        """
        # Normalize weights
        total_weight = rsi_weight + macd_weight + bb_weight
        self.rsi_weight = rsi_weight / total_weight
        self.macd_weight = macd_weight / total_weight
        self.bb_weight = bb_weight / total_weight
        self.signal_threshold = signal_threshold

        # Initialize sub-strategies
        self.rsi_strategy = RSIStrategy()
        self.macd_strategy = MACDStrategy()
        self.bb_strategy = BollingerBandsStrategy()

    def calculate_signal_strength(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate combined signal strength from all indicators.

        Returns:
            Series with signal strength values between -1 and 1
        """
        # Get signals from each strategy
        rsi_signals = self.rsi_strategy.generate_signals(data)
        macd_signals = self.macd_strategy.generate_signals(data)
        bb_signals = self.bb_strategy.generate_signals(data)

        # Calculate weighted combination
        combined_signal = (
            rsi_signals * self.rsi_weight
            + macd_signals * self.macd_weight
            + bb_signals * self.bb_weight
        )

        return combined_signal

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on multiple indicators.

        Only generates signals when combined indicator strength exceeds threshold.

        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        # Calculate combined signal strength
        signal_strength = self.calculate_signal_strength(data)

        # Generate signals based on threshold
        signals = pd.Series(0, index=data.index)

        # Strong buy signal
        signals[signal_strength >= self.signal_threshold] = 1

        # Strong sell signal
        signals[signal_strength <= -self.signal_threshold] = -1

        # Clean up consecutive signals (only trade on new signals)
        signals_diff = signals.diff()
        clean_signals = pd.Series(0, index=data.index)

        # Only keep signal changes
        clean_signals[signals_diff > 0] = 1  # New buy signal
        clean_signals[signals_diff < 0] = -1  # New sell signal

        return clean_signals

    def get_indicator_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Get all indicator values for analysis.

        Returns:
            DataFrame with all indicator values
        """
        result = pd.DataFrame(index=data.index)

        # RSI
        rsi = self.rsi_strategy.calculate_rsi(data["Close"])
        result["RSI"] = rsi

        # MACD
        macd, signal, histogram = self.macd_strategy.calculate_macd(data["Close"])
        result["MACD"] = macd
        result["MACD_Signal"] = signal
        result["MACD_Histogram"] = histogram

        # Bollinger Bands
        upper, middle, lower = self.bb_strategy.calculate_bollinger_bands(data["Close"])
        result["BB_Upper"] = upper
        result["BB_Middle"] = middle
        result["BB_Lower"] = lower

        # Signal strength
        result["Signal_Strength"] = self.calculate_signal_strength(data)

        return result
