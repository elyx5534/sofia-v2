"""
Test Watchdog Pause Conditions
"""

import pytest
import asyncio
from decimal import Decimal
from src.core.watchdog import Watchdog, SystemState


@pytest.mark.asyncio
async def test_clock_skew_pause():
    """Test pause on clock skew"""
    watchdog = Watchdog()
    
    # Simulate high clock skew
    watchdog.state.clock_skew_ms = 5000  # 5 seconds
    
    # This should trigger pause
    if watchdog.state.clock_skew_ms > watchdog.pause_conditions["clock_skew"]:
        await watchdog._pause_system(f"Clock skew: {watchdog.state.clock_skew_ms}ms")
    
    assert watchdog.state.status == "PAUSED"
    assert "Clock skew" in watchdog.state.pause_reason


@pytest.mark.asyncio
async def test_error_burst_pause():
    """Test pause on error burst"""
    watchdog = Watchdog()
    
    # Simulate error burst
    for _ in range(12):
        watchdog.report_error()
    
    watchdog._check_error_burst()
    
    # Should be paused after 10 errors
    await asyncio.sleep(0.1)  # Let async task complete
    
    assert watchdog.state.error_count >= 10


@pytest.mark.asyncio
async def test_daily_drawdown_pause():
    """Test pause on daily drawdown"""
    watchdog = Watchdog()
    
    # Simulate drawdown
    watchdog.state.daily_pnl = Decimal("-1.5")  # -1.5%
    watchdog.state.daily_high_water_mark = Decimal("0")
    
    drawdown = watchdog.state.daily_pnl - watchdog.state.daily_high_water_mark
    
    if drawdown <= Decimal(str(watchdog.pause_conditions["daily_drawdown_pct"])):
        await watchdog._pause_system(f"Drawdown: {float(drawdown):.2f}%")
    
    assert watchdog.state.status == "PAUSED"
    assert "Drawdown" in watchdog.state.pause_reason


@pytest.mark.asyncio
async def test_rate_limit_pause():
    """Test pause on rate limit"""
    watchdog = Watchdog()
    
    # Simulate rate limit hits
    for _ in range(6):
        watchdog.report_rate_limit()
    
    watchdog._check_rate_limits()
    
    await asyncio.sleep(0.1)  # Let async task complete
    
    assert watchdog.state.rate_limit_hits >= 5


@pytest.mark.asyncio
async def test_resume_system():
    """Test system resume"""
    watchdog = Watchdog()
    
    # First pause the system
    await watchdog._pause_system("Test pause")
    assert watchdog.state.status == "PAUSED"
    
    # Now resume
    await watchdog.resume_system()
    
    assert watchdog.state.status == "NORMAL"
    assert watchdog.state.pause_reason is None
    assert watchdog.state.error_count == 0
    assert watchdog.state.rate_limit_hits == 0


def test_state_serialization():
    """Test state serialization to dict"""
    state = SystemState()
    state.status = "PAUSED"
    state.pause_reason = "Test reason"
    state.error_count = 5
    state.daily_pnl = Decimal("1.23")
    
    state_dict = state.to_dict()
    
    assert state_dict["status"] == "PAUSED"
    assert state_dict["pause_reason"] == "Test reason"
    assert state_dict["error_count"] == 5
    assert state_dict["daily_pnl"] == 1.23
    assert "timestamp" in state_dict