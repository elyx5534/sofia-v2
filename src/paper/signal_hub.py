"""
Signal Hub for Strategy Fusion and ML Integration
"""

import os
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
import numpy as np
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    timestamp: datetime
    strategy: str
    direction: int  # +1 buy, 0 neutral, -1 sell
    strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any]


class SignalHub:
    """Signal aggregation and fusion hub"""
    
    def __init__(self):
        self.ml_enabled = os.getenv('ML_PREDICTOR_ENABLED', 'false').lower() == 'true'
        self.ml_weight = 0.5  # Weight for ML contribution
        
        # Import new strategies
        from src.strategies.donchian_breakout import DonchianBreakoutStrategy
        from src.strategies.supertrend import SuperTrendStrategy
        from src.strategies.bollinger_revert import BollingerRevertStrategy
        
        # Strategy instances
        self.strategies = {
            'sma_cross': SMACrossStrategy(),
            'ema_breakout': EMABreakoutStrategy(),
            'rsi_mean_reversion': RSIMeanReversionStrategy(),
            'donchian_breakout': DonchianBreakoutStrategy(),
            'supertrend': SuperTrendStrategy(),
            'bollinger_revert': BollingerRevertStrategy()
        }
        
        # OHLCV data storage
        self.ohlcv_data: Dict[str, pd.DataFrame] = {}
        
        # Signal cache
        self.signal_cache: Dict[str, List[Signal]] = {}
        
    async def initialize(self):
        """Initialize signal hub"""
        logger.info("Initializing signal hub...")
        
        # Initialize strategies
        for name, strategy in self.strategies.items():
            strategy.initialize()
            
        logger.info(f"Signal hub initialized with {len(self.strategies)} strategies")
    
    def update_ohlcv(self, symbol: str, ohlcv: List):
        """Update OHLCV data for symbol"""
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        self.ohlcv_data[symbol] = df
        
        # Update strategies with new data
        for strategy in self.strategies.values():
            strategy.update_data(symbol, df)
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Dict[str, Any]:
        """Get fused signal for symbol"""
        if symbol not in self.ohlcv_data:
            return {'symbol': symbol, 'strength': 0, 'confidence': 0}
        
        # Collect signals from all strategies
        signals = []
        
        for name, strategy in self.strategies.items():
            try:
                signal = strategy.get_signal(symbol, current_price)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"Strategy {name} failed for {symbol}: {e}")
        
        if not signals:
            return {'symbol': symbol, 'strength': 0, 'confidence': 0}
        
        # Apply fusion logic
        fused_signal = self._fuse_signals(signals)
        
        # Apply ML contribution if enabled
        if self.ml_enabled:
            ml_signal = self._get_ml_signal(symbol, current_price)
            if ml_signal:
                fused_signal = self._apply_ml_weight(fused_signal, ml_signal)
        
        # Cache signal
        if symbol not in self.signal_cache:
            self.signal_cache[symbol] = []
        self.signal_cache[symbol].append(Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            strategy='fusion',
            direction=int(np.sign(fused_signal['strength'])),
            strength=abs(fused_signal['strength']),
            confidence=fused_signal['confidence'],
            metadata=fused_signal
        ))
        
        return fused_signal
    
    def _fuse_signals(self, signals: List[Signal]) -> Dict[str, Any]:
        """Fuse multiple signals using majority vote with confidence weighting"""
        if not signals:
            return {'strength': 0, 'confidence': 0}
        
        # Weighted voting
        total_weight = 0
        weighted_direction = 0
        
        for signal in signals:
            weight = signal.confidence
            weighted_direction += signal.direction * weight
            total_weight += weight
        
        if total_weight == 0:
            return {'strength': 0, 'confidence': 0}
        
        # Calculate fused direction
        fused_direction = weighted_direction / total_weight
        
        # Calculate average confidence
        avg_confidence = np.mean([s.confidence for s in signals])
        
        # Calculate strength (normalized)
        strength = min(1.0, abs(fused_direction))
        
        # Adjust sign based on direction
        if fused_direction < 0:
            strength = -strength
        
        return {
            'strength': strength,
            'confidence': avg_confidence,
            'num_signals': len(signals),
            'strategies': [s.strategy for s in signals],
            'directions': [s.direction for s in signals]
        }
    
    def _get_ml_signal(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Get ML prediction signal"""
        try:
            # Mock ML prediction - replace with actual ML model
            # In production, this would call the ML predictor service
            
            # Simulate ML prediction
            import random
            direction = random.choice([-1, 0, 1])
            probability = random.uniform(0.4, 0.8)
            
            if probability > 0.6:  # Only use high confidence predictions
                return Signal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    strategy='ml_predictor',
                    direction=direction,
                    strength=probability,
                    confidence=probability,
                    metadata={'model': 'mock', 'features': 10}
                )
        except Exception as e:
            logger.warning(f"ML prediction failed for {symbol}: {e}")
        
        return None
    
    def _apply_ml_weight(self, fused_signal: Dict[str, Any], ml_signal: Signal) -> Dict[str, Any]:
        """Apply ML weight to fused signal"""
        # Weighted average between fused and ML
        ml_contribution = ml_signal.direction * ml_signal.confidence * self.ml_weight
        current_strength = fused_signal['strength']
        
        # Combine with ML
        new_strength = current_strength * (1 - self.ml_weight) + ml_contribution
        
        # Update confidence
        new_confidence = (fused_signal['confidence'] + ml_signal.confidence) / 2
        
        fused_signal['strength'] = new_strength
        fused_signal['confidence'] = new_confidence
        fused_signal['ml_contribution'] = ml_contribution
        
        return fused_signal


class BaseStrategy:
    """Base strategy class"""
    
    def __init__(self):
        self.data: Dict[str, pd.DataFrame] = {}
        self.indicators: Dict[str, pd.DataFrame] = {}
        
    def initialize(self):
        """Initialize strategy"""
        pass
    
    def update_data(self, symbol: str, df: pd.DataFrame):
        """Update data for symbol"""
        self.data[symbol] = df
        self._calculate_indicators(symbol)
    
    def _calculate_indicators(self, symbol: str):
        """Calculate strategy indicators"""
        raise NotImplementedError
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Get strategy signal"""
        raise NotImplementedError


class SMACrossStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy"""
    
    def __init__(self):
        super().__init__()
        self.fast_period = 20
        self.slow_period = 50
    
    def _calculate_indicators(self, symbol: str):
        """Calculate SMA indicators"""
        if symbol not in self.data:
            return
        
        df = self.data[symbol]
        
        # Calculate SMAs
        df['sma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=self.slow_period).mean()
        
        # Calculate crossover signals
        df['signal'] = 0
        df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
        df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
        
        self.indicators[symbol] = df
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Get SMA crossover signal"""
        if symbol not in self.indicators:
            return None
        
        df = self.indicators[symbol]
        
        if len(df) < self.slow_period:
            return None
        
        # Get latest signal
        latest_signal = df['signal'].iloc[-1]
        prev_signal = df['signal'].iloc[-2] if len(df) > 1 else 0
        
        # Check for crossover
        if latest_signal != prev_signal and latest_signal != 0:
            # Calculate confidence based on separation
            sma_fast = df['sma_fast'].iloc[-1]
            sma_slow = df['sma_slow'].iloc[-1]
            separation = abs(sma_fast - sma_slow) / sma_slow
            confidence = min(1.0, separation * 100)  # Scale separation to confidence
            
            return Signal(
                symbol=symbol,
                timestamp=datetime.now(),
                strategy='sma_cross',
                direction=int(latest_signal),
                strength=confidence,
                confidence=confidence,
                metadata={
                    'sma_fast': float(sma_fast),
                    'sma_slow': float(sma_slow),
                    'crossover': True
                }
            )
        
        return None


class EMABreakoutStrategy(BaseStrategy):
    """Exponential Moving Average Breakout Strategy"""
    
    def __init__(self):
        super().__init__()
        self.ema_period = 21
        self.breakout_threshold = 0.02  # 2% breakout
    
    def _calculate_indicators(self, symbol: str):
        """Calculate EMA indicators"""
        if symbol not in self.data:
            return
        
        df = self.data[symbol]
        
        # Calculate EMA
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()
        
        # Calculate breakout
        df['breakout'] = (df['close'] - df['ema']) / df['ema']
        
        self.indicators[symbol] = df
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Get EMA breakout signal"""
        if symbol not in self.indicators:
            return None
        
        df = self.indicators[symbol]
        
        if len(df) < self.ema_period:
            return None
        
        # Check for breakout
        breakout = df['breakout'].iloc[-1]
        
        if abs(breakout) > self.breakout_threshold:
            direction = 1 if breakout > 0 else -1
            strength = min(1.0, abs(breakout) / self.breakout_threshold)
            
            return Signal(
                symbol=symbol,
                timestamp=datetime.now(),
                strategy='ema_breakout',
                direction=direction,
                strength=strength,
                confidence=strength * 0.8,  # Slightly lower confidence
                metadata={
                    'ema': float(df['ema'].iloc[-1]),
                    'breakout_pct': float(breakout * 100)
                }
            )
        
        return None


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI Mean Reversion Strategy"""
    
    def __init__(self):
        super().__init__()
        self.rsi_period = 14
        self.oversold = 30
        self.overbought = 70
    
    def _calculate_indicators(self, symbol: str):
        """Calculate RSI indicators"""
        if symbol not in self.data:
            return
        
        df = self.data[symbol]
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        self.indicators[symbol] = df
    
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Get RSI mean reversion signal"""
        if symbol not in self.indicators:
            return None
        
        df = self.indicators[symbol]
        
        if len(df) < self.rsi_period:
            return None
        
        rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2] if len(df) > 1 else rsi
        
        # Check for oversold/overbought conditions
        if rsi < self.oversold and prev_rsi >= self.oversold:
            # Oversold - buy signal
            strength = (self.oversold - rsi) / self.oversold
            
            return Signal(
                symbol=symbol,
                timestamp=datetime.now(),
                strategy='rsi_mean_reversion',
                direction=1,
                strength=strength,
                confidence=strength * 0.7,
                metadata={
                    'rsi': float(rsi),
                    'condition': 'oversold'
                }
            )
        
        elif rsi > self.overbought and prev_rsi <= self.overbought:
            # Overbought - sell signal
            strength = (rsi - self.overbought) / (100 - self.overbought)
            
            return Signal(
                symbol=symbol,
                timestamp=datetime.now(),
                strategy='rsi_mean_reversion',
                direction=-1,
                strength=strength,
                confidence=strength * 0.7,
                metadata={
                    'rsi': float(rsi),
                    'condition': 'overbought'
                }
            )
        
        return None