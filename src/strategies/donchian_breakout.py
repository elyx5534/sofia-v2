"""
Donchian Channel Breakout Strategy
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from .base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    """
    Donchian Channel breakout strategy with trend filter

    Parameters:
    - donchian_period: lookback period for channel (20-120)
    - breakout_strength: multiplier for breakout strength calculation
    - trend_filter: whether to apply trend filter
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "donchian_period": 50,
            "breakout_strength": 1.0,
            "trend_filter": True,
            "atr_stop_k": 2.0,
            "take_profit_k": 3.0,
            "max_hold_bars": 48,
        }

        if params:
            default_params.update(params)

        super().__init__(default_params)
        self.donchian_period = self.params["donchian_period"]
        self.breakout_strength = self.params["breakout_strength"]
        self.trend_filter = self.params["trend_filter"]

    def _calculate_strategy_indicators(self, symbol: str):
        """Calculate Donchian Channel indicators"""
        if symbol not in self.data:
            return

        df = self.indicators[symbol].copy()
        period = self.donchian_period

        # Donchian Channels
        df["donchian_high"] = df["high"].rolling(window=period).max()
        df["donchian_low"] = df["low"].rolling(window=period).min()
        df["donchian_mid"] = (df["donchian_high"] + df["donchian_low"]) / 2

        # Channel width for breakout strength
        df["channel_width"] = (df["donchian_high"] - df["donchian_low"]) / df["close"]
        df["channel_width_ma"] = df["channel_width"].rolling(window=20).mean()
        df["channel_width_ratio"] = df["channel_width"] / df["channel_width_ma"]

        # Breakout signals
        df["upper_breakout"] = (df["close"] > df["donchian_high"].shift(1)) & (
            df["close"].shift(1) <= df["donchian_high"].shift(1)
        )
        df["lower_breakout"] = (df["close"] < df["donchian_low"].shift(1)) & (
            df["close"].shift(1) >= df["donchian_low"].shift(1)
        )

        # Position relative to channel
        df["channel_position"] = (df["close"] - df["donchian_low"]) / (
            df["donchian_high"] - df["donchian_low"]
        )

        self.indicators[symbol] = df

    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Generate Donchian breakout signal"""
        if symbol not in self.indicators:
            return None

        df = self.indicators[symbol]
        if len(df) < self.donchian_period + 20:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = {
            "strategy": "donchian_breakout",
            "symbol": symbol,
            "direction": 0,
            "strength": 0.0,
            "confidence": 0.0,
            "metadata": {},
        }

        # Check for breakouts
        if latest["upper_breakout"]:
            # Upward breakout - long signal
            signal["direction"] = 1

            # Strength based on channel width and volume
            base_strength = self.breakout_strength

            # Wider channels = stronger breakouts
            width_multiplier = min(latest["channel_width_ratio"], 2.0)

            # Volume confirmation
            volume_multiplier = (
                min(latest["volume_ratio"], 2.0) if "volume_ratio" in latest else 1.0
            )

            signal["strength"] = base_strength * width_multiplier * volume_multiplier * 0.5
            signal["strength"] = min(signal["strength"], 1.0)

            # Confidence based on trend alignment and breakout quality
            confidence = 0.6
            if self.trend_filter and latest["trend_regime"] > 0:
                confidence += 0.2  # Trend alignment bonus

            # Breakout quality - how far above channel
            breakout_distance = (float(current_price) - latest["donchian_high"]) / latest[
                "donchian_high"
            ]
            if breakout_distance > 0.01:  # > 1% breakout
                confidence += 0.1

            signal["confidence"] = min(confidence, 1.0)

            signal["metadata"] = {
                "breakout_type": "upper",
                "channel_width_ratio": latest["channel_width_ratio"],
                "donchian_high": latest["donchian_high"],
                "donchian_low": latest["donchian_low"],
            }

        elif latest["lower_breakout"]:
            # Downward breakout - short signal
            signal["direction"] = -1

            # Similar strength calculation for shorts
            base_strength = self.breakout_strength
            width_multiplier = min(latest["channel_width_ratio"], 2.0)
            volume_multiplier = (
                min(latest["volume_ratio"], 2.0) if "volume_ratio" in latest else 1.0
            )

            signal["strength"] = base_strength * width_multiplier * volume_multiplier * 0.5
            signal["strength"] = min(signal["strength"], 1.0)

            confidence = 0.6
            if self.trend_filter and latest["trend_regime"] < 0:
                confidence += 0.2  # Trend alignment bonus

            # Breakout quality - how far below channel
            breakout_distance = (latest["donchian_low"] - float(current_price)) / latest[
                "donchian_low"
            ]
            if breakout_distance > 0.01:  # > 1% breakout
                confidence += 0.1

            signal["confidence"] = min(confidence, 1.0)

            signal["metadata"] = {
                "breakout_type": "lower",
                "channel_width_ratio": latest["channel_width_ratio"],
                "donchian_high": latest["donchian_high"],
                "donchian_low": latest["donchian_low"],
            }

        # Apply filters
        if signal["direction"] != 0:
            signal = self._apply_filters(symbol, signal)

        return signal if signal["strength"] > 0.1 else None
