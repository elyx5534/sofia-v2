"""
Sofia V2 Trading Strategies - World-Class Algorithmic Trading
Professional strategies competing with hedge funds and quant firms
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import deque, defaultdict
import math
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
import warnings
warnings.filterwarnings('ignore')

import structlog

from .engine import BaseStrategy, OrderSide, Portfolio
from .indicators import (AdvancedIndicators, QuantitativeIndicators, 
                        MachineLearningIndicators, MarketMicrostructureIndicators,
                        MultiTimeframeAnalysis)

logger = structlog.get_logger(__name__)

class MeanReversionStrategy(BaseStrategy):
    """Statistical mean reversion strategy using Bollinger Bands and Z-Score"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'bb_period': 20,
            'bb_std': 2.0,
            'z_score_threshold': 2.0,
            'min_volume': 1000,
            'atr_multiplier': 2.0
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("Mean Reversion", portfolio, default_settings)
        self.z_scores = defaultdict(lambda: deque(maxlen=100))
        self.volume_avg = defaultdict(lambda: deque(maxlen=50))
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < self.settings['bb_period']:
            return None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        volumes = [d['volume'] for d in self.market_data[symbol]]
        
        # Update volume average
        self.volume_avg[symbol].extend(volumes[-10:])
        avg_volume = np.mean(list(self.volume_avg[symbol])) if self.volume_avg[symbol] else 0
        
        # Skip if volume too low
        if price_data['volume'] < max(avg_volume * 0.5, self.settings['min_volume']):
            return None
        
        # Calculate Bollinger Bands
        upper, middle, lower = AdvancedIndicators.bollinger_bands(
            prices, self.settings['bb_period'], self.settings['bb_std']
        )
        
        if upper == 0 or middle == 0 or lower == 0:
            return None
        
        current_price = prices[-1]
        
        # Z-Score calculation
        z_score = (current_price - middle) / max((upper - middle), 0.0001)
        self.z_scores[symbol].append(z_score)
        
        # RSI for additional confirmation
        rsi = AdvancedIndicators.rsi(prices)
        
        # Generate signals
        signal = None
        
        # Oversold condition (buy signal)
        if (z_score < -self.settings['z_score_threshold'] and 
            rsi < 30 and 
            current_price <= lower):
            
            signal = {
                'symbol': symbol,
                'side': 'buy',
                'action': 'open',
                'confidence': min(abs(z_score) / 3, 1.0),
                'reason': f'Mean reversion buy: Z={z_score:.2f}, RSI={rsi:.1f}',
                'indicators': {
                    'z_score': z_score,
                    'rsi': rsi,
                    'bb_upper': upper,
                    'bb_lower': lower,
                    'bb_middle': middle
                }
            }
            
        # Overbought condition (sell signal)
        elif (z_score > self.settings['z_score_threshold'] and 
              rsi > 70 and 
              current_price >= upper):
            
            signal = {
                'symbol': symbol,
                'side': 'sell',
                'action': 'open',
                'confidence': min(abs(z_score) / 3, 1.0),
                'reason': f'Mean reversion sell: Z={z_score:.2f}, RSI={rsi:.1f}',
                'indicators': {
                    'z_score': z_score,
                    'rsi': rsi,
                    'bb_upper': upper,
                    'bb_lower': lower,
                    'bb_middle': middle
                }
            }
        
        # Mean reversion exit signals
        elif len(self.z_scores[symbol]) >= 2:
            prev_z = self.z_scores[symbol][-2]
            
            # Exit long when crossing above mean
            if prev_z < -0.5 and z_score > -0.5:
                signal = {
                    'symbol': symbol,
                    'action': 'close',
                    'reason': 'Mean reversion exit: returning to mean'
                }
            
            # Exit short when crossing below mean
            elif prev_z > 0.5 and z_score < 0.5:
                signal = {
                    'symbol': symbol,
                    'action': 'close',
                    'reason': 'Mean reversion exit: returning to mean'
                }
        
        if signal:
            self.total_signals += 1
        
        return signal
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < 20:
            return None, None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        
        # Use ATR for stop loss
        atr = AdvancedIndicators.atr(prices, prices, prices, 14)
        if atr == 0:
            return None, None
        
        stop_loss_distance = atr * self.settings['atr_multiplier']
        
        # Mean reversion typically has tight stops
        stop_loss = current_price - stop_loss_distance
        take_profit = current_price + stop_loss_distance * 1.5  # 1.5:1 R/R
        
        return stop_loss, take_profit

