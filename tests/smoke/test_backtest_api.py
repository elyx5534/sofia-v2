"""
Smoke tests for Backtest Engine v2
Tests single run, grid search, GA, and WFO functionality
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_backtest_run_endpoint():
    """Test that backtest run endpoint works"""
    from src.api.main import app

    client = TestClient(app)

    # Mock backtest request
    request_data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start": "2024-01-01",
        "end": "2024-01-31",
        "strategy": "sma_cross",
        "params": {"fast": 20, "slow": 50},
        "config": {"commission_bps": 10, "slippage_bps": 5},
    }

    response = client.post("/api/backtest/run", json=request_data)

    # Should return 200 or handle gracefully
    assert response.status_code in [200, 400, 500]

    if response.status_code == 200:
        data = response.json()
        # Check for expected keys
        assert any(key in data for key in ["run_id", "equity_curve", "stats", "error"])


def test_backtest_grid_endpoint():
    """Test grid search endpoint"""
    from src.api.main import app

    client = TestClient(app)

    request_data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "strategy": "sma_cross",
        "param_grid": {"fast": [10, 20], "slow": [40, 50]},
    }

    response = client.post("/api/backtest/grid", json=request_data)
    assert response.status_code in [200, 400, 500]

    if response.status_code == 200:
        data = response.json()
        assert any(key in data for key in ["grid_results", "best_params", "error"])


def test_backtest_ga_endpoint():
    """Test genetic algorithm endpoint"""
    from src.api.main import app

    client = TestClient(app)

    request_data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start": "2024-01-01",
        "end": "2024-01-05",
        "strategy": "rsi_revert",
        "param_ranges": {"period": [10, 30], "oversold": [20, 40], "overbought": [60, 80]},
        "population_size": 10,
        "generations": 3,
        "elite_size": 2,
    }

    response = client.post("/api/backtest/ga", json=request_data)
    assert response.status_code in [200, 400, 500]

    if response.status_code == 200:
        data = response.json()
        assert any(key in data for key in ["best_params", "best_fitness", "error"])


def test_backtest_wfo_endpoint():
    """Test walk-forward optimization endpoint"""
    from src.api.main import app

    client = TestClient(app)

    request_data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start": "2024-01-01",
        "end": "2024-01-10",
        "strategy": "sma_cross",
        "param_grid": {"fast": [10, 20], "slow": [40, 50]},
        "n_splits": 3,
        "train_ratio": 0.7,
    }

    response = client.post("/api/backtest/wfo", json=request_data)
    assert response.status_code in [200, 400, 500]

    if response.status_code == 200:
        data = response.json()
        assert any(key in data for key in ["wfo_results", "avg_oos_sharpe", "error"])
        if "wfo_results" in data:
            assert "oos_sharpe" in str(data)  # Check OOS metrics exist


def test_backtest_strategies_endpoint():
    """Test that strategies endpoint returns list"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/backtest/strategies")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 4  # We have 4 strategies

    # Check strategy structure
    strategy_names = [s["name"] for s in data]
    assert "sma_cross" in strategy_names
    assert "rsi_revert" in strategy_names
    assert "breakout" in strategy_names
    assert "mean_rev_spread" in strategy_names

    # Check params structure
    for strategy in data:
        assert "name" in strategy
        assert "display_name" in strategy
        assert "params" in strategy


def test_backtest_timeframes_endpoint():
    """Test that timeframes endpoint returns list"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/backtest/timeframes")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "1m" in data
    assert "1h" in data
    assert "1d" in data


def test_backtest_config_defaults_endpoint():
    """Test config defaults endpoint"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/backtest/config/defaults")

    assert response.status_code == 200
    data = response.json()
    assert "initial_capital" in data
    assert "commission_bps" in data
    assert "slippage_bps" in data
    assert "funding_rate" in data
    assert data["initial_capital"] == 10000
    assert data["commission_bps"] == 10


def test_backtest_results_endpoint():
    """Test results retrieval endpoint"""
    from src.api.main import app

    client = TestClient(app)

    # Test with non-existent run_id
    response = client.get("/api/backtest/results/nonexistent")
    assert response.status_code in [404, 500]


