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
    add_all_indicators, get_latest_indicators
)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2023-01-01', periods=100, freq='1H')
    
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
        

if __name__ == "__main__":
    pytest.main([__file__])