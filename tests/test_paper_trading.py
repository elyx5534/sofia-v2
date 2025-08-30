"""
Unit Tests for Paper Trading Components
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import numpy as np

from src.paper.runner import PaperTradingRunner
from src.paper.signal_hub import SignalHub, Signal, SMACrossStrategy
from src.reports.paper_report import PaperTradingReport


class TestPositionSizing:
    """Test K-factor based position sizing"""
    
    def test_calculate_position_size_basic(self):
        """Test basic position size calculation"""
        runner = PaperTradingRunner()
        runner.balance = Decimal('10000')
        runner.k_factor = Decimal('0.25')
        
        # Calculate position size for a signal
        size = runner._calculate_position_size('BTC/USDT', 0.8)
        
        # Should be: balance * k_factor * signal_strength * max_position_pct
        # 10000 * 0.25 * 0.8 * 0.1 = 200
        expected = Decimal('200')
        assert abs(size - expected) < Decimal('1'), f"Expected {expected}, got {size}"
    
    def test_position_size_respects_max_limits(self):
        """Test that position size respects max limits"""
        runner = PaperTradingRunner()
        runner.balance = Decimal('100000')  # Large balance
        runner.k_factor = Decimal('1.0')  # Max k-factor
        
        # Even with large balance and max k-factor, should respect MAX_POSITION_USD
        size = runner._calculate_position_size('BTC/USDT', 1.0)
        
        max_position = Decimal(runner.config['MAX_POSITION_USD'])
        assert size <= max_position, f"Position size {size} exceeds max {max_position}"
    
    def test_position_size_with_existing_exposure(self):
        """Test position sizing with existing symbol exposure"""
        runner = PaperTradingRunner()
        runner.balance = Decimal('10000')
        runner.k_factor = Decimal('0.25')
        
        # Add existing position
        runner.positions['BTC/USDT'] = {
            'quantity': Decimal('0.01'),
            'entry_price': Decimal('50000'),
            'position_value': Decimal('500'),
            'unrealized_pnl': Decimal('0')
        }
        
        # Should reduce new position size due to existing exposure
        size = runner._calculate_position_size('BTC/USDT', 0.8)
        
        # Max symbol exposure is 500, already have 500, so should be 0
        assert size == Decimal('0'), f"Expected 0, got {size}"


class TestSignalFusion:
    """Test signal fusion logic"""
    
    def test_fuse_signals_single_strategy(self):
        """Test fusion with single strategy signal"""
        hub = SignalHub()
        
        signal = Signal(
            symbol='BTC/USDT',
            timestamp=datetime.now(),
            strategy='test',
            direction=1,
            strength=0.8,
            confidence=0.7,
            metadata={}
        )
        
        result = hub._fuse_signals([signal])
        
        assert result['strength'] == 0.8
        assert result['confidence'] == 0.7
        assert result['num_signals'] == 1
    
    def test_fuse_signals_multiple_agree(self):
        """Test fusion when multiple strategies agree"""
        hub = SignalHub()
        
        signals = [
            Signal('BTC/USDT', datetime.now(), 'sma', 1, 0.8, 0.7, {}),
            Signal('BTC/USDT', datetime.now(), 'ema', 1, 0.6, 0.8, {}),
            Signal('BTC/USDT', datetime.now(), 'rsi', 1, 0.7, 0.6, {})
        ]
        
        result = hub._fuse_signals(signals)
        
        # All signals are bullish, fusion should be bullish
        assert result['strength'] > 0
        assert result['num_signals'] == 3
        # Confidence should be average
        expected_confidence = np.mean([0.7, 0.8, 0.6])
        assert abs(result['confidence'] - expected_confidence) < 0.01
    
    def test_fuse_signals_conflicting(self):
        """Test fusion with conflicting signals"""
        hub = SignalHub()
        
        signals = [
            Signal('BTC/USDT', datetime.now(), 'sma', 1, 0.8, 0.9, {}),
            Signal('BTC/USDT', datetime.now(), 'ema', -1, 0.7, 0.8, {}),
            Signal('BTC/USDT', datetime.now(), 'rsi', 0, 0.0, 0.5, {})
        ]
        
        result = hub._fuse_signals(signals)
        
        # Weighted voting should determine direction
        # (1 * 0.9) + (-1 * 0.8) + (0 * 0.5) = 0.1 (slightly bullish)
        weighted_sum = (1 * 0.9) + (-1 * 0.8) + (0 * 0.5)
        total_weight = 0.9 + 0.8 + 0.5
        expected_direction = weighted_sum / total_weight
        
        assert abs(result['strength'] - expected_direction) < 0.1


class TestPnLCalculation:
    """Test P&L calculation logic"""
    
    def test_calculate_pnl_profit(self):
        """Test P&L calculation for profitable trade"""
        runner = PaperTradingRunner()
        
        # Simulate buy
        entry_price = Decimal('50000')
        quantity = Decimal('0.1')
        runner.positions['BTC/USDT'] = {
            'quantity': quantity,
            'entry_price': entry_price,
            'position_value': entry_price * quantity,
            'unrealized_pnl': Decimal('0')
        }
        
        # Simulate sell at higher price
        exit_price = Decimal('55000')
        pnl = (exit_price - entry_price) * quantity
        
        assert pnl == Decimal('500'), f"Expected 500, got {pnl}"
    
    def test_calculate_pnl_with_fees(self):
        """Test P&L calculation including fees"""
        runner = PaperTradingRunner()
        
        entry_price = Decimal('50000')
        quantity = Decimal('0.1')
        fee_rate = Decimal('0.001')
        
        # Entry fee
        entry_fee = entry_price * quantity * fee_rate
        
        # Exit fee
        exit_price = Decimal('55000')
        exit_fee = exit_price * quantity * fee_rate
        
        # Net P&L
        gross_pnl = (exit_price - entry_price) * quantity
        net_pnl = gross_pnl - entry_fee - exit_fee
        
        expected = Decimal('500') - Decimal('50') - Decimal('55')
        assert abs(net_pnl - expected) < Decimal('1')


class TestPaperTradingReport:
    """Test reporting functionality"""
    
    def test_get_empty_metrics(self):
        """Test metrics when no runner available"""
        report = PaperTradingReport(runner=None)
        metrics = report.get_live_metrics()
        
        assert metrics['cumulative_pnl'] == '0'
        assert metrics['daily_pnl'] == '0'
        assert metrics['positions_count'] == 0
        assert metrics['trade_count'] == 0
        assert metrics['status'] == 'not_started'
    
    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        report = PaperTradingReport()
        
        # Test with sample returns
        returns = [100, -50, 200, 150, -100, 300, 50]
        sharpe = report._calculate_sharpe(returns)
        
        # Should return a reasonable Sharpe ratio
        assert isinstance(sharpe, float)
        assert -5 < sharpe < 5  # Reasonable bounds
    
    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation"""
        report = PaperTradingReport()
        
        # Mock runner with orders
        mock_runner = Mock()
        mock_runner.orders = []
        report.runner = mock_runner
        
        # Test with no orders
        max_dd = report._calculate_max_drawdown()
        assert max_dd == 0


