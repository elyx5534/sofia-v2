"""RSI-based trading strategy."""

import pandas as pd
import numpy as np
from typing import Tuple
from .base import BaseStrategy


class RSIStrategy(BaseStrategy):
    """RSI Oversold/Overbought Strategy."""
    
    def __init__(self, rsi_period: int = 14, oversold_level: int = 30, overbought_level: int = 70):
        """
        Initialize RSI strategy.
        
        Args:
            rsi_period: Period for RSI calculation
            oversold_level: RSI level to consider oversold (buy signal)
            overbought_level: RSI level to consider overbought (sell signal)
        """
        self.rsi_period = rsi_period
        self.oversold_level = oversold_level
        self.overbought_level = overbought_level
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals based on RSI.
        
        Returns:
            Series with values: 1 (buy), -1 (sell), 0 (hold)
        """
        # Calculate RSI
        rsi = self.calculate_rsi(data['Close'])
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        
        # Buy when RSI crosses below oversold level
        signals[rsi < self.oversold_level] = 1
        
        # Sell when RSI crosses above overbought level
        signals[rsi > self.overbought_level] = -1
        
        # Clean up signals (only trigger on crossovers)
        signals_clean = signals.diff()
        signals_clean[signals_clean > 0] = 1  # Buy signal
        signals_clean[signals_clean < 0] = -1  # Sell signal
        signals_clean[(signals_clean != 1) & (signals_clean != -1)] = 0
        
        return signals_clean