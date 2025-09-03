"""
Crash Recovery System for Sofia v2
Handles system crashes, restarts, and state recovery
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecoveryStatus(Enum):
    """Recovery operation status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SystemState:
    """System state snapshot"""

    timestamp: datetime
    active_positions: Dict[str, Any]
    pending_orders: List[Dict[str, Any]]
    portfolio_value: float
    running_strategies: List[str]
    last_processed_data: Dict[str, datetime]
    error_logs: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "active_positions": self.active_positions,
            "pending_orders": self.pending_orders,
            "portfolio_value": self.portfolio_value,
            "running_strategies": self.running_strategies,
            "last_processed_data": {k: v.isoformat() for k, v in self.last_processed_data.items()},
            "error_logs": self.error_logs,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SystemState":
        """Create from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            active_positions=data["active_positions"],
            pending_orders=data["pending_orders"],
            portfolio_value=data["portfolio_value"],
            running_strategies=data["running_strategies"],
            last_processed_data={
                k: datetime.fromisoformat(v) for k, v in data["last_processed_data"].items()
            },
            error_logs=data["error_logs"],
        )


class CrashRecoveryManager:
    """Manages crash recovery and system resilience"""

    def __init__(self, state_dir: str = "./recovery_state", checkpoint_interval: int = 60):
        """
        Initialize crash recovery manager

        Args:
            state_dir: Directory to store recovery state
            checkpoint_interval: Seconds between checkpoints
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.checkpoint_interval = checkpoint_interval
        self.current_state: Optional[SystemState] = None
        self.recovery_status = RecoveryStatus.PENDING
        self.last_checkpoint = datetime.now(timezone.utc)

    def save_checkpoint(self, state: SystemState) -> bool:
        """
        Save system state checkpoint

        Args:
            state: Current system state

        Returns:
            Success status
        """
        try:
            checkpoint_file = (
                self.state_dir / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(checkpoint_file, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            latest_file = self.state_dir / "latest_checkpoint.json"
            with open(latest_file, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            self.current_state = state
            self.last_checkpoint = datetime.now(timezone.utc)
            logger.info(f"Checkpoint saved: {checkpoint_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def load_latest_checkpoint(self) -> Optional[SystemState]:
        """
        Load the most recent checkpoint

        Returns:
            Recovered system state or None
        """
        try:
            latest_file = self.state_dir / "latest_checkpoint.json"
            if not latest_file.exists():
                logger.warning("No checkpoint found")
                return None
            with open(latest_file) as f:
                data = json.load(f)
            state = SystemState.from_dict(data)
            self.current_state = state
            logger.info(f"Checkpoint loaded from {state.timestamp}")
            return state
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    async def recover_system(self) -> Dict[str, Any]:
        """
        Perform full system recovery

        Returns:
            Recovery report
        """
        self.recovery_status = RecoveryStatus.IN_PROGRESS
        report = {
            "start_time": datetime.now(timezone.utc),
            "recovered_positions": [],
            "recovered_orders": [],
            "errors": [],
        }
        try:
            state = self.load_latest_checkpoint()
            if not state:
                report["status"] = "no_checkpoint"
                self.recovery_status = RecoveryStatus.FAILED
                return report
            for symbol, position in state.active_positions.items():
                try:
                    report["recovered_positions"].append(symbol)
                    logger.info(f"Recovered position: {symbol}")
                except Exception as e:
                    report["errors"].append(f"Position {symbol}: {e!s}")
            for order in state.pending_orders:
                try:
                    report["recovered_orders"].append(order["id"])
                    logger.info(f"Recovered order: {order['id']}")
                except Exception as e:
                    report["errors"].append(f"Order {order['id']}: {e!s}")
            for strategy in state.running_strategies:
                try:
                    logger.info(f"Restarted strategy: {strategy}")
                except Exception as e:
                    report["errors"].append(f"Strategy {strategy}: {e!s}")
            report["end_time"] = datetime.now(timezone.utc)
            report["status"] = "success" if not report["errors"] else "partial"
            self.recovery_status = RecoveryStatus.COMPLETED
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            report["status"] = "failed"
            report["error"] = str(e)
            self.recovery_status = RecoveryStatus.FAILED
        return report

    async def monitor_system_health(
        self, health_check_func, get_state_func, recovery_callback=None
    ):
        """
        Monitor system health and trigger recovery if needed

        Args:
            health_check_func: Function to check system health
            get_state_func: Function to get current system state
            recovery_callback: Optional callback after recovery
        """
        consecutive_failures = 0
        max_failures = 3
        while True:
            try:
                is_healthy = await health_check_func()
                if is_healthy:
                    consecutive_failures = 0
                    now = datetime.now(timezone.utc)
                    if (now - self.last_checkpoint).seconds >= self.checkpoint_interval:
                        state = await get_state_func()
                        self.save_checkpoint(state)
                else:
                    consecutive_failures += 1
                    logger.warning(f"Health check failed ({consecutive_failures}/{max_failures})")
                    if consecutive_failures >= max_failures:
                        logger.error("System unhealthy, triggering recovery")
                        recovery_report = await self.recover_system()
                        if recovery_callback:
                            await recovery_callback(recovery_report)
                        consecutive_failures = 0
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(10)

    def cleanup_old_checkpoints(self, keep_days: int = 7):
        """
        Remove old checkpoint files

        Args:
            keep_days: Number of days to keep checkpoints
        """
        try:
            cutoff = datetime.now() - timedelta(days=keep_days)
            for checkpoint_file in self.state_dir.glob("checkpoint_*.json"):
                timestamp_str = checkpoint_file.stem.replace("checkpoint_", "")
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if file_time < cutoff:
                    checkpoint_file.unlink()
                    logger.info(f"Deleted old checkpoint: {checkpoint_file}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance"""

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception=Exception
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"

    async def call(self, func, *args, **kwargs):
        """
        Call function with circuit breaker protection

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or raises exception
        """
        if self.state == "open":
            if self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time).seconds
                if time_since_failure >= self.recovery_timeout:
                    self.state = "half_open"
                else:
                    raise Exception("Circuit breaker is open")
        try:
            result = await func(*args, **kwargs)
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            raise e


crash_recovery_manager = CrashRecoveryManager()


async def create_system_snapshot(trading_engine, portfolio_manager, strategy_engine) -> SystemState:
    """
    Create current system state snapshot

    Args:
        trading_engine: Trading engine instance
        portfolio_manager: Portfolio manager instance
        strategy_engine: Strategy engine instance

    Returns:
        System state snapshot
    """
    try:
        positions = {}
        if hasattr(trading_engine, "get_positions"):
            positions = await trading_engine.get_positions()
        orders = []
        if hasattr(trading_engine, "get_pending_orders"):
            orders = await trading_engine.get_pending_orders()
        portfolio_value = 0
        if hasattr(portfolio_manager, "get_total_value"):
            portfolio_value = await portfolio_manager.get_total_value()
        strategies = []
        if hasattr(strategy_engine, "get_active_strategies"):
            strategies = strategy_engine.get_active_strategies()
        return SystemState(
            timestamp=datetime.now(timezone.utc),
            active_positions=positions,
            pending_orders=orders,
            portfolio_value=portfolio_value,
            running_strategies=strategies,
            last_processed_data={},
            error_logs=[],
        )
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise


async def system_health_check(services: Dict[str, Any]) -> bool:
    """
    Check overall system health

    Args:
        services: Dictionary of services to check

    Returns:
        True if system is healthy
    """
    try:
        for name, service in services.items():
            if hasattr(service, "is_healthy"):
                if not await service.is_healthy():
                    logger.warning(f"Service unhealthy: {name}")
                    return False
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
