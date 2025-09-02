"""
Funding Farmer v2
Delta-neutral funding rate strategy with borrow costs
"""

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class FundingFarmerV2:
    """Enhanced funding rate farming with cost awareness"""

    def __init__(self, config: Dict = None):
        if config is None:
            config = self.load_config()

        # Strategy parameters
        self.min_funding_rate_bps = Decimal(str(config.get("min_funding_rate_bps", 10)))
        self.max_position_size = Decimal(str(config.get("max_position_size", 100000)))
        self.rebalance_threshold = Decimal(str(config.get("rebalance_threshold", 0.02)))

        # Cost parameters
        self.borrow_rate_annual = Decimal(str(config.get("borrow_rate_annual", 0.1)))  # 10% APR
        self.funding_interval_hours = config.get("funding_interval_hours", 8)

        # Positions
        self.positions = {}
        self.total_funding_collected = Decimal("0")
        self.total_borrow_costs = Decimal("0")

        # Delta monitoring
        self.delta_history = []
        self.max_delta_drift = Decimal(str(config.get("max_delta_drift", 0.05)))

    def load_config(self) -> Dict:
        """Load funding farmer configuration"""
        config_file = Path("config/funding_farmer.yaml")

        if config_file.exists():
            import yaml

            with open(config_file) as f:
                return yaml.safe_load(f)

        # Default config
        return {
            "min_funding_rate_bps": 10,
            "max_position_size": 100000,
            "rebalance_threshold": 0.02,
            "borrow_rate_annual": 0.1,
            "funding_interval_hours": 8,
            "max_delta_drift": 0.05,
        }

    def get_funding_rates(self) -> Dict[str, Decimal]:
        """Get current funding rates from exchanges"""

        # Mock funding rates for testing
        # In production, fetch from exchange APIs
        rates = {
            "BTCUSDT_PERP": Decimal("0.0015"),  # 15 bps
            "ETHUSDT_PERP": Decimal("0.0012"),  # 12 bps
            "SOLUSDT_PERP": Decimal("0.0020"),  # 20 bps
            "BNBUSDT_PERP": Decimal("0.0008"),  # 8 bps
        }

        return rates

    def get_spot_prices(self) -> Dict[str, Decimal]:
        """Get spot prices for delta hedging"""

        # Mock spot prices
        prices = {
            "BTCUSDT": Decimal("50000"),
            "ETHUSDT": Decimal("3000"),
            "SOLUSDT": Decimal("100"),
            "BNBUSDT": Decimal("400"),
        }

        return prices

    def calculate_borrow_cost_hourly(self, position_value: Decimal) -> Decimal:
        """Calculate hourly borrow cost"""

        # Convert annual rate to hourly
        hourly_rate = self.borrow_rate_annual / Decimal("8760")  # Hours in year

        return position_value * hourly_rate

    def calculate_net_funding_rate(self, funding_rate: Decimal, position_value: Decimal) -> Decimal:
        """Calculate net funding rate after borrow costs"""

        # Funding collected per interval
        funding_collected = position_value * funding_rate

        # Borrow cost for funding interval
        borrow_cost = self.calculate_borrow_cost_hourly(position_value) * Decimal(
            str(self.funding_interval_hours)
        )

        # Net funding
        net_funding = funding_collected - borrow_cost

        # Convert to rate
        net_rate = net_funding / position_value if position_value > 0 else Decimal("0")

        return net_rate

    def calculate_position_delta(self) -> Decimal:
        """Calculate current portfolio delta"""

        total_long = Decimal("0")
        total_short = Decimal("0")

        for symbol, position in self.positions.items():
            if position["side"] == "long":
                total_long += position["value"]
            else:
                total_short += position["value"]

        # Delta = (Long - Short) / Total
        total = total_long + total_short
        if total > 0:
            delta = (total_long - total_short) / total
        else:
            delta = Decimal("0")

        return delta

    def should_open_position(
        self, symbol: str, funding_rate: Decimal, spot_price: Decimal
    ) -> Tuple[bool, Decimal, str]:
        """Determine if position should be opened"""

        # Convert to basis points
        funding_rate_bps = funding_rate * Decimal("10000")

        # Check minimum funding rate
        if funding_rate_bps < self.min_funding_rate_bps:
            return False, Decimal("0"), f"Funding rate {funding_rate_bps:.2f} bps below minimum"

        # Calculate position size
        base_size = self.max_position_size * Decimal("0.2")  # 20% of max per position

        # Calculate net rate
        net_rate = self.calculate_net_funding_rate(funding_rate, base_size)
        net_rate_bps = net_rate * Decimal("10000")

        # Check if profitable after costs
        if net_rate_bps < Decimal("5"):  # Minimum 5 bps net
            return False, Decimal("0"), f"Net rate {net_rate_bps:.2f} bps too low after costs"

        # Adjust size based on net rate strength
        if net_rate_bps > Decimal("15"):
            size_multiplier = Decimal("1.5")
        elif net_rate_bps > Decimal("10"):
            size_multiplier = Decimal("1.0")
        else:
            size_multiplier = Decimal("0.7")

        position_size = base_size * size_multiplier

        return True, position_size, f"Open position for {net_rate_bps:.2f} bps net funding"

    def open_delta_neutral_position(
        self, symbol: str, position_size: Decimal, spot_price: Decimal, funding_rate: Decimal
    ) -> Dict:
        """Open delta-neutral position (long spot, short perp)"""

        # Calculate quantities
        perp_symbol = f"{symbol}_PERP"
        quantity = position_size / spot_price

        # Create position
        position = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "perp_symbol": perp_symbol,
            "side": "neutral",  # Delta-neutral
            "spot_side": "long",
            "perp_side": "short",
            "quantity": float(quantity),
            "spot_price": float(spot_price),
            "perp_price": float(spot_price),  # Assume same for simplicity
            "value": float(position_size),
            "funding_rate": float(funding_rate),
            "net_funding_rate": float(self.calculate_net_funding_rate(funding_rate, position_size)),
            "funding_collected": 0,
            "borrow_costs": 0,
            "pnl": 0,
        }

        # Store position
        self.positions[symbol] = position

        logger.info(f"Opened delta-neutral position: {symbol} size={position_size:.2f}")

        return position

    def check_rebalance_needed(self) -> Tuple[bool, str]:
        """Check if rebalancing is needed"""

        # Calculate current delta
        current_delta = self.calculate_position_delta()

        # Store in history
        self.delta_history.append(
            {"timestamp": datetime.now().isoformat(), "delta": float(current_delta)}
        )

        # Check if delta drifted too much
        if abs(current_delta) > self.rebalance_threshold:
            return True, f"Delta drift: {current_delta:.4f}"

        # Check individual positions
        spot_prices = self.get_spot_prices()

        for symbol, position in self.positions.items():
            if symbol in spot_prices:
                current_price = spot_prices[symbol]
                entry_price = Decimal(str(position["spot_price"]))

                # Calculate price change
                price_change = abs((current_price - entry_price) / entry_price)

                if price_change > self.max_delta_drift:
                    return True, f"{symbol} price drift: {price_change:.2%}"

        return False, ""

    def rebalance_positions(self) -> List[Dict]:
        """Rebalance to maintain delta neutrality"""

        actions = []
        current_delta = self.calculate_position_delta()
        spot_prices = self.get_spot_prices()

        logger.info(f"Rebalancing positions, current delta: {current_delta:.4f}")

        for symbol, position in self.positions.items():
            if symbol not in spot_prices:
                continue

            current_price = spot_prices[symbol]
            entry_price = Decimal(str(position["spot_price"]))
            quantity = Decimal(str(position["quantity"]))

            # Calculate drift
            price_ratio = current_price / entry_price

            # Rebalance amounts
            if price_ratio > Decimal("1.02"):  # Price up 2%
                # Reduce long spot, increase short perp
                rebalance_qty = quantity * Decimal("0.1")  # 10% adjustment

                actions.append(
                    {
                        "symbol": symbol,
                        "action": "reduce_spot_long",
                        "quantity": float(rebalance_qty),
                        "reason": "Price increased, reducing long exposure",
                    }
                )

            elif price_ratio < Decimal("0.98"):  # Price down 2%
                # Increase long spot, reduce short perp
                rebalance_qty = quantity * Decimal("0.1")

                actions.append(
                    {
                        "symbol": symbol,
                        "action": "increase_spot_long",
                        "quantity": float(rebalance_qty),
                        "reason": "Price decreased, increasing long exposure",
                    }
                )

        return actions

    def collect_funding(self) -> Dict:
        """Collect funding payments"""

        funding_report = {
            "timestamp": datetime.now().isoformat(),
            "positions": [],
            "total_collected": 0,
            "total_costs": 0,
            "net_collected": 0,
        }

        for symbol, position in self.positions.items():
            # Calculate funding for this interval
            position_value = Decimal(str(position["value"]))
            funding_rate = Decimal(str(position["funding_rate"]))

            funding_collected = position_value * funding_rate
            borrow_cost = self.calculate_borrow_cost_hourly(position_value) * Decimal(
                str(self.funding_interval_hours)
            )
            net_funding = funding_collected - borrow_cost

            # Update position
            position["funding_collected"] += float(funding_collected)
            position["borrow_costs"] += float(borrow_cost)
            position["pnl"] += float(net_funding)

            # Update totals
            self.total_funding_collected += funding_collected
            self.total_borrow_costs += borrow_cost

            # Add to report
            funding_report["positions"].append(
                {
                    "symbol": symbol,
                    "funding_collected": float(funding_collected),
                    "borrow_cost": float(borrow_cost),
                    "net_funding": float(net_funding),
                    "total_pnl": position["pnl"],
                }
            )

            funding_report["total_collected"] += float(funding_collected)
            funding_report["total_costs"] += float(borrow_cost)
            funding_report["net_collected"] += float(net_funding)

        return funding_report

    def close_position(self, symbol: str, reason: str = "") -> Dict:
        """Close a funding position"""

        if symbol not in self.positions:
            return {"error": f"Position {symbol} not found"}

        position = self.positions[symbol]

        # Calculate final P&L
        final_pnl = position["pnl"]

        # Create close report
        close_report = {
            "symbol": symbol,
            "close_time": datetime.now().isoformat(),
            "reason": reason,
            "total_funding_collected": position["funding_collected"],
            "total_borrow_costs": position["borrow_costs"],
            "net_pnl": final_pnl,
            "return_pct": (final_pnl / position["value"]) * 100 if position["value"] > 0 else 0,
        }

        # Remove position
        del self.positions[symbol]

        logger.info(f"Closed position {symbol}: P&L={final_pnl:.2f}")

        return close_report

    def get_status(self) -> Dict:
        """Get current strategy status"""

        status = {
            "timestamp": datetime.now().isoformat(),
            "active_positions": len(self.positions),
            "total_value": sum(p["value"] for p in self.positions.values()),
            "current_delta": float(self.calculate_position_delta()),
            "total_funding_collected": float(self.total_funding_collected),
            "total_borrow_costs": float(self.total_borrow_costs),
            "net_pnl": float(self.total_funding_collected - self.total_borrow_costs),
            "positions": [],
        }

        for symbol, position in self.positions.items():
            status["positions"].append(
                {
                    "symbol": symbol,
                    "value": position["value"],
                    "funding_rate_bps": position["funding_rate"] * 10000,
                    "net_rate_bps": position["net_funding_rate"] * 10000,
                    "pnl": position["pnl"],
                }
            )

        return status

    def run_cycle(self) -> Dict:
        """Run one funding farmer cycle"""

        cycle_report = {"timestamp": datetime.now().isoformat(), "actions": []}

        # Get current rates
        funding_rates = self.get_funding_rates()
        spot_prices = self.get_spot_prices()

        # Check for new opportunities
        for perp_symbol, funding_rate in funding_rates.items():
            base_symbol = perp_symbol.replace("_PERP", "")

            if base_symbol not in self.positions and base_symbol in spot_prices:
                should_open, size, reason = self.should_open_position(
                    base_symbol, funding_rate, spot_prices[base_symbol]
                )

                if should_open:
                    position = self.open_delta_neutral_position(
                        base_symbol, size, spot_prices[base_symbol], funding_rate
                    )

                    cycle_report["actions"].append(
                        {
                            "type": "open_position",
                            "symbol": base_symbol,
                            "size": float(size),
                            "reason": reason,
                        }
                    )

        # Check if rebalancing needed
        needs_rebalance, rebalance_reason = self.check_rebalance_needed()

        if needs_rebalance:
            rebalance_actions = self.rebalance_positions()
            cycle_report["actions"].extend(rebalance_actions)
            cycle_report["rebalance_reason"] = rebalance_reason

        # Collect funding (if interval passed)
        # In production, check actual funding times
        if len(self.positions) > 0:
            funding_report = self.collect_funding()
            cycle_report["funding"] = funding_report

        # Check for positions to close
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]

            # Close if funding rate dropped
            current_rate = funding_rates.get(f"{symbol}_PERP", Decimal("0"))
            if current_rate * Decimal("10000") < Decimal("5"):  # Below 5 bps
                close_report = self.close_position(symbol, "Low funding rate")
                cycle_report["actions"].append(
                    {"type": "close_position", "symbol": symbol, "report": close_report}
                )

        return cycle_report


