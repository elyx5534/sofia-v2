"""
Trend following strategy implementation for Sofia V2.
Uses moving average crossovers with volatility filters and stop losses.
"""

import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .base import Signal, SignalType, Strategy

logger = logging.getLogger(__name__)


class TrendStrategy(Strategy):
    """
    Trend following strategy with MA crossovers and risk management.
    
    Parameters:
        fast_ma: Fast moving average period
        slow_ma: Slow moving average period
        vol_filter: ATR period for volatility filter
        stop_pct: Stop loss percentage
        trailing_pct: Trailing stop percentage
        max_position: Maximum position size (USD)
        atr_multiplier: ATR multiplier for stop distance
        regime_threshold: Threshold for regime detection
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # MA parameters
        self.fast_ma = config.get("fast_ma", 20)
        self.slow_ma = config.get("slow_ma", 60)
        self.vol_filter = config.get("vol_filter", 14)
        
        # Risk parameters
        self.stop_pct = config.get("stop_pct", 2.0)
        self.trailing_pct = config.get("trailing_pct", 1.5)
        self.max_position = config.get("max_position", 100.0)
        self.atr_multiplier = config.get("atr_multiplier", 2.0)
        self.regime_threshold = config.get("regime_threshold", 0.02)
        
        # Kelly parameters
        self.kelly_fraction = config.get("kelly_fraction", 0.25)
        self.min_win_prob = config.get("min_win_prob", 0.45)
        
        # State tracking
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        
        self.fast_ma_value: float = 0.0
        self.slow_ma_value: float = 0.0
        self.atr_value: float = 0.0
        
        self.position_size: float = 0.0
        self.entry_price: float = 0.0
        self.stop_loss: float = 0.0
        self.trailing_stop: float = 0.0
        self.highest_price: float = 0.0
        self.lowest_price: float = float('inf')
        
        self.regime: str = "neutral"  # bullish, bearish, neutral
        self.signal_strength: float = 0.0
        
        # Performance tracking
        self.trades: List[Dict] = []
        self.win_count: int = 0
        self.loss_count: int = 0
        self.total_return: float = 0.0
        
        self.symbol: str = ""
    
    def initialize(self, symbol: str, historical_data: Optional[pd.DataFrame] = None):
        """Initialize strategy with historical data"""
        self.symbol = symbol
        self.state["symbol"] = symbol
        
        if historical_data is not None and len(historical_data) > 0:
            # Load price history
            if "close" in historical_data.columns:
                self.price_history = historical_data["close"].tail(
                    max(self.slow_ma, self.vol_filter) * 2
                ).tolist()
            
            if "high" in historical_data.columns:
                self.high_history = historical_data["high"].tail(
                    self.vol_filter * 2
                ).tolist()
            
            if "low" in historical_data.columns:
                self.low_history = historical_data["low"].tail(
                    self.vol_filter * 2
                ).tolist()
            
            if "volume" in historical_data.columns:
                self.volume_history = historical_data["volume"].tail(
                    self.vol_filter * 2
                ).tolist()
            
            # Calculate initial indicators
            self._update_indicators()
            self._detect_regime()
            
            logger.info(f"Trend strategy initialized for {symbol}: "
                       f"fast_ma={self.fast_ma_value:.2f}, "
                       f"slow_ma={self.slow_ma_value:.2f}, "
                       f"regime={self.regime}")
    
    def _update_indicators(self):
        """Update technical indicators"""
        if len(self.price_history) >= self.fast_ma:
            self.fast_ma_value = self.calculate_ema(
                np.array(self.price_history), self.fast_ma
            )
        
        if len(self.price_history) >= self.slow_ma:
            self.slow_ma_value = self.calculate_ema(
                np.array(self.price_history), self.slow_ma
            )
        
        if (len(self.high_history) >= self.vol_filter and 
            len(self.low_history) >= self.vol_filter and
            len(self.price_history) >= self.vol_filter):
            
            self.atr_value = self.calculate_atr(
                np.array(self.high_history),
                np.array(self.low_history),
                np.array(self.price_history[-self.vol_filter:]),
                self.vol_filter
            )
    
    def _detect_regime(self):
        """Detect market regime (bullish/bearish/neutral)"""
        if self.fast_ma_value == 0 or self.slow_ma_value == 0:
            self.regime = "neutral"
            return
        
        ma_diff_pct = (self.fast_ma_value - self.slow_ma_value) / self.slow_ma_value
        
        # Volume confirmation
        volume_increasing = False
        if len(self.volume_history) >= 20:
            recent_vol = np.mean(self.volume_history[-5:])
            avg_vol = np.mean(self.volume_history[-20:])
            volume_increasing = recent_vol > avg_vol * 1.2
        
        # Regime detection with volume confirmation
        if ma_diff_pct > self.regime_threshold:
            self.regime = "bullish" if volume_increasing else "neutral"
            self.signal_strength = min(1.0, abs(ma_diff_pct) / 0.05)
        elif ma_diff_pct < -self.regime_threshold:
            self.regime = "bearish" if volume_increasing else "neutral"
            self.signal_strength = min(1.0, abs(ma_diff_pct) / 0.05)
        else:
            self.regime = "neutral"
            self.signal_strength = 0.0
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size using Kelly Criterion"""
        # Estimate win probability from historical performance
        win_prob = self.win_count / (self.win_count + self.loss_count) \
                  if (self.win_count + self.loss_count) > 10 else 0.5
        
        # Estimate win/loss ratio
        avg_win = self.metrics.get("avg_win", self.atr_value * 2) if self.win_count > 0 else self.atr_value * 2
        avg_loss = self.metrics.get("avg_loss", self.atr_value) if self.loss_count > 0 else self.atr_value
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
        
        # Kelly calculation
        if win_prob >= self.min_win_prob:
            kelly_pct = self.kelly_criterion(win_prob, win_loss_ratio, self.kelly_fraction)
        else:
            kelly_pct = 0.0
        
        # Adjust for regime strength
        kelly_pct *= self.signal_strength
        
        # Calculate position size in units
        position_value = min(
            self.max_position * kelly_pct,
            self.max_position
        )
        
        return position_value / price if price > 0 else 0.0
    
    def _calculate_stops(self, entry_price: float, side: SignalType) -> tuple[float, float]:
        """Calculate stop loss and initial trailing stop"""
        if self.atr_value > 0:
            stop_distance = self.atr_value * self.atr_multiplier
        else:
            stop_distance = entry_price * (self.stop_pct / 100)
        
        if side == SignalType.BUY:
            stop_loss = entry_price - stop_distance
            trailing_stop = entry_price - stop_distance * (self.trailing_pct / self.stop_pct)
        else:
            stop_loss = entry_price + stop_distance
            trailing_stop = entry_price + stop_distance * (self.trailing_pct / self.stop_pct)
        
        return stop_loss, trailing_stop
    
    def _check_stops(self, current_price: float) -> Optional[Signal]:
        """Check if stop loss or trailing stop is hit"""
        if self.position_size == 0:
            return None
        
        # Update trailing stop
        if self.position_size > 0:  # Long position
            if current_price > self.highest_price:
                self.highest_price = current_price
                new_trailing = current_price - self.atr_value * self.atr_multiplier * (self.trailing_pct / self.stop_pct)
                self.trailing_stop = max(self.trailing_stop, new_trailing)
            
            # Check stops
            if current_price <= self.stop_loss:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    strategy=self.name,
                    price=None,
                    quantity=self.position_size,
                    strength=1.0,
                    reason=f"Stop loss hit at {current_price:.2f}",
                    metadata={"stop_type": "stop_loss", "entry": self.entry_price},
                    params_hash=self._params_hash
                )
            elif current_price <= self.trailing_stop:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    strategy=self.name,
                    price=None,
                    quantity=self.position_size,
                    strength=1.0,
                    reason=f"Trailing stop hit at {current_price:.2f}",
                    metadata={"stop_type": "trailing_stop", "entry": self.entry_price},
                    params_hash=self._params_hash
                )
        
        else:  # Short position
            if current_price < self.lowest_price:
                self.lowest_price = current_price
                new_trailing = current_price + self.atr_value * self.atr_multiplier * (self.trailing_pct / self.stop_pct)
                self.trailing_stop = min(self.trailing_stop, new_trailing)
            
            # Check stops
            if current_price >= self.stop_loss:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    strategy=self.name,
                    price=None,
                    quantity=abs(self.position_size),
                    strength=1.0,
                    reason=f"Stop loss hit at {current_price:.2f}",
                    metadata={"stop_type": "stop_loss", "entry": self.entry_price},
                    params_hash=self._params_hash
                )
            elif current_price >= self.trailing_stop:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    strategy=self.name,
                    price=None,
                    quantity=abs(self.position_size),
                    strength=1.0,
                    reason=f"Trailing stop hit at {current_price:.2f}",
                    metadata={"stop_type": "trailing_stop", "entry": self.entry_price},
                    params_hash=self._params_hash
                )
        
        return None
    
    def on_tick(self, tick: Dict[str, Any]) -> List[Signal]:
        """Process tick data - mainly for stop checking"""
        signals = []
        current_price = tick.get("price", 0)
        
        if current_price > 0:
            # Check stops on every tick
            stop_signal = self._check_stops(current_price)
            if stop_signal:
                signals.append(stop_signal)
                # Reset position
                self.position_size = 0
                self.entry_price = 0
                self.update_metrics(stop_signal)
        
        return signals
    
    def on_bar(self, bar: Dict[str, Any]) -> List[Signal]:
        """Process bar data and generate trend signals"""
        signals = []
        
        # Update price history
        if "close" in bar:
            self.price_history.append(bar["close"])
            if len(self.price_history) > self.slow_ma * 2:
                self.price_history.pop(0)
        
        if "high" in bar:
            self.high_history.append(bar["high"])
            if len(self.high_history) > self.vol_filter * 2:
                self.high_history.pop(0)
        
        if "low" in bar:
            self.low_history.append(bar["low"])
            if len(self.low_history) > self.vol_filter * 2:
                self.low_history.pop(0)
        
        if "volume" in bar:
            self.volume_history.append(bar["volume"])
            if len(self.volume_history) > self.vol_filter * 2:
                self.volume_history.pop(0)
        
        # Need enough data
        if len(self.price_history) < self.slow_ma:
            return signals
        
        # Update indicators
        prev_fast_ma = self.fast_ma_value
        prev_slow_ma = self.slow_ma_value
        prev_regime = self.regime
        
        self._update_indicators()
        self._detect_regime()
        
        current_price = bar["close"]
        
        # Check for MA crossover signals
        if self.position_size == 0:
            # Look for entry signals
            if (prev_regime != "bullish" and self.regime == "bullish" and
                prev_fast_ma <= prev_slow_ma and self.fast_ma_value > self.slow_ma_value):
                
                # Bullish crossover - BUY signal
                quantity = self._calculate_position_size(current_price)
                if quantity > 0:
                    self.stop_loss, self.trailing_stop = self._calculate_stops(
                        current_price, SignalType.BUY
                    )
                    
                    signal = Signal(
                        symbol=self.symbol,
                        signal_type=SignalType.BUY,
                        strategy=self.name,
                        price=None,
                        quantity=quantity,
                        strength=self.signal_strength,
                        reason=f"Bullish MA crossover: fast({self.fast_ma_value:.2f}) > slow({self.slow_ma_value:.2f})",
                        metadata={
                            "regime": self.regime,
                            "fast_ma": self.fast_ma_value,
                            "slow_ma": self.slow_ma_value,
                            "atr": self.atr_value,
                            "stop_loss": self.stop_loss,
                            "trailing_stop": self.trailing_stop
                        },
                        params_hash=self._params_hash
                    )
                    signals.append(signal)
                    
                    # Update position
                    self.position_size = quantity
                    self.entry_price = current_price
                    self.highest_price = current_price
                    self.update_metrics(signal)
            
            elif (prev_regime != "bearish" and self.regime == "bearish" and
                  prev_fast_ma >= prev_slow_ma and self.fast_ma_value < self.slow_ma_value):
                
                # Bearish crossover - SELL signal (short)
                quantity = self._calculate_position_size(current_price)
                if quantity > 0:
                    self.stop_loss, self.trailing_stop = self._calculate_stops(
                        current_price, SignalType.SELL
                    )
                    
                    signal = Signal(
                        symbol=self.symbol,
                        signal_type=SignalType.SELL,
                        strategy=self.name,
                        price=None,
                        quantity=quantity,
                        strength=self.signal_strength,
                        reason=f"Bearish MA crossover: fast({self.fast_ma_value:.2f}) < slow({self.slow_ma_value:.2f})",
                        metadata={
                            "regime": self.regime,
                            "fast_ma": self.fast_ma_value,
                            "slow_ma": self.slow_ma_value,
                            "atr": self.atr_value,
                            "stop_loss": self.stop_loss,
                            "trailing_stop": self.trailing_stop
                        },
                        params_hash=self._params_hash
                    )
                    signals.append(signal)
                    
                    # Update position
                    self.position_size = -quantity
                    self.entry_price = current_price
                    self.lowest_price = current_price
                    self.update_metrics(signal)
        
        else:
            # Check for exit signals based on regime change
            if self.position_size > 0 and self.regime == "bearish":
                # Exit long position
                signal = Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    strategy=self.name,
                    price=None,
                    quantity=self.position_size,
                    strength=0.8,
                    reason=f"Regime changed to bearish, exiting long",
                    metadata={"regime": self.regime, "entry": self.entry_price},
                    params_hash=self._params_hash
                )
                signals.append(signal)
                
                # Track trade
                pnl = (current_price - self.entry_price) * self.position_size
                self.trades.append({
                    "entry": self.entry_price,
                    "exit": current_price,
                    "pnl": pnl,
                    "side": "long"
                })
                if pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # Reset position
                self.position_size = 0
                self.entry_price = 0
                self.update_metrics(signal, {"pnl": pnl})
            
            elif self.position_size < 0 and self.regime == "bullish":
                # Exit short position
                signal = Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    strategy=self.name,
                    price=None,
                    quantity=abs(self.position_size),
                    strength=0.8,
                    reason=f"Regime changed to bullish, exiting short",
                    metadata={"regime": self.regime, "entry": self.entry_price},
                    params_hash=self._params_hash
                )
                signals.append(signal)
                
                # Track trade
                pnl = (self.entry_price - current_price) * abs(self.position_size)
                self.trades.append({
                    "entry": self.entry_price,
                    "exit": current_price,
                    "pnl": pnl,
                    "side": "short"
                })
                if pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # Reset position
                self.position_size = 0
                self.entry_price = 0
                self.update_metrics(signal, {"pnl": pnl})
        
        # Check stops even on bar close
        if self.position_size != 0:
            stop_signal = self._check_stops(current_price)
            if stop_signal:
                signals.append(stop_signal)
                self.position_size = 0
                self.entry_price = 0
        
        return signals