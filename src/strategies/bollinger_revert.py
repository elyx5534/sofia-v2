"""
Bollinger Bands Mean Reversion Strategy
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from .base import BaseStrategy


class BollingerRevertStrategy(BaseStrategy):
    """
    Bollinger Bands mean reversion strategy

    Parameters:
    - bb_period: Bollinger Bands period (10-40)
    - bb_std: Standard deviation multiplier (1.5-3.0)
    - revert_threshold: How far from mean to trigger (0.8-1.0 = 80-100% of band)
    - mean_revert_filter: Additional mean reversion filters
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "revert_threshold": 0.9,
            "mean_revert_filter": True,
            "atr_stop_k": 1.5,
            "take_profit_k": 2.0,
            "max_hold_bars": 24,
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)
        self.bb_period = self.params["bb_period"]
        self.bb_std = self.params["bb_std"]
        self.revert_threshold = self.params["revert_threshold"]

    def _calculate_strategy_indicators(self, symbol: str):
        """Calculate Bollinger Bands indicators"""
        if symbol not in self.data:
            return
        df = self.indicators[symbol].copy()
        period = self.bb_period
        std_mult = self.bb_std
        df["bb_ma"] = df["close"].rolling(window=period).mean()
        df["bb_std"] = df["close"].rolling(window=period).std()
        df["bb_upper"] = df["bb_ma"] + df["bb_std"] * std_mult
        df["bb_lower"] = df["bb_ma"] - df["bb_std"] * std_mult
        df["bb_position"] = (df["close"] - df["bb_ma"]) / (df["bb_std"] * std_mult)
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_ma"]
        df["bb_width_ma"] = df["bb_width"].rolling(window=10).mean()
        df["bb_width_ratio"] = df["bb_width"] / df["bb_width_ma"]
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - 100 / (1 + rs)
        df["roc_5"] = (df["close"] - df["close"].shift(5)) / df["close"].shift(5)
        df["bb_squeeze"] = df["bb_width"] < df["bb_width_ma"] * 0.8
        self.indicators[symbol] = df

    def get_signal(self, symbol: str, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Generate Bollinger mean reversion signal"""
        if symbol not in self.indicators:
            return None
        df = self.indicators[symbol]
        if len(df) < self.bb_period + 20:
            return None
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        signal = {
            "strategy": "bollinger_revert",
            "symbol": symbol,
            "direction": 0,
            "strength": 0.0,
            "confidence": 0.0,
            "metadata": {},
        }
        bb_pos = latest["bb_position"]
        rsi = latest["rsi"]
        if bb_pos < -self.revert_threshold:
            signal["direction"] = 1
            base_strength = min(abs(bb_pos), 1.0) * 0.8
            if rsi < 30:
                base_strength *= 1.3
            elif rsi < 40:
                base_strength *= 1.1
            if latest["bb_width_ratio"] > 1.2:
                base_strength *= 1.2
            elif latest["bb_width_ratio"] < 0.8:
                base_strength *= 0.7
            signal["strength"] = min(base_strength, 1.0)
            confidence = 0.5 + abs(bb_pos) * 0.3
            if rsi < 30:
                confidence += 0.15
            if latest["roc_5"] < -0.03:
                confidence += 0.1
            if not latest["bb_squeeze"]:
                confidence += 0.1
            signal["confidence"] = min(confidence, 1.0)
            signal["metadata"] = {
                "bb_position": bb_pos,
                "rsi": rsi,
                "bb_upper": latest["bb_upper"],
                "bb_lower": latest["bb_lower"],
                "revert_type": "oversold",
            }
        elif bb_pos > self.revert_threshold:
            signal["direction"] = -1
            base_strength = min(abs(bb_pos), 1.0) * 0.8
            if rsi > 70:
                base_strength *= 1.3
            elif rsi > 60:
                base_strength *= 1.1
            if latest["bb_width_ratio"] > 1.2:
                base_strength *= 1.2
            elif latest["bb_width_ratio"] < 0.8:
                base_strength *= 0.7
            signal["strength"] = min(base_strength, 1.0)
            confidence = 0.5 + abs(bb_pos) * 0.3
            if rsi > 70:
                confidence += 0.15
            if latest["roc_5"] > 0.03:
                confidence += 0.1
            if not latest["bb_squeeze"]:
                confidence += 0.1
            signal["confidence"] = min(confidence, 1.0)
            signal["metadata"] = {
                "bb_position": bb_pos,
                "rsi": rsi,
                "bb_upper": latest["bb_upper"],
                "bb_lower": latest["bb_lower"],
                "revert_type": "overbought",
            }
        if signal["direction"] != 0:
            if hasattr(latest, "trend_regime"):
                if abs(latest["trend_regime"]) > 0:
                    signal["strength"] *= 0.7
            signal = self._apply_filters(symbol, signal)
        return signal if signal["strength"] > 0.15 else None

    def get_exit_signals(self, symbol: str, position: Dict[str, Any]) -> Dict[str, Any]:
        """Bollinger-specific exit signals"""
        base_exit = super().get_exit_signals(symbol, position)
        if base_exit["should_exit"]:
            return base_exit
        if symbol not in self.indicators:
            return {"should_exit": False}
        df = self.indicators[symbol]
        if len(df) == 0:
            return {"should_exit": False}
        latest = df.iloc[-1]
        position_side = position["side"]
        bb_pos = latest["bb_position"]
        if position_side == "long":
            if bb_pos > -0.2:
                return {"should_exit": True, "reason": "mean_revert_complete", "urgency": "medium"}
        elif bb_pos < 0.2:
            return {"should_exit": True, "reason": "mean_revert_complete", "urgency": "medium"}
        rsi = latest["rsi"]
        if position_side == "long" and rsi > 60:
            return {"should_exit": True, "reason": "rsi_reversal", "urgency": "low"}
        elif position_side == "short" and rsi < 40:
            return {"should_exit": True, "reason": "rsi_reversal", "urgency": "low"}
        return {"should_exit": False}
