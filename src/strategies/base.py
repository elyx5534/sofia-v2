"""
Base strategy interface for backtesting
"""

from typing import Dict, Any, Optional
import pandas as pd
from abc import ABC, abstractmethod


class Strategy(ABC):
    """Base strategy class for all trading strategies"""
    
    name: str = "base"
    description: str = "Base strategy"
    
    # Default parameters
    default_params: Dict[str, Any] = {}
    
    # Parameter ranges for optimization
    param_ranges: Dict[str, Dict[str, Any]] = {}
    
    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """
        Generate trading signals from OHLCV data
        
        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume]
            params: Strategy parameters
            
        Returns:
            Series of signals: 1 (buy), -1 (sell), 0 (hold)
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate strategy parameters"""
        for key, value in params.items():
            if key in self.param_ranges:
                range_def = self.param_ranges[key]
                if 'min' in range_def and value < range_def['min']:
                    return False
                if 'max' in range_def and value > range_def['max']:
                    return False
                if 'values' in range_def and value not in range_def['values']:
                    return False
        return True
    
    def preprocess_data(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Preprocess data before generating signals"""
        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in ohlcv.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Sort by index (timestamp)
        ohlcv = ohlcv.sort_index()
        
        # Handle missing values
        ohlcv = ohlcv.fillna(method='ffill').fillna(method='bfill')
        
        return ohlcv
    
    def __call__(self, ohlcv: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.Series:
        """Make strategy callable"""
        if params is None:
            params = self.default_params.copy()
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError(f"Invalid parameters for strategy {self.name}")
        
        # Preprocess data
        ohlcv = self.preprocess_data(ohlcv)
        
        # Generate signals
        return self.generate_signals(ohlcv, params)
    
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': self.description,
            'default_params': self.default_params,
            'param_ranges': self.param_ranges,
        }