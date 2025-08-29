"""
Canary Deployment Script - Gradual rollout to production
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.live_adapter import LiveAdapter
from src.trading.shadow_mode import ShadowModeController, TradingMode
from src.risk.engine import RiskEngine
from src.risk.kill_switch import KillSwitch
from src.reconciliation.eod_reports import ReconciliationEngine
from src.observability.monitoring import observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CanaryDeployment:
    """Canary deployment controller"""
    
    def __init__(self):
        self.live_adapter = None
        self.shadow_controller = None
        self.risk_engine = None
        self.kill_switch = None
        self.reconciliation = None
        
        # Canary configuration
        self.canary_duration_minutes = int(os.getenv('CANARY_DURATION_MINUTES', '60'))
        self.canary_percentage_steps = [10, 25, 50, 75, 100]  # Gradual increase
        self.success_threshold = 0.95  # 95% success rate required
        self.max_loss_threshold = Decimal('50')  # Max loss in canary
        
        # Monitoring
        self.start_time = None
        self.metrics = {
            'orders_created': 0,
            'orders_successful': 0,
            'orders_failed': 0,
            'total_volume': Decimal('0'),
            'pnl': Decimal('0'),
            'errors': []
        }
    
    async def initialize_components(self):
        """Initialize all trading components"""
        logger.info("Initializing components...")
        
        try:
            # Initialize components
            self.live_adapter = LiveAdapter()
            await self.live_adapter.initialize()
            
            self.risk_engine = RiskEngine()
            self.kill_switch = KillSwitch(self.risk_engine)
            
            self.shadow_controller = ShadowModeController(
                live_adapter=self.live_adapter,
                risk_engine=self.risk_engine
            )
            
            self.reconciliation = ReconciliationEngine(
                live_adapter=self.live_adapter,
                risk_engine=self.risk_engine,
                shadow_controller=self.shadow_controller
            )
            
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            return False
    
    async def start_shadow_mode(self) -> bool:
        """Start in shadow mode for baseline"""
        logger.info("Starting shadow mode for baseline...")
        
        self.shadow_controller.set_mode("shadow")
        self.start_time = datetime.now()
        
        # Run in shadow for 10 minutes
        shadow_duration = min(10, self.canary_duration_minutes // 6)
        end_time = self.start_time + timedelta(minutes=shadow_duration)
        
        while datetime.now() < end_time:
            # Simulate some orders
            await self._simulate_order()
            await asyncio.sleep(30)  # Check every 30 seconds
        
        shadow_metrics = self.shadow_controller.get_status()
        logger.info(f"Shadow mode complete: {shadow_metrics['shadow_count']} orders simulated")
        
        return shadow_metrics['shadow_count'] > 0
    
    async def start_canary_rollout(self) -> bool:
        """Start canary rollout with gradual percentage increase"""
        logger.info("Starting canary rollout...")
        
        for percentage in self.canary_percentage_steps:
            logger.info(f"Canary phase: {percentage}% of traffic")
            
            # Update canary percentage
            os.environ['CANARY_PERCENTAGE'] = str(percentage)
            self.shadow_controller.canary_percentage = percentage
            self.shadow_controller.set_mode("canary")
            
            # Run for phase duration
            phase_duration = self.canary_duration_minutes / len(self.canary_percentage_steps)
            phase_end = datetime.now() + timedelta(minutes=phase_duration)
            
            phase_success = await self._run_canary_phase(phase_end)
            
            if not phase_success:
                logger.error(f"Canary phase {percentage}% failed!")
                await self._rollback("Canary phase failed")
                return False
            
            logger.info(f"Canary phase {percentage}% successful")
        
        return True
    
    async def _run_canary_phase(self, end_time: datetime) -> bool:
        """Run a single canary phase"""
        phase_start = datetime.now()
        
        while datetime.now() < end_time:
            # Check health metrics
            health_check = await self._check_canary_health()
            
            if not health_check['healthy']:
                logger.error(f"Canary unhealthy: {health_check['reason']}")
                return False
            
            # Simulate order
            await self._simulate_order()
            
            # Sleep before next check
            await asyncio.sleep(10)
        
        # Evaluate phase
        phase_metrics = self._calculate_phase_metrics(phase_start)
        
        if phase_metrics['success_rate'] < self.success_threshold:
            logger.error(f"Success rate {phase_metrics['success_rate']:.1%} below threshold")
            return False
        
        return True
    
    async def _check_canary_health(self) -> Dict[str, Any]:
        """Check canary health metrics"""
        # Check kill switch
        if self.kill_switch.get_state() == "ON":
            return {
                'healthy': False,
                'reason': 'Kill switch activated'
            }
        
        # Check error rate
        if self.metrics['orders_created'] > 0:
            error_rate = self.metrics['orders_failed'] / self.metrics['orders_created']
            if error_rate > 0.1:  # 10% error rate
                return {
                    'healthy': False,
                    'reason': f'Error rate {error_rate:.1%} too high'
                }
        
        # Check P&L
        if self.metrics['pnl'] < -self.max_loss_threshold:
            return {
                'healthy': False,
                'reason': f'Loss ${abs(self.metrics["pnl"])} exceeds threshold'
            }
        
        # Check latency
        if self.risk_engine.latency_samples:
            avg_latency = sum(self.risk_engine.latency_samples) / len(self.risk_engine.latency_samples)
            if avg_latency > 5000000:  # 5 seconds
                return {
                    'healthy': False,
                    'reason': f'Latency {avg_latency/1000:.0f}ms too high'
                }
        
        return {
            'healthy': True,
            'reason': 'All checks passed'
        }
    
    async def _simulate_order(self):
        """Simulate a trading order"""
        try:
            # Create a small test order
            executed, result = await self.shadow_controller.create_order(
                symbol="BTC/USDT",
                side="buy" if self.metrics['orders_created'] % 2 == 0 else "sell",
                order_type="limit",
                quantity=Decimal("0.001"),
                price=Decimal("50000"),
                strategy="canary_test"
            )
            
            self.metrics['orders_created'] += 1
            
            if executed and result:
                self.metrics['orders_successful'] += 1
                self.metrics['total_volume'] += Decimal("0.001") * Decimal("50000")
            elif not executed:
                # Shadow order, still count as success
                self.metrics['orders_successful'] += 1
            
        except Exception as e:
            self.metrics['orders_failed'] += 1
            self.metrics['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })
            logger.error(f"Order simulation failed: {e}")
    
    def _calculate_phase_metrics(self, phase_start: datetime) -> Dict[str, Any]:
        """Calculate metrics for current phase"""
        duration = (datetime.now() - phase_start).total_seconds()
        
        success_rate = 0
        if self.metrics['orders_created'] > 0:
            success_rate = self.metrics['orders_successful'] / self.metrics['orders_created']
        
        return {
            'duration_seconds': duration,
            'orders_created': self.metrics['orders_created'],
            'success_rate': success_rate,
            'total_volume': self.metrics['total_volume'],
            'pnl': self.metrics['pnl'],
            'errors': len(self.metrics['errors'])
        }
    
    async def promote_to_production(self) -> bool:
        """Promote to full production"""
        logger.info("Promoting to production...")
        
        # Final health check
        health = await self._check_canary_health()
        if not health['healthy']:
            logger.error(f"Final health check failed: {health['reason']}")
            return False
        
        # Check with shadow controller
        can_promote, reason = self.shadow_controller.should_promote_to_live()
        if not can_promote:
            logger.error(f"Cannot promote: {reason}")
            return False
        
        # Promote to live
        success = await self.shadow_controller.promote_to_live()
        
        if success:
            logger.info("Successfully promoted to production!")
            
            # Generate promotion report
            await self._generate_promotion_report()
            
            return True
        else:
            logger.error("Promotion failed!")
            return False
    
    async def _rollback(self, reason: str):
        """Rollback to shadow mode"""
        logger.warning(f"Initiating rollback: {reason}")
        
        # Rollback to shadow
        await self.shadow_controller.rollback_to_shadow(reason)
        
        # Activate kill switch
        await self.kill_switch.activate(
            trigger=self.kill_switch.TriggerType.EXTERNAL,
            reason=f"Canary rollback: {reason}",
            metadata=self.metrics
        )
        
        # Generate rollback report
        await self._generate_rollback_report(reason)
    
    async def _generate_promotion_report(self):
        """Generate promotion report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'type': 'promotion',
            'duration_minutes': (datetime.now() - self.start_time).total_seconds() / 60,
            'metrics': self.metrics,
            'final_mode': self.shadow_controller.mode.value,
            'canary_metrics': self.shadow_controller.get_canary_metrics()
        }
        
        with open('canary_promotion_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info("Promotion report generated: canary_promotion_report.json")
    
    async def _generate_rollback_report(self, reason: str):
        """Generate rollback report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'type': 'rollback',
            'reason': reason,
            'duration_minutes': (datetime.now() - self.start_time).total_seconds() / 60 if self.start_time else 0,
            'metrics': self.metrics,
            'errors': self.metrics['errors'][-10:]  # Last 10 errors
        }
        
        with open('canary_rollback_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info("Rollback report generated: canary_rollback_report.json")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.live_adapter:
            await self.live_adapter.close()


async def main():
    """Main canary deployment"""
    print("\n" + "="*60)
    print("CANARY DEPLOYMENT")
    print("="*60 + "\n")
    
    deployment = CanaryDeployment()
    
    try:
        # Initialize
        if not await deployment.initialize_components():
            logger.error("Initialization failed!")
            return 1
        
        # Run shadow baseline
        if not await deployment.start_shadow_mode():
            logger.error("Shadow mode failed!")
            return 1
        
        # Run canary rollout
        if not await deployment.start_canary_rollout():
            logger.error("Canary rollout failed!")
            return 1
        
        # Promote to production
        if not await deployment.promote_to_production():
            logger.error("Production promotion failed!")
            return 1
        
        print("\n[SUCCESS] Canary deployment completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Canary deployment failed: {e}")
        await deployment._rollback(f"Exception: {e}")
        return 1
        
    finally:
        await deployment.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)