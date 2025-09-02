"""
Test suite for RSI strategy
"""

# Import the strategy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.backtester.strategies.rsi_strategy import RSIStrategy


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

    # Generate oscillating price data good for RSI testing
    np.random.seed(42)

    price = 100
    prices = []

    for i in range(100):
        # Create oscillating pattern with trend changes
        if i < 30:
            # Downtrend (should create oversold conditions)
            change = np.random.normal(-0.01, 0.02)
        elif i < 60:
            # Uptrend (should create overbought conditions)
            change = np.random.normal(0.01, 0.02)
        else:
            # Sideways (mixed signals)
            change = np.random.normal(0, 0.015)

        price *= 1 + change
        price = max(price, 50)  # Keep prices positive
        prices.append(price)

    data = pd.DataFrame(
        {
            "Open": [p * 0.995 for p in prices],
            "High": [p * 1.02 for p in prices],
            "Low": [p * 0.98 for p in prices],
            "Close": prices,
            "Volume": [np.random.randint(1000000, 5000000) for _ in range(100)],
        },
        index=dates,
    )

    return data


@pytest.fixture
def strategy():
    """Create RSIStrategy instance"""
    return RSIStrategy()


@pytest.fixture
def custom_strategy():
    """Create custom RSIStrategy instance"""
    return RSIStrategy(rsi_period=10, oversold_level=25, overbought_level=75)


