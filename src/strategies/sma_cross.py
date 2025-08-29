"""
Simple Moving Average Cross Strategy
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from .base import Strategy


class SmaCross(Strategy):
    """SMA Cross strategy: Buy when fast SMA crosses above slow SMA"""
    
    name = "sma_cross"
    description = "Simple Moving Average Crossover Strategy"
    
    default_params = {
        'fast': 10,
        'slow': 30,
        'signal_mode': 'cross',  # 'cross' or 'position'
    }
    
    param_ranges = {
        'fast': {'min': 5, 'max': 50, 'step': 5},
        'slow': {'min': 20, 'max': 200, 'step': 10},
        'signal_mode': {'values': ['cross', 'position']},
    }
    
    def generate_signals(self, ohlcv: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """Generate SMA cross signals"""
        
        fast_period = params.get('fast', self.default_params['fast'])
        slow_period = params.get('slow', self.default_params['slow'])
        signal_mode = params.get('signal_mode', self.default_params['signal_mode'])
        
        # Validate periods
        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")
        
        # Calculate SMAs
        close = ohlcv['close']
        fast_sma = close.rolling(window=fast_period).mean()
        slow_sma = close.rolling(window=slow_period).mean()
        
        # Generate signals based on mode
        if signal_mode == 'cross':
            # Generate signals only at crossover points
            position = (fast_sma > slow_sma).astype(int)
            signals = position.diff().fillna(0)
            # 1 = buy signal (cross up), -1 = sell signal (cross down), 0 = hold
        else:  # position mode
            # Generate continuous position signals
            signals = (fast_sma > slow_sma).astype(int)
            # Convert to buy/sell signals
            signals = signals.replace(0, -1)  # 1 = long, -1 = short
        
        return signals


class EmaBreakout(Strategy):
    """EMA Breakout strategy with volatility filter"""
    
    name = "ema_breakout"
    description = "Exponential Moving Average Breakout with ATR filter"
    
    default_params = {
        'ema_period': 20,
        'atr_period': 14,
        'atr_multiplier': 2.0,
        'use_volume': False,
    }
    
    param_ranges = {
        'ema_period': {'min': 10, 'max': 100, 'step': 5},
        'atr_period': {'min': 7, 'max': 28, 'step': 7},
        'atr_multiplier': {'min': 1.0, 'max': 4.0, 'step': 0.5},
        'use_volume': {'values': [True, False]},
    }
    
    def generate_signals(self, ohlcv: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """Generate EMA breakout signals"""
        
        ema_period = params.get('ema_period', self.default_params['ema_period'])
        atr_period = params.get('atr_period', self.default_params['atr_period'])
        atr_multiplier = params.get('atr_multiplier', self.default_params['atr_multiplier'])
        use_volume = params.get('use_volume', self.default_params['use_volume'])
        
        # Calculate EMA
        close = ohlcv['close']
        ema = close.ewm(span=ema_period, adjust=False).mean()
        
        # Calculate ATR for volatility
        high = ohlcv['high']
        low = ohlcv['low']
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period).mean()
        
        # Calculate breakout bands
        upper_band = ema + (atr * atr_multiplier)
        lower_band = ema - (atr * atr_multiplier)
        
        # Generate signals
        signals = pd.Series(0, index=ohlcv.index)
        
        # Buy signal: price breaks above upper band
        buy_condition = close > upper_band
        
        # Sell signal: price breaks below lower band
        sell_condition = close < lower_band
        
        # Apply volume filter if enabled
        if use_volume:
            volume = ohlcv['volume']
            volume_sma = volume.rolling(window=20).mean()
            volume_condition = volume > volume_sma
            buy_condition = buy_condition & volume_condition
            sell_condition = sell_condition & volume_condition
        
        # Set signals
        signals[buy_condition] = 1
        signals[sell_condition] = -1
        
        return signals


class RSIMeanReversion(Strategy):
    """RSI Mean Reversion strategy"""
    
    name = "rsi_reversion"
    description = "RSI-based mean reversion strategy"
    
    default_params = {
        'rsi_period': 14,
        'oversold': 30,
        'overbought': 70,
        'exit_at_mean': True,
    }
    
    param_ranges = {
        'rsi_period': {'min': 7, 'max': 28, 'step': 7},
        'oversold': {'min': 20, 'max': 40, 'step': 5},
        'overbought': {'min': 60, 'max': 80, 'step': 5},
        'exit_at_mean': {'values': [True, False]},
    }
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, ohlcv: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
        """Generate RSI mean reversion signals"""
        
        rsi_period = params.get('rsi_period', self.default_params['rsi_period'])
        oversold = params.get('oversold', self.default_params['oversold'])
        overbought = params.get('overbought', self.default_params['overbought'])
        exit_at_mean = params.get('exit_at_mean', self.default_params['exit_at_mean'])
        
        # Calculate RSI
        close = ohlcv['close']
        rsi = self.calculate_rsi(close, rsi_period)
        
        # Generate signals
        signals = pd.Series(0, index=ohlcv.index)
        
        # Buy when RSI is oversold
        signals[rsi < oversold] = 1
        
        # Sell when RSI is overbought
        signals[rsi > overbought] = -1
        
        # Exit at mean if enabled
        if exit_at_mean:
            mean_level = 50
            exit_zone = 5  # Exit within 5 points of mean
            in_position = 0
            
            for i in range(1, len(signals)):
                if signals.iloc[i-1] != 0:
                    in_position = signals.iloc[i-1]
                
                if in_position != 0:
                    # Check for mean reversion exit
                    if abs(rsi.iloc[i] - mean_level) < exit_zone:
                        signals.iloc[i] = -in_position  # Exit signal
                        in_position = 0
        
        return signals