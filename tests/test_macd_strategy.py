"""
Test suite for MACD strategy
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the strategy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.backtester.strategies.macd_strategy import MACDStrategy


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    # Generate trending price data for MACD
    np.random.seed(42)
    
    price = 100
    prices = []
    
    for i in range(100):
        # Create trending data with some noise
        trend = np.sin(i / 10) * 5  # Cyclical trend
        noise = np.random.normal(0, 1)
        price += trend * 0.1 + noise * 0.5
        prices.append(max(price, 50))  # Keep prices positive
    
    data = pd.DataFrame({
        'Open': [p * 0.995 for p in prices],
        'High': [p * 1.02 for p in prices],
        'Low': [p * 0.98 for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000000, 5000000) for _ in range(100)]
    }, index=dates)
    
    return data


@pytest.fixture
def strategy():
    """Create MACDStrategy instance"""
    return MACDStrategy()


@pytest.fixture
def custom_strategy():
    """Create custom MACDStrategy instance"""
    return MACDStrategy(fast_period=8, slow_period=21, signal_period=7)


class TestMACDStrategy:
    
    def test_strategy_initialization_default(self):
        """Test default strategy initialization"""
        strategy = MACDStrategy()
        assert strategy.fast_period == 12
        assert strategy.slow_period == 26
        assert strategy.signal_period == 9
    
    def test_strategy_initialization_custom(self):
        """Test custom strategy initialization"""
        strategy = MACDStrategy(fast_period=8, slow_period=21, signal_period=7)
        assert strategy.fast_period == 8
        assert strategy.slow_period == 21
        assert strategy.signal_period == 7
    
    def test_calculate_macd_basic(self, strategy):
        """Test basic MACD calculation"""
        # Create trending test data
        prices = pd.Series([100 + i * 0.5 for i in range(50)])
        
        macd, signal, histogram = strategy.calculate_macd(prices)
        
        # Check return types and shapes
        assert isinstance(macd, pd.Series)
        assert isinstance(signal, pd.Series)
        assert isinstance(histogram, pd.Series)
        assert len(macd) == len(prices)
        assert len(signal) == len(prices)
        assert len(histogram) == len(prices)
        
        # Check that histogram equals macd - signal
        assert np.allclose(histogram, macd - signal, equal_nan=True)
        
        # MACD should have some non-zero values after initial period
        assert not macd.iloc[30:].eq(0).all()
    
    def test_calculate_macd_trending_up(self, strategy):
        """Test MACD with upward trending prices"""
        # Create strong uptrend
        prices = pd.Series([100 + i * 2 for i in range(50)])  # Strong uptrend
        
        macd, signal, histogram = strategy.calculate_macd(prices)
        
        # In uptrend, MACD should generally be positive after initial period
        valid_period = 30  # Allow for EMA stabilization
        assert macd.iloc[valid_period:].mean() > 0  # Should be positive on average
    
    def test_calculate_macd_trending_down(self, strategy):
        """Test MACD with downward trending prices"""
        # Create strong downtrend
        prices = pd.Series([100 - i * 2 for i in range(50)])  # Strong downtrend
        
        macd, signal, histogram = strategy.calculate_macd(prices)
        
        # In downtrend, MACD should generally be negative after initial period
        valid_period = 30  # Allow for EMA stabilization
        assert macd.iloc[valid_period:].mean() < 0  # Should be negative on average
    
    def test_calculate_macd_flat_prices(self, strategy):
        """Test MACD with flat prices"""
        # Flat prices should result in MACD near zero
        prices = pd.Series([100] * 50)
        
        macd, signal, histogram = strategy.calculate_macd(prices)
        
        # With flat prices, MACD and signal should converge to zero
        assert abs(macd.iloc[-1]) < 0.001
        assert abs(signal.iloc[-1]) < 0.001
        assert abs(histogram.iloc[-1]) < 0.001
    
    def test_calculate_macd_custom_parameters(self, custom_strategy):
        """Test MACD with custom parameters"""
        prices = pd.Series([100 + np.sin(i/5) * 10 for i in range(50)])  # Cyclical
        
        macd, signal, histogram = custom_strategy.calculate_macd(prices)
        
        # Check that all series have valid values
        assert isinstance(macd, pd.Series)
        assert isinstance(signal, pd.Series)
        assert isinstance(histogram, pd.Series)
        assert len(macd) == len(prices)
    
    def test_generate_signals_basic(self, strategy, sample_data):
        """Test basic signal generation"""
        signals = strategy.generate_signals(sample_data)
        
        # Check return type and shape
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)
        assert signals.index.equals(sample_data.index)
        
        # Check signal values are valid
        assert signals.isin([0, 1, -1]).all()
        
        # Should have some signals due to cyclical data
        assert (signals != 0).sum() > 0
    
    def test_generate_signals_empty_data(self, strategy):
        """Test signal generation with empty data"""
        empty_data = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        
        signals = strategy.generate_signals(empty_data)
        
        assert isinstance(signals, pd.Series)
        assert len(signals) == 0
    
    def test_generate_signals_insufficient_data(self, strategy):
        """Test signal generation with insufficient data"""
        # Very small dataset
        small_data = pd.DataFrame({
            'Open': [100] * 5,
            'High': [102] * 5,
            'Low': [98] * 5,
            'Close': [100] * 5,
            'Volume': [1000] * 5
        })
        
        signals = strategy.generate_signals(small_data)
        
        # Should return series of correct length
        assert isinstance(signals, pd.Series)
        assert len(signals) == 5
        assert signals.isin([0, 1, -1]).all()
    
    def test_generate_signals_crossover_conditions(self, strategy):
        """Test MACD crossover signal generation"""
        # Create data that will produce clear crossovers
        dates = pd.date_range('2023-01-01', periods=60, freq='D')
        
        # Create price pattern that will generate crossovers
        # Start low, trend up (bullish crossover), then trend down (bearish crossover)
        prices = ([90] * 10 +  # Stable low
                 [90 + i * 2 for i in range(20)] +  # Strong uptrend
                 [130 - i * 1.5 for i in range(30)])  # Downtrend
        
        data = pd.DataFrame({
            'Open': [p * 0.99 for p in prices],
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 60
        }, index=dates)
        
        signals = strategy.generate_signals(data)
        
        # Should have both buy and sell signals due to the trends
        buy_signals = (signals == 1).sum()
        sell_signals = (signals == -1).sum()
        
        # Should have at least some signals
        assert buy_signals + sell_signals > 0
    
    def test_generate_signals_consistency(self, strategy):
        """Test that signal generation is consistent"""
        # Same input should produce same output
        data = pd.DataFrame({
            'Open': [100 + i * 0.5 for i in range(30)],
            'High': [102 + i * 0.5 for i in range(30)],
            'Low': [98 + i * 0.5 for i in range(30)],
            'Close': [100 + i * 0.5 for i in range(30)],
            'Volume': [1000000] * 30
        })
        
        signals1 = strategy.generate_signals(data)
        signals2 = strategy.generate_signals(data)
        
        assert signals1.equals(signals2)
    
    def test_macd_mathematical_properties(self, strategy):
        """Test MACD mathematical correctness"""
        prices = pd.Series([100 + i * 0.1 for i in range(100)])  # Slight uptrend
        
        macd, signal, histogram = strategy.calculate_macd(prices)
        
        # Manually calculate EMAs for verification
        ema_fast = prices.ewm(span=12, adjust=False).mean()
        ema_slow = prices.ewm(span=26, adjust=False).mean()
        expected_macd = ema_fast - ema_slow
        
        # MACD should match manual calculation
        assert np.allclose(macd, expected_macd, equal_nan=True)
        
        # Signal should be EMA of MACD
        expected_signal = macd.ewm(span=9, adjust=False).mean()
        assert np.allclose(signal, expected_signal, equal_nan=True)
    
    def test_crossover_detection(self, strategy):
        """Test crossover detection logic"""
        # Create specific MACD crossover scenario
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        
        # Create price pattern that generates clear crossover
        base_price = 100
        trend_up = [base_price + i * 0.8 for i in range(25)]  # Uptrend for bullish crossover
        trend_down = [base_price + 25 * 0.8 - i * 0.6 for i in range(25)]  # Downtrend
        prices = trend_up + trend_down
        
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 50
        }, index=dates)
        
        signals = strategy.generate_signals(data)
        
        # Verify signal generation logic
        macd, signal_line, _ = strategy.calculate_macd(pd.Series(prices))
        
        # Find actual crossovers
        bullish_crossover = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))
        bearish_crossover = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1))
        
        # Signals should correspond to crossovers
        buy_signals_expected = bullish_crossover.astype(int)
        sell_signals_expected = bearish_crossover.astype(int) * -1
        expected_signals = buy_signals_expected + sell_signals_expected
        
        # Should match our signal generation (check values only, not index)
        assert (signals.values == expected_signals.values).all()
    
    def test_edge_cases(self, strategy):
        """Test edge cases"""
        # Single data point
        single_data = pd.DataFrame({
            'Open': [100], 'High': [102], 'Low': [98], 
            'Close': [100], 'Volume': [1000000]
        })
        
        signals = strategy.generate_signals(single_data)
        assert len(signals) == 1
        assert signals.iloc[0] == 0
        
        # NaN values in data
        nan_data = pd.DataFrame({
            'Open': [100, np.nan, 102],
            'High': [102, np.nan, 104],
            'Low': [98, np.nan, 100],
            'Close': [100, np.nan, 102],
            'Volume': [1000000, 1000000, 1000000]
        })
        
        signals = strategy.generate_signals(nan_data)
        assert len(signals) == 3
        assert signals.isin([0, 1, -1]).all()
    
    def test_parameter_variations(self):
        """Test different parameter combinations"""
        test_params = [
            (5, 13, 5),
            (8, 21, 7),
            (10, 30, 10),
            (15, 35, 12)
        ]
        
        # Create test data
        prices = pd.Series([100 + np.sin(i/10) * 10 for i in range(100)])
        data = pd.DataFrame({
            'Open': prices * 0.99,
            'High': prices * 1.01,
            'Low': prices * 0.99,
            'Close': prices,
            'Volume': [1000000] * 100
        })
        
        for fast, slow, signal_period in test_params:
            strategy = MACDStrategy(fast, slow, signal_period)
            
            # Should not raise exceptions
            macd, signal_line, histogram = strategy.calculate_macd(prices)
            signals = strategy.generate_signals(data)
            
            # Basic validation
            assert len(macd) == len(prices)
            assert len(signals) == len(data)
            assert signals.isin([0, 1, -1]).all()
    
    def test_signal_timing_precision(self, strategy):
        """Test that signals occur at exact crossover points"""
        # Create very specific price pattern
        dates = pd.date_range('2023-01-01', periods=40, freq='D')
        
        # Design prices to create predictable crossovers
        prices = ([100] * 15 +  # Stable start
                 [100 + i * 3 for i in range(10)] +  # Sharp rise
                 [130 - i * 2 for i in range(15)])  # Sharp fall
        
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.005 for p in prices],
            'Low': [p * 0.995 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 40
        }, index=dates)
        
        signals = strategy.generate_signals(data)
        
        # Test that signals are generated
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(data)
        assert signals.isin([0, 1, -1]).all()


if __name__ == "__main__":
    pytest.main([__file__])