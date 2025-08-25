"""
Test suite for technical indicators
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the indicators module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.metrics.indicators import (
    rsi, sma, ema, bbands, atr, macd, stochastic, 
    volume_sma, price_change_percent,
    add_all_indicators, get_latest_indicators
)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
    
    # Generate realistic price data with some trend and volatility
    np.random.seed(42)  # For reproducible tests
    
    price = 100  # Starting price
    data = []
    
    for i in range(100):
        # Random walk with slight upward bias
        change = np.random.normal(0.001, 0.02)  # 0.1% mean, 2% std
        price *= (1 + change)
        
        # OHLC around the price
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = price * (1 + np.random.normal(0, 0.005))
        close_price = price
        volume = abs(np.random.normal(1000000, 200000))
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


class TestTechnicalIndicators:
    """Test technical indicators calculations"""
    
    def test_rsi_basic(self, sample_ohlcv_data):
        """Test RSI calculation"""
        df = sample_ohlcv_data
        rsi_values = rsi(df, period=14)
        
        # RSI should be between 0 and 100
        assert rsi_values.min() >= 0
        assert rsi_values.max() <= 100
        
        # Should have NaN values for initial periods
        assert pd.isna(rsi_values.iloc[0])
        
        # Should have valid values after initial period
        assert not pd.isna(rsi_values.iloc[20])
        
    def test_sma_basic(self, sample_ohlcv_data):
        """Test Simple Moving Average"""
        df = sample_ohlcv_data
        sma_values = sma(df, period=20)
        
        # Should have NaN for initial periods
        assert pd.isna(sma_values.iloc[10])
        
        # Should have valid values after period
        assert not pd.isna(sma_values.iloc[25])
        
        # SMA should be close to actual prices (rough check)
        valid_sma = sma_values.dropna()
        valid_close = df['close'].iloc[len(df) - len(valid_sma):]
        
        # SMA should be within reasonable range of actual prices
        assert abs(valid_sma.mean() - valid_close.mean()) < valid_close.mean() * 0.1
        
    def test_ema_basic(self, sample_ohlcv_data):
        """Test Exponential Moving Average"""
        df = sample_ohlcv_data
        ema_values = ema(df, period=20)
        
        # EMA should have fewer NaN values than SMA
        assert not pd.isna(ema_values.iloc[5])
        
        # EMA should respond faster to price changes than SMA
        sma_values = sma(df, period=20)
        
        # This is a rough test - EMA should be different from SMA
        ema_valid = ema_values.dropna()
        sma_valid = sma_values.dropna()
        
        # Make sure they're not identical (EMA responds faster)
        assert not ema_valid.equals(sma_valid)
        
    def test_bollinger_bands(self, sample_ohlcv_data):
        """Test Bollinger Bands"""
        df = sample_ohlcv_data
        bb_upper, bb_middle, bb_lower = bbands(df, period=20, std_dev=2)
        
        # Middle band should equal SMA
        sma_values = sma(df, period=20)
        pd.testing.assert_series_equal(bb_middle, sma_values, check_names=False)
        
        # Upper band should be higher than middle
        valid_indices = ~(bb_upper.isna() | bb_middle.isna())
        assert (bb_upper[valid_indices] >= bb_middle[valid_indices]).all()
        
        # Lower band should be lower than middle
        valid_indices = ~(bb_lower.isna() | bb_middle.isna())
        assert (bb_lower[valid_indices] <= bb_middle[valid_indices]).all()
        
    def test_atr_basic(self, sample_ohlcv_data):
        """Test Average True Range"""
        df = sample_ohlcv_data
        atr_values = atr(df, period=14)
        
        # ATR should be positive
        valid_atr = atr_values.dropna()
        assert (valid_atr >= 0).all()
        
        # Should have some reasonable values
        assert valid_atr.mean() > 0
        
    def test_macd_basic(self, sample_ohlcv_data):
        """Test MACD"""
        df = sample_ohlcv_data
        macd_line, signal_line, histogram = macd(df)
        
        # All should have same length
        assert len(macd_line) == len(signal_line) == len(histogram)
        
        # Histogram should equal MACD - Signal
        valid_indices = ~(macd_line.isna() | signal_line.isna() | histogram.isna())
        expected_histogram = macd_line - signal_line
        
        pd.testing.assert_series_equal(
            histogram[valid_indices], 
            expected_histogram[valid_indices], 
            check_names=False,
            check_exact=False
        )
        
    def test_stochastic_basic(self, sample_ohlcv_data):
        """Test Stochastic Oscillator"""
        df = sample_ohlcv_data
        stoch_k, stoch_d = stochastic(df, k_period=14, d_period=3)
        
        # Should be between 0 and 100
        valid_k = stoch_k.dropna()
        valid_d = stoch_d.dropna()
        
        assert (valid_k >= 0).all() and (valid_k <= 100).all()
        assert (valid_d >= 0).all() and (valid_d <= 100).all()
        
    def test_add_all_indicators(self, sample_ohlcv_data):
        """Test adding all indicators to DataFrame"""
        df = sample_ohlcv_data
        df_with_indicators = add_all_indicators(df)
        
        # Should have all original columns
        for col in df.columns:
            assert col in df_with_indicators.columns
            
        # Should have indicator columns
        expected_indicators = [
            'rsi', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'bb_upper', 'bb_middle', 'bb_lower',
            'atr', 'macd', 'macd_signal', 'macd_histogram',
            'stoch_k', 'stoch_d', 'volume_sma',
            'price_change_1h', 'price_change_24h'
        ]
        
        for indicator in expected_indicators:
            assert indicator in df_with_indicators.columns
            
    def test_get_latest_indicators(self, sample_ohlcv_data):
        """Test getting latest indicator values"""
        df = sample_ohlcv_data
        latest = get_latest_indicators(df)
        
        # Should be a dictionary
        assert isinstance(latest, dict)
        
        # Should have basic OHLCV data
        assert 'open' in latest
        assert 'high' in latest
        assert 'low' in latest
        assert 'close' in latest
        assert 'volume' in latest
        
        # Should have indicator values
        assert 'rsi' in latest
        assert 'sma_20' in latest
        assert 'macd' in latest
        
        # Values should be numbers
        assert isinstance(latest['rsi'], float)
        assert isinstance(latest['close'], float)
        
    def test_empty_data_handling(self):
        """Test indicator functions with empty data"""
        empty_df = pd.DataFrame()
        
        # Functions should handle empty data gracefully
        assert rsi(empty_df).empty
        assert sma(empty_df, 20).empty
        assert ema(empty_df, 20).empty
        
        bb_upper, bb_middle, bb_lower = bbands(empty_df)
        assert bb_upper.empty and bb_middle.empty and bb_lower.empty
        
    def test_insufficient_data_handling(self):
        """Test indicators with insufficient data"""
        # Create very small dataset
        small_df = pd.DataFrame({
            'open': [100, 101],
            'high': [102, 103], 
            'low': [99, 100],
            'close': [101, 102],
            'volume': [1000, 1100]
        })
        
        # RSI with insufficient data should return mostly NaN
        rsi_result = rsi(small_df, period=14)
        assert len(rsi_result) == 2
        
        # Most values should be NaN for insufficient data
        bb_upper, bb_middle, bb_lower = bbands(small_df, period=20)
        assert pd.isna(bb_upper).all()

    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data (covers line 13-14)"""
        small_df = pd.DataFrame({
            'close': [100, 101, 102],  # Only 3 points, need 14 for RSI
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'volume': [1000, 1100, 1200]
        })
        
        rsi_result = rsi(small_df, period=14)
        assert len(rsi_result) == 3
        assert rsi_result.empty or pd.isna(rsi_result).all()

    def test_rsi_error_handling(self):
        """Test RSI with invalid data to trigger exception (covers lines 29-31)"""
        # Create DataFrame with invalid column
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]
        })
        
        # This should trigger exception and return empty series
        rsi_result = rsi(invalid_df, period=14, column='close')  # 'close' column doesn't exist
        assert isinstance(rsi_result, pd.Series)
        assert len(rsi_result) == len(invalid_df)

    def test_sma_error_handling(self):
        """Test SMA with invalid data (covers lines 38-40)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103]
        })
        
        sma_result = sma(invalid_df, period=2, column='close')  # 'close' column doesn't exist
        assert isinstance(sma_result, pd.Series)
        assert len(sma_result) == len(invalid_df)

    def test_ema_error_handling(self):
        """Test EMA with invalid data (covers lines 47-49)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103]
        })
        
        ema_result = ema(invalid_df, period=2, column='close')  # 'close' column doesn't exist
        assert isinstance(ema_result, pd.Series)
        assert len(ema_result) == len(invalid_df)

    def test_bbands_insufficient_data(self):
        """Test Bollinger Bands with insufficient data (covers lines 56-58)"""
        small_df = pd.DataFrame({
            'close': [100, 101],  # Only 2 points, need 20 for BB
            'open': [99, 100],
            'high': [101, 102],
            'low': [98, 99],
            'volume': [1000, 1100]
        })
        
        bb_upper, bb_middle, bb_lower = bbands(small_df, period=20)
        assert len(bb_upper) == 2
        assert len(bb_middle) == 2
        assert len(bb_lower) == 2
        assert pd.isna(bb_upper).all()
        assert pd.isna(bb_middle).all()
        assert pd.isna(bb_lower).all()

    def test_bbands_error_handling(self):
        """Test Bollinger Bands with invalid data (covers lines 68-71)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102] * 10  # 30 points but no 'close' column
        })
        
        bb_upper, bb_middle, bb_lower = bbands(invalid_df, period=10, column='close')
        assert isinstance(bb_upper, pd.Series)
        assert isinstance(bb_middle, pd.Series)  
        assert isinstance(bb_lower, pd.Series)
        assert len(bb_upper) == len(invalid_df)

    def test_atr_error_handling(self):
        """Test ATR with invalid data (covers lines 86-88)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115]
        })
        
        # Missing required columns 'high', 'low', 'close'
        atr_result = atr(invalid_df, period=14)
        assert isinstance(atr_result, pd.Series)
        assert len(atr_result) == len(invalid_df)

    def test_macd_error_handling(self):
        """Test MACD with invalid data (covers lines 104-107)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102] * 10  # 30 points but no 'close' column
        })
        
        macd_line, signal_line, histogram = macd(invalid_df, column='close')
        assert isinstance(macd_line, pd.Series)
        assert isinstance(signal_line, pd.Series)
        assert isinstance(histogram, pd.Series)
        assert len(macd_line) == len(invalid_df)

    def test_stochastic_insufficient_data(self):
        """Test Stochastic with insufficient data (covers lines 113-115)"""
        small_df = pd.DataFrame({
            'high': [102, 103],  # Only 2 points, need 14 for stochastic
            'low': [98, 99],
            'close': [100, 101]
        })
        
        stoch_k, stoch_d = stochastic(small_df, k_period=14)
        assert len(stoch_k) == 2
        assert len(stoch_d) == 2
        assert pd.isna(stoch_k).all()
        assert pd.isna(stoch_d).all()

    def test_stochastic_error_handling(self):
        """Test Stochastic with invalid data (covers lines 125-128)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102] * 10  # 30 points but missing required columns
        })
        
        stoch_k, stoch_d = stochastic(invalid_df, k_period=14)
        assert isinstance(stoch_k, pd.Series)
        assert isinstance(stoch_d, pd.Series)
        assert len(stoch_k) == len(invalid_df)

    def test_volume_sma(self, sample_ohlcv_data):
        """Test Volume Simple Moving Average"""
        df = sample_ohlcv_data
        vol_sma = volume_sma(df, period=10)
        
        # Should have valid values
        valid_vol_sma = vol_sma.dropna()
        assert len(valid_vol_sma) > 0
        assert (valid_vol_sma > 0).all()  # Volume should be positive

    def test_volume_sma_error_handling(self):
        """Test Volume SMA with invalid data (covers lines 135-137)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103, 104]
        })
        
        vol_sma_result = volume_sma(invalid_df, period=3)  # Missing 'volume' column
        assert isinstance(vol_sma_result, pd.Series)
        assert len(vol_sma_result) == len(invalid_df)

    def test_price_change_percent(self, sample_ohlcv_data):
        """Test Price Change Percentage"""
        df = sample_ohlcv_data
        
        # Test 1-period change
        change_1 = price_change_percent(df, periods=1)
        assert len(change_1) == len(df)
        
        # Test 24-period change
        change_24 = price_change_percent(df, periods=24)
        assert len(change_24) == len(df)
        
        # First value should be NaN (no previous value)
        assert pd.isna(change_1.iloc[0])

    def test_price_change_percent_error_handling(self):
        """Test Price Change Percent with invalid data (covers lines 144-146)"""
        invalid_df = pd.DataFrame({
            'invalid_column': [100, 101, 102, 103, 104]
        })
        
        change_result = price_change_percent(invalid_df, periods=1, column='close')  # Missing 'close'
        assert isinstance(change_result, pd.Series)
        assert len(change_result) == len(invalid_df)

    def test_add_all_indicators_empty_df(self):
        """Test add_all_indicators with empty DataFrame (covers line 152-153)"""
        empty_df = pd.DataFrame()
        result = add_all_indicators(empty_df)
        assert result.equals(empty_df)  # Should return same empty DataFrame

    def test_add_all_indicators_insufficient_data(self):
        """Test add_all_indicators with insufficient data (covers line 152-153)"""
        small_df = pd.DataFrame({
            'open': [100, 101, 102],  # Only 3 points, need at least 26
            'high': [102, 103, 104],
            'low': [99, 100, 101],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200]
        })
        
        result = add_all_indicators(small_df)
        assert result.equals(small_df)  # Should return original DataFrame unchanged

    def test_add_all_indicators_error_handling(self):
        """Test add_all_indicators with exception (covers lines 196-198)"""
        # Create DataFrame with valid size but trigger error with invalid operations
        df = pd.DataFrame({
            'open': [100] * 30,
            'high': [102] * 30,
            'low': [99] * 30,
            'close': [101] * 30,
            'volume': [1000] * 30
        })
        
        # Mock an exception by temporarily replacing a function
        import src.metrics.indicators as indicators_module
        original_rsi = indicators_module.rsi
        
        def mock_rsi_error(*args, **kwargs):
            raise ValueError("Mock RSI error")
        
        indicators_module.rsi = mock_rsi_error
        
        try:
            result = add_all_indicators(df)
            # Should return original DataFrame on exception
            assert result.equals(df)
        finally:
            # Restore original function
            indicators_module.rsi = original_rsi

    def test_get_latest_indicators_empty_df(self):
        """Test get_latest_indicators with empty DataFrame (covers lines 204-205)"""
        empty_df = pd.DataFrame()
        result = get_latest_indicators(empty_df)
        assert result == {}  # Should return empty dict

    def test_get_latest_indicators_small_data(self):
        """Test get_latest_indicators with insufficient data for full indicators"""
        # Create DataFrame with < 26 periods (not enough for full MACD)
        df = pd.DataFrame({
            'open': [100, 101],
            'high': [102, 103],
            'low': [99, 100], 
            'close': [101, 102],
            'volume': [1000, 1100]
        })
        
        result = get_latest_indicators(df)
        # Should still return basic data from latest row
        assert result['close'] == 102.0
        assert result['open'] == 101.0
        assert result['volume'] == 1100.0
        # RSI, MACD etc. will have NaN or default values
        assert 'rsi' in result

    def test_get_latest_indicators_error_handling(self):
        """Test get_latest_indicators with exception (covers lines 236-238)"""
        # Create valid DataFrame but force an error
        df = pd.DataFrame({
            'open': [100] * 30,
            'high': [102] * 30,
            'low': [99] * 30,
            'close': [101] * 30,
            'volume': [1000] * 30
        })
        
        # Mock an exception in add_all_indicators
        import src.metrics.indicators as indicators_module
        original_add_all = indicators_module.add_all_indicators
        
        def mock_add_all_error(*args, **kwargs):
            raise ValueError("Mock processing error")
        
        indicators_module.add_all_indicators = mock_add_all_error
        
        try:
            result = get_latest_indicators(df)
            assert result == {}  # Should return empty dict on exception
        finally:
            # Restore original function
            indicators_module.add_all_indicators = original_add_all

    def test_rsi_edge_cases(self):
        """Test RSI with edge cases and boundary conditions"""
        # Test with all price increases
        df_up = pd.DataFrame({
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116]
        })
        result = rsi(df_up)
        # RSI should approach 100 with consistent gains
        assert result.iloc[-1] > 80  # Should be high RSI

        # Test with all price decreases
        df_down = pd.DataFrame({
            'close': [116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        })
        result = rsi(df_down)
        # RSI should approach 0 with consistent losses
        assert result.iloc[-1] < 20  # Should be low RSI

    def test_bollinger_bands_edge_cases(self):
        """Test Bollinger Bands with edge cases"""
        # Test with flat prices (no volatility)
        df_flat = pd.DataFrame({
            'close': [100] * 25  # 25 identical prices
        })
        upper, middle, lower = bbands(df_flat)
        # With no volatility, upper and lower should equal middle
        assert abs(upper.iloc[-1] - middle.iloc[-1]) < 0.001
        assert abs(lower.iloc[-1] - middle.iloc[-1]) < 0.001
        assert middle.iloc[-1] == 100

        # Test with high volatility
        df_volatile = pd.DataFrame({
            'close': [100, 120, 80, 140, 60, 160, 40, 180, 20] + [100] * 16  # High volatility then stable
        })
        upper, middle, lower = bbands(df_volatile)
        # Bands should be wide initially
        initial_width = upper.iloc[24] - lower.iloc[24]
        assert initial_width > 20  # Should have wide bands due to high volatility

    def test_atr_with_gaps(self):
        """Test ATR with price gaps"""
        # Create enough data for ATR (14 periods default)
        base_data = {
            'high': [105, 110, 115, 112, 108, 107, 106, 109, 111, 110, 108, 107, 109, 110, 200, 205],
            'low': [95, 100, 105, 100, 98, 97, 96, 99, 101, 100, 98, 97, 99, 100, 190, 195],
            'close': [100, 105, 110, 106, 103, 102, 101, 104, 106, 105, 103, 102, 104, 105, 195, 200]
        }
        df = pd.DataFrame(base_data)
        result = atr(df)
        
        # ATR should increase after the gap (compare positions with valid data)
        # Since ATR needs 14 periods, valid values start from index 13
        assert not pd.isna(result.iloc[14])  # Should have ATR value at gap
        assert not pd.isna(result.iloc[15])  # Should have ATR value after gap

    def test_macd_crossover_signals(self):
        """Test MACD crossover scenarios"""
        # Create trending data
        trend_data = list(range(100, 150))  # Uptrend
        df = pd.DataFrame({
            'close': trend_data
        })
        macd_line, signal_line, histogram = macd(df)
        
        # In uptrend, MACD should generally be above signal
        assert macd_line.iloc[-1] > signal_line.iloc[-1]
        assert histogram.iloc[-1] > 0

    def test_stochastic_overbought_oversold(self):
        """Test Stochastic in overbought/oversold conditions"""
        # Create data with clear highs and lows (need 14+ periods)
        prices = [100] * 5 + [110] * 5 + [90] * 8  # Base, high, low periods = 18 total
        df = pd.DataFrame({
            'high': [p + 2 for p in prices],
            'low': [p - 2 for p in prices],
            'close': prices
        })
        
        k_percent, d_percent = stochastic(df)
        # Check that we have valid stochastic values (after 14 period lookback)
        assert not pd.isna(k_percent.iloc[-1])  # Should have valid %K
        assert not pd.isna(d_percent.iloc[-1])  # Should have valid %D
        # In the last low period, %K should be relatively low
        assert k_percent.iloc[-1] < 50  # Should be in lower range

    def test_volume_indicators(self):
        """Test volume-based indicators"""
        df = pd.DataFrame({
            'volume': [1000, 1500, 2000, 1200, 800, 1800, 1600, 1400, 1100, 1300] + [1000] * 15
        })
        result = volume_sma(df, period=5)
        expected_avg = np.mean([1000, 1500, 2000, 1200, 800])
        assert abs(result.iloc[4] - expected_avg) < 0.1

    def test_price_change_periods(self):
        """Test price change with different periods"""
        df = pd.DataFrame({
            'close': [100, 102, 104, 106, 108, 110]  # 2% growth each period
        })
        
        # 1-period change
        change_1 = price_change_percent(df, 1)
        assert abs(change_1.iloc[1] - 2.0) < 0.1  # Should be ~2%
        
        # 2-period change
        change_2 = price_change_percent(df, 2)
        assert abs(change_2.iloc[2] - 4.0) < 0.2  # Should be ~4%

    def test_add_all_indicators_comprehensive(self):
        """Test add_all_indicators with comprehensive data validation"""
        # Create sufficient data (50 periods)
        np.random.seed(123)
        dates = pd.date_range('2023-01-01', periods=50, freq='1h')
        
        price = 100
        data = []
        for i in range(50):
            price += np.random.normal(0, 1)  # Random walk
            data.append({
                'open': price - 0.5,
                'high': price + 1,
                'low': price - 1,
                'close': price,
                'volume': 1000 + np.random.normal(0, 100)
            })
        
        df = pd.DataFrame(data, index=dates)
        result = add_all_indicators(df)
        
        # Verify all expected columns are present
        expected_columns = [
            'open', 'high', 'low', 'close', 'volume',
            'rsi', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'bb_upper', 'bb_middle', 'bb_lower',
            'atr', 'macd', 'macd_signal', 'macd_histogram',
            'stoch_k', 'stoch_d', 'volume_sma',
            'price_change_1h', 'price_change_24h'
        ]
        
        for col in expected_columns:
            assert col in result.columns, f"Missing column: {col}"
        
        # Verify indicators have reasonable values (not all NaN)
        assert not result['rsi'].iloc[-10:].isna().all()  # RSI should have values
        assert not result['sma_20'].iloc[-10:].isna().all()  # SMA should have values
        assert not result['macd'].iloc[-10:].isna().all()  # MACD should have values

    def test_indicators_with_missing_columns(self):
        """Test indicators when DataFrame is missing required columns"""
        # Test without 'high' column for ATR
        df_no_high = pd.DataFrame({
            'low': [95, 96, 97],
            'close': [100, 101, 102]
        })
        
        try:
            atr(df_no_high)
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected behavior

        # Test without 'volume' column for volume SMA
        df_no_volume = pd.DataFrame({
            'close': [100, 101, 102]
        })
        
        try:
            volume_sma(df_no_volume)
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected behavior

    def test_macd_exception_handling(self):
        """Test MACD exception handling (covers lines 104-107)"""
        # Force an exception by mocking ema function to fail
        import src.metrics.indicators as indicators_module
        original_ema = indicators_module.ema
        
        def mock_ema_error(*args, **kwargs):
            raise ValueError("Mock EMA error")
        
        indicators_module.ema = mock_ema_error
        
        try:
            df = pd.DataFrame({'close': [100, 101, 102]})
            macd_line, signal_line, histogram = macd(df)
            
            # Should return empty series on error
            assert len(macd_line) == len(df)
            assert len(signal_line) == len(df)
            assert len(histogram) == len(df)
            assert macd_line.isna().all()  # All values should be NaN
            assert signal_line.isna().all()
            assert histogram.isna().all()
        finally:
            # Restore original function
            indicators_module.ema = original_ema

    def test_get_latest_indicators_empty_after_add_all(self):
        """Test get_latest_indicators when add_all_indicators returns empty (covers line 210)"""
        # Mock add_all_indicators to return empty DataFrame
        import src.metrics.indicators as indicators_module
        original_add_all = indicators_module.add_all_indicators
        
        def mock_add_all_empty(*args, **kwargs):
            return pd.DataFrame()  # Return empty DataFrame
        
        indicators_module.add_all_indicators = mock_add_all_empty
        
        try:
            df = pd.DataFrame({'close': [100, 101, 102]})
            result = get_latest_indicators(df)
            assert result == {}  # Should return empty dict
        finally:
            # Restore original function
            indicators_module.add_all_indicators = original_add_all


if __name__ == "__main__":
    pytest.main([__file__])