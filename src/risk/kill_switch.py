"""
Kill Switch Controller with Manual and Automatic Triggers
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import aiofiles

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Kill switch trigger types"""
    MANUAL = "MANUAL"
    DAILY_LOSS = "DAILY_LOSS"
    LATENCY = "LATENCY"
    WS_DOWNTIME = "WS_DOWNTIME"
    ERROR_RATE = "ERROR_RATE"
    POSITION_LIMIT = "POSITION_LIMIT"
    EXTERNAL = "EXTERNAL"


@dataclass
class KillSwitchEvent:
    """Kill switch event record"""
    trigger: TriggerType
    reason: str
    timestamp: datetime
    metadata: Dict[str, Any]
    activated: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'trigger': self.trigger.value,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'activated': self.activated
        }


class KillSwitch:
    """Kill switch controller with persistence"""
    
    def __init__(self, risk_engine=None):
        self.risk_engine = risk_engine
        self.state_file = "kill_switch_state.json"
        self.events: List[KillSwitchEvent] = []
        self.callbacks: List[Callable] = []
        
        # Thresholds for automatic triggers
        self.error_rate_threshold = 0.1  # 10% error rate
        self.error_window_seconds = 60
        self.recent_errors: List[datetime] = []
        
        # Load persisted state
        self._load_state()
        
        logger.info(f"Kill Switch initialized: state={self.get_state()}")
    
    def _load_state(self):
        """Load persisted kill switch state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    
                    # Restore state to risk engine
                    if self.risk_engine and 'state' in data:
                        self.risk_engine.update_kill_switch(data['state'])
                    
                    # Restore events
                    if 'events' in data:
                        for event_data in data['events'][-100:]:  # Keep last 100
                            event = KillSwitchEvent(
                                trigger=TriggerType[event_data['trigger']],
                                reason=event_data['reason'],
                                timestamp=datetime.fromisoformat(event_data['timestamp']),
                                metadata=event_data['metadata'],
                                activated=event_data['activated']
                            )
                            self.events.append(event)
                    
                    logger.info(f"Kill switch state loaded: {len(self.events)} events")
        except Exception as e:
            logger.error(f"Failed to load kill switch state: {e}")
    
    async def _save_state(self):
        """Persist kill switch state"""
        try:
            state_data = {
                'state': self.get_state(),
                'events': [event.to_dict() for event in self.events[-100:]],
                'last_updated': datetime.now().isoformat()
            }
            
            async with aiofiles.open(self.state_file, 'w') as f:
                await f.write(json.dumps(state_data, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")
    
    def get_state(self) -> str:
        """Get current kill switch state"""
        if self.risk_engine:
            return self.risk_engine.kill_switch.value
        return "OFF"
    
    def register_callback(self, callback: Callable):
        """Register callback for kill switch events"""
        self.callbacks.append(callback)
    
    async def _trigger_callbacks(self, event: KillSwitchEvent):
        """Trigger registered callbacks"""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def activate(self, trigger: TriggerType, reason: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Activate kill switch
        
        Returns:
            True if activated, False if already active
        """
        current_state = self.get_state()
        
        if current_state == "ON":
            logger.warning("Kill switch already active")
            return False
        
        # Create event
        event = KillSwitchEvent(
            trigger=trigger,
            reason=reason,
            timestamp=datetime.now(),
            metadata=metadata or {},
            activated=True
        )
        self.events.append(event)
        
        # Update risk engine
        if self.risk_engine:
            self.risk_engine.update_kill_switch("ON")
        
        # Log critical event
        logger.critical(json.dumps({
            'event': 'kill_switch_activated',
            'trigger': trigger.value,
            'reason': reason,
            'metadata': metadata,
            'timestamp': datetime.now().isoformat()
        }))
        
        # Save state
        await self._save_state()
        
        # Trigger callbacks
        await self._trigger_callbacks(event)
        
        return True
    
    async def deactivate(self, reason: str = "Manual deactivation") -> bool:
        """
        Deactivate kill switch
        
        Returns:
            True if deactivated, False if already inactive
        """
        current_state = self.get_state()
        
        if current_state == "OFF":
            logger.warning("Kill switch already inactive")
            return False
        
        # Create event
        event = KillSwitchEvent(
            trigger=TriggerType.MANUAL,
            reason=reason,
            timestamp=datetime.now(),
            metadata={'previous_state': current_state},
            activated=False
        )
        self.events.append(event)
        
        # Update risk engine
        if self.risk_engine:
            self.risk_engine.update_kill_switch("OFF")
        
        # Log event
        logger.warning(json.dumps({
            'event': 'kill_switch_deactivated',
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }))
        
        # Save state
        await self._save_state()
        
        # Trigger callbacks
        await self._trigger_callbacks(event)
        
        return True
    
    async def set_auto_mode(self, enabled: bool = True) -> bool:
        """Enable or disable automatic mode"""
        new_state = "AUTO" if enabled else "OFF"
        
        if self.risk_engine:
            self.risk_engine.update_kill_switch(new_state)
        
        # Create event
        event = KillSwitchEvent(
            trigger=TriggerType.MANUAL,
            reason=f"Auto mode {'enabled' if enabled else 'disabled'}",
            timestamp=datetime.now(),
            metadata={'auto_mode': enabled},
            activated=False
        )
        self.events.append(event)
        
        # Save state
        await self._save_state()
        
        logger.info(f"Kill switch auto mode: {enabled}")
        return True
    
    def record_error(self):
        """Record an error for error rate monitoring"""
        now = datetime.now()
        self.recent_errors.append(now)
        
        # Clean old errors
        cutoff = now - timedelta(seconds=self.error_window_seconds)
        self.recent_errors = [t for t in self.recent_errors if t > cutoff]
    
    async def check_error_rate(self, total_requests: int) -> bool:
        """
        Check if error rate exceeds threshold
        
        Returns:
            True if kill switch was activated
        """
        if total_requests == 0:
            return False
        
        error_count = len(self.recent_errors)
        error_rate = error_count / total_requests
        
        if error_rate > self.error_rate_threshold:
            await self.activate(
                trigger=TriggerType.ERROR_RATE,
                reason=f"Error rate {error_rate:.1%} exceeded threshold",
                metadata={
                    'error_count': error_count,
                    'total_requests': total_requests,
                    'error_rate': error_rate,
                    'threshold': self.error_rate_threshold
                }
            )
            return True
        
        return False
    
    async def check_daily_loss(self, daily_pnl: float, max_loss: float) -> bool:
        """
        Check if daily loss exceeded
        
        Returns:
            True if kill switch was activated
        """
        if daily_pnl < -max_loss:
            await self.activate(
                trigger=TriggerType.DAILY_LOSS,
                reason=f"Daily loss ${abs(daily_pnl):.2f} exceeded limit",
                metadata={
                    'daily_pnl': daily_pnl,
                    'max_loss': max_loss,
                    'exceeded_by': abs(daily_pnl) - max_loss
                }
            )
            return True
        
        return False
    
    async def check_latency(self, latency_ms: float, threshold_ms: float) -> bool:
        """
        Check if latency exceeded threshold
        
        Returns:
            True if kill switch was activated
        """
        if latency_ms > threshold_ms:
            await self.activate(
                trigger=TriggerType.LATENCY,
                reason=f"Latency {latency_ms:.0f}ms exceeded threshold",
                metadata={
                    'latency_ms': latency_ms,
                    'threshold_ms': threshold_ms,
                    'exceeded_by': latency_ms - threshold_ms
                }
            )
            return True
        
        return False
    
    async def check_ws_downtime(self, downtime_seconds: float, threshold_seconds: float) -> bool:
        """
        Check if WebSocket downtime exceeded
        
        Returns:
            True if kill switch was activated
        """
        if downtime_seconds > threshold_seconds:
            await self.activate(
                trigger=TriggerType.WS_DOWNTIME,
                reason=f"WebSocket down for {downtime_seconds:.0f}s",
                metadata={
                    'downtime_seconds': downtime_seconds,
                    'threshold_seconds': threshold_seconds,
                    'exceeded_by': downtime_seconds - threshold_seconds
                }
            )
            return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status"""
        recent_events = self.events[-10:] if self.events else []
        
        return {
            'state': self.get_state(),
            'total_events': len(self.events),
            'recent_events': [event.to_dict() for event in recent_events],
            'error_count': len(self.recent_errors),
            'error_rate': len(self.recent_errors) / max(1, len(self.events)) if self.events else 0,
            'last_activation': next(
                (event.timestamp.isoformat() for event in reversed(self.events) if event.activated),
                None
            ),
            'last_deactivation': next(
                (event.timestamp.isoformat() for event in reversed(self.events) if not event.activated),
                None
            )
        }
    
    def get_events(self, limit: int = 100, trigger: Optional[TriggerType] = None) -> List[Dict[str, Any]]:
        """Get kill switch events"""
        events = self.events
        
        if trigger:
            events = [e for e in events if e.trigger == trigger]
        
        return [event.to_dict() for event in events[-limit:]]