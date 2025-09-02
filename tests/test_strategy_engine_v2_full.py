"""
Comprehensive tests for Strategy Engine v2
"""

import numpy as np
import pandas as pd
import pytest
from src.strategy_engine_v2.asset_allocator import AssetAllocator
from src.strategy_engine_v2.portfolio_manager import PortfolioManager


class TestPortfolioManager:
    """Test PortfolioManager functionality"""

    @pytest.fixture
    def portfolio_manager(self):
        """Create portfolio manager instance"""
        return PortfolioManager(initial_capital=10000, max_positions=10, risk_per_trade=0.02)

    def test_init(self, portfolio_manager):
        """Test portfolio manager initialization"""
        assert portfolio_manager.initial_capital == 10000
        assert portfolio_manager.max_positions == 10
        assert portfolio_manager.risk_per_trade == 0.02
        assert portfolio_manager.positions == {}
        assert portfolio_manager.balance == 10000

    def test_add_position(self, portfolio_manager):
        """Test adding a position"""
        position = portfolio_manager.add_position(symbol="BTC/USDT", amount=0.5, entry_price=50000)

        assert position is not None
        assert "BTC/USDT" in portfolio_manager.positions
        assert portfolio_manager.positions["BTC/USDT"]["amount"] == 0.5
        assert portfolio_manager.positions["BTC/USDT"]["entry_price"] == 50000

    def test_close_position(self, portfolio_manager):
        """Test closing a position"""
        # Add position first
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)

        # Close position
        result = portfolio_manager.close_position("BTC/USDT", 55000)

        assert result is not None
        assert "BTC/USDT" not in portfolio_manager.positions
        assert result["profit"] > 0

    def test_update_position(self, portfolio_manager):
        """Test updating a position"""
        # Add position
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)

        # Update position
        updated = portfolio_manager.update_position("BTC/USDT", current_price=52000)

        assert updated is not None
        assert updated["unrealized_pnl"] > 0

    def test_calculate_portfolio_value(self, portfolio_manager):
        """Test portfolio value calculation"""
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)
        portfolio_manager.add_position("ETH/USDT", 10, 3000)

        prices = {"BTC/USDT": 52000, "ETH/USDT": 3200}

        value = portfolio_manager.calculate_portfolio_value(prices)
        assert value > portfolio_manager.initial_capital

    def test_get_position_size(self, portfolio_manager):
        """Test position size calculation"""
        size = portfolio_manager.get_position_size(symbol="BTC/USDT", price=50000, stop_loss=48000)

        assert size > 0
        assert size <= portfolio_manager.balance * portfolio_manager.risk_per_trade / 2000

    def test_rebalance_portfolio(self, portfolio_manager):
        """Test portfolio rebalancing"""
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)
        portfolio_manager.add_position("ETH/USDT", 10, 3000)

        target_weights = {"BTC/USDT": 0.6, "ETH/USDT": 0.4}

        prices = {"BTC/USDT": 52000, "ETH/USDT": 3200}

        trades = portfolio_manager.rebalance(target_weights, prices)
        assert trades is not None
        assert len(trades) > 0

    def test_calculate_metrics(self, portfolio_manager):
        """Test portfolio metrics calculation"""
        # Add some positions and trades
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)
        portfolio_manager.close_position("BTC/USDT", 52000)

        metrics = portfolio_manager.calculate_metrics()
        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics

    def test_risk_management(self, portfolio_manager):
        """Test risk management features"""
        # Test max positions limit
        for i in range(12):
            portfolio_manager.add_position(f"COIN{i}/USDT", 100, 100)

        assert len(portfolio_manager.positions) <= portfolio_manager.max_positions

    def test_position_tracking(self, portfolio_manager):
        """Test position tracking and history"""
        # Add and close multiple positions
        portfolio_manager.add_position("BTC/USDT", 0.5, 50000)
        portfolio_manager.close_position("BTC/USDT", 52000)

        portfolio_manager.add_position("ETH/USDT", 10, 3000)
        portfolio_manager.close_position("ETH/USDT", 2900)

        history = portfolio_manager.get_trade_history()
        assert len(history) == 2
        assert history[0]["profit"] > 0
        assert history[1]["profit"] < 0


