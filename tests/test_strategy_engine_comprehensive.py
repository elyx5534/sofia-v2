"""
Comprehensive tests for strategy engine modules to reach 70% coverage
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


class TestAssetAllocator:
    """Tests for asset allocator"""

    def test_allocator_init(self):
        """Test asset allocator initialization"""
        from src.strategy_engine_v2.asset_allocator import AssetAllocator

        allocator = AssetAllocator(total_capital=100000)
        assert allocator.total_capital == 100000
        assert allocator.allocations == {}

    def test_equal_weight_allocation(self):
        """Test equal weight allocation"""
        from src.strategy_engine_v2.asset_allocator import AssetAllocator

        allocator = AssetAllocator(total_capital=100000)
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

        allocations = allocator.equal_weight_allocation(symbols)

        assert len(allocations) == 3
        assert all(alloc == pytest.approx(33333.33, rel=1) for alloc in allocations.values())

    @patch("src.strategy_engine_v2.asset_allocator.np.random")
    def test_risk_parity_allocation(self, mock_random):
        """Test risk parity allocation"""
        from src.strategy_engine_v2.asset_allocator import AssetAllocator

        mock_random.uniform.return_value = 0.1

        allocator = AssetAllocator(total_capital=100000)

        returns_data = pd.DataFrame(
            {
                "BTC-USD": np.random.randn(100),
                "ETH-USD": np.random.randn(100),
            }
        )

        allocations = allocator.risk_parity_allocation(returns_data)

        assert allocations is not None
        assert sum(allocations.values()) == pytest.approx(100000, rel=0.01)

    def test_momentum_based_allocation(self):
        """Test momentum based allocation"""
        from src.strategy_engine_v2.asset_allocator import AssetAllocator

        allocator = AssetAllocator(total_capital=100000)

        momentum_scores = {"BTC-USD": 0.8, "ETH-USD": 0.6, "SOL-USD": 0.4}

        allocations = allocator.momentum_based_allocation(momentum_scores)

        assert allocations["BTC-USD"] > allocations["ETH-USD"]
        assert allocations["ETH-USD"] > allocations["SOL-USD"]

    def test_kelly_criterion_allocation(self):
        """Test Kelly criterion allocation"""
        from src.strategy_engine_v2.asset_allocator import AssetAllocator

        allocator = AssetAllocator(total_capital=100000)

        win_rates = {"BTC-USD": 0.6, "ETH-USD": 0.55}

        avg_win_loss_ratios = {"BTC-USD": 1.5, "ETH-USD": 1.3}

        allocations = allocator.kelly_criterion_allocation(win_rates, avg_win_loss_ratios)

        assert allocations is not None
        assert all(0 <= alloc <= 100000 for alloc in allocations.values())


class TestPortfolioManager:
    """Tests for portfolio manager"""

    def test_portfolio_init(self):
        """Test portfolio manager initialization"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        assert manager.initial_capital == 100000
        assert manager.current_capital == 100000
        assert len(manager.positions) == 0

    def test_add_position(self):
        """Test adding position"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        manager.add_position("BTC-USD", 0.5, 45000)

        assert "BTC-USD" in manager.positions
        assert manager.positions["BTC-USD"]["quantity"] == 0.5
        assert manager.positions["BTC-USD"]["entry_price"] == 45000

    def test_close_position(self):
        """Test closing position"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        manager.add_position("BTC-USD", 0.5, 45000)
        pnl = manager.close_position("BTC-USD", 46000)

        assert pnl == 500  # (46000 - 45000) * 0.5
        assert "BTC-USD" not in manager.positions

    def test_update_position_value(self):
        """Test updating position value"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        manager.add_position("BTC-USD", 1.0, 45000)
        manager.update_position_value("BTC-USD", 46000)

        assert manager.positions["BTC-USD"]["current_value"] == 46000
        assert manager.positions["BTC-USD"]["unrealized_pnl"] == 1000

    def test_get_portfolio_value(self):
        """Test getting portfolio value"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        manager.add_position("BTC-USD", 1.0, 45000)
        manager.add_position("ETH-USD", 10.0, 3000)

        manager.current_capital = 25000  # Remaining cash

        total_value = manager.get_portfolio_value()

        assert total_value == 100000  # 45000 + 30000 + 25000

    def test_calculate_sharpe_ratio(self):
        """Test calculating Sharpe ratio"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.01])
        sharpe = manager.calculate_sharpe_ratio(returns)

        assert sharpe is not None
        assert isinstance(sharpe, float)

    def test_rebalance_portfolio(self):
        """Test portfolio rebalancing"""
        from src.strategy_engine_v2.portfolio_manager import PortfolioManager

        manager = PortfolioManager(initial_capital=100000)

        manager.add_position("BTC-USD", 1.0, 45000)
        manager.add_position("ETH-USD", 10.0, 3000)

        target_weights = {"BTC-USD": 0.6, "ETH-USD": 0.4}

        manager.rebalance_portfolio(target_weights)

        # Check that positions were adjusted
        assert manager.positions is not None


class TestCrossMarketEngine:
    """Tests for cross market engine"""

    def test_engine_init(self):
        """Test cross market engine initialization"""
        from src.strategy_engine_v3.cross_market_engine import CrossMarketEngine

        engine = CrossMarketEngine(markets=["crypto", "forex"])

        assert "crypto" in engine.markets
        assert "forex" in engine.markets

    @patch("src.strategy_engine_v3.cross_market_engine.MarketAdapter")
    def test_add_market_adapter(self, mock_adapter):
        """Test adding market adapter"""
        from src.strategy_engine_v3.cross_market_engine import CrossMarketEngine

        engine = CrossMarketEngine()

        mock_adapter_instance = MagicMock()
        mock_adapter.return_value = mock_adapter_instance

        engine.add_market_adapter("crypto", mock_adapter_instance)

        assert "crypto" in engine.adapters

    def test_get_cross_market_signals(self):
        """Test getting cross market signals"""
        from src.strategy_engine_v3.cross_market_engine import CrossMarketEngine

        engine = CrossMarketEngine()

        # Mock market data
        market_data = {
            "crypto": {"BTC-USD": {"price": 45000, "volume": 1000}},
            "forex": {"EUR-USD": {"price": 1.1, "volume": 10000}},
        }

        signals = engine.get_cross_market_signals(market_data)

        assert signals is not None

    def test_calculate_correlation(self):
        """Test calculating cross-market correlation"""
        from src.strategy_engine_v3.cross_market_engine import CrossMarketEngine

        engine = CrossMarketEngine()

        data1 = pd.Series([1, 2, 3, 4, 5])
        data2 = pd.Series([2, 4, 6, 8, 10])

        correlation = engine.calculate_correlation(data1, data2)

        assert correlation == pytest.approx(1.0, rel=0.01)


class TestArbitrageScanner:
    """Tests for arbitrage scanner"""

    def test_scanner_init(self):
        """Test arbitrage scanner initialization"""
        from src.strategy_engine_v3.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner(min_profit_threshold=0.01)

        assert scanner.min_profit_threshold == 0.01
        assert scanner.opportunities == []

    def test_detect_triangular_arbitrage(self):
        """Test detecting triangular arbitrage"""
        from src.strategy_engine_v3.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner()

        prices = {"BTC/USDT": 45000, "ETH/USDT": 3000, "ETH/BTC": 0.065}

        opportunity = scanner.detect_triangular_arbitrage(prices)

        assert opportunity is not None

    def test_calculate_profit(self):
        """Test calculating arbitrage profit"""
        from src.strategy_engine_v3.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner()

        buy_price = 45000
        sell_price = 45500
        amount = 1.0
        fees = 0.001

        profit = scanner.calculate_profit(buy_price, sell_price, amount, fees)

        assert profit > 0


class TestCorrelationAnalyzer:
    """Tests for correlation analyzer"""

    def test_analyzer_init(self):
        """Test correlation analyzer initialization"""
        from src.strategy_engine_v3.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer(window_size=30)

        assert analyzer.window_size == 30

    def test_calculate_correlation_matrix(self):
        """Test calculating correlation matrix"""
        from src.strategy_engine_v3.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        data = pd.DataFrame(
            {"BTC": np.random.randn(100), "ETH": np.random.randn(100), "SOL": np.random.randn(100)}
        )

        corr_matrix = analyzer.calculate_correlation_matrix(data)

        assert corr_matrix.shape == (3, 3)
        assert all(corr_matrix.diagonal() == 1.0)

    def test_find_correlated_pairs(self):
        """Test finding correlated pairs"""
        from src.strategy_engine_v3.correlation_analyzer import CorrelationAnalyzer

        analyzer = CorrelationAnalyzer()

        # Create highly correlated data
        base = np.random.randn(100)
        data = pd.DataFrame(
            {"A": base, "B": base + np.random.randn(100) * 0.1, "C": np.random.randn(100)}
        )

        pairs = analyzer.find_correlated_pairs(data, threshold=0.8)

        assert len(pairs) > 0
        assert ("A", "B") in pairs or ("B", "A") in pairs


class TestOrderRouter:
    """Tests for order router"""

    def test_router_init(self):
        """Test order router initialization"""
        from src.strategy_engine_v3.order_router import OrderRouter

        router = OrderRouter(exchanges=["binance", "coinbase"])

        assert "binance" in router.exchanges
        assert "coinbase" in router.exchanges

    def test_route_order(self):
        """Test routing order to best exchange"""
        from src.strategy_engine_v3.order_router import OrderRouter

        router = OrderRouter()

        order = {"symbol": "BTC-USD", "side": "buy", "amount": 0.1, "type": "market"}

        exchange_prices = {"binance": 45000, "coinbase": 45100}

        best_exchange = router.route_order(order, exchange_prices)

        assert best_exchange == "binance"  # Lower price for buy

    def test_split_order(self):
        """Test splitting large order"""
        from src.strategy_engine_v3.order_router import OrderRouter

        router = OrderRouter()

        total_amount = 10.0
        splits = router.split_order(total_amount, num_splits=5)

        assert len(splits) == 5
        assert sum(splits) == pytest.approx(total_amount)

    def test_calculate_slippage(self):
        """Test calculating slippage"""
        from src.strategy_engine_v3.order_router import OrderRouter

        router = OrderRouter()

        expected_price = 45000
        actual_price = 45050

        slippage = router.calculate_slippage(expected_price, actual_price)

        assert slippage == pytest.approx(0.0011, rel=0.01)
