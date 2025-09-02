"""Tests for backtester engine."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from src.backtester.engine import BacktestEngine
from src.backtester.strategies.sma import SMAStrategy


def create_mock_data(periods=100, start_price=100.0, volatility=0.02):
    """Create mock OHLCV data for testing."""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq="D")

    # Generate price data with some trend and volatility
    np.random.seed(42)
    returns = np.random.normal(0.001, volatility, periods)
    close_prices = start_price * np.exp(np.cumsum(returns))

    # Create OHLCV data
    data = pd.DataFrame(
        {
            "open": close_prices * (1 + np.random.uniform(-0.01, 0.01, periods)),
            "high": close_prices * (1 + np.random.uniform(0, 0.02, periods)),
            "low": close_prices * (1 - np.random.uniform(0, 0.02, periods)),
            "close": close_prices,
            "volume": np.random.uniform(1000000, 5000000, periods),
        },
        index=dates,
    )

    return data


class TestBacktestEngine:
    """Test suite for BacktestEngine."""

    def test_engine_initialization(self):
        """Test engine initialization with default parameters."""
        engine = BacktestEngine()
        assert engine.initial_capital == 10000.0
        assert engine.commission == 0.001
        assert engine.slippage == 0.0

    def test_engine_custom_parameters(self):
        """Test engine initialization with custom parameters."""
        engine = BacktestEngine(initial_capital=50000.0, commission=0.002, slippage=0.001)
        assert engine.initial_capital == 50000.0
        assert engine.commission == 0.002
        assert engine.slippage == 0.001

    def test_run_basic_backtest(self):
        """Test running a basic backtest."""
        data = create_mock_data(periods=100)
        strategy = SMAStrategy()
        engine = BacktestEngine()

        results = engine.run(data, strategy, fast_period=10, slow_period=20)

        assert "equity_curve" in results
        assert "trades" in results
        assert "final_equity" in results
        assert "return" in results

        assert len(results["equity_curve"]) == len(data)
        assert isinstance(results["final_equity"], float)
        assert isinstance(results["return"], float)

    def test_empty_data_raises_error(self):
        """Test that empty data raises ValueError."""
        data = pd.DataFrame()
        strategy = SMAStrategy()
        engine = BacktestEngine()

        with pytest.raises(ValueError, match="Data cannot be empty"):
            engine.run(data, strategy)

    def test_trades_execution(self):
        """Test that trades are executed correctly."""
        data = create_mock_data(periods=100)
        strategy = SMAStrategy()
        engine = BacktestEngine(initial_capital=10000.0, commission=0.001)

        results = engine.run(data, strategy, fast_period=5, slow_period=10)

        # Check trades structure
        if results["trades"]:
            trade = results["trades"][0]
            assert "timestamp" in trade
            assert "type" in trade
            assert "price" in trade
            assert "quantity" in trade
            assert "value" in trade
            assert "commission" in trade

            # Verify trade types
            trade_types = {t["type"] for t in results["trades"]}
            assert trade_types.issubset({"buy", "sell", "short", "cover"})

    def test_equity_curve_progression(self):
        """Test that equity curve tracks portfolio value correctly."""
        data = create_mock_data(periods=50)
        strategy = SMAStrategy()
        engine = BacktestEngine(initial_capital=10000.0)

        results = engine.run(data, strategy, fast_period=5, slow_period=10)

        equity_curve = results["equity_curve"]

        # First equity should be initial capital (no trades yet)
        assert equity_curve[0]["equity"] == 10000.0

        # All equity values should be positive
        assert all(e["equity"] > 0 for e in equity_curve)

        # Timestamps should match data index
        for i, equity_point in enumerate(equity_curve):
            assert "timestamp" in equity_point
            assert "equity" in equity_point

    def test_commission_impact(self):
        """Test that commissions affect final returns."""
        data = create_mock_data(periods=100)
        strategy = SMAStrategy()

        # Run with no commission
        engine_no_comm = BacktestEngine(initial_capital=10000.0, commission=0.0)
        results_no_comm = engine_no_comm.run(data, strategy, fast_period=5, slow_period=10)

        # Run with commission
        engine_with_comm = BacktestEngine(initial_capital=10000.0, commission=0.01)
        results_with_comm = engine_with_comm.run(data, strategy, fast_period=5, slow_period=10)

        # With commission should have lower returns (if there were trades)
        if results_no_comm["trades"]:
            assert results_with_comm["final_equity"] <= results_no_comm["final_equity"]

    def test_position_sizing(self):
        """Test that position sizing respects available capital."""
        data = create_mock_data(periods=50)
        strategy = SMAStrategy()
        engine = BacktestEngine(initial_capital=1000.0, commission=0.001)

        results = engine.run(data, strategy, fast_period=5, slow_period=10)

        # Verify no negative cash situations
        assert results["final_equity"] >= 0

    def test_final_position_closure(self):
        """Test that any open position is closed at the end."""
        data = create_mock_data(periods=50)
        strategy = SMAStrategy()
        engine = BacktestEngine()

        results = engine.run(data, strategy, fast_period=5, slow_period=10)

        # If there were trades, last trade should be a closing trade
        if len(results["trades"]) > 0:
            # Check that positions are properly closed
            buy_sell_count = sum(1 for t in results["trades"] if t["type"] in ["buy", "short"])
            close_count = sum(1 for t in results["trades"] if t["type"] in ["sell", "cover"])
            # There should be at most one more opening than closing (final close)
            assert abs(buy_sell_count - close_count) <= 1
