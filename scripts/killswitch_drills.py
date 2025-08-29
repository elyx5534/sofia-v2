"""
Kill Switch Drill Scripts - Emergency Response Testing
"""

import os
import sys
import time
import json
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.live_adapter import LiveAdapter
from src.risk.engine import RiskEngine
from src.risk.kill_switch import KillSwitch, TriggerType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KillSwitchDrills:
    """Kill switch drill scenarios"""
    
    def __init__(self):
        self.drill_results = []
        self.timing_results = []
        
    async def drill_manual_activation(self) -> Dict[str, Any]:
        """Drill: Manual kill switch activation and deactivation"""
        logger.info("Starting Manual Kill Switch Drill...")
        
        result = {
            'drill': 'manual_activation',
            'start': datetime.now().isoformat(),
            'activation_time': None,
            'deactivation_time': None,
            'state_changes': []
        }
        
        risk_engine = RiskEngine()
        kill_switch = KillSwitch(risk_engine)
        
        try:
            # Initial state
            initial_state = kill_switch.get_state()
            result['state_changes'].append({
                'state': initial_state,
                'timestamp': datetime.now().isoformat()
            })
            
            # Activate kill switch
            start = time.time()
            activated = await kill_switch.activate(
                trigger=TriggerType.MANUAL,
                reason="Drill: Manual activation test"
            )
            result['activation_time'] = time.time() - start
            
            if activated:
                result['state_changes'].append({
                    'state': 'ON',
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"Kill switch activated in {result['activation_time']:.3f}s")
            
            # Wait 2 seconds
            await asyncio.sleep(2)
            
            # Deactivate kill switch
            start = time.time()
            deactivated = await kill_switch.deactivate(
                reason="Drill: Manual deactivation test"
            )
            result['deactivation_time'] = time.time() - start
            
            if deactivated:
                result['state_changes'].append({
                    'state': 'OFF',
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"Kill switch deactivated in {result['deactivation_time']:.3f}s")
            
            result['passed'] = activated and deactivated
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def drill_pnl_trigger(self) -> Dict[str, Any]:
        """Drill: P&L loss trigger"""
        logger.info("Starting P&L Trigger Drill...")
        
        result = {
            'drill': 'pnl_trigger',
            'start': datetime.now().isoformat(),
            'trigger_time': None,
            'pnl_breaches': []
        }
        
        risk_engine = RiskEngine()
        kill_switch = KillSwitch(risk_engine)
        
        # Set auto mode
        await kill_switch.set_auto_mode(True)
        
        try:
            # Simulate increasing losses
            losses = [50, 100, 150, 180, 200, 220]  # Cross threshold at 200
            
            for loss in losses:
                risk_engine.update_daily_pnl(Decimal(f"-{loss}"))
                
                triggered = await kill_switch.check_daily_loss(
                    daily_pnl=-loss,
                    max_loss=200
                )
                
                result['pnl_breaches'].append({
                    'loss': loss,
                    'triggered': triggered,
                    'timestamp': datetime.now().isoformat()
                })
                
                if triggered:
                    result['trigger_time'] = datetime.now().isoformat()
                    logger.info(f"Kill switch triggered at loss: ${loss}")
                    break
                
                await asyncio.sleep(0.5)
            
            result['passed'] = result['trigger_time'] is not None
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def drill_latency_trigger(self) -> Dict[str, Any]:
        """Drill: Latency threshold trigger"""
        logger.info("Starting Latency Trigger Drill...")
        
        result = {
            'drill': 'latency_trigger',
            'start': datetime.now().isoformat(),
            'trigger_time': None,
            'latency_samples': []
        }
        
        risk_engine = RiskEngine()
        kill_switch = KillSwitch(risk_engine)
        
        # Set auto mode
        await kill_switch.set_auto_mode(True)
        
        try:
            # Simulate increasing latency
            latencies_ms = [100, 500, 1000, 3000, 5000, 7000]  # Threshold at 5000ms
            
            for latency_ms in latencies_ms:
                triggered = await kill_switch.check_latency(
                    latency_ms=latency_ms,
                    threshold_ms=5000
                )
                
                result['latency_samples'].append({
                    'latency_ms': latency_ms,
                    'triggered': triggered,
                    'timestamp': datetime.now().isoformat()
                })
                
                if triggered:
                    result['trigger_time'] = datetime.now().isoformat()
                    logger.info(f"Kill switch triggered at latency: {latency_ms}ms")
                    break
                
                await asyncio.sleep(0.5)
            
            result['passed'] = result['trigger_time'] is not None
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def drill_heartbeat_loss(self) -> Dict[str, Any]:
        """Drill: WebSocket heartbeat loss trigger"""
        logger.info("Starting Heartbeat Loss Drill...")
        
        result = {
            'drill': 'heartbeat_loss',
            'start': datetime.now().isoformat(),
            'trigger_time': None,
            'downtime_samples': []
        }
        
        risk_engine = RiskEngine()
        kill_switch = KillSwitch(risk_engine)
        
        # Set auto mode
        await kill_switch.set_auto_mode(True)
        
        try:
            # Simulate increasing downtime
            downtimes = [5, 10, 20, 30, 40]  # Threshold at 30s
            
            for downtime_seconds in downtimes:
                triggered = await kill_switch.check_ws_downtime(
                    downtime_seconds=downtime_seconds,
                    threshold_seconds=30
                )
                
                result['downtime_samples'].append({
                    'downtime_seconds': downtime_seconds,
                    'triggered': triggered,
                    'timestamp': datetime.now().isoformat()
                })
                
                if triggered:
                    result['trigger_time'] = datetime.now().isoformat()
                    logger.info(f"Kill switch triggered at downtime: {downtime_seconds}s")
                    break
                
                await asyncio.sleep(0.5)
            
            result['passed'] = result['trigger_time'] is not None
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def drill_cancel_all_orders(self) -> Dict[str, Any]:
        """Drill: Cancel all orders within 2 seconds"""
        logger.info("Starting Cancel All Orders Drill...")
        
        result = {
            'drill': 'cancel_all_orders',
            'start': datetime.now().isoformat(),
            'orders_created': 0,
            'orders_canceled': 0,
            'cancel_time': None,
            'target_met': False
        }
        
        adapter = LiveAdapter()
        
        try:
            await adapter.initialize()
            
            # Create multiple test orders
            test_orders = []
            for i in range(5):
                try:
                    order = await adapter.create_order(
                        symbol="BTC/USDT",
                        side="buy" if i % 2 == 0 else "sell",
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal("45000" if i % 2 == 0 else "55000")  # Far from market
                    )
                    test_orders.append(order)
                    result['orders_created'] += 1
                except Exception as e:
                    logger.warning(f"Failed to create test order: {e}")
            
            if test_orders:
                # Start cancel timer
                start = time.time()
                
                # Cancel all orders
                for order in test_orders:
                    try:
                        success = await adapter.cancel_order(
                            order.order_id,
                            order.symbol
                        )
                        if success:
                            result['orders_canceled'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to cancel order: {e}")
                
                result['cancel_time'] = time.time() - start
                result['target_met'] = result['cancel_time'] < 2.0  # 2 second target
                
                logger.info(f"Canceled {result['orders_canceled']}/{result['orders_created']} orders in {result['cancel_time']:.3f}s")
            
            await adapter.close()
            
            result['passed'] = result['target_met']
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def drill_state_persistence(self) -> Dict[str, Any]:
        """Drill: Kill switch state persistence across restart"""
        logger.info("Starting State Persistence Drill...")
        
        result = {
            'drill': 'state_persistence',
            'start': datetime.now().isoformat(),
            'initial_state': None,
            'persisted_state': None,
            'recovered_state': None
        }
        
        try:
            # Create first instance
            risk_engine1 = RiskEngine()
            kill_switch1 = KillSwitch(risk_engine1)
            
            # Set initial state
            result['initial_state'] = kill_switch1.get_state()
            
            # Activate kill switch
            await kill_switch1.activate(
                trigger=TriggerType.MANUAL,
                reason="Persistence test"
            )
            result['persisted_state'] = kill_switch1.get_state()
            
            # Simulate restart - create new instance
            await asyncio.sleep(1)
            
            risk_engine2 = RiskEngine()
            kill_switch2 = KillSwitch(risk_engine2)
            
            # Check recovered state
            result['recovered_state'] = kill_switch2.get_state()
            
            # Verify persistence
            result['passed'] = result['persisted_state'] == result['recovered_state']
            
            # Clean up - deactivate
            await kill_switch2.deactivate("Cleanup after test")
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        result['end'] = datetime.now().isoformat()
        self.drill_results.append(result)
        
        return result
    
    async def run_all_drills(self) -> Dict[str, Any]:
        """Run all kill switch drills"""
        logger.info("Starting Kill Switch Drill Suite...")
        
        drills = [
            self.drill_manual_activation,
            self.drill_pnl_trigger,
            self.drill_latency_trigger,
            self.drill_heartbeat_loss,
            self.drill_cancel_all_orders,
            self.drill_state_persistence
        ]
        
        for drill_func in drills:
            try:
                await drill_func()
            except Exception as e:
                logger.error(f"Drill {drill_func.__name__} crashed: {e}")
                self.drill_results.append({
                    'drill': drill_func.__name__,
                    'passed': False,
                    'error': str(e)
                })
            
            # Cool down between drills
            await asyncio.sleep(2)
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        with open('killswitch_drill_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate drill report"""
        passed = sum(1 for r in self.drill_results if r.get('passed', False))
        total = len(self.drill_results)
        
        # Calculate timing metrics
        cancel_times = [r['cancel_time'] for r in self.drill_results 
                       if 'cancel_time' in r and r['cancel_time'] is not None]
        
        timing_summary = {
            'avg_cancel_time': sum(cancel_times) / len(cancel_times) if cancel_times else None,
            'max_cancel_time': max(cancel_times) if cancel_times else None,
            'cancel_target_met': all(t < 2.0 for t in cancel_times) if cancel_times else False
        }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_drills': total,
                'passed': passed,
                'failed': total - passed,
                'success_rate': passed / max(1, total)
            },
            'timing_summary': timing_summary,
            'drill_results': self.drill_results,
            'verdict': 'PASS' if passed == total else 'FAIL'
        }


async def main():
    """Main drill execution"""
    print("\n" + "="*60)
    print("KILL SWITCH DRILL SUITE")
    print("="*60 + "\n")
    
    drills = KillSwitchDrills()
    report = await drills.run_all_drills()
    
    # Print summary
    print("\n" + "="*60)
    print("DRILL SUMMARY")
    print("="*60)
    print(f"Total Drills: {report['summary']['total_drills']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1%}")
    
    if report['timing_summary']['avg_cancel_time']:
        print(f"\nCancel Timing:")
        print(f"  Average: {report['timing_summary']['avg_cancel_time']:.3f}s")
        print(f"  Maximum: {report['timing_summary']['max_cancel_time']:.3f}s")
        print(f"  Target Met (<2s): {report['timing_summary']['cancel_target_met']}")
    
    print(f"\nVerdict: {report['verdict']}")
    
    # Print individual results
    print("\nIndividual Results:")
    for result in report['drill_results']:
        status = "PASS" if result.get('passed', False) else "FAIL"
        print(f"  - {result['drill']}: {status}")
    
    print(f"\nReport saved to: killswitch_drill_report.json")
    
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)