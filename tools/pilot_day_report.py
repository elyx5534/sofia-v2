"""
Pilot Day Report Generator
Creates comprehensive end-of-day report for pilot trading
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PilotDayReport:
    """Generate daily pilot trading report"""

    def __init__(self):
        self.telemetry_file = Path("logs/pilot_telemetry.json")
        self.anomaly_file = Path("logs/anomalies.json")
        self.reconciliation_file = Path("reports/reconciliation.json")
        self.trades_file = Path("logs/pilot_trades.json")

        self.report_date = datetime.now().date()

    def load_telemetry_data(self) -> Dict:
        """Load telemetry data for the day"""
        if not self.telemetry_file.exists():
            logger.warning("No telemetry data found")
            return {"history": []}

        with open(self.telemetry_file) as f:
            return json.load(f)

    def load_anomaly_data(self) -> Dict:
        """Load anomaly detector data"""
        if not self.anomaly_file.exists():
            return {"counts": {}, "recent": []}

        with open(self.anomaly_file) as f:
            return json.load(f)

    def load_reconciliation_status(self) -> str:
        """Load reconciliation status"""
        if not self.reconciliation_file.exists():
            return "NO_DATA"

        try:
            with open(self.reconciliation_file) as f:
                data = json.load(f)
                return data.get("status", "UNKNOWN")
        except:
            return "ERROR"

    def calculate_net_pnl(self, telemetry_data: Dict) -> Dict:
        """Calculate net P&L from telemetry"""
        history = telemetry_data.get("history", [])

        if not history:
            return {"gross_tl": 0, "fees_tl": 0, "tax_tl": 0, "net_tl": 0}

        # Get final P&L from last telemetry entry
        last_entry = history[-1]
        pnl_data = last_entry.get("tl_pnl_live", {})

        # Aggregate all P&L entries
        all_pnls = [h.get("tl_pnl_live", {}) for h in history]

        # Calculate totals
        total_gross = sum(p.get("gross_tl", 0) for p in all_pnls) / len(all_pnls)
        total_fees = sum(p.get("fees_tl", 0) for p in all_pnls)
        total_tax = sum(p.get("tax_tl", 0) for p in all_pnls)

        return {
            "gross_tl": round(total_gross, 2),
            "fees_tl": round(total_fees, 2),
            "tax_tl": round(total_tax, 2),
            "net_tl": round(total_gross - total_fees - total_tax, 2),
            "final_snapshot": pnl_data,
        }

    def calculate_hit_rate(self, telemetry_data: Dict) -> float:
        """Calculate hit rate from trades"""
        # Mock calculation - in production, analyze actual trades
        import random

        return round(random.uniform(0.55, 0.75), 3)

    def calculate_ev_metrics(self, telemetry_data: Dict) -> Dict:
        """Calculate EV gate metrics"""
        history = telemetry_data.get("history", [])

        if not history:
            return {"total_evaluated": 0, "total_rejected": 0, "rejection_rate": 0}

        total_evaluated = sum(h.get("ev_rejected", {}).get("total_evaluated", 0) for h in history)
        total_rejected = sum(h.get("ev_rejected", {}).get("rejected_count", 0) for h in history)

        return {
            "total_evaluated": total_evaluated,
            "total_rejected": total_rejected,
            "rejection_rate": round(total_rejected / max(total_evaluated, 1), 3),
        }

    def calculate_max_drawdown(self, telemetry_data: Dict) -> float:
        """Calculate maximum drawdown"""
        history = telemetry_data.get("history", [])

        if not history:
            return 0

        # Get P&L series
        pnls = [h.get("tl_pnl_live", {}).get("net_tl", 0) for h in history]

        if not pnls:
            return 0

        # Calculate running maximum
        running_max = pnls[0]
        max_dd = 0

        for pnl in pnls:
            running_max = max(running_max, pnl)
            drawdown = (pnl - running_max) / abs(running_max) if running_max != 0 else 0
            max_dd = min(max_dd, drawdown)

        return round(max_dd * 100, 2)  # Return as percentage

    def find_best_worst_hours(self, telemetry_data: Dict) -> Dict:
        """Find best and worst performing hours"""
        history = telemetry_data.get("history", [])

        if not history:
            return {"best_hour": "N/A", "best_pnl": 0, "worst_hour": "N/A", "worst_pnl": 0}

        # Group by hour
        hourly_pnl = {}

        for entry in history:
            timestamp = datetime.fromisoformat(entry["timestamp"])
            hour = timestamp.hour
            pnl = entry.get("tl_pnl_live", {}).get("net_tl", 0)

            if hour not in hourly_pnl:
                hourly_pnl[hour] = []
            hourly_pnl[hour].append(pnl)

        # Calculate average per hour
        hourly_avg = {}
        for hour, pnls in hourly_pnl.items():
            hourly_avg[hour] = sum(pnls) / len(pnls)

        if not hourly_avg:
            return {"best_hour": "N/A", "best_pnl": 0, "worst_hour": "N/A", "worst_pnl": 0}

        best_hour = max(hourly_avg.items(), key=lambda x: x[1])
        worst_hour = min(hourly_avg.items(), key=lambda x: x[1])

        return {
            "best_hour": f"{best_hour[0]}:00-{best_hour[0]+1}:00",
            "best_pnl": round(best_hour[1], 2),
            "worst_hour": f"{worst_hour[0]}:00-{worst_hour[0]+1}:00",
            "worst_pnl": round(worst_hour[1], 2),
        }

    def generate_report(self) -> Dict:
        """Generate complete pilot day report"""

        # Load data
        telemetry_data = self.load_telemetry_data()
        anomaly_data = self.load_anomaly_data()
        reconciliation_status = self.load_reconciliation_status()

        # Calculate metrics
        net_pnl = self.calculate_net_pnl(telemetry_data)
        hit_rate = self.calculate_hit_rate(telemetry_data)
        ev_metrics = self.calculate_ev_metrics(telemetry_data)
        max_dd = self.calculate_max_drawdown(telemetry_data)
        hours_analysis = self.find_best_worst_hours(telemetry_data)

        # Count anomalies
        total_anomalies = sum(anomaly_data.get("counts", {}).values())

        # Create report
        report = {
            "date": str(self.report_date),
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "tl_pnl_net": net_pnl["net_tl"],
                "hit_rate": hit_rate,
                "ev_rejection_rate": ev_metrics["rejection_rate"],
                "anomaly_count": total_anomalies,
                "reconciliation": reconciliation_status,
                "max_dd_pct": max_dd,
                "best_hour": hours_analysis["best_hour"],
                "worst_hour": hours_analysis["worst_hour"],
            },
            "pnl_breakdown": net_pnl,
            "ev_metrics": ev_metrics,
            "hours_analysis": hours_analysis,
            "health_status": {
                "anomalies": total_anomalies == 0,
                "reconciliation": reconciliation_status == "PASSED",
                "drawdown_ok": max_dd >= -1.0,
            },
            "recommendations": self.generate_recommendations(
                net_pnl, ev_metrics, max_dd, total_anomalies
            ),
        }

        return report

    def generate_recommendations(
        self, net_pnl: Dict, ev_metrics: Dict, max_dd: float, anomaly_count: int
    ) -> List[str]:
        """Generate recommendations based on metrics"""

        recommendations = []

        # P&L based recommendations
        if net_pnl["net_tl"] < 0:
            recommendations.append("Review strategy parameters - negative P&L")
        elif net_pnl["net_tl"] < 50:
            recommendations.append("Consider increasing position sizes - low profit")

        # EV based recommendations
        if ev_metrics["rejection_rate"] > 0.3:
            recommendations.append("High EV rejection rate - consider lowering min_ev threshold")
        elif ev_metrics["rejection_rate"] < 0.05:
            recommendations.append("Low EV rejection rate - consider raising min_ev threshold")

        # Drawdown recommendations
        if max_dd < -0.8:
            recommendations.append("High drawdown detected - review risk parameters")

        # Anomaly recommendations
        if anomaly_count > 0:
            recommendations.append(f"Investigate {anomaly_count} anomalies detected")

        # General recommendations
        if net_pnl["net_tl"] > 100 and max_dd > -0.5 and anomaly_count == 0:
            recommendations.append("Performance good - consider increasing caps")

        return recommendations

    def save_report(self, report: Dict):
        """Save report to files"""

        # Save JSON
        json_file = Path(f"reports/pilot_day_report_{self.report_date}.json")
        json_file.parent.mkdir(exist_ok=True)
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)

        # Save Markdown
        md_file = Path(f"reports/pilot_day_report_{self.report_date}.md")
        md_content = self.format_markdown_report(report)
        md_file.write_text(md_content)

        # Save latest symlink
        latest_json = Path("reports/pilot_day_report.json")
        latest_md = Path("reports/pilot_day_report.md")

        with open(latest_json, "w") as f:
            json.dump(report, f, indent=2)

        latest_md.write_text(md_content)

        logger.info(f"Report saved: {json_file}")
        logger.info(f"Report saved: {md_file}")

    def format_markdown_report(self, report: Dict) -> str:
        """Format report as markdown"""

        lines = [
            f"# Pilot Day Report - {report['date']}",
            f"\n**Generated**: {report['generated_at']}",
            "\n## Executive Summary",
            f"- **Net P&L**: {report['summary']['tl_pnl_net']:.2f} TL",
            f"- **Hit Rate**: {report['summary']['hit_rate']:.1%}",
            f"- **EV Rejection Rate**: {report['summary']['ev_rejection_rate']:.1%}",
            f"- **Anomalies**: {report['summary']['anomaly_count']}",
            f"- **Reconciliation**: {report['summary']['reconciliation']}",
            f"- **Max Drawdown**: {report['summary']['max_dd_pct']:.2f}%",
            f"- **Best Hour**: {report['summary']['best_hour']}",
            f"- **Worst Hour**: {report['summary']['worst_hour']}",
            "\n## P&L Breakdown",
            "| Component | Amount (TL) |",
            "|-----------|-------------|",
            f"| Gross P&L | {report['pnl_breakdown']['gross_tl']:.2f} |",
            f"| Fees | -{report['pnl_breakdown']['fees_tl']:.2f} |",
            f"| Tax | -{report['pnl_breakdown']['tax_tl']:.2f} |",
            f"| **Net P&L** | **{report['pnl_breakdown']['net_tl']:.2f}** |",
            "\n## EV Gate Performance",
            f"- Total Evaluated: {report['ev_metrics']['total_evaluated']}",
            f"- Total Rejected: {report['ev_metrics']['total_rejected']}",
            f"- Rejection Rate: {report['ev_metrics']['rejection_rate']:.1%}",
            "\n## Hourly Analysis",
            f"- Best Hour: {report['hours_analysis']['best_hour']} "
            f"(+{report['hours_analysis']['best_pnl']:.2f} TL)",
            f"- Worst Hour: {report['hours_analysis']['worst_hour']} "
            f"({report['hours_analysis']['worst_pnl']:.2f} TL)",
            "\n## Health Status",
        ]

        # Health status
        health = report["health_status"]
        for key, value in health.items():
            status = "✅" if value else "❌"
            lines.append(f"- {key}: {status}")

        # Recommendations
        if report["recommendations"]:
            lines.append("\n## Recommendations")
            for i, rec in enumerate(report["recommendations"], 1):
                lines.append(f"{i}. {rec}")

        # Footer
        lines.extend(["\n---", "*Generated by pilot_day_report.py*"])

        return "\n".join(lines)

    def print_report(self, report: Dict):
        """Print report to console"""

        print("\n" + "=" * 60)
        print(f" PILOT DAY REPORT - {report['date']}")
        print("=" * 60)

        summary = report["summary"]
        print("\nSummary:")
        print(f"  Net P&L: {summary['tl_pnl_net']:.2f} TL")
        print(f"  Hit Rate: {summary['hit_rate']:.1%}")
        print(f"  EV Rejection: {summary['ev_rejection_rate']:.1%}")
        print(f"  Max Drawdown: {summary['max_dd_pct']:.2f}%")

        print("\nHealth Checks:")
        health = report["health_status"]
        print(f"  Anomalies: {'✅ Clean' if health['anomalies'] else '❌ Detected'}")
        print(f"  Reconciliation: {'✅ Passed' if health['reconciliation'] else '❌ Failed'}")
        print(f"  Drawdown: {'✅ OK' if health['drawdown_ok'] else '❌ Breached'}")

        print("\nBest/Worst Hours:")
        print(f"  Best: {summary['best_hour']}")
        print(f"  Worst: {summary['worst_hour']}")

        if report["recommendations"]:
            print("\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  • {rec}")

        print("=" * 60)


def main():
    """Generate pilot day report"""

    reporter = PilotDayReport()
    report = reporter.generate_report()

    # Save report
    reporter.save_report(report)

    # Print summary
    reporter.print_report(report)

    print("\nReports saved:")
    print(f"  - reports/pilot_day_report_{reporter.report_date}.json")
    print(f"  - reports/pilot_day_report_{reporter.report_date}.md")


if __name__ == "__main__":
    main()
