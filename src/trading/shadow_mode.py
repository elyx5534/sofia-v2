"""
Shadow Mode Trading - Log without executing
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import aiofiles

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode states"""
    SHADOW = "shadow"      # Log only, no execution
    CANARY = "canary"      # Execute small % of orders
    LIVE = "live"          # Full execution


@dataclass
class ShadowOrder:
    """Shadow order for logging"""
    order_id: str
    symbol: str
    side: str
    type: str
    quantity: Decimal
    price: Optional[Decimal]
    mode: TradingMode
    executed: bool
    timestamp: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['mode'] = self.mode.value
        d['quantity'] = str(self.quantity)
        d['price'] = str(self.price) if self.price else None
        d['timestamp'] = self.timestamp.isoformat()
        return d


class ShadowModeController:
    """Controller for shadow mode trading"""
    
    def __init__(self, live_adapter=None, risk_engine=None):
        self.live_adapter = live_adapter
        self.risk_engine = risk_engine
        
        # Mode configuration
        self.mode = TradingMode[os.getenv('TRADING_MODE', 'shadow').upper()]
        self.canary_enabled = os.getenv('CANARY_ENABLED', 'false').lower() == 'true'
        self.canary_percentage = float(os.getenv('CANARY_PERCENTAGE', '10'))  # 10% default
        
        # Shadow tracking
        self.shadow_orders: List[ShadowOrder] = []
        self.shadow_pnl = Decimal('0')
        self.shadow_positions: Dict[str, Decimal] = {}
        
        # Canary tracking
        self.canary_orders: List[str] = []
        self.canary_success_rate = 1.0
        self.canary_errors: List[Dict] = []
        
        # Performance metrics
        self.order_count = 0
        self.executed_count = 0
        self.shadow_count = 0
        
        # Log file
        self.shadow_log_file = "shadow_orders.jsonl"
        
        logger.info(f"Shadow Mode Controller initialized: mode={self.mode.value}, canary={self.canary_enabled}")
    
    def set_mode(self, mode: str) -> bool:
        """Change trading mode"""
        try:
            new_mode = TradingMode[mode.upper()]
            old_mode = self.mode
            self.mode = new_mode
            
            logger.warning(json.dumps({
                'event': 'trading_mode_changed',
                'old_mode': old_mode.value,
                'new_mode': new_mode.value,
                'timestamp': datetime.now().isoformat()
            }))
            
            return True
        except KeyError:
            logger.error(f"Invalid trading mode: {mode}")
            return False
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        strategy: str = "manual",
        correlation_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        Create order based on current mode
        
        Returns:
            (executed, result)
        """
        self.order_count += 1
        
        # Check mode
        should_execute = self._should_execute_order()
        
        # Create shadow order for logging
        shadow_order = ShadowOrder(
            order_id=f"SHADOW-{self.order_count}-{datetime.now().timestamp()}",
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            mode=self.mode,
            executed=should_execute,
            timestamp=datetime.now(),
            metadata={
                'strategy': strategy,
                'correlation_id': correlation_id,
                'canary': self.mode == TradingMode.CANARY and should_execute
            }
        )
        
        # Log shadow order
        await self._log_shadow_order(shadow_order)
        self.shadow_orders.append(shadow_order)
        
        # Execute if needed
        result = None
        if should_execute and self.live_adapter:
            try:
                # Perform risk check first
                if self.risk_engine:
                    risk_check = await self.risk_engine.pre_trade_check(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price
                    )
                    
                    if risk_check.action.value == "BLOCK":
                        logger.warning(f"Order blocked by risk engine: {risk_check.reason}")
                        return False, None
                
                # Execute real order
                result = await self.live_adapter.create_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    strategy=strategy,
                    correlation_id=correlation_id
                )
                
                self.executed_count += 1
                
                # Track canary order
                if self.mode == TradingMode.CANARY:
                    self.canary_orders.append(result.order_id)
                
                logger.info(json.dumps({
                    'event': 'order_executed',
                    'mode': self.mode.value,
                    'order_id': result.order_id if result else shadow_order.order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': str(quantity),
                    'executed': True
                }))
                
            except Exception as e:
                logger.error(f"Order execution failed: {e}")
                
                # Track canary error
                if self.mode == TradingMode.CANARY:
                    self.canary_errors.append({
                        'timestamp': datetime.now().isoformat(),
                        'error': str(e),
                        'order': shadow_order.to_dict()
                    })
                    self._update_canary_success_rate()
                
                return False, None
        else:
            self.shadow_count += 1
            
            # Update shadow position tracking
            self._update_shadow_position(symbol, side, quantity, price)
            
            logger.info(json.dumps({
                'event': 'shadow_order_logged',
                'mode': self.mode.value,
                'order_id': shadow_order.order_id,
                'symbol': symbol,
                'side': side,
                'quantity': str(quantity),
                'executed': False
            }))
        
        return should_execute, result
    
    def _should_execute_order(self) -> bool:
        """Determine if order should be executed based on mode"""
        if self.mode == TradingMode.LIVE:
            return True
        elif self.mode == TradingMode.CANARY and self.canary_enabled:
            # Execute canary_percentage of orders
            import random
            return random.random() * 100 < self.canary_percentage
        else:  # SHADOW mode
            return False
    
    def _update_shadow_position(self, symbol: str, side: str, quantity: Decimal, price: Optional[Decimal]):
        """Update shadow position tracking"""
        current = self.shadow_positions.get(symbol, Decimal('0'))
        
        if side == 'buy':
            self.shadow_positions[symbol] = current + quantity
        else:  # sell
            self.shadow_positions[symbol] = current - quantity
        
        # Clean up zero positions
        if self.shadow_positions[symbol] == 0:
            del self.shadow_positions[symbol]
    
    def _update_canary_success_rate(self):
        """Update canary success rate"""
        if self.canary_orders:
            failures = len(self.canary_errors)
            total = len(self.canary_orders)
            self.canary_success_rate = (total - failures) / total
    
    async def _log_shadow_order(self, order: ShadowOrder):
        """Log shadow order to file"""
        try:
            async with aiofiles.open(self.shadow_log_file, 'a') as f:
                await f.write(json.dumps(order.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to log shadow order: {e}")
    
    def should_promote_to_live(self) -> Tuple[bool, str]:
        """
        Check if canary should be promoted to live
        
        Returns:
            (should_promote, reason)
        """
        if self.mode != TradingMode.CANARY:
            return False, "Not in canary mode"
        
        if not self.canary_orders:
            return False, "No canary orders executed"
        
        if len(self.canary_orders) < 10:
            return False, f"Insufficient canary orders: {len(self.canary_orders)}/10"
        
        if self.canary_success_rate < 0.95:
            return False, f"Success rate too low: {self.canary_success_rate:.1%}"
        
        # Check if risk metrics are acceptable
        if self.risk_engine:
            status = self.risk_engine.get_status()
            if status['daily_pnl'] and Decimal(status['daily_pnl']) < 0:
                return False, f"Negative P&L in canary: {status['daily_pnl']}"
        
        return True, f"Canary successful: {self.canary_success_rate:.1%} success rate"
    
    async def promote_to_live(self) -> bool:
        """Promote from canary to live mode"""
        can_promote, reason = self.should_promote_to_live()
        
        if not can_promote:
            logger.warning(f"Cannot promote to live: {reason}")
            return False
        
        self.set_mode("live")
        
        logger.warning(json.dumps({
            'event': 'promoted_to_live',
            'canary_orders': len(self.canary_orders),
            'success_rate': self.canary_success_rate,
            'timestamp': datetime.now().isoformat()
        }))
        
        return True
    
    async def rollback_to_shadow(self, reason: str = "Manual rollback"):
        """Rollback to shadow mode"""
        old_mode = self.mode
        self.set_mode("shadow")
        
        # Cancel all open orders if rolling back from live
        if old_mode == TradingMode.LIVE and self.live_adapter:
            try:
                open_orders = await self.live_adapter.get_open_orders()
                for order in open_orders:
                    await self.live_adapter.cancel_order(order.order_id, order.symbol)
                    logger.warning(f"Cancelled order {order.order_id} during rollback")
            except Exception as e:
                logger.error(f"Failed to cancel orders during rollback: {e}")
        
        logger.critical(json.dumps({
            'event': 'rollback_to_shadow',
            'from_mode': old_mode.value,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }))
    
    def get_status(self) -> Dict[str, Any]:
        """Get shadow mode status"""
        return {
            'mode': self.mode.value,
            'canary_enabled': self.canary_enabled,
            'canary_percentage': self.canary_percentage,
            'order_count': self.order_count,
            'executed_count': self.executed_count,
            'shadow_count': self.shadow_count,
            'shadow_positions': {k: str(v) for k, v in self.shadow_positions.items()},
            'shadow_pnl': str(self.shadow_pnl),
            'canary_orders': len(self.canary_orders),
            'canary_success_rate': self.canary_success_rate,
            'canary_errors': len(self.canary_errors),
            'can_promote': self.should_promote_to_live()[0],
            'promotion_reason': self.should_promote_to_live()[1]
        }
    
    def get_shadow_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent shadow orders"""
        return [order.to_dict() for order in self.shadow_orders[-limit:]]
    
    def get_canary_metrics(self) -> Dict[str, Any]:
        """Get detailed canary metrics"""
        if not self.canary_orders:
            return {
                'status': 'No canary orders',
                'orders': [],
                'errors': []
            }
        
        return {
            'total_orders': len(self.canary_orders),
            'success_rate': self.canary_success_rate,
            'errors': self.canary_errors[-10:],  # Last 10 errors
            'order_ids': self.canary_orders[-20:],  # Last 20 order IDs
            'duration': (datetime.now() - self.shadow_orders[0].timestamp).total_seconds() if self.shadow_orders else 0,
            'ready_for_promotion': self.should_promote_to_live()[0]
        }