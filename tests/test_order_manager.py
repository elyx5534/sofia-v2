"""Tests for the order management module."""

from datetime import datetime

import pytest
from src.core.order_manager import (
    Order,
    OrderManager,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


class TestOrderEnums:
    """Test cases for Order enums."""

    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderType.STOP == "stop"
        assert OrderType.STOP_LIMIT == "stop_limit"
        assert OrderType.TRAILING_STOP == "trailing_stop"

    def test_order_side_values(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"

    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.OPEN == "open"
        assert OrderStatus.PARTIALLY_FILLED == "partially_filled"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.CANCELLED == "cancelled"
        assert OrderStatus.REJECTED == "rejected"
        assert OrderStatus.EXPIRED == "expired"

    def test_time_in_force_values(self):
        """Test TimeInForce enum values."""
        assert TimeInForce.GTC == "gtc"
        assert TimeInForce.IOC == "ioc"
        assert TimeInForce.FOK == "fok"
        assert TimeInForce.DAY == "day"


class TestOrder:
    """Test cases for Order class."""

    def test_order_creation_minimal(self):
        """Test creating an order with minimal parameters."""
        order = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)

        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.MARKET
        assert order.quantity == 100
        assert order.price is None
        assert order.stop_price is None
        assert order.time_in_force == TimeInForce.GTC
        assert order.status == OrderStatus.PENDING
        assert order.filled_quantity == 0
        assert order.average_fill_price is None
        assert order.notes is None
        assert isinstance(order.id, str)
        assert len(order.id) > 0
        assert isinstance(order.created_at, datetime)
        assert isinstance(order.updated_at, datetime)

    def test_order_creation_full_parameters(self):
        """Test creating an order with all parameters."""
        order = Order(
            symbol="GOOGL",
            side=OrderSide.SELL,
            type=OrderType.LIMIT,
            quantity=50,
            price=2000.0,
            stop_price=1950.0,
            time_in_force=TimeInForce.IOC,
            notes="Test order",
        )

        assert order.symbol == "GOOGL"
        assert order.side == OrderSide.SELL
        assert order.type == OrderType.LIMIT
        assert order.quantity == 50
        assert order.price == 2000.0
        assert order.stop_price == 1950.0
        assert order.time_in_force == TimeInForce.IOC
        assert order.notes == "Test order"

    def test_order_unique_ids(self):
        """Test that orders get unique IDs."""
        order1 = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)
        order2 = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)

        assert order1.id != order2.id

    def test_is_filled_method(self):
        """Test is_filled method."""
        order = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)

        # Initially not filled
        assert not order.is_filled()

        # After setting to filled
        order.status = OrderStatus.FILLED
        assert order.is_filled()

    def test_is_active_method(self):
        """Test is_active method."""
        order = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)

        # Test active statuses
        for status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            order.status = status
            assert order.is_active()

        # Test inactive statuses
        for status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        ]:
            order.status = status
            assert not order.is_active()

    def test_cancel_method(self):
        """Test cancel method."""
        order = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)
        initial_time = order.updated_at

        # Cancel active order
        assert order.is_active()
        order.cancel()
        assert order.status == OrderStatus.CANCELLED
        assert order.updated_at > initial_time

        # Try to cancel already cancelled order
        order.cancel()
        assert order.status == OrderStatus.CANCELLED  # Should remain cancelled

    def test_cancel_inactive_order(self):
        """Test cancelling an inactive order does nothing."""
        order = Order(symbol="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, quantity=100)
        order.status = OrderStatus.FILLED
        initial_time = order.updated_at

        order.cancel()
        assert order.status == OrderStatus.FILLED  # Should remain filled
        assert order.updated_at == initial_time  # Time shouldn't change


class TestOrderManager:
    """Test cases for OrderManager class."""

    @pytest.fixture
    def order_manager(self):
        """Create a test order manager."""
        return OrderManager()

    def test_order_manager_initialization(self, order_manager):
        """Test OrderManager initialization."""
        assert len(order_manager.orders) == 0
        assert len(order_manager.active_orders) == 0
        assert len(order_manager.order_history) == 0

    def test_create_order_market(self, order_manager):
        """Test creating a market order."""
        order = order_manager.create_order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=100
        )

        assert isinstance(order, Order)
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.MARKET
        assert order.quantity == 100
        assert order.price is None
        assert order.time_in_force == TimeInForce.GTC

        # Check order is stored correctly
        assert len(order_manager.orders) == 1
        assert order.id in order_manager.orders
        assert len(order_manager.active_orders) == 1
        assert order in order_manager.active_orders

    def test_create_order_limit(self, order_manager):
        """Test creating a limit order."""
        order = order_manager.create_order(
            symbol="GOOGL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=2000.0,
            time_in_force=TimeInForce.IOC,
        )

        assert order.type == OrderType.LIMIT
        assert order.price == 2000.0
        assert order.time_in_force == TimeInForce.IOC

    def test_create_order_stop(self, order_manager):
        """Test creating a stop order."""
        order = order_manager.create_order(
            symbol="MSFT",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=75,
            stop_price=300.0,
        )

        assert order.type == OrderType.STOP
        assert order.stop_price == 300.0

    def test_cancel_order_success(self, order_manager):
        """Test successfully cancelling an order."""
        # Create an order
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        order_id = order.id

        # Cancel the order
        result = order_manager.cancel_order(order_id)

        assert result is True
        assert order.status == OrderStatus.CANCELLED
        assert len(order_manager.active_orders) == 0
        assert len(order_manager.order_history) == 1
        assert order in order_manager.order_history

    def test_cancel_order_nonexistent(self, order_manager):
        """Test cancelling a non-existent order."""
        result = order_manager.cancel_order("invalid_id")
        assert result is False

    def test_cancel_order_inactive(self, order_manager):
        """Test cancelling an already inactive order."""
        # Create and fill an order
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        order.status = OrderStatus.FILLED
        order_id = order.id

        # Try to cancel filled order
        result = order_manager.cancel_order(order_id)
        assert result is False
        assert order.status == OrderStatus.FILLED  # Should remain filled

    def test_update_order_status_basic(self, order_manager):
        """Test updating order status."""
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        initial_time = order.updated_at
        order_id = order.id

        # Update to open status
        result = order_manager.update_order_status(order_id, OrderStatus.OPEN)

        assert result is True
        assert order.status == OrderStatus.OPEN
        assert order.updated_at > initial_time

    def test_update_order_status_with_fills(self, order_manager):
        """Test updating order status with fill information."""
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 100, 150.0)
        order_id = order.id

        # Partially fill the order
        result = order_manager.update_order_status(
            order_id, OrderStatus.PARTIALLY_FILLED, filled_quantity=50, average_fill_price=149.50
        )

        assert result is True
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 50
        assert order.average_fill_price == 149.50
        assert order in order_manager.active_orders  # Still active

    def test_update_order_status_complete_fill(self, order_manager):
        """Test updating order to completely filled."""
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 100, 150.0)
        order_id = order.id

        # Completely fill the order
        result = order_manager.update_order_status(
            order_id, OrderStatus.FILLED, filled_quantity=100, average_fill_price=150.25
        )

        assert result is True
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order.average_fill_price == 150.25
        assert order not in order_manager.active_orders  # Moved to history
        assert order in order_manager.order_history

    def test_update_order_status_nonexistent(self, order_manager):
        """Test updating non-existent order."""
        result = order_manager.update_order_status("invalid_id", OrderStatus.FILLED)
        assert result is False

    def test_get_active_orders_all(self, order_manager):
        """Test getting all active orders."""
        # Create multiple orders
        order1 = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        order2 = order_manager.create_order("GOOGL", OrderSide.SELL, OrderType.LIMIT, 50, 2000.0)
        order3 = order_manager.create_order(
            "MSFT", OrderSide.BUY, OrderType.STOP, 75, stop_price=300.0
        )

        # Fill one order (should not be in active list)
        order_manager.update_order_status(order2.id, OrderStatus.FILLED)

        active_orders = order_manager.get_active_orders()

        assert len(active_orders) == 2
        assert order1 in active_orders
        assert order2 not in active_orders  # Should be in history
        assert order3 in active_orders

    def test_get_active_orders_by_symbol(self, order_manager):
        """Test getting active orders for specific symbol."""
        # Create orders for different symbols
        aapl_order1 = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        aapl_order2 = order_manager.create_order("AAPL", OrderSide.SELL, OrderType.LIMIT, 50, 160.0)
        googl_order = order_manager.create_order("GOOGL", OrderSide.BUY, OrderType.MARKET, 25)

        aapl_orders = order_manager.get_active_orders("AAPL")

        assert len(aapl_orders) == 2
        assert aapl_order1 in aapl_orders
        assert aapl_order2 in aapl_orders
        assert googl_order not in aapl_orders

    def test_get_active_orders_returns_copy(self, order_manager):
        """Test that get_active_orders returns a copy, not the original list."""
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)

        active_orders = order_manager.get_active_orders()
        original_length = len(order_manager.active_orders)

        # Modify the returned list
        active_orders.append("dummy")

        # Original should be unchanged
        assert len(order_manager.active_orders) == original_length

    def test_get_order_history_all(self, order_manager):
        """Test getting complete order history."""
        # Create and complete some orders
        order1 = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        order2 = order_manager.create_order("GOOGL", OrderSide.SELL, OrderType.LIMIT, 50, 2000.0)

        # Complete the orders
        order_manager.update_order_status(order1.id, OrderStatus.FILLED)
        order_manager.cancel_order(order2.id)

        history = order_manager.get_order_history()

        assert len(history) == 2
        assert order1 in history
        assert order2 in history

    def test_get_order_history_by_symbol(self, order_manager):
        """Test getting order history for specific symbol."""
        # Create orders
        aapl_order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
        googl_order = order_manager.create_order(
            "GOOGL", OrderSide.SELL, OrderType.LIMIT, 50, 2000.0
        )

        # Complete orders
        order_manager.update_order_status(aapl_order.id, OrderStatus.FILLED)
        order_manager.update_order_status(googl_order.id, OrderStatus.FILLED)

        aapl_history = order_manager.get_order_history("AAPL")

        assert len(aapl_history) == 1
        assert aapl_order in aapl_history
        assert googl_order not in aapl_history

    def test_get_order_history_with_limit(self, order_manager):
        """Test getting order history with limit."""
        # Create many completed orders
        orders = []
        for i in range(10):
            order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100)
            order_manager.update_order_status(order.id, OrderStatus.FILLED)
            orders.append(order)

        # Get last 5 orders
        history = order_manager.get_order_history(limit=5)

        assert len(history) == 5
        # Should get the last 5 orders
        assert all(order in orders[-5:] for order in history)

    def test_order_lifecycle(self, order_manager):
        """Test complete order lifecycle."""
        # Create order
        order = order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 100, 150.0)

        assert order.status == OrderStatus.PENDING
        assert order in order_manager.active_orders

        # Update to open
        order_manager.update_order_status(order.id, OrderStatus.OPEN)
        assert order.status == OrderStatus.OPEN
        assert order in order_manager.active_orders

        # Partial fill
        order_manager.update_order_status(order.id, OrderStatus.PARTIALLY_FILLED, 30, 149.75)
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == 30
        assert order in order_manager.active_orders

        # Complete fill
        order_manager.update_order_status(order.id, OrderStatus.FILLED, 100, 150.10)
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order not in order_manager.active_orders
        assert order in order_manager.order_history

    def test_multiple_orders_management(self, order_manager):
        """Test managing multiple orders simultaneously."""
        # Create multiple orders
        orders = []
        for i in range(5):
            order = order_manager.create_order(
                f"STOCK{i}", OrderSide.BUY, OrderType.MARKET, 100 + i * 10
            )
            orders.append(order)

        assert len(order_manager.active_orders) == 5

        # Cancel some orders
        order_manager.cancel_order(orders[0].id)
        order_manager.cancel_order(orders[2].id)

        assert len(order_manager.active_orders) == 3
        assert len(order_manager.order_history) == 2

        # Fill remaining orders
        for order in orders[1:]:
            if order.status != OrderStatus.CANCELLED:
                order_manager.update_order_status(order.id, OrderStatus.FILLED)

        assert len(order_manager.active_orders) == 0
        assert len(order_manager.order_history) == 5
