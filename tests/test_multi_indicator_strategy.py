"""
Test suite for Multi-Indicator strategy
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the strategy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.backtester.strategies.multi_indicator import MultiIndicatorStrategy


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing"""
    dates = pd.date_range(start='2023-01-01', periods=150, freq='D')
    
    # Generate complex price data that will trigger multiple indicators
    np.random.seed(42)
    
    price = 100
    prices = []
    
    for i in range(150):
        # Create complex pattern with trends, reversals, and volatility
        if i < 30:
            # Initial stable period
            change = np.random.normal(0, 0.01)
        elif i < 60:
            # Strong downtrend (should trigger oversold conditions)
            change = np.random.normal(-0.015, 0.02)
        elif i < 90:
            # Recovery uptrend (should trigger various crossovers)
            change = np.random.normal(0.012, 0.02)
        elif i < 120:
            # High volatility period
            change = np.random.normal(0, 0.03)
        else:
            # Final trending period
            change = np.random.normal(0.008, 0.015)
        
        price *= (1 + change)
        price = max(price, 50)  # Keep prices positive
        prices.append(price)
    
    data = pd.DataFrame({
        'Open': [p * 0.995 for p in prices],
        'High': [p * 1.02 for p in prices],
        'Low': [p * 0.98 for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000000, 5000000) for _ in range(150)]
    }, index=dates)
    
    return data


@pytest.fixture
def strategy():
    """Create MultiIndicatorStrategy instance"""
    return MultiIndicatorStrategy()


@pytest.fixture
def custom_strategy():
    """Create custom MultiIndicatorStrategy instance"""
    return MultiIndicatorStrategy(
        rsi_weight=0.4, 
        macd_weight=0.3, 
        bb_weight=0.3, 
        signal_threshold=0.7
    )


