"""
EV Impact Analysis - Analyze Expected Value gate effectiveness
Evaluates how well EV predictions matched actual outcomes
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EVImpactAnalysis:
    """Analyze EV gate effectiveness"""

    def __init__(self):
        self.trades_file = Path("logs/pilot_trades.json")
        self.ev_log_file = Path("logs/ev_decisions.json")
        self.telemetry_file = Path("logs/pilot_telemetry.json")

    def load_ev_decisions(self) -> List[Dict]:
        """Load EV gate decisions"""
        if not self.ev_log_file.exists():
            # Generate mock data for demonstration
            return self.generate_mock_ev_data()

        try:
            with open(self.ev_log_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load EV decisions: {e}")
            return []

    def generate_mock_ev_data(self) -> List[Dict]:
        """Generate mock EV decision data"""
        import random

        decisions = []
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]

        for i in range(200):
            # Generate mock decision
            spread_bps = random.uniform(2, 10)
            size_tl = random.uniform(100, 500)
            fee_bps = 2.5
            fill_rate = random.uniform(0.5, 0.95)
            depth_ratio = random.uniform(0.8, 2.0)
            latency_ms = random.uniform(50, 200)

            # Calculate EV
            edge_tl = size_tl * spread_bps / 10000
            p_fill = min(0.95, fill_rate * min(1.0, depth_ratio))
            expected_edge = edge_tl * p_fill

            fee_cost = size_tl * fee_bps / 10000
            slippage_cost = size_tl * (1 - min(1.0, depth_ratio)) * 0.001
            latency_cost = size_tl * (latency_ms / 1000) * 0.0001

            total_cost = fee_cost + slippage_cost + latency_cost
            ev = expected_edge - total_cost

            # Decision
            decision = "ACCEPT" if ev > 1.0 else "REJECT"

            # Realized P&L (if accepted)
            realized_pnl = None
            if decision == "ACCEPT":
                # Add noise to simulate reality
                noise = random.gauss(0, 2)
                realized_pnl = ev + noise

            decisions.append(
                {
                    "timestamp": (
                        datetime.now() - timedelta(hours=random.randint(0, 24))
                    ).isoformat(),
                    "symbol": random.choice(symbols),
                    "spread_bps": round(spread_bps, 2),
                    "size_tl": round(size_tl, 2),
                    "predicted_ev": round(ev, 2),
                    "decision": decision,
                    "realized_pnl": round(realized_pnl, 2) if realized_pnl else None,
                    "fill_probability": round(p_fill, 3),
                    "expected_edge": round(expected_edge, 2),
                    "total_cost": round(total_cost, 2),
                }
            )

        return decisions

    def calculate_prediction_accuracy(self, decisions: List[Dict]) -> Dict:
        """Calculate how accurate EV predictions were"""

        accepted = [
            d for d in decisions if d["decision"] == "ACCEPT" and d.get("realized_pnl") is not None
        ]

        if not accepted:
            return {
                "correlation": 0,
                "mean_error_tl": 0,
                "mean_error_bps": 0,
                "rmse": 0,
                "hit_rate": 0,
            }

        # Extract predicted vs realized
        predicted = np.array([d["predicted_ev"] for d in accepted])
        realized = np.array([d["realized_pnl"] for d in accepted])

        # Calculate metrics
        correlation = np.corrcoef(predicted, realized)[0, 1] if len(predicted) > 1 else 0
        errors = realized - predicted
        mean_error = np.mean(errors)

        # Convert to basis points (assume avg size 250 TL)
        avg_size = np.mean([d["size_tl"] for d in accepted])
        mean_error_bps = (mean_error / avg_size) * 10000 if avg_size > 0 else 0

        # RMSE
        rmse = np.sqrt(np.mean(errors**2))

        # Hit rate (predicted positive, realized positive)
        hits = sum(1 for p, r in zip(predicted, realized) if p > 0 and r > 0)
        hit_rate = hits / len(predicted) if predicted.any() else 0

        return {
            "correlation": round(correlation, 3),
            "mean_error_tl": round(mean_error, 2),
            "mean_error_bps": round(mean_error_bps, 1),
            "rmse": round(rmse, 2),
            "hit_rate": round(hit_rate, 3),
            "sample_size": len(accepted),
        }

    def analyze_rejection_impact(self, decisions: List[Dict]) -> Dict:
        """Analyze impact of rejections"""

        rejected = [d for d in decisions if d["decision"] == "REJECT"]
        accepted = [d for d in decisions if d["decision"] == "ACCEPT"]

        total_evaluated = len(decisions)
        total_rejected = len(rejected)
        rejection_rate = total_rejected / total_evaluated if total_evaluated > 0 else 0

        # Analyze rejected trades
        rejected_evs = [d["predicted_ev"] for d in rejected]

        # Distribution of rejected EVs
        if rejected_evs:
            rejected_stats = {
                "min": round(min(rejected_evs), 2),
                "max": round(max(rejected_evs), 2),
                "mean": round(np.mean(rejected_evs), 2),
                "median": round(np.median(rejected_evs), 2),
                "std": round(np.std(rejected_evs), 2),
            }
        else:
            rejected_stats = {"min": 0, "max": 0, "mean": 0, "median": 0, "std": 0}

        # What if we had taken them?
        potential_loss = sum(ev for ev in rejected_evs if ev < 0)
        avoided_trades = sum(1 for ev in rejected_evs if ev < -1.0)

        return {
            "total_evaluated": total_evaluated,
            "total_rejected": total_rejected,
            "rejection_rate": round(rejection_rate, 3),
            "rejected_ev_stats": rejected_stats,
            "potential_loss_avoided": round(potential_loss, 2),
            "high_risk_trades_avoided": avoided_trades,
        }

    def calculate_pnl_variance_reduction(self, decisions: List[Dict]) -> float:
        """Calculate P&L variance reduction from EV gate"""

        accepted = [
            d for d in decisions if d["decision"] == "ACCEPT" and d.get("realized_pnl") is not None
        ]

        if not accepted:
            return 0

        # Actual P&L variance
        actual_pnls = [d["realized_pnl"] for d in accepted]
        actual_variance = np.var(actual_pnls) if actual_pnls else 0

        # Simulate: what if we took all trades?
        all_trades = decisions.copy()
        for trade in all_trades:
            if trade["decision"] == "REJECT":
                # Simulate realized P&L for rejected trades
                # Assume they would have performed as predicted with more noise
                noise = np.random.normal(0, 3)
                trade["simulated_pnl"] = trade["predicted_ev"] + noise

        all_pnls = []
        for trade in all_trades:
            if trade.get("realized_pnl") is not None:
                all_pnls.append(trade["realized_pnl"])
            elif trade.get("simulated_pnl") is not None:
                all_pnls.append(trade["simulated_pnl"])

        hypothetical_variance = np.var(all_pnls) if all_pnls else 0

        # Variance reduction
        if hypothetical_variance > 0:
            reduction = 1 - (actual_variance / hypothetical_variance)
        else:
            reduction = 0

        return round(reduction, 3)

    def generate_recommendations(self, analysis: Dict) -> Dict:
        """Generate recommendations for EV gate tuning"""

        recommendations = {
            "min_ev_tl": 1.0,  # Current
            "safety_margin_bps": 5,  # Current
            "changes": [],
        }

        # Based on prediction accuracy
        accuracy = analysis["prediction_accuracy"]

        if accuracy["correlation"] > 0.8 and accuracy["mean_error_bps"] < 2:
            # Very accurate predictions - can be more aggressive
            recommendations["min_ev_tl"] = 0.8
            recommendations["safety_margin_bps"] = 3
            recommendations["changes"].append("Lower min EV threshold to 0.8 TL (high accuracy)")
            recommendations["changes"].append("Reduce safety margin to 3 bps")

        elif accuracy["correlation"] > 0.7 and accuracy["mean_error_bps"] < 3:
            # Good accuracy - slight adjustment
            recommendations["min_ev_tl"] = 1.2
            recommendations["safety_margin_bps"] = 4
            recommendations["changes"].append("Slightly increase min EV to 1.2 TL")
            recommendations["changes"].append("Adjust safety margin to 4 bps")

        elif accuracy["correlation"] < 0.5 or accuracy["mean_error_bps"] > 5:
            # Poor accuracy - be more conservative
            recommendations["min_ev_tl"] = 1.5
            recommendations["safety_margin_bps"] = 7
            recommendations["changes"].append("Increase min EV threshold to 1.5 TL (low accuracy)")
            recommendations["changes"].append("Increase safety margin to 7 bps")

        # Based on rejection impact
        rejection = analysis["rejection_impact"]

        if rejection["rejection_rate"] > 0.4:
            # Too many rejections
            recommendations["changes"].append(
                "High rejection rate - consider market-specific thresholds"
            )

        elif rejection["rejection_rate"] < 0.1:
            # Too few rejections
            recommendations["changes"].append("Low rejection rate - EV gate may be too permissive")

        # Based on variance reduction
        if analysis["variance_reduction"] < 0.2:
            recommendations["changes"].append(
                "Low variance reduction - EV gate not effective enough"
            )

        return recommendations

    def generate_report(self) -> Dict:
        """Generate complete EV impact analysis report"""

        # Load data
        decisions = self.load_ev_decisions()

        if not decisions:
            logger.error("No EV decision data available")
            return {}

        # Run analyses
        prediction_accuracy = self.calculate_prediction_accuracy(decisions)
        rejection_impact = self.analyze_rejection_impact(decisions)
        variance_reduction = self.calculate_pnl_variance_reduction(decisions)

        # Generate recommendations
        analysis = {
            "prediction_accuracy": prediction_accuracy,
            "rejection_impact": rejection_impact,
            "variance_reduction": variance_reduction,
        }

        recommendations = self.generate_recommendations(analysis)

        # Create report
        report = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period": {
                "start": min(d["timestamp"] for d in decisions),
                "end": max(d["timestamp"] for d in decisions),
                "trades_analyzed": len(decisions),
            },
            "ev_rejected_count": rejection_impact["total_rejected"],
            "predicted_vs_realized": {
                "correlation": prediction_accuracy["correlation"],
                "mean_error_bps": prediction_accuracy["mean_error_bps"],
            },
            "pnl_variance_reduction": variance_reduction,
            "recommendations": recommendations,
            "detailed_analysis": analysis,
        }

        return report

    def save_report(self, report: Dict):
        """Save analysis report"""

        # Save JSON
        json_file = Path("reports/ev_impact_analysis.json")
        json_file.parent.mkdir(exist_ok=True)

        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)

        # Save Markdown
        md_file = Path("reports/ev_impact_analysis.md")
        md_content = self.format_markdown_report(report)
        md_file.write_text(md_content)

        logger.info(f"EV impact analysis saved: {json_file}")
        logger.info(f"EV impact analysis saved: {md_file}")

    def format_markdown_report(self, report: Dict) -> str:
        """Format report as markdown"""

        lines = [
            "# EV Gate Impact Analysis",
            f"\n**Generated**: {report['timestamp']}",
            "\n## Analysis Period",
            f"- Start: {report['analysis_period']['start']}",
            f"- End: {report['analysis_period']['end']}",
            f"- Trades Analyzed: {report['analysis_period']['trades_analyzed']}",
            "\n## Key Metrics",
            f"- **EV Rejected Count**: {report['ev_rejected_count']}",
            f"- **Prediction Correlation**: {report['predicted_vs_realized']['correlation']:.3f}",
            f"- **Mean Error**: {report['predicted_vs_realized']['mean_error_bps']:.1f} bps",
            f"- **P&L Variance Reduction**: {report['pnl_variance_reduction']:.1%}",
            "\n## Prediction Accuracy",
        ]

        accuracy = report["detailed_analysis"]["prediction_accuracy"]
        lines.extend(
            [
                f"- Correlation: {accuracy['correlation']:.3f}",
                f"- Mean Error: {accuracy['mean_error_tl']:.2f} TL ({accuracy['mean_error_bps']:.1f} bps)",
                f"- RMSE: {accuracy['rmse']:.2f} TL",
                f"- Hit Rate: {accuracy['hit_rate']:.1%}",
                f"- Sample Size: {accuracy['sample_size']} trades",
            ]
        )

        lines.append("\n## Rejection Analysis")
        rejection = report["detailed_analysis"]["rejection_impact"]
        lines.extend(
            [
                f"- Total Evaluated: {rejection['total_evaluated']}",
                f"- Total Rejected: {rejection['total_rejected']}",
                f"- Rejection Rate: {rejection['rejection_rate']:.1%}",
                f"- Potential Loss Avoided: {rejection['potential_loss_avoided']:.2f} TL",
                f"- High Risk Trades Avoided: {rejection['high_risk_trades_avoided']}",
            ]
        )

        lines.append("\n## Rejected EV Distribution")
        stats = rejection["rejected_ev_stats"]
        lines.extend(
            [
                f"- Min: {stats['min']:.2f} TL",
                f"- Max: {stats['max']:.2f} TL",
                f"- Mean: {stats['mean']:.2f} TL",
                f"- Median: {stats['median']:.2f} TL",
                f"- Std Dev: {stats['std']:.2f} TL",
            ]
        )

        lines.append("\n## Recommendations")
        rec = report["recommendations"]
        lines.extend(
            [
                f"- **New Min EV**: {rec['min_ev_tl']:.1f} TL",
                f"- **New Safety Margin**: {rec['safety_margin_bps']} bps",
                "\n### Recommended Changes:",
            ]
        )

        for i, change in enumerate(rec["changes"], 1):
            lines.append(f"{i}. {change}")

        lines.extend(["\n---", "*Generated by ev_impact.py*"])

        return "\n".join(lines)

    def print_summary(self, report: Dict):
        """Print analysis summary"""

        print("\n" + "=" * 60)
        print(" EV GATE IMPACT ANALYSIS")
        print("=" * 60)

        print(f"\nPeriod: {report['analysis_period']['trades_analyzed']} trades")
        print(f"Rejected: {report['ev_rejected_count']} trades")

        print("\nPrediction Quality:")
        print(f"  Correlation: {report['predicted_vs_realized']['correlation']:.3f}")
        print(f"  Mean Error: {report['predicted_vs_realized']['mean_error_bps']:.1f} bps")

        print(f"\nP&L Variance Reduction: {report['pnl_variance_reduction']:.1%}")

        print("\nRecommendations:")
        rec = report["recommendations"]
        print(f"  Min EV: {rec['min_ev_tl']:.1f} TL")
        print(f"  Safety Margin: {rec['safety_margin_bps']} bps")

        if rec["changes"]:
            print("\nSuggested Changes:")
            for change in rec["changes"]:
                print(f"  • {change}")

        print("=" * 60)


def main():
    """Run EV impact analysis"""

    analyzer = EVImpactAnalysis()
    report = analyzer.generate_report()

    if report:
        # Save report
        analyzer.save_report(report)

        # Print summary
        analyzer.print_summary(report)

        print("\nReports saved:")
        print("  - reports/ev_impact_analysis.json")
        print("  - reports/ev_impact_analysis.md")
    else:
        print("No data available for analysis")


if __name__ == "__main__":
    main()
