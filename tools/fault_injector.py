"""
Kill-Switch Fault Injector
Scenario-based testing for emergency stops
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.watchdog import Watchdog


class FaultInjector:
    """Inject faults to test kill-switch behavior"""

    def __init__(self):
        self.scenarios = {
            "CLOCK_SKEW": self.inject_clock_skew,
            "ERROR_BURST": self.inject_error_burst,
            "RATE_LIMIT": self.inject_rate_limit,
            "DAILY_DD": self.inject_daily_drawdown,
        }
        self.results = []
        self.watchdog = Watchdog()

    def inject_clock_skew(self) -> Dict:
        """Simulate clock skew beyond threshold"""
        print("\n[SCENARIO] CLOCK_SKEW - Simulating time drift > 4s")

        # Mock the time difference
        with patch("src.core.watchdog.datetime") as mock_dt:
            # Set local time 5 seconds ahead
            mock_dt.now.return_value = datetime.now() + timedelta(seconds=5)
            mock_dt.fromisoformat = datetime.fromisoformat

            # Create mock response with server time
            mock_response = {
                "server_time": datetime.now().isoformat(),
                "local_time": mock_dt.now().isoformat(),
            }

            # Check clock skew
            self.watchdog.last_proof_time = datetime.now() - timedelta(seconds=1)
            status = self.watchdog.check_clock_sync()

            result = {
                "scenario": "CLOCK_SKEW",
                "injected_skew_seconds": 5,
                "threshold_seconds": 4,
                "triggered_pause": not status,
                "details": mock_response,
            }

            if not status:
                print("  [TRIGGERED] Clock skew detected - PAUSE activated")
            else:
                print("  [FAILED] Clock skew not detected")

            return result

    def inject_error_burst(self) -> Dict:
        """Simulate error burst exceeding threshold"""
        print("\n[SCENARIO] ERROR_BURST - Injecting 10+ errors in 60s")

        # Mock logger to count errors
        mock_logger = Mock()
        error_count = 0

        def mock_error(msg):
            nonlocal error_count
            error_count += 1

        mock_logger.error = mock_error

        # Inject errors
        with patch("src.core.watchdog.logger", mock_logger):
            # Simulate 12 errors
            for i in range(12):
                self.watchdog.error_counts.append(datetime.now())
                mock_logger.error(f"Simulated error {i+1}")

            # Check error rate
            status = self.watchdog.check_error_rate()

            result = {
                "scenario": "ERROR_BURST",
                "errors_injected": 12,
                "time_window_seconds": 60,
                "threshold": 10,
                "triggered_pause": not status,
                "error_count": error_count,
            }

            if not status:
                print(
                    f"  [TRIGGERED] Error burst detected ({error_count} errors) - PAUSE activated"
                )
            else:
                print("  [FAILED] Error burst not detected")

            return result

    def inject_rate_limit(self) -> Dict:
        """Simulate rate limit exception from exchange"""
        print("\n[SCENARIO] RATE_LIMIT - Simulating exchange rate limit")

        # Mock ccxt exception
        class RateLimitException(Exception):
            pass

        triggered = False

        try:
            # Simulate rate limit hit
            for i in range(5):
                if i >= 3:
                    raise RateLimitException("429 Too Many Requests")
                time.sleep(0.1)
        except RateLimitException:
            # Watchdog should detect this
            self.watchdog.consecutive_api_errors += 1
            status = self.watchdog.check_api_health()
            triggered = not status

            if triggered:
                print("  [TRIGGERED] Rate limit detected - PAUSE activated")
            else:
                print("  [FAILED] Rate limit not handled properly")

        result = {
            "scenario": "RATE_LIMIT",
            "api_calls_before_limit": 3,
            "exception_type": "RateLimitException",
            "triggered_pause": triggered,
            "consecutive_errors": self.watchdog.consecutive_api_errors,
        }

        return result

    def inject_daily_drawdown(self) -> Dict:
        """Simulate daily drawdown exceeding limit"""
        print("\n[SCENARIO] DAILY_DD - Simulating -1.2% daily drawdown")

        # Mock P&L feed
        initial_balance = 10000
        current_balance = initial_balance * 0.988  # -1.2% loss

        with patch.object(self.watchdog, "get_current_pnl", return_value=-120):
            with patch.object(self.watchdog, "daily_pnl_limit", -100):  # -1% limit
                # Check daily P&L
                status = self.watchdog.check_daily_pnl()

                result = {
                    "scenario": "DAILY_DD",
                    "initial_balance": initial_balance,
                    "current_balance": current_balance,
                    "drawdown_pct": -1.2,
                    "limit_pct": -1.0,
                    "triggered_pause": not status,
                    "pnl_amount": -120,
                }

                if not status:
                    print("  [TRIGGERED] Daily drawdown limit breached - PAUSE activated")
                else:
                    print("  [FAILED] Drawdown limit not detected")

                return result

    def run_all_scenarios(self) -> List[Dict]:
        """Run all fault injection scenarios"""
        print("=" * 60)
        print("KILL-SWITCH FAULT INJECTION TEST")
        print("=" * 60)
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Scenarios: {list(self.scenarios.keys())}")
        print("-" * 60)

        for scenario_name, scenario_func in self.scenarios.items():
            try:
                result = scenario_func()
                result["timestamp"] = datetime.now().isoformat()
                self.results.append(result)

                # Reset watchdog state between scenarios
                self.watchdog.reset_state()
                time.sleep(1)

            except Exception as e:
                print(f"  [ERROR] Scenario {scenario_name} failed: {e}")
                self.results.append(
                    {"scenario": scenario_name, "error": str(e), "triggered_pause": False}
                )

        return self.results

    def generate_report(self) -> Dict:
        """Generate test report"""
        report = {
            "test_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.now().isoformat(),
            "scenarios_tested": len(self.results),
            "scenarios_passed": sum(1 for r in self.results if r.get("triggered_pause", False)),
            "results": self.results,
            "summary": self._generate_summary(),
        }

        return report

    def _generate_summary(self) -> Dict:
        """Generate test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("triggered_pause", False))
        failed = total - passed

        summary = {
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "all_passed": passed == total,
        }

        # Add details for failed scenarios
        if failed > 0:
            summary["failed_scenarios"] = [
                r["scenario"] for r in self.results if not r.get("triggered_pause", False)
            ]

        return summary

    def save_report(self, report: Dict):
        """Save test report"""
        report_file = Path("logs/fault_report.json")
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n[SAVED] Fault injection report: {report_file}")

        # Also save markdown version
        self.save_markdown_report(report)

    def save_markdown_report(self, report: Dict):
        """Save markdown report"""
        md_file = Path("reports/FAULT_INJECTION.md")
        md_file.parent.mkdir(exist_ok=True)

        with open(md_file, "w") as f:
            f.write("# Kill-Switch Fault Injection Report\n\n")
            f.write(f"**Test ID:** {report['test_id']}\n")
            f.write(f"**Timestamp:** {report['timestamp']}\n\n")

            # Summary
            s = report["summary"]
            f.write("## Summary\n\n")
            f.write(f"- Total Scenarios: {s['total_scenarios']}\n")
            f.write(f"- Passed: {s['passed']}\n")
            f.write(f"- Failed: {s['failed']}\n")
            f.write(f"- Success Rate: {s['success_rate']:.1f}%\n")
            f.write(f"- **Overall Result:** {'PASS' if s['all_passed'] else 'FAIL'}\n\n")

            # Scenario details
            f.write("## Scenario Results\n\n")
            f.write("| Scenario | Triggered | Details |\n")
            f.write("|----------|-----------|---------|")

            for result in report["results"]:
                status = "[PASS]" if result.get("triggered_pause", False) else "[FAIL]"

                details = ""
                if result["scenario"] == "CLOCK_SKEW":
                    details = f"Skew: {result.get('injected_skew_seconds', 0)}s"
                elif result["scenario"] == "ERROR_BURST":
                    details = f"Errors: {result.get('errors_injected', 0)}"
                elif result["scenario"] == "RATE_LIMIT":
                    details = f"API errors: {result.get('consecutive_errors', 0)}"
                elif result["scenario"] == "DAILY_DD":
                    details = f"DD: {result.get('drawdown_pct', 0):.1f}%"

                f.write(f"\n| {result['scenario']} | {status} | {details} |")

            f.write("\n\n")

            if not s["all_passed"] and "failed_scenarios" in s:
                f.write("## Failed Scenarios\n\n")
                for scenario in s["failed_scenarios"]:
                    f.write(f"- {scenario}\n")

    def print_summary(self, report: Dict):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("FAULT INJECTION TEST COMPLETE")
        print("=" * 60)

        s = report["summary"]
        print(f"Scenarios Tested: {s['total_scenarios']}")
        print(f"Passed: {s['passed']}")
        print(f"Failed: {s['failed']}")
        print(f"Success Rate: {s['success_rate']:.1f}%")

        print("\nRESULTS:")
        for result in report["results"]:
            status = "[PASS]" if result.get("triggered_pause", False) else "[FAIL]"
            print(f"  {result['scenario']:15} {status}")

        print(
            f"\nOVERALL: {'PASS - All kill-switches working' if s['all_passed'] else 'FAIL - Some kill-switches not triggered'}"
        )

        print("\nREPORTS SAVED:")
        print("  - logs/fault_report.json")
        print("  - reports/FAULT_INJECTION.md")
        print("=" * 60)


def main():
    injector = FaultInjector()
    results = injector.run_all_scenarios()
    report = injector.generate_report()
    injector.save_report(report)
    injector.print_summary(report)

    # Exit with appropriate code
    sys.exit(0 if report["summary"]["all_passed"] else 1)


if __name__ == "__main__":
    main()
