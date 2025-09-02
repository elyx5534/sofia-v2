"""Tests for the portfolio management module."""

import pytest
from src.core.portfolio import Asset, Portfolio


class TestAsset:
    """Test cases for Asset class."""

    def test_asset_creation(self):
        """Test asset creation with basic parameters."""
        asset = Asset(symbol="AAPL", quantity=100, average_cost=150.0, current_price=155.0)

        assert asset.symbol == "AAPL"
        assert asset.quantity == 100
        assert asset.average_cost == 150.0
        assert asset.current_price == 155.0
        assert asset.market_value == 0  # Default value
        assert asset.unrealized_pnl == 0  # Default value
        assert asset.realized_pnl == 0  # Default value
        assert asset.weight == 0  # Default value

    def test_update_price(self):
        """Test price update functionality."""
        asset = Asset(symbol="AAPL", quantity=100, average_cost=150.0, current_price=150.0)

        # Update price
        asset.update_price(160.0)

        assert asset.current_price == 160.0
        assert asset.market_value == 16000.0  # 100 * 160
        assert asset.unrealized_pnl == 1000.0  # (160 - 150) * 100

    def test_update_price_loss(self):
        """Test price update with loss."""
        asset = Asset(symbol="AAPL", quantity=100, average_cost=150.0, current_price=150.0)

        # Update price to lower value
        asset.update_price(140.0)

        assert asset.current_price == 140.0
        assert asset.market_value == 14000.0  # 100 * 140
        assert asset.unrealized_pnl == -1000.0  # (140 - 150) * 100


