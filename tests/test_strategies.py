"""
Tests for trading strategies
"""

import pytest
import pandas as pd
import numpy as np

from src.strategies.sma_cross import SmaCross, EmaBreakout, RSIMeanReversion


class TestStrategies:
    """Test trading strategy implementations"""
    
    @pytest.fixture
    def sample_ohlcv(self):
        """Generate sample OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='1h')
        
        # Generate trending price data
        np.random.seed(42)
        trend = np.linspace(100, 120, 200)
        noise = np.random.randn(200) * 2
        price = trend + noise
        
        df = pd.DataFrame({
            'open': price * (1 + np.random.randn(200) * 0.001),
            'high': price * (1 + np.abs(np.random.randn(200)) * 0.002),
            'low': price * (1 - np.abs(np.random.randn(200)) * 0.002),
            'close': price,
            'volume': np.random.randint(1000000, 10000000, 200)
        }, index=dates)
        
        return df
    
    @pytest.fixture
    def ranging_ohlcv(self):
        """Generate ranging market data"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='1h')
        
        # Generate oscillating price data
        np.random.seed(42)
        t = np.linspace(0, 4*np.pi, 200)
        price = 100 + 10 * np.sin(t) + np.random.randn(200) * 2
        
        df = pd.DataFrame({
            'open': price * (1 + np.random.randn(200) * 0.001),
            'high': price * (1 + np.abs(np.random.randn(200)) * 0.002),
            'low': price * (1 - np.abs(np.random.randn(200)) * 0.002),
            'close': price,
            'volume': np.random.randint(1000000, 10000000, 200)
        }, index=dates)
        
        return df


class TestSmaCross:
    """Test SMA Cross strategy"""
    
    def test_initialization(self):
        """Test strategy initialization"""
        strategy = SmaCross()
        assert strategy.name == "sma_cross"
        assert strategy.default_params['fast'] == 10
        assert strategy.default_params['slow'] == 30
    
    def test_signal_generation_cross_mode(self, sample_ohlcv):
        """Test signal generation in cross mode"""
        strategy = SmaCross()
        params = {'fast': 10, 'slow': 30, 'signal_mode': 'cross'}
        
        signals = strategy.generate_signals(sample_ohlcv, params)
        
        # Check signal types
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_ohlcv)
        assert set(signals.unique()).issubset({-1, 0, 1})
        
        # In cross mode, signals should be sparse (only at crossovers)
        non_zero_signals = signals[signals != 0]
        assert len(non_zero_signals) < len(signals) * 0.2  # Less than 20% should be signals
    
    def test_signal_generation_position_mode(self, sample_ohlcv):
        """Test signal generation in position mode"""
        strategy = SmaCross()
        params = {'fast': 10, 'slow': 30, 'signal_mode': 'position'}
        
        signals = strategy.generate_signals(sample_ohlcv, params)
        
        # In position mode, should have continuous signals
        assert set(signals.unique()).issubset({-1, 1})
        assert 0 not in signals.unique()  # No neutral signals
    
    def test_parameter_validation(self):
        """Test parameter validation"""
        strategy = SmaCross()
        
        # Invalid params (fast >= slow)
        invalid_params = {'fast': 30, 'slow': 20}
        with pytest.raises(ValueError):
            strategy.generate_signals(pd.DataFrame(), invalid_params)
    
    def test_trending_market_performance(self, sample_ohlcv):
        """Test that SMA cross performs well in trending markets"""
        strategy = SmaCross()
        params = {'fast': 10, 'slow': 30, 'signal_mode': 'cross'}
        
        signals = strategy.generate_signals(sample_ohlcv, params)
        
        # In uptrend, should have more buy signals early
        first_half = signals[:len(signals)//2]
        buy_signals = first_half[first_half == 1]
        assert len(buy_signals) > 0


class TestEmaBreakout:
    """Test EMA Breakout strategy"""
    
    def test_initialization(self):
        """Test strategy initialization"""
        strategy = EmaBreakout()
        assert strategy.name == "ema_breakout"
        assert strategy.default_params['ema_period'] == 20
        assert strategy.default_params['atr_period'] == 14
    
    def test_signal_generation(self, sample_ohlcv):
        """Test signal generation"""
        strategy = EmaBreakout()
        params = {
            'ema_period': 20,
            'atr_period': 14,
            'atr_multiplier': 2.0,
            'use_volume': False
        }
        
        signals = strategy.generate_signals(sample_ohlcv, params)
        
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_ohlcv)
        assert set(signals.unique()).issubset({-1, 0, 1})
    
    def test_volume_filter(self, sample_ohlcv):
        """Test volume filter functionality"""
        strategy = EmaBreakout()
        
        # Without volume filter
        params_no_volume = {
            'ema_period': 20,
            'atr_period': 14,
            'atr_multiplier': 2.0,
            'use_volume': False
        }
        signals_no_volume = strategy.generate_signals(sample_ohlcv, params_no_volume)
        
        # With volume filter
        params_volume = params_no_volume.copy()
        params_volume['use_volume'] = True
        signals_volume = strategy.generate_signals(sample_ohlcv, params_volume)
        
        # Volume filter should reduce number of signals
        assert (signals_volume != 0).sum() <= (signals_no_volume != 0).sum()
    
    def test_atr_bands(self, sample_ohlcv):
        """Test that ATR bands adjust with volatility"""
        strategy = EmaBreakout()
        
        # Tight bands
        params_tight = {
            'ema_period': 20,
            'atr_period': 14,
            'atr_multiplier': 1.0,
            'use_volume': False
        }
        signals_tight = strategy.generate_signals(sample_ohlcv, params_tight)
        
        # Wide bands
        params_wide = params_tight.copy()
        params_wide['atr_multiplier'] = 3.0
        signals_wide = strategy.generate_signals(sample_ohlcv, params_wide)
        
        # Tight bands should generate more signals
        assert (signals_tight != 0).sum() >= (signals_wide != 0).sum()


