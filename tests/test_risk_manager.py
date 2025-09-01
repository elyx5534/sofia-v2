"""Tests for the risk management module."""

import pytest
from datetime import datetime, timezone
from src.trading_engine.risk_manager import RiskParameters, RiskMetrics, RiskManager


class TestRiskParameters:
    """Test cases for RiskParameters class."""

    def test_risk_parameters_default_values(self):
        """Test RiskParameters with default values."""
        params = RiskParameters()
        
        assert params.max_position_size == 0.1
        assert params.max_daily_loss == 0.02
        assert params.max_drawdown == 0.1
        assert params.stop_loss_percentage == 0.02
        assert params.take_profit_percentage == 0.05
        assert params.max_leverage == 1.0
        assert params.max_open_positions == 10
        assert params.min_risk_reward_ratio == 2.0

    def test_risk_parameters_custom_values(self):
        """Test RiskParameters with custom values."""
        params = RiskParameters(
            max_position_size=0.2,
            max_daily_loss=0.05,
            max_drawdown=0.15,
            stop_loss_percentage=0.03,
            take_profit_percentage=0.08,
            max_leverage=2.0,
            max_open_positions=20,
            min_risk_reward_ratio=3.0
        )
        
        assert params.max_position_size == 0.2
        assert params.max_daily_loss == 0.05
        assert params.max_drawdown == 0.15
        assert params.stop_loss_percentage == 0.03
        assert params.take_profit_percentage == 0.08
        assert params.max_leverage == 2.0
        assert params.max_open_positions == 20
        assert params.min_risk_reward_ratio == 3.0

    def test_risk_parameters_field_descriptions(self):
        """Test that all fields have proper descriptions."""
        params = RiskParameters()
        schema = params.model_json_schema()
        
        assert "Max position size as % of portfolio" in str(schema['properties']['max_position_size'])
        assert "Max daily loss as % of portfolio" in str(schema['properties']['max_daily_loss'])
        assert "Max drawdown as % of portfolio" in str(schema['properties']['max_drawdown'])


class TestRiskMetrics:
    """Test cases for RiskMetrics class."""

    def test_risk_metrics_default_values(self):
        """Test RiskMetrics with default values."""
        metrics = RiskMetrics()
        
        assert metrics.current_drawdown == 0
        assert metrics.daily_pnl == 0
        assert metrics.sharpe_ratio == 0
        assert metrics.win_rate == 0
        assert metrics.avg_win == 0
        assert metrics.avg_loss == 0
        assert metrics.risk_reward_ratio == 0
        assert metrics.var_95 == 0
        assert isinstance(metrics.updated_at, datetime)

    def test_risk_metrics_custom_values(self):
        """Test RiskMetrics with custom values."""
        custom_time = datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        metrics = RiskMetrics(
            current_drawdown=0.05,
            daily_pnl=-1000.0,
            sharpe_ratio=1.5,
            win_rate=0.6,
            avg_win=500.0,
            avg_loss=300.0,
            risk_reward_ratio=1.67,
            var_95=-2000.0,
            updated_at=custom_time
        )
        
        assert metrics.current_drawdown == 0.05
        assert metrics.daily_pnl == -1000.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.win_rate == 0.6
        assert metrics.avg_win == 500.0
        assert metrics.avg_loss == 300.0
        assert metrics.risk_reward_ratio == 1.67
        assert metrics.var_95 == -2000.0
        assert metrics.updated_at == custom_time


