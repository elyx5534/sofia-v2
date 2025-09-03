"""
Advanced Risk Manager with Profit Guard and Trailing Lock
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Current risk management state"""

    daily_pnl_pct: Decimal = Decimal("0")
    daily_high_water_mark: Decimal = Decimal("0")
    trailing_stop_level: Optional[Decimal] = None
    current_scale_factor: Decimal = Decimal("1.0")
    positions_blocked: bool = False
    block_reason: Optional[str] = None
    consecutive_losses: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "daily_pnl_pct": float(self.daily_pnl_pct),
            "daily_high_water_mark": float(self.daily_high_water_mark),
            "trailing_stop_level": (
                float(self.trailing_stop_level) if self.trailing_stop_level else None
            ),
            "current_scale_factor": float(self.current_scale_factor),
            "positions_blocked": self.positions_blocked,
            "block_reason": self.block_reason,
            "consecutive_losses": self.consecutive_losses,
            "last_reset": self.last_reset.isoformat(),
        }


class ProfitGuard:
    """Profit protection and scaling system"""

    def __init__(self, config_path: str = "config/risk.yaml"):
        self.config = self._load_config(config_path)
        self.state = RiskState()
        self.logger = logging.getLogger(f"{__name__}.ProfitGuard")
        self._monitor_task = None

    def _load_config(self, config_path: str) -> Dict:
        """Load risk configuration"""
        path = Path(config_path)
        if not path.exists():
            return {
                "daily_targets": {
                    "profit_target_pct": 0.5,
                    "max_drawdown_pct": -1.0,
                    "scale_on_profit": {0.3: 0.8, 0.5: 0.5, 0.7: 0.2},
                    "trailing_lock": {
                        "enabled": True,
                        "lock_profit_at": 0.4,
                        "trail_distance": 0.1,
                    },
                },
                "position_limits": {
                    "max_position_size_pct": 20,
                    "max_total_exposure_pct": 60,
                    "max_concurrent_positions": 5,
                },
                "emergency_stops": {
                    "daily_loss_limit_pct": -2.0,
                    "consecutive_losses": 5,
                    "cooldown_minutes": 30,
                    "reset_at_utc": "00:00",
                },
            }
        with open(path) as f:
            return yaml.safe_load(f)

    async def start_monitoring(self):
        """Start risk monitoring"""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Profit guard monitoring started")

    async def stop_monitoring(self):
        """Stop risk monitoring"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Profit guard monitoring stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._check_daily_reset()
                self._update_trailing_stop()
                self._check_emergency_stops()
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")

    async def _check_daily_reset(self):
        """Check if daily limits should reset"""
        reset_time_str = self.config["emergency_stops"]["reset_at_utc"]
        reset_hour, reset_minute = map(int, reset_time_str.split(":"))
        reset_time = time(reset_hour, reset_minute)
        now = datetime.utcnow()
        if now.time() >= reset_time and (now - self.state.last_reset).total_seconds() > 3600:
            self.reset_daily_state()
            self.logger.info("Daily risk state reset")

    def reset_daily_state(self):
        """Reset daily risk metrics"""
        self.state.daily_pnl_pct = Decimal("0")
        self.state.daily_high_water_mark = Decimal("0")
        self.state.trailing_stop_level = None
        self.state.current_scale_factor = Decimal("1.0")
        self.state.positions_blocked = False
        self.state.block_reason = None
        self.state.consecutive_losses = 0
        self.state.last_reset = datetime.now()

    def update_pnl(self, pnl_pct: float):
        """Update daily P&L and adjust risk parameters"""
        self.state.daily_pnl_pct = Decimal(str(pnl_pct))
        self.state.daily_high_water_mark = max(
            self.state.daily_pnl_pct, self.state.daily_high_water_mark
        )
        self._update_position_scaling()
        self._check_trailing_lock_activation()

    def _update_position_scaling(self):
        """Update position size scaling based on daily P&L"""
        scale_config = self.config["daily_targets"]["scale_on_profit"]
        scale_factor = Decimal("1.0")
        for threshold, scale in sorted(scale_config.items()):
            if float(self.state.daily_pnl_pct) >= threshold:
                scale_factor = Decimal(str(scale))
        self.state.current_scale_factor = scale_factor
        if scale_factor < Decimal("1.0"):
            self.logger.info(
                f"Position scaling adjusted to {float(scale_factor) * 100:.0f}% due to profit level"
            )

    def _check_trailing_lock_activation(self):
        """Check if trailing profit lock should activate"""
        trail_config = self.config["daily_targets"]["trailing_lock"]
        if not trail_config["enabled"]:
            return
        lock_at = Decimal(str(trail_config["lock_profit_at"]))
        trail_distance = Decimal(str(trail_config["trail_distance"]))
        if self.state.daily_pnl_pct >= lock_at and self.state.trailing_stop_level is None:
            self.state.trailing_stop_level = self.state.daily_pnl_pct - trail_distance
            self.logger.info(
                f"Trailing profit lock activated at {float(self.state.trailing_stop_level):.2f}%"
            )

    def _update_trailing_stop(self):
        """Update trailing stop level"""
        if self.state.trailing_stop_level is None:
            return
        trail_distance = Decimal(
            str(self.config["daily_targets"]["trailing_lock"]["trail_distance"])
        )
        new_stop_level = self.state.daily_pnl_pct - trail_distance
        if new_stop_level > self.state.trailing_stop_level:
            self.state.trailing_stop_level = new_stop_level
            self.logger.info(
                f"Trailing stop updated to {float(self.state.trailing_stop_level):.2f}%"
            )
        if self.state.daily_pnl_pct <= self.state.trailing_stop_level:
            self.state.positions_blocked = True
            self.state.block_reason = (
                f"Trailing stop hit at {float(self.state.trailing_stop_level):.2f}%"
            )
            self.logger.warning(f"Positions blocked: {self.state.block_reason}")

    def _check_emergency_stops(self):
        """Check emergency stop conditions"""
        emergency = self.config["emergency_stops"]
        if float(self.state.daily_pnl_pct) <= emergency["daily_loss_limit_pct"]:
            self.state.positions_blocked = True
            self.state.block_reason = (
                f"Daily loss limit hit: {float(self.state.daily_pnl_pct):.2f}%"
            )
            self.logger.critical(f"EMERGENCY STOP: {self.state.block_reason}")
        if self.state.consecutive_losses >= emergency["consecutive_losses"]:
            self.state.positions_blocked = True
            self.state.block_reason = f"Consecutive losses: {self.state.consecutive_losses}"
            self.logger.critical(f"EMERGENCY STOP: {self.state.block_reason}")

    def report_trade_result(self, is_win: bool):
        """Report trade result for consecutive loss tracking"""
        if is_win:
            self.state.consecutive_losses = 0
        else:
            self.state.consecutive_losses += 1

    def can_open_position(self, size_pct: float) -> Tuple[bool, Optional[str]]:
        """Check if new position can be opened"""
        if self.state.positions_blocked:
            return (False, self.state.block_reason)
        max_size = self.config["position_limits"]["max_position_size_pct"]
        scaled_size = size_pct * float(self.state.current_scale_factor)
        if scaled_size > max_size:
            return (False, f"Position size {scaled_size:.1f}% exceeds limit {max_size}%")
        return (True, None)

    def get_scaled_position_size(self, base_size: float) -> float:
        """Get scaled position size based on current risk state"""
        return base_size * float(self.state.current_scale_factor)

    def get_risk_status(self) -> Dict:
        """Get current risk status"""
        return {
            "state": self.state.to_dict(),
            "limits": {
                "daily_target": self.config["daily_targets"]["profit_target_pct"],
                "max_drawdown": self.config["daily_targets"]["max_drawdown_pct"],
                "current_scale": float(self.state.current_scale_factor),
                "can_trade": not self.state.positions_blocked,
            },
            "alerts": self._get_risk_alerts(),
        }

    def _get_risk_alerts(self) -> List[str]:
        """Get current risk alerts"""
        alerts = []
        if self.state.positions_blocked:
            alerts.append(f"BLOCKED: {self.state.block_reason}")
        if self.state.trailing_stop_level is not None:
            alerts.append(f"Trailing stop active at {float(self.state.trailing_stop_level):.2f}%")
        if self.state.current_scale_factor < Decimal("1.0"):
            alerts.append(
                f"Position scaling at {float(self.state.current_scale_factor) * 100:.0f}%"
            )
        if self.state.consecutive_losses > 2:
            alerts.append(f"Warning: {self.state.consecutive_losses} consecutive losses")
        return alerts


profit_guard = ProfitGuard()
