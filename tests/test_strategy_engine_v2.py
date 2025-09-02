"""
Tests for Strategy Engine v2
Testing portfolio manager and asset allocator
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from src.strategy_engine_v2.asset_allocator import AssetAllocator

# Import strategy engine v2 modules
from src.strategy_engine_v2.portfolio_manager import PortfolioManager


class TestPortfolioManager:
    """Test PortfolioManager functionality"""

    @pytest.fixture
    def portfolio_manager(self):
        """Create portfolio manager instance"""
        return PortfolioManager(initial_capital=10000)

    def test_manager_initialization(self, portfolio_manager):
        """Test manager initialization"""
        assert portfolio_manager is not None
        assert portfolio_manager.initial_capital == 10000
        assert portfolio_manager.current_capital == 10000
        assert len(portfolio_manager.positions) == 0

    def test_add_position(self, portfolio_manager):
        """Test adding position"""
        position = Position(
            symbol="BTC/USDT", quantity=0.5, entry_price=50000, position_type="long"
        )

        portfolio_manager.add_position(position)
        assert len(portfolio_manager.positions) == 1
        assert portfolio_manager.positions["BTC/USDT"] == position

    def test_close_position(self, portfolio_manager):
        """Test closing position"""
        position = Position(
            symbol="BTC/USDT", quantity=0.5, entry_price=50000, position_type="long"
        )

        portfolio_manager.add_position(position)
        trade = portfolio_manager.close_position("BTC/USDT", exit_price=55000)

        assert trade is not None
        assert trade.profit == 2500  # 0.5 * (55000 - 50000)
        assert len(portfolio_manager.positions) == 0

    def test_calculate_portfolio_value(self, portfolio_manager):
        """Test portfolio value calculation"""
        position1 = Position(
            symbol="BTC/USDT", quantity=0.5, entry_price=50000, position_type="long"
        )
        position2 = Position(symbol="ETH/USDT", quantity=10, entry_price=3000, position_type="long")

        portfolio_manager.add_position(position1)
        portfolio_manager.add_position(position2)

        current_prices = {"BTC/USDT": 52000, "ETH/USDT": 3100}

        value = portfolio_manager.calculate_portfolio_value(current_prices)
        expected = 10000 + (0.5 * 2000) + (10 * 100)  # Initial + profits
        assert value == expected

    def test_calculate_metrics(self, portfolio_manager):
        """Test portfolio metrics calculation"""
        # Add some trades
        trades = [
            Trade("BTC/USDT", "buy", 0.5, 50000, datetime.now()),
            Trade("BTC/USDT", "sell", 0.5, 52000, datetime.now()),
            Trade("ETH/USDT", "buy", 10, 3000, datetime.now()),
            Trade("ETH/USDT", "sell", 10, 2900, datetime.now()),
        ]

        for trade in trades:
            portfolio_manager.add_trade(trade)

        metrics = portfolio_manager.calculate_metrics()

        assert metrics is not None
        assert hasattr(metrics, "total_trades")
        assert hasattr(metrics, "win_rate")
        assert hasattr(metrics, "total_profit")
        assert metrics.total_trades == 4

    def test_risk_management(self, portfolio_manager):
        """Test risk management features"""
        portfolio_manager.max_position_size = 0.2  # 20% max per position
        portfolio_manager.stop_loss = 0.05  # 5% stop loss

        # Test position size limit
        can_add = portfolio_manager.can_add_position(
            symbol="BTC/USDT",
            position_value=3000,  # 30% of portfolio
        )
        assert can_add is False

        can_add = portfolio_manager.can_add_position(
            symbol="ETH/USDT",
            position_value=1500,  # 15% of portfolio
        )
        assert can_add is True

    def test_portfolio_rebalancing(self, portfolio_manager):
        """Test portfolio rebalancing"""
        target_allocation = {"BTC/USDT": 0.5, "ETH/USDT": 0.3, "SOL/USDT": 0.2}

        current_prices = {"BTC/USDT": 50000, "ETH/USDT": 3000, "SOL/USDT": 100}

        rebalance_orders = portfolio_manager.rebalance(target_allocation, current_prices)

        assert rebalance_orders is not None
        assert len(rebalance_orders) <= 3


class TestAssetAllocator:
    """Test AssetAllocator functionality"""

    @pytest.fixture
    def asset_allocator(self):
        """Create asset allocator instance"""
        return AssetAllocator(
            strategy=AllocationStrategy.MEAN_VARIANCE, objective=OptimizationObjective.MAX_SHARPE
        )

    def test_allocator_initialization(self, asset_allocator):
        """Test allocator initialization"""
        assert asset_allocator is not None
        assert asset_allocator.strategy == AllocationStrategy.MEAN_VARIANCE
        assert asset_allocator.objective == OptimizationObjective.MAX_SHARPE

    def test_calculate_optimal_weights(self, asset_allocator):
        """Test optimal weight calculation"""
        returns_data = pd.DataFrame(
            {
                "BTC": [0.02, 0.01, -0.01, 0.03, 0.02],
                "ETH": [0.03, 0.02, -0.02, 0.04, 0.01],
                "SOL": [0.05, -0.01, -0.03, 0.06, 0.02],
            }
        )

        weights = asset_allocator.calculate_optimal_weights(returns_data)

        assert weights is not None
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01  # Sum to 1
        assert all(0 <= w <= 1 for w in weights.values())

    def test_risk_parity_allocation(self):
        """Test risk parity allocation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.RISK_PARITY, objective=OptimizationObjective.MIN_RISK
        )

        volatilities = {"BTC": 0.8, "ETH": 0.6, "SOL": 1.0}

        weights = allocator.risk_parity_allocation(volatilities)

        assert weights is not None
        assert len(weights) == 3
        # Risk parity: lower vol assets get higher weight
        assert weights["ETH"] > weights["BTC"] > weights["SOL"]

    def test_equal_weight_allocation(self):
        """Test equal weight allocation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.EQUAL_WEIGHT, objective=OptimizationObjective.MAX_SHARPE
        )

        assets = ["BTC", "ETH", "SOL", "AVAX"]
        weights = allocator.equal_weight_allocation(assets)

        assert weights is not None
        assert len(weights) == 4
        assert all(w == 0.25 for w in weights.values())

    def test_momentum_allocation(self):
        """Test momentum-based allocation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.MOMENTUM, objective=OptimizationObjective.MAX_RETURN
        )

        momentum_scores = {"BTC": 0.8, "ETH": 0.6, "SOL": 0.9, "AVAX": 0.4}

        weights = allocator.momentum_allocation(momentum_scores)

        assert weights is not None
        assert weights["SOL"] > weights["BTC"] > weights["ETH"] > weights["AVAX"]

    def test_apply_constraints(self, asset_allocator):
        """Test applying allocation constraints"""
        weights = {"BTC": 0.6, "ETH": 0.3, "SOL": 0.1}

        constraints = {"max_weight": 0.4, "min_weight": 0.15}

        constrained = asset_allocator.apply_constraints(weights, constraints)

        assert constrained["BTC"] <= 0.4
        assert constrained["SOL"] >= 0.15
        assert abs(sum(constrained.values()) - 1.0) < 0.01

    def test_calculate_allocation_metrics(self, asset_allocator):
        """Test allocation metrics calculation"""
        weights = {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2}

        returns_data = pd.DataFrame(
            {
                "BTC": [0.02, 0.01, -0.01, 0.03],
                "ETH": [0.03, 0.02, -0.02, 0.04],
                "SOL": [0.05, -0.01, -0.03, 0.06],
            }
        )

        metrics = asset_allocator.calculate_metrics(weights, returns_data)

        assert metrics is not None
        assert "expected_return" in metrics
        assert "volatility" in metrics
        assert "sharpe_ratio" in metrics


