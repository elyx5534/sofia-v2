"""
Attribution Decider - Plan next day symbols based on performance
Analyzes profit attribution and decides optimal symbol allocation
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AttributionDecider:
    """Decide next day's symbol plan based on attribution"""

    def __init__(self):
        self.attribution_file = Path("reports/profit_attribution.json")
        self.telemetry_file = Path("logs/pilot_telemetry.json")
        self.trades_file = Path("logs/pilot_trades.json")

    def load_profit_attribution(self) -> Dict:
        """Load profit attribution data"""
        if not self.attribution_file.exists():
            # Generate mock attribution data
            return self.generate_mock_attribution()

        try:
            with open(self.attribution_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load attribution: {e}")
            return {}

    def generate_mock_attribution(self) -> Dict:
        """Generate mock profit attribution data"""
        import random

        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]

        attribution = {"timestamp": datetime.now().isoformat(), "period": "24h", "symbols": {}}

        for symbol in symbols:
            # Generate hourly performance
            hourly_pnl = {}
            for hour in range(10, 18):  # Trading hours 10:00-18:00
                pnl = random.uniform(-50, 100)
                trades = random.randint(5, 20)
                fill_rate = random.uniform(0.4, 0.9)

                hourly_pnl[f"{hour:02d}:00"] = {
                    "pnl_tl": round(pnl, 2),
                    "trades": trades,
                    "fill_rate": round(fill_rate, 3),
                    "avg_spread_bps": round(random.uniform(2, 8), 1),
                    "avg_latency_ms": round(random.uniform(50, 150), 0),
                }

            # Calculate totals
            total_pnl = sum(h["pnl_tl"] for h in hourly_pnl.values())
            total_trades = sum(h["trades"] for h in hourly_pnl.values())
            avg_fill_rate = sum(h["fill_rate"] for h in hourly_pnl.values()) / len(hourly_pnl)

            attribution["symbols"][symbol] = {
                "total_pnl_tl": round(total_pnl, 2),
                "total_trades": total_trades,
                "avg_fill_rate": round(avg_fill_rate, 3),
                "hourly": hourly_pnl,
                "best_hour": max(hourly_pnl.items(), key=lambda x: x[1]["pnl_tl"])[0],
                "worst_hour": min(hourly_pnl.items(), key=lambda x: x[1]["pnl_tl"])[0],
            }

        return attribution

    def analyze_time_performance(self, attribution: Dict) -> Dict:
        """Analyze performance by time of day"""

        time_analysis = {
            "morning": {"symbols": {}, "total_pnl": 0},  # 10:00-14:00
            "afternoon": {"symbols": {}, "total_pnl": 0},  # 14:00-18:00
        }

        for symbol, data in attribution.get("symbols", {}).items():
            morning_pnl = 0
            afternoon_pnl = 0
            morning_trades = 0
            afternoon_trades = 0

            for hour_str, hour_data in data.get("hourly", {}).items():
                hour = int(hour_str.split(":")[0])

                if 10 <= hour < 14:
                    morning_pnl += hour_data["pnl_tl"]
                    morning_trades += hour_data["trades"]
                elif 14 <= hour < 18:
                    afternoon_pnl += hour_data["pnl_tl"]
                    afternoon_trades += hour_data["trades"]

            time_analysis["morning"]["symbols"][symbol] = {
                "pnl_tl": round(morning_pnl, 2),
                "trades": morning_trades,
                "pnl_per_trade": round(morning_pnl / max(morning_trades, 1), 2),
            }

            time_analysis["afternoon"]["symbols"][symbol] = {
                "pnl_tl": round(afternoon_pnl, 2),
                "trades": afternoon_trades,
                "pnl_per_trade": round(afternoon_pnl / max(afternoon_trades, 1), 2),
            }

            time_analysis["morning"]["total_pnl"] += morning_pnl
            time_analysis["afternoon"]["total_pnl"] += afternoon_pnl

        return time_analysis

    def analyze_fill_rates(self, attribution: Dict) -> Dict:
        """Analyze fill rates by symbol and time"""

        fill_analysis = {}

        for symbol, data in attribution.get("symbols", {}).items():
            morning_fills = []
            afternoon_fills = []

            for hour_str, hour_data in data.get("hourly", {}).items():
                hour = int(hour_str.split(":")[0])
                fill_rate = hour_data.get("fill_rate", 0)

                if 10 <= hour < 14:
                    morning_fills.append(fill_rate)
                elif 14 <= hour < 18:
                    afternoon_fills.append(fill_rate)

            fill_analysis[symbol] = {
                "morning_avg": round(sum(morning_fills) / max(len(morning_fills), 1), 3),
                "afternoon_avg": round(sum(afternoon_fills) / max(len(afternoon_fills), 1), 3),
                "overall_avg": data.get("avg_fill_rate", 0),
            }

        return fill_analysis

    def rank_symbols(self, time_analysis: Dict, fill_analysis: Dict) -> Dict:
        """Rank symbols for each time period"""

        rankings = {"morning": [], "afternoon": []}

        # Morning rankings (10:00-14:00)
        for symbol, perf in time_analysis["morning"]["symbols"].items():
            score = (
                perf["pnl_per_trade"] * 0.5  # P&L per trade weight
                + perf["pnl_tl"] * 0.3  # Total P&L weight
                + fill_analysis[symbol]["morning_avg"] * 100 * 0.2  # Fill rate weight
            )

            rankings["morning"].append(
                {
                    "symbol": symbol,
                    "score": round(score, 2),
                    "pnl_tl": perf["pnl_tl"],
                    "pnl_per_trade": perf["pnl_per_trade"],
                    "fill_rate": fill_analysis[symbol]["morning_avg"],
                }
            )

        # Afternoon rankings (14:00-18:00)
        for symbol, perf in time_analysis["afternoon"]["symbols"].items():
            score = (
                perf["pnl_per_trade"] * 0.5
                + perf["pnl_tl"] * 0.3
                + fill_analysis[symbol]["afternoon_avg"] * 100 * 0.2
            )

            rankings["afternoon"].append(
                {
                    "symbol": symbol,
                    "score": round(score, 2),
                    "pnl_tl": perf["pnl_tl"],
                    "pnl_per_trade": perf["pnl_per_trade"],
                    "fill_rate": fill_analysis[symbol]["afternoon_avg"],
                }
            )

        # Sort by score
        rankings["morning"].sort(key=lambda x: x["score"], reverse=True)
        rankings["afternoon"].sort(key=lambda x: x["score"], reverse=True)

        return rankings

    def generate_symbol_plan(self, rankings: Dict, max_symbols: int = 2) -> Dict:
        """Generate tomorrow's symbol plan"""

        plan = {
            "generated_at": datetime.now().isoformat(),
            "for_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "AM": {"symbols": [], "reasoning": "", "expected_performance": {}},
            "PM": {"symbols": [], "reasoning": "", "expected_performance": {}},
        }

        # Select top symbols for morning
        morning_symbols = [s["symbol"] for s in rankings["morning"][:max_symbols]]
        morning_top = rankings["morning"][:max_symbols]

        plan["AM"]["symbols"] = morning_symbols
        plan["AM"]["reasoning"] = f"Top {max_symbols} performers in 10:00-14:00 window"
        plan["AM"]["expected_performance"] = {
            "total_pnl_tl": sum(s["pnl_tl"] for s in morning_top),
            "avg_fill_rate": (
                sum(s["fill_rate"] for s in morning_top) / len(morning_top) if morning_top else 0
            ),
            "details": morning_top,
        }

        # Select top symbols for afternoon
        afternoon_symbols = [s["symbol"] for s in rankings["afternoon"][:max_symbols]]
        afternoon_top = rankings["afternoon"][:max_symbols]

        plan["PM"]["symbols"] = afternoon_symbols
        plan["PM"]["reasoning"] = f"Top {max_symbols} performers in 14:00-18:00 window"
        plan["PM"]["expected_performance"] = {
            "total_pnl_tl": sum(s["pnl_tl"] for s in afternoon_top),
            "avg_fill_rate": (
                sum(s["fill_rate"] for s in afternoon_top) / len(afternoon_top)
                if afternoon_top
                else 0
            ),
            "details": afternoon_top,
        }

        # Add diversity check
        overlap = set(morning_symbols) & set(afternoon_symbols)
        if overlap:
            plan["notes"] = f"Symbols {overlap} perform well in both sessions"
        else:
            plan["notes"] = "Different optimal symbols for AM and PM sessions"

        return plan

    def add_risk_adjustments(self, plan: Dict, attribution: Dict) -> Dict:
        """Add risk-based adjustments to plan"""

        # Check for consistently negative performers
        avoid_symbols = []

        for symbol, data in attribution.get("symbols", {}).items():
            if data["total_pnl_tl"] < -100:
                avoid_symbols.append(symbol)

        if avoid_symbols:
            plan["risk_adjustments"] = {
                "avoid_symbols": avoid_symbols,
                "reason": "Consistent negative P&L in previous session",
            }

            # Remove from plan if present
            for session in ["AM", "PM"]:
                plan[session]["symbols"] = [
                    s for s in plan[session]["symbols"] if s not in avoid_symbols
                ]

        # Add position limits based on volatility
        plan["position_limits"] = {
            "high_volatility": 100,  # TL
            "normal": 250,  # TL
            "low_volatility": 400,  # TL
        }

        return plan

    def generate_report(self) -> Dict:
        """Generate complete attribution decision report"""

        # Load attribution data
        attribution = self.load_profit_attribution()

        if not attribution:
            logger.error("No attribution data available")
            return {}

        # Analyze performance
        time_analysis = self.analyze_time_performance(attribution)
        fill_analysis = self.analyze_fill_rates(attribution)

        # Rank symbols
        rankings = self.rank_symbols(time_analysis, fill_analysis)

        # Generate plan
        symbol_plan = self.generate_symbol_plan(rankings)

        # Add risk adjustments
        symbol_plan = self.add_risk_adjustments(symbol_plan, attribution)

        # Create report
        report = {
            "timestamp": datetime.now().isoformat(),
            "attribution_data": attribution,
            "time_analysis": time_analysis,
            "fill_analysis": fill_analysis,
            "rankings": rankings,
            "symbol_plan": symbol_plan,
        }

        return report

    def save_plan(self, report: Dict):
        """Save symbol plan for tomorrow"""

        # Save full report
        report_file = Path("reports/attribution_decision.json")
        report_file.parent.mkdir(exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        # Save just the plan
        plan_file = Path("config/symbol_plan_tomorrow.json")
        plan_file.parent.mkdir(exist_ok=True)

        with open(plan_file, "w") as f:
            json.dump(report["symbol_plan"], f, indent=2)

        # Save markdown report
        md_file = Path("reports/symbol_plan_tomorrow.md")
        md_content = self.format_markdown_report(report)
        md_file.write_text(md_content)

        logger.info(f"Attribution decision saved: {report_file}")
        logger.info(f"Symbol plan saved: {plan_file}")
        logger.info(f"Markdown report saved: {md_file}")

    def format_markdown_report(self, report: Dict) -> str:
        """Format report as markdown"""

        plan = report["symbol_plan"]
        rankings = report["rankings"]

        lines = [
            f"# Symbol Plan for {plan['for_date']}",
            f"\n**Generated**: {plan['generated_at']}",
            "\n## Morning Session (10:00-14:00)",
            f"**Selected Symbols**: {', '.join(plan['AM']['symbols'])}",
            f"\n**Reasoning**: {plan['AM']['reasoning']}",
            "\n### Expected Performance:",
            f"- Total P&L: {plan['AM']['expected_performance']['total_pnl_tl']:.2f} TL",
            f"- Avg Fill Rate: {plan['AM']['expected_performance']['avg_fill_rate']:.1%}",
            "\n### Top Morning Performers:",
        ]

        for i, symbol in enumerate(rankings["morning"][:5], 1):
            lines.append(
                f"{i}. **{symbol['symbol']}**: Score={symbol['score']:.1f}, "
                f"P&L={symbol['pnl_tl']:.2f} TL, Fill={symbol['fill_rate']:.1%}"
            )

        lines.extend(
            [
                "\n## Afternoon Session (14:00-18:00)",
                f"**Selected Symbols**: {', '.join(plan['PM']['symbols'])}",
                f"\n**Reasoning**: {plan['PM']['reasoning']}",
                "\n### Expected Performance:",
                f"- Total P&L: {plan['PM']['expected_performance']['total_pnl_tl']:.2f} TL",
                f"- Avg Fill Rate: {plan['PM']['expected_performance']['avg_fill_rate']:.1%}",
                "\n### Top Afternoon Performers:",
            ]
        )

        for i, symbol in enumerate(rankings["afternoon"][:5], 1):
            lines.append(
                f"{i}. **{symbol['symbol']}**: Score={symbol['score']:.1f}, "
                f"P&L={symbol['pnl_tl']:.2f} TL, Fill={symbol['fill_rate']:.1%}"
            )

        if plan.get("notes"):
            lines.extend(["\n## Notes", plan["notes"]])

        if plan.get("risk_adjustments"):
            lines.extend(
                [
                    "\n## Risk Adjustments",
                    f"- Avoid: {', '.join(plan['risk_adjustments'].get('avoid_symbols', []))}",
                    f"- Reason: {plan['risk_adjustments'].get('reason', 'N/A')}",
                ]
            )

        lines.extend(
            [
                "\n## Position Limits",
                f"- High Volatility: {plan['position_limits']['high_volatility']} TL",
                f"- Normal: {plan['position_limits']['normal']} TL",
                f"- Low Volatility: {plan['position_limits']['low_volatility']} TL",
                "\n---",
                "*Generated by attribution_decider.py*",
            ]
        )

        return "\n".join(lines)

    def print_plan(self, report: Dict):
        """Print symbol plan summary"""

        plan = report["symbol_plan"]

        print("\n" + "=" * 60)
        print(f" SYMBOL PLAN FOR {plan['for_date']}")
        print("=" * 60)

        print("\nMorning (10:00-14:00):")
        print(f"  Symbols: {', '.join(plan['AM']['symbols'])}")
        print(f"  Expected P&L: {plan['AM']['expected_performance']['total_pnl_tl']:.2f} TL")

        print("\nAfternoon (14:00-18:00):")
        print(f"  Symbols: {', '.join(plan['PM']['symbols'])}")
        print(f"  Expected P&L: {plan['PM']['expected_performance']['total_pnl_tl']:.2f} TL")

        if plan.get("notes"):
            print(f"\nNotes: {plan['notes']}")

        if plan.get("risk_adjustments"):
            print(f"\nRisk: Avoid {plan['risk_adjustments']['avoid_symbols']}")

        print("=" * 60)


def main():
    """Generate symbol plan for tomorrow"""

    decider = AttributionDecider()
    report = decider.generate_report()

    if report:
        # Save plan
        decider.save_plan(report)

        # Print summary
        decider.print_plan(report)

        print("\nFiles saved:")
        print("  - config/symbol_plan_tomorrow.json")
        print("  - reports/attribution_decision.json")
        print("  - reports/symbol_plan_tomorrow.md")
    else:
        print("No attribution data available")


if __name__ == "__main__":
    main()
