"""MACD-based trading strategy."""

import pandas as pd
import numpy as np
from typing import Tuple
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
        # Calculate EMAs
        ema_fast = prices.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=self.slow_period, adjust=False).mean()
        
        # MACD line
        macd = ema_fast - ema_slow
        
        # Signal line
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        
        # Histogram
        histogram = macd - signal
        
        return macd, signal, histogram
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on MACD crossovers.
        
        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        # Calculate MACD
        macd, signal, histogram = self.calculate_macd(data['Close'])
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy when MACD crosses above signal line
        signals[(macd > signal) & (macd.shift(1) <= signal.shift(1))] = 1
        
        # Sell when MACD crosses below signal line
        signals[(macd < signal) & (macd.shift(1) >= signal.shift(1))] = -1
        
        return signals