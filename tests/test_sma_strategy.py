"""Tests for SMA Strategy module."""

import pytest
import pandas as pd
import numpy as np
from src.backtester.strategies.sma import SMAStrategy


class TestSMAStrategy:
    """Test cases for SMA Strategy."""

    @pytest.fixture
    def strategy(self):
        """Create SMA strategy instance."""
        return SMAStrategy()

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        # Generate realistic price data
        close_prices = []
        price = 100
        for _ in range(100):
            price += np.random.normal(0, 1)  # Random walk
            close_prices.append(price)
        
        return pd.DataFrame({
            'date': dates,
            'open': [p * 0.99 for p in close_prices],
            'high': [p * 1.01 for p in close_prices],
            'low': [p * 0.98 for p in close_prices],
            'close': close_prices,
            'volume': np.random.randint(1000, 5000, 100)
        })

    def test_sma_strategy_normal_operation(self, strategy, sample_data):
        """Test SMA strategy with normal data."""
        signals = strategy.generate_signals(sample_data, fast_period=10, slow_period=20)
        
        assert len(signals) == len(sample_data)
        assert all(s in [-1, 0, 1] for s in signals)
        
        # First 20 points should be mostly 0 due to insufficient data for slow SMA
        # But may have some valid signals once fast SMA has enough data
        assert signals[0] == 0  # First point should definitely be 0
        assert signals[5] == 0  # Early points should be 0

    def test_sma_strategy_insufficient_data(self, strategy):
        """Test SMA strategy with insufficient data (should hit line 32)."""
        # Create data with fewer points than slow_period
        short_data = pd.DataFrame({
            'close': [100, 101, 102, 103, 104],  # Only 5 points
            'open': [99, 100, 101, 102, 103],
            'high': [101, 102, 103, 104, 105],
            'low': [98, 99, 100, 101, 102],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        # Use slow_period=50 which is more than data length (5)
        signals = strategy.generate_signals(short_data, fast_period=20, slow_period=50)
        
        # Should return all zeros due to insufficient data
        assert len(signals) == 5
        assert all(s == 0 for s in signals)

    def test_sma_strategy_equal_smas(self, strategy):
        """Test SMA strategy when fast and slow SMAs are equal (should hit line 48)."""
        # Create data where SMAs will be equal
        # Use constant price so SMAs will be equal
        constant_data = pd.DataFrame({
            'close': [100] * 60,  # Constant price
            'open': [99] * 60,
            'high': [101] * 60, 
            'low': [98] * 60,
            'volume': [1000] * 60
        })
        
        signals = strategy.generate_signals(constant_data, fast_period=10, slow_period=20)
        
        assert len(signals) == 60
        # After the initial warm-up period, signals should be 0 (flat) when SMAs are equal
        # Check some signals after warm-up period
        assert signals[25] == 0  # Should be flat when SMAs are equal
        assert signals[30] == 0
        assert signals[40] == 0

    def test_sma_strategy_crossover_signals(self, strategy):
        """Test SMA strategy generates correct crossover signals."""
        # Create trending data
        trending_data = pd.DataFrame({
            'close': list(range(100, 160)),  # Strong uptrend
            'open': list(range(99, 159)),
            'high': list(range(101, 161)),
            'low': list(range(98, 158)),
            'volume': [1000] * 60
        })
        
        signals = strategy.generate_signals(trending_data, fast_period=5, slow_period=15)
        
        assert len(signals) == 60
        # In a strong uptrend, should eventually get long signals
        # Check latter part of the signal series
        assert any(s == 1 for s in signals[20:])  # Should have some long signals

    def test_sma_strategy_downtrend(self, strategy):
        """Test SMA strategy in downtrend."""
        # Create downtrending data
        downtrend_data = pd.DataFrame({
            'close': list(range(160, 100, -1)),  # Strong downtrend
            'open': list(range(161, 101, -1)),
            'high': list(range(162, 102, -1)),
            'low': list(range(159, 99, -1)),
            'volume': [1000] * 60
        })
        
        signals = strategy.generate_signals(downtrend_data, fast_period=5, slow_period=15)
        
        assert len(signals) == 60
        # In a strong downtrend, should eventually get short signals
        assert any(s == -1 for s in signals[20:])  # Should have some short signals

    def test_sma_strategy_with_nan_data(self, strategy):
        """Test SMA strategy handles NaN values correctly."""
        # Create data with some NaN values
        data_with_nan = pd.DataFrame({
            'close': [100, 101, np.nan, 103, 104, 105, 106, 107, 108, 109] + [110] * 50,
            'open': [99, 100, np.nan, 102, 103, 104, 105, 106, 107, 108] + [109] * 50,
            'high': [101, 102, np.nan, 104, 105, 106, 107, 108, 109, 110] + [111] * 50,
            'low': [98, 99, np.nan, 101, 102, 103, 104, 105, 106, 107] + [108] * 50,
            'volume': [1000] * 60
        })
        
        signals = strategy.generate_signals(data_with_nan, fast_period=5, slow_period=10)
        
        assert len(signals) == 60
        # Should handle NaN gracefully and return valid signals
        assert all(isinstance(s, (int, np.integer)) for s in signals)

    def test_sma_strategy_custom_parameters(self, strategy, sample_data):
        """Test SMA strategy with custom parameters."""
        # Test with different parameter combinations
        signals1 = strategy.generate_signals(sample_data, fast_period=5, slow_period=10)
        signals2 = strategy.generate_signals(sample_data, fast_period=15, slow_period=30)
        
        assert len(signals1) == len(sample_data)
        assert len(signals2) == len(sample_data)
        
        # Different parameters should potentially give different signals
        # (though not necessarily - depends on the data)
        assert isinstance(signals1, list)
        assert isinstance(signals2, list)

    def test_sma_strategy_edge_case_periods(self, strategy):
        """Test SMA strategy with edge case periods."""
        # Test with very small periods
        small_data = pd.DataFrame({
            'close': [100, 101, 102, 103, 104, 105],
            'open': [99, 100, 101, 102, 103, 104],
            'high': [101, 102, 103, 104, 105, 106],
            'low': [98, 99, 100, 101, 102, 103],
            'volume': [1000] * 6
        })
        
        signals = strategy.generate_signals(small_data, fast_period=2, slow_period=3)
        
        assert len(signals) == 6
        assert all(s in [-1, 0, 1] for s in signals)

    def test_sma_strategy_single_data_point(self, strategy):
        """Test SMA strategy with single data point."""
        single_point = pd.DataFrame({
            'close': [100],
            'open': [99],
            'high': [101],
            'low': [98],
            'volume': [1000]
        })
        
        signals = strategy.generate_signals(single_point, fast_period=5, slow_period=10)
        
        assert len(signals) == 1
        assert signals[0] == 0  # Should return 0 for insufficient data

    def test_sma_strategy_empty_data(self, strategy):
        """Test SMA strategy with empty data."""
        empty_data = pd.DataFrame({
            'close': [],
            'open': [],
            'high': [],
            'low': [],
            'volume': []
        })
        
        signals = strategy.generate_signals(empty_data, fast_period=5, slow_period=10)
        
        assert len(signals) == 0
        assert signals == []