class TestPortfolioOptimization:
    """Test portfolio optimization features"""

    def test_efficient_frontier(self):
        """Test efficient frontier calculation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.MEAN_VARIANCE, objective=OptimizationObjective.MAX_SHARPE
        )

        returns_data = pd.DataFrame(
            np.random.randn(100, 4) * 0.01, columns=["BTC", "ETH", "SOL", "AVAX"]
        )

        frontier = allocator.calculate_efficient_frontier(returns_data)

        assert frontier is not None
        assert len(frontier) > 0
        assert all("return" in point and "risk" in point for point in frontier)

    def test_black_litterman_allocation(self):
        """Test Black-Litterman allocation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.BLACK_LITTERMAN, objective=OptimizationObjective.MAX_SHARPE
        )

        market_caps = {"BTC": 1000000000000, "ETH": 400000000000, "SOL": 50000000000}

        views = {
            "BTC": 0.10,  # 10% expected return
            "ETH": 0.15,  # 15% expected return
            "SOL": 0.20,  # 20% expected return
        }

        weights = allocator.black_litterman_allocation(market_caps, views)

        assert weights is not None
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_kelly_criterion_allocation(self):
        """Test Kelly Criterion allocation"""
        allocator = AssetAllocator(
            strategy=AllocationStrategy.KELLY_CRITERION, objective=OptimizationObjective.MAX_GROWTH
        )

        win_probabilities = {"BTC": 0.6, "ETH": 0.55, "SOL": 0.65}

        avg_win_loss_ratios = {"BTC": 1.5, "ETH": 1.8, "SOL": 2.0}

        weights = allocator.kelly_criterion_allocation(win_probabilities, avg_win_loss_ratios)

        assert weights is not None
        assert all(0 <= w <= 1 for w in weights.values())
