"""
Base Strategy Class with Common Risk Management
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Base strategy with common risk management and filters"""

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}
        self.name = self.__class__.__name__

        # Common parameters
        self.atr_stop_k = Decimal(str(self.params.get("atr_stop_k", 2.0)))
        self.take_profit_k = Decimal(str(self.params.get("take_profit_k", 3.0)))
        self.max_hold_bars = self.params.get("max_hold_bars", 48)
        self.min_atr_pct = self.params.get("min_atr_pct", 0.005)  # 0.5% min volatility
        self.trend_slope_threshold = self.params.get("trend_slope_threshold", 0.001)
        self.max_spread_bps = self.params.get("max_spread_bps", 50)
        self.min_volume = self.params.get("min_volume", 1000)

        # Data storage
        self.data: Dict[str, pd.DataFrame] = {}
        self.indicators: Dict[str, pd.DataFrame] = {}
        self.positions: Dict[str, Dict] = {}

    def update_data(self, symbol: str, ohlcv: pd.DataFrame):
        """Update data and calculate indicators"""
        self.data[symbol] = ohlcv.copy()
        self._calculate_common_indicators(symbol)
        self._calculate_strategy_indicators(symbol)

    def _calculate_common_indicators(self, symbol: str):
        """Calculate common indicators used by all strategies"""
        if symbol not in self.data:
            return

        df = self.data[symbol].copy()

        # ATR for volatility and stops
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift(1))
        low_close = np.abs(df["low"] - df["close"].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["atr"] = true_range.rolling(window=14).mean()
        df["atr_pct"] = df["atr"] / df["close"]

        # Trend filter - EMA slope
        df["ema_21"] = df["close"].ewm(span=21).mean()
        df["ema_slope"] = (df["ema_21"] - df["ema_21"].shift(5)) / df["ema_21"].shift(5)
        df["trend_regime"] = np.where(
            df["ema_slope"] > self.trend_slope_threshold,
            1,  # Uptrend
            np.where(df["ema_slope"] < -self.trend_slope_threshold, -1, 0),  # Downtrend or flat
        )

        # Volume MA for liquidity filter
        df["volume_ma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]

        self.indicators[symbol] = df

    @abstractmethod
    def _calculate_strategy_indicators(self, symbol: str):
        """Calculate strategy-specific indicators"""
        pass

    @abstractmethod
    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Get trading signal"""
        pass

    def _apply_filters(self, symbol: str, raw_signal: Dict[str, Any]) -> Dict[str, Any]:
        """Apply common filters to raw signal"""
        if symbol not in self.indicators:
            return {"direction": 0, "strength": 0, "confidence": 0, "filtered": True}

        df = self.indicators[symbol]
        if len(df) < 21:
            return {"direction": 0, "strength": 0, "confidence": 0, "filtered": True}

        latest = df.iloc[-1]

        # Volatility filter - don't trade if too low volatility
        if latest["atr_pct"] < self.min_atr_pct:
            return {
                "direction": 0,
                "strength": 0,
                "confidence": 0,
                "filtered": True,
                "reason": "low_volatility",
            }

        # Trend filter - apply based on regime
        trend_regime = latest["trend_regime"]
        signal_direction = raw_signal["direction"]

        # In strong uptrend, favor long signals
        if trend_regime == 1 and signal_direction < 0:
            raw_signal["strength"] *= 0.5  # Reduce short strength
        # In strong downtrend, favor short signals
        elif trend_regime == -1 and signal_direction > 0:
            raw_signal["strength"] *= 0.5  # Reduce long strength

        # Volume filter - reduce strength if low volume
        if latest["volume_ratio"] < 0.8:
            raw_signal["strength"] *= 0.8

        # Session filter (basic - can be enhanced)
        current_hour = datetime.now().hour
        # Reduce activity during low liquidity hours (2-6 AM UTC for crypto)
        if 2 <= current_hour <= 6:
            raw_signal["strength"] *= 0.7

        return raw_signal

    def calculate_position_size(
        self, symbol: str, signal_strength: float, balance: Decimal, k_factor: Decimal
    ) -> Decimal:
        """Calculate position size with ATR-based sizing"""
        if symbol not in self.indicators:
            return Decimal("0")

        df = self.indicators[symbol]
        if len(df) == 0:
            return Decimal("0")

        latest = df.iloc[-1]
        current_price = Decimal(str(latest["close"]))
        atr = Decimal(str(latest["atr"]))

        # Kelly-inspired sizing with ATR risk
        risk_per_trade = balance * k_factor * Decimal(str(abs(signal_strength)))

        # Use ATR for stop distance
        stop_distance = atr * self.atr_stop_k

        if stop_distance > 0:
            position_size = risk_per_trade / stop_distance
        else:
            position_size = Decimal("0")

        return position_size

    def get_exit_signals(self, symbol: str, position: Dict[str, Any]) -> Dict[str, Any]:
        """Get exit signals for position"""
        if symbol not in self.indicators:
            return {"should_exit": False}

        df = self.indicators[symbol]
        if len(df) == 0:
            return {"should_exit": False}

        latest = df.iloc[-1]
        current_price = Decimal(str(latest["close"]))
        entry_price = Decimal(str(position["entry_price"]))
        entry_time = position["entry_time"]
        side = position["side"]

        # ATR-based stop loss
        atr = Decimal(str(latest["atr"]))

        if side == "long":
            stop_price = entry_price - (atr * self.atr_stop_k)
            take_profit_price = entry_price + (atr * self.take_profit_k)

            if current_price <= stop_price:
                return {"should_exit": True, "reason": "stop_loss", "urgency": "high"}
            elif current_price >= take_profit_price:
                return {"should_exit": True, "reason": "take_profit", "urgency": "medium"}
        else:  # short
            stop_price = entry_price + (atr * self.atr_stop_k)
            take_profit_price = entry_price - (atr * self.take_profit_k)

            if current_price >= stop_price:
                return {"should_exit": True, "reason": "stop_loss", "urgency": "high"}
            elif current_price <= take_profit_price:
                return {"should_exit": True, "reason": "take_profit", "urgency": "medium"}

        # Max holding period
        bars_held = len(df) - position.get("entry_bar", len(df))
        if bars_held >= self.max_hold_bars:
            return {"should_exit": True, "reason": "max_hold", "urgency": "medium"}

        return {"should_exit": False}

    def get_trailing_stop(self, symbol: str, position: Dict[str, Any]) -> Optional[Decimal]:
        """Calculate trailing stop price"""
        if symbol not in self.indicators or not self.params.get("use_trailing_stop", False):
            return None

        df = self.indicators[symbol]
        if len(df) == 0:
            return None

        latest = df.iloc[-1]
        current_price = Decimal(str(latest["close"]))
        atr = Decimal(str(latest["atr"]))
        side = position["side"]

        if side == "long":
            trailing_stop = current_price - (atr * self.atr_stop_k)
        else:  # short
            trailing_stop = current_price + (atr * self.atr_stop_k)

        return trailing_stop
