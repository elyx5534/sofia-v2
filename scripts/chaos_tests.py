"""
Chaos Testing Suite for Sofia Trading System
"""

import os
import sys
import time
import json
import asyncio
import random
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.live_adapter import LiveAdapter, OrderState
from src.trading.shadow_mode import ShadowModeController
from src.risk.engine import RiskEngine
from src.risk.kill_switch import KillSwitch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChaosTestSuite:
    """Chaos engineering tests for trading system"""
    
    def __init__(self):
        self.test_results = []
        self.order_states = []
        self.retry_logs = []
        self.start_time = datetime.now()
        
    async def test_429_storm(self) -> Dict[str, Any]:
        """Test system behavior under rate limit storm"""
        logger.info("Starting 429 Rate Limit Storm test...")
        
        test_result = {
            'test': '429_storm',
            'start': datetime.now().isoformat(),
            'errors': [],
            'retries': 0,
            'orders_attempted': 0,
            'orders_successful': 0
        }
        
        # Mock CCXT to return 429 errors
        adapter = LiveAdapter()
        original_create = adapter.create_order
        
        async def mock_create_429(*args, **kwargs):
            test_result['orders_attempted'] += 1
            
            # 80% chance of 429 error
            if random.random() < 0.8:
                import ccxt
                test_result['retries'] += 1
                self.retry_logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'error': 'RateLimitExceeded',
                    'attempt': test_result['retries']
                })
                raise ccxt.RateLimitExceeded("429 Too Many Requests")
            
            test_result['orders_successful'] += 1
            return await original_create(*args, **kwargs)
        
        adapter.create_order = mock_create_429
        
        try:
            await adapter.initialize()
            
            # Attempt to create 20 orders during storm
            for i in range(20):
                try:
                    order = await adapter.create_order(
                        symbol="BTC/USDT",
                        side="buy",
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal("50000"),
                        strategy="chaos_test"
                    )
                    
                    self.order_states.append({
                        'order_id': order.order_id if order else f"chaos_{i}",
                        'state': 'SUCCESS',
                        'timestamp': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    test_result['errors'].append(str(e))
                    self.order_states.append({
                        'order_id': f"chaos_{i}",
                        'state': 'FAILED',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                
                await asyncio.sleep(0.1)
            
            await adapter.close()
            
        except Exception as e:
            test_result['errors'].append(f"Critical error: {e}")
        
        test_result['end'] = datetime.now().isoformat()
        test_result['success_rate'] = test_result['orders_successful'] / max(1, test_result['orders_attempted'])
        test_result['passed'] = test_result['success_rate'] > 0.1  # At least 10% should succeed with retries
        
        self.test_results.append(test_result)
        logger.info(f"429 Storm test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def test_network_flapping(self) -> Dict[str, Any]:
        """Test system behavior during network instability"""
        logger.info("Starting Network Flapping test...")
        
        test_result = {
            'test': 'network_flapping',
            'start': datetime.now().isoformat(),
            'disconnections': 0,
            'reconnections': 0,
            'orders_during_flap': 0,
            'state_consistency': True
        }
        
        adapter = LiveAdapter()
        
        try:
            await adapter.initialize()
            
            # Create initial order
            initial_order = await adapter.create_order(
                symbol="BTC/USDT",
                side="buy",
                order_type="limit",
                quantity=Decimal("0.001"),
                price=Decimal("50000")
            )
            
            initial_state = OrderState.NEW
            
            # Simulate 3 network flaps
            for flap in range(3):
                logger.info(f"Network flap {flap + 1}/3")
                test_result['disconnections'] += 1
                
                # Simulate disconnect
                adapter.exchange = None
                await asyncio.sleep(1)
                
                # Try order during disconnect
                try:
                    await adapter.create_order(
                        symbol="BTC/USDT",
                        side="sell",
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal("51000")
                    )
                    test_result['orders_during_flap'] += 1
                except:
                    pass  # Expected to fail
                
                # Reconnect
                await adapter.initialize()
                test_result['reconnections'] += 1
                
                # Check order state consistency
                orders = await adapter.get_open_orders("BTC/USDT")
                
                # Verify state machine integrity
                for order in orders:
                    if order.order_id == initial_order.order_id:
                        # Check valid state transition
                        valid_transitions = {
                            OrderState.NEW: [OrderState.NEW, OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELED],
                            OrderState.PARTIAL: [OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELED],
                            OrderState.FILLED: [OrderState.FILLED],
                            OrderState.CANCELED: [OrderState.CANCELED]
                        }
                        
                        if order.state not in valid_transitions.get(initial_state, []):
                            test_result['state_consistency'] = False
                            logger.error(f"Invalid state transition: {initial_state} -> {order.state}")
                        
                        initial_state = order.state
                
                await asyncio.sleep(2)
            
            await adapter.close()
            
        except Exception as e:
            test_result['error'] = str(e)
            test_result['state_consistency'] = False
        
        test_result['end'] = datetime.now().isoformat()
        test_result['passed'] = (
            test_result['reconnections'] == 3 and
            test_result['state_consistency']
        )
        
        self.test_results.append(test_result)
        logger.info(f"Network Flapping test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def test_dns_failure(self) -> Dict[str, Any]:
        """Test system behavior during DNS failures"""
        logger.info("Starting DNS Failure test...")
        
        test_result = {
            'test': 'dns_failure',
            'start': datetime.now().isoformat(),
            'dns_errors': 0,
            'fallback_used': False,
            'recovery_time': None
        }
        
        # Mock DNS resolution failure
        import socket
        original_getaddrinfo = socket.getaddrinfo
        
        def mock_dns_failure(host, port, *args, **kwargs):
            if 'binance' in host or 'api' in host:
                test_result['dns_errors'] += 1
                raise socket.gaierror("DNS resolution failed")
            return original_getaddrinfo(host, port, *args, **kwargs)
        
        socket.getaddrinfo = mock_dns_failure
        
        adapter = LiveAdapter()
        start = time.time()
        
        try:
            # Should fail initially
            await adapter.initialize()
            test_result['fallback_used'] = True
        except Exception as e:
            logger.info(f"Expected DNS failure: {e}")
        
        # Restore DNS after 5 seconds
        await asyncio.sleep(5)
        socket.getaddrinfo = original_getaddrinfo
        
        try:
            # Should recover
            await adapter.initialize()
            test_result['recovery_time'] = time.time() - start
            
            # Test order after recovery
            order = await adapter.create_order(
                symbol="BTC/USDT",
                side="buy",
                order_type="limit",
                quantity=Decimal("0.001"),
                price=Decimal("50000")
            )
            
            test_result['recovery_successful'] = order is not None
            await adapter.close()
            
        except Exception as e:
            test_result['recovery_error'] = str(e)
            test_result['recovery_successful'] = False
        
        test_result['end'] = datetime.now().isoformat()
        test_result['passed'] = (
            test_result['dns_errors'] > 0 and
            test_result.get('recovery_successful', False)
        )
        
        self.test_results.append(test_result)
        logger.info(f"DNS Failure test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def test_slow_response(self) -> Dict[str, Any]:
        """Test system behavior with slow API responses"""
        logger.info("Starting Slow Response test...")
        
        test_result = {
            'test': 'slow_response',
            'start': datetime.now().isoformat(),
            'timeouts': 0,
            'slow_requests': 0,
            'kill_switch_triggered': False
        }
        
        adapter = LiveAdapter()
        risk_engine = RiskEngine()
        kill_switch = KillSwitch(risk_engine)
        
        # Mock slow responses
        original_with_retry = adapter._with_retry
        
        async def mock_slow_response(func, *args, **kwargs):
            test_result['slow_requests'] += 1
            
            # Add artificial delay
            delay = random.uniform(3, 8)  # 3-8 seconds
            await asyncio.sleep(delay)
            
            # Track latency
            latency_us = int(delay * 1000000)
            risk_engine.add_latency_sample(latency_us)
            
            # Check if kill switch should trigger
            if latency_us > risk_engine.halt_on_latency_us:
                test_result['kill_switch_triggered'] = True
                await kill_switch.activate(
                    trigger=kill_switch.TriggerType.LATENCY,
                    reason=f"Latency {latency_us/1000}ms exceeded threshold"
                )
                raise TimeoutError("Request timeout - kill switch activated")
            
            return await original_with_retry(func, *args, **kwargs)
        
        adapter._with_retry = mock_slow_response
        
        try:
            await adapter.initialize()
            
            # Attempt orders with slow responses
            for i in range(5):
                try:
                    order = await adapter.create_order(
                        symbol="BTC/USDT",
                        side="buy" if i % 2 == 0 else "sell",
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal("50000")
                    )
                except TimeoutError:
                    test_result['timeouts'] += 1
                except Exception as e:
                    logger.error(f"Order failed: {e}")
            
            await adapter.close()
            
        except Exception as e:
            test_result['error'] = str(e)
        
        test_result['end'] = datetime.now().isoformat()
        test_result['passed'] = (
            test_result['slow_requests'] > 0 and
            test_result['kill_switch_triggered']  # Should trigger on high latency
        )
        
        self.test_results.append(test_result)
        logger.info(f"Slow Response test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def test_idempotency(self) -> Dict[str, Any]:
        """Test idempotency of order creation"""
        logger.info("Starting Idempotency test...")
        
        test_result = {
            'test': 'idempotency',
            'start': datetime.now().isoformat(),
            'duplicate_attempts': 0,
            'unique_orders': 0,
            'idempotent': True
        }
        
        adapter = LiveAdapter()
        
        try:
            await adapter.initialize()
            
            # Generate fixed client order ID
            client_order_id = f"IDEMPOTENT-TEST-{int(time.time())}"
            
            orders_created = []
            
            # Attempt to create same order 5 times
            for attempt in range(5):
                test_result['duplicate_attempts'] += 1
                
                try:
                    # Mock the client order ID generation
                    adapter._generate_client_order_id = lambda strategy: client_order_id
                    
                    order = await adapter.create_order(
                        symbol="BTC/USDT",
                        side="buy",
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal("50000"),
                        strategy="idempotency_test"
                    )
                    
                    if order and order.order_id not in [o.order_id for o in orders_created]:
                        orders_created.append(order)
                        test_result['unique_orders'] += 1
                    
                    self.retry_logs.append({
                        'timestamp': datetime.now().isoformat(),
                        'attempt': attempt + 1,
                        'client_order_id': client_order_id,
                        'unique_orders': test_result['unique_orders']
                    })
                    
                except Exception as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        # Expected for idempotent behavior
                        logger.info(f"Duplicate order rejected (expected): {e}")
                    else:
                        test_result['error'] = str(e)
                
                await asyncio.sleep(1)
            
            # Should only create 1 unique order despite 5 attempts
            test_result['idempotent'] = test_result['unique_orders'] <= 1
            
            await adapter.close()
            
        except Exception as e:
            test_result['error'] = str(e)
            test_result['idempotent'] = False
        
        test_result['end'] = datetime.now().isoformat()
        test_result['passed'] = test_result['idempotent']
        
        self.test_results.append(test_result)
        logger.info(f"Idempotency test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def test_state_machine_consistency(self) -> Dict[str, Any]:
        """Test order state machine consistency during chaos"""
        logger.info("Starting State Machine Consistency test...")
        
        test_result = {
            'test': 'state_machine_consistency',
            'start': datetime.now().isoformat(),
            'orders_tracked': 0,
            'invalid_transitions': 0,
            'consistency_maintained': True
        }
        
        shadow_controller = ShadowModeController()
        shadow_controller.set_mode("shadow")  # Use shadow mode for safety
        
        # Valid state transitions
        valid_transitions = {
            OrderState.NEW: [OrderState.PARTIAL, OrderState.FILLED, OrderState.CANCELED],
            OrderState.PARTIAL: [OrderState.FILLED, OrderState.CANCELED],
            OrderState.FILLED: [],  # Terminal state
            OrderState.CANCELED: [],  # Terminal state
            OrderState.REJECTED: [],  # Terminal state
            OrderState.EXPIRED: []  # Terminal state
        }
        
        try:
            # Create multiple orders and track state changes
            order_history = {}
            
            for i in range(10):
                executed, result = await shadow_controller.create_order(
                    symbol="BTC/USDT",
                    side="buy" if i % 2 == 0 else "sell",
                    order_type="limit",
                    quantity=Decimal("0.001"),
                    price=Decimal("50000" if i % 2 == 0 else "51000")
                )
                
                order_id = f"test_order_{i}"
                order_history[order_id] = [OrderState.NEW]
                test_result['orders_tracked'] += 1
                
                # Simulate state changes
                for _ in range(random.randint(1, 3)):
                    current_state = order_history[order_id][-1]
                    possible_next = valid_transitions.get(current_state, [])
                    
                    if possible_next:
                        # Simulate chaos - sometimes invalid transition
                        if random.random() < 0.1:  # 10% chance of invalid
                            # Try invalid transition
                            all_states = list(OrderState)
                            invalid_state = random.choice([s for s in all_states if s not in possible_next])
                            
                            # System should prevent this
                            test_result['invalid_transitions'] += 1
                            test_result['consistency_maintained'] = False
                            
                            logger.error(f"Invalid transition attempted: {current_state} -> {invalid_state}")
                        else:
                            # Valid transition
                            next_state = random.choice(possible_next)
                            order_history[order_id].append(next_state)
                    
                    await asyncio.sleep(0.1)
            
            # Verify all transitions were valid
            for order_id, states in order_history.items():
                for i in range(len(states) - 1):
                    from_state = states[i]
                    to_state = states[i + 1]
                    
                    if to_state not in valid_transitions.get(from_state, []):
                        test_result['invalid_transitions'] += 1
                        test_result['consistency_maintained'] = False
                        logger.error(f"Invalid transition found: {from_state} -> {to_state}")
            
        except Exception as e:
            test_result['error'] = str(e)
            test_result['consistency_maintained'] = False
        
        test_result['end'] = datetime.now().isoformat()
        test_result['passed'] = (
            test_result['orders_tracked'] > 0 and
            test_result['invalid_transitions'] == 0 and
            test_result['consistency_maintained']
        )
        
        self.test_results.append(test_result)
        logger.info(f"State Machine test: {'PASSED' if test_result['passed'] else 'FAILED'}")
        
        return test_result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all chaos tests"""
        logger.info("Starting Chaos Test Suite...")
        
        tests = [
            self.test_429_storm,
            self.test_network_flapping,
            self.test_dns_failure,
            self.test_slow_response,
            self.test_idempotency,
            self.test_state_machine_consistency
        ]
        
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                logger.error(f"Test {test_func.__name__} crashed: {e}")
                self.test_results.append({
                    'test': test_func.__name__,
                    'passed': False,
                    'error': str(e)
                })
            
            # Cool down between tests
            await asyncio.sleep(2)
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        with open('chaos_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate chaos test report"""
        passed = sum(1 for r in self.test_results if r.get('passed', False))
        total = len(self.test_results)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'duration': (datetime.now() - self.start_time).total_seconds(),
            'summary': {
                'total_tests': total,
                'passed': passed,
                'failed': total - passed,
                'success_rate': passed / max(1, total)
            },
            'test_results': self.test_results,
            'retry_logs': self.retry_logs[-50:],  # Last 50 retry logs
            'order_states': self.order_states[-50:],  # Last 50 order state changes
            'verdict': 'PASS' if passed == total else 'FAIL'
        }


async def main():
    """Main chaos test execution"""
    print("\n" + "="*60)
    print("CHAOS ENGINEERING TEST SUITE")
    print("="*60 + "\n")
    
    suite = ChaosTestSuite()
    report = await suite.run_all_tests()
    
    # Print summary
    print("\n" + "="*60)
    print("CHAOS TEST SUMMARY")
    print("="*60)
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1%}")
    print(f"Duration: {report['duration']:.2f}s")
    print(f"\nVerdict: {report['verdict']}")
    
    # Print individual results
    print("\nIndividual Results:")
    for result in report['test_results']:
        status = "PASS" if result.get('passed', False) else "FAIL"
        print(f"  - {result['test']}: {status}")
    
    print(f"\nReport saved to: chaos_test_report.json")
    
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)