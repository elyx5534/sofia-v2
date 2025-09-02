"""
Tests for MM-Lite strategy
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.strategies.mm_lite import MakerOrder, MMLite, OrderSide


class TestMMLite:
    """Test MM-Lite strategy"""

    def test_initialization(self):
        """Test strategy initialization"""
        mm = MMLite()
        assert mm.symbol == "BTCUSDT"
        assert mm.current_position == Decimal("0")
        assert mm.paper_balance == Decimal("100000")
        assert len(mm.orders) == 0

    def test_order_price_calculation(self):
        """Test order price calculation"""
        mm = MMLite()

        # Wide spread - should join best
        best_bid = Decimal("50000")
        best_ask = Decimal("50010")
        buy_price, sell_price = mm.calculate_order_prices(best_bid, best_ask)

        assert buy_price == best_bid
        assert sell_price == best_ask

        # Tight spread - should step in
        best_bid = Decimal("50000")
        best_ask = Decimal("50000.01")
        buy_price, sell_price = mm.calculate_order_prices(best_bid, best_ask)

        assert buy_price < best_bid
        assert sell_price > best_ask

    def test_inventory_adjustment(self):
        """Test order size adjustment based on inventory"""
        mm = MMLite()

        # Neutral position
        mm.current_position = Decimal("0")
        buy_size = mm.calculate_order_size(OrderSide.BUY)
        sell_size = mm.calculate_order_size(OrderSide.SELL)
        assert buy_size == mm.base_quantity
        assert sell_size == mm.base_quantity

        # Long heavy
        mm.current_position = Decimal("0.08")
        buy_size = mm.calculate_order_size(OrderSide.BUY)
        sell_size = mm.calculate_order_size(OrderSide.SELL)
        assert buy_size < mm.base_quantity  # Reduce buys
        assert sell_size > mm.base_quantity  # Increase sells

        # Short heavy
        mm.current_position = Decimal("-0.08")
        buy_size = mm.calculate_order_size(OrderSide.BUY)
        sell_size = mm.calculate_order_size(OrderSide.SELL)
        assert buy_size > mm.base_quantity  # Increase buys
        assert sell_size < mm.base_quantity  # Reduce sells

    def test_neutralization_trigger(self):
        """Test position neutralization logic"""
        mm = MMLite()

        # Small position - no neutralization
        mm.current_position = Decimal("0.02")
        assert not mm.should_neutralize()

        # Large position - should neutralize
        mm.current_position = Decimal("0.09")
        assert mm.should_neutralize()

        # Time-based neutralization
        mm.current_position = Decimal("0.03")
        mm.last_neutralization = datetime.now()
        assert not mm.should_neutralize()

        # Simulate time passing
        from datetime import timedelta

        mm.last_neutralization = datetime.now() - timedelta(seconds=70)
        assert mm.should_neutralize()

    def test_order_placement(self):
        """Test maker order placement"""
        mm = MMLite()

        orders = mm.place_maker_orders()

        # Should place both buy and sell
        assert len(orders) == 2

        buy_orders = [o for o in orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in orders if o.side == OrderSide.SELL]

        assert len(buy_orders) == 1
        assert len(sell_orders) == 1

        # Check order properties
        buy_order = buy_orders[0]
        assert buy_order.symbol == mm.symbol
        assert buy_order.quantity > 0
        assert not buy_order.filled

    def test_fill_simulation(self):
        """Test order fill simulation"""
        mm = MMLite()

        # Place orders
        mm.place_maker_orders()
        initial_position = mm.current_position

        # Simulate fills
        filled = mm.simulate_fills()

        # Some orders might fill
        if filled:
            # Check position updated
            assert mm.current_position != initial_position

            # Check fill properties
            for order in filled:
                assert order.filled
                assert order.fill_price is not None
                assert order.fill_time is not None

    def test_pnl_calculation(self):
        """Test P&L calculation"""
        mm = MMLite()

        # Create mock filled orders
        buy_order = MakerOrder(
            id="test_buy",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("50000"),
            quantity=Decimal("0.01"),
            timestamp=datetime.now(),
            filled=True,
            fill_price=Decimal("50000"),
        )

        sell_order = MakerOrder(
            id="test_sell",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            price=Decimal("50010"),
            quantity=Decimal("0.01"),
            timestamp=datetime.now(),
            filled=True,
            fill_price=Decimal("50010"),
        )

        mm.filled_orders = [buy_order, sell_order]

        pnl = mm.calculate_pnl()

        # Should have positive P&L (sold higher than bought)
        assert pnl > 0
        expected_pnl = (Decimal("50010") - Decimal("50000")) * Decimal("0.01")
        assert abs(pnl - expected_pnl) < Decimal("0.01")

    def test_pass_criteria(self):
        """Test PASS criteria checking"""
        mm = MMLite()

        # Initial state - might not pass
        pass_check, criteria = mm.check_pass_criteria()

        assert isinstance(pass_check, bool)
        assert "pnl_positive" in criteria
        assert "inventory_controlled" in criteria
        assert "fill_rate_good" in criteria

        # Simulate successful trading
        mm.fill_count = 50
        mm.order_count = 100
        mm.total_pnl = Decimal("10")

        pass_check, criteria = mm.check_pass_criteria()
        assert criteria["fill_rate_good"]  # 50% fill rate > 40%

    def test_full_cycle(self):
        """Test full trading cycle"""
        mm = MMLite()

        # Run multiple cycles
        for _ in range(10):
            report = mm.run_cycle()

            assert "timestamp" in report
            assert "actions" in report
            assert "metrics" in report

            metrics = report["metrics"]
            assert "current_position" in metrics
            assert "fill_rate" in metrics
            assert "pnl" in metrics
            assert "pnl_pct" in metrics

        # Check final state
        metrics = mm.get_metrics()
        assert metrics["order_count"] > 0
        assert metrics["fill_rate"] >= 0
        assert metrics["fill_rate"] <= 1

    def test_position_limits(self):
        """Test position limit enforcement"""
        mm = MMLite()

        # Set to max long position
        mm.current_position = mm.max_position

        orders = mm.place_maker_orders()

        # Should only place sell orders
        buy_orders = [o for o in orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in orders if o.side == OrderSide.SELL]

        assert len(buy_orders) == 0
        assert len(sell_orders) > 0

        # Set to max short position
        mm.current_position = -mm.max_position

        orders = mm.place_maker_orders()

        # Should only place buy orders
        buy_orders = [o for o in orders if o.side == OrderSide.BUY]
        sell_orders = [o for o in orders if o.side == OrderSide.SELL]

        assert len(buy_orders) > 0
        assert len(sell_orders) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
