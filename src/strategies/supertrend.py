"""
SuperTrend Strategy
"""

from decimal import Decimal
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .base import BaseStrategy


class SuperTrendStrategy(BaseStrategy):
    """
    SuperTrend strategy with dynamic factor adjustment

    Parameters:
    - atr_length: ATR calculation period (10-20)
    - factor: SuperTrend factor (1.5-4.0)
    - trend_filter: whether to apply additional trend filter
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "atr_length": 14,
            "factor": 2.5,
            "trend_filter": True,
            "atr_stop_k": 1.5,
            "take_profit_k": 2.5,
            "max_hold_bars": 36,
        }

        if params:
            default_params.update(params)

        super().__init__(default_params)
        self.atr_length = self.params["atr_length"]
        self.factor = self.params["factor"]

    def _calculate_strategy_indicators(self, symbol: str):
        """Calculate SuperTrend indicators"""
        if symbol not in self.data:
            return

        df = self.indicators[symbol].copy()

        # Calculate ATR for SuperTrend
        atr_length = self.atr_length
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift(1))
        low_close = np.abs(df["low"] - df["close"].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["st_atr"] = true_range.rolling(window=atr_length).mean()

        # Calculate HL2 (median price)
        df["hl2"] = (df["high"] + df["low"]) / 2

        # Calculate basic upper and lower bands
        df["upper_band"] = df["hl2"] + (self.factor * df["st_atr"])
        df["lower_band"] = df["hl2"] - (self.factor * df["st_atr"])

        # Initialize SuperTrend arrays
        df["final_upper_band"] = df["upper_band"].copy()
        df["final_lower_band"] = df["lower_band"].copy()
        df["supertrend"] = 0.0
        df["st_direction"] = 1  # 1 for up, -1 for down

        # Calculate final bands and SuperTrend
        for i in range(1, len(df)):
            # Final upper band
            if (
                df["upper_band"].iloc[i] < df["final_upper_band"].iloc[i - 1]
                or df["close"].iloc[i - 1] > df["final_upper_band"].iloc[i - 1]
            ):
                df.iloc[i, df.columns.get_loc("final_upper_band")] = df["upper_band"].iloc[i]
            else:
                df.iloc[i, df.columns.get_loc("final_upper_band")] = df["final_upper_band"].iloc[
                    i - 1
                ]

            # Final lower band
            if (
                df["lower_band"].iloc[i] > df["final_lower_band"].iloc[i - 1]
                or df["close"].iloc[i - 1] < df["final_lower_band"].iloc[i - 1]
            ):
                df.iloc[i, df.columns.get_loc("final_lower_band")] = df["lower_band"].iloc[i]
            else:
                df.iloc[i, df.columns.get_loc("final_lower_band")] = df["final_lower_band"].iloc[
                    i - 1
                ]

            # SuperTrend direction
            if df["close"].iloc[i] <= df["final_lower_band"].iloc[i]:
                df.iloc[i, df.columns.get_loc("st_direction")] = -1
            elif df["close"].iloc[i] >= df["final_upper_band"].iloc[i]:
                df.iloc[i, df.columns.get_loc("st_direction")] = 1
            else:
                df.iloc[i, df.columns.get_loc("st_direction")] = df["st_direction"].iloc[i - 1]

            # SuperTrend value
            if df["st_direction"].iloc[i] == 1:
                df.iloc[i, df.columns.get_loc("supertrend")] = df["final_lower_band"].iloc[i]
            else:
                df.iloc[i, df.columns.get_loc("supertrend")] = df["final_upper_band"].iloc[i]

        # Detect direction changes
        df["st_direction_change"] = df["st_direction"].diff().fillna(0)

        # Calculate trend strength
        df["trend_strength"] = np.abs(df["close"] - df["supertrend"]) / df["st_atr"]
        df["trend_strength_ma"] = df["trend_strength"].rolling(window=10).mean()

        self.indicators[symbol] = df

    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Generate SuperTrend signal"""
        if symbol not in self.indicators:
            return None

        df = self.indicators[symbol]
        if len(df) < self.atr_length + 20:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = {
            "strategy": "supertrend",
            "symbol": symbol,
            "direction": 0,
            "strength": 0.0,
            "confidence": 0.0,
            "metadata": {},
        }

        # Check for direction changes
        if latest["st_direction_change"] != 0:
            signal["direction"] = int(latest["st_direction"])

            # Base strength from trend change
            base_strength = 0.7

            # Adjust strength based on trend strength
            if latest["trend_strength"] > latest["trend_strength_ma"] * 1.2:
                base_strength *= 1.2  # Strong trend
            elif latest["trend_strength"] < latest["trend_strength_ma"] * 0.8:
                base_strength *= 0.8  # Weak trend

            # Volume confirmation
            volume_multiplier = 1.0
            if "volume_ratio" in latest and not pd.isna(latest["volume_ratio"]):
                volume_multiplier = min(latest["volume_ratio"], 1.5)

            signal["strength"] = min(base_strength * volume_multiplier, 1.0)

            # Confidence based on various factors
            confidence = 0.6

            # Trend alignment with longer EMA
            if hasattr(latest, "trend_regime"):
                if (signal["direction"] == 1 and latest["trend_regime"] >= 0) or (
                    signal["direction"] == -1 and latest["trend_regime"] <= 0
                ):
                    confidence += 0.15

            # Distance from SuperTrend line
            st_distance = abs(float(current_price) - latest["supertrend"]) / latest["supertrend"]
            if st_distance < 0.02:  # Close to SuperTrend line
                confidence += 0.1

            # ATR-based volatility check
            if latest["atr_pct"] > self.min_atr_pct:
                confidence += 0.15

            signal["confidence"] = min(confidence, 1.0)

            signal["metadata"] = {
                "supertrend_value": latest["supertrend"],
                "st_direction": latest["st_direction"],
                "trend_strength": latest["trend_strength"],
                "atr_factor": self.factor,
            }

        # Apply filters
        if signal["direction"] != 0:
            signal = self._apply_filters(symbol, signal)

        return signal if signal["strength"] > 0.2 else None

    def get_exit_signals(self, symbol: str, position: Dict[str, Any]) -> Dict[str, Any]:
        """SuperTrend-specific exit signals"""
        # First check base exit conditions
        base_exit = super().get_exit_signals(symbol, position)
        if base_exit["should_exit"]:
            return base_exit

        # SuperTrend exit logic
        if symbol not in self.indicators:
            return {"should_exit": False}

        df = self.indicators[symbol]
        if len(df) == 0:
            return {"should_exit": False}

        latest = df.iloc[-1]
        position_side = position["side"]

        # Exit on SuperTrend direction change
        if position_side == "long" and latest["st_direction"] == -1:
            return {"should_exit": True, "reason": "supertrend_reversal", "urgency": "high"}
        elif position_side == "short" and latest["st_direction"] == 1:
            return {"should_exit": True, "reason": "supertrend_reversal", "urgency": "high"}

        # Exit if price crosses SuperTrend line against position
        current_price = Decimal(str(latest["close"]))
        supertrend_price = Decimal(str(latest["supertrend"]))

        if position_side == "long" and current_price < supertrend_price:
            return {"should_exit": True, "reason": "supertrend_cross", "urgency": "high"}
        elif position_side == "short" and current_price > supertrend_price:
            return {"should_exit": True, "reason": "supertrend_cross", "urgency": "high"}

        return {"should_exit": False}