class TestAssetAllocator:
    """Test AssetAllocator functionality"""

    @pytest.fixture
    def allocator(self):
        """Create asset allocator instance"""
        return AssetAllocator(assets=["BTC", "ETH", "SOL"], total_capital=100000)

    def test_init(self, allocator):
        """Test allocator initialization"""
        assert allocator.assets == ["BTC", "ETH", "SOL"]
        assert allocator.total_capital == 100000
        assert allocator.allocations == {}

    def test_equal_weight_allocation(self, allocator):
        """Test equal weight allocation strategy"""
        allocations = allocator.equal_weight_allocation()

        assert len(allocations) == 3
        assert all(abs(w - 1 / 3) < 0.01 for w in allocations.values())
        assert abs(sum(allocations.values()) - 1.0) < 0.01

    def test_risk_parity_allocation(self, allocator):
        """Test risk parity allocation"""
        volatilities = {"BTC": 0.8, "ETH": 0.9, "SOL": 1.2}

        allocations = allocator.risk_parity_allocation(volatilities)

        assert len(allocations) == 3
        assert abs(sum(allocations.values()) - 1.0) < 0.01
        # Lower volatility should get higher allocation
        assert allocations["BTC"] > allocations["SOL"]

    def test_momentum_allocation(self, allocator):
        """Test momentum-based allocation"""
        returns = {"BTC": 0.15, "ETH": 0.25, "SOL": -0.05}

        allocations = allocator.momentum_allocation(returns)

        assert len(allocations) == 3
        assert allocations["ETH"] > allocations["BTC"]
        assert allocations["SOL"] == 0 or allocations["SOL"] < allocations["BTC"]

    def test_mean_variance_optimization(self, allocator):
        """Test mean-variance optimization"""
        returns = pd.DataFrame(
            {
                "BTC": np.random.randn(100) * 0.02 + 0.001,
                "ETH": np.random.randn(100) * 0.025 + 0.0008,
                "SOL": np.random.randn(100) * 0.03 + 0.0012,
            }
        )

        allocations = allocator.mean_variance_optimization(returns, target_return=0.001)

        assert len(allocations) == 3
        assert abs(sum(allocations.values()) - 1.0) < 0.01
        assert all(w >= 0 for w in allocations.values())

    def test_black_litterman_allocation(self, allocator):
        """Test Black-Litterman allocation"""
        market_caps = {"BTC": 1000000000000, "ETH": 400000000000, "SOL": 50000000000}

        views = {"BTC": 0.10, "ETH": 0.15}  # 10% expected return  # 15% expected return

        allocations = allocator.black_litterman_allocation(market_caps, views)

        assert len(allocations) == 3
        assert abs(sum(allocations.values()) - 1.0) < 0.01

    def test_kelly_criterion_allocation(self, allocator):
        """Test Kelly Criterion allocation"""
        win_probabilities = {"BTC": 0.55, "ETH": 0.60, "SOL": 0.45}

        win_loss_ratios = {"BTC": 1.5, "ETH": 1.8, "SOL": 1.2}

        allocations = allocator.kelly_criterion_allocation(
            win_probabilities, win_loss_ratios, max_leverage=1.0
        )

        assert len(allocations) == 3
        assert sum(allocations.values()) <= 1.0
        # Higher edge should get higher allocation
        assert allocations["ETH"] >= allocations["SOL"]

    def test_correlation_adjusted_allocation(self, allocator):
        """Test correlation-adjusted allocation"""
        base_allocations = {"BTC": 0.4, "ETH": 0.4, "SOL": 0.2}

        correlations = pd.DataFrame(
            {"BTC": [1.0, 0.7, 0.5], "ETH": [0.7, 1.0, 0.6], "SOL": [0.5, 0.6, 1.0]},
            index=["BTC", "ETH", "SOL"],
        )

        adjusted = allocator.adjust_for_correlation(base_allocations, correlations)

        assert len(adjusted) == 3
        assert abs(sum(adjusted.values()) - 1.0) < 0.01

    def test_dynamic_rebalancing(self, allocator):
        """Test dynamic rebalancing logic"""
        current_allocations = {"BTC": 0.35, "ETH": 0.40, "SOL": 0.25}

        target_allocations = {"BTC": 0.40, "ETH": 0.35, "SOL": 0.25}

        trades = allocator.calculate_rebalancing_trades(
            current_allocations, target_allocations, threshold=0.02
        )

        assert "BTC" in trades
        assert "ETH" in trades
        assert trades["SOL"] == 0  # No rebalancing needed

    def test_allocation_constraints(self, allocator):
        """Test allocation with constraints"""
        min_allocations = {"BTC": 0.2, "ETH": 0.1, "SOL": 0.05}

        max_allocations = {"BTC": 0.5, "ETH": 0.4, "SOL": 0.3}

        allocations = allocator.constrained_allocation(min_allocations, max_allocations)

        assert all(
            min_allocations[asset] <= allocations[asset] <= max_allocations[asset]
            for asset in allocator.assets
        )
        assert abs(sum(allocations.values()) - 1.0) < 0.01
