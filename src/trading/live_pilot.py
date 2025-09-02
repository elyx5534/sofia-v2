"""
Live Trading Pilot System with Multiple Safety Guards
Gradual transition from paper to live trading with strict controls
"""

import os
import json
import asyncio
from enum import Enum
from decimal import Decimal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode stages"""
    PAPER = "paper"  # Full paper trading
    SHADOW = "shadow"  # Paper trading with live order validation
    PILOT = "pilot"  # Live trading with strict limits
    SCALED = "scaled"  # Scaled live trading
    FULL = "full"  # Full live trading


@dataclass
class PilotLimits:
    """Pilot trading limits"""
    max_position_size_usd: Decimal = Decimal("50")  # Start with $50 max
    max_daily_trades: int = 10
    max_open_positions: int = 2
    max_daily_loss_usd: Decimal = Decimal("25")
    allowed_symbols: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    required_paper_profit_pct: float = 2.0  # Need 2% paper profit before pilot
    required_paper_trades: int = 100  # Need 100 paper trades before pilot
    

@dataclass
class PilotState:
    """Current pilot state"""
    mode: TradingMode = TradingMode.PAPER
    paper_stats: Dict = field(default_factory=dict)
    pilot_stats: Dict = field(default_factory=dict)
    daily_trades: int = 0
    daily_pnl_usd: Decimal = Decimal("0")
    open_positions: List[Dict] = field(default_factory=list)
    mode_started_at: datetime = field(default_factory=datetime.now)
    violations: List[str] = field(default_factory=list)
    emergency_stop_triggered: bool = False
    

class LiveTradingPilot:
    """Manages transition from paper to live trading"""
    
    def __init__(self, config_file: str = "config/pilot.json"):
        self.config_file = Path(config_file)
        self.limits = PilotLimits()
        self.state = PilotState()
        self.logger = logging.getLogger(f"{__name__}.LivePilot")
        
        # Load configuration
        self._load_config()
        
        # Safety checks
        self.pre_trade_checks = [
            self._check_mode_requirements,
            self._check_daily_limits,
            self._check_position_limits,
            self._check_symbol_allowed,
            self._check_risk_limits,
        ]
        
        self.post_trade_checks = [
            self._check_daily_pnl,
            self._check_consecutive_losses,
            self._check_error_rate,
        ]
        
        # Monitoring
        self._monitor_task = None
        self._last_health_check = datetime.now()
        
    def _load_config(self):
        """Load pilot configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            # Load limits
            if 'limits' in config:
                for key, value in config['limits'].items():
                    if hasattr(self.limits, key):
                        if key in ['max_position_size_usd', 'max_daily_loss_usd']:
                            setattr(self.limits, key, Decimal(str(value)))
                        else:
                            setattr(self.limits, key, value)
                            
            # Load state
            if 'state' in config:
                self.state.mode = TradingMode(config['state'].get('mode', 'paper'))
                self.state.paper_stats = config['state'].get('paper_stats', {})
                self.state.pilot_stats = config['state'].get('pilot_stats', {})
                
        self._save_config()
        
    def _save_config(self):
        """Save pilot configuration"""
        self.config_file.parent.mkdir(exist_ok=True)
        
        config = {
            'limits': {
                'max_position_size_usd': float(self.limits.max_position_size_usd),
                'max_daily_trades': self.limits.max_daily_trades,
                'max_open_positions': self.limits.max_open_positions,
                'max_daily_loss_usd': float(self.limits.max_daily_loss_usd),
                'allowed_symbols': self.limits.allowed_symbols,
                'required_paper_profit_pct': self.limits.required_paper_profit_pct,
                'required_paper_trades': self.limits.required_paper_trades,
            },
            'state': {
                'mode': self.state.mode.value,
                'paper_stats': self.state.paper_stats,
                'pilot_stats': self.state.pilot_stats,
                'mode_started_at': self.state.mode_started_at.isoformat(),
                'emergency_stop_triggered': self.state.emergency_stop_triggered,
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
    async def start_monitoring(self):
        """Start pilot monitoring"""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info(f"Live pilot monitoring started in {self.state.mode.value} mode")
        
    async def stop_monitoring(self):
        """Stop pilot monitoring"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Live pilot monitoring stopped")
        
    async def _monitor_loop(self):
        """Monitor pilot trading health"""
        while True:
            try:
                # Health check every minute
                if (datetime.now() - self._last_health_check).seconds >= 60:
                    await self._health_check()
                    self._last_health_check = datetime.now()
                    
                # Reset daily counters at midnight
                if datetime.now().hour == 0 and datetime.now().minute == 0:
                    self._reset_daily_counters()
                    
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                
    async def _health_check(self):
        """Perform system health check"""
        checks_passed = []
        checks_failed = []
        
        # Check API connectivity
        api_healthy = await self._check_api_health()
        if api_healthy:
            checks_passed.append("API connectivity")
        else:
            checks_failed.append("API connectivity")
            
        # Check account balance
        balance_healthy = await self._check_account_balance()
        if balance_healthy:
            checks_passed.append("Account balance")
        else:
            checks_failed.append("Account balance")
            
        # Check for violations
        if not self.state.violations:
            checks_passed.append("No violations")
        else:
            checks_failed.append(f"{len(self.state.violations)} violations")
            
        # Log health status
        if checks_failed:
            self.logger.warning(f"Health check - Passed: {checks_passed}, Failed: {checks_failed}")
        else:
            self.logger.info(f"Health check - All {len(checks_passed)} checks passed")
            
        # Emergency stop if critical failures
        if "API connectivity" in checks_failed or "Account balance" in checks_failed:
            await self._trigger_emergency_stop("Critical health check failure")
            
    async def _check_api_health(self) -> bool:
        """Check API connectivity"""
        # Implement actual API health check
        return True  # Placeholder
        
    async def _check_account_balance(self) -> bool:
        """Check account balance is sufficient"""
        # Implement actual balance check
        return True  # Placeholder
        
    def can_execute_trade(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check if trade can be executed in current mode"""
        # Run pre-trade checks
        for check in self.pre_trade_checks:
            passed, reason = check(trade_request)
            if not passed:
                self.logger.warning(f"Trade rejected: {reason}")
                return False, reason
                
        # Mode-specific logic
        if self.state.mode == TradingMode.PAPER:
            return True, None  # Always allow paper trades
            
        elif self.state.mode == TradingMode.SHADOW:
            # Validate but don't execute
            self.logger.info("Shadow mode: Trade validated but not executed")
            return False, "Shadow mode - validation only"
            
        elif self.state.mode == TradingMode.PILOT:
            # Check pilot limits
            size_usd = Decimal(str(trade_request.get('size_usd', 0)))
            if size_usd > self.limits.max_position_size_usd:
                return False, f"Size ${size_usd} exceeds pilot limit ${self.limits.max_position_size_usd}"
            return True, None
            
        elif self.state.mode == TradingMode.SCALED:
            # Allow scaled positions
            return True, None
            
        elif self.state.mode == TradingMode.FULL:
            # Full trading allowed
            return True, None
            
        return False, f"Unknown mode: {self.state.mode}"
        
    def _check_mode_requirements(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check if mode requirements are met"""
        if self.state.mode == TradingMode.PAPER:
            return True, None
            
        # Check paper trading requirements for pilot
        if self.state.mode in [TradingMode.PILOT, TradingMode.SHADOW]:
            paper_trades = self.state.paper_stats.get('total_trades', 0)
            paper_profit = self.state.paper_stats.get('profit_pct', 0)
            
            if paper_trades < self.limits.required_paper_trades:
                return False, f"Need {self.limits.required_paper_trades} paper trades, have {paper_trades}"
                
            if paper_profit < self.limits.required_paper_profit_pct:
                return False, f"Need {self.limits.required_paper_profit_pct}% paper profit, have {paper_profit:.2f}%"
                
        return True, None
        
    def _check_daily_limits(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check daily trade limits"""
        if self.state.daily_trades >= self.limits.max_daily_trades:
            return False, f"Daily trade limit reached: {self.limits.max_daily_trades}"
        return True, None
        
    def _check_position_limits(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check position limits"""
        if len(self.state.open_positions) >= self.limits.max_open_positions:
            return False, f"Max open positions reached: {self.limits.max_open_positions}"
        return True, None
        
    def _check_symbol_allowed(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check if symbol is allowed"""
        symbol = trade_request.get('symbol')
        if symbol not in self.limits.allowed_symbols:
            return False, f"Symbol {symbol} not in allowed list"
        return True, None
        
    def _check_risk_limits(self, trade_request: Dict) -> Tuple[bool, Optional[str]]:
        """Check risk limits"""
        if self.state.daily_pnl_usd <= -self.limits.max_daily_loss_usd:
            return False, f"Daily loss limit reached: ${self.limits.max_daily_loss_usd}"
        return True, None
        
    def _check_daily_pnl(self, trade_result: Dict) -> Tuple[bool, Optional[str]]:
        """Check daily P&L after trade"""
        if self.state.daily_pnl_usd <= -self.limits.max_daily_loss_usd:
            return False, "Daily loss limit breached"
        return True, None
        
    def _check_consecutive_losses(self, trade_result: Dict) -> Tuple[bool, Optional[str]]:
        """Check for consecutive losses"""
        # Implement consecutive loss tracking
        return True, None
        
    def _check_error_rate(self, trade_result: Dict) -> Tuple[bool, Optional[str]]:
        """Check error rate"""
        # Implement error rate tracking
        return True, None
        
    def report_trade(self, trade_result: Dict):
        """Report trade result"""
        # Update statistics
        if self.state.mode == TradingMode.PAPER:
            self._update_paper_stats(trade_result)
        else:
            self._update_pilot_stats(trade_result)
            
        # Update daily counters
        self.state.daily_trades += 1
        pnl = Decimal(str(trade_result.get('pnl_usd', 0)))
        self.state.daily_pnl_usd += pnl
        
        # Run post-trade checks
        for check in self.post_trade_checks:
            passed, reason = check(trade_result)
            if not passed:
                self.state.violations.append(reason)
                self.logger.warning(f"Post-trade violation: {reason}")
                
        # Save state
        self._save_config()
        
    def _update_paper_stats(self, trade_result: Dict):
        """Update paper trading statistics"""
        if 'total_trades' not in self.state.paper_stats:
            self.state.paper_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl_usd': 0,
                'profit_pct': 0,
            }
            
        self.state.paper_stats['total_trades'] += 1
        
        pnl = trade_result.get('pnl_usd', 0)
        if pnl > 0:
            self.state.paper_stats['winning_trades'] += 1
            
        self.state.paper_stats['total_pnl_usd'] += pnl
        
        # Calculate profit percentage (simplified)
        if self.state.paper_stats['total_trades'] > 0:
            self.state.paper_stats['profit_pct'] = (
                self.state.paper_stats['total_pnl_usd'] / 10000 * 100  # Assume $10k starting capital
            )
            
    def _update_pilot_stats(self, trade_result: Dict):
        """Update pilot trading statistics"""
        if 'total_trades' not in self.state.pilot_stats:
            self.state.pilot_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl_usd': 0,
                'max_drawdown_usd': 0,
            }
            
        self.state.pilot_stats['total_trades'] += 1
        
        pnl = trade_result.get('pnl_usd', 0)
        if pnl > 0:
            self.state.pilot_stats['winning_trades'] += 1
            
        self.state.pilot_stats['total_pnl_usd'] += pnl
        
        # Track max drawdown
        if pnl < 0 and abs(pnl) > self.state.pilot_stats['max_drawdown_usd']:
            self.state.pilot_stats['max_drawdown_usd'] = abs(pnl)
            
    def promote_mode(self) -> bool:
        """Promote to next trading mode if conditions met"""
        current_mode = self.state.mode
        
        if current_mode == TradingMode.PAPER:
            # Check if ready for shadow mode
            if (self.state.paper_stats.get('total_trades', 0) >= self.limits.required_paper_trades and
                self.state.paper_stats.get('profit_pct', 0) >= self.limits.required_paper_profit_pct):
                self.state.mode = TradingMode.SHADOW
                self.logger.info("Promoted to SHADOW mode")
                
        elif current_mode == TradingMode.SHADOW:
            # Need manual approval for pilot
            self.logger.info("Ready for PILOT mode - awaiting manual approval")
            return False
            
        elif current_mode == TradingMode.PILOT:
            # Check pilot performance
            if (self.state.pilot_stats.get('total_trades', 0) >= 50 and
                self.state.pilot_stats.get('total_pnl_usd', 0) > 0):
                self.state.mode = TradingMode.SCALED
                self.limits.max_position_size_usd *= Decimal("2")  # Double position size
                self.logger.info("Promoted to SCALED mode")
                
        elif current_mode == TradingMode.SCALED:
            # Need manual approval for full trading
            self.logger.info("Ready for FULL mode - awaiting manual approval")
            return False
            
        if self.state.mode != current_mode:
            self.state.mode_started_at = datetime.now()
            self._save_config()
            return True
            
        return False
        
    async def _trigger_emergency_stop(self, reason: str):
        """Trigger emergency stop"""
        self.logger.critical(f"EMERGENCY STOP: {reason}")
        self.state.emergency_stop_triggered = True
        self.state.mode = TradingMode.PAPER  # Revert to paper trading
        
        # Close all positions
        for position in self.state.open_positions:
            self.logger.info(f"Emergency closing position: {position}")
            # Implement actual position closing
            
        self.state.open_positions = []
        self._save_config()
        
        # Send notifications
        await self._send_emergency_notification(reason)
        
    async def _send_emergency_notification(self, reason: str):
        """Send emergency notifications"""
        try:
            from src.integrations.notify import send_alert
            await send_alert(f"EMERGENCY STOP: {reason}", priority="critical")
        except Exception as e:
            self.logger.error(f"Failed to send emergency notification: {e}")
            
    def _reset_daily_counters(self):
        """Reset daily counters"""
        self.state.daily_trades = 0
        self.state.daily_pnl_usd = Decimal("0")
        self.logger.info("Daily counters reset")
        
    def get_status(self) -> Dict:
        """Get pilot status"""
        return {
            'mode': self.state.mode.value,
            'mode_duration': str(datetime.now() - self.state.mode_started_at),
            'limits': {
                'max_position_size_usd': float(self.limits.max_position_size_usd),
                'max_daily_trades': self.limits.max_daily_trades,
                'max_open_positions': self.limits.max_open_positions,
                'max_daily_loss_usd': float(self.limits.max_daily_loss_usd),
            },
            'daily': {
                'trades': self.state.daily_trades,
                'pnl_usd': float(self.state.daily_pnl_usd),
                'open_positions': len(self.state.open_positions),
            },
            'paper_stats': self.state.paper_stats,
            'pilot_stats': self.state.pilot_stats,
            'violations': self.state.violations[-10:],  # Last 10 violations
            'emergency_stop': self.state.emergency_stop_triggered,
        }


# Global instance
live_pilot = LiveTradingPilot()