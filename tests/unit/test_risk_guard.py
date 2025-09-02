"""Tests for Risk Guard and Kill Switch."""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta
from decimal import Decimal


class TestRiskGuard:
    """Test risk management and kill switch functionality."""
    
    def test_daily_loss_limit_trigger(self):
        """Test daily loss limit triggers trade rejection."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_daily_loss=0.02,  # 2% daily loss limit
            max_position_size=0.1,
            max_drawdown=0.1
        )
        
        manager = RiskManager(params)
        manager.update_portfolio_value(10000)
        
        # Simulate 2.5% loss
        manager.daily_pnl = -250
        manager.start_of_day_value = 10000
        
        # Check should fail
        allowed, message = manager.check_daily_loss_limit()
        assert not allowed
        assert "daily loss limit" in message.lower()
    
    def test_position_size_limit(self):
        """Test position size limit enforcement."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_position_size=0.1,  # 10% max position
            max_daily_loss=0.05,
            max_drawdown=0.2
        )
        
        manager = RiskManager(params)
        portfolio_value = 10000
        
        # Try to open 15% position
        position_value = 1500
        allowed, message = manager.check_position_size(position_value, portfolio_value)
        
        assert not allowed
        assert "position size" in message.lower()
        
        # Try 8% position - should pass
        position_value = 800
        allowed, message = manager.check_position_size(position_value, portfolio_value)
        assert allowed
    
    def test_max_drawdown_kill_switch(self):
        """Test max drawdown triggers kill switch."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_drawdown=0.1,  # 10% max drawdown
            kill_switch_enabled=True
        )
        
        manager = RiskManager(params)
        
        # Set peak value
        manager.peak_value = 10000
        manager.current_value = 10000
        
        # Simulate 12% drawdown
        manager.current_value = 8800
        
        # Check drawdown
        allowed, message = manager.check_drawdown()
        assert not allowed
        assert "kill switch" in message.lower() or "drawdown" in message.lower()
        
        # Kill switch should be active
        assert manager.is_kill_switch_active()
    
    def test_concurrent_position_limit(self):
        """Test concurrent position limits."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_open_positions=3,
            max_position_size=0.1
        )
        
        manager = RiskManager(params)
        
        # Check with 3 positions - should allow closing
        allowed, message = manager.check_open_positions(3, is_closing=True)
        assert allowed
        
        # Check with 3 positions - should block opening
        allowed, message = manager.check_open_positions(3, is_closing=False)
        assert not allowed
        assert "position limit" in message.lower()
        
        # Check with 2 positions - should allow
        allowed, message = manager.check_open_positions(2, is_closing=False)
        assert allowed
    
    def test_risk_metrics_calculation(self):
        """Test risk metrics calculation."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        manager = RiskManager()
        
        # Add some P&L history
        pnl_history = [100, -50, 75, -25, 150, -100, 50]
        for pnl in pnl_history:
            manager.add_pnl(pnl)
        
        metrics = manager.calculate_metrics()
        
        assert 'sharpe_ratio' in metrics
        assert 'sortino_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        
        # Win rate should be 4/7
        assert abs(metrics['win_rate'] - 4/7) < 0.01
    
    def test_trade_rejection_on_risk_breach(self):
        """Test trade rejection when risk limits breached."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_daily_loss=0.02,
            max_position_size=0.05,
            max_drawdown=0.1
        )
        
        manager = RiskManager(params)
        manager.update_portfolio_value(10000)
        
        # Set daily loss at limit
        manager.daily_pnl = -200
        manager.start_of_day_value = 10000
        
        # Attempt new trade
        trade_request = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000
        }
        
        allowed = manager.can_execute_trade(trade_request)
        assert not allowed
        
        # Reset daily P&L
        manager.reset_daily_metrics()
        
        # Now should allow
        allowed = manager.can_execute_trade(trade_request)
        assert allowed
    
    def test_emergency_stop_all_trading(self):
        """Test emergency stop functionality."""
        from src.core.profit_guard import ProfitGuard
        
        guard = ProfitGuard(
            daily_loss_limit=0.05,
            max_drawdown=0.15,
            emergency_stop_enabled=True
        )
        
        # Trigger emergency stop
        guard.trigger_emergency_stop("Manual intervention required")
        
        assert guard.is_stopped
        assert not guard.can_trade()
        
        # Verify all new trades blocked
        for _ in range(5):
            assert not guard.can_trade()
        
        # Reset emergency stop
        guard.reset_emergency_stop()
        assert not guard.is_stopped
        assert guard.can_trade()