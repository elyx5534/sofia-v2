"""
Risk Engine with pre-trade and runtime checks
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio

logger = logging.getLogger(__name__)


class RiskAction(Enum):
    """Risk action types"""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"
    HALT = "HALT"


class KillSwitchState(Enum):
    """Kill switch states"""
    OFF = "OFF"
    ON = "ON"
    AUTO = "AUTO"


@dataclass
class RiskCheck:
    """Risk check result"""
    name: str
    action: RiskAction
    reason: Optional[str] = None
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['action'] = self.action.value
        d['timestamp'] = self.timestamp.isoformat()
        return d


class RiskEngine:
    """Risk management engine with circuit breakers"""
    
    def __init__(self):
        # Configuration from environment
        self.max_daily_loss = Decimal(os.getenv('MAX_DAILY_LOSS', '200'))
        self.max_position_usd = Decimal(os.getenv('MAX_POSITION_USD', '1000'))
        self.max_symbol_exposure = Decimal(os.getenv('MAX_SYMBOL_EXPOSURE_USD', '500'))
        self.single_order_max = Decimal(os.getenv('SINGLE_ORDER_MAX_USD', '100'))
        self.slippage_bps = int(os.getenv('SLIPPAGE_BPS', '50'))
        
        # Latency and downtime thresholds
        self.halt_on_latency_us = int(os.getenv('HALT_ON_LAT_MICROSECONDS', '5000000'))  # 5 seconds
        self.halt_on_ws_downtime = int(os.getenv('HALT_ON_WS_DOWNTIME_SEC', '30'))
        
        # Kill switch
        self.kill_switch = KillSwitchState[os.getenv('KILL_SWITCH', 'OFF')]
        
        # State tracking
        self.daily_pnl = Decimal('0')
        self.positions: Dict[str, Decimal] = {}
        self.open_orders: Dict[str, Dict] = {}
        self.last_ws_heartbeat = datetime.now()
        self.latency_samples: List[int] = []
        self.audit_log: List[RiskCheck] = []
        self.halt_reasons: List[str] = []
        
        # Runtime metrics
        self.checks_performed = 0
        self.checks_blocked = 0
        self.auto_halts = 0
        
        logger.info(f"Risk Engine initialized: max_daily_loss={self.max_daily_loss}, kill_switch={self.kill_switch.value}")
    
    def update_kill_switch(self, state: str) -> bool:
        """Update kill switch state"""
        try:
            new_state = KillSwitchState[state.upper()]
            old_state = self.kill_switch
            self.kill_switch = new_state
            
            logger.warning(json.dumps({
                'event': 'kill_switch_changed',
                'old_state': old_state.value,
                'new_state': new_state.value,
                'timestamp': datetime.now().isoformat()
            }))
            
            if new_state == KillSwitchState.ON:
                self.halt_reasons.append(f"Manual kill switch activated at {datetime.now().isoformat()}")
            
            return True
        except KeyError:
            logger.error(f"Invalid kill switch state: {state}")
            return False
    
    def update_ws_heartbeat(self):
        """Update WebSocket heartbeat timestamp"""
        self.last_ws_heartbeat = datetime.now()
    
    def add_latency_sample(self, latency_us: int):
        """Add latency sample for monitoring"""
        self.latency_samples.append(latency_us)
        # Keep last 100 samples
        if len(self.latency_samples) > 100:
            self.latency_samples.pop(0)
    
    def update_daily_pnl(self, pnl: Decimal):
        """Update daily P&L"""
        self.daily_pnl = pnl
        
        # Auto-halt if daily loss exceeded
        if self.kill_switch == KillSwitchState.AUTO:
            if self.daily_pnl < -self.max_daily_loss:
                self.kill_switch = KillSwitchState.ON
                self.halt_reasons.append(f"Auto-halt: Daily loss {self.daily_pnl} exceeded limit {-self.max_daily_loss}")
                self.auto_halts += 1
                
                logger.critical(json.dumps({
                    'event': 'auto_halt_triggered',
                    'reason': 'daily_loss_exceeded',
                    'daily_pnl': str(self.daily_pnl),
                    'max_loss': str(self.max_daily_loss),
                    'timestamp': datetime.now().isoformat()
                }))
    
    def update_position(self, symbol: str, position_usd: Decimal):
        """Update position tracking"""
        if position_usd == 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = abs(position_usd)
    
    async def pre_trade_check(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        current_price: Optional[Decimal] = None
    ) -> RiskCheck:
        """
        Perform pre-trade risk checks
        
        Returns:
            RiskCheck with action (ALLOW/BLOCK/WARN)
        """
        self.checks_performed += 1
        
        # Check 1: Kill switch
        if self.kill_switch == KillSwitchState.ON:
            check = RiskCheck(
                name="kill_switch",
                action=RiskAction.BLOCK,
                reason="Kill switch is ON",
                value=self.kill_switch.value
            )
            self._audit(check)
            self.checks_blocked += 1
            return check
        
        # Calculate notional value
        if order_type == 'market' and current_price:
            notional = quantity * current_price
        elif order_type == 'limit' and price:
            notional = quantity * price
        else:
            # Can't calculate, allow with warning
            check = RiskCheck(
                name="notional_calculation",
                action=RiskAction.WARN,
                reason="Cannot calculate notional value"
            )
            self._audit(check)
            return check
        
        # Check 2: Single order size
        if notional > self.single_order_max:
            check = RiskCheck(
                name="single_order_size",
                action=RiskAction.BLOCK,
                reason=f"Order size {notional} exceeds limit",
                value=str(notional),
                threshold=str(self.single_order_max)
            )
            self._audit(check)
            self.checks_blocked += 1
            return check
        
        # Check 3: Symbol exposure
        current_exposure = self.positions.get(symbol, Decimal('0'))
        new_exposure = current_exposure + notional
        
        if new_exposure > self.max_symbol_exposure:
            check = RiskCheck(
                name="symbol_exposure",
                action=RiskAction.BLOCK,
                reason=f"Symbol exposure {new_exposure} exceeds limit",
                value=str(new_exposure),
                threshold=str(self.max_symbol_exposure)
            )
            self._audit(check)
            self.checks_blocked += 1
            return check
        
        # Check 4: Total position
        total_position = sum(self.positions.values()) + notional
        if total_position > self.max_position_usd:
            check = RiskCheck(
                name="total_position",
                action=RiskAction.BLOCK,
                reason=f"Total position {total_position} exceeds limit",
                value=str(total_position),
                threshold=str(self.max_position_usd)
            )
            self._audit(check)
            self.checks_blocked += 1
            return check
        
        # Check 5: Daily loss (if already in loss)
        if self.daily_pnl < 0:
            potential_loss = abs(self.daily_pnl) + notional
            if potential_loss > self.max_daily_loss * Decimal('0.8'):  # Warn at 80%
                check = RiskCheck(
                    name="daily_loss_warning",
                    action=RiskAction.WARN,
                    reason=f"Approaching daily loss limit",
                    value=str(self.daily_pnl),
                    threshold=str(self.max_daily_loss)
                )
                self._audit(check)
                # Don't block, just warn
        
        # Check 6: Slippage for market orders
        if order_type == 'market' and price and current_price:
            slippage_bps_actual = abs((current_price - price) / price) * 10000
            if slippage_bps_actual > self.slippage_bps:
                check = RiskCheck(
                    name="slippage",
                    action=RiskAction.WARN,
                    reason=f"High slippage detected",
                    value=f"{slippage_bps_actual:.0f}bps",
                    threshold=f"{self.slippage_bps}bps"
                )
                self._audit(check)
                # Don't block market orders for slippage, just warn
        
        # All checks passed
        check = RiskCheck(
            name="pre_trade",
            action=RiskAction.ALLOW,
            reason="All checks passed"
        )
        self._audit(check)
        return check
    
    async def runtime_check(self) -> RiskCheck:
        """
        Perform runtime risk checks
        
        Returns:
            RiskCheck with action (ALLOW/HALT)
        """
        # Check 1: WebSocket downtime
        ws_downtime = (datetime.now() - self.last_ws_heartbeat).total_seconds()
        if ws_downtime > self.halt_on_ws_downtime:
            check = RiskCheck(
                name="ws_downtime",
                action=RiskAction.HALT,
                reason=f"WebSocket down for {ws_downtime:.0f}s",
                value=f"{ws_downtime:.0f}s",
                threshold=f"{self.halt_on_ws_downtime}s"
            )
            self._audit(check)
            
            if self.kill_switch == KillSwitchState.AUTO:
                self.kill_switch = KillSwitchState.ON
                self.halt_reasons.append(f"Auto-halt: WebSocket downtime {ws_downtime}s")
                self.auto_halts += 1
            
            return check
        
        # Check 2: Latency
        if self.latency_samples:
            avg_latency = sum(self.latency_samples) / len(self.latency_samples)
            if avg_latency > self.halt_on_latency_us:
                check = RiskCheck(
                    name="high_latency",
                    action=RiskAction.HALT,
                    reason=f"Average latency {avg_latency/1000:.0f}ms exceeds threshold",
                    value=f"{avg_latency/1000:.0f}ms",
                    threshold=f"{self.halt_on_latency_us/1000:.0f}ms"
                )
                self._audit(check)
                
                if self.kill_switch == KillSwitchState.AUTO:
                    self.kill_switch = KillSwitchState.ON
                    self.halt_reasons.append(f"Auto-halt: High latency {avg_latency/1000:.0f}ms")
                    self.auto_halts += 1
                
                return check
        
        # Check 3: Daily loss
        if self.daily_pnl < -self.max_daily_loss:
            check = RiskCheck(
                name="daily_loss",
                action=RiskAction.HALT,
                reason=f"Daily loss {self.daily_pnl} exceeded",
                value=str(self.daily_pnl),
                threshold=str(self.max_daily_loss)
            )
            self._audit(check)
            
            if self.kill_switch == KillSwitchState.AUTO:
                self.kill_switch = KillSwitchState.ON
                self.halt_reasons.append(f"Auto-halt: Daily loss exceeded")
                self.auto_halts += 1
            
            return check
        
        # All runtime checks passed
        return RiskCheck(
            name="runtime",
            action=RiskAction.ALLOW,
            reason="All runtime checks passed"
        )
    
    def _audit(self, check: RiskCheck):
        """Add check to audit log"""
        self.audit_log.append(check)
        
        # Keep last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log.pop(0)
        
        # Log critical events
        if check.action in [RiskAction.BLOCK, RiskAction.HALT]:
            logger.warning(json.dumps({
                'event': 'risk_check_failed',
                'check': check.name,
                'action': check.action.value,
                'reason': check.reason,
                'value': check.value,
                'threshold': check.threshold,
                'timestamp': check.timestamp.isoformat()
            }))
    
    def get_status(self) -> Dict[str, Any]:
        """Get risk engine status"""
        return {
            'kill_switch': self.kill_switch.value,
            'daily_pnl': str(self.daily_pnl),
            'total_position': str(sum(self.positions.values())),
            'positions': {k: str(v) for k, v in self.positions.items()},
            'checks_performed': self.checks_performed,
            'checks_blocked': self.checks_blocked,
            'auto_halts': self.auto_halts,
            'halt_reasons': self.halt_reasons[-5:],  # Last 5 reasons
            'ws_downtime': (datetime.now() - self.last_ws_heartbeat).total_seconds(),
            'avg_latency_ms': sum(self.latency_samples) / len(self.latency_samples) / 1000 if self.latency_samples else 0,
            'last_check': self.audit_log[-1].to_dict() if self.audit_log else None
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries"""
        return [check.to_dict() for check in self.audit_log[-limit:]]
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at EOD)"""
        logger.info(json.dumps({
            'event': 'daily_stats_reset',
            'daily_pnl': str(self.daily_pnl),
            'checks_performed': self.checks_performed,
            'checks_blocked': self.checks_blocked,
            'timestamp': datetime.now().isoformat()
        }))
        
        self.daily_pnl = Decimal('0')
        self.checks_performed = 0
        self.checks_blocked = 0
        # Don't reset positions or kill switch state