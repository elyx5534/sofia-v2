"""
Sofia V2 Trading Indicators - Professional Technical Analysis
Advanced indicators used by hedge funds and quant traders
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional
from collections import deque
import talib
import math
from scipy import stats
from sklearn.preprocessing import MinMaxScaler
from scipy.signal import argrelextrema

import structlog

logger = structlog.get_logger(__name__)

class AdvancedIndicators:
    """Advanced technical indicators for professional trading"""
    
    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
        
        prices_array = np.array(prices[-period*2:])  # Use more data for accuracy
        return talib.EMA(prices_array, timeperiod=period)[-1]
    
    @staticmethod
    def sma(prices: List[float], period: int) -> float:
        """Simple Moving Average"""
        if len(prices) < period:
            return np.mean(prices) if prices else 0.0
        return np.mean(prices[-period:])
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        prices_array = np.array(prices)
        return talib.RSI(prices_array, timeperiod=period)[-1]
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0
        
        prices_array = np.array(prices)
        macd, macd_signal, macd_hist = talib.MACD(prices_array, fastperiod=fast, slowperiod=slow, signalperiod=signal)
        return macd[-1], macd_signal[-1], macd_hist[-1]
    
    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std: float = 2.0) -> Tuple[float, float, float]:
        """Bollinger Bands"""
        if len(prices) < period:
            return 0.0, 0.0, 0.0
        
        prices_array = np.array(prices)
        upper, middle, lower = talib.BBANDS(prices_array, timeperiod=period, nbdevup=std, nbdevdn=std)
        return upper[-1], middle[-1], lower[-1]
    
    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float], k: int = 14, d: int = 3) -> Tuple[float, float]:
        """Stochastic Oscillator"""
        if len(closes) < k:
            return 50.0, 50.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        slowk, slowd = talib.STOCH(highs_array, lows_array, closes_array, 
                                  fastk_period=k, slowk_period=d, slowd_period=d)
        return slowk[-1], slowd[-1]
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Average True Range - Volatility Indicator"""
        if len(closes) < period:
            return 0.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        atr = talib.ATR(highs_array, lows_array, closes_array, timeperiod=period)
        return atr[-1]
    
    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Average Directional Index - Trend Strength"""
        if len(closes) < period * 2:
            return 0.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        adx = talib.ADX(highs_array, lows_array, closes_array, timeperiod=period)
        return adx[-1]
    
    @staticmethod
    def williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Williams %R"""
        if len(closes) < period:
            return -50.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        willr = talib.WILLR(highs_array, lows_array, closes_array, timeperiod=period)
        return willr[-1]
    
    @staticmethod
    def cci(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Commodity Channel Index"""
        if len(closes) < period:
            return 0.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        
        cci = talib.CCI(highs_array, lows_array, closes_array, timeperiod=period)
        return cci[-1]

class QuantitativeIndicators:
    """Quantitative indicators used by hedge funds"""
    
    @staticmethod
    def hurst_exponent(prices: List[float], max_lag: int = 20) -> float:
        """Hurst Exponent - Measures trend persistence"""
        if len(prices) < max_lag * 2:
            return 0.5
        
        prices_array = np.array(prices)
        lags = range(2, max_lag + 1)
        
        # Calculate the array of the variances of the lagged differences
        tau = [np.sqrt(np.std(np.subtract(prices_array[lag:], prices_array[:-lag]))) for lag in lags]
        
        # Use a linear fit to estimate the Hurst Exponent
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        
        # Return the Hurst exponent from the polyfit output
        return poly[0]
    
    @staticmethod
    def fractal_dimension(prices: List[float]) -> float:
        """Fractal Dimension - Market complexity measure"""
        if len(prices) < 10:
            return 1.5
        
        hurst = QuantitativeIndicators.hurst_exponent(prices)
        return 2 - hurst
    
    @staticmethod
    def shannon_entropy(prices: List[float], bins: int = 10) -> float:
        """Shannon Entropy - Price uncertainty measure"""
        if len(prices) < bins:
            return 0.0
        
        # Calculate returns
        returns = np.diff(np.array(prices)) / np.array(prices[:-1])
        
        # Create histogram
        counts, _ = np.histogram(returns, bins=bins)
        
        # Calculate probabilities
        probabilities = counts / len(returns)
        
        # Remove zeros to avoid log(0)
        probabilities = probabilities[probabilities > 0]
        
        # Calculate Shannon entropy
        entropy = -np.sum(probabilities * np.log2(probabilities))
        return entropy
    
    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Kelly Criterion for optimal position sizing"""
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        win_loss_ratio = avg_win / abs(avg_loss)
        kelly_percentage = win_rate - (1 - win_rate) / win_loss_ratio
        
        # Cap at 25% for safety
        return min(max(kelly_percentage, 0), 0.25)
    
    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Sharpe Ratio - Risk-adjusted returns"""
        if len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    @staticmethod
    def maximum_drawdown(prices: List[float]) -> float:
        """Maximum Drawdown"""
        if len(prices) < 2:
            return 0.0
        
        prices_array = np.array(prices)
        peak = np.maximum.accumulate(prices_array)
        drawdown = (peak - prices_array) / peak
        return np.max(drawdown)
    
    @staticmethod
    def value_at_risk(returns: List[float], confidence: float = 0.05) -> float:
        """Value at Risk (VaR)"""
        if len(returns) < 10:
            return 0.0
        
        returns_array = np.array(returns)
        return np.percentile(returns_array, confidence * 100)
    
    @staticmethod
    def conditional_value_at_risk(returns: List[float], confidence: float = 0.05) -> float:
        """Conditional Value at Risk (CVaR)"""
        var = QuantitativeIndicators.value_at_risk(returns, confidence)
        returns_array = np.array(returns)
        return np.mean(returns_array[returns_array <= var])

class MachineLearningIndicators:
    """ML-based indicators for advanced pattern recognition"""
    
    @staticmethod
    def price_momentum_score(prices: List[float], lookback: int = 20) -> float:
        """ML-based momentum score"""
        if len(prices) < lookback + 1:
            return 0.0
        
        prices_array = np.array(prices[-lookback-1:])
        
        # Calculate multiple momentum factors
        returns = np.diff(prices_array) / prices_array[:-1]
        
        # Recent vs older momentum
        recent_momentum = np.mean(returns[-5:]) if len(returns) >= 5 else 0
        older_momentum = np.mean(returns[-lookback:-5]) if len(returns) >= lookback else 0
        
        # Acceleration
        acceleration = recent_momentum - older_momentum
        
        # Volatility-adjusted momentum
        volatility = np.std(returns) if len(returns) > 1 else 1
        vol_adj_momentum = recent_momentum / max(volatility, 0.001)
        
        # Combine factors
        momentum_score = (recent_momentum * 0.4 + 
                         acceleration * 0.3 + 
                         vol_adj_momentum * 0.3)
        
        return momentum_score
    
    @staticmethod
    def support_resistance_strength(prices: List[float], window: int = 20) -> Tuple[float, float, float]:
        """Support/Resistance level strength using local extrema"""
        if len(prices) < window * 2:
            return 0.0, 0.0, 0.0
        
        prices_array = np.array(prices)
        
        # Find local maxima and minima
        local_maxima = argrelextrema(prices_array, np.greater, order=window//4)[0]
        local_minima = argrelextrema(prices_array, np.less, order=window//4)[0]
        
        current_price = prices_array[-1]
        
        # Calculate distance to nearest support/resistance
        if len(local_maxima) > 0:
            resistance_levels = prices_array[local_maxima]
            resistance_distances = np.abs(resistance_levels - current_price) / current_price
            nearest_resistance = np.min(resistance_distances)
        else:
            nearest_resistance = 1.0
        
        if len(local_minima) > 0:
            support_levels = prices_array[local_minima]
            support_distances = np.abs(support_levels - current_price) / current_price
            nearest_support = np.min(support_distances)
        else:
            nearest_support = 1.0
        
        # Calculate strength (inverse of distance)
        resistance_strength = 1 / (1 + nearest_resistance)
        support_strength = 1 / (1 + nearest_support)
        
        # Overall level strength
        level_strength = (resistance_strength + support_strength) / 2
        
        return support_strength, resistance_strength, level_strength
    
    @staticmethod
    def pattern_recognition_score(prices: List[float], volumes: List[float] = None) -> Dict[str, float]:
        """Advanced pattern recognition using multiple techniques"""
        if len(prices) < 50:
            return {'trend_strength': 0.0, 'reversal_probability': 0.0, 'breakout_potential': 0.0}
        
        prices_array = np.array(prices)
        
        # Linear regression for trend
        x = np.arange(len(prices_array))
        slope, intercept, r_value, _, _ = stats.linregress(x, prices_array)
        trend_strength = abs(r_value)  # R-squared shows trend strength
        
        # Reversal indicators
        recent_prices = prices_array[-20:]
        price_std = np.std(recent_prices)
        price_mean = np.mean(recent_prices)
        z_score = (prices_array[-1] - price_mean) / max(price_std, 0.001)
        reversal_probability = min(abs(z_score) / 2, 1.0)
        
        # Breakout potential (volatility expansion)
        short_vol = np.std(prices_array[-10:]) if len(prices_array) >= 10 else 0
        long_vol = np.std(prices_array[-30:]) if len(prices_array) >= 30 else short_vol
        breakout_potential = short_vol / max(long_vol, 0.001) if long_vol > 0 else 0
        
        return {
            'trend_strength': trend_strength,
            'reversal_probability': reversal_probability,
            'breakout_potential': min(breakout_potential, 2.0)  # Cap at 2x
        }

class MarketMicrostructureIndicators:
    """Market microstructure indicators for HFT-style analysis"""
    
    @staticmethod
    def order_flow_imbalance(buy_volume: List[float], sell_volume: List[float]) -> float:
        """Order flow imbalance indicator"""
        if not buy_volume or not sell_volume or len(buy_volume) != len(sell_volume):
            return 0.0
        
        total_buy = sum(buy_volume)
        total_sell = sum(sell_volume)
        total_volume = total_buy + total_sell
        
        if total_volume == 0:
            return 0.0
        
        return (total_buy - total_sell) / total_volume
    
    @staticmethod
    def volume_weighted_average_price(prices: List[float], volumes: List[float]) -> float:
        """VWAP calculation"""
        if not prices or not volumes or len(prices) != len(volumes):
            return 0.0
        
        prices_array = np.array(prices)
        volumes_array = np.array(volumes)
        
        total_volume = np.sum(volumes_array)
        if total_volume == 0:
            return np.mean(prices_array)
        
        return np.sum(prices_array * volumes_array) / total_volume
    
    @staticmethod
    def price_volume_trend(prices: List[float], volumes: List[float]) -> float:
        """Price Volume Trend indicator"""
        if len(prices) < 2 or len(volumes) < 2:
            return 0.0
        
        prices_array = np.array(prices)
        volumes_array = np.array(volumes)
        
        price_changes = np.diff(prices_array) / prices_array[:-1]
        pvt = np.sum(price_changes * volumes_array[1:])
        
        return pvt
    
    @staticmethod
    def money_flow_index(highs: List[float], lows: List[float], closes: List[float], 
                        volumes: List[float], period: int = 14) -> float:
        """Money Flow Index"""
        if len(closes) < period + 1:
            return 50.0
        
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        closes_array = np.array(closes)
        volumes_array = np.array(volumes)
        
        mfi = talib.MFI(highs_array, lows_array, closes_array, volumes_array, timeperiod=period)
        return mfi[-1]

class MultiTimeframeAnalysis:
    """Multi-timeframe analysis for professional trading"""
    
    def __init__(self):
        self.timeframes = {
            '1m': deque(maxlen=1440),    # 1 day of 1-minute data
            '5m': deque(maxlen=288),     # 1 day of 5-minute data  
            '15m': deque(maxlen=96),     # 1 day of 15-minute data
            '1h': deque(maxlen=168),     # 1 week of hourly data
            '4h': deque(maxlen=180),     # 1 month of 4-hour data
            '1d': deque(maxlen=365)      # 1 year of daily data
        }
        self.last_update = {}
    
    def update_timeframe_data(self, timeframe: str, price: float, volume: float, timestamp):
        """Update specific timeframe data"""
        if timeframe in self.timeframes:
            self.timeframes[timeframe].append({
                'price': price,
                'volume': volume,
                'timestamp': timestamp
            })
            self.last_update[timeframe] = timestamp
    
    def get_mtf_trend_alignment(self) -> float:
        """Multi-timeframe trend alignment score"""
        trends = {}
        
        for tf, data in self.timeframes.items():
            if len(data) >= 20:
                prices = [d['price'] for d in list(data)[-20:]]
                
                # Calculate trend direction using linear regression
                x = np.arange(len(prices))
                slope, _, r_value, _, _ = stats.linregress(x, prices)
                
                # Trend direction (-1 to 1)
                trend_direction = np.tanh(slope * 100)  # Normalize slope
                trend_strength = abs(r_value)
                
                trends[tf] = {
                    'direction': trend_direction,
                    'strength': trend_strength,
                    'score': trend_direction * trend_strength
                }
        
        if not trends:
            return 0.0
        
        # Calculate alignment score
        scores = [trend['score'] for trend in trends.values()]
        
        # Higher timeframes get more weight
        weights = {'1d': 0.3, '4h': 0.25, '1h': 0.2, '15m': 0.15, '5m': 0.07, '1m': 0.03}
        
        weighted_score = 0.0
        total_weight = 0.0
        
        for tf, trend in trends.items():
            weight = weights.get(tf, 0.1)
            weighted_score += trend['score'] * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_score / total_weight
        
        return np.mean(scores)
    
    def get_mtf_momentum_divergence(self) -> float:
        """Detect momentum divergences across timeframes"""
        momentum_scores = {}
        
        for tf, data in self.timeframes.items():
            if len(data) >= 20:
                prices = [d['price'] for d in list(data)]
                momentum = MachineLearningIndicators.price_momentum_score(prices)
                momentum_scores[tf] = momentum
        
        if len(momentum_scores) < 2:
            return 0.0
        
        # Compare short-term vs long-term momentum
        short_term_avg = np.mean([momentum_scores.get(tf, 0) for tf in ['1m', '5m', '15m']])
        long_term_avg = np.mean([momentum_scores.get(tf, 0) for tf in ['1h', '4h', '1d']])
        
        # Divergence score (negative means bearish divergence, positive means bullish)
        divergence = short_term_avg - long_term_avg
        
        return divergence