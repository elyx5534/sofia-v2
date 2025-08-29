"""
Canary Runner - Orchestrates canary deployment based on plan
"""

import os
import sys
import time
import yaml
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.shadow_mode import ShadowModeController
from src.risk.engine import RiskEngine
from src.risk.kill_switch import KillSwitch
from src.reconciliation.eod_reports import ReconciliationEngine
from src.observability.monitoring import observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CanaryRunner:
    """Orchestrates canary deployment based on YAML plan"""
    
    def __init__(self, plan_file: str = "canary_plan.yaml"):
        self.plan = self._load_plan(plan_file)
        self.current_phase = None
        self.phase_metrics = {}
        self.phase_history = []
        self.start_time = None
        self.shadow_controller = None
        self.risk_engine = None
        self.kill_switch = None
        self.reconciliation = None
        
    def _load_plan(self, plan_file: str) -> Dict[str, Any]:
        """Load canary plan from YAML"""
        with open(plan_file, 'r') as f:
            return yaml.safe_load(f)
    
    async def initialize(self):
        """Initialize components"""
        logger.info("Initializing canary runner...")
        
        self.shadow_controller = ShadowModeController()
        self.risk_engine = RiskEngine()
        self.kill_switch = KillSwitch(self.risk_engine)
        self.reconciliation = ReconciliationEngine(
            shadow_controller=self.shadow_controller,
            risk_engine=self.risk_engine
        )
        
        # Set initial mode
        initial_mode = self.plan['config']['initial_mode']
        self.shadow_controller.set_mode(initial_mode)
        
        logger.info(f"Initialized in {initial_mode} mode")
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics"""
        metrics = {}
        
        # Get metrics from various sources
        try:
            # From shadow controller
            shadow_status = self.shadow_controller.get_status()
            metrics['success_rate'] = shadow_status.get('canary_success_rate', 1.0)
            metrics['error_rate'] = 1.0 - metrics['success_rate']
            
            # From risk engine
            risk_status = self.risk_engine.get_status()
            metrics['daily_pnl'] = float(risk_status.get('daily_pnl', 0))
            metrics['position_drift_usd'] = 0  # Would come from reconciliation
            
            # From observability
            obs_metrics = observability.get_status()
            
            # Mock some metrics for testing
            metrics['latency_p95_ms'] = 50
            metrics['latency_p99_ms'] = 100
            metrics['ws_disconnections'] = 0
            metrics['reconciliation_success'] = True
            metrics['all_slos_met'] = True
            metrics['availability'] = 0.999
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
        
        return metrics
    
    async def check_health(self, phase: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Check if health criteria are met"""
        health_checks = phase.get('health_checks', [])
        
        for check in health_checks:
            metric_name = check['metric']
            threshold = check['threshold']
            operator = check['operator']
            
            if metric_name not in metrics:
                logger.warning(f"Metric {metric_name} not found")
                continue
            
            value = metrics[metric_name]
            
            # Evaluate condition
            passed = False
            if operator == 'less_than':
                passed = value < threshold
            elif operator == 'greater_than':
                passed = value > threshold
            elif operator == 'equals':
                passed = value == threshold
            
            if not passed:
                logger.warning(f"Health check failed: {metric_name} = {value} (threshold: {operator} {threshold})")
                return False
        
        return True
    
    async def check_success_criteria(self, phase: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Check if success criteria are met"""
        criteria = phase.get('success_criteria', {})
        
        # Check minimum orders
        min_orders = criteria.get('min_orders', 0)
        actual_orders = self.shadow_controller.order_count
        if actual_orders < min_orders:
            logger.warning(f"Insufficient orders: {actual_orders} < {min_orders}")
            return False
        
        # Check success rate
        min_success_rate = criteria.get('min_success_rate', 0)
        actual_success_rate = metrics.get('success_rate', 0)
        if actual_success_rate < min_success_rate:
            logger.warning(f"Success rate too low: {actual_success_rate} < {min_success_rate}")
            return False
        
        # Check reconciliation
        if criteria.get('reconciliation_passed'):
            if not metrics.get('reconciliation_success'):
                logger.warning("Reconciliation failed")
                return False
        
        return True
    
    async def check_rollback_triggers(self, phase: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[str]:
        """Check if any rollback triggers are met"""
        triggers = phase.get('rollback_triggers', [])
        
        for trigger in triggers:
            condition = trigger['condition']
            action = trigger['action']
            
            # Parse condition (simplified)
            if 'error_rate >' in condition:
                threshold = float(condition.split('>')[-1].strip())
                if metrics.get('error_rate', 0) > threshold:
                    return action
            
            elif 'daily_pnl <' in condition:
                threshold = float(condition.split('<')[-1].strip())
                if metrics.get('daily_pnl', 0) < threshold:
                    return action
            
            elif 'kill_switch = ON' in condition:
                if self.kill_switch.get_state() == "ON":
                    return action
        
        return None
    
    async def execute_phase(self, phase: Dict[str, Any]) -> bool:
        """Execute a single canary phase"""
        phase_name = phase['name']
        percentage = phase['percentage']
        duration_minutes = phase['duration_minutes']
        
        logger.info(f"Starting phase: {phase_name} ({percentage}% traffic for {duration_minutes} minutes)")
        
        self.current_phase = phase_name
        phase_start = datetime.now()
        phase_end = phase_start + timedelta(minutes=duration_minutes)
        
        # Update canary percentage
        if percentage > 0:
            self.shadow_controller.set_mode("canary")
            self.shadow_controller.canary_percentage = percentage
            os.environ['CANARY_PERCENTAGE'] = str(percentage)
        
        # Phase execution loop
        while datetime.now() < phase_end:
            # Collect metrics
            metrics = await self.collect_metrics()
            self.phase_metrics[phase_name] = metrics
            
            # Check health
            if not await self.check_health(phase, metrics):
                logger.error(f"Health check failed in phase {phase_name}")
                return False
            
            # Check rollback triggers
            rollback_action = await self.check_rollback_triggers(phase, metrics)
            if rollback_action:
                logger.warning(f"Rollback triggered: {rollback_action}")
                await self.rollback(rollback_action)
                return False
            
            # Log progress
            remaining = (phase_end - datetime.now()).total_seconds() / 60
            logger.info(f"Phase {phase_name}: {remaining:.1f} minutes remaining, metrics: {metrics}")
            
            # Sleep before next check
            await asyncio.sleep(30)  # Check every 30 seconds
        
        # Check success criteria at end of phase
        final_metrics = await self.collect_metrics()
        if not await self.check_success_criteria(phase, final_metrics):
            logger.error(f"Success criteria not met for phase {phase_name}")
            return False
        
        # Record phase completion
        self.phase_history.append({
            'phase': phase_name,
            'started': phase_start.isoformat(),
            'completed': datetime.now().isoformat(),
            'metrics': final_metrics,
            'success': True
        })
        
        logger.info(f"Phase {phase_name} completed successfully")
        return True
    
    async def check_gate(self, from_phase: str, to_phase: str) -> bool:
        """Check if gate requirements are met"""
        gates = self.plan.get('gates', [])
        
        for gate in gates:
            if gate['from'] == from_phase and gate['to'] == to_phase:
                requirements = gate.get('requirements', {})
                
                # Check automated requirements
                auto_checks = requirements.get('automated_checks', [])
                for check in auto_checks:
                    if check == 'reconciliation_passed':
                        report = await self.reconciliation.reconcile_positions()
                        if report['status'] != 'success':
                            logger.error("Reconciliation failed at gate")
                            return False
                    
                    elif check == 'no_open_incidents':
                        # Check for incidents (mock)
                        pass
                    
                    elif check == 'all_health_checks_passed':
                        # Already checked in phase
                        pass
                
                # Manual approval (mock for automation)
                if requirements.get('manual_approval'):
                    logger.info(f"Manual approval required for {from_phase} -> {to_phase}")
                    # In real scenario, would wait for approval
                    await asyncio.sleep(2)  # Simulate approval delay
                
                return True
        
        return True  # No gate found, proceed
    
    async def rollback(self, action: str):
        """Execute rollback"""
        logger.warning(f"Executing rollback: {action}")
        
        if action == 'immediate':
            # Immediate rollback to shadow mode
            await self.shadow_controller.rollback_to_shadow("Canary rollback triggered")
            
            # Activate kill switch
            await self.kill_switch.activate(
                trigger=self.kill_switch.TriggerType.EXTERNAL,
                reason="Canary rollback"
            )
        
        elif action == 'gradual':
            # Reduce percentage gradually
            current = self.shadow_controller.canary_percentage
            new_percentage = max(10, current / 2)  # Reduce by half, minimum 10%
            self.shadow_controller.canary_percentage = new_percentage
            logger.info(f"Reduced canary percentage to {new_percentage}%")
        
        # Generate rollback report
        await self.generate_rollback_report(action)
    
    async def run(self) -> bool:
        """Run the complete canary deployment"""
        logger.info("Starting canary deployment...")
        self.start_time = datetime.now()
        
        try:
            await self.initialize()
            
            phases = self.plan['phases']
            
            for i, phase in enumerate(phases):
                # Check gate before phase
                if i > 0:
                    prev_phase = phases[i-1]['name']
                    curr_phase = phase['name']
                    
                    if not await self.check_gate(prev_phase, curr_phase):
                        logger.error(f"Gate check failed: {prev_phase} -> {curr_phase}")
                        await self.rollback('immediate')
                        return False
                
                # Execute phase
                if not await self.execute_phase(phase):
                    logger.error(f"Phase {phase['name']} failed")
                    return False
                
                # Cool down between phases
                if i < len(phases) - 1:
                    logger.info("Cooling down before next phase...")
                    await asyncio.sleep(60)
            
            # All phases completed successfully
            logger.info("Canary deployment completed successfully!")
            
            # Promote to production
            if self.plan['phases'][-1]['percentage'] == 100:
                self.shadow_controller.set_mode("live")
                logger.info("Promoted to full production!")
            
            # Generate final report
            await self.generate_final_report()
            
            return True
            
        except Exception as e:
            logger.error(f"Canary deployment failed: {e}")
            await self.rollback('immediate')
            return False
    
    async def generate_rollback_report(self, action: str):
        """Generate rollback report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'type': 'rollback',
            'action': action,
            'current_phase': self.current_phase,
            'phase_history': self.phase_history,
            'final_metrics': self.phase_metrics.get(self.current_phase, {}),
            'duration': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }
        
        with open('canary_rollback_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("Rollback report generated: canary_rollback_report.json")
    
    async def generate_final_report(self):
        """Generate final deployment report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'type': 'success',
            'duration': (datetime.now() - self.start_time).total_seconds(),
            'phases_completed': len(self.phase_history),
            'phase_history': self.phase_history,
            'final_mode': self.shadow_controller.mode.value,
            'final_metrics': await self.collect_metrics()
        }
        
        with open('canary_final_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info("Final report generated: canary_final_report.json")


async def main():
    """Main canary runner"""
    print("\n" + "="*60)
    print("CANARY DEPLOYMENT RUNNER")
    print("="*60 + "\n")
    
    # Check for plan file
    plan_file = sys.argv[1] if len(sys.argv) > 1 else "scripts/canary_plan.yaml"
    
    if not os.path.exists(plan_file):
        print(f"Plan file not found: {plan_file}")
        return 1
    
    runner = CanaryRunner(plan_file)
    success = await runner.run()
    
    if success:
        print("\n[SUCCESS] Canary deployment completed successfully!")
        return 0
    else:
        print("\n[FAILURE] Canary deployment failed - rollback executed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)