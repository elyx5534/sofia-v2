"""
Mock Quick Campaign Runner - Simulates campaign without actual trading
"""

import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


class MockQuickCampaign:
    """Mock version that simulates results without running actual sessions"""

    def __init__(self):
        self.sessions = []
        self.start_time = datetime.now()

    def simulate_session(self, session_num: int) -> dict:
        """Simulate a session with realistic random results"""
        print(f"\n{'='*60}")
        print(f" SESSION {session_num}/3 (MOCK)")
        print(f"{'='*60}")

        session_time = "AM" if session_num == 1 else "PM"
        prefer_fastest = session_num == 2

        # Simulate metrics with some randomness
        metrics = {
            "grid": {
                "pnl_pct": random.uniform(-0.5, 1.5),
                "maker_fill_rate": random.uniform(55, 75),
                "avg_fill_time_ms": random.randint(5000, 25000),
                "tl_pnl": random.uniform(-50, 150),
            },
            "arbitrage": {
                "pnl_tl": random.uniform(-20, 80),
                "success_rate": random.uniform(50, 70),
                "avg_latency_ms": random.randint(150, 300),
            },
            "qa": {
                "consistency": "PASS" if random.random() > 0.3 else "FAIL",
                "shadow_avg_diff_bps": random.uniform(2, 8),
                "shadow_p95_bps": random.uniform(4, 10),
            },
            "risk": {"max_dd_pct": random.uniform(-1.5, -0.3)},
            "latency": {
                "p50": random.randint(100, 200) if not prefer_fastest else random.randint(50, 150),
                "p95": random.randint(200, 400) if not prefer_fastest else random.randint(100, 300),
            },
            "ev_gate": {
                "reject_count": random.randint(0, 5),
                "total_evaluated": random.randint(20, 50),
            },
        }

        # Calculate pass/fail
        passes = 0
        if metrics["grid"]["maker_fill_rate"] >= 60:
            passes += 1
        if metrics["grid"]["avg_fill_time_ms"] < 20000:
            passes += 1
        if metrics["grid"]["pnl_pct"] > 0:
            passes += 1
        if metrics["arbitrage"]["pnl_tl"] >= 0:
            passes += 1
        if metrics["arbitrage"]["success_rate"] >= 55:
            passes += 1
        if metrics["arbitrage"]["avg_latency_ms"] < 250:
            passes += 1
        if metrics["qa"]["consistency"] == "PASS":
            passes += 1
        if metrics["qa"]["shadow_avg_diff_bps"] < 5:
            passes += 1
        if metrics["qa"]["shadow_p95_bps"] < 7:
            passes += 1
        if metrics["risk"]["max_dd_pct"] >= -1:
            passes += 1

        status = "PASS" if passes >= 7 else "FAIL"

        session_data = {
            "session_num": session_num,
            "start_time": datetime.now().isoformat(),
            "session_time": session_time,
            "prefer_fastest": prefer_fastest,
            "ev_gate_enabled": True,
            "metrics": metrics,
            "status": status,
            "passes": passes,
            "end_time": (datetime.now() + timedelta(seconds=2)).isoformat(),
        }

        print(f"Session Time: {session_time}")
        print(f"Route Mode: {'FAST' if prefer_fastest else 'NORMAL'}")
        print(f"Criteria Passed: {passes}/10")
        print(f"Status: {status}")

        # Simulate processing time
        time.sleep(1)

        return session_data

    def run_campaign(self):
        """Run the mock campaign"""
        print("=" * 60)
        print(" MOCK 24-HOUR QUICK CAMPAIGN")
        print("=" * 60)
        print(f"Start Time: {self.start_time}")
        print("Sessions: 3 (simulated)")
        print("-" * 60)

        # Run 3 mock sessions
        for i in range(1, 4):
            session = self.simulate_session(i)
            self.sessions.append(session)

            # Save session report
            session_file = Path(
                f"reports/mock_session_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            session_file.parent.mkdir(exist_ok=True)
            with open(session_file, "w") as f:
                json.dump(session, f, indent=2)

            print(f"Session report saved: {session_file}")

            if i < 3:
                print("\nCooldown: 2 seconds...")
                time.sleep(2)

        # Generate summary
        self.generate_summary()

        print("\n" + "=" * 60)
        print(" MOCK CAMPAIGN COMPLETE")
        print("=" * 60)

    def generate_summary(self):
        """Generate campaign summary"""
        total_passes = sum(1 for s in self.sessions if s["status"] == "PASS")

        # Calculate A/B test results
        fast_session = next((s for s in self.sessions if s["prefer_fastest"]), None)
        normal_sessions = [s for s in self.sessions if not s["prefer_fastest"]]

        ab_results = {}
        if fast_session and normal_sessions:
            fast_latency = fast_session["metrics"]["latency"]["p50"]
            normal_latency = sum(s["metrics"]["latency"]["p50"] for s in normal_sessions) / len(
                normal_sessions
            )
            diff_pct = (
                ((normal_latency - fast_latency) / normal_latency) * 100
                if normal_latency > 0
                else 0
            )
            ab_results = {
                "latency_improvement_pct": diff_pct,
                "fast_p50": fast_latency,
                "normal_p50": normal_latency,
                "winner": "fast" if diff_pct > 10 else "normal",
            }

        # Save JSON report
        report_data = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "mode": "MOCK",
            "sessions": self.sessions,
            "ab_test": ab_results,
            "summary": {"total_passes": total_passes, "all_passed": total_passes == 3},
        }

        json_file = Path("reports/mock_quick_campaign.json")
        json_file.parent.mkdir(exist_ok=True)
        with open(json_file, "w") as f:
            json.dump(report_data, f, indent=2)

        # Generate markdown report
        report = []
        report.append("# MOCK 24-Hour Proof Sprint Report")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("**Mode**: MOCK (Simulated Results)")
        report.append(
            f"**Duration**: {(datetime.now() - self.start_time).total_seconds():.1f} seconds"
        )
        report.append(f"**Sessions**: {len(self.sessions)}")
        report.append(f"**PASS Rate**: {total_passes}/{len(self.sessions)}")
        report.append("")

        # Session Summary Table
        report.append("## Session Summary")
        report.append("")
        report.append(
            "| Session | Status | Passes | TL P&L | Fill Rate | Latency p50 | Shadow avg | Route |"
        )
        report.append(
            "|---------|--------|--------|---------|-----------|-------------|------------|-------|"
        )

        for i, session in enumerate(self.sessions, 1):
            m = session["metrics"]
            status_icon = "✅" if session["status"] == "PASS" else "❌"
            total_pnl = m["grid"]["tl_pnl"] + m["arbitrage"]["pnl_tl"]
            route_mode = "FAST" if session.get("prefer_fastest") else "NORMAL"

            report.append(
                f"| {i} | {status_icon} | {session['passes']}/10 | "
                f"{total_pnl:.2f} | "
                f"{m['grid']['maker_fill_rate']:.1f}% | "
                f"{m['latency']['p50']}ms | "
                f"{m['qa']['shadow_avg_diff_bps']:.1f} bps | "
                f"{route_mode} |"
            )

        # A/B Test Results
        if ab_results:
            report.append("")
            report.append("## A/B Route Test Results")
            report.append("")
            report.append(
                f"- **Latency Improvement**: {ab_results['latency_improvement_pct']:.1f}%"
            )
            report.append(f"- **Fast Mode p50**: {ab_results['fast_p50']:.0f}ms")
            report.append(f"- **Normal Mode p50**: {ab_results['normal_p50']:.0f}ms")
            report.append(f"- **Winner**: {ab_results['winner'].upper()}")

        # Overall Assessment
        report.append("")
        report.append("## Overall Assessment")
        report.append("")
        if total_passes == 3:
            report.append("### 🎯 READY FOR LIVE (MOCK)")
            report.append("All 3 sessions passed criteria in simulation.")
        elif total_passes >= 2:
            report.append("### ⚠️ MARGINAL (MOCK)")
            report.append(f"Only {total_passes}/3 sessions passed in simulation.")
        else:
            report.append("### ❌ NOT READY (MOCK)")
            report.append(f"Only {total_passes}/3 sessions passed in simulation.")

        report.append("")
        report.append("---")
        report.append("*Generated by run_quick_campaign_mock.py - SIMULATED RESULTS*")

        # Write report
        report_content = "\n".join(report)
        report_file = Path("reports/mock_quick_campaign.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"\nSummary report: {report_file}")
        print(f"JSON report: {json_file}")
        print("\n" + report_content)


def main():
    """Run the mock campaign"""
    campaign = MockQuickCampaign()
    campaign.run_campaign()

    # Check results
    total_passes = sum(1 for s in campaign.sessions if s["status"] == "PASS")
    sys.exit(0 if total_passes == 3 else 1)


if __name__ == "__main__":
    main()
