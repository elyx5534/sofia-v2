"""
Scanning rules for cryptocurrency technical analysis signals
"""

from typing import Any, Dict

import pandas as pd
from loguru import logger

from ..metrics.indicators import add_all_indicators


class ScanRule:
    """Base class for scanning rules"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate rule and return signal information"""
        raise NotImplementedError

    def __repr__(self):
        return f"ScanRule(name='{self.name}', weight={self.weight})"


class RSIReboundRule(ScanRule):
    """RSI rebound from oversold condition"""

    def __init__(self, oversold_threshold: float = 30, recent_periods: int = 5):
        super().__init__("RSI Rebound", weight=2.0)
        self.oversold_threshold = oversold_threshold
        self.recent_periods = recent_periods

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            current_rsi = indicators.get("rsi", 50)

            if len(df) < self.recent_periods + 1:
                return {"signal": 0, "message": "Insufficient data"}

            df_with_indicators = add_all_indicators(df)
            recent_rsi = df_with_indicators["rsi"].iloc[-self.recent_periods :]

            # Check if RSI was oversold and is now recovering
            was_oversold = (recent_rsi <= self.oversold_threshold).any()
            is_recovering = current_rsi > self.oversold_threshold

            if was_oversold and is_recovering:
                signal_strength = min((current_rsi - self.oversold_threshold) / 10, 1.0)
                return {
                    "signal": signal_strength * self.weight,
                    "message": f"RSI rebounding from oversold ({current_rsi:.1f})",
                    "rsi": current_rsi,
                }

            return {"signal": 0, "message": "No RSI rebound signal"}

        except Exception as e:
            logger.error(f"Error in RSI rebound rule: {e}")
            return {"signal": 0, "message": "Error evaluating RSI"}


class SMACrossRule(ScanRule):
    """SMA crossover signal"""

    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        super().__init__("SMA Cross", weight=1.5)
        self.fast_period = fast_period
        self.slow_period = slow_period

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if len(df) < max(self.fast_period, self.slow_period) + 2:
                return {"signal": 0, "message": "Insufficient data for SMA cross"}

            df_with_indicators = add_all_indicators(df)

            sma_20 = df_with_indicators["sma_20"].iloc[-2:]
            sma_50 = df_with_indicators["sma_50"].iloc[-2:]

            # Check for bullish crossover
            if sma_20.iloc[-2] <= sma_50.iloc[-2] and sma_20.iloc[-1] > sma_50.iloc[-1]:
                cross_strength = abs(sma_20.iloc[-1] - sma_50.iloc[-1]) / sma_50.iloc[-1]
                signal_strength = min(cross_strength * 100, 1.0)

                return {
                    "signal": signal_strength * self.weight,
                    "message": "Bullish SMA cross (20 > 50)",
                    "sma_20": float(sma_20.iloc[-1]),
                    "sma_50": float(sma_50.iloc[-1]),
                }

            return {"signal": 0, "message": "No SMA crossover"}

        except Exception as e:
            logger.error(f"Error in SMA cross rule: {e}")
            return {"signal": 0, "message": "Error evaluating SMA cross"}


class BollingerBandsBounceRule(ScanRule):
    """Bollinger Bands bounce signal"""

    def __init__(self, touch_threshold: float = 0.02):
        super().__init__("BB Bounce", weight=1.0)
        self.touch_threshold = touch_threshold

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if len(df) < 25:  # Need at least 20 periods for BB + some history
                return {"signal": 0, "message": "Insufficient data for BB"}

            df_with_indicators = add_all_indicators(df)
            recent_data = df_with_indicators.iloc[-5:]  # Last 5 periods

            bb_lower = recent_data["bb_lower"]
            close_prices = recent_data["close"]

            current_close = indicators.get("close", 0)
            current_bb_lower = indicators.get("bb_lower", 0)
            current_bb_upper = indicators.get("bb_upper", 0)

            # Check if price touched lower band and bounced
            touched_lower = ((close_prices - bb_lower) / bb_lower <= self.touch_threshold).any()
            bouncing_up = current_close > current_bb_lower * (1 + self.touch_threshold)

            if touched_lower and bouncing_up:
                band_width = (current_bb_upper - current_bb_lower) / current_bb_lower
                signal_strength = min(band_width * 2, 1.0)

                return {
                    "signal": signal_strength * self.weight,
                    "message": "BB lower band bounce",
                    "bb_lower": current_bb_lower,
                    "current_price": current_close,
                }

            return {"signal": 0, "message": "No BB bounce signal"}

        except Exception as e:
            logger.error(f"Error in BB bounce rule: {e}")
            return {"signal": 0, "message": "Error evaluating BB bounce"}


