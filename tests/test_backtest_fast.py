"""Fast tests for backtest engine using mocks."""

from unittest.mock import patch

import pandas as pd


def test_backtest_engine_run_with_mock():
    """Test backtest engine run with mock data."""
    from src.backtest.engine import BacktestEngine
    from src.backtest.strategies.sma import SMAStrategy

    # Create mock data
    mock_data = pd.DataFrame(
        {
            "open": [100 + i for i in range(50)],
            "high": [101 + i for i in range(50)],
            "low": [99 + i for i in range(50)],
            "close": [100 + i for i in range(50)],
            "volume": [1000] * 50,
        }
    )

    engine = BacktestEngine(initial_capital=10000)
    strategy = SMAStrategy()

    with patch.object(engine, "_fetch_data", return_value=mock_data):
        results = engine.run(strategy=strategy, data=mock_data, fast_period=5, slow_period=10)

    assert "equity_curve" in results
    assert "trades" in results
    assert "final_capital" in results


def test_sma_strategy_signals():
    """Test SMA strategy signal generation."""
    from src.backtest.strategies.sma import SMAStrategy

    # Create test data with clear trend
    data = pd.DataFrame({"close": [100] * 10 + [110] * 10 + [120] * 10})

    strategy = SMAStrategy()
    signals = strategy.generate_signals(data, fast_period=3, slow_period=5)

    assert len(signals) == len(data)
    # Should have buy signal when fast crosses above slow
    assert 1 in signals  # At least one buy signal


def test_backtest_metrics_calculation():
    """Test backtest metrics calculation."""
    from src.backtest.metrics import calculate_metrics

    equity_curve = [10000, 10100, 10050, 10200, 10150, 10300]
    trades = [
        {"pnl": 100, "return": 0.01},
        {"pnl": -50, "return": -0.005},
        {"pnl": 150, "return": 0.015},
    ]

    metrics = calculate_metrics(equity_curve, trades)

    assert "total_return" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "win_rate" in metrics
    assert metrics["win_rate"] == 2 / 3  # 2 wins out of 3 trades


@patch("src.backtest.api.backtester")
def test_backtest_api_endpoint(mock_backtester, client):
    """Test backtest API endpoint with mocks."""
    mock_backtester.run_backtest.return_value = {
        "run_id": "test-123",
        "equity_curve": [[0, 10000], [1, 10100]],
        "trades": [],
        "stats": {"total_return": 0.01},
    }

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTC/USDT",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "strategy": "sma_cross",
            "params": {"fast_period": 10, "slow_period": 20},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "test-123"
    assert data["stats"]["total_return"] == 0.01