class MomentumBreakoutStrategy(BaseStrategy):
    """Momentum breakout strategy with volume confirmation"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'lookback_period': 20,
            'breakout_threshold': 0.02,  # 2% breakout
            'volume_multiplier': 1.5,
            'atr_period': 14,
            'rsi_overbought': 80,
            'rsi_oversold': 20
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("Momentum Breakout", portfolio, default_settings)
        self.resistance_levels = defaultdict(lambda: deque(maxlen=10))
        self.support_levels = defaultdict(lambda: deque(maxlen=10))
        self.volume_sma = defaultdict(lambda: deque(maxlen=50))
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < self.settings['lookback_period']:
            return None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        volumes = [d['volume'] for d in self.market_data[symbol]]
        
        current_price = prices[-1]
        current_volume = price_data['volume']
        
        # Update volume SMA
        self.volume_sma[symbol].extend(volumes[-10:])
        avg_volume = np.mean(list(self.volume_sma[symbol])) if self.volume_sma[symbol] else current_volume
        
        # Find support and resistance levels
        recent_prices = prices[-self.settings['lookback_period']:]
        resistance = max(recent_prices)
        support = min(recent_prices)
        
        # Update levels
        if len(self.resistance_levels[symbol]) == 0 or resistance > max(self.resistance_levels[symbol]):
            self.resistance_levels[symbol].append(resistance)
        if len(self.support_levels[symbol]) == 0 or support < min(self.support_levels[symbol]):
            self.support_levels[symbol].append(support)
        
        # Calculate breakout thresholds
        breakout_up = resistance * (1 + self.settings['breakout_threshold'])
        breakout_down = support * (1 - self.settings['breakout_threshold'])
        
        # Volume confirmation
        volume_confirmed = current_volume > avg_volume * self.settings['volume_multiplier']
        
        # Additional indicators
        rsi = AdvancedIndicators.rsi(prices)
        macd, macd_signal, macd_hist = AdvancedIndicators.macd(prices)
        adx = AdvancedIndicators.adx(prices, prices, prices)  # Trend strength
        
        # Machine learning momentum score
        momentum_score = MachineLearningIndicators.price_momentum_score(prices)
        
        signal = None
        
        # Bullish breakout
        if (current_price > breakout_up and 
            volume_confirmed and 
            rsi < self.settings['rsi_overbought'] and
            macd > macd_signal and
            adx > 25 and  # Strong trend
            momentum_score > 0.001):
            
            signal = {
                'symbol': symbol,
                'side': 'buy',
                'action': 'open',
                'confidence': min((current_price - resistance) / resistance + 0.3, 1.0),
                'reason': f'Bullish breakout: Price={current_price:.4f}, Resistance={resistance:.4f}',
                'indicators': {
                    'breakout_level': breakout_up,
                    'volume_ratio': current_volume / avg_volume,
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'adx': adx,
                    'momentum_score': momentum_score
                }
            }
        
        # Bearish breakdown
        elif (current_price < breakout_down and 
              volume_confirmed and 
              rsi > self.settings['rsi_oversold'] and
              macd < macd_signal and
              adx > 25 and
              momentum_score < -0.001):
            
            signal = {
                'symbol': symbol,
                'side': 'sell',
                'action': 'open',
                'confidence': min((support - current_price) / support + 0.3, 1.0),
                'reason': f'Bearish breakdown: Price={current_price:.4f}, Support={support:.4f}',
                'indicators': {
                    'breakout_level': breakout_down,
                    'volume_ratio': current_volume / avg_volume,
                    'rsi': rsi,
                    'macd_hist': macd_hist,
                    'adx': adx,
                    'momentum_score': momentum_score
                }
            }
        
        if signal:
            self.total_signals += 1
        
        return signal
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < 20:
            return None, None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        
        # ATR-based stops for breakouts
        atr = AdvancedIndicators.atr(prices, prices, prices, self.settings['atr_period'])
        if atr == 0:
            return None, None
        
        # Breakouts need wider stops
        stop_multiplier = 3.0
        profit_multiplier = 2.0  # 2:1 R/R
        
        stop_loss = current_price - (atr * stop_multiplier)
        take_profit = current_price + (atr * stop_multiplier * profit_multiplier)
        
        return stop_loss, take_profit

class ScalpingStrategy(BaseStrategy):
    """High-frequency scalping strategy for small, quick profits"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'ema_fast': 5,
            'ema_slow': 13,
            'rsi_period': 7,
            'min_profit_pct': 0.001,  # 0.1% minimum profit
            'max_hold_minutes': 15,
            'volume_threshold': 2.0
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("Scalping", portfolio, default_settings)
        self.last_signals = defaultdict(lambda: deque(maxlen=10))
        self.price_ticks = defaultdict(lambda: deque(maxlen=100))
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < self.settings['ema_slow']:
            return None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        volumes = [d['volume'] for d in self.market_data[symbol]]
        
        current_price = prices[-1]
        
        # Store price ticks for microstructure analysis
        self.price_ticks[symbol].append(current_price)
        
        # EMAs for trend
        ema_fast = AdvancedIndicators.ema(prices, self.settings['ema_fast'])
        ema_slow = AdvancedIndicators.ema(prices, self.settings['ema_slow'])
        
        # RSI for momentum
        rsi = AdvancedIndicators.rsi(prices, self.settings['rsi_period'])
        
        # Volume analysis
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        volume_ratio = price_data['volume'] / max(avg_volume, 1)
        
        # Tick analysis for microstructure
        if len(self.price_ticks[symbol]) >= 5:
            recent_ticks = list(self.price_ticks[symbol])[-5:]
            tick_momentum = (recent_ticks[-1] - recent_ticks[0]) / recent_ticks[0]
        else:
            tick_momentum = 0
        
        # Market microstructure indicators
        if len(prices) >= 10:
            vwap = MarketMicrostructureIndicators.volume_weighted_average_price(prices[-10:], volumes[-10:])
        else:
            vwap = current_price
        
        signal = None
        
        # Bullish scalp setup
        if (ema_fast > ema_slow and 
            current_price > ema_fast and
            rsi > 45 and rsi < 65 and  # Not overbought
            volume_ratio > self.settings['volume_threshold'] and
            tick_momentum > 0.0001 and
            current_price > vwap):
            
            signal = {
                'symbol': symbol,
                'side': 'buy',
                'action': 'open',
                'confidence': 0.7,  # Lower confidence for scalping
                'reason': f'Bullish scalp: EMA cross, RSI={rsi:.1f}, Vol={volume_ratio:.1f}x',
                'indicators': {
                    'ema_fast': ema_fast,
                    'ema_slow': ema_slow,
                    'rsi': rsi,
                    'volume_ratio': volume_ratio,
                    'tick_momentum': tick_momentum,
                    'vwap': vwap
                }
            }
        
        # Bearish scalp setup
        elif (ema_fast < ema_slow and 
              current_price < ema_fast and
              rsi < 55 and rsi > 35 and  # Not oversold
              volume_ratio > self.settings['volume_threshold'] and
              tick_momentum < -0.0001 and
              current_price < vwap):
            
            signal = {
                'symbol': symbol,
                'side': 'sell',
                'action': 'open',
                'confidence': 0.7,
                'reason': f'Bearish scalp: EMA cross, RSI={rsi:.1f}, Vol={volume_ratio:.1f}x',
                'indicators': {
                    'ema_fast': ema_fast,
                    'ema_slow': ema_slow,
                    'rsi': rsi,
                    'volume_ratio': volume_ratio,
                    'tick_momentum': tick_momentum,
                    'vwap': vwap
                }
            }
        
        if signal:
            self.total_signals += 1
            self.last_signals[symbol].append(datetime.now(timezone.utc))
        
        return signal
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        # Scalping uses very tight stops
        stop_pct = 0.002  # 0.2% stop loss
        profit_pct = self.settings['min_profit_pct'] * 2  # 0.2% take profit
        
        stop_loss = current_price * (1 - stop_pct)
        take_profit = current_price * (1 + profit_pct)
        
        return stop_loss, take_profit