class VolumeBreakoutRule(ScanRule):
    """Volume breakout signal"""

    def __init__(self, volume_multiplier: float = 2.0):
        super().__init__("Volume Breakout", weight=1.0)
        self.volume_multiplier = volume_multiplier

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if len(df) < 21:  # Need 20 periods for volume SMA
                return {"signal": 0, "message": "Insufficient data for volume analysis"}

            current_volume = indicators.get("volume", 0)

            df_with_indicators = add_all_indicators(df)
            volume_sma = df_with_indicators["volume_sma"].iloc[-1]

            if current_volume > volume_sma * self.volume_multiplier:
                volume_ratio = current_volume / volume_sma
                signal_strength = min((volume_ratio - self.volume_multiplier) / 2, 1.0)

                return {
                    "signal": signal_strength * self.weight,
                    "message": f"High volume ({volume_ratio:.1f}x avg)",
                    "volume": current_volume,
                    "volume_avg": volume_sma,
                }

            return {"signal": 0, "message": "No volume breakout"}

        except Exception as e:
            logger.error(f"Error in volume breakout rule: {e}")
            return {"signal": 0, "message": "Error evaluating volume"}


class MACDSignalRule(ScanRule):
    """MACD signal line crossover"""

    def __init__(self):
        super().__init__("MACD Signal", weight=1.5)

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if len(df) < 35:  # Need enough data for MACD
                return {"signal": 0, "message": "Insufficient data for MACD"}

            df_with_indicators = add_all_indicators(df)

            macd_recent = df_with_indicators["macd"].iloc[-2:]
            signal_recent = df_with_indicators["macd_signal"].iloc[-2:]

            # Check for bullish MACD crossover
            if (
                macd_recent.iloc[-2] <= signal_recent.iloc[-2]
                and macd_recent.iloc[-1] > signal_recent.iloc[-1]
            ):
                current_macd = indicators.get("macd", 0)
                current_signal = indicators.get("macd_signal", 0)

                cross_strength = abs(current_macd - current_signal) / max(abs(current_signal), 0.01)
                signal_strength = min(cross_strength, 1.0)

                return {
                    "signal": signal_strength * self.weight,
                    "message": "Bullish MACD crossover",
                    "macd": current_macd,
                    "macd_signal": current_signal,
                }

            return {"signal": 0, "message": "No MACD signal"}

        except Exception as e:
            logger.error(f"Error in MACD signal rule: {e}")
            return {"signal": 0, "message": "Error evaluating MACD"}


class PriceActionRule(ScanRule):
    """Price action and momentum signals"""

    def __init__(self):
        super().__init__("Price Action", weight=1.0)

    def evaluate(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        try:
            price_change_1h = indicators.get("price_change_1h", 0)
            price_change_24h = indicators.get("price_change_24h", 0)

            signal_strength = 0
            messages = []

            # Strong 1h momentum
            if abs(price_change_1h) > 5:
                if price_change_1h > 0:
                    signal_strength += 0.5
                    messages.append(f"+{price_change_1h:.1f}% 1h")

            # Reasonable 24h performance
            if 0 < price_change_24h < 20:
                signal_strength += 0.3
                messages.append(f"+{price_change_24h:.1f}% 24h")

            if signal_strength > 0:
                return {
                    "signal": min(signal_strength, 1.0) * self.weight,
                    "message": f'Price momentum: {", ".join(messages)}',
                    "price_change_1h": price_change_1h,
                    "price_change_24h": price_change_24h,
                }

            return {"signal": 0, "message": "No significant price action"}

        except Exception as e:
            logger.error(f"Error in price action rule: {e}")
            return {"signal": 0, "message": "Error evaluating price action"}


# Default rule set
DEFAULT_RULES = [
    RSIReboundRule(),
    SMACrossRule(),
    BollingerBandsBounceRule(),
    VolumeBreakoutRule(),
    MACDSignalRule(),
    PriceActionRule(),
]