def test_funding_farmer():
    """Test funding farmer strategy"""

    print("=" * 60)
    print(" FUNDING FARMER V2 TEST")
    print("=" * 60)

    farmer = FundingFarmerV2()

    # Run a few cycles
    for cycle in range(3):
        print(f"\nCycle {cycle + 1}:")
        print("-" * 30)

        report = farmer.run_cycle()

        if report["actions"]:
            print("Actions:")
            for action in report["actions"]:
                if action.get("type") == "open_position":
                    print(f"  [OPEN] {action['symbol']} size=${action['size']:,.0f}")
                elif action.get("type") == "close_position":
                    print(f"  [CLOSE] {action['symbol']}")
                else:
                    print(
                        f"  [REBALANCE] {action.get('symbol', 'N/A')}: {action.get('action', 'N/A')}"
                    )

        if "funding" in report:
            funding = report["funding"]
            print("\nFunding Collection:")
            print(f"  Collected: ${funding['total_collected']:.2f}")
            print(f"  Costs: ${funding['total_costs']:.2f}")
            print(f"  Net: ${funding['net_collected']:.2f}")

    # Print final status
    status = farmer.get_status()

    print("\n" + "=" * 60)
    print(" FINAL STATUS")
    print("=" * 60)
    print(f"Active Positions: {status['active_positions']}")
    print(f"Total Value: ${status['total_value']:,.2f}")
    print(f"Current Delta: {status['current_delta']:.4f}")
    print(f"Total Funding: ${status['total_funding_collected']:.2f}")
    print(f"Total Costs: ${status['total_borrow_costs']:.2f}")
    print(f"Net P&L: ${status['net_pnl']:.2f}")

    if status["positions"]:
        print("\nPositions:")
        for pos in status["positions"]:
            print(
                f"  {pos['symbol']}: P&L=${pos['pnl']:.2f} (Net rate: {pos['net_rate_bps']:.2f} bps)"
            )

    print("=" * 60)


if __name__ == "__main__":
    test_funding_farmer()