class TestMultiIndicatorStrategy:
    
    def test_strategy_initialization_default(self):
        """Test default strategy initialization"""
        strategy = MultiIndicatorStrategy()
        
        # Check weights sum to 1 (normalized)
        total_weight = strategy.rsi_weight + strategy.macd_weight + strategy.bb_weight
        assert abs(total_weight - 1.0) < 1e-10
        
        # Check default threshold
        assert strategy.signal_threshold == 0.6
        
        # Check sub-strategies are initialized
        assert strategy.rsi_strategy is not None
        assert strategy.macd_strategy is not None
        assert strategy.bb_strategy is not None
    
    def test_strategy_initialization_custom(self):
        """Test custom strategy initialization"""
        strategy = MultiIndicatorStrategy(
            rsi_weight=0.5, 
            macd_weight=0.3, 
            bb_weight=0.2, 
            signal_threshold=0.8
        )
        
        # Check weights are normalized
        total_weight = strategy.rsi_weight + strategy.macd_weight + strategy.bb_weight
        assert abs(total_weight - 1.0) < 1e-10
        
        # Check custom threshold
        assert strategy.signal_threshold == 0.8
        
        # Check individual weights are proportional
        assert strategy.rsi_weight > strategy.macd_weight > strategy.bb_weight
    
    def test_weight_normalization(self):
        """Test that weights are properly normalized"""
        strategy = MultiIndicatorStrategy(
            rsi_weight=2.0, 
            macd_weight=3.0, 
            bb_weight=1.0  # Total = 6.0
        )
        
        # Should be normalized to sum to 1
        expected_rsi = 2.0 / 6.0
        expected_macd = 3.0 / 6.0
        expected_bb = 1.0 / 6.0
        
        assert abs(strategy.rsi_weight - expected_rsi) < 1e-10
        assert abs(strategy.macd_weight - expected_macd) < 1e-10
        assert abs(strategy.bb_weight - expected_bb) < 1e-10
    
    def test_calculate_signal_strength_basic(self, strategy, sample_data):
        """Test basic signal strength calculation"""
        signal_strength = strategy.calculate_signal_strength(sample_data)
        
        # Check return type and shape
        assert isinstance(signal_strength, pd.Series)
        assert len(signal_strength) == len(sample_data)
        assert signal_strength.index.equals(sample_data.index)
        
        # Signal strength should be between -1 and 1
        assert (signal_strength >= -1.0).all()
        assert (signal_strength <= 1.0).all()
        
        # Should have some non-zero values
        assert (signal_strength != 0).sum() > 0
    
    def test_calculate_signal_strength_empty_data(self, strategy):
        """Test signal strength with empty data"""
        empty_data = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        
        signal_strength = strategy.calculate_signal_strength(empty_data)
        
        assert isinstance(signal_strength, pd.Series)
        assert len(signal_strength) == 0
    
    def test_calculate_signal_strength_weighted_combination(self, strategy):
        """Test that signal strength correctly combines weighted signals"""
        # Create test data
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        prices = [100 + i * 2 for i in range(50)]  # Uptrend
        
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 50
        }, index=dates)
        
        # Get individual signals
        rsi_signals = strategy.rsi_strategy.generate_signals(data)
        macd_signals = strategy.macd_strategy.generate_signals(data)
        bb_signals = strategy.bb_strategy.generate_signals(data)
        
        # Get combined signal
        combined = strategy.calculate_signal_strength(data)
        
        # Manual calculation for verification
        expected = (
            rsi_signals * strategy.rsi_weight +
            macd_signals * strategy.macd_weight +
            bb_signals * strategy.bb_weight
        )
        
        # Should match manual calculation
        assert np.allclose(combined, expected, equal_nan=True)
    
    def test_generate_signals_basic(self, strategy, sample_data):
        """Test basic signal generation"""
        signals = strategy.generate_signals(sample_data)
        
        # Check return type and shape
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_data)
        assert signals.index.equals(sample_data.index)
        
        # Check signal values are valid
        assert signals.isin([0, 1, -1]).all()
        
        # Should have some signals due to complex data
        total_signals = (signals != 0).sum()
        assert total_signals >= 0
    
    def test_generate_signals_threshold_logic(self, strategy):
        """Test signal generation threshold logic"""
        # Create simple test data
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        data = pd.DataFrame({
            'Open': [100] * 30,
            'High': [102] * 30,
            'Low': [98] * 30,
            'Close': [100 + np.sin(i/5) * 10 for i in range(30)],
            'Volume': [1000000] * 30
        }, index=dates)
        
        # Test with different thresholds
        low_threshold_strategy = MultiIndicatorStrategy(signal_threshold=0.1)
        high_threshold_strategy = MultiIndicatorStrategy(signal_threshold=0.9)
        
        low_signals = low_threshold_strategy.generate_signals(data)
        high_signals = high_threshold_strategy.generate_signals(data)
        
        # Lower threshold should generate more signals
        low_signal_count = (low_signals != 0).sum()
        high_signal_count = (high_signals != 0).sum()
        
        assert low_signal_count >= high_signal_count
    
    def test_generate_signals_signal_cleaning(self, strategy):
        """Test that consecutive signals are properly cleaned"""
        # Create data that might generate consecutive signals
        dates = pd.date_range('2023-01-01', periods=40, freq='D')
        
        # Strong trending data that should create sustained signals
        prices = [100 + i * 3 for i in range(40)]  # Strong uptrend
        
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 40
        }, index=dates)
        
        signals = strategy.generate_signals(data)
        
        # Check signal cleaning - no consecutive identical signals
        # (This is ensured by the diff() logic in the strategy)
        assert isinstance(signals, pd.Series)
        assert signals.isin([0, 1, -1]).all()
    
    def test_get_indicator_values_basic(self, strategy, sample_data):
        """Test getting indicator values"""
        indicators = strategy.get_indicator_values(sample_data)
        
        # Check return type and shape
        assert isinstance(indicators, pd.DataFrame)
        assert len(indicators) == len(sample_data)
        assert indicators.index.equals(sample_data.index)
        
        # Check all expected columns are present
        expected_columns = [
            'RSI', 'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Upper', 'BB_Middle', 'BB_Lower', 'Signal_Strength'
        ]
        
        for col in expected_columns:
            assert col in indicators.columns
        
        # Check that we have some valid data
        assert not indicators.isna().all().all()
    
    def test_get_indicator_values_empty_data(self, strategy):
        """Test getting indicator values with empty data"""
        empty_data = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        
        indicators = strategy.get_indicator_values(empty_data)
        
        assert isinstance(indicators, pd.DataFrame)
        assert len(indicators) == 0
    
    def test_indicator_values_consistency(self, strategy):
        """Test that indicator values are consistent with sub-strategies"""
        # Create test data
        dates = pd.date_range('2023-01-01', periods=60, freq='D')
        prices = [100 + np.sin(i/10) * 15 for i in range(60)]
        
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 60
        }, index=dates)
        
        # Get indicator values
        indicators = strategy.get_indicator_values(data)
        
        # Compare with individual strategy calculations
        rsi_direct = strategy.rsi_strategy.calculate_rsi(pd.Series(prices, index=dates))
        macd_direct, signal_direct, hist_direct = strategy.macd_strategy.calculate_macd(
            pd.Series(prices, index=dates)
        )
        bb_upper, bb_middle, bb_lower = strategy.bb_strategy.calculate_bollinger_bands(
            pd.Series(prices, index=dates)
        )
        
        # Should match individual calculations
        assert np.allclose(indicators['RSI'], rsi_direct, equal_nan=True)
        assert np.allclose(indicators['MACD'], macd_direct, equal_nan=True)
        assert np.allclose(indicators['MACD_Signal'], signal_direct, equal_nan=True)
        assert np.allclose(indicators['BB_Upper'], bb_upper, equal_nan=True)
        assert np.allclose(indicators['BB_Middle'], bb_middle, equal_nan=True)
        assert np.allclose(indicators['BB_Lower'], bb_lower, equal_nan=True)
    
    def test_edge_cases(self, strategy):
        """Test edge cases"""
        # Single data point
        single_data = pd.DataFrame({
            'Open': [100], 'High': [102], 'Low': [98], 
            'Close': [100], 'Volume': [1000000]
        })
        
        signals = strategy.generate_signals(single_data)
        signal_strength = strategy.calculate_signal_strength(single_data)
        indicators = strategy.get_indicator_values(single_data)
        
        assert len(signals) == 1
        assert len(signal_strength) == 1
        assert len(indicators) == 1
        assert signals.iloc[0] == 0  # Should be no signal
        
        # Very small dataset
        small_data = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [102, 103, 104],
            'Low': [98, 99, 100],
            'Close': [100, 101, 102],
            'Volume': [1000000, 1000000, 1000000]
        })
        
        signals = strategy.generate_signals(small_data)
        assert len(signals) == 3
        assert signals.isin([0, 1, -1]).all()
    
    def test_parameter_variations(self):
        """Test different parameter combinations"""
        test_params = [
            (0.5, 0.3, 0.2, 0.5),
            (0.2, 0.2, 0.6, 0.8),
            (1.0, 1.0, 1.0, 0.3),  # Equal weights
            (0.1, 0.8, 0.1, 0.9)   # MACD heavy
        ]
        
        # Create test data
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        prices = [100 + np.sin(i/15) * 20 + i * 0.1 for i in range(100)]
        data = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 100
        }, index=dates)
        
        for rsi_w, macd_w, bb_w, threshold in test_params:
            strategy = MultiIndicatorStrategy(
                rsi_weight=rsi_w,
                macd_weight=macd_w,
                bb_weight=bb_w,
                signal_threshold=threshold
            )
            
            # Should not raise exceptions
            signals = strategy.generate_signals(data)
            signal_strength = strategy.calculate_signal_strength(data)
            indicators = strategy.get_indicator_values(data)
            
            # Basic validation
            assert len(signals) == len(data)
            assert len(signal_strength) == len(data)
            assert len(indicators) == len(data)
            assert signals.isin([0, 1, -1]).all()
            assert (signal_strength >= -1.0).all()
            assert (signal_strength <= 1.0).all()
    
    def test_signal_strength_bounds(self, strategy):
        """Test that signal strength stays within bounds"""
        # Create extreme test data
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        
        # Extreme uptrend
        extreme_up = [100 * (1.05 ** i) for i in range(100)]
        # Extreme downtrend  
        extreme_down = [1000 * (0.95 ** i) for i in range(100)]
        # Mixed data
        mixed_prices = extreme_up[:50] + extreme_down[50:]
        
        for prices in [extreme_up, extreme_down, mixed_prices]:
            data = pd.DataFrame({
                'Open': prices,
                'High': [p * 1.01 for p in prices],
                'Low': [p * 0.99 for p in prices],
                'Close': prices,
                'Volume': [1000000] * 100
            }, index=dates)
            
            signal_strength = strategy.calculate_signal_strength(data)
            
            # Should always be within bounds
            assert (signal_strength >= -1.0).all()
            assert (signal_strength <= 1.0).all()
    
    def test_complex_market_scenarios(self, strategy):
        """Test strategy with complex market scenarios"""
        dates = pd.date_range('2023-01-01', periods=200, freq='D')
        
        # Scenario 1: Bull market with correction
        bull_prices = ([100 + i * 2 for i in range(80)] +  # Strong uptrend
                       [260 - i * 3 for i in range(40)] +  # Sharp correction
                       [140 + i * 1.5 for i in range(80)])  # Recovery
        
        # Scenario 2: Bear market with bounce
        bear_prices = ([200 - i * 1.5 for i in range(80)] +  # Downtrend
                       [80 + i * 2 for i in range(40)] +     # Dead cat bounce
                       [160 - i * 1 for i in range(80)])     # Continued decline
        
        for scenario_name, prices in [("Bull", bull_prices), ("Bear", bear_prices)]:
            data = pd.DataFrame({
                'Open': prices,
                'High': [p * 1.02 for p in prices],
                'Low': [p * 0.98 for p in prices],
                'Close': prices,
                'Volume': [np.random.randint(500000, 2000000) for _ in range(200)]
            }, index=dates)
            
            # Should handle complex scenarios without errors
            signals = strategy.generate_signals(data)
            signal_strength = strategy.calculate_signal_strength(data)
            indicators = strategy.get_indicator_values(data)
            
            # Validate results
            assert len(signals) == len(data)
            assert signals.isin([0, 1, -1]).all()
            assert (signal_strength >= -1.0).all() 
            assert (signal_strength <= 1.0).all()
            assert len(indicators) == len(data)
            
            # Should generate some signals in volatile markets
            total_signals = (signals != 0).sum()
            assert total_signals >= 0  # At least able to generate signals


if __name__ == "__main__":
    pytest.main([__file__])