"""Base strategy protocol for all trading strategies."""

from abc import ABC, abstractmethod
from typing import List, Any
import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, **params) -> List[int]:
        """
        Generate trading signals based on market data.
        
        Args:
            data: OHLCV DataFrame with columns: open, high, low, close, volume
            **params: Strategy-specific parameters
            
        Returns:
            List of position signals:
                1: Long position
                0: No position (flat)
                -1: Short position
        """
        pass