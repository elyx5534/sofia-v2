"""
Pilot Preparation Report
48-72 hour readiness plan with score targets
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))


class PilotPlanGenerator:
    """Generate and track pilot preparation plan"""

    def __init__(self):
        self.plan_hours = 72
        self.target_scores = {
            "paper_trades": 500,
            "fill_rate": 60,
            "shadow_diff": 5,
            "consistency": 95,
            "max_drawdown": 10,
            "readiness": 80,
        }

    def check_current_status(self) -> Dict:
        """Check current system status"""
        status = {
            "paper_trades": 0,
            "fill_rate": 0,
            "shadow_diff": 0,
            "consistency": 0,
            "max_drawdown": 0,
            "readiness": 0,
        }

        # Check paper trades
        report_file = Path("logs/paper_session_report.json")
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
                status["paper_trades"] = report.get("session", {}).get("trades_executed", 0)
                status["fill_rate"] = report.get("fill_metrics", {}).get("maker_fill_rate", 0)

        # Check shadow diff
        shadow_file = Path("logs/shadow_diff.jsonl")
        if shadow_file.exists():
            diffs = []
            with open(shadow_file) as f:
                for line in f:
                    try:
                        diff = json.loads(line)
                        diffs.append(diff.get("price_diff_bps", 0))
                    except:
                        continue
            if diffs:
                status["shadow_diff"] = sum(diffs) / len(diffs)

        # Run consistency check
        try:
            from tools.consistency_check import ConsistencyChecker

            checker = ConsistencyChecker()
            passed, report = checker.check_all_sources()
            if report["overall"] == "PASS":
                status["consistency"] = 95
            elif report["overall"] == "WARN":
                status["consistency"] = 80
            else:
                status["consistency"] = 50
        except:
            pass

        # Check readiness
        try:
            from tools.live_readiness import LiveReadinessChecker

            checker = LiveReadinessChecker()
            checker.run()
            status["readiness"] = checker.readiness_score
        except:
            pass

        return status

    def generate_hour_plan(self) -> List[Dict]:
        """Generate hour-by-hour plan"""
        plan = []
        current_time = datetime.now()

        # Hour 0-12: Setup and initial testing
        for hour in range(0, 12):
            time_slot = current_time + timedelta(hours=hour)

            if hour == 0:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "System setup and configuration check",
                    "commands": [
                        "python tools/consistency_check.py",
                        "python tools/live_readiness.py",
                    ],
                    "targets": {"consistency": "PASS", "readiness": "> 30"},
                }
            elif hour in [2, 4, 6, 8, 10]:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": f"Paper trading session #{hour//2}",
                    "commands": ["python run_paper_session.py 60"],
                    "targets": {"trades": "> 20", "fill_rate": "> 50%"},
                }
            else:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "QA and metrics review",
                    "commands": ["python tools/qa_proof.py"],
                    "targets": {"shadow_diff": "< 10 bps"},
                }

            plan.append(task)

        # Hour 12-24: Intensive paper trading
        for hour in range(12, 24):
            time_slot = current_time + timedelta(hours=hour)

            if hour % 2 == 0:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": f"Extended paper session #{(hour-12)//2 + 6}",
                    "commands": ["python run_paper_session.py 90"],
                    "targets": {"trades": "> 30", "fill_rate": "> 55%"},
                }
            else:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "Parameter tuning",
                    "commands": ["python tools/apply_adaptive_params.py"],
                    "targets": {"adjustment": "optimal"},
                }

            plan.append(task)

        # Hour 24-48: Turkish arbitrage and grid trading
        for hour in range(24, 48):
            time_slot = current_time + timedelta(hours=hour)

            if hour % 4 == 0:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": f"Turkish arbitrage session #{(hour-24)//4 + 1}",
                    "commands": ["python tools/run_tr_arbitrage_session.py 30"],
                    "targets": {"opportunities": "> 5", "success_rate": "> 70%"},
                }
            elif hour % 4 == 2:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": f"Grid trading session #{(hour-24)//4 + 1}",
                    "commands": ["python run_paper_session.py 120"],
                    "targets": {"trades": "> 40", "pnl": "positive"},
                }
            else:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "Performance review",
                    "commands": [
                        "python tools/session_orchestrator.py --grid-mins 60 --arb-mins 30"
                    ],
                    "targets": {"daily_score": "generated"},
                }

            plan.append(task)

        # Hour 48-72: Final preparation and validation
        for hour in range(48, 72):
            time_slot = current_time + timedelta(hours=hour)

            if hour == 48:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "Full system validation",
                    "commands": [
                        "python tools/live_readiness.py",
                        "python tools/consistency_check.py",
                    ],
                    "targets": {"readiness": "> 70", "consistency": "PASS"},
                }
            elif hour < 60:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": f"Final paper session #{hour-48}",
                    "commands": ["python run_paper_session.py 60"],
                    "targets": {"fill_rate": "> 60%", "shadow_diff": "< 5 bps"},
                }
            elif hour == 70:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "Live pilot decision",
                    "commands": ["python tools/pilot_decision.py"],
                    "targets": {"decision": "GO/NO-GO", "confidence": "> 80%"},
                }
            elif hour == 71:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "Live environment setup",
                    "commands": ['echo "Configure live API keys"', 'echo "Set pilot limits"'],
                    "targets": {"api_keys": "configured", "limits": "set"},
                }
            else:
                task = {
                    "hour": hour,
                    "time": time_slot.strftime("%H:%M"),
                    "task": "System monitoring",
                    "commands": ["python tools/qa_proof.py"],
                    "targets": {"status": "ready"},
                }

            plan.append(task)

        return plan

    def calculate_milestones(self) -> List[Dict]:
        """Calculate key milestones"""
        milestones = [
            {
                "hour": 12,
                "name": "Initial Setup Complete",
                "criteria": {"paper_trades": 100, "consistency": "PASS", "readiness": 40},
            },
            {
                "hour": 24,
                "name": "Paper Trading Validated",
                "criteria": {"paper_trades": 200, "fill_rate": 55, "shadow_diff": 8},
            },
            {
                "hour": 48,
                "name": "Arbitrage Tested",
                "criteria": {
                    "paper_trades": 400,
                    "arb_sessions": 6,
                    "grid_sessions": 6,
                    "readiness": 70,
                },
            },
            {
                "hour": 60,
                "name": "Target Metrics Met",
                "criteria": {
                    "paper_trades": 500,
                    "fill_rate": 60,
                    "shadow_diff": 5,
                    "consistency": 95,
                },
            },
            {
                "hour": 72,
                "name": "Live Pilot Ready",
                "criteria": {"readiness": 80, "all_checks": "PASS", "confidence": 85},
            },
        ]

        return milestones

    def generate_checklist(self) -> Dict:
        """Generate pre-pilot checklist"""
        checklist = {
            "infrastructure": [
                {"item": "API keys configured", "status": "pending"},
                {"item": "Network latency < 50ms", "status": "pending"},
                {"item": "Error logging enabled", "status": "pending"},
                {"item": "Monitoring dashboard ready", "status": "pending"},
            ],
            "risk_controls": [
                {"item": "Kill switch tested", "status": "pending"},
                {"item": "Position limits set", "status": "pending"},
                {"item": "Max drawdown configured", "status": "pending"},
                {"item": "Alert system active", "status": "pending"},
            ],
            "performance": [
                {"item": "Fill rate > 60%", "status": "pending"},
                {"item": "Shadow diff < 5 bps", "status": "pending"},
                {"item": "P&L consistency > 95%", "status": "pending"},
                {"item": "Max drawdown < 10%", "status": "pending"},
            ],
            "documentation": [
                {"item": "Runbook created", "status": "pending"},
                {"item": "Rollback plan ready", "status": "pending"},
                {"item": "Emergency contacts listed", "status": "pending"},
                {"item": "Incident response plan", "status": "pending"},
            ],
        }

        return checklist

    def generate_report(self) -> Dict:
        """Generate complete pilot preparation report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "plan_duration_hours": self.plan_hours,
            "current_status": self.check_current_status(),
            "target_scores": self.target_scores,
            "hour_plan": self.generate_hour_plan(),
            "milestones": self.calculate_milestones(),
            "checklist": self.generate_checklist(),
        }

        # Calculate readiness percentage
        current = report["current_status"]
        targets = self.target_scores

        readiness_items = []
        for metric, target in targets.items():
            current_val = current.get(metric, 0)
            if metric in ["max_drawdown"]:
                # Lower is better
                score = 100 if current_val <= target else (target / current_val) * 100
            else:
                # Higher is better
                score = min(100, (current_val / target) * 100) if target > 0 else 0

            readiness_items.append(
                {"metric": metric, "current": current_val, "target": target, "score": score}
            )

        overall_readiness = sum(item["score"] for item in readiness_items) / len(readiness_items)

        report["readiness_summary"] = {
            "items": readiness_items,
            "overall_score": overall_readiness,
            "status": "READY" if overall_readiness >= 80 else "NOT READY",
        }

        return report

    def save_report(self, report: Dict):
        """Save report to file"""
        report_file = Path("reports/pilot_plan.json")
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        # Also save markdown version
        self.save_markdown_report(report)

    def save_markdown_report(self, report: Dict):
        """Save report as markdown"""
        md_file = Path("reports/PILOT_PLAN.md")

        with open(md_file, "w") as f:
            f.write("# Live Pilot Preparation Plan\n\n")
            f.write(f"Generated: {report['timestamp']}\n")
            f.write(f"Duration: {report['plan_duration_hours']} hours\n\n")

            # Current Status
            f.write("## Current Status\n\n")
            f.write("| Metric | Current | Target | Status |\n")
            f.write("|--------|---------|--------|--------|\n")

            for item in report["readiness_summary"]["items"]:
                status = "[OK]" if item["score"] >= 80 else "[NEEDS WORK]"
                f.write(
                    f"| {item['metric']} | {item['current']:.1f} | {item['target']} | {status} |\n"
                )

            f.write(
                f"\n**Overall Readiness: {report['readiness_summary']['overall_score']:.1f}%**\n\n"
            )

            # Milestones
            f.write("## Key Milestones\n\n")
            for milestone in report["milestones"]:
                f.write(f"### Hour {milestone['hour']}: {milestone['name']}\n")
                for key, value in milestone["criteria"].items():
                    f.write(f"- {key}: {value}\n")
                f.write("\n")

            # Checklist
            f.write("## Pre-Pilot Checklist\n\n")
            for category, items in report["checklist"].items():
                f.write(f"### {category.replace('_', ' ').title()}\n")
                for item in items:
                    check = "[ ]" if item["status"] == "pending" else "[x]"
                    f.write(f"- {check} {item['item']}\n")
                f.write("\n")

            # Commands
            f.write("## Quick Commands\n\n")
            f.write("```bash\n")
            f.write("# Start paper trading\n")
            f.write("python run_paper_session.py 60\n\n")
            f.write("# Run Turkish arbitrage\n")
            f.write("python tools/run_tr_arbitrage_session.py 30\n\n")
            f.write("# Check readiness\n")
            f.write("python tools/live_readiness.py\n\n")
            f.write("# Daily validation\n")
            f.write("python tools/session_orchestrator.py\n")
            f.write("```\n")

    def print_summary(self, report: Dict):
        """Print report summary"""
        print("=" * 70)
        print(" PILOT PREPARATION REPORT")
        print("=" * 70)
        print(f"Duration: {report['plan_duration_hours']} hours")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("-" * 70)

        print("\nCURRENT STATUS:")
        for item in report["readiness_summary"]["items"]:
            status = "[OK]" if item["score"] >= 80 else "[NEEDS WORK]"
            print(f"  {item['metric']:15} {item['current']:6.1f} / {item['target']:6} {status}")

        print(f"\nOVERALL READINESS: {report['readiness_summary']['overall_score']:.1f}%")
        print(f"STATUS: {report['readiness_summary']['status']}")

        print("\nKEY MILESTONES:")
        for milestone in report["milestones"]:
            print(f"  Hour {milestone['hour']:2}: {milestone['name']}")

        print("\nNEXT STEPS:")
        if report["readiness_summary"]["overall_score"] < 30:
            print("  1. Complete initial setup and configuration")
            print("  2. Run first paper trading sessions")
            print("  3. Verify consistency checks pass")
        elif report["readiness_summary"]["overall_score"] < 60:
            print("  1. Continue paper trading to reach 500 trades")
            print("  2. Tune parameters for better fill rate")
            print("  3. Reduce shadow diff below 5 bps")
        elif report["readiness_summary"]["overall_score"] < 80:
            print("  1. Final parameter optimization")
            print("  2. Complete all checklist items")
            print("  3. Run final validation")
        else:
            print("  1. System ready for live pilot")
            print("  2. Configure live API keys")
            print("  3. Set conservative limits and begin pilot")

        print("\nREPORT SAVED TO:")
        print("  - reports/pilot_plan.json")
        print("  - reports/PILOT_PLAN.md")
        print("=" * 70)


def main():
    generator = PilotPlanGenerator()
    report = generator.generate_report()
    generator.save_report(report)
    generator.print_summary(report)


if __name__ == "__main__":
    main()
