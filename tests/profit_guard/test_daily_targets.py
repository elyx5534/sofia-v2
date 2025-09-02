"""
Test Profit Guard Daily Targets and Scaling
"""

from decimal import Decimal

from src.core.profit_guard import ProfitGuard


def test_position_scaling():
    """Test position size scaling based on profit"""
    guard = ProfitGuard()

    # Test different profit levels
    test_cases = [
        (0.2, 1.0),  # Below first threshold, full size
        (0.3, 0.8),  # At 0.3%, scale to 80%
        (0.5, 0.5),  # At 0.5%, scale to 50%
        (0.7, 0.2),  # At 0.7%, scale to 20%
        (1.0, 0.2),  # Above all thresholds, minimum scale
    ]

    for pnl, expected_scale in test_cases:
        guard.update_pnl(pnl)
        assert float(guard.state.current_scale_factor) == expected_scale

        # Test scaled position size
        base_size = 10.0
        scaled = guard.get_scaled_position_size(base_size)
        assert scaled == base_size * expected_scale


def test_trailing_lock_activation():
    """Test trailing profit lock activation"""
    guard = ProfitGuard()

    # Should not activate below threshold
    guard.update_pnl(0.3)
    assert guard.state.trailing_stop_level is None

    # Should activate at threshold
    guard.update_pnl(0.4)
    assert guard.state.trailing_stop_level is not None
    assert float(guard.state.trailing_stop_level) == 0.3  # 0.4 - 0.1 trail distance


def test_trailing_stop_update():
    """Test trailing stop movement"""
    guard = ProfitGuard()

    # Activate trailing lock
    guard.update_pnl(0.4)
    initial_stop = guard.state.trailing_stop_level

    # Move up - should update
    guard.update_pnl(0.6)
    guard._update_trailing_stop()
    assert guard.state.trailing_stop_level > initial_stop
    assert float(guard.state.trailing_stop_level) == 0.5  # 0.6 - 0.1

    # Move down - should not update
    old_stop = guard.state.trailing_stop_level
    guard.update_pnl(0.5)
    guard._update_trailing_stop()
    assert guard.state.trailing_stop_level == old_stop  # No change


def test_trailing_stop_hit():
    """Test positions blocked when trailing stop hit"""
    guard = ProfitGuard()

    # Activate trailing lock at 0.5%
    guard.update_pnl(0.5)
    assert guard.state.trailing_stop_level is not None

    # Drop below stop level
    guard.update_pnl(0.35)  # Below 0.4 stop level
    guard._update_trailing_stop()

    assert guard.state.positions_blocked
    assert "Trailing stop hit" in guard.state.block_reason


def test_emergency_stop_daily_loss():
    """Test emergency stop on daily loss limit"""
    guard = ProfitGuard()

    # Hit daily loss limit
    guard.update_pnl(-2.1)
    guard._check_emergency_stops()

    assert guard.state.positions_blocked
    assert "Daily loss limit" in guard.state.block_reason


def test_consecutive_losses():
    """Test consecutive loss tracking"""
    guard = ProfitGuard()

    # Report wins and losses
    guard.report_trade_result(False)
    assert guard.state.consecutive_losses == 1

    guard.report_trade_result(False)
    assert guard.state.consecutive_losses == 2

    guard.report_trade_result(True)  # Win resets counter
    assert guard.state.consecutive_losses == 0

    # Hit consecutive loss limit
    for _ in range(5):
        guard.report_trade_result(False)

    guard._check_emergency_stops()
    assert guard.state.positions_blocked
    assert "Consecutive losses" in guard.state.block_reason


def test_position_permission():
    """Test position opening permission"""
    guard = ProfitGuard()

    # Normal conditions - allowed
    can_open, reason = guard.can_open_position(10.0)
    assert can_open
    assert reason is None

    # Blocked state - not allowed
    guard.state.positions_blocked = True
    guard.state.block_reason = "Test block"

    can_open, reason = guard.can_open_position(10.0)
    assert not can_open
    assert reason == "Test block"

    # Reset and test size limit
    guard.state.positions_blocked = False
    can_open, reason = guard.can_open_position(25.0)  # Exceeds 20% limit
    assert not can_open
    assert "exceeds limit" in reason


def test_daily_reset():
    """Test daily state reset"""
    guard = ProfitGuard()

    # Set some state
    guard.update_pnl(0.5)
    guard.state.consecutive_losses = 3
    guard.state.positions_blocked = True
    guard.state.block_reason = "Test"

    # Reset
    guard.reset_daily_state()

    assert guard.state.daily_pnl_pct == Decimal("0")
    assert guard.state.daily_high_water_mark == Decimal("0")
    assert guard.state.trailing_stop_level is None
    assert guard.state.current_scale_factor == Decimal("1.0")
    assert not guard.state.positions_blocked
    assert guard.state.block_reason is None
    assert guard.state.consecutive_losses == 0


def test_risk_status():
    """Test risk status reporting"""
    guard = ProfitGuard()

    # Update state
    guard.update_pnl(0.45)
    guard.report_trade_result(False)
    guard.report_trade_result(False)
    guard.report_trade_result(False)

    status = guard.get_risk_status()

    assert "state" in status
    assert "limits" in status
    assert "alerts" in status

    # Check alerts
    alerts = status["alerts"]
    assert any("Trailing stop active" in alert for alert in alerts)
    assert any("consecutive losses" in alert for alert in alerts)
    assert any("Position scaling" in alert for alert in alerts)
