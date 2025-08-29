"""
Comprehensive Tests for Canary Live Trading System
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta, date
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import numpy as np

from src.canary.orchestrator import CanaryOrchestrator, TradingMode
from src.portfolio.constructor import PortfolioConstructor
from src.execution.engine import SmartExecutionEngine, OrderStyle


class TestCanaryOrchestrator:
    """Test canary orchestration and ramping"""
    
    @pytest.mark.asyncio
    async def test_start_canary_shadow_mode(self):
        """Test starting canary in shadow mode"""
        orchestrator = CanaryOrchestrator()
        
        result = await orchestrator.start_canary(TradingMode.SHADOW)
        
        assert result['status'] == 'started'
        assert result['mode'] == 'shadow'
        assert orchestrator.running == True
        assert orchestrator.state.mode == TradingMode.SHADOW
        
        await orchestrator.stop_canary()
    
    @pytest.mark.asyncio
    async def test_capital_allocation_schedule(self):
        """Test capital allocation follows schedule"""
        orchestrator = CanaryOrchestrator()
        
        # Day 1
        orchestrator.state.days_running = 1
        allocation = orchestrator._get_capital_allocation()
        assert allocation == 5.0  # 5% for days 1-2
        
        # Day 3
        orchestrator.state.days_running = 3
        allocation = orchestrator._get_capital_allocation()
        assert allocation == 15.0  # 15% for days 3-4
        
        # Day 6
        orchestrator.state.days_running = 6
        allocation = orchestrator._get_capital_allocation()
        assert allocation == 30.0  # 30% for days 5-7
        
        # Day 10
        orchestrator.state.days_running = 10
        allocation = orchestrator._get_capital_allocation()
        assert allocation == 50.0  # 50% for day 8+
    
    @pytest.mark.asyncio
    async def test_gates_evaluation(self):
        """Test gates evaluation logic"""
        orchestrator = CanaryOrchestrator()
        
        # Good performance
        good_performance = {
            'total_pnl': 100.0,
            'max_drawdown': -2.0,
            'error_rate': 0.5,
            'slippage_p95': 40.0,
            'trade_count': 20
        }
        
        gates = orchestrator._check_gates(good_performance)
        assert all(gates.values()), "All gates should pass with good performance"
        
        # Bad performance
        bad_performance = {
            'total_pnl': -50.0,
            'max_drawdown': -8.0,
            'error_rate': 2.5,
            'slippage_p95': 80.0,
            'trade_count': 2
        }
        
        gates = orchestrator._check_gates(bad_performance)
        assert not all(gates.values()), "Some gates should fail with bad performance"
    
    @pytest.mark.asyncio 
    async def test_kill_switch_activation(self):
        """Test automatic kill switch activation"""
        orchestrator = CanaryOrchestrator()
        
        # Set state for kill switch test
        orchestrator.state.max_drawdown = -15.0  # Below -10% threshold
        orchestrator.running = True
        
        # Mock performance evaluation
        async def mock_evaluate():
            return {'max_drawdown': -15.0}
        
        orchestrator._evaluate_canary_performance = mock_evaluate
        
        # Trigger gates check
        await orchestrator._make_ramp_decision()
        
        assert orchestrator.state.kill_switch_active == True
        assert orchestrator.running == False


class TestPortfolioConstruction:
    """Test portfolio construction methods"""
    
    def test_hrp_portfolio_construction(self):
        """Test Hierarchical Risk Parity"""
        constructor = PortfolioConstructor(method='hrp')
        
        # Generate mock returns data
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        returns_data = {}
        
        strategies = ['strategy_A', 'strategy_B', 'strategy_C', 'strategy_D']
        for strategy in strategies:
            returns = np.random.normal(0.001, 0.02, 60)  # Daily returns
            returns_data[strategy] = pd.Series(returns, index=dates)
        
        result = constructor.build_portfolio(returns_data)
        
        assert 'error' not in result
        assert abs(sum(result['weights'].values()) - 1.0) < 1e-6  # Weights sum to 1
        assert all(w >= 0 for w in result['weights'].values())  # Non-negative weights
        assert result['metrics']['effective_n_assets'] > 1.0  # Some diversification
    
    def test_volatility_targeting(self):
        """Test volatility targeting method"""
        constructor = PortfolioConstructor(method='voltarget')
        
        # Create strategies with different volatilities
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        returns_data = {
            'low_vol_strategy': pd.Series(np.random.normal(0.001, 0.01, 60), index=dates),
            'high_vol_strategy': pd.Series(np.random.normal(0.002, 0.04, 60), index=dates)
        }
        
        result = constructor.build_portfolio(returns_data)
        
        assert 'error' not in result
        # Low vol strategy should have higher weight
        low_vol_weight = result['weights']['low_vol_strategy']
        high_vol_weight = result['weights']['high_vol_strategy']
        assert low_vol_weight > high_vol_weight
    
    def test_kelly_optimal(self):
        """Test Kelly optimal allocation"""
        constructor = PortfolioConstructor(method='kelly')
        
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        returns_data = {
            'good_strategy': pd.Series(np.random.normal(0.002, 0.01, 60), index=dates),  # High Sharpe
            'bad_strategy': pd.Series(np.random.normal(-0.001, 0.02, 60), index=dates)   # Negative Sharpe
        }
        
        result = constructor.build_portfolio(returns_data)
        
        assert 'error' not in result
        # Good strategy should have much higher weight
        assert result['weights']['good_strategy'] > result['weights']['bad_strategy']
    
    def test_constraint_application(self):
        """Test portfolio constraints"""
        constructor = PortfolioConstructor(method='equal')
        constructor.max_symbol_weight = 0.25  # 25% max per symbol
        
        # Create data where symbols would exceed constraints
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        returns_data = {
            'strategy1_AAPL': pd.Series(np.random.normal(0.001, 0.01, 60), index=dates),
            'strategy2_AAPL': pd.Series(np.random.normal(0.001, 0.01, 60), index=dates),
            'strategy3_AAPL': pd.Series(np.random.normal(0.001, 0.01, 60), index=dates),
            'strategy1_BTC': pd.Series(np.random.normal(0.001, 0.01, 60), index=dates)
        }
        
        result = constructor.build_portfolio(returns_data)
        
        # Check symbol constraints
        aapl_total = (result['weights']['strategy1_AAPL'] + 
                     result['weights']['strategy2_AAPL'] + 
                     result['weights']['strategy3_AAPL'])
        
        assert aapl_total <= 0.26  # Within constraint + small tolerance


class TestSmartExecution:
    """Test advanced execution engine"""
    
    @pytest.mark.asyncio
    async def test_post_only_execution(self):
        """Test post-only execution"""
        engine = SmartExecutionEngine()
        
        result = await engine.execute_order(
            symbol='BTC/USDT',
            side='buy',
            quantity=Decimal('0.1'),
            style=OrderStyle.POST_ONLY
        )
        
        assert 'error' not in result
        assert 'order_id' in result
        if result['status'] == 'filled':
            assert result['execution_style'] == 'post_only'
            assert result['fees_bps'] <= 5  # Maker fees
    
    @pytest.mark.asyncio
    async def test_twap_execution(self):
        """Test TWAP execution for large orders"""
        engine = SmartExecutionEngine()
        engine.config['MAX_SLICE_USD'] = 1000  # Lower threshold for testing
        
        # Large order that should trigger TWAP
        result = await engine.execute_order(
            symbol='BTC/USDT',
            side='buy', 
            quantity=Decimal('1.0'),  # Large quantity
            style=OrderStyle.TWAP
        )
        
        assert 'error' not in result
        if result['status'] in ['filled', 'partial']:
            assert result['execution_style'] == 'twap'
            assert 'n_slices' in result
            assert result['n_slices'] > 1
    
    @pytest.mark.asyncio
    async def test_dynamic_offset_calculation(self):
        """Test dynamic offset calculation"""
        engine = SmartExecutionEngine()
        
        # Low volatility market
        low_vol_market = {
            'spread_bps': 2,
            'volatility': 0.01,
            'bid': 50000,
            'ask': 50001
        }
        
        offset_low = engine._calculate_dynamic_offset('BTC/USDT', low_vol_market)
        
        # High volatility market  
        high_vol_market = {
            'spread_bps': 10,
            'volatility': 0.05,
            'bid': 50000,
            'ask': 50005
        }
        
        offset_high = engine._calculate_dynamic_offset('BTC/USDT', high_vol_market)
        
        assert offset_high > offset_low  # Higher vol should have larger offset
    
    @pytest.mark.asyncio
    async def test_spike_detection(self):
        """Test price spike detection"""
        engine = SmartExecutionEngine()
        
        # Build price history
        normal_prices = [50000 + i for i in range(10)]
        for price in normal_prices:
            engine._is_price_spike('BTC/USDT', price)
        
        # Normal price - should not be spike
        assert not engine._is_price_spike('BTC/USDT', 50010)
        
        # Spike price - should be detected
        assert engine._is_price_spike('BTC/USDT', 52000)  # 4% spike
    
    def test_execution_metrics_calculation(self):
        """Test execution metrics calculation"""
        engine = SmartExecutionEngine()
        
        market_data = {
            'mid_price': 50000,
            'spread_bps': 5,
            'ask': 50002.5,
            'bid': 49997.5
        }
        
        execution_result = {
            'filled_quantity': 0.1,
            'avg_fill_price': 50010,
            'fill_ratio': 1.0,
            'execution_style': 'post_only'
        }
        
        metrics = engine._calculate_execution_metrics(
            'BTC/USDT', 'buy', Decimal('0.1'),
            execution_result, market_data, datetime.now()
        )
        
        assert metrics.symbol == 'BTC/USDT'
        assert metrics.slippage_bps > 0  # Should have some slippage
        assert metrics.fill_ratio == 1.0
        assert metrics.style == 'post_only'


class TestSentimentIntegration:
    """Test AI sentiment integration with trading"""
    
    @pytest.mark.asyncio
    async def test_sentiment_k_factor_adjustment(self):
        """Test K-factor adjustment based on sentiment"""
        from src.ai.news_sentiment import NewsSentimentAnalyzer, SentimentScore
        
        analyzer = NewsSentimentAnalyzer()
        
        # Positive sentiment
        positive_sentiment = SentimentScore(
            symbol='BTC/USDT',
            score_1h=0.7,
            score_24h=0.5,
            volume_1h=10,
            volume_24h=25,
            confidence_1h=0.8,
            confidence_24h=0.7,
            last_update=datetime.now()
        )
        
        overlay = analyzer.get_strategy_overlay_signals('BTC/USDT', positive_sentiment)
        
        assert overlay['k_factor_adjustment'] > 0  # Should increase K-factor
        assert overlay['strategy_bias'] in ['trend_following', 'neutral']
        
        # Negative sentiment
        negative_sentiment = SentimentScore(
            symbol='BTC/USDT',
            score_1h=-0.7,
            score_24h=-0.3,
            volume_1h=8,
            volume_24h=20,
            confidence_1h=0.7,
            confidence_24h=0.6,
            last_update=datetime.now()
        )
        
        overlay = analyzer.get_strategy_overlay_signals('BTC/USDT', negative_sentiment)
        
        assert overlay['strategy_bias'] == 'mean_reversion'


class TestRiskGates:
    """Test risk gates and auto-ramping"""
    
    def test_gates_with_good_performance(self):
        """Test gates pass with good performance"""
        orchestrator = CanaryOrchestrator()
        
        good_performance = {
            'total_pnl': 50.0,
            'max_drawdown': -2.0,
            'error_rate': 0.3,
            'slippage_p95': 30.0,
            'trade_count': 15
        }
        
        gates = orchestrator._check_gates(good_performance)
        
        assert gates['pnl_positive'] == True
        assert gates['drawdown_acceptable'] == True
        assert gates['error_rate_low'] == True
        assert gates['slippage_acceptable'] == True
        assert gates['sufficient_trades'] == True
    
    def test_gates_with_poor_performance(self):
        """Test gates fail with poor performance"""
        orchestrator = CanaryOrchestrator()
        
        poor_performance = {
            'total_pnl': -20.0,
            'max_drawdown': -6.0,
            'error_rate': 3.0,
            'slippage_p95': 80.0,
            'trade_count': 2
        }
        
        gates = orchestrator._check_gates(poor_performance)
        
        assert gates['pnl_positive'] == False
        assert gates['error_rate_low'] == False
        assert gates['slippage_acceptable'] == False
        assert gates['sufficient_trades'] == False
    
    @pytest.mark.asyncio
    async def test_auto_ramp_up(self):
        """Test automatic capital ramp up"""
        orchestrator = CanaryOrchestrator()
        orchestrator.state.capital_pct = 5.0
        orchestrator.state.days_running = 3  # Should ramp to 15%
        orchestrator.state.auto_ramp_enabled = True
        
        # Mock good performance
        async def mock_evaluate():
            return {
                'total_pnl': 25.0,
                'max_drawdown': -1.5,
                'error_rate': 0.2,
                'slippage_p95': 25.0,
                'trade_count': 12
            }
        
        orchestrator._evaluate_canary_performance = mock_evaluate
        orchestrator._notify_ramp_change = AsyncMock()
        
        old_capital = orchestrator.state.capital_pct
        await orchestrator._make_ramp_decision()
        
        assert orchestrator.state.capital_pct > old_capital  # Should increase
        orchestrator._notify_ramp_change.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_auto_ramp_down(self):
        """Test automatic capital ramp down"""
        orchestrator = CanaryOrchestrator()
        orchestrator.state.capital_pct = 30.0
        orchestrator.state.auto_ramp_enabled = True
        
        # Mock poor performance
        async def mock_evaluate():
            return {
                'total_pnl': -30.0,
                'max_drawdown': -5.0,
                'error_rate': 3.0,
                'slippage_p95': 100.0,
                'trade_count': 20
            }
        
        orchestrator._evaluate_canary_performance = mock_evaluate
        orchestrator._notify_ramp_change = AsyncMock()
        
        old_capital = orchestrator.state.capital_pct
        await orchestrator._make_ramp_decision()
        
        assert orchestrator.state.capital_pct < old_capital  # Should decrease
        assert orchestrator.state.capital_pct == old_capital * 0.5  # Halved


class TestExecutionQuality:
    """Test execution quality metrics and gates"""
    
    def test_execution_metrics_aggregation(self):
        """Test execution metrics aggregation"""
        engine = SmartExecutionEngine()
        
        # Add some mock execution metrics
        from src.execution.engine import ExecutionMetrics
        
        metrics1 = ExecutionMetrics(
            symbol='BTC/USDT',
            total_quantity=Decimal('0.1'),
            avg_fill_price=Decimal('50000'),
            vwap_benchmark=Decimal('49995'),
            slippage_bps=10.0,
            fill_ratio=1.0,
            effective_spread_bps=8.0,
            queue_slip_bps=2.0,
            execution_time_ms=1500,
            style='post_only'
        )
        
        metrics2 = ExecutionMetrics(
            symbol='ETH/USDT',
            total_quantity=Decimal('1.0'),
            avg_fill_price=Decimal('3450'),
            vwap_benchmark=Decimal('3448'),
            slippage_bps=15.0,
            fill_ratio=0.98,
            effective_spread_bps=12.0,
            queue_slip_bps=3.0,
            execution_time_ms=2000,
            style='ioc'
        )
        
        engine.execution_metrics = [metrics1, metrics2]
        
        report = engine.get_execution_report(lookback_hours=24)
        
        assert report['total_executions'] == 2
        assert report['avg_slippage_bps'] == 12.5  # (10 + 15) / 2
        assert report['p95_slippage_bps'] >= 10.0
        assert len(report['style_breakdown']) == 2  # Two different styles
        assert 'gate_status' in report


class TestPortfolioIntegration:
    """Test portfolio integration with live trading"""
    
    def test_portfolio_weight_to_k_factor_conversion(self):
        """Test converting portfolio weights to K-factors"""
        # Mock portfolio weights
        portfolio_weights = {
            'supertrend_BTC/USDT': 0.25,
            'bollinger_revert_ETH/USDT': 0.20,
            'sma_cross_AAPL': 0.15,
            'donchian_breakout_MSFT': 0.40
        }
        
        # Convert to K-factors (scaled by capital allocation)
        capital_pct = 0.30  # 30% canary allocation
        
        k_factors = {}
        for strategy, weight in portfolio_weights.items():
            k_factors[strategy] = weight * capital_pct
        
        assert abs(sum(k_factors.values()) - 0.30) < 1e-6  # Should sum to capital_pct
        assert max(k_factors.values()) <= 0.12  # 40% * 30% = 12%
        assert min(k_factors.values()) >= 0.045  # 15% * 30% = 4.5%
    
    def test_sentiment_overlay_application(self):
        """Test sentiment overlay affects portfolio weights"""
        from src.ai.news_sentiment import SentimentScore
        
        base_k_factor = 0.25
        
        # Strong positive sentiment - should increase trend strategies
        positive_sentiment = SentimentScore(
            symbol='BTC/USDT',
            score_1h=0.8,
            score_24h=0.6,
            volume_1h=15,
            volume_24h=40,
            confidence_1h=0.9,
            confidence_24h=0.8,
            last_update=datetime.now()
        )
        
        # Mock sentiment analyzer
        from src.ai.news_sentiment import NewsSentimentAnalyzer
        analyzer = NewsSentimentAnalyzer()
        
        overlay = analyzer.get_strategy_overlay_signals('BTC/USDT', positive_sentiment)
        
        # Apply overlay to K-factor
        adjusted_k_factor = base_k_factor + overlay['k_factor_adjustment']
        
        assert adjusted_k_factor != base_k_factor  # Should be adjusted
        if overlay['strategy_bias'] == 'trend_following':
            assert adjusted_k_factor > base_k_factor  # Should increase for trend strategies


class TestEndToEndCanaryFlow:
    """Test complete canary trading flow"""
    
    @pytest.mark.asyncio
    async def test_shadow_to_canary_transition(self):
        """Test transition from shadow to canary mode"""
        orchestrator = CanaryOrchestrator()
        
        # Start in shadow mode
        result = await orchestrator.start_canary(TradingMode.SHADOW)
        assert result['status'] == 'started'
        assert orchestrator.state.mode == TradingMode.SHADOW
        
        # Simulate good performance for 24 hours
        orchestrator.state.total_pnl = Decimal('50')
        orchestrator.state.max_drawdown = -1.5
        orchestrator.state.error_rate = 0.1
        
        # Mock evaluation
        async def mock_good_eval():
            return {
                'total_pnl': 50.0,
                'daily_pnl': 25.0,
                'max_drawdown': -1.5,
                'error_rate': 0.1,
                'slippage_p95': 20.0,
                'trade_count': 15
            }
        
        orchestrator._evaluate_canary_performance = mock_good_eval
        
        # Should pass gates
        performance = await orchestrator._evaluate_canary_performance()
        gates = orchestrator._check_gates(performance)
        
        assert all(gates.values()), "All gates should pass with good performance"
        
        await orchestrator.stop_canary()
    
    @pytest.mark.asyncio
    async def test_complete_ramp_schedule(self):
        """Test complete capital ramping schedule"""
        orchestrator = CanaryOrchestrator()
        
        test_days = [1, 2, 3, 4, 5, 6, 7, 10]
        expected_allocations = [5, 5, 15, 15, 30, 30, 30, 50]
        
        for day, expected in zip(test_days, expected_allocations):
            orchestrator.state.days_running = day
            allocation = orchestrator._get_capital_allocation()
            assert allocation == expected, f"Day {day}: expected {expected}%, got {allocation}%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])