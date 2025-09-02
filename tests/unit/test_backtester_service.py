"""Unit tests for Backtester service."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestBacktesterService:
    """Test Backtester service with synthetic data."""
    
    def create_synthetic_data(self, periods=100):
        """Create synthetic OHLCV data with sin wave pattern."""
        dates = pd.date_range('2024-01-01', periods=periods, freq='1h')
        base_price = 50000
        amplitude = 1000
        
        # Create sin wave pattern
        prices = base_price + amplitude * np.sin(np.linspace(0, 4*np.pi, periods))
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices + np.random.randn(periods) * 10,
            'high': prices + abs(np.random.randn(periods) * 50) + 50,
            'low': prices - abs(np.random.randn(periods) * 50) - 50,
            'close': prices + np.random.randn(periods) * 10,
            'volume': np.random.uniform(100, 1000, periods)
        })
        
        return df
    
    @patch('src.services.backtester.datahub')
    def test_run_backtest_basic(self, mock_datahub):
        """Test basic backtest run with SMA strategy."""
        from src.services.backtester import Backtester, BacktestConfig
        
        # Mock data fetching
        synthetic_data = self.create_synthetic_data(200)
        mock_datahub.get_ohlcv.return_value = synthetic_data.values.tolist()
        
        backtester = Backtester()
        result = backtester.run_backtest(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-08",
            strategy="sma_cross",
            params={"fast_period": 10, "slow_period": 20}
        )
        
        assert 'run_id' in result
        assert 'equity_curve' in result
        assert 'drawdown' in result
        assert 'trades' in result
        assert 'stats' in result
        
        # Verify stats keys
        stats = result['stats']
        assert 'total_return' in stats
        assert 'sharpe_ratio' in stats
        assert 'max_drawdown' in stats
        assert 'win_rate' in stats
    
    @patch('src.services.backtester.datahub')
    def test_backtest_with_fees_and_slippage(self, mock_datahub):
        """Test backtest with fees and slippage applied."""
        from src.services.backtester import Backtester, BacktestConfig
        
        synthetic_data = self.create_synthetic_data(100)
        mock_datahub.get_ohlcv.return_value = synthetic_data.values.tolist()
        
        config = BacktestConfig(
            initial_capital=10000,
            fee_rate=0.001,  # 0.1%
            slippage=0.0005  # 0.05%
        )
        
        backtester = Backtester()
        result = backtester.run_backtest(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-04",
            strategy="sma_cross",
            params={"fast_period": 5, "slow_period": 10},
            config=config
        )
        
        # Verify fees are applied in trades
        if result['trades']:
            for trade in result['trades']:
                if 'fee' in trade:
                    assert trade['fee'] > 0
    
    @patch('src.services.backtester.datahub')
    def test_grid_search_optimization(self, mock_datahub):
        """Test grid search optimization."""
        from src.services.backtester import Backtester
        
        synthetic_data = self.create_synthetic_data(150)
        mock_datahub.get_ohlcv.return_value = synthetic_data.values.tolist()
        
        backtester = Backtester()
        result = backtester.run_grid_search(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-05",
            strategy="sma_cross",
            param_grid={
                "fast_period": [5, 10],
                "slow_period": [15, 20]
            }
        )
        
        assert 'best_params' in result
        assert 'best_sharpe' in result
        assert 'all_results' in result
        
        # Should test 2x2 = 4 combinations
        assert len(result['all_results']) == 4
        
        # Best params should be one of the combinations
        best = result['best_params']
        assert best['fast_period'] in [5, 10]
        assert best['slow_period'] in [15, 20]
    
    @patch('src.services.backtester.datahub')
    def test_genetic_algorithm_optimization(self, mock_datahub):
        """Test genetic algorithm optimization."""
        from src.services.backtester import Backtester
        
        synthetic_data = self.create_synthetic_data(150)
        mock_datahub.get_ohlcv.return_value = synthetic_data.values.tolist()
        
        backtester = Backtester()
        result = backtester.run_genetic_algorithm(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-05",
            strategy="sma_cross",
            param_ranges={
                "fast_period": [5, 15],
                "slow_period": [15, 30]
            },
            population_size=8,
            generations=3,
            elite_size=2
        )
        
        assert 'best_params' in result
        assert 'best_fitness' in result
        assert 'generation_history' in result
        
        # Should have 3 generations
        assert len(result['generation_history']) == 3
        
        # Best params should be within ranges
        best = result['best_params']
        assert 5 <= best['fast_period'] <= 15
        assert 15 <= best['slow_period'] <= 30
    
    @patch('src.services.backtester.datahub')
    def test_walk_forward_optimization(self, mock_datahub):
        """Test walk-forward optimization."""
        from src.services.backtester import Backtester
        
        synthetic_data = self.create_synthetic_data(300)
        mock_datahub.get_ohlcv.return_value = synthetic_data.values.tolist()
        
        backtester = Backtester()
        result = backtester.run_walk_forward(
            symbol="BTC/USDT",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-01-12",
            strategy="sma_cross",
            param_grid={
                "fast_period": [5, 10],
                "slow_period": [15, 20]
            },
            n_splits=3,
            train_ratio=0.7
        )
        
        assert 'splits' in result
        assert 'oos_sharpe' in result
        assert 'best_params_per_split' in result
        
        # Should have 3 splits
        assert len(result['splits']) == 3
        
        # Each split should have in-sample and out-of-sample results
        for split in result['splits']:
            assert 'train_sharpe' in split
            assert 'test_sharpe' in split
            assert 'best_params' in split
    
    def test_strategy_registry(self):
        """Test strategy registry availability."""
        from src.backtest.strategies.registry import StrategyRegistry
        
        registry = StrategyRegistry()
        
        # Check basic strategies exist
        strategies = registry.list_strategy_names()
        assert 'sma_cross' in strategies or 'sma' in strategies
        assert 'rsi' in strategies
        
        # Get strategy instance
        sma_strategy = registry.get_strategy('sma_cross') or registry.get_strategy('sma')
        assert sma_strategy is not None
        
        # Check strategy has generate_signals method
        assert hasattr(sma_strategy, 'generate_signals')