class GridTradingStrategy(BaseStrategy):
    """Grid trading strategy for ranging markets"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'grid_levels': 10,
            'grid_spacing_pct': 0.005,  # 0.5% spacing
            'base_order_size': 100,
            'max_positions': 5
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("Grid Trading", portfolio, default_settings)
        self.grid_levels = defaultdict(list)
        self.grid_positions = defaultdict(list)
        self.base_price = defaultdict(float)
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < 50:
            return None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        current_price = prices[-1]
        
        # Initialize grid if not exists
        if not self.grid_levels[symbol]:
            self._initialize_grid(symbol, current_price)
        
        # Check for grid trading opportunities
        signal = self._check_grid_levels(symbol, current_price)
        
        if signal:
            self.total_signals += 1
        
        return signal
    
    def _initialize_grid(self, symbol: str, current_price: float):
        """Initialize grid levels around current price"""
        self.base_price[symbol] = current_price
        spacing = self.settings['grid_spacing_pct']
        levels = self.settings['grid_levels']
        
        # Create buy and sell levels
        for i in range(1, levels // 2 + 1):
            buy_level = current_price * (1 - spacing * i)
            sell_level = current_price * (1 + spacing * i)
            
            self.grid_levels[symbol].append({
                'level': buy_level,
                'type': 'buy',
                'active': True
            })
            self.grid_levels[symbol].append({
                'level': sell_level,
                'type': 'sell',
                'active': True
            })
        
        logger.info(f"Grid initialized for {symbol}", 
                   base_price=current_price,
                   levels=len(self.grid_levels[symbol]))
    
    def _check_grid_levels(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """Check if price hit any grid levels"""
        for level in self.grid_levels[symbol]:
            if not level['active']:
                continue
            
            tolerance = current_price * 0.0001  # 0.01% tolerance
            
            # Buy level hit
            if (level['type'] == 'buy' and 
                current_price <= level['level'] + tolerance and
                len([p for p in self.grid_positions[symbol] if p['side'] == 'buy']) < self.settings['max_positions']):
                
                level['active'] = False  # Deactivate this level
                
                return {
                    'symbol': symbol,
                    'side': 'buy',
                    'action': 'open',
                    'confidence': 0.8,
                    'reason': f'Grid buy at {level["level"]:.4f}',
                    'grid_level': level['level']
                }
            
            # Sell level hit  
            elif (level['type'] == 'sell' and 
                  current_price >= level['level'] - tolerance and
                  len([p for p in self.grid_positions[symbol] if p['side'] == 'sell']) < self.settings['max_positions']):
                
                level['active'] = False  # Deactivate this level
                
                return {
                    'symbol': symbol,
                    'side': 'sell', 
                    'action': 'open',
                    'confidence': 0.8,
                    'reason': f'Grid sell at {level["level"]:.4f}',
                    'grid_level': level['level']
                }
        
        return None
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        # Grid trading uses the next grid level as profit target
        spacing = self.settings['grid_spacing_pct']
        
        stop_loss = current_price * (1 - spacing * 2)  # 2 levels down
        take_profit = current_price * (1 + spacing)     # Next level up
        
        return stop_loss, take_profit

class ArbitrageStrategy(BaseStrategy):
    """Cross-exchange arbitrage strategy"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'min_spread_pct': 0.002,  # 0.2% minimum spread
            'max_execution_time': 30,  # seconds
            'transaction_cost_pct': 0.001  # 0.1% transaction costs
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("Arbitrage", portfolio, default_settings)
        self.exchange_prices = defaultdict(dict)  # symbol -> {exchange: price}
        self.last_arbitrage = defaultdict(float)  # symbol -> timestamp
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        exchange = price_data.get('exchange', 'unknown')
        current_price = price_data['price']
        
        # Store price by exchange
        self.exchange_prices[symbol][exchange] = {
            'price': current_price,
            'timestamp': datetime.now(timezone.utc),
            'volume': price_data['volume']
        }
        
        # Need at least 2 exchanges for arbitrage
        if len(self.exchange_prices[symbol]) < 2:
            return None
        
        # Find arbitrage opportunities
        signal = self._find_arbitrage_opportunity(symbol)
        
        if signal:
            self.total_signals += 1
        
        return signal
    
    def _find_arbitrage_opportunity(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Find arbitrage opportunities between exchanges"""
        exchanges = list(self.exchange_prices[symbol].keys())
        current_time = datetime.now(timezone.utc)
        
        # Check all exchange pairs
        for i, exchange1 in enumerate(exchanges):
            for exchange2 in exchanges[i+1:]:
                data1 = self.exchange_prices[symbol][exchange1]
                data2 = self.exchange_prices[symbol][exchange2]
                
                # Check if data is recent (within 5 seconds)
                if ((current_time - data1['timestamp']).seconds > 5 or
                    (current_time - data2['timestamp']).seconds > 5):
                    continue
                
                price1 = data1['price']
                price2 = data2['price']
                
                # Calculate spread
                spread_pct = abs(price1 - price2) / min(price1, price2)
                
                # Check if spread exceeds minimum threshold
                if spread_pct > self.settings['min_spread_pct'] + self.settings['transaction_cost_pct']:
                    
                    # Determine direction (buy low, sell high)
                    if price1 < price2:
                        buy_exchange = exchange1
                        sell_exchange = exchange2
                        profit_pct = (price2 - price1) / price1 - self.settings['transaction_cost_pct']
                    else:
                        buy_exchange = exchange2  
                        sell_exchange = exchange1
                        profit_pct = (price1 - price2) / price2 - self.settings['transaction_cost_pct']
                    
                    # Check if we haven't done arbitrage recently
                    last_arb_time = self.last_arbitrage.get(symbol, 0)
                    if (current_time.timestamp() - last_arb_time) < 60:  # 1 minute cooldown
                        continue
                    
                    self.last_arbitrage[symbol] = current_time.timestamp()
                    
                    return {
                        'symbol': symbol,
                        'side': 'buy',  # We'll handle both sides in execution
                        'action': 'arbitrage',
                        'confidence': min(profit_pct * 10, 1.0),
                        'reason': f'Arbitrage: {spread_pct:.3f}% spread between {buy_exchange} and {sell_exchange}',
                        'arbitrage_data': {
                            'buy_exchange': buy_exchange,
                            'sell_exchange': sell_exchange,
                            'spread_pct': spread_pct,
                            'expected_profit_pct': profit_pct,
                            'buy_price': min(price1, price2),
                            'sell_price': max(price1, price2)
                        }
                    }
        
        return None
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        # Arbitrage has minimal risk if executed quickly
        stop_loss = current_price * 0.995  # 0.5% stop
        take_profit = current_price * 1.005  # 0.5% profit
        
        return stop_loss, take_profit

class MLMomentumStrategy(BaseStrategy):
    """Machine Learning enhanced momentum strategy"""
    
    def __init__(self, portfolio: Portfolio, settings: Dict[str, Any] = None):
        default_settings = {
            'lookback_period': 50,
            'prediction_threshold': 0.6,
            'feature_window': 20,
            'min_confidence': 0.7
        }
        if settings:
            default_settings.update(settings)
        
        super().__init__("ML Momentum", portfolio, default_settings)
        self.feature_history = defaultdict(lambda: deque(maxlen=200))
        self.prediction_models = {}
        
    async def analyze(self, symbol: str, price_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < self.settings['lookback_period']:
            return None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        volumes = [d['volume'] for d in self.market_data[symbol]]
        
        # Extract features
        features = self._extract_features(prices, volumes)
        if not features:
            return None
        
        self.feature_history[symbol].append(features)
        
        # Need enough history to train/predict
        if len(self.feature_history[symbol]) < 50:
            return None
        
        # Get ML prediction
        prediction, confidence = self._get_ml_prediction(symbol)
        
        if confidence < self.settings['min_confidence']:
            return None
        
        signal = None
        
        # Generate trading signals based on ML prediction
        if prediction > self.settings['prediction_threshold']:
            signal = {
                'symbol': symbol,
                'side': 'buy',
                'action': 'open',
                'confidence': confidence,
                'reason': f'ML bullish prediction: {prediction:.3f} (confidence: {confidence:.3f})',
                'ml_prediction': prediction,
                'ml_confidence': confidence
            }
        elif prediction < -self.settings['prediction_threshold']:
            signal = {
                'symbol': symbol,
                'side': 'sell',
                'action': 'open',
                'confidence': confidence,
                'reason': f'ML bearish prediction: {prediction:.3f} (confidence: {confidence:.3f})',
                'ml_prediction': prediction,
                'ml_confidence': confidence
            }
        
        if signal:
            self.total_signals += 1
        
        return signal
    
    def _extract_features(self, prices: List[float], volumes: List[float]) -> Optional[Dict[str, float]]:
        """Extract features for ML model"""
        try:
            if len(prices) < self.settings['feature_window']:
                return None
            
            # Price-based features
            returns = np.diff(prices) / prices[:-1]
            
            features = {
                # Price momentum features
                'return_1': returns[-1] if len(returns) >= 1 else 0,
                'return_5': np.mean(returns[-5:]) if len(returns) >= 5 else 0,
                'return_10': np.mean(returns[-10:]) if len(returns) >= 10 else 0,
                
                # Volatility features
                'volatility_5': np.std(returns[-5:]) if len(returns) >= 5 else 0,
                'volatility_20': np.std(returns[-20:]) if len(returns) >= 20 else 0,
                
                # Technical indicators
                'rsi': AdvancedIndicators.rsi(prices),
                'rsi_divergence': 0,  # Could calculate RSI divergence
                
                # Volume features
                'volume_ratio': volumes[-1] / np.mean(volumes[-10:]) if len(volumes) >= 10 and np.mean(volumes[-10:]) > 0 else 1,
                'volume_trend': stats.linregress(range(len(volumes[-5:])), volumes[-5:])[0] if len(volumes) >= 5 else 0,
                
                # Price pattern features
                'price_position': (prices[-1] - min(prices[-20:])) / (max(prices[-20:]) - min(prices[-20:])) if len(prices) >= 20 and max(prices[-20:]) != min(prices[-20:]) else 0.5,
                
                # Momentum features
                'momentum_score': MachineLearningIndicators.price_momentum_score(prices),
                
                # Support/Resistance
                'support_strength': MachineLearningIndicators.support_resistance_strength(prices)[0],
                'resistance_strength': MachineLearningIndicators.support_resistance_strength(prices)[1],
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None
    
    def _get_ml_prediction(self, symbol: str) -> Tuple[float, float]:
        """Get ML model prediction"""
        try:
            # Prepare training data
            features_list = list(self.feature_history[symbol])
            if len(features_list) < 30:
                return 0.0, 0.0
            
            # Create features matrix
            feature_names = list(features_list[0].keys())
            X = np.array([[f[name] for name in feature_names] for f in features_list[:-1]])
            
            # Create labels (future returns)
            prices = [f.get('return_1', 0) for f in features_list]
            y = np.array([1 if p > 0.001 else (-1 if p < -0.001 else 0) for p in prices[1:]])
            
            # Skip if no variation in labels
            if len(np.unique(y)) < 2:
                return 0.0, 0.0
            
            # Train model if not exists or periodically retrain
            if symbol not in self.prediction_models or len(features_list) % 20 == 0:
                try:
                    from sklearn.ensemble import RandomForestClassifier
                    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
                    model.fit(X, y)
                    self.prediction_models[symbol] = model
                except Exception as e:
                    logger.error(f"Model training error: {e}")
                    return 0.0, 0.0
            
            # Make prediction
            model = self.prediction_models[symbol]
            current_features = np.array([[features_list[-1][name] for name in feature_names]])
            
            # Get prediction probabilities
            proba = model.predict_proba(current_features)[0]
            
            # Convert to prediction score (-1 to 1)
            if len(proba) >= 3:  # -1, 0, 1 classes
                prediction = proba[2] - proba[0]  # P(buy) - P(sell)
                confidence = max(proba[0], proba[2])  # Confidence is max of extreme predictions
            elif len(proba) == 2:  # Binary classification
                prediction = proba[1] * 2 - 1  # Scale to -1 to 1
                confidence = max(proba)
            else:
                prediction, confidence = 0.0, 0.0
            
            return prediction, confidence
            
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return 0.0, 0.0
    
    def get_risk_params(self, symbol: str, current_price: float) -> Tuple[Optional[float], Optional[float]]:
        if symbol not in self.market_data or len(self.market_data[symbol]) < 20:
            return None, None
        
        prices = [d['price'] for d in self.market_data[symbol]]
        
        # Use ATR for dynamic stops
        atr = AdvancedIndicators.atr(prices, prices, prices, 14)
        if atr == 0:
            return None, None
        
        # ML strategies can use wider stops due to higher accuracy
        stop_loss = current_price - (atr * 2.5)
        take_profit = current_price + (atr * 3.0)  # 1.2:1 R/R
        
        return stop_loss, take_profit