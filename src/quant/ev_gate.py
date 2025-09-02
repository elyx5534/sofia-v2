"""
Expected Value Gate v2
Calculates EV = p(fill) * edge * size - cost - slippage_budget
Only allows positive EV trades
"""

import logging
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class EVGate:
    """Expected Value gate for trade decisions"""

    def __init__(self, config: Dict = None):
        if config is None:
            config = self.load_config()

        self.min_ev_threshold = Decimal(str(config.get("min_ev_tl", 1)))  # Minimum 1 TL EV

        # Penalty parameters
        self.latency_penalty_per_100ms = Decimal(str(config.get("latency_penalty_bps", 2)))
        self.slippage_multiplier = Decimal(str(config.get("slippage_multiplier", 1.5)))

        # Historical data for p(fill) model
        self.fill_history = []
        self.slippage_history = []

    def load_config(self) -> Dict:
        """Load EV configuration"""
        config_file = Path("config/arb_ev.yaml")

        if config_file.exists():
            import yaml

            with open(config_file) as f:
                return yaml.safe_load(f)

        # Default config
        return {
            "min_ev_tl": 1,
            "latency_penalty_bps": 2,
            "slippage_multiplier": 1.5,
            "min_pfill": 0.3,
            "max_position_tl": 10000,
        }

    def calculate_fill_probability(
        self, maker_fill_rate: float, depth_ratio: float, spread_bps: float, latency_ms: float
    ) -> float:
        """
        Calculate probability of fill using logistic model

        Args:
            maker_fill_rate: Historical maker fill rate (0-1)
            depth_ratio: Ask depth / Bid depth
            spread_bps: Current spread in basis points
            latency_ms: Round-trip latency
        """

        # Feature engineering
        features = {
            "fill_rate": maker_fill_rate,
            "depth_balance": 1 / (1 + abs(1 - depth_ratio)),  # Best at 1.0
            "spread_tightness": 1 / (1 + spread_bps / 10),  # Tighter is better
            "speed_factor": 1 / (1 + latency_ms / 100),  # Faster is better
        }

        # Weights (tuned empirically)
        weights = {
            "fill_rate": 0.4,
            "depth_balance": 0.2,
            "spread_tightness": 0.2,
            "speed_factor": 0.2,
        }

        # Calculate weighted score
        score = sum(features[k] * weights[k] for k in features)

        # Apply logistic transformation
        p_fill = 1 / (1 + np.exp(-4 * (score - 0.5)))

        # Ensure reasonable bounds
        return max(0.1, min(0.95, p_fill))

    def estimate_slippage_budget(self, size_tl: Decimal, volatility_pct: float = 0.1) -> Decimal:
        """
        Estimate slippage budget based on historical data

        Args:
            size_tl: Trade size in TL
            volatility_pct: Recent volatility percentage
        """

        # Base slippage from size impact
        size_impact_bps = Decimal("1") * (size_tl / Decimal("10000"))  # 1 bps per 10K TL

        # Volatility adjustment
        vol_adjustment = Decimal(str(volatility_pct * 10))  # 10 bps per 1% volatility

        # Historical P95 if available
        if self.slippage_history:
            p95_slippage = Decimal(str(np.percentile(self.slippage_history, 95)))
        else:
            p95_slippage = Decimal("5")  # Default 5 bps

        # Total budget
        slippage_budget = (
            size_impact_bps + vol_adjustment + p95_slippage
        ) * self.slippage_multiplier

        return slippage_budget

    def calculate_latency_cost(self, latency_ms: float, size_tl: Decimal) -> Decimal:
        """
        Calculate cost of latency risk

        Args:
            latency_ms: Round-trip latency in milliseconds
            size_tl: Trade size in TL
        """

        # Penalty increases with latency
        latency_hundreds = Decimal(str(latency_ms / 100))
        penalty_bps = latency_hundreds * self.latency_penalty_per_100ms

        # Convert to TL
        latency_cost = (size_tl * penalty_bps) / Decimal("10000")

        return latency_cost

    def calculate_ev(
        self,
        spread_bps: Decimal,
        size_tl: Decimal,
        fee_bps: Decimal,
        maker_fill_rate: float,
        depth_ratio: float,
        latency_ms: float,
        volatility_pct: float = 0.1,
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate expected value of a trade

        Returns:
            (ev_tl, details)
        """

        # Calculate p(fill)
        p_fill = self.calculate_fill_probability(
            maker_fill_rate=maker_fill_rate,
            depth_ratio=depth_ratio,
            spread_bps=float(spread_bps),
            latency_ms=latency_ms,
        )

        # Calculate edge (gross profit)
        edge_tl = (size_tl * spread_bps) / Decimal("10000")

        # Calculate costs
        fee_cost = (size_tl * fee_bps) / Decimal("10000") * 2  # Round trip
        slippage_budget = self.estimate_slippage_budget(size_tl, volatility_pct)
        slippage_cost = (size_tl * slippage_budget) / Decimal("10000")
        latency_cost = self.calculate_latency_cost(latency_ms, size_tl)

        # Calculate EV
        expected_edge = edge_tl * Decimal(str(p_fill))
        total_cost = fee_cost + slippage_cost + latency_cost

        ev = expected_edge - total_cost

        # Prepare details
        details = {
            "p_fill": p_fill,
            "edge_tl": float(edge_tl),
            "expected_edge_tl": float(expected_edge),
            "fee_cost": float(fee_cost),
            "slippage_cost": float(slippage_cost),
            "latency_cost": float(latency_cost),
            "total_cost": float(total_cost),
            "ev_tl": float(ev),
            "ev_bps": float((ev / size_tl) * Decimal("10000")) if size_tl > 0 else 0,
        }

        return ev, details

    def should_trade(
        self,
        spread_bps: Decimal,
        size_tl: Decimal,
        fee_bps: Decimal,
        maker_fill_rate: float,
        depth_ratio: float,
        latency_ms: float,
        volatility_pct: float = 0.1,
    ) -> Tuple[bool, Decimal, Dict]:
        """
        Determine if trade should be executed

        Returns:
            (should_trade, recommended_size, details)
        """

        # Calculate EV
        ev, details = self.calculate_ev(
            spread_bps=spread_bps,
            size_tl=size_tl,
            fee_bps=fee_bps,
            maker_fill_rate=maker_fill_rate,
            depth_ratio=depth_ratio,
            latency_ms=latency_ms,
            volatility_pct=volatility_pct,
        )

        # Check if EV is positive and above threshold
        should_trade = ev >= self.min_ev_threshold

        # Calculate recommended size based on EV
        if should_trade:
            # Scale size based on EV strength
            ev_strength = ev / self.min_ev_threshold

            if ev_strength > 3:
                # Very strong EV, can increase size
                size_multiplier = min(Decimal("1.5"), Decimal("1") + ev_strength / Decimal("10"))
            elif ev_strength > 1.5:
                # Good EV, keep size
                size_multiplier = Decimal("1")
            else:
                # Marginal EV, reduce size
                size_multiplier = Decimal("0.7")

            recommended_size = size_tl * size_multiplier

            # Apply max position limit
            max_position = Decimal(str(self.load_config().get("max_position_tl", 10000)))
            recommended_size = min(recommended_size, max_position)
        else:
            recommended_size = Decimal("0")

        details["should_trade"] = should_trade
        details["recommended_size_tl"] = float(recommended_size)
        details["size_multiplier"] = float(recommended_size / size_tl) if size_tl > 0 else 0

        return should_trade, recommended_size, details

    def record_fill_result(self, filled: bool, slippage_bps: float):
        """Record actual fill result for model improvement"""

        self.fill_history.append(filled)
        if filled and slippage_bps is not None:
            self.slippage_history.append(slippage_bps)

        # Keep only recent history
        if len(self.fill_history) > 1000:
            self.fill_history = self.fill_history[-1000:]
        if len(self.slippage_history) > 1000:
            self.slippage_history = self.slippage_history[-1000:]


def test_ev_gate():
    """Test EV Gate"""

    gate = EVGate()

    print("=" * 60)
    print(" EV GATE TEST")
    print("=" * 60)

    # Test scenarios
    scenarios = [
        {
            "name": "High EV opportunity",
            "spread_bps": Decimal("30"),
            "size_tl": Decimal("5000"),
            "fee_bps": Decimal("20"),
            "maker_fill_rate": 0.7,
            "depth_ratio": 1.0,
            "latency_ms": 50,
            "volatility_pct": 0.1,
        },
        {
            "name": "Marginal opportunity",
            "spread_bps": Decimal("15"),
            "size_tl": Decimal("5000"),
            "fee_bps": Decimal("20"),
            "maker_fill_rate": 0.5,
            "depth_ratio": 0.8,
            "latency_ms": 150,
            "volatility_pct": 0.2,
        },
        {
            "name": "Negative EV (high latency)",
            "spread_bps": Decimal("20"),
            "size_tl": Decimal("5000"),
            "fee_bps": Decimal("20"),
            "maker_fill_rate": 0.3,
            "depth_ratio": 0.5,
            "latency_ms": 500,
            "volatility_pct": 0.3,
        },
    ]

    for scenario in scenarios:
        name = scenario.pop("name")
        should_trade, recommended_size, details = gate.should_trade(**scenario)

        print(f"\n{name}:")
        print(f"  Should Trade: {should_trade}")
        print(f"  EV: {details['ev_tl']:.2f} TL ({details['ev_bps']:.2f} bps)")
        print(f"  P(fill): {details['p_fill']:.2%}")
        print(f"  Recommended Size: {recommended_size:.0f} TL")
        print("  Breakdown:")
        print(f"    Expected Edge: {details['expected_edge_tl']:.2f} TL")
        print(f"    Costs: {details['total_cost']:.2f} TL")

    print("=" * 60)


if __name__ == "__main__":
    test_ev_gate()
