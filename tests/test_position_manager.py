"""Tests for the position management module."""

from datetime import datetime

import pytest
from src.core.position_manager import Position, PositionManager


class TestPosition:
    """Test cases for Position class."""

    def test_position_creation(self):
        """Test position creation with basic parameters."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0)

        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.current_price == 155.0
        assert position.realized_pnl == 0
        assert position.unrealized_pnl == 0  # Not calculated until update_price
        assert isinstance(position.id, str)
        assert len(position.id) > 0
        assert isinstance(position.opened_at, datetime)
        assert isinstance(position.updated_at, datetime)

    def test_position_unique_ids(self):
        """Test that positions get unique IDs."""
        position1 = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0)
        position2 = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0)

        assert position1.id != position2.id

    def test_update_price(self):
        """Test price update functionality."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=150.0)
        initial_time = position.updated_at

        # Update to higher price
        position.update_price(160.0)

        assert position.current_price == 160.0
        assert position.unrealized_pnl == 1000.0  # (160 - 150) * 100
        assert position.updated_at > initial_time

    def test_update_price_loss(self):
        """Test price update with loss."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=150.0)

        # Update to lower price
        position.update_price(140.0)

        assert position.current_price == 140.0
        assert position.unrealized_pnl == -1000.0  # (140 - 150) * 100

    def test_update_price_short_position(self):
        """Test price update for short position (negative quantity)."""
        position = Position(
            symbol="AAPL",
            quantity=-100,
            entry_price=150.0,
            current_price=150.0,  # Short position
        )

        # Price goes up - loss for short position
        position.update_price(160.0)

        assert position.current_price == 160.0
        assert position.unrealized_pnl == -1000.0  # (160 - 150) * (-100)

    def test_close_position(self):
        """Test closing a position."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0)
        initial_time = position.updated_at

        # Close at profit
        realized_pnl = position.close_position(160.0)

        assert realized_pnl == 1000.0  # (160 - 150) * 100
        assert position.realized_pnl == 1000.0
        assert position.quantity == 0
        assert position.updated_at > initial_time

    def test_close_position_loss(self):
        """Test closing a position at loss."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=145.0)

        # Close at loss
        realized_pnl = position.close_position(140.0)

        assert realized_pnl == -1000.0  # (140 - 150) * 100
        assert position.realized_pnl == -1000.0
        assert position.quantity == 0

    def test_is_profitable(self):
        """Test profitability check."""
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=150.0)

        # Initially no unrealized profit
        assert not position.is_profitable()

        # Update to profitable price
        position.update_price(160.0)
        assert position.is_profitable()

        # Update to loss
        position.update_price(140.0)
        assert not position.is_profitable()

    def test_get_return_percentage(self):
        """Test return percentage calculation."""
        position = Position(symbol="AAPL", quantity=100, entry_price=100.0, current_price=110.0)

        # 10% gain
        assert position.get_return_percentage() == 10.0

        # Update to 20% gain
        position.update_price(120.0)
        assert position.get_return_percentage() == 20.0

        # Update to 10% loss
        position.update_price(90.0)
        assert position.get_return_percentage() == -10.0

    def test_get_return_percentage_zero_entry_price(self):
        """Test return percentage with zero entry price."""
        position = Position(symbol="FREE", quantity=100, entry_price=0.0, current_price=10.0)

        # Should handle division by zero gracefully
        assert position.get_return_percentage() == 0


class TestPositionManager:
    """Test cases for PositionManager class."""

    @pytest.fixture
    def position_manager(self):
        """Create a test position manager."""
        return PositionManager()

    def test_position_manager_initialization(self, position_manager):
        """Test PositionManager initialization."""
        assert len(position_manager.positions) == 0
        assert len(position_manager.closed_positions) == 0
        assert position_manager.total_realized_pnl == 0

    def test_open_position_new(self, position_manager):
        """Test opening a new position."""
        position = position_manager.open_position("AAPL", 100, 150.0)

        assert isinstance(position, Position)
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.current_price == 150.0

        # Check it's stored in manager
        assert len(position_manager.positions) == 1
        assert "AAPL" in position_manager.positions
        assert position_manager.positions["AAPL"] is position

    def test_open_position_add_to_existing(self, position_manager):
        """Test adding to existing position (averaging)."""
        # Open initial position
        position1 = position_manager.open_position("AAPL", 100, 150.0)

        # Add to position at different price
        position2 = position_manager.open_position("AAPL", 50, 160.0)

        # Should be the same position object
        assert position1 is position2
        assert len(position_manager.positions) == 1

        # Check averaging
        assert position2.quantity == 150  # 100 + 50
        # Average price: (100*150 + 50*160) / 150 = 153.33
        assert abs(position2.entry_price - 153.33) < 0.01

    def test_open_position_multiple_symbols(self, position_manager):
        """Test opening positions for multiple symbols."""
        aapl = position_manager.open_position("AAPL", 100, 150.0)
        googl = position_manager.open_position("GOOGL", 50, 2000.0)
        msft = position_manager.open_position("MSFT", 200, 300.0)

        assert len(position_manager.positions) == 3
        assert position_manager.positions["AAPL"] is aapl
        assert position_manager.positions["GOOGL"] is googl
        assert position_manager.positions["MSFT"] is msft

    def test_close_position_full(self, position_manager):
        """Test closing a full position."""
        # Open position
        position_manager.open_position("AAPL", 100, 150.0)

        # Close at profit
        realized_pnl = position_manager.close_position("AAPL", 160.0)

        assert realized_pnl == 1000.0  # (160 - 150) * 100
        assert len(position_manager.positions) == 0  # Position removed
        assert len(position_manager.closed_positions) == 1  # Moved to closed
        assert position_manager.total_realized_pnl == 1000.0

    def test_close_position_partial(self, position_manager):
        """Test partial position closing."""
        # Open position
        position_manager.open_position("AAPL", 100, 150.0)

        # Close 30 shares at profit
        realized_pnl = position_manager.close_position("AAPL", 160.0, quantity=30)

        assert realized_pnl == 300.0  # (160 - 150) * 30
        assert len(position_manager.positions) == 1  # Position still open
        assert position_manager.positions["AAPL"].quantity == 70  # 100 - 30
        assert position_manager.positions["AAPL"].realized_pnl == 300.0
        assert position_manager.total_realized_pnl == 300.0

    def test_close_position_partial_exact_quantity(self, position_manager):
        """Test partial close with exact remaining quantity."""
        position_manager.open_position("AAPL", 100, 150.0)

        # Close exact remaining quantity (should be full close)
        realized_pnl = position_manager.close_position("AAPL", 160.0, quantity=100)

        assert realized_pnl == 1000.0
        assert len(position_manager.positions) == 0  # Position fully closed

    def test_close_position_more_than_available(self, position_manager):
        """Test closing more shares than available."""
        position_manager.open_position("AAPL", 100, 150.0)

        # Try to close 200 shares (more than 100 available)
        realized_pnl = position_manager.close_position("AAPL", 160.0, quantity=200)

        # Should close full position
        assert realized_pnl == 1000.0  # Full position PnL
        assert len(position_manager.positions) == 0

    def test_close_position_nonexistent(self, position_manager):
        """Test closing non-existent position."""
        result = position_manager.close_position("NONEXISTENT", 100.0)
        assert result is None

    def test_update_prices(self, position_manager):
        """Test updating prices for multiple positions."""
        # Open multiple positions
        position_manager.open_position("AAPL", 100, 150.0)
        position_manager.open_position("GOOGL", 50, 2000.0)
        position_manager.open_position("MSFT", 200, 300.0)

        # Update prices
        prices = {"AAPL": 160.0, "GOOGL": 2100.0, "MSFT": 290.0, "TSLA": 800.0}  # Not in positions
        position_manager.update_prices(prices)

        # Check updated prices and PnLs
        assert position_manager.positions["AAPL"].current_price == 160.0
        assert position_manager.positions["AAPL"].unrealized_pnl == 1000.0

        assert position_manager.positions["GOOGL"].current_price == 2100.0
        assert position_manager.positions["GOOGL"].unrealized_pnl == 5000.0

        assert position_manager.positions["MSFT"].current_price == 290.0
        assert position_manager.positions["MSFT"].unrealized_pnl == -2000.0

    def test_get_position(self, position_manager):
        """Test getting specific position."""
        position = position_manager.open_position("AAPL", 100, 150.0)

        retrieved = position_manager.get_position("AAPL")
        assert retrieved is position

        nonexistent = position_manager.get_position("NONEXISTENT")
        assert nonexistent is None

    def test_get_all_positions(self, position_manager):
        """Test getting all positions."""
        aapl = position_manager.open_position("AAPL", 100, 150.0)
        googl = position_manager.open_position("GOOGL", 50, 2000.0)

        all_positions = position_manager.get_all_positions()

        assert len(all_positions) == 2
        assert aapl in all_positions
        assert googl in all_positions

    def test_get_all_positions_empty(self, position_manager):
        """Test getting all positions when empty."""
        all_positions = position_manager.get_all_positions()
        assert len(all_positions) == 0
        assert all_positions == []

    def test_get_total_unrealized_pnl(self, position_manager):
        """Test total unrealized PnL calculation."""
        # Open positions
        position_manager.open_position("AAPL", 100, 150.0)
        position_manager.open_position("GOOGL", 50, 2000.0)

        # Update prices
        position_manager.update_prices({"AAPL": 160.0, "GOOGL": 1900.0})  # +1000 PnL  # -5000 PnL

        total_pnl = position_manager.get_total_unrealized_pnl()
        assert total_pnl == -4000.0  # 1000 - 5000

    def test_get_total_unrealized_pnl_empty(self, position_manager):
        """Test total unrealized PnL when no positions."""
        total_pnl = position_manager.get_total_unrealized_pnl()
        assert total_pnl == 0.0

    def test_get_total_value(self, position_manager):
        """Test total position value calculation."""
        position_manager.open_position("AAPL", 100, 150.0)
        position_manager.open_position("GOOGL", 50, 2000.0)

        # Update prices
        position_manager.update_prices({"AAPL": 160.0, "GOOGL": 2100.0})

        total_value = position_manager.get_total_value()
        expected = (100 * 160.0) + (50 * 2100.0)  # 16000 + 105000
        assert total_value == expected

    def test_get_total_value_empty(self, position_manager):
        """Test total value when no positions."""
        total_value = position_manager.get_total_value()
        assert total_value == 0.0

    def test_complex_position_lifecycle(self, position_manager):
        """Test complex position management scenario."""
        # Open initial position
        position_manager.open_position("AAPL", 100, 150.0)

        # Add to position
        position_manager.open_position("AAPL", 50, 160.0)
        # Average price should be (100*150 + 50*160) / 150 = 153.33

        position = position_manager.get_position("AAPL")
        assert position.quantity == 150
        assert abs(position.entry_price - 153.33) < 0.01

        # Update price
        position_manager.update_prices({"AAPL": 170.0})

        # Partial close
        pnl1 = position_manager.close_position("AAPL", 175.0, quantity=50)
        # PnL: (175 - 153.33) * 50 = ~1083.5
        assert abs(pnl1 - 1083.5) < 1.0

        # Check remaining position
        position = position_manager.get_position("AAPL")
        assert position.quantity == 100
        assert abs(position.realized_pnl - 1083.5) < 1.0

        # Close remaining position
        pnl2 = position_manager.close_position("AAPL", 180.0)
        # PnL: (180 - 153.33) * 100 = ~2667
        assert abs(pnl2 - 2666.7) < 1.0

        # Position should be closed
        assert position_manager.get_position("AAPL") is None
        assert len(position_manager.closed_positions) == 1

        # Total realized PnL
        expected_total = 1083.5 + 2666.7
        assert abs(position_manager.total_realized_pnl - expected_total) < 1.0

    def test_short_position_management(self, position_manager):
        """Test managing short positions."""
        # Open short position
        position = position_manager.open_position("AAPL", -100, 150.0)

        assert position.quantity == -100

        # Price goes down - profit for short
        position_manager.update_prices({"AAPL": 140.0})
        assert position.unrealized_pnl == 1000.0  # (140 - 150) * (-100)
        assert position.is_profitable()

        # Price goes up - loss for short
        position_manager.update_prices({"AAPL": 160.0})
        assert position.unrealized_pnl == -1000.0  # (160 - 150) * (-100)
        assert not position.is_profitable()

        # Close short position (buy to cover)
        realized_pnl = position_manager.close_position("AAPL", 145.0)
        assert realized_pnl == 500.0  # (145 - 150) * (-100)

    def test_zero_quantity_position(self, position_manager):
        """Test handling zero quantity position."""
        position = position_manager.open_position("AAPL", 0, 150.0)

        assert position.quantity == 0

        position_manager.update_prices({"AAPL": 160.0})
        assert position.unrealized_pnl == 0.0  # No quantity, no PnL

        realized_pnl = position_manager.close_position("AAPL", 160.0)
        assert realized_pnl == 0.0
