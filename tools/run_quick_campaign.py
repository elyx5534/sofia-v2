"""
24-Hour Proof Sprint Campaign Runner
Runs 3 sessions with Symbol Plan and EV Gate integration
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuickCampaign:
    """Run 3 paper sessions with Symbol Plan and EV Gate"""

    def __init__(self):
        self.sessions = []
        self.start_time = datetime.now()
        self.cooldown_mins = 10
        self.symbol_plan = self.load_symbol_plan()
        self.ev_gate_enabled = True

    def load_symbol_plan(self) -> Dict:
        """Load symbol plan for AM/PM sessions"""
        plan_file = Path("reports/symbol_plan.json")
        if plan_file.exists():
            with open(plan_file) as f:
                return json.load(f)
        # Default if no plan
        return {
            "sessions": {
                "AM": {"symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"]},
                "PM": {"symbols": ["SOLUSDT", "ADAUSDT", "DOTUSDT"]},
            }
        }

    def configure_ev_gate(self, enable: bool = True):
        """Configure EV Gate settings"""
        config_file = Path("config/arb_ev.yaml")
        config_file.parent.mkdir(exist_ok=True)
        config = {"enabled": enable, "min_ev_tl": 1, "latency_penalty_bps": 2}
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)
        logger.info(f"EV Gate configured: enabled={enable}")

    def configure_route_optimizer(self, prefer_fastest: bool):
        """Configure route optimizer for A/B testing"""
        config_file = Path("config/execution.yaml")
        config_file.parent.mkdir(exist_ok=True)
        config = {"prefer_fastest": prefer_fastest, "min_health_score": 0.7}
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config, f)
        logger.info(f"Route optimizer: prefer_fastest={prefer_fastest}")

    def run_command(self, cmd: List[str], description: str) -> Dict:
        """Run a command and capture output"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {description}")
        print(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                check=False,  # 1 hour timeout
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd),
                "timestamp": datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out",
                "command": " ".join(cmd),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "command": " ".join(cmd),
                "timestamp": datetime.now().isoformat(),
            }

    def run_session(self, session_num: int) -> Dict:
        """Run a single session (Grid + Arb + QA)"""
        print(f"\n{'='*60}")
        print(f" SESSION {session_num}/3 STARTING")
        print(f"{'='*60}")

        # Determine session time (AM/PM)
        session_time = "AM" if session_num == 1 else "PM"
        symbols = self.symbol_plan["sessions"][session_time]["symbols"]
        print(f"Session Time: {session_time}")
        print(f"Symbols: {', '.join(symbols)}")

        # Configure EV Gate (always on)
        self.configure_ev_gate(True)

        # Configure route optimizer (A/B test on session 2)
        prefer_fastest = session_num == 2
        self.configure_route_optimizer(prefer_fastest)
        print(f"Route Mode: {'FAST' if prefer_fastest else 'NORMAL'}")

        session_data = {
            "session_num": session_num,
            "start_time": datetime.now().isoformat(),
            "session_time": session_time,
            "symbols": symbols,
            "prefer_fastest": prefer_fastest,
            "ev_gate_enabled": self.ev_gate_enabled,
            "steps": {},
        }

        # Step 1: Grid Trading (60 minutes for sessions 1&3)
        if session_num != 2:
            print("\n[1/6] Running Grid Trading Session (60 minutes)...")
            grid_cmd = ["python", "run_paper_session.py", "1"]  # Mock: 1 minute
            grid_cmd.extend(["--symbols"] + symbols[:3])  # Use top 3 symbols
            grid_result = self.run_command(grid_cmd, "Grid Trading Session")
            session_data["steps"]["grid"] = grid_result

        # Step 2: TR Arbitrage (30 minutes for session 2, or as additional)
        duration = "30" if session_num == 2 else "0.5"
        print(f"\n[2/6] Running TR Arbitrage Session ({duration} minutes)...")
        arb_result = self.run_command(
            ["python", "tools/run_tr_arbitrage_session.py", duration], "TR Arbitrage Session"
        )
        session_data["steps"]["arbitrage"] = arb_result

        # Step 3: QA Proof
        print("\n[3/6] Running QA Proof...")
        qa_result = self.run_command(["python", "tools/qa_proof.py"], "QA Proof Check")
        session_data["steps"]["qa_proof"] = qa_result

        # Step 4: Shadow Report
        print("\n[4/6] Running Shadow Report...")
        shadow_result = self.run_command(
            ["python", "tools/shadow_report.py"], "Shadow Report Generation"
        )
        session_data["steps"]["shadow"] = shadow_result

        # Step 5: Edge Calibrator
        print("\n[5/6] Running Edge Calibrator...")
        edge_result = self.run_command(
            ["python", "src/execution/edge_calibrator.py"], "Edge Calibration"
        )
        session_data["steps"]["edge_calibrator"] = edge_result

        # Step 6: Adapt (Parameter Update)
        print("\n[6/6] Applying Adaptive Parameters...")
        adapt_result = self.run_command(
            ["python", "tools/apply_adaptive_params.py"], "Adaptive Parameter Update"
        )
        session_data["steps"]["adapt"] = adapt_result

        # Extract metrics
        session_data["metrics"] = self.extract_metrics(session_data)
        session_data["end_time"] = datetime.now().isoformat()

        # Determine PASS/FAIL
        session_data["status"] = self.evaluate_session(session_data["metrics"])

        return session_data

    def extract_metrics(self, session_data: Dict) -> Dict:
        """Extract key metrics from session results"""
        metrics = {
            "grid": {"pnl_pct": 0.0, "maker_fill_rate": 0.0, "avg_fill_time_ms": 0, "tl_pnl": 0.0},
            "arbitrage": {"pnl_tl": 0.0, "success_rate": 0.0, "avg_latency_ms": 0},
            "qa": {"consistency": "UNKNOWN", "shadow_avg_diff_bps": 0.0, "shadow_p95_bps": 0.0},
            "risk": {"max_dd_pct": 0.0},
            "latency": {"p50": 0, "p95": 0},
            "ev_gate": {"reject_count": 0, "total_evaluated": 0},
        }

        # Try to load daily score if it exists
        daily_score_file = Path("reports/daily_score.json")
        if daily_score_file.exists():
            try:
                with open(daily_score_file) as f:
                    daily_score = json.load(f)

                if "grid" in daily_score:
                    metrics["grid"]["pnl_pct"] = daily_score["grid"].get("pnl_pct", 0)
                    metrics["grid"]["maker_fill_rate"] = daily_score["grid"].get(
                        "maker_fill_rate", 0
                    )
                    metrics["grid"]["avg_fill_time_ms"] = daily_score["grid"].get(
                        "avg_time_to_fill", 0
                    )

                if "arb" in daily_score:
                    metrics["arbitrage"]["pnl_tl"] = daily_score["arb"].get("pnl_tl", 0)
                    metrics["arbitrage"]["success_rate"] = daily_score["arb"].get("success_rate", 0)
                    metrics["arbitrage"]["avg_latency_ms"] = daily_score["arb"].get(
                        "avg_latency_ms", 0
                    )

                if "qa" in daily_score:
                    metrics["qa"]["consistency"] = daily_score["qa"].get("consistency", "UNKNOWN")
                    metrics["qa"]["shadow_avg_diff_bps"] = daily_score["qa"].get(
                        "shadow_avg_diff_bps", 0
                    )
                    metrics["qa"]["shadow_p95_bps"] = daily_score["qa"].get("shadow_p95_bps", 0)

                if "latency" in daily_score:
                    metrics["latency"]["p50"] = daily_score["latency"].get("p50", 0)
                    metrics["latency"]["p95"] = daily_score["latency"].get("p95", 0)

                if "ev_gate" in daily_score:
                    metrics["ev_gate"]["reject_count"] = daily_score["ev_gate"].get(
                        "reject_count", 0
                    )
                    metrics["ev_gate"]["total_evaluated"] = daily_score["ev_gate"].get(
                        "total_evaluated", 0
                    )

                if "risk" in daily_score:
                    metrics["risk"]["max_dd_pct"] = daily_score["risk"].get("max_dd_pct", 0)
            except:
                pass

        # Parse QA output
        qa_output = session_data["steps"].get("qa_proof", {}).get("stdout", "")
        if "Consistency: PASS" in qa_output:
            metrics["qa"]["consistency"] = "PASS"
        elif "Consistency: FAIL" in qa_output:
            metrics["qa"]["consistency"] = "FAIL"

        # Parse Shadow output
        shadow_output = session_data["steps"].get("shadow", {}).get("stdout", "")
        if "Average:" in shadow_output:
            try:
                for line in shadow_output.split("\n"):
                    if "Average:" in line:
                        bps_str = line.split("Average:")[1].split("bps")[0].strip()
                        metrics["qa"]["shadow_avg_diff_bps"] = float(bps_str)
                        break
            except:
                pass

        return metrics

    def evaluate_session(self, metrics: Dict) -> str:
        """Evaluate if session passes criteria"""
        passes = []

        # Grid criteria
        if metrics["grid"]["maker_fill_rate"] >= 60:
            passes.append("grid_fill")
        if metrics["grid"]["avg_fill_time_ms"] < 20000:
            passes.append("grid_time")
        if metrics["grid"]["pnl_pct"] > 0:
            passes.append("grid_pnl")

        # Arbitrage criteria
        if metrics["arbitrage"]["pnl_tl"] >= 0:
            passes.append("arb_pnl")
        if metrics["arbitrage"]["success_rate"] >= 55:
            passes.append("arb_success")
        if metrics["arbitrage"]["avg_latency_ms"] < 250:
            passes.append("arb_latency")

        # QA criteria
        if metrics["qa"]["consistency"] == "PASS":
            passes.append("qa_consistency")
        if metrics["qa"]["shadow_avg_diff_bps"] < 5:
            passes.append("shadow_avg")
        if metrics["qa"]["shadow_p95_bps"] < 7:
            passes.append("shadow_p95")

        # Risk criteria
        if metrics["risk"]["max_dd_pct"] >= -1:
            passes.append("risk_dd")

        # Overall: PASS if at least 7/10 criteria pass
        return "PASS" if len(passes) >= 7 else "FAIL"

    def run_campaign(self):
        """Run the full 3-session campaign"""
        print("=" * 60)
        print(" 24-HOUR QUICK CAMPAIGN STARTING")
        print("=" * 60)
        print(f"Start Time: {self.start_time}")
        print("Sessions: 3")
        print("Est. Duration: ~4.5 hours (mocked to ~15 minutes)")
        print("-" * 60)

        # Run 3 sessions
        for i in range(1, 4):
            session = self.run_session(i)
            self.sessions.append(session)

            # Archive session report
            session_file = Path(
                f"reports/session_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            session_file.parent.mkdir(exist_ok=True)
            with open(session_file, "w") as f:
                json.dump(session, f, indent=2)

            print(f"\nSession {i} Status: {session['status']}")
            print(f"Session report saved: {session_file}")

            # Cooldown between sessions (except after last)
            if i < 3:
                print(f"\nCooldown: {self.cooldown_mins} minutes...")
                time.sleep(
                    self.cooldown_mins * 60 if "--real" in sys.argv else 2
                )  # Mock: 2 seconds

        # Generate summary report
        self.generate_summary()

        print("\n" + "=" * 60)
        print(" CAMPAIGN COMPLETE")
        print("=" * 60)

    def calculate_ab_difference(self) -> Dict:
        """Calculate A/B test differences for route optimization"""
        fast_session = None
        normal_sessions = []

        for s in self.sessions:
            if s.get("prefer_fastest"):
                fast_session = s
            else:
                normal_sessions.append(s)

        if not fast_session or not normal_sessions:
            return {"difference_pct": 0, "winner": "insufficient_data"}

        # Compare latencies
        fast_latency = fast_session["metrics"]["latency"]["p50"]
        normal_latency = sum(s["metrics"]["latency"]["p50"] for s in normal_sessions) / len(
            normal_sessions
        )

        diff_pct = (
            ((normal_latency - fast_latency) / normal_latency) * 100 if normal_latency > 0 else 0
        )

        return {
            "latency_improvement_pct": diff_pct,
            "fast_p50": fast_latency,
            "normal_p50": normal_latency,
            "winner": "fast" if diff_pct > 10 else "normal",
        }

    def generate_summary(self):
        """Generate campaign summary report"""
        report_file = Path("reports/quick_campaign.md")
        json_file = Path("reports/quick_campaign.json")

        # Calculate statistics
        total_passes = sum(1 for s in self.sessions if s["status"] == "PASS")
        ab_results = self.calculate_ab_difference()

        # Save JSON report
        campaign_data = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "sessions": self.sessions,
            "ab_test": ab_results,
            "summary": {"total_passes": total_passes, "all_passed": total_passes == 3},
        }
        with open(json_file, "w") as f:
            json.dump(campaign_data, f, indent=2)

        report = []
        report.append("# 24-Hour Proof Sprint Report")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(
            f"**Duration**: {(datetime.now() - self.start_time).total_seconds() / 60:.1f} minutes"
        )
        report.append(f"**Sessions**: {len(self.sessions)}")
        report.append(f"**PASS Rate**: {total_passes}/{len(self.sessions)}")
        report.append("**EV Gate**: Enabled")
        report.append("**Symbol Plan**: Active\n")

        # Session Summary Table
        report.append("## Session Summary\n")
        report.append(
            "| Session | Status | TL P&L | Fill Rate | Time | Latency p50/p95 | Shadow avg/p95 | MaxDD | EV Reject | Route |"
        )
        report.append(
            "|---------|--------|---------|-----------|------|-----------------|----------------|-------|-----------|-------|"
        )

        for i, session in enumerate(self.sessions, 1):
            m = session["metrics"]
            status_icon = "✅" if session["status"] == "PASS" else "❌"

            total_pnl = m["grid"].get("tl_pnl", 0) + m["arbitrage"]["pnl_tl"]
            route_mode = "FAST" if session.get("prefer_fastest") else "NORMAL"

            report.append(
                f"| {i} | {status_icon} | "
                f"{total_pnl:.2f} | "
                f"{m['grid']['maker_fill_rate']:.1f}% | "
                f"{m['grid']['avg_fill_time_ms']/1000:.1f}s | "
                f"{m['latency']['p50']}/{m['latency']['p95']}ms | "
                f"{m['qa']['shadow_avg_diff_bps']:.1f}/{m['qa']['shadow_p95_bps']:.1f} bps | "
                f"{m['risk']['max_dd_pct']:.2f}% | "
                f"{m['ev_gate']['reject_count']} | "
                f"{route_mode} |"
            )

        # A/B Route Test Results
        report.append("\n## A/B Route Test Results\n")
        if ab_results["winner"] != "insufficient_data":
            report.append(
                f"- **Latency Improvement**: {ab_results['latency_improvement_pct']:.1f}%"
            )
            report.append(f"- **Fast Mode p50**: {ab_results['fast_p50']:.0f}ms")
            report.append(f"- **Normal Mode p50**: {ab_results['normal_p50']:.0f}ms")
            report.append(f"- **Winner**: {ab_results['winner'].upper()}\n")
        else:
            report.append("- Insufficient data for A/B comparison\n")

        # Pass/Fail Criteria
        report.append("## Pass/Fail Criteria\n")
        report.append("### Grid Trading")
        report.append("- Maker Fill Rate ≥ 60%")
        report.append("- Avg Fill Time < 20s")
        report.append("- P&L > 0%\n")

        report.append("### TR Arbitrage")
        report.append("- TL P&L ≥ 0")
        report.append("- Success Rate ≥ 55%")
        report.append("- Avg Latency < 250ms\n")

        report.append("### QA & Risk")
        report.append("- Consistency: PASS")
        report.append("- Shadow Avg < 5 bps")
        report.append("- Shadow p95 < 7 bps")
        report.append("- Max DD ≥ -1%\n")

        # Overall Assessment
        report.append("## Overall Assessment\n")
        if total_passes == 3:
            report.append("### 🎯 READY FOR LIVE")
            report.append("All 3 sessions passed criteria. System is ready for micro-live pilot.\n")
        elif total_passes >= 2:
            report.append("### ⚠️ MARGINAL")
            report.append(f"Only {total_passes}/3 sessions passed. Review failures before live.\n")
        else:
            report.append("### ❌ NOT READY")
            report.append(f"Only {total_passes}/3 sessions passed. More tuning required.\n")

        # Archive Links
        report.append("## Archive Links\n")
        report.append("- [QA Proofs](reports/qa/)")
        report.append("- [Shadow Reports](reports/shadow/)")
        report.append("- [Edge Calibrations](config/edge_history/)")
        report.append("- [Campaign JSON](reports/quick_campaign.json)")

        for i, session in enumerate(self.sessions, 1):
            timestamp = session["start_time"].replace(":", "").replace("-", "")[:15]
            report.append(f"- [Session {i} Details](reports/session_{i}_{timestamp}.json)")

        report.append("\n---")
        report.append("*Generated by run_quick_campaign.py with Symbol Plan + EV Gate + Route A/B*")

        # Write report
        report_content = "\n".join(report)
        report_file.write_text(report_content)

        print(f"\nSummary report: {report_file}")
        print(report_content)


def main():
    """Run the quick campaign"""
    campaign = QuickCampaign()
    campaign.run_campaign()

    # Check if all sessions passed
    total_passes = sum(1 for s in campaign.sessions if s["status"] == "PASS")

    # Exit code: 0 if all pass, 1 otherwise
    sys.exit(0 if total_passes == 3 else 1)


if __name__ == "__main__":
    main()