class TestRSIMeanReversion:
    """Test RSI Mean Reversion strategy"""
    
    def test_initialization(self):
        """Test strategy initialization"""
        strategy = RSIMeanReversion()
        assert strategy.name == "rsi_reversion"
        assert strategy.default_params['rsi_period'] == 14
        assert strategy.default_params['oversold'] == 30
        assert strategy.default_params['overbought'] == 70
    
    def test_rsi_calculation(self):
        """Test RSI calculation"""
        strategy = RSIMeanReversion()
        
        # Create simple price series
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109])
        rsi = strategy.calculate_rsi(prices, period=5)
        
        # RSI should be between 0 and 100
        assert all((rsi >= 0) & (rsi <= 100))
    
    def test_signal_generation_basic(self, ranging_ohlcv):
        """Test basic signal generation"""
        strategy = RSIMeanReversion()
        params = {
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70,
            'exit_at_mean': False
        }
        
        signals = strategy.generate_signals(ranging_ohlcv, params)
        
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(ranging_ohlcv)
        assert set(signals.unique()).issubset({-1, 0, 1})
    
    def test_exit_at_mean(self, ranging_ohlcv):
        """Test exit at mean functionality"""
        strategy = RSIMeanReversion()
        
        # Without exit at mean
        params_no_exit = {
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70,
            'exit_at_mean': False
        }
        signals_no_exit = strategy.generate_signals(ranging_ohlcv, params_no_exit)
        
        # With exit at mean
        params_exit = params_no_exit.copy()
        params_exit['exit_at_mean'] = True
        signals_exit = strategy.generate_signals(ranging_ohlcv, params_exit)
        
        # Should have different signal patterns
        assert not signals_no_exit.equals(signals_exit)
    
    def test_ranging_market_performance(self, ranging_ohlcv):
        """Test that RSI reversion works well in ranging markets"""
        strategy = RSIMeanReversion()
        params = {
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70,
            'exit_at_mean': True
        }
        
        signals = strategy.generate_signals(ranging_ohlcv, params)
        
        # Should generate multiple buy/sell signals in ranging market
        buy_signals = signals[signals == 1]
        sell_signals = signals[signals == -1]
        
        assert len(buy_signals) > 2
        assert len(sell_signals) > 2
    
    def test_oversold_overbought_levels(self, sample_ohlcv):
        """Test different oversold/overbought levels"""
        strategy = RSIMeanReversion()
        
        # Tight levels
        params_tight = {
            'rsi_period': 14,
            'oversold': 40,
            'overbought': 60,
            'exit_at_mean': False
        }
        signals_tight = strategy.generate_signals(sample_ohlcv, params_tight)
        
        # Wide levels
        params_wide = {
            'rsi_period': 14,
            'oversold': 20,
            'overbought': 80,
            'exit_at_mean': False
        }
        signals_wide = strategy.generate_signals(sample_ohlcv, params_wide)
        
        # Tight levels should generate more signals
        assert (signals_tight != 0).sum() >= (signals_wide != 0).sum()