"""Tests for Trend following strategy"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sofia_strategies.base import SignalType
from sofia_strategies.trend import TrendStrategy


@pytest.fixture
def trend_config():
    """Default trend strategy configuration"""
    return {
        "fast_ma": 20,
        "slow_ma": 60,
        "vol_filter": 14,
        "stop_pct": 2.0,
        "trailing_pct": 1.5,
        "max_position": 100.0,
        "atr_multiplier": 2.0,
        "regime_threshold": 0.02,
        "kelly_fraction": 0.25,
        "min_win_prob": 0.45,
    }


@pytest.fixture
def trending_data():
    """Generate trending price data for testing"""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=200, freq="1h")

    # Create uptrend then downtrend
    trend1 = np.linspace(50000, 52000, 100)  # Uptrend
    trend2 = np.linspace(52000, 51000, 100)  # Downtrend
    trend = np.concatenate([trend1, trend2])

    # Add realistic noise
    noise = np.random.normal(0, 100, 200)
    prices = trend + noise

    # Generate OHLCV data
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * 0.999,
            "high": prices * 1.001,
            "low": prices * 0.998,
            "close": prices,
            "volume": np.random.uniform(100, 1000, 200),
        }
    )


def test_trend_initialization(trend_config, trending_data):
    """Test trend strategy initialization"""
    strategy = TrendStrategy(trend_config)
    strategy.initialize("BTCUSDT", trending_data)

    assert strategy.symbol == "BTCUSDT"
    assert len(strategy.price_history) > 0
    assert strategy.fast_ma_value > 0
    assert strategy.slow_ma_value > 0
    assert strategy.atr_value > 0
    assert strategy.regime in ["bullish", "bearish", "neutral"]


def test_ma_calculation(trend_config):
    """Test moving average calculations"""
    strategy = TrendStrategy(trend_config)

    # Create simple price series
    prices = [100] * 20 + [110] * 20  # Step change
    strategy.price_history = prices

    strategy._update_indicators()

    assert strategy.fast_ma_value > 100
    assert strategy.fast_ma_value < 110
    # Fast MA should be closer to recent prices
    assert strategy.fast_ma_value > strategy.slow_ma_value


def test_regime_detection(trend_config):
    """Test market regime detection"""
    strategy = TrendStrategy(trend_config)

    # Bullish regime
    strategy.fast_ma_value = 51000
    strategy.slow_ma_value = 50000
    strategy.volume_history = [100] * 20 + [150] * 5  # Volume increasing
    strategy._detect_regime()
    assert strategy.regime == "bullish"
    assert strategy.signal_strength > 0

    # Bearish regime
    strategy.fast_ma_value = 49000
    strategy.slow_ma_value = 50000
    strategy._detect_regime()
    assert strategy.regime == "bearish"

    # Neutral regime
    strategy.fast_ma_value = 50000
    strategy.slow_ma_value = 49990
    strategy._detect_regime()
    assert strategy.regime == "neutral"
    assert strategy.signal_strength == 0


def test_position_sizing(trend_config):
    """Test Kelly Criterion position sizing"""
    strategy = TrendStrategy(trend_config)
    strategy.atr_value = 500
    strategy.win_count = 6
    strategy.loss_count = 4
    strategy.signal_strength = 0.8

    size = strategy._calculate_position_size(50000)

    assert size > 0
    assert size <= trend_config["max_position"] / 50000

    # Test with low win rate
    strategy.win_count = 3
    strategy.loss_count = 7
    size_low_win = strategy._calculate_position_size(50000)
    assert size_low_win < size or size_low_win == 0


def test_stop_calculation(trend_config):
    """Test stop loss and trailing stop calculation"""
    strategy = TrendStrategy(trend_config)
    strategy.atr_value = 500

    # Test long position stops
    stop_loss, trailing_stop = strategy._calculate_stops(50000, SignalType.BUY)
    assert stop_loss < 50000
    assert trailing_stop < 50000
    assert trailing_stop > stop_loss

    # Test short position stops
    stop_loss, trailing_stop = strategy._calculate_stops(50000, SignalType.SELL)
    assert stop_loss > 50000
    assert trailing_stop > 50000
    assert trailing_stop < stop_loss


def test_crossover_signals(trend_config, trending_data):
    """Test MA crossover signal generation"""
    strategy = TrendStrategy(trend_config)
    strategy.initialize("BTCUSDT", trending_data[:100])  # Use uptrend portion

    # Simulate bullish crossover
    bar = {
        "timestamp": datetime.now(UTC),
        "open": 51800,
        "high": 51900,
        "low": 51700,
        "close": 51850,
        "volume": 500,
    }

    # Set up crossover conditions
    strategy.regime = "neutral"
    strategy.fast_ma_value = 51700
    strategy.slow_ma_value = 51800
    strategy.position_size = 0

    # Update to trigger crossover
    strategy.price_history.append(bar["close"])
    strategy._update_indicators()
    strategy.fast_ma_value = 51850  # Force crossover
    strategy.regime = "bullish"
    strategy.signal_strength = 0.7

    signals = strategy.on_bar(bar)

    # Should generate buy signal
    assert len(signals) > 0
    buy_signal = signals[0]
    assert buy_signal.signal_type == SignalType.BUY
    assert buy_signal.quantity > 0
    assert "crossover" in buy_signal.reason.lower()


def test_stop_loss_trigger(trend_config):
    """Test stop loss triggering"""
    strategy = TrendStrategy(trend_config)
    strategy.symbol = "BTCUSDT"
    strategy.position_size = 0.01
    strategy.entry_price = 50000
    strategy.stop_loss = 49000
    strategy.trailing_stop = 49200
    strategy.highest_price = 50000

    # Price hits stop loss
    tick = {"price": 48900}
    signals = strategy.on_tick(tick)

    assert len(signals) == 1
    assert signals[0].signal_type == SignalType.SELL
    assert signals[0].quantity == 0.01
    assert "stop_loss" in signals[0].metadata["stop_type"]


def test_trailing_stop_update(trend_config):
    """Test trailing stop update and trigger"""
    strategy = TrendStrategy(trend_config)
    strategy.symbol = "BTCUSDT"
    strategy.position_size = 0.01
    strategy.entry_price = 50000
    strategy.stop_loss = 49000
    strategy.trailing_stop = 49500
    strategy.highest_price = 50000
    strategy.atr_value = 500

    # Price increases, should update trailing stop
    tick1 = {"price": 51000}
    signals1 = strategy.on_tick(tick1)
    assert len(signals1) == 0
    assert strategy.highest_price == 51000
    assert strategy.trailing_stop > 49500

    # Price drops to hit trailing stop
    old_trailing = strategy.trailing_stop
    tick2 = {"price": old_trailing - 10}
    signals2 = strategy.on_tick(tick2)
    assert len(signals2) == 1
    assert signals2[0].signal_type == SignalType.SELL
    assert "trailing_stop" in signals2[0].metadata["stop_type"]


def test_regime_exit(trend_config, trending_data):
    """Test position exit on regime change"""
    strategy = TrendStrategy(trend_config)
    strategy.initialize("BTCUSDT", trending_data)

    # Set up long position
    strategy.position_size = 0.01
    strategy.entry_price = 50000
    strategy.regime = "bullish"

    # Change to bearish regime
    strategy.regime = "bearish"
    bar = {
        "timestamp": datetime.now(UTC),
        "close": 49500,
        "high": 49600,
        "low": 49400,
        "volume": 500,
    }

    signals = strategy.on_bar(bar)

    # Should exit long position
    assert len(signals) > 0
    exit_signal = signals[0]
    assert exit_signal.signal_type == SignalType.SELL
    assert exit_signal.quantity == 0.01
    assert "regime" in exit_signal.reason.lower()


def test_trade_tracking(trend_config):
    """Test trade performance tracking"""
    strategy = TrendStrategy(trend_config)
    strategy.symbol = "BTCUSDT"

    # Simulate a winning trade
    strategy.position_size = 0.01
    strategy.entry_price = 50000
    strategy.regime = "bearish"

    bar = {"close": 51000, "high": 51100, "low": 50900, "volume": 500}

    signals = strategy.on_bar(bar)

    # Check trade was recorded
    assert len(strategy.trades) == 1
    trade = strategy.trades[0]
    assert trade["entry"] == 50000
    assert trade["exit"] == 51000
    assert trade["pnl"] == 10  # (51000 - 50000) * 0.01
    assert strategy.win_count == 1


@pytest.mark.parametrize(
    "atr,multiplier,expected_distance",
    [
        (500, 2.0, 1000),
        (300, 1.5, 450),
        (1000, 2.5, 2500),
    ],
)
def test_atr_based_stops(trend_config, atr, multiplier, expected_distance):
    """Test ATR-based stop distance calculation"""
    config = trend_config.copy()
    config["atr_multiplier"] = multiplier

    strategy = TrendStrategy(config)
    strategy.atr_value = atr

    stop_loss, _ = strategy._calculate_stops(50000, SignalType.BUY)
    actual_distance = 50000 - stop_loss

    assert abs(actual_distance - expected_distance) < 1  # Floating point tolerance
