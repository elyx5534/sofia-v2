"""
Pairs Trading with Cointegration Strategy
"""

from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS

from .base import BaseStrategy


class PairsCointStrategy(BaseStrategy):
    """
    Pairs trading using Engle-Granger cointegration test
    
    Parameters:
    - pair_symbols: tuple of two symbols to trade
    - lookback_period: period for cointegration test (60-200)
    - z_entry: z-score threshold for entry (1.5-3.0)
    - z_exit: z-score threshold for exit (0.0-0.5)
    - half_life_max: maximum half-life for mean reversion (20 bars)
    """
    
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'pair_symbols': ('BTC/USDT', 'ETH/USDT'),
            'lookback_period': 120,
            'z_entry': 2.0,
            'z_exit': 0.3,
            'half_life_max': 20,
            'min_correlation': 0.7,
            'atr_stop_k': 2.5,
            'take_profit_k': 1.5,
            'max_hold_bars': 48
        }
        
        if params:
            default_params.update(params)
        
        super().__init__(default_params)
        self.pair_symbols = self.params['pair_symbols']
        self.symbol_a, self.symbol_b = self.pair_symbols
        self.lookback_period = self.params['lookback_period']
        self.z_entry = self.params['z_entry']
        self.z_exit = self.params['z_exit']
        self.half_life_max = self.params['half_life_max']
        self.min_correlation = self.params['min_correlation']
        
        # Store both symbols' data
        self.pair_data: Dict[str, pd.DataFrame] = {}
        self.spread_data: pd.DataFrame = None
        self.hedge_ratio: float = 1.0
        self.cointegration_pvalue: float = 1.0
        
    def update_pair_data(self, symbol_a_data: pd.DataFrame, symbol_b_data: pd.DataFrame):
        """Update data for both symbols in the pair"""
        self.pair_data[self.symbol_a] = symbol_a_data.copy()
        self.pair_data[self.symbol_b] = symbol_b_data.copy()
        
        # Update individual symbol data for base class
        self.update_data(self.symbol_a, symbol_a_data)
        
        # Calculate pair-specific indicators
        self._calculate_pair_indicators()
    
    def _calculate_strategy_indicators(self, symbol: str):
        """Individual symbol indicators (handled by base class)"""
        # Base class handles common indicators
        pass
    
    def _calculate_pair_indicators(self):
        """Calculate pairs trading indicators"""
        if len(self.pair_data) < 2:
            return
        
        df_a = self.pair_data[self.symbol_a]
        df_b = self.pair_data[self.symbol_b]
        
        # Align data by timestamp
        combined = pd.merge(df_a[['close']], df_b[['close']], 
                          left_index=True, right_index=True, 
                          suffixes=('_a', '_b'))
        
        if len(combined) < self.lookback_period:
            return
        
        # Keep only recent data for analysis
        recent_data = combined.tail(self.lookback_period)
        
        price_a = recent_data['close_a']
        price_b = recent_data['close_b']
        
        # Calculate correlation
        correlation = price_a.corr(price_b)
        
        if correlation < self.min_correlation:
            self.spread_data = None
            return
        
        # Cointegration test
        try:
            coint_result = coint(price_a, price_b)
            self.cointegration_pvalue = coint_result[1]
            
            if self.cointegration_pvalue > 0.05:  # Not cointegrated
                self.spread_data = None
                return
                
        except Exception as e:
            self.spread_data = None
            return
        
        # Calculate hedge ratio using OLS regression
        # price_a = alpha + beta * price_b + residuals
        try:
            model = OLS(price_a, price_b).fit()
            self.hedge_ratio = model.params.iloc[0]
            residuals = model.resid
        except Exception as e:
            self.hedge_ratio = 1.0
            residuals = price_a - price_b
        
        # Create spread
        spread = price_a - self.hedge_ratio * price_b
        
        # Z-score of spread
        spread_mean = spread.rolling(window=self.lookback_period//2).mean()
        spread_std = spread.rolling(window=self.lookback_period//2).std()
        z_score = (spread - spread_mean) / spread_std
        
        # Half-life calculation (mean reversion speed)
        spread_diff = spread.diff().dropna()
        spread_lag = spread.shift(1).dropna()
        
        # Align the series
        min_len = min(len(spread_diff), len(spread_lag))
        spread_diff = spread_diff.iloc[-min_len:]
        spread_lag = spread_lag.iloc[-min_len:]
        
        try:
            regression = OLS(spread_diff, spread_lag).fit()
            half_life = -np.log(2) / regression.params.iloc[0] if regression.params.iloc[0] < 0 else 999
        except:
            half_life = 999
        
        # Store spread data
        self.spread_data = pd.DataFrame({
            'spread': spread,
            'z_score': z_score,
            'spread_mean': spread_mean,
            'spread_std': spread_std,
            'correlation': correlation,
            'half_life': half_life
        }, index=combined.index)
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Generate pairs trading signal"""
        # Pairs trading signals are generated for the primary symbol
        if symbol != self.symbol_a or self.spread_data is None:
            return None
        
        if len(self.spread_data) < 20:
            return None
        
        latest = self.spread_data.iloc[-1]
        
        signal = {
            'strategy': 'pairs_coint',
            'symbol': symbol,
            'pair_symbol': self.symbol_b,
            'direction': 0,
            'strength': 0.0,
            'confidence': 0.0,
            'metadata': {}
        }
        
        z_score = latest['z_score']
        half_life = latest['half_life']
        
        # Only trade if half-life is reasonable (mean-reverting)
        if half_life > self.half_life_max:
            return None
        
        # Entry signals based on z-score
        if z_score > self.z_entry:
            # Spread is high: short A, long B
            # For our primary symbol A, this is a short signal
            signal['direction'] = -1
            
            # Strength based on z-score magnitude
            signal['strength'] = min(abs(z_score) / self.z_entry * 0.6, 1.0)
            
            # Confidence based on cointegration strength and mean reversion speed
            confidence = 0.5
            if self.cointegration_pvalue < 0.01:  # Strong cointegration
                confidence += 0.2
            elif self.cointegration_pvalue < 0.05:
                confidence += 0.1
            
            if half_life < self.half_life_max / 2:  # Fast mean reversion
                confidence += 0.15
            
            if latest['correlation'] > 0.8:  # High correlation
                confidence += 0.1
            
            signal['confidence'] = min(confidence, 1.0)
            
        elif z_score < -self.z_entry:
            # Spread is low: long A, short B
            # For our primary symbol A, this is a long signal
            signal['direction'] = 1
            
            signal['strength'] = min(abs(z_score) / self.z_entry * 0.6, 1.0)
            
            # Same confidence calculation
            confidence = 0.5
            if self.cointegration_pvalue < 0.01:
                confidence += 0.2
            elif self.cointegration_pvalue < 0.05:
                confidence += 0.1
            
            if half_life < self.half_life_max / 2:
                confidence += 0.15
            
            if latest['correlation'] > 0.8:
                confidence += 0.1
            
            signal['confidence'] = min(confidence, 1.0)
        
        if signal['direction'] != 0:
            signal['metadata'] = {
                'z_score': z_score,
                'hedge_ratio': self.hedge_ratio,
                'spread': latest['spread'],
                'correlation': latest['correlation'],
                'cointegration_pvalue': self.cointegration_pvalue,
                'half_life': half_life,
                'pair_type': 'long_short' if signal['direction'] == 1 else 'short_long'
            }
            
            # Apply base filters (but pairs trading is less affected by trend filters)
            # Override some trend filters for pairs trading
            original_trend_filter = self.params.get('trend_filter', True)
            self.params['trend_filter'] = False  # Disable trend filter for pairs
            signal = self._apply_filters(symbol, signal)
            self.params['trend_filter'] = original_trend_filter  # Restore
        
        return signal if signal['strength'] > 0.1 else None
    
    def get_exit_signals(self, symbol: str, position: Dict[str, Any]) -> Dict[str, Any]:
        """Pairs trading exit signals"""
        # Check base exit conditions first
        base_exit = super().get_exit_signals(symbol, position)
        if base_exit['should_exit']:
            return base_exit
        
        if self.spread_data is None or len(self.spread_data) == 0:
            return {'should_exit': True, 'reason': 'no_spread_data', 'urgency': 'high'}
        
        latest = self.spread_data.iloc[-1]
        z_score = latest['z_score']
        position_side = position['side']
        
        # Exit when spread reverts to mean
        if abs(z_score) < self.z_exit:
            return {'should_exit': True, 'reason': 'spread_mean_revert', 'urgency': 'medium'}
        
        # Exit if cointegration breaks down
        if self.cointegration_pvalue > 0.1:
            return {'should_exit': True, 'reason': 'cointegration_breakdown', 'urgency': 'high'}
        
        # Exit if correlation drops significantly
        if latest['correlation'] < self.min_correlation * 0.8:
            return {'should_exit': True, 'reason': 'correlation_breakdown', 'urgency': 'high'}
        
        # Exit if half-life becomes too long (losing mean reversion)
        if latest['half_life'] > self.half_life_max * 1.5:
            return {'should_exit': True, 'reason': 'slow_mean_reversion', 'urgency': 'medium'}
        
        return {'should_exit': False}
    
    def calculate_pair_position_sizes(self, symbol: str, signal_strength: float, 
                                    balance: Decimal, k_factor: Decimal) -> Tuple[Decimal, Decimal]:
        """Calculate position sizes for both legs of the pair"""
        if symbol != self.symbol_a or self.spread_data is None:
            return Decimal('0'), Decimal('0')
        
        # Get current prices
        price_a = Decimal(str(self.pair_data[self.symbol_a]['close'].iloc[-1]))
        price_b = Decimal(str(self.pair_data[self.symbol_b]['close'].iloc[-1]))
        
        # Total risk for the pair trade
        total_risk = balance * k_factor * Decimal(str(abs(signal_strength)))
        
        # Calculate position sizes maintaining hedge ratio
        hedge_ratio_decimal = Decimal(str(abs(self.hedge_ratio)))
        
        # Position size for symbol A
        size_a = total_risk / (price_a + hedge_ratio_decimal * price_b)
        
        # Position size for symbol B (hedged)
        size_b = size_a * hedge_ratio_decimal
        
        return size_a, size_b