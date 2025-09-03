"""
Watchdog System with Kill-Switch and Notifications
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional


@dataclass
class SystemState:
    """System state for watchdog monitoring"""

    status: str = "NORMAL"
    pause_reason: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    error_window_start: datetime = field(default_factory=datetime.now)
    daily_pnl: Decimal = Decimal("0")
    daily_high_water_mark: Decimal = Decimal("0")
    clock_skew_ms: int = 0
    rate_limit_hits: int = 0

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "pause_reason": self.pause_reason,
            "last_check": self.last_check.isoformat(),
            "error_count": self.error_count,
            "daily_pnl": float(self.daily_pnl),
            "clock_skew_ms": self.clock_skew_ms,
            "rate_limit_hits": self.rate_limit_hits,
            "timestamp": datetime.now().isoformat(),
        }


class Watchdog:
    """System watchdog with multiple kill-switch conditions"""

    def __init__(self):
        self.state = SystemState()
        self.logger = logging.getLogger(__name__)
        self.pause_conditions = {
            "clock_skew": 3000,
            "error_burst_threshold": 10,
            "error_burst_window": 60,
            "daily_drawdown_pct": -1.0,
            "rate_limit_threshold": 5,
        }
        self._running = False
        self._monitor_task = None
        self.notifications_enabled = False

    async def start(self):
        """Start watchdog monitoring"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Watchdog started")

    async def stop(self):
        """Stop watchdog monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Watchdog stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                await self._check_all_conditions()
                self._save_state()
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Watchdog error: {e}")

    async def _check_all_conditions(self):
        """Check all pause conditions"""
        self.state.last_check = datetime.now()
        await self._check_clock_skew()
        self._check_error_burst()
        self._check_daily_drawdown()
        self._check_rate_limits()

    async def _check_clock_skew(self):
        """Check for clock skew with exchange"""
        try:
            import ccxt

            exchange = ccxt.binance()
            exchange_time = exchange.fetch_time()
            local_time = int(time.time() * 1000)
            self.state.clock_skew_ms = abs(exchange_time - local_time)
            if self.state.clock_skew_ms > self.pause_conditions["clock_skew"]:
                await self._pause_system(f"Clock skew too high: {self.state.clock_skew_ms}ms")
        except Exception as e:
            self.logger.warning(f"Clock skew check failed: {e}")

    def _check_error_burst(self):
        """Check for error burst"""
        current_time = datetime.now()
        window_duration = timedelta(seconds=self.pause_conditions["error_burst_window"])
        if current_time - self.state.error_window_start > window_duration:
            self.state.error_count = 0
            self.state.error_window_start = current_time
        if self.state.error_count >= self.pause_conditions["error_burst_threshold"]:
            asyncio.create_task(
                self._pause_system(
                    f"Error burst: {self.state.error_count} errors in {self.pause_conditions['error_burst_window']}s"
                )
            )

    def _check_daily_drawdown(self):
        """Check daily drawdown limit"""
        try:
            summary_path = Path("logs/pnl_summary.json")
            if summary_path.exists():
                with open(summary_path) as f:
                    data = json.load(f)
                self.state.daily_pnl = Decimal(str(data.get("pnl_percentage", 0)))
                self.state.daily_high_water_mark = max(
                    self.state.daily_pnl, self.state.daily_high_water_mark
                )
                drawdown = self.state.daily_pnl - self.state.daily_high_water_mark
                if drawdown <= Decimal(str(self.pause_conditions["daily_drawdown_pct"])):
                    asyncio.create_task(
                        self._pause_system(f"Daily drawdown limit hit: {float(drawdown):.2f}%")
                    )
        except Exception as e:
            self.logger.warning(f"Drawdown check failed: {e}")

    def _check_rate_limits(self):
        """Check for rate limit violations"""
        if self.state.rate_limit_hits >= self.pause_conditions["rate_limit_threshold"]:
            asyncio.create_task(
                self._pause_system(
                    f"Rate limit threshold exceeded: {self.state.rate_limit_hits} hits"
                )
            )

    async def _pause_system(self, reason: str):
        """Pause the system and send notifications"""
        if self.state.status == "PAUSED":
            return
        self.state.status = "PAUSED"
        self.state.pause_reason = reason
        self.logger.critical(f"SYSTEM PAUSED: {reason}")
        if self.notifications_enabled:
            await self._send_notifications(f"⚠️ SYSTEM PAUSED\n\nReason: {reason}")
        self._save_state()

    async def resume_system(self):
        """Resume system operation"""
        if self.state.status != "PAUSED":
            return
        self.state.status = "NORMAL"
        self.state.pause_reason = None
        self.state.error_count = 0
        self.state.rate_limit_hits = 0
        self.logger.info("System resumed")
        if self.notifications_enabled:
            await self._send_notifications("✅ System resumed")
        self._save_state()

    def report_error(self):
        """Report an error to the watchdog"""
        self.state.error_count += 1

    def report_rate_limit(self):
        """Report a rate limit hit"""
        self.state.rate_limit_hits += 1

    def _save_state(self):
        """Save system state to file"""
        state_path = Path("logs/system_state.json")
        state_path.parent.mkdir(exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    async def _send_notifications(self, message: str):
        """Send notifications (placeholder for actual implementation)"""
        try:
            from src.integrations.notify import send_discord, send_telegram

            try:
                await send_telegram(message)
            except Exception as e:
                self.logger.warning(f"Telegram notification failed: {e}")
            try:
                await send_discord(message)
            except Exception as e:
                self.logger.warning(f"Discord notification failed: {e}")
        except ImportError:
            self.logger.warning("Notification module not available")

    def get_status(self) -> Dict:
        """Get current watchdog status"""
        return {
            "status": self.state.status,
            "pause_reason": self.state.pause_reason,
            "error_count": self.state.error_count,
            "daily_pnl": float(self.state.daily_pnl),
            "clock_skew_ms": self.state.clock_skew_ms,
            "rate_limit_hits": self.state.rate_limit_hits,
            "last_check": self.state.last_check.isoformat(),
        }


watchdog = Watchdog()
