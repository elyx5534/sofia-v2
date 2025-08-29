"""
Tests for backtest runner
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal

from src.backtest.runner import BacktestRunner


class TestBacktestRunner:
    """Test backtest runner functionality"""
    
    @pytest.fixture
    def runner(self):
        """Create backtest runner instance"""
        return BacktestRunner(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005")
        )
    
    @pytest.fixture
    def sample_ohlcv(self):
        """Generate sample OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1h')
        
        # Generate synthetic price data
        np.random.seed(42)
        returns = np.random.randn(100) * 0.01
        price = 100 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'open': price * (1 + np.random.randn(100) * 0.001),
            'high': price * (1 + np.abs(np.random.randn(100)) * 0.002),
            'low': price * (1 - np.abs(np.random.randn(100)) * 0.002),
            'close': price,
            'volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)
        
        return df
    
    @pytest.fixture
    def sample_signals(self, sample_ohlcv):
        """Generate sample trading signals"""
        signals = pd.Series(0, index=sample_ohlcv.index)
        
        # Generate some buy/sell signals
        signals.iloc[10] = 1   # Buy
        signals.iloc[30] = -1  # Sell
        signals.iloc[50] = 1   # Buy
        signals.iloc[70] = -1  # Sell
        
        return signals
    
    def test_runner_initialization(self, runner):
        """Test runner initializes correctly"""
        assert runner.initial_capital == Decimal("10000")
        assert runner.fee_rate == Decimal("0.001")
        assert runner.slippage_rate == Decimal("0.0005")
        assert runner.use_stops == True
    
    def test_run_backtest_basic(self, runner, sample_ohlcv, sample_signals):
        """Test basic backtest execution"""
        metrics, equity_df, trades_df, logs = runner.run_backtest(
            sample_ohlcv, sample_signals
        )
        
        # Check return types
        assert isinstance(metrics, dict)
        assert isinstance(equity_df, pd.DataFrame)
        assert isinstance(trades_df, pd.DataFrame)
        assert isinstance(logs, str)
        
        # Check metrics
        assert 'total_return' in metrics
        assert 'cagr' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        assert 'total_trades' in metrics
        
        # Check equity curve
        assert not equity_df.empty
        assert 'equity' in equity_df.columns
        assert 'capital' in equity_df.columns
        assert 'position_value' in equity_df.columns
        
        # Check trades
        assert len(trades_df) == 4  # 2 buys + 2 sells
        buy_trades = trades_df[trades_df['type'] == 'BUY']
        sell_trades = trades_df[trades_df['type'] == 'SELL']
        assert len(buy_trades) == 2
        assert len(sell_trades) == 2
    
    def test_fees_and_slippage(self, runner, sample_ohlcv, sample_signals):
        """Test that fees and slippage are applied correctly"""
        metrics, equity_df, trades_df, _ = runner.run_backtest(
            sample_ohlcv, sample_signals
        )
        
        # Check that fees are recorded
        assert all(trades_df['fee'] > 0)
        
        # Check that slippage affects execution price
        for _, trade in trades_df.iterrows():
            idx = sample_ohlcv.index.get_loc(trade['timestamp'])
            market_price = sample_ohlcv.iloc[idx]['close']
            
            if trade['type'] == 'BUY':
                # Buy price should be higher due to slippage
                assert trade['price'] > market_price
            else:
                # Sell price should be lower due to slippage
                assert trade['price'] < market_price
    
    def test_stop_loss(self, runner, sample_ohlcv):
        """Test stop loss functionality"""
        # Create signal to buy and hold
        signals = pd.Series(0, index=sample_ohlcv.index)
        signals.iloc[10] = 1  # Buy signal
        
        # Artificially create a drawdown
        sample_ohlcv.loc[sample_ohlcv.index[15:20], 'low'] = sample_ohlcv.iloc[10]['close'] * 0.94
        
        metrics, _, trades_df, logs = runner.run_backtest(
            sample_ohlcv, signals, stop_loss=0.05  # 5% stop loss
        )
        
        # Check that stop loss was triggered
        assert 'Stop loss triggered' in logs
        assert len(trades_df[trades_df['type'] == 'SELL']) > 0
    
    def test_take_profit(self, runner, sample_ohlcv):
        """Test take profit functionality"""
        # Create signal to buy and hold
        signals = pd.Series(0, index=sample_ohlcv.index)
        signals.iloc[10] = 1  # Buy signal
        
        # Artificially create a profit spike
        sample_ohlcv.loc[sample_ohlcv.index[15:20], 'high'] = sample_ohlcv.iloc[10]['close'] * 1.11
        
        metrics, _, trades_df, logs = runner.run_backtest(
            sample_ohlcv, signals, take_profit=0.10  # 10% take profit
        )
        
        # Check that take profit was triggered
        assert 'Take profit triggered' in logs
        assert len(trades_df[trades_df['type'] == 'SELL']) > 0
    
    def test_metrics_calculation(self, runner, sample_ohlcv, sample_signals):
        """Test metrics calculation accuracy"""
        metrics, equity_df, trades_df, _ = runner.run_backtest(
            sample_ohlcv, sample_signals
        )
        
        # Test total return calculation
        initial = float(runner.initial_capital)
        final = equity_df['equity'].iloc[-1]
        expected_return = (final - initial) / initial * 100
        assert abs(metrics['total_return'] - expected_return) < 0.01
        
        # Test max drawdown
        rolling_max = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - rolling_max) / rolling_max * 100
        expected_max_dd = abs(drawdown.min())
        assert abs(metrics['max_drawdown'] - expected_max_dd) < 0.01
        
        # Test win rate
        sell_trades = trades_df[trades_df['type'] == 'SELL']
        if not sell_trades.empty and 'pnl' in sell_trades.columns:
            winning_trades = sell_trades[sell_trades['pnl'] > 0]
            expected_win_rate = len(winning_trades) / len(sell_trades) * 100
            assert abs(metrics['win_rate'] - expected_win_rate) < 0.01
    
    def test_empty_signals(self, runner, sample_ohlcv):
        """Test with no trading signals"""
        signals = pd.Series(0, index=sample_ohlcv.index)
        
        metrics, equity_df, trades_df, _ = runner.run_backtest(
            sample_ohlcv, signals
        )
        
        # No trades should be executed
        assert trades_df.empty
        assert metrics['total_trades'] == 0
        assert metrics['total_return'] == 0
        
        # Equity should remain constant
        assert all(equity_df['equity'] == float(runner.initial_capital))
    
    def test_position_sizing(self, runner, sample_ohlcv, sample_signals):
        """Test position sizing parameter"""
        # Run with 50% position size
        metrics, equity_df, trades_df, _ = runner.run_backtest(
            sample_ohlcv, sample_signals, position_size=0.5
        )
        
        # Check that positions use only 50% of capital
        buy_trades = trades_df[trades_df['type'] == 'BUY']
        for _, trade in buy_trades.iterrows():
            position_value = trade['price'] * trade['quantity']
            # Position value should be approximately 50% of available capital
            assert position_value < float(runner.initial_capital) * 0.6  # Allow for fees