"""Tests for Grid trading strategy"""

import json
import pytest
from datetime import datetime, UTC
import pandas as pd
import numpy as np
from pathlib import Path

from sofia_strategies.grid import GridStrategy
from sofia_strategies.base import SignalType


@pytest.fixture
def grid_config():
    """Default grid strategy configuration"""
    return {
        "base_qty": 20.0,
        "grid_step_pct": 0.45,
        "grid_levels": 5,
        "take_profit_pct": 2.0,
        "max_inventory": 200.0,
        "cooldown_s": 5,
        "rebalance_threshold": 0.7
    }


@pytest.fixture
def sample_data():
    """Generate sample price data for testing"""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    
    # Generate synthetic price data with trend and noise
    trend = np.linspace(50000, 51000, 100)
    noise = np.random.normal(0, 200, 100)
    prices = trend + noise
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices * 0.998,
        "high": prices * 1.002,
        "low": prices * 0.997,
        "close": prices,
        "volume": np.random.uniform(100, 1000, 100)
    })


def test_grid_initialization(grid_config, sample_data):
    """Test grid strategy initialization"""
    strategy = GridStrategy(grid_config)
    strategy.initialize("BTCUSDT", sample_data)
    
    assert strategy.symbol == "BTCUSDT"
    assert strategy.mid_price > 0
    assert strategy.volatility > 0
    assert len(strategy.price_history) > 0


def test_grid_level_calculation(grid_config):
    """Test grid level calculation"""
    strategy = GridStrategy(grid_config)
    strategy.mid_price = 50000
    
    levels = strategy._calculate_grid_levels()
    
    assert "buy" in levels
    assert "sell" in levels
    assert len(levels["buy"]) == grid_config["grid_levels"]
    assert len(levels["sell"]) == grid_config["grid_levels"]
    
    # Check buy levels are below mid price
    for price in levels["buy"]:
        assert price < strategy.mid_price
    
    # Check sell levels are above mid price
    for price in levels["sell"]:
        assert price > strategy.mid_price
    
    # Check spacing
    expected_step = strategy.mid_price * grid_config["grid_step_pct"] / 100
    assert abs(levels["buy"][0] - levels["buy"][1]) - expected_step < 1


def test_grid_signals_generation(grid_config, sample_data):
    """Test signal generation for grid strategy"""
    strategy = GridStrategy(grid_config)
    strategy.initialize("BTCUSDT", sample_data)
    
    # Test tick processing
    tick = {
        "symbol": "BTCUSDT",
        "price": 50000,
        "bid": 49990,
        "ask": 50010,
        "volume": 100
    }
    
    signals = strategy.on_tick(tick)
    
    # Should generate grid orders
    assert len(signals) > 0
    
    # Check signal properties
    for signal in signals:
        assert signal.symbol == "BTCUSDT"
        assert signal.strategy == "GridStrategy"
        assert signal.signal_type in [SignalType.BUY, SignalType.SELL]
        assert signal.quantity > 0
        if signal.signal_type == SignalType.BUY:
            assert signal.price < tick["price"]
        else:
            assert signal.price > tick["price"]


def test_inventory_management(grid_config):
    """Test inventory tracking and limits"""
    strategy = GridStrategy(grid_config)
    strategy.mid_price = 50000
    strategy.symbol = "BTCUSDT"
    
    # Simulate order fills
    buy_order = {
        "side": "buy",
        "quantity": 0.01,
        "price": 49500,
        "order_id": "test1"
    }
    
    strategy.on_order_fill(buy_order)
    assert strategy.inventory == 0.01
    
    # Test max inventory check
    strategy.inventory = grid_config["max_inventory"] / 50000  # Max in BTC
    assert strategy._should_rebalance() == False
    
    strategy.inventory = grid_config["max_inventory"] * grid_config["rebalance_threshold"] / 50000 + 0.001
    assert strategy._should_rebalance() == True


def test_rebalancing_signal(grid_config):
    """Test rebalancing signal generation"""
    strategy = GridStrategy(grid_config)
    strategy.mid_price = 50000
    strategy.symbol = "BTCUSDT"
    strategy.inventory = 0.01  # Long position
    
    signal = strategy._generate_rebalance_signal()
    
    assert signal is not None
    assert signal.signal_type == SignalType.SELL
    assert signal.quantity > 0
    assert signal.quantity <= strategy.inventory
    assert "rebalance" in signal.metadata


def test_take_profit(grid_config, sample_data):
    """Test take profit logic"""
    strategy = GridStrategy(grid_config)
    strategy.initialize("BTCUSDT", sample_data)
    strategy.inventory = 0.01
    
    # Simulate price increase for take profit
    strategy.price_history = [50000] * 20 + [51100] * 10  # 2.2% gain
    strategy.mid_price = 51100
    
    signal = strategy._check_take_profit()
    
    assert signal is not None
    assert signal.signal_type == SignalType.SELL
    assert "take_profit" in signal.metadata
    assert signal.metadata["pnl_pct"] > grid_config["take_profit_pct"]


def test_order_size_calculation(grid_config):
    """Test dynamic order size calculation"""
    strategy = GridStrategy(grid_config)
    strategy.mid_price = 50000
    strategy.volatility = 0.02  # 2% volatility
    
    # Test with no inventory
    strategy.inventory = 0
    size = strategy._calculate_order_size(50000, SignalType.BUY)
    base_size = grid_config["base_qty"] / 50000
    assert size > 0
    assert size <= base_size * 1.5  # Max adjustment factor
    
    # Test with high inventory (should reduce buy size)
    strategy.inventory = grid_config["max_inventory"] * 0.8 / 50000
    size_with_inventory = strategy._calculate_order_size(50000, SignalType.BUY)
    assert size_with_inventory < size


def test_cooldown_period(grid_config):
    """Test cooldown between orders"""
    strategy = GridStrategy(grid_config)
    strategy.initialize("BTCUSDT", pd.DataFrame())
    strategy.mid_price = 50000
    
    tick = {
        "symbol": "BTCUSDT",
        "price": 50000,
        "bid": 49990,
        "ask": 50010
    }
    
    # First tick should generate signals
    signals1 = strategy.on_tick(tick)
    assert len(signals1) > 0
    
    # Immediate second tick should not generate signals (cooldown)
    signals2 = strategy.on_tick(tick)
    assert len(signals2) == 0


@pytest.mark.parametrize("volatility,expected_factor", [
    (0.01, 1.0),   # Low volatility, max size
    (0.02, 1.0),   # Normal volatility
    (0.05, 0.5),   # High volatility, reduced size
])
def test_volatility_adjustment(grid_config, volatility, expected_factor):
    """Test order size adjustment based on volatility"""
    strategy = GridStrategy(grid_config)
    strategy.mid_price = 50000
    strategy.volatility = volatility
    strategy.inventory = 0
    
    size = strategy._calculate_order_size(50000, SignalType.BUY)
    base_size = grid_config["base_qty"] / 50000
    
    # Higher volatility should reduce position size
    assert size <= base_size * expected_factor * 1.1  # Allow 10% tolerance