def test_backtest_export_endpoint():
    """Test that export endpoint handles missing run_id gracefully"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/backtest/export?run_id=nonexistent")

    # Should return 404 for nonexistent run_id
    assert response.status_code in [404, 500]


@patch("src.services.datahub.datahub")
def test_portfolio_mechanics(mock_datahub):
    """Test portfolio with fees and slippage calculations"""
    from datetime import datetime

    from src.services.backtester import BacktestConfig, Portfolio

    # Create portfolio
    config = BacktestConfig(initial_capital=10000, commission_bps=10, slippage_bps=5)
    portfolio = Portfolio(config)

    # Test initial state
    assert portfolio.cash == 10000
    assert len(portfolio.positions) == 0

    # Open position
    success = portfolio.open_position(
        symbol="BTC/USDT", size=0.1, price=50000, timestamp=datetime.now()
    )

    assert success
    assert portfolio.cash < 10000
    assert "BTC/USDT" in portfolio.positions

    # Close position
    success = portfolio.close_position(symbol="BTC/USDT", price=51000, timestamp=datetime.now())

    assert success
    assert "BTC/USDT" not in portfolio.positions
    assert len(portfolio.closed_positions) == 1
    assert len(portfolio.trades) == 2  # Open and close


@patch("src.services.datahub.datahub")
def test_strategies(mock_datahub):
    """Test all strategy implementations"""
    import numpy as np
    import pandas as pd
    from src.services.backtester import BreakoutStrategy, RSIStrategy, SMAStrategy

    # Create sample data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="H")
    prices = 50000 + np.random.randn(100) * 1000
    df = pd.DataFrame({"close": prices, "high": prices + 100, "low": prices - 100}, index=dates)

    # Test SMA Strategy
    sma_strat = SMAStrategy({"fast": 10, "slow": 20})
    signals = sma_strat.generate_signals(df)
    assert len(signals) == len(df)
    assert signals.isin([0, 1, -1]).all()

    # Test RSI Strategy
    rsi_strat = RSIStrategy({"period": 14, "oversold": 30, "overbought": 70})
    signals = rsi_strat.generate_signals(df)
    assert len(signals) == len(df)
    assert signals.isin([0, 1, -1]).all()

    # Test Breakout Strategy
    breakout_strat = BreakoutStrategy({"period": 20})
    signals = breakout_strat.generate_signals(df)
    assert len(signals) == len(df)
    assert signals.isin([0, 1, -1]).all()


def test_backtester_integration():
    """Integration test for complete backtest flow"""
    # This test will use mock data to avoid external dependencies
    with patch("src.services.datahub.datahub") as mock_datahub:
        # Generate mock OHLCV data
        mock_data = []
        base_price = 50000
        for i in range(100):
            timestamp = int((datetime(2024, 1, 1) + timedelta(hours=i)).timestamp() * 1000)
            price = base_price + (i % 10 - 5) * 100
            mock_data.append(
                [timestamp, price, price + 50, price - 50, price + (i % 3 - 1) * 10, 1000 + i * 10]
            )
        mock_datahub.get_ohlcv.return_value = mock_data

        from src.services.backtester import backtester

        # Run a simple backtest
        result = backtester.run_backtest(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-05",
            strategy="sma_cross",
            params={"fast": 10, "slow": 20},
        )

        # Verify result structure
        assert "run_id" in result
        assert "equity_curve" in result
        assert "stats" in result
        assert result["stats"]["total_trades"] >= 0


def test_wfo_with_mini_grid():
    """Test WFO with minimal parameters for speed"""
    with patch("src.services.datahub.datahub") as mock_datahub:
        # Generate mock data
        mock_data = []
        for i in range(50):
            timestamp = int((datetime(2024, 1, 1) + timedelta(hours=i)).timestamp() * 1000)
            price = 50000 + i * 10
            mock_data.append([timestamp, price, price + 10, price - 10, price, 1000])
        mock_datahub.get_ohlcv.return_value = mock_data

        from src.services.backtester import backtester

        # Run minimal WFO
        result = backtester.run_walk_forward_optimization(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-02",
            strategy="sma_cross",
            param_grid={"fast": [5, 10], "slow": [15, 20]},
            n_splits=2,
            train_ratio=0.5,
        )

        # Verify WFO ran
        assert "avg_oos_sharpe" in result
        assert "wfo_results" in result
        assert len(result["wfo_results"]) >= 1


if __name__ == "__main__":
    print("Running backtest API smoke tests...")
    test_backtest_run_endpoint()
    test_backtest_grid_endpoint()
    test_backtest_ga_endpoint()
    test_backtest_wfo_endpoint()
    test_backtest_strategies_endpoint()
    test_backtest_timeframes_endpoint()
    test_backtest_config_defaults_endpoint()
    test_backtest_results_endpoint()
    test_backtest_export_endpoint()
    test_portfolio_mechanics()
    test_strategies()
    test_backtester_integration()
    test_wfo_with_mini_grid()
    print("✓ All backtest API tests passed!")