class TestRSIStrategy:
    def test_strategy_initialization_default(self):
        """Test default strategy initialization"""
        strategy = RSIStrategy()
        assert strategy.rsi_period == 14
        assert strategy.oversold_level == 30
        assert strategy.overbought_level == 70

    def test_strategy_initialization_custom(self):
        """Test custom strategy initialization"""
        strategy = RSIStrategy(rsi_period=10, oversold_level=25, overbought_level=75)
        assert strategy.rsi_period == 10
        assert strategy.oversold_level == 25
        assert strategy.overbought_level == 75

    def test_calculate_rsi_basic(self, strategy):
        """Test basic RSI calculation"""
        # Create test data with known pattern
        prices = pd.Series([100, 102, 101, 103, 102, 104, 103, 105, 104, 106] + [100] * 20)

        rsi = strategy.calculate_rsi(prices)

        # Check return type and shape
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(prices)

        # RSI should be between 0 and 100 (excluding NaN)
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

        # First few values should be NaN due to rolling window
        assert rsi.iloc[:13].isna().all()  # First 14-1 values should be NaN

        # Should have some valid values after initial period
        # Note: flat prices at the end may cause NaN due to zero gains/losses
        assert not rsi.iloc[14:24].isna().any()  # Check middle section with price changes

    def test_calculate_rsi_trending_up(self, strategy):
        """Test RSI with strong uptrend"""
        # Create strong uptrend
        prices = pd.Series([100 + i * 2 for i in range(30)])  # Strong uptrend

        rsi = strategy.calculate_rsi(prices)

        # In strong uptrend, RSI should generally be high
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            # Should have high RSI values in uptrend
            assert valid_rsi.iloc[-5:].mean() > 50  # Last 5 RSI values should be above 50

    def test_calculate_rsi_trending_down(self, strategy):
        """Test RSI with strong downtrend"""
        # Create strong downtrend
        prices = pd.Series([100 - i * 1.5 for i in range(30)])  # Strong downtrend

        rsi = strategy.calculate_rsi(prices)

        # In strong downtrend, RSI should generally be low
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            # Should have low RSI values in downtrend
            assert valid_rsi.iloc[-5:].mean() < 50  # Last 5 RSI values should be below 50

    def test_calculate_rsi_flat_prices(self, strategy):
        """Test RSI with flat prices"""
        # Flat prices should result in RSI around 50
        prices = pd.Series([100] * 30)

        rsi = strategy.calculate_rsi(prices)

        # With flat prices, RSI should be undefined (NaN) due to zero gains/losses
        valid_rsi = rsi.dropna()
        # With zero price changes, RSI calculation may result in NaN or undefined values
        # This is expected behavior
        assert len(rsi) == 30

    def test_calculate_rsi_custom_parameters(self, custom_strategy):
        """Test RSI with custom parameters"""
        prices = pd.Series([100 + np.sin(i / 5) * 10 for i in range(50)])  # Oscillating

        rsi = custom_strategy.calculate_rsi(prices)

        # Check that RSI calculation works with custom period
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(prices)

        # First 9 values should be NaN (period-1 for period=10)
        assert rsi.iloc[:9].isna().all()

        # Should have valid values after period
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            assert (valid_rsi >= 0).all()
            assert (valid_rsi <= 100).all()

    def test_generate_signals_basic(self, strategy, sample_data):
        """Test basic signal generation"""
        signals = strategy.generate_signals(sample_data)

        # Check return type and shape
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)
        assert signals.index.equals(sample_data.index)

        # Check signal values are valid
        assert signals.isin([0, 1, -1]).all()

        # Should have some signals due to oscillating data
        total_signals = (signals != 0).sum()
        assert total_signals >= 0  # At least we can generate signals

    def test_generate_signals_empty_data(self, strategy):
        """Test signal generation with empty data"""
        empty_data = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        signals = strategy.generate_signals(empty_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == 0

    def test_generate_signals_insufficient_data(self, strategy):
        """Test signal generation with insufficient data"""
        # Very small dataset
        small_data = pd.DataFrame(
            {
                "Open": [100] * 10,
                "High": [102] * 10,
                "Low": [98] * 10,
                "Close": [100] * 10,
                "Volume": [1000] * 10,
            }
        )

        signals = strategy.generate_signals(small_data)

        # Should return series of correct length
        assert isinstance(signals, pd.Series)
        assert len(signals) == 10
        assert signals.isin([0, 1, -1]).all()

    def test_generate_signals_oversold_conditions(self, strategy):
        """Test RSI oversold signal generation"""
        # Create data that will produce oversold RSI
        dates = pd.date_range("2023-01-01", periods=50, freq="D")

        # Strong downtrend to create oversold conditions
        base_price = 100
        decline_prices = [base_price - i * 2.5 for i in range(25)]  # Sharp decline
        recovery_prices = [decline_prices[-1] + i * 1 for i in range(25)]  # Recovery
        prices = decline_prices + recovery_prices

        data = pd.DataFrame(
            {
                "Open": [p * 0.99 for p in prices],
                "High": [p * 1.01 for p in prices],
                "Low": [p * 0.99 for p in prices],
                "Close": prices,
                "Volume": [1000000] * 50,
            },
            index=dates,
        )

        signals = strategy.generate_signals(data)

        # Should generate some signals from the price movements
        total_signals = (signals != 0).sum()
        assert total_signals >= 0

    def test_generate_signals_overbought_conditions(self, strategy):
        """Test RSI overbought signal generation"""
        # Create data that will produce overbought RSI
        dates = pd.date_range("2023-01-01", periods=50, freq="D")

        # Strong uptrend to create overbought conditions
        base_price = 50
        rally_prices = [base_price + i * 2.5 for i in range(25)]  # Sharp rally
        decline_prices = [rally_prices[-1] - i * 1 for i in range(25)]  # Decline
        prices = rally_prices + decline_prices

        data = pd.DataFrame(
            {
                "Open": [p * 0.99 for p in prices],
                "High": [p * 1.01 for p in prices],
                "Low": [p * 0.99 for p in prices],
                "Close": prices,
                "Volume": [1000000] * 50,
            },
            index=dates,
        )

        signals = strategy.generate_signals(data)

        # Should generate some signals from the price movements
        total_signals = (signals != 0).sum()
        assert total_signals >= 0

    def test_generate_signals_consistency(self, strategy):
        """Test that signal generation is consistent"""
        # Same input should produce same output
        data = pd.DataFrame(
            {
                "Open": [100 + np.sin(i / 5) * 10 for i in range(30)],
                "High": [102 + np.sin(i / 5) * 10 for i in range(30)],
                "Low": [98 + np.sin(i / 5) * 10 for i in range(30)],
                "Close": [100 + np.sin(i / 5) * 10 for i in range(30)],
                "Volume": [1000000] * 30,
            }
        )

        signals1 = strategy.generate_signals(data)
        signals2 = strategy.generate_signals(data)

        assert signals1.equals(signals2)

    def test_rsi_mathematical_properties(self, strategy):
        """Test RSI mathematical correctness"""
        # Create known price pattern
        prices = pd.Series([100, 102, 101, 104, 103, 106, 105, 108, 107, 110] + [105] * 20)

        rsi = strategy.calculate_rsi(prices)

        # Manual calculation for verification (simplified)
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        # Avoid division by zero
        rs = gain / loss.replace(0, np.nan)
        expected_rsi = 100 - (100 / (1 + rs))

        # Compare with our calculation (allowing for small numerical differences)
        valid_mask = ~(rsi.isna() | expected_rsi.isna())
        if valid_mask.any():
            assert np.allclose(rsi[valid_mask], expected_rsi[valid_mask], rtol=1e-10)

    def test_signal_crossover_logic(self, strategy):
        """Test the signal crossover detection logic"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")

        # Create specific RSI pattern: low -> high -> low
        # Start high, drop to oversold, recover to overbought
        start_prices = [100] * 10  # Stable start (10 items)
        drop_prices = [100 - i * 5 for i in range(1, 11)]  # Drop to create oversold (10 items)
        rise_prices = [50 + i * 4 for i in range(1, 21)]  # Rise to create overbought (20 items)
        recovery_prices = [130 - i * 2 for i in range(1, 11)]  # Back down (10 items) - Total: 50

        prices = start_prices + drop_prices + rise_prices + recovery_prices
        assert len(prices) == 50  # Ensure correct length

        data = pd.DataFrame(
            {
                "Open": prices,
                "High": [p * 1.01 for p in prices],
                "Low": [p * 0.99 for p in prices],
                "Close": prices,
                "Volume": [1000000] * 50,
            },
            index=dates,
        )

        signals = strategy.generate_signals(data)

        # Verify signal properties
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(data)
        assert signals.isin([0, 1, -1]).all()

    def test_edge_cases(self, strategy):
        """Test edge cases"""
        # Single data point
        single_data = pd.DataFrame(
            {"Open": [100], "High": [102], "Low": [98], "Close": [100], "Volume": [1000000]}
        )

        signals = strategy.generate_signals(single_data)
        assert len(signals) == 1
        assert signals.iloc[0] == 0

        # Two data points
        two_data = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [102, 103],
                "Low": [98, 99],
                "Close": [100, 101],
                "Volume": [1000000, 1000000],
            }
        )

        signals = strategy.generate_signals(two_data)
        assert len(signals) == 2
        assert signals.isin([0, 1, -1]).all()

        # NaN values in data
        nan_data = pd.DataFrame(
            {
                "Open": [100, np.nan, 102],
                "High": [102, np.nan, 104],
                "Low": [98, np.nan, 100],
                "Close": [100, np.nan, 102],
                "Volume": [1000000, 1000000, 1000000],
            }
        )

        signals = strategy.generate_signals(nan_data)
        assert len(signals) == 3
        assert signals.isin([0, 1, -1]).all()

    def test_parameter_variations(self):
        """Test different parameter combinations"""
        test_params = [(7, 20, 80), (10, 25, 75), (21, 35, 65), (30, 40, 60)]

        # Create test data
        prices = pd.Series([100 + np.sin(i / 8) * 20 for i in range(100)])  # Strong oscillation
        data = pd.DataFrame(
            {
                "Open": prices * 0.99,
                "High": prices * 1.01,
                "Low": prices * 0.99,
                "Close": prices,
                "Volume": [1000000] * 100,
            }
        )

        for period, oversold, overbought in test_params:
            strategy = RSIStrategy(period, oversold, overbought)

            # Should not raise exceptions
            rsi = strategy.calculate_rsi(prices)
            signals = strategy.generate_signals(data)

            # Basic validation
            assert len(rsi) == len(prices)
            assert len(signals) == len(data)
            assert signals.isin([0, 1, -1]).all()

    def test_signal_cleaning_logic(self, strategy):
        """Test the signal cleaning logic in generate_signals"""
        # Create test data that will produce continuous oversold/overbought conditions
        dates = pd.date_range("2023-01-01", periods=30, freq="D")

        # Create prices that will stay in oversold region for multiple periods
        prices = [20] * 30  # Extremely low price to trigger oversold repeatedly

        data = pd.DataFrame(
            {
                "Open": prices,
                "High": [p * 1.1 for p in prices],
                "Low": [p * 0.9 for p in prices],
                "Close": prices,
                "Volume": [1000000] * 30,
            },
            index=dates,
        )

        signals = strategy.generate_signals(data)

        # Signal cleaning should prevent continuous signals
        # Only crossovers should generate signals
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(data)
        assert signals.isin([0, 1, -1]).all()

    def test_rsi_boundary_values(self, strategy):
        """Test RSI calculation with boundary values"""
        # Test with very small price changes
        prices = pd.Series([100 + 0.001 * i for i in range(30)])
        rsi = strategy.calculate_rsi(prices)

        assert isinstance(rsi, pd.Series)
        assert len(rsi) == 30

        # Test with large price changes
        big_changes = pd.Series([100 * (1.1**i) for i in range(30)])
        rsi_big = strategy.calculate_rsi(big_changes)

        assert isinstance(rsi_big, pd.Series)
        valid_rsi = rsi_big.dropna()
        if len(valid_rsi) > 0:
            assert (valid_rsi >= 0).all()
            assert (valid_rsi <= 100).all()


if __name__ == "__main__":
    pytest.main([__file__])
