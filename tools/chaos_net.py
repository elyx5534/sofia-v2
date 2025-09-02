"""
Chaos Network Testing
Simulates network issues and verifies system recovery
"""

import time
import platform
import subprocess
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging
import random
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChaosNetworkTest:
    """Network chaos testing for resilience verification"""
    
    def __init__(self):
        self.os_type = platform.system().lower()
        self.test_duration_seconds = 180  # 3 minutes
        self.latency_ms = 200
        self.packet_loss_percent = 1
        
        # Test results
        self.results = {
            "start_time": None,
            "end_time": None,
            "tests": [],
            "recovery": {},
            "passed": False
        }
        
        # Monitoring
        self.monitoring_active = False
        self.system_state = "normal"
        self.error_count = 0
        self.recovery_time = None
    
    def is_admin(self) -> bool:
        """Check if running with admin privileges"""
        if self.os_type == "windows":
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        else:
            import os
            return os.geteuid() == 0
    
    def apply_network_chaos_linux(self):
        """Apply network chaos using tc/netem on Linux"""
        if not self.is_admin():
            logger.warning("Need root privileges for tc/netem. Using simulation mode.")
            return self.simulate_network_chaos()
        
        try:
            # Add latency and packet loss
            cmd = f"tc qdisc add dev eth0 root netem delay {self.latency_ms}ms loss {self.packet_loss_percent}%"
            subprocess.run(cmd.split(), check=True)
            logger.info(f"Applied network chaos: {self.latency_ms}ms latency, {self.packet_loss_percent}% loss")
            return True
        except Exception as e:
            logger.error(f"Failed to apply tc/netem: {e}")
            return False
    
    def remove_network_chaos_linux(self):
        """Remove network chaos on Linux"""
        if not self.is_admin():
            return
        
        try:
            cmd = "tc qdisc del dev eth0 root"
            subprocess.run(cmd.split(), check=True)
            logger.info("Removed network chaos")
        except:
            pass
    
    def simulate_network_chaos(self):
        """Simulate network chaos in Python (cross-platform)"""
        logger.info(f"Simulating network chaos: {self.latency_ms}ms latency, {self.packet_loss_percent}% loss")
        
        # Start chaos simulation thread
        self.chaos_active = True
        chaos_thread = threading.Thread(target=self._chaos_simulator)
        chaos_thread.daemon = True
        chaos_thread.start()
        
        return True
    
    def _chaos_simulator(self):
        """Background thread to simulate network issues"""
        while self.chaos_active:
            # Simulate latency
            time.sleep(self.latency_ms / 1000)
            
            # Simulate packet loss
            if random.random() < (self.packet_loss_percent / 100):
                self.error_count += 1
            
            time.sleep(0.1)
    
    def stop_chaos_simulation(self):
        """Stop chaos simulation"""
        self.chaos_active = False
        logger.info("Stopped chaos simulation")
    
    async def monitor_system(self):
        """Monitor system during chaos test"""
        self.monitoring_active = True
        monitoring_results = {
            "states": [],
            "errors": [],
            "recovery_events": []
        }
        
        start_time = datetime.now()
        
        while self.monitoring_active:
            current_time = datetime.now()
            elapsed = (current_time - start_time).total_seconds()
            
            # Check system state
            state = await self.check_system_state()
            
            monitoring_results["states"].append({
                "timestamp": current_time.isoformat(),
                "elapsed_seconds": elapsed,
                "state": state,
                "error_count": self.error_count
            })
            
            # State transitions
            if self.system_state != state:
                logger.info(f"State transition: {self.system_state} -> {state}")
                
                if self.system_state == "degraded" and state == "normal":
                    # Recovery detected
                    self.recovery_time = elapsed
                    monitoring_results["recovery_events"].append({
                        "timestamp": current_time.isoformat(),
                        "recovery_time_seconds": self.recovery_time,
                        "from_state": self.system_state,
                        "to_state": state
                    })
                
                self.system_state = state
            
            # Check for errors
            if self.error_count > 0:
                monitoring_results["errors"].append({
                    "timestamp": current_time.isoformat(),
                    "error_count": self.error_count,
                    "type": "simulated_packet_loss"
                })
            
            await asyncio.sleep(1)
        
        return monitoring_results
    
    async def check_system_state(self) -> str:
        """Check current system state"""
        try:
            # Mock health check - in production, call actual health endpoint
            import aiohttp
            
            health_checks = {
                "api": False,
                "websocket": False,
                "data_feed": False
            }
            
            # Simulate health checks
            async with aiohttp.ClientSession() as session:
                try:
                    # Check API health
                    async with session.get("http://localhost:8000/api/health", timeout=5) as resp:
                        if resp.status == 200:
                            health_checks["api"] = True
                except:
                    pass
                
                # Simulate other checks
                health_checks["websocket"] = random.random() > 0.1  # 90% success
                health_checks["data_feed"] = random.random() > 0.05  # 95% success
            
            # Determine state
            healthy_count = sum(health_checks.values())
            
            if healthy_count == 3:
                return "normal"
            elif healthy_count >= 2:
                return "degraded"
            else:
                return "critical"
            
        except Exception as e:
            logger.error(f"Error checking system state: {e}")
            return "unknown"
    
    def check_watchdog_response(self) -> Dict:
        """Check if watchdog responded correctly"""
        watchdog_log = Path("logs/watchdog.log")
        
        response = {
            "detected_degradation": False,
            "triggered_pause": False,
            "recovery_detected": False
        }
        
        if watchdog_log.exists():
            with open(watchdog_log, 'r') as f:
                content = f.read()
                
                if "degraded" in content.lower():
                    response["detected_degradation"] = True
                
                if "pause" in content.lower() or "halt" in content.lower():
                    response["triggered_pause"] = True
                
                if "recovered" in content.lower() or "normal" in content.lower():
                    response["recovery_detected"] = True
        
        return response
    
    async def run_chaos_test(self) -> Dict:
        """Run complete chaos test"""
        logger.info("="*60)
        logger.info(" CHAOS NETWORK TEST")
        logger.info("="*60)
        
        self.results["start_time"] = datetime.now().isoformat()
        
        # Phase 1: Baseline measurement
        logger.info("\nPhase 1: Baseline measurement (30s)")
        baseline = await self.measure_baseline()
        self.results["tests"].append({
            "phase": "baseline",
            "duration": 30,
            "metrics": baseline
        })
        
        # Phase 2: Apply chaos
        logger.info(f"\nPhase 2: Applying chaos ({self.test_duration_seconds}s)")
        logger.info(f"  Latency: +{self.latency_ms}ms")
        logger.info(f"  Packet loss: {self.packet_loss_percent}%")
        
        if self.os_type == "linux":
            chaos_applied = self.apply_network_chaos_linux()
        else:
            chaos_applied = self.simulate_network_chaos()
        
        if not chaos_applied:
            logger.error("Failed to apply chaos")
            self.results["passed"] = False
            return self.results
        
        # Start monitoring
        monitor_task = asyncio.create_task(self.monitor_system())
        
        # Wait for chaos duration
        await asyncio.sleep(self.test_duration_seconds)
        
        # Phase 3: Remove chaos and verify recovery
        logger.info("\nPhase 3: Removing chaos and verifying recovery")
        
        if self.os_type == "linux":
            self.remove_network_chaos_linux()
        else:
            self.stop_chaos_simulation()
        
        # Monitor recovery for 60 seconds
        await asyncio.sleep(60)
        
        # Stop monitoring
        self.monitoring_active = False
        monitoring_results = await monitor_task
        
        self.results["tests"].append({
            "phase": "chaos",
            "duration": self.test_duration_seconds,
            "monitoring": monitoring_results
        })
        
        # Phase 4: Verify recovery
        logger.info("\nPhase 4: Verifying recovery")
        recovery = await self.verify_recovery()
        self.results["recovery"] = recovery
        
        # Check watchdog response
        watchdog = self.check_watchdog_response()
        self.results["watchdog"] = watchdog
        
        # Determine pass/fail
        self.results["passed"] = self.evaluate_results()
        self.results["end_time"] = datetime.now().isoformat()
        
        return self.results
    
    async def measure_baseline(self) -> Dict:
        """Measure baseline performance"""
        metrics = {
            "latency_ms": [],
            "success_rate": 0,
            "throughput": 0
        }
        
        # Simulate baseline measurements
        for _ in range(10):
            # Mock latency measurement
            latency = random.uniform(10, 30)
            metrics["latency_ms"].append(latency)
            await asyncio.sleep(0.5)
        
        metrics["avg_latency_ms"] = sum(metrics["latency_ms"]) / len(metrics["latency_ms"])
        metrics["success_rate"] = 0.99  # 99% baseline success
        metrics["throughput"] = 1000  # msgs/sec
        
        return metrics
    
    async def verify_recovery(self) -> Dict:
        """Verify system recovered after chaos"""
        recovery = {
            "recovered": False,
            "recovery_time_seconds": None,
            "final_state": None,
            "checks": {}
        }
        
        # Check final state
        final_state = await self.check_system_state()
        recovery["final_state"] = final_state
        recovery["recovered"] = final_state == "normal"
        
        if self.recovery_time:
            recovery["recovery_time_seconds"] = self.recovery_time
        
        # Specific recovery checks
        recovery["checks"] = {
            "api_responsive": await self.check_api_responsive(),
            "data_feeds_active": await self.check_data_feeds(),
            "no_persistent_errors": self.error_count == 0
        }
        
        return recovery
    
    async def check_api_responsive(self) -> bool:
        """Check if API is responsive"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/api/health", timeout=2) as resp:
                    return resp.status == 200
        except:
            return False
    
    async def check_data_feeds(self) -> bool:
        """Check if data feeds are active"""
        # Mock check - in production, verify actual feeds
        return True
    
    def evaluate_results(self) -> bool:
        """Evaluate if test passed"""
        
        # Pass criteria:
        # 1. System detected degradation
        # 2. Did not trigger full pause (threshold not exceeded)
        # 3. Recovered within reasonable time
        # 4. Final state is normal
        
        criteria = {
            "degradation_detected": False,
            "no_unnecessary_pause": True,
            "recovered": False,
            "reasonable_recovery_time": False
        }
        
        # Check monitoring results
        if self.results["tests"]:
            for test in self.results["tests"]:
                if test.get("phase") == "chaos":
                    monitoring = test.get("monitoring", {})
                    states = monitoring.get("states", [])
                    
                    # Check if degradation was detected
                    for state in states:
                        if state["state"] == "degraded":
                            criteria["degradation_detected"] = True
                            break
        
        # Check watchdog response
        if self.results.get("watchdog"):
            watchdog = self.results["watchdog"]
            if watchdog.get("triggered_pause"):
                # Pause should not trigger for mild chaos
                criteria["no_unnecessary_pause"] = False
        
        # Check recovery
        if self.results.get("recovery"):
            recovery = self.results["recovery"]
            criteria["recovered"] = recovery.get("recovered", False)
            
            # Recovery should happen within 60 seconds
            recovery_time = recovery.get("recovery_time_seconds")
            if recovery_time and recovery_time < 60:
                criteria["reasonable_recovery_time"] = True
        
        # Overall pass: most criteria met
        passed_count = sum(criteria.values())
        return passed_count >= 3
    
    def save_report(self):
        """Save chaos test report"""
        report_file = Path("reports/chaos_report.json")
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Report saved to {report_file}")
        
        # Also create markdown report
        self.create_markdown_report()
    
    def create_markdown_report(self):
        """Create human-readable markdown report"""
        report_file = Path("reports/chaos_report.md")
        
        lines = [
            "# Chaos Network Test Report",
            f"\nGenerated: {datetime.now().isoformat()}",
            f"\n## Test Configuration",
            f"- Duration: {self.test_duration_seconds} seconds",
            f"- Latency: +{self.latency_ms}ms",
            f"- Packet Loss: {self.packet_loss_percent}%",
            f"\n## Results",
            f"\n**Overall: {'PASS' if self.results['passed'] else 'FAIL'}**",
        ]
        
        # Recovery details
        if self.results.get("recovery"):
            recovery = self.results["recovery"]
            lines.extend([
                f"\n### Recovery",
                f"- Recovered: {recovery.get('recovered', False)}",
                f"- Recovery Time: {recovery.get('recovery_time_seconds', 'N/A')} seconds",
                f"- Final State: {recovery.get('final_state', 'unknown')}",
            ])
        
        # Watchdog response
        if self.results.get("watchdog"):
            watchdog = self.results["watchdog"]
            lines.extend([
                f"\n### Watchdog Response",
                f"- Detected Degradation: {watchdog.get('detected_degradation', False)}",
                f"- Triggered Pause: {watchdog.get('triggered_pause', False)}",
                f"- Recovery Detected: {watchdog.get('recovery_detected', False)}",
            ])
        
        # Test phases
        lines.append("\n## Test Phases")
        for test in self.results.get("tests", []):
            phase = test.get("phase", "unknown")
            lines.append(f"\n### {phase.title()} Phase")
            
            if phase == "baseline" and test.get("metrics"):
                metrics = test["metrics"]
                lines.append(f"- Average Latency: {metrics.get('avg_latency_ms', 0):.2f}ms")
                lines.append(f"- Success Rate: {metrics.get('success_rate', 0)*100:.1f}%")
            
            elif phase == "chaos" and test.get("monitoring"):
                monitoring = test["monitoring"]
                states = monitoring.get("states", [])
                if states:
                    # Count states
                    state_counts = {}
                    for state in states:
                        s = state["state"]
                        state_counts[s] = state_counts.get(s, 0) + 1
                    
                    lines.append("\nState Distribution:")
                    for state, count in state_counts.items():
                        percentage = (count / len(states)) * 100
                        lines.append(f"- {state}: {count} ({percentage:.1f}%)")
        
        # Recommendations
        lines.extend([
            "\n## Recommendations",
        ])
        
        if self.results["passed"]:
            lines.append("- System demonstrated good resilience to network chaos")
            lines.append("- Continue regular chaos testing")
        else:
            lines.append("- System needs improved resilience")
            lines.append("- Review timeout and retry configurations")
            lines.append("- Enhance circuit breaker patterns")
        
        with open(report_file, 'w') as f:
            f.write("\n".join(lines))
        
        logger.info(f"Markdown report saved to {report_file}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print(" CHAOS TEST SUMMARY")
        print("="*60)
        
        print(f"Status: {'PASS' if self.results['passed'] else 'FAIL'}")
        
        if self.results.get("recovery"):
            recovery = self.results["recovery"]
            print(f"Recovery: {recovery.get('recovered', False)}")
            if recovery.get("recovery_time_seconds"):
                print(f"Recovery Time: {recovery['recovery_time_seconds']:.1f} seconds")
        
        if self.results.get("watchdog"):
            watchdog = self.results["watchdog"]
            print(f"Watchdog Detected Issues: {watchdog.get('detected_degradation', False)}")
            print(f"Unnecessary Pause: {watchdog.get('triggered_pause', False)}")
        
        print("="*60)


async def main():
    """Run chaos network test"""
    
    chaos = ChaosNetworkTest()
    
    # Run test
    results = await chaos.run_chaos_test()
    
    # Save reports
    chaos.save_report()
    
    # Print summary
    chaos.print_summary()
    
    return results["passed"]


if __name__ == "__main__":
    passed = asyncio.run(main())
    exit(0 if passed else 1)