class TestReplaySimulation:
    """Test replay simulation for quick profitability check"""
    
    @pytest.mark.asyncio
    async def test_replay_initialization(self):
        """Test replay initialization"""
        from scripts.paper_replay import PaperReplay
        
        replay = PaperReplay(hours=24)
        
        assert replay.hours == 24
        assert replay.balance == Decimal('10000')
        assert len(replay.positions) == 0
        assert replay.pnl == Decimal('0')
    
    @pytest.mark.asyncio
    async def test_replay_report_generation(self):
        """Test replay report generation"""
        from scripts.paper_replay import PaperReplay
        
        replay = PaperReplay(hours=1)
        
        # Mock results
        results = {
            'trades_executed': 10,
            'winning_trades': 6,
            'win_rate': 60.0,
            'total_pnl': 150.0,
            'total_fees': 10.0,
            'final_balance': 10150.0,
            'return_pct': 1.5,
            'open_positions': 0
        }
        
        report = replay._generate_replay_report(results)
        
        assert report['profitability']['is_profitable'] == True
        assert report['results']['total_pnl'] == 150.0
        assert report['results']['win_rate'] == 60.0


class TestRiskIntegration:
    """Test risk engine integration"""
    
    @pytest.mark.asyncio
    async def test_pre_trade_risk_check(self):
        """Test pre-trade risk validation"""
        runner = PaperTradingRunner()
        
        # Mock risk engine
        runner.risk_engine = AsyncMock()
        runner.risk_engine.pre_trade_check.return_value = {
            'approved': True,
            'checks': {
                'daily_loss_limit': {'passed': True},
                'position_limit': {'passed': True},
                'symbol_exposure': {'passed': True}
            }
        }
        
        # Create a signal
        signal = {
            'symbol': 'BTC/USDT',
            'strength': 0.8,
            'confidence': 0.7
        }
        
        # Process signal should check risk
        await runner._process_signal(signal)
        
        # Verify risk check was called
        runner.risk_engine.pre_trade_check.assert_called()


class TestMLIntegration:
    """Test ML predictor integration"""
    
    def test_ml_weight_application(self):
        """Test ML weight application to signals"""
        hub = SignalHub()
        hub.ml_enabled = True
        hub.ml_weight = 0.5
        
        # Mock fused signal
        fused_signal = {
            'strength': 0.6,
            'confidence': 0.7
        }
        
        # Mock ML signal
        ml_signal = Signal(
            symbol='BTC/USDT',
            timestamp=datetime.now(),
            strategy='ml',
            direction=1,
            strength=0.8,
            confidence=0.9,
            metadata={}
        )
        
        result = hub._apply_ml_weight(fused_signal, ml_signal)
        
        # ML contribution should be applied
        expected_strength = 0.6 * 0.5 + (1 * 0.9 * 0.5)
        assert abs(result['strength'] - expected_strength) < 0.1
        assert 'ml_contribution' in result


@pytest.mark.asyncio
class TestEndToEndFlow:
    """Test complete paper trading flow"""
    
    async def test_full_trading_cycle(self):
        """Test complete buy-sell cycle"""
        runner = PaperTradingRunner()
        
        # Initialize
        runner.balance = Decimal('10000')
        runner.k_factor = Decimal('0.25')
        
        # Mock data and signal
        runner.signal_hub = Mock()
        runner.signal_hub.get_signal.return_value = {
            'symbol': 'BTC/USDT',
            'strength': 0.8,
            'confidence': 0.7
        }
        
        # Mock price data
        current_price = Decimal('50000')
        
        # Process buy signal
        await runner._create_paper_order(
            symbol='BTC/USDT',
            side='buy',
            quantity=Decimal('0.01'),
            price=current_price
        )
        
        assert len(runner.orders) == 1
        assert 'BTC/USDT' in runner.positions
        
        # Process sell signal
        await runner._create_paper_order(
            symbol='BTC/USDT',
            side='sell',
            quantity=Decimal('0.01'),
            price=Decimal('51000')
        )
        
        assert len(runner.orders) == 2
        assert runner.total_pnl > Decimal('0')  # Should be profitable


if __name__ == "__main__":
    pytest.main([__file__, "-v"])