class TestPortfolio:
    """Test cases for Portfolio class."""

    @pytest.fixture
    def portfolio(self):
        """Create a test portfolio."""
        return Portfolio(id="test", cash_balance=100000.0, initial_capital=100000.0)

    def test_portfolio_creation(self, portfolio):
        """Test portfolio creation with default values."""
        assert portfolio.id == "test"
        assert portfolio.cash_balance == 100000.0
        assert portfolio.initial_capital == 100000.0
        assert len(portfolio.assets) == 0
        assert portfolio.total_value == 100000.0
        assert portfolio.total_pnl == 0.0
        assert portfolio.total_return == 0.0

    def test_add_asset_new_position(self, portfolio):
        """Test adding new asset to portfolio."""
        # Add AAPL position
        result = portfolio.add_asset("AAPL", 100, 150.0)

        assert result is True
        assert "AAPL" in portfolio.assets
        assert portfolio.cash_balance == 85000.0  # 100000 - (100 * 150)

        asset = portfolio.assets["AAPL"]
        assert asset.symbol == "AAPL"
        assert asset.quantity == 100
        assert asset.average_cost == 150.0
        assert asset.current_price == 150.0
        assert asset.market_value == 15000.0

    def test_add_asset_existing_position(self, portfolio):
        """Test adding to existing position."""
        # Add initial position
        portfolio.add_asset("AAPL", 100, 150.0)

        # Add more shares at different price
        result = portfolio.add_asset("AAPL", 50, 160.0)

        assert result is True
        assert len(portfolio.assets) == 1
        assert portfolio.cash_balance == 77000.0  # 100000 - 15000 - 8000

        asset = portfolio.assets["AAPL"]
        assert asset.quantity == 150
        # Average cost: (100*150 + 50*160) / 150 = 153.33
        assert abs(asset.average_cost - 153.33) < 0.01
        assert asset.current_price == 160.0
        assert asset.market_value == 24000.0  # 150 * 160

    def test_add_asset_insufficient_funds(self, portfolio):
        """Test adding asset with insufficient funds."""
        # Try to buy more than available cash
        result = portfolio.add_asset("AAPL", 1000, 150.0)  # Costs 150,000

        assert result is False
        assert len(portfolio.assets) == 0
        assert portfolio.cash_balance == 100000.0  # Unchanged

    def test_remove_asset_partial(self, portfolio):
        """Test partial asset removal."""
        # Add initial position
        portfolio.add_asset("AAPL", 100, 150.0)

        # Remove partial position at higher price
        realized_pnl = portfolio.remove_asset("AAPL", 30, 160.0)

        assert realized_pnl == 300.0  # (160 - 150) * 30
        assert "AAPL" in portfolio.assets

        asset = portfolio.assets["AAPL"]
        assert asset.quantity == 70
        assert asset.realized_pnl == 300.0
        assert portfolio.cash_balance == 89800.0  # 85000 + (30 * 160)

    def test_remove_asset_complete(self, portfolio):
        """Test complete asset removal."""
        # Add initial position
        portfolio.add_asset("AAPL", 100, 150.0)

        # Remove complete position
        realized_pnl = portfolio.remove_asset("AAPL", 100, 160.0)

        assert realized_pnl == 1000.0  # (160 - 150) * 100
        assert "AAPL" not in portfolio.assets
        assert portfolio.cash_balance == 101000.0  # 85000 + (100 * 160)

    def test_remove_asset_nonexistent(self, portfolio):
        """Test removing non-existent asset."""
        result = portfolio.remove_asset("AAPL", 100, 150.0)
        assert result is None

    def test_remove_asset_insufficient_quantity(self, portfolio):
        """Test removing more than available quantity."""
        portfolio.add_asset("AAPL", 100, 150.0)
        result = portfolio.remove_asset("AAPL", 200, 160.0)
        assert result is None

    def test_update_prices(self, portfolio):
        """Test updating multiple asset prices."""
        # Add multiple positions
        portfolio.add_asset("AAPL", 100, 150.0)
        portfolio.add_asset("GOOGL", 10, 2000.0)

        # Update prices
        prices = {"AAPL": 160.0, "GOOGL": 2100.0, "MSFT": 300.0}  # MSFT not in portfolio
        portfolio.update_prices(prices)

        assert portfolio.assets["AAPL"].current_price == 160.0
        assert portfolio.assets["GOOGL"].current_price == 2100.0
        assert portfolio.assets["AAPL"].market_value == 16000.0
        assert portfolio.assets["GOOGL"].market_value == 21000.0

    def test_portfolio_metrics_calculation(self, portfolio):
        """Test portfolio metrics calculation."""
        # Add positions
        portfolio.add_asset("AAPL", 100, 150.0)
        portfolio.add_asset("GOOGL", 10, 2000.0)

        # Update prices to create unrealized gains
        portfolio.update_prices({"AAPL": 160.0, "GOOGL": 2100.0})

        assert portfolio.total_value == 102000.0  # 65000 cash + 37000 assets
        assert portfolio.total_pnl == 2000.0  # 1000 + 1000 unrealized
        assert portfolio.total_return == 2.0  # 2% return

    def test_get_asset(self, portfolio):
        """Test getting specific asset."""
        portfolio.add_asset("AAPL", 100, 150.0)

        asset = portfolio.get_asset("AAPL")
        assert asset is not None
        assert asset.symbol == "AAPL"

        non_existent = portfolio.get_asset("MSFT")
        assert non_existent is None

    def test_get_allocation(self, portfolio):
        """Test portfolio allocation calculation."""
        # Add positions
        portfolio.add_asset("AAPL", 100, 150.0)  # 15000 value
        portfolio.add_asset("GOOGL", 10, 2000.0)  # 20000 value
        # Cash: 65000, Total: 100000

        allocation = portfolio.get_allocation()

        assert allocation["cash"] == 65.0  # 65%
        assert allocation["AAPL"] == 15.0  # 15%
        assert allocation["GOOGL"] == 20.0  # 20%

    def test_get_performance_metrics(self, portfolio):
        """Test performance metrics retrieval."""
        portfolio.add_asset("AAPL", 100, 150.0)
        portfolio.add_asset("GOOGL", 10, 2000.0)

        metrics = portfolio.get_performance_metrics()

        expected_metrics = {
            "total_value": 100000.0,
            "cash_balance": 65000.0,
            "assets_value": 35000.0,
            "total_pnl": 0.0,
            "total_return": 0.0,
            "num_positions": 2,
        }

        for key, value in expected_metrics.items():
            assert metrics[key] == value

    def test_rebalance_calculation(self, portfolio):
        """Test rebalancing trade calculation."""
        # Add initial positions
        portfolio.add_asset("AAPL", 100, 150.0)  # $15,000
        portfolio.add_asset("GOOGL", 10, 2000.0)  # $20,000
        # Total value: $100,000, Cash: $65,000

        # Target allocation: 50% AAPL, 30% GOOGL
        target_weights = {"AAPL": 50.0, "GOOGL": 30.0}
        prices = {"AAPL": 150.0, "GOOGL": 2000.0}

        trades = portfolio.rebalance(target_weights, prices)

        # Expected trades:
        # AAPL target: $50,000, current: $15,000, need: +$35,000 = +233.33 shares
        # GOOGL target: $30,000, current: $20,000, need: +$10,000 = +5 shares

        assert len(trades) == 2

        aapl_trade = next(trade for trade in trades if trade["symbol"] == "AAPL")
        assert aapl_trade["action"] == "buy"
        assert abs(aapl_trade["quantity"] - 233.33) < 0.01

        googl_trade = next(trade for trade in trades if trade["symbol"] == "GOOGL")
        assert googl_trade["action"] == "buy"
        assert googl_trade["quantity"] == 5.0

    def test_rebalance_sell_scenario(self, portfolio):
        """Test rebalancing with sell orders."""
        # Add large position
        portfolio.add_asset("AAPL", 600, 150.0)  # $90,000
        # Total value: $100,000, Cash: $10,000

        # Target: reduce AAPL to 30%
        target_weights = {"AAPL": 30.0}
        prices = {"AAPL": 150.0}

        trades = portfolio.rebalance(target_weights, prices)

        # Target: $30,000, current: $90,000, need: -$60,000 = -400 shares
        assert len(trades) == 1
        trade = trades[0]
        assert trade["symbol"] == "AAPL"
        assert trade["action"] == "sell"
        assert trade["quantity"] == 400.0

    def test_rebalance_small_differences_ignored(self, portfolio):
        """Test that small rebalancing differences are ignored."""
        portfolio.add_asset("AAPL", 100, 150.0)

        # Very small target difference (less than $10 threshold)
        target_weights = {"AAPL": 15.005}  # Difference is $5
        prices = {"AAPL": 150.0}

        trades = portfolio.rebalance(target_weights, prices)

        # Should be empty due to minimum threshold
        assert len(trades) == 0

    def test_zero_price_in_rebalance(self, portfolio):
        """Test rebalancing with zero price."""
        portfolio.add_asset("AAPL", 100, 150.0)

        target_weights = {"AAPL": 50.0}
        prices = {"AAPL": 0}  # Zero price

        trades = portfolio.rebalance(target_weights, prices)

        # Should not generate trades for zero price
        assert len(trades) == 0

    def test_asset_weights_calculation(self, portfolio):
        """Test asset weight calculations."""
        portfolio.add_asset("AAPL", 100, 100.0)  # $10,000
        portfolio.add_asset("GOOGL", 5, 2000.0)  # $10,000
        # Total: $80,000 cash + $20,000 assets = $100,000

        aapl_weight = portfolio.assets["AAPL"].weight
        googl_weight = portfolio.assets["GOOGL"].weight

        assert aapl_weight == 10.0  # 10%
        assert googl_weight == 10.0  # 10%

    def test_empty_portfolio_allocation(self):
        """Test allocation calculation for empty portfolio."""
        portfolio = Portfolio(cash_balance=0)
        allocation = portfolio.get_allocation()

        # Should handle division by zero gracefully
        assert allocation["cash"] == 0

    def test_portfolio_metrics_update_timestamp(self, portfolio):
        """Test that portfolio update timestamp changes."""
        initial_time = portfolio.updated_at

        # Add asset and check timestamp updated
        portfolio.add_asset("AAPL", 100, 150.0)

        assert portfolio.updated_at > initial_time