class TestRiskManager:
    """Test cases for RiskManager class."""

    @pytest.fixture
    def risk_manager(self):
        """Create a test risk manager."""
        return RiskManager()

    @pytest.fixture
    def custom_risk_manager(self):
        """Create a risk manager with custom parameters."""
        params = RiskParameters(
            max_position_size=0.15,
            max_daily_loss=0.03,
            max_drawdown=0.08,
            stop_loss_percentage=0.025,
            take_profit_percentage=0.06,
            max_open_positions=15
        )
        return RiskManager(params)

    def test_risk_manager_initialization_default(self, risk_manager):
        """Test RiskManager initialization with default parameters."""
        assert isinstance(risk_manager.parameters, RiskParameters)
        assert isinstance(risk_manager.metrics, RiskMetrics)
        assert risk_manager.daily_losses == 0
        assert risk_manager.peak_value == 0
        assert risk_manager.current_value == 0
        assert risk_manager.trades_today == 0
        assert risk_manager.winning_trades == 0
        assert risk_manager.losing_trades == 0
        assert risk_manager.total_wins == 0
        assert risk_manager.total_losses == 0

    def test_risk_manager_initialization_custom(self, custom_risk_manager):
        """Test RiskManager initialization with custom parameters."""
        assert custom_risk_manager.parameters.max_position_size == 0.15
        assert custom_risk_manager.parameters.max_daily_loss == 0.03
        assert custom_risk_manager.parameters.max_drawdown == 0.08

    def test_check_position_size_within_limits(self, risk_manager):
        """Test position size check within limits."""
        is_valid, message = risk_manager.check_position_size(5000, 100000)
        
        assert is_valid is True
        assert "Position size OK" in message

    def test_check_position_size_exceeds_limit(self, risk_manager):
        """Test position size check exceeding limits."""
        is_valid, message = risk_manager.check_position_size(15000, 100000)  # 15% > 10%
        
        assert is_valid is False
        assert "exceeds max" in message
        assert "15.00%" in message

    def test_check_position_size_zero_portfolio(self, risk_manager):
        """Test position size check with zero portfolio value."""
        is_valid, message = risk_manager.check_position_size(1000, 0)
        
        assert is_valid is False
        assert "Portfolio value is zero" in message

    def test_check_daily_loss_limit_within_bounds(self, risk_manager):
        """Test daily loss limit check within bounds."""
        risk_manager.current_value = 100000
        risk_manager.daily_losses = -1000  # 1% loss < 2% limit
        
        is_valid, message = risk_manager.check_daily_loss_limit()
        
        assert is_valid is True
        assert "within limits" in message

    def test_check_daily_loss_limit_exceeded(self, risk_manager):
        """Test daily loss limit check exceeded."""
        risk_manager.current_value = 100000
        risk_manager.daily_losses = -3000  # 3% loss > 2% limit
        
        is_valid, message = risk_manager.check_daily_loss_limit()
        
        assert is_valid is False
        assert "exceeds limit" in message

    def test_check_daily_loss_limit_no_portfolio_value(self, risk_manager):
        """Test daily loss limit check with no portfolio value."""
        risk_manager.current_value = 0
        
        is_valid, message = risk_manager.check_daily_loss_limit()
        
        assert is_valid is True
        assert "No portfolio value set" in message

    def test_check_drawdown_within_limits(self, risk_manager):
        """Test drawdown check within limits."""
        risk_manager.peak_value = 100000
        risk_manager.current_value = 95000  # 5% drawdown < 10% limit
        
        is_valid, message = risk_manager.check_drawdown()
        
        assert is_valid is True
        assert "within limits" in message
        assert risk_manager.metrics.current_drawdown == 0.05

    def test_check_drawdown_exceeds_limit(self, risk_manager):
        """Test drawdown check exceeding limits."""
        risk_manager.peak_value = 100000
        risk_manager.current_value = 85000  # 15% drawdown > 10% limit
        
        is_valid, message = risk_manager.check_drawdown()
        
        assert is_valid is False
        assert "exceeds limit" in message

    def test_check_drawdown_no_peak_value(self, risk_manager):
        """Test drawdown check with no peak value."""
        risk_manager.peak_value = 0
        
        is_valid, message = risk_manager.check_drawdown()
        
        assert is_valid is True
        assert "No peak value set" in message

    def test_check_open_positions_within_limit(self, risk_manager):
        """Test open positions check within limit."""
        is_valid, message = risk_manager.check_open_positions(5)
        
        assert is_valid is True
        assert "Can open 5 more positions" in message

    def test_check_open_positions_at_limit(self, risk_manager):
        """Test open positions check at limit."""
        is_valid, message = risk_manager.check_open_positions(10)
        
        assert is_valid is False
        assert "at limit" in message

    def test_check_open_positions_exceeds_limit(self, risk_manager):
        """Test open positions check exceeding limit."""
        is_valid, message = risk_manager.check_open_positions(15)
        
        assert is_valid is False
        assert "at limit" in message

    def test_calculate_position_size_basic(self, risk_manager):
        """Test basic position size calculation."""
        position_size = risk_manager.calculate_position_size(
            portfolio_value=100000,
            risk_per_trade=0.01,  # 1%
            stop_loss_distance=0.02  # 2%
        )
        
        expected = 100000 * 0.01 / 0.02  # $1000 / 0.02 = $50000
        max_allowed = 100000 * 0.1  # 10% = $10000
        expected_final = min(expected, max_allowed)  # $10000
        
        assert position_size == expected_final

    def test_calculate_position_size_within_max_limit(self, risk_manager):
        """Test position size calculation within max limit."""
        position_size = risk_manager.calculate_position_size(
            portfolio_value=100000,
            risk_per_trade=0.005,  # 0.5%
            stop_loss_distance=0.05  # 5%
        )
        
        expected = 100000 * 0.005 / 0.05  # $500 / 0.05 = $10000
        max_allowed = 100000 * 0.1  # $10000
        expected_final = min(expected, max_allowed)  # $10000
        
        assert position_size == expected_final

    def test_calculate_position_size_exceeds_max_limit(self, risk_manager):
        """Test position size calculation exceeding max limit."""
        position_size = risk_manager.calculate_position_size(
            portfolio_value=100000,
            risk_per_trade=0.02,  # 2%
            stop_loss_distance=0.01  # 1%
        )
        
        # Would be: $2000 / 0.01 = $200000, but max is $10000
        max_allowed = 100000 * 0.1  # $10000
        
        assert position_size == max_allowed

    def test_update_metrics_winning_trade(self, risk_manager):
        """Test metrics update after winning trade."""
        risk_manager.update_metrics(500.0)
        
        assert risk_manager.daily_losses == 0  # No loss
        assert risk_manager.winning_trades == 1
        assert risk_manager.losing_trades == 0
        assert risk_manager.total_wins == 500.0
        assert risk_manager.total_losses == 0
        assert risk_manager.metrics.win_rate == 1.0
        assert risk_manager.metrics.avg_win == 500.0
        assert risk_manager.metrics.avg_loss == 0

    def test_update_metrics_losing_trade(self, risk_manager):
        """Test metrics update after losing trade."""
        risk_manager.update_metrics(-300.0)
        
        assert risk_manager.daily_losses == -300.0
        assert risk_manager.winning_trades == 0
        assert risk_manager.losing_trades == 1
        assert risk_manager.total_wins == 0
        assert risk_manager.total_losses == 300.0
        assert risk_manager.metrics.win_rate == 0.0
        assert risk_manager.metrics.avg_win == 0
        assert risk_manager.metrics.avg_loss == 300.0

    def test_update_metrics_mixed_trades(self, risk_manager):
        """Test metrics update with mixed winning and losing trades."""
        risk_manager.update_metrics(500.0)  # Win
        risk_manager.update_metrics(-200.0)  # Loss
        risk_manager.update_metrics(800.0)  # Win
        risk_manager.update_metrics(-100.0)  # Loss
        
        assert risk_manager.daily_losses == -300.0  # Total losses
        assert risk_manager.winning_trades == 2
        assert risk_manager.losing_trades == 2
        assert risk_manager.total_wins == 1300.0
        assert risk_manager.total_losses == 300.0
        assert risk_manager.metrics.win_rate == 0.5
        assert risk_manager.metrics.avg_win == 650.0  # 1300/2
        assert risk_manager.metrics.avg_loss == 150.0  # 300/2
        assert risk_manager.metrics.risk_reward_ratio == 650.0 / 150.0

    def test_update_metrics_risk_reward_ratio(self, risk_manager):
        """Test risk/reward ratio calculation."""
        risk_manager.update_metrics(600.0)  # Win
        risk_manager.update_metrics(-200.0)  # Loss
        
        expected_ratio = 600.0 / 200.0  # 3.0
        assert risk_manager.metrics.risk_reward_ratio == expected_ratio

    def test_update_metrics_zero_losses(self, risk_manager):
        """Test metrics update with only wins (no losses)."""
        risk_manager.update_metrics(500.0)
        risk_manager.update_metrics(300.0)
        
        assert risk_manager.metrics.risk_reward_ratio == 0  # No losses to divide by

    def test_update_portfolio_value_first_time(self, risk_manager):
        """Test updating portfolio value for first time."""
        risk_manager.update_portfolio_value(100000.0)
        
        assert risk_manager.current_value == 100000.0
        assert risk_manager.peak_value == 100000.0

    def test_update_portfolio_value_new_peak(self, risk_manager):
        """Test updating portfolio value with new peak."""
        risk_manager.update_portfolio_value(100000.0)
        risk_manager.update_portfolio_value(110000.0)  # New peak
        
        assert risk_manager.current_value == 110000.0
        assert risk_manager.peak_value == 110000.0

    def test_update_portfolio_value_below_peak(self, risk_manager):
        """Test updating portfolio value below peak."""
        risk_manager.update_portfolio_value(100000.0)
        risk_manager.update_portfolio_value(95000.0)  # Below peak
        
        assert risk_manager.current_value == 95000.0
        assert risk_manager.peak_value == 100000.0  # Peak unchanged

    def test_reset_daily_metrics(self, risk_manager):
        """Test resetting daily metrics."""
        risk_manager.daily_losses = -1000.0
        risk_manager.trades_today = 5
        risk_manager.metrics.daily_pnl = -500.0
        
        risk_manager.reset_daily_metrics()
        
        assert risk_manager.daily_losses == 0
        assert risk_manager.trades_today == 0
        assert risk_manager.metrics.daily_pnl == 0

    def test_get_stop_loss_price_buy(self, risk_manager):
        """Test stop loss price calculation for buy order."""
        entry_price = 100.0
        stop_loss = risk_manager.get_stop_loss_price(entry_price, "buy")
        
        expected = 100.0 * (1 - 0.02)  # 98.0
        assert stop_loss == expected

    def test_get_stop_loss_price_sell(self, risk_manager):
        """Test stop loss price calculation for sell order."""
        entry_price = 100.0
        stop_loss = risk_manager.get_stop_loss_price(entry_price, "sell")
        
        expected = 100.0 * (1 + 0.02)  # 102.0
        assert stop_loss == expected

    def test_get_take_profit_price_buy(self, risk_manager):
        """Test take profit price calculation for buy order."""
        entry_price = 100.0
        take_profit = risk_manager.get_take_profit_price(entry_price, "buy")
        
        expected = 100.0 * (1 + 0.05)  # 105.0
        assert take_profit == expected

    def test_get_take_profit_price_sell(self, risk_manager):
        """Test take profit price calculation for sell order."""
        entry_price = 100.0
        take_profit = risk_manager.get_take_profit_price(entry_price, "sell")
        
        expected = 100.0 * (1 - 0.05)  # 95.0
        assert take_profit == expected

    def test_comprehensive_risk_scenario(self, risk_manager):
        """Test comprehensive risk management scenario."""
        # Setup portfolio
        risk_manager.update_portfolio_value(100000.0)
        
        # Check initial position
        is_valid, _ = risk_manager.check_position_size(8000, 100000)  # 8% < 10%
        assert is_valid
        
        # Simulate some trades
        risk_manager.update_metrics(500.0)   # Win
        risk_manager.update_metrics(-200.0)  # Loss
        risk_manager.update_metrics(800.0)   # Win
        
        # Check daily loss limit
        is_valid, _ = risk_manager.check_daily_loss_limit()
        assert is_valid  # Only $200 loss < 2% ($2000) limit
        
        # Update portfolio value (drawdown)
        risk_manager.update_portfolio_value(92000.0)  # 8% drawdown < 10% limit
        
        # Check drawdown
        is_valid, _ = risk_manager.check_drawdown()
        assert is_valid
        
        # Check metrics
        assert risk_manager.metrics.win_rate == 2/3  # 2 wins out of 3 trades
        assert risk_manager.metrics.avg_win == 650.0  # (500+800)/2
        assert risk_manager.metrics.avg_loss == 200.0

    def test_edge_case_zero_values(self, risk_manager):
        """Test edge cases with zero values."""
        # Zero entry price for stop loss/take profit
        stop_loss = risk_manager.get_stop_loss_price(0.0, "buy")
        take_profit = risk_manager.get_take_profit_price(0.0, "buy")
        
        assert stop_loss == 0.0
        assert take_profit == 0.0
        
        # Zero position size calculation
        position_size = risk_manager.calculate_position_size(0, 0.01, 0.02)
        assert position_size == 0

    def test_custom_parameters_usage(self, custom_risk_manager):
        """Test that custom parameters are properly used."""
        # Test custom max position size (15%)
        is_valid, _ = custom_risk_manager.check_position_size(12000, 100000)  # 12% < 15%
        assert is_valid
        
        is_valid, _ = custom_risk_manager.check_position_size(18000, 100000)  # 18% > 15%
        assert not is_valid
        
        # Test custom stop loss (2.5%)
        entry_price = 100.0
        stop_loss = custom_risk_manager.get_stop_loss_price(entry_price, "buy")
        expected = 100.0 * (1 - 0.025)  # 97.5
        assert stop_loss == expected