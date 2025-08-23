import math
from backtest.engine import run_dummy_backtest, sma_signals

def test_dummy_backtest_has_keys():
    metrics = run_dummy_backtest([100, 101, 102, 101, 103])
    assert set(metrics.keys()) == {"trades", "win_rate", "total_return"}

def test_dummy_backtest_values_reasonable():
    metrics = run_dummy_backtest([100, 101, 102, 101, 103])
    assert metrics["trades"] == 4
    assert 0.0 <= metrics["win_rate"] <= 1.0
    assert isinstance(metrics["total_return"], float)

def test_sma_signals_length():
    prices = [100, 101, 102, 101, 103, 104, 103]
    signals = sma_signals(prices, short=3, long=5)
    assert len(signals) == len(prices)