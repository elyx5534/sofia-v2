"""
Arbitrage Opportunity Scorer
Score opportunities 0-1 and determine position size
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ArbitrageScorer:
    """Score arbitrage opportunities and size positions"""

    def __init__(self, max_position_tl: float = 10000, min_lot_tl: float = 100):
        self.max_position_tl = max_position_tl
        self.min_lot_tl = min_lot_tl
        self.weights = {
            "spread": 2.0,
            "depth": 0.8,
            "volatility": -0.5,
            "latency": -1.0,
            "fail_rate": -1.5,
        }
        self.norm_params = {
            "spread_bps": {"min": 0, "max": 100},
            "depth_ratio": {"min": 0.5, "max": 2.0},
            "volatility_pct": {"min": 0, "max": 5},
            "latency_ms": {"min": 10, "max": 500},
            "fail_rate": {"min": 0, "max": 0.5},
        }
        self.recent_trades = []
        self.trade_window = 20

    def normalize_feature(self, value: float, feature: str) -> float:
        """Normalize feature to 0-1 range"""
        params = self.norm_params.get(feature, {"min": 0, "max": 1})
        normalized = (value - params["min"]) / (params["max"] - params["min"])
        return np.clip(normalized, 0, 1)

    def sigmoid(self, x: float) -> float:
        """Sigmoid activation for final score"""
        return 1 / (1 + np.exp(-x))

    def calculate_fail_rate(self) -> float:
        """Calculate recent failure rate"""
        if not self.recent_trades:
            return 0
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent = [t for t in self.recent_trades if t["timestamp"] > one_hour_ago]
        if not recent:
            return 0
        failures = sum(1 for t in recent if not t["success"])
        return failures / len(recent)

    def score_opportunity(
        self,
        net_spread_bps: float,
        depth_balance: float,
        volatility_5m: float,
        latency_ms: float,
        **kwargs,
    ) -> Tuple[float, Dict]:
        """
        Score an arbitrage opportunity

        Returns:
            (score, details) where score is 0-1
        """
        features = {
            "spread": self.normalize_feature(net_spread_bps, "spread_bps"),
            "depth": 1 - abs(1 - self.normalize_feature(depth_balance, "depth_ratio")),
            "volatility": self.normalize_feature(volatility_5m, "volatility_pct"),
            "latency": self.normalize_feature(latency_ms, "latency_ms"),
            "fail_rate": self.calculate_fail_rate(),
        }
        weighted_sum = 0
        for feature, value in features.items():
            weighted_sum += self.weights[feature] * value
        score = self.sigmoid(weighted_sum)
        details = {
            "raw_features": {
                "net_spread_bps": net_spread_bps,
                "depth_balance": depth_balance,
                "volatility_5m": volatility_5m,
                "latency_ms": latency_ms,
                "fail_rate_1h": features["fail_rate"],
            },
            "normalized_features": features,
            "weighted_sum": weighted_sum,
            "final_score": score,
        }
        return (score, details)

    def calculate_position_size(
        self, score: float, available_capital_tl: float = None
    ) -> Tuple[float, str]:
        """
        Calculate position size based on score

        Returns:
            (size_tl, reason)
        """
        if available_capital_tl is None:
            available_capital_tl = self.max_position_tl
        if score < 0.3:
            return (0, "Score too low (<0.3)")
        if score < 0.5:
            size_tl = self.min_lot_tl
            reason = f"Low confidence (score={score:.2f})"
        elif score < 0.7:
            size_pct = 0.2 + (score - 0.5) * 2
            size_tl = min(available_capital_tl * size_pct, self.max_position_tl * 0.5)
            reason = f"Medium confidence (score={score:.2f})"
        else:
            size_pct = 0.6 + (score - 0.7) * 1.33
            size_tl = min(available_capital_tl * size_pct, self.max_position_tl)
            reason = f"High confidence (score={score:.2f})"
        size_tl = max(self.min_lot_tl, min(size_tl, self.max_position_tl))
        size_tl = round(size_tl / 10) * 10
        return (size_tl, reason)

    def record_trade_result(self, success: bool):
        """Record trade result for fail rate calculation"""
        self.recent_trades.append({"timestamp": datetime.now(), "success": success})
        if len(self.recent_trades) > self.trade_window:
            self.recent_trades = self.recent_trades[-self.trade_window :]

    def get_size_for_opportunity(
        self,
        net_spread_bps: float,
        depth_balance: float,
        volatility_5m: float,
        latency_ms: float,
        available_capital_tl: float = None,
        **kwargs,
    ) -> Tuple[float, float, Dict]:
        """
        Get position size for an opportunity

        Returns:
            (size_tl, score, details)
        """
        score, score_details = self.score_opportunity(
            net_spread_bps=net_spread_bps,
            depth_balance=depth_balance,
            volatility_5m=volatility_5m,
            latency_ms=latency_ms,
            **kwargs,
        )
        size_tl, size_reason = self.calculate_position_size(score, available_capital_tl)
        details = {**score_details, "position_size_tl": size_tl, "size_reason": size_reason}
        logger.info(
            f"Opportunity scored: {score:.3f} | Size: {size_tl} TL | Spread: {net_spread_bps:.1f}bps | Reason: {size_reason}"
        )
        return (size_tl, score, details)


def test_scorer():
    """Test the scorer with various scenarios"""
    scorer = ArbitrageScorer(max_position_tl=10000, min_lot_tl=100)
    scenarios = [
        {
            "name": "High opportunity",
            "net_spread_bps": 50,
            "depth_balance": 1.0,
            "volatility_5m": 1.0,
            "latency_ms": 50,
        },
        {
            "name": "Medium opportunity",
            "net_spread_bps": 25,
            "depth_balance": 1.2,
            "volatility_5m": 2.0,
            "latency_ms": 100,
        },
        {
            "name": "Low opportunity",
            "net_spread_bps": 10,
            "depth_balance": 0.5,
            "volatility_5m": 4.0,
            "latency_ms": 300,
        },
        {
            "name": "Bad opportunity",
            "net_spread_bps": 5,
            "depth_balance": 0.3,
            "volatility_5m": 5.0,
            "latency_ms": 500,
        },
    ]
    print("=" * 60)
    print("ARBITRAGE SCORER TEST")
    print("=" * 60)
    for scenario in scenarios:
        name = scenario.pop("name")
        size_tl, score, details = scorer.get_size_for_opportunity(**scenario)
        print(f"\n{name}:")
        print(f"  Score: {score:.3f}")
        print(f"  Size: {size_tl} TL")
        print(f"  Reason: {details['size_reason']}")
    print("=" * 60)


if __name__ == "__main__":
    test_scorer()
