"""
Profit Attribution Dashboard
Analyzes P&L sources by strategy, symbol, time, and edge
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProfitAttribution:
    """Analyzes and attributes profit sources"""
    
    def __init__(self):
        self.hour_buckets = [
            (10, 12, "Morning"),
            (12, 14, "Noon"),
            (14, 16, "Afternoon"),
            (16, 18, "Evening")
        ]
        
        self.edge_bins = [
            (0, 10, "Low"),
            (10, 20, "Medium"),
            (20, 30, "High"),
            (30, 100, "VeryHigh")
        ]
        
        self.latency_bins = [
            (0, 50, "Fast"),
            (50, 100, "Normal"),
            (100, 200, "Slow"),
            (200, 1000, "VerySlow")
        ]
    
    def load_audit_logs(self) -> List[Dict]:
        """Load paper trading audit logs"""
        audit_file = Path("logs/paper_audit.jsonl")
        trades = []
        
        if audit_file.exists():
            with open(audit_file, 'r') as f:
                for line in f:
                    try:
                        trade = json.loads(line)
                        trades.append(trade)
                    except:
                        continue
        
        # Generate mock data if no logs
        if not trades:
            trades = self._generate_mock_trades()
        
        return trades
    
    def load_daily_scores(self) -> Dict:
        """Load daily score report"""
        score_file = Path("reports/daily_score.json")
        
        if score_file.exists():
            with open(score_file, 'r') as f:
                return json.load(f)
        
        # Mock data
        return {
            "date": datetime.now().isoformat(),
            "total_pnl": 1500,
            "win_rate": 0.65,
            "trades": 50
        }
    
    def _generate_mock_trades(self) -> List[Dict]:
        """Generate mock trade data for testing"""
        trades = []
        strategies = ["grid", "arb", "scalp", "swing"]
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        
        for i in range(100):
            hour = np.random.randint(10, 18)
            timestamp = datetime.now() - timedelta(hours=np.random.randint(0, 24))
            
            trade = {
                "id": f"trade_{i}",
                "timestamp": timestamp.isoformat(),
                "strategy": np.random.choice(strategies),
                "symbol": np.random.choice(symbols),
                "side": np.random.choice(["buy", "sell"]),
                "price": float(np.random.uniform(30000, 60000)),
                "quantity": float(np.random.uniform(0.001, 0.1)),
                "pnl": float(np.random.uniform(-50, 100)),
                "edge_bps": float(np.random.uniform(5, 35)),
                "latency_ms": float(np.random.uniform(20, 300)),
                "hour": hour
            }
            trades.append(trade)
        
        return trades
    
    def categorize_trade(self, trade: Dict) -> Dict:
        """Categorize trade by buckets"""
        categories = {}
        
        # Hour bucket
        hour = trade.get("hour", datetime.fromisoformat(trade["timestamp"]).hour)
        for start, end, label in self.hour_buckets:
            if start <= hour < end:
                categories["hour_bucket"] = label
                break
        else:
            categories["hour_bucket"] = "OffHours"
        
        # Edge bin
        edge = trade.get("edge_bps", 0)
        for min_edge, max_edge, label in self.edge_bins:
            if min_edge <= edge < max_edge:
                categories["edge_bin"] = label
                break
        
        # Latency bin
        latency = trade.get("latency_ms", 100)
        for min_lat, max_lat, label in self.latency_bins:
            if min_lat <= latency < max_lat:
                categories["latency_bin"] = label
                break
        
        return categories
    
    def analyze_attribution(self, trades: List[Dict]) -> Dict:
        """Analyze profit attribution"""
        
        attribution = {
            "total_pnl": 0,
            "total_trades": len(trades),
            "by_strategy": defaultdict(lambda: {"pnl": 0, "trades": 0, "win_rate": 0}),
            "by_symbol": defaultdict(lambda: {"pnl": 0, "trades": 0, "win_rate": 0}),
            "by_hour": defaultdict(lambda: {"pnl": 0, "trades": 0, "win_rate": 0}),
            "by_edge": defaultdict(lambda: {"pnl": 0, "trades": 0, "win_rate": 0}),
            "by_latency": defaultdict(lambda: {"pnl": 0, "trades": 0, "win_rate": 0}),
            "combinations": defaultdict(lambda: {"pnl": 0, "trades": 0})
        }
        
        # Process each trade
        for trade in trades:
            pnl = trade.get("pnl", 0)
            attribution["total_pnl"] += pnl
            
            # Categorize
            categories = self.categorize_trade(trade)
            
            # By strategy
            strategy = trade.get("strategy", "unknown")
            attribution["by_strategy"][strategy]["pnl"] += pnl
            attribution["by_strategy"][strategy]["trades"] += 1
            if pnl > 0:
                attribution["by_strategy"][strategy]["win_rate"] += 1
            
            # By symbol
            symbol = trade.get("symbol", "unknown")
            attribution["by_symbol"][symbol]["pnl"] += pnl
            attribution["by_symbol"][symbol]["trades"] += 1
            if pnl > 0:
                attribution["by_symbol"][symbol]["win_rate"] += 1
            
            # By hour bucket
            hour_bucket = categories.get("hour_bucket", "unknown")
            attribution["by_hour"][hour_bucket]["pnl"] += pnl
            attribution["by_hour"][hour_bucket]["trades"] += 1
            if pnl > 0:
                attribution["by_hour"][hour_bucket]["win_rate"] += 1
            
            # By edge bin
            edge_bin = categories.get("edge_bin", "unknown")
            attribution["by_edge"][edge_bin]["pnl"] += pnl
            attribution["by_edge"][edge_bin]["trades"] += 1
            if pnl > 0:
                attribution["by_edge"][edge_bin]["win_rate"] += 1
            
            # By latency bin
            latency_bin = categories.get("latency_bin", "unknown")
            attribution["by_latency"][latency_bin]["pnl"] += pnl
            attribution["by_latency"][latency_bin]["trades"] += 1
            if pnl > 0:
                attribution["by_latency"][latency_bin]["win_rate"] += 1
            
            # Combinations
            combo_key = f"{strategy}_{symbol}_{hour_bucket}"
            attribution["combinations"][combo_key]["pnl"] += pnl
            attribution["combinations"][combo_key]["trades"] += 1
        
        # Calculate win rates
        for category in ["by_strategy", "by_symbol", "by_hour", "by_edge", "by_latency"]:
            for key, data in attribution[category].items():
                if data["trades"] > 0:
                    data["win_rate"] = data["win_rate"] / data["trades"]
                    data["avg_pnl"] = data["pnl"] / data["trades"]
        
        # Convert defaultdicts to regular dicts
        attribution["by_strategy"] = dict(attribution["by_strategy"])
        attribution["by_symbol"] = dict(attribution["by_symbol"])
        attribution["by_hour"] = dict(attribution["by_hour"])
        attribution["by_edge"] = dict(attribution["by_edge"])
        attribution["by_latency"] = dict(attribution["by_latency"])
        attribution["combinations"] = dict(attribution["combinations"])
        
        return attribution
    
    def find_insights(self, attribution: Dict) -> List[str]:
        """Extract key insights from attribution"""
        insights = []
        
        # Best performing strategy
        if attribution["by_strategy"]:
            best_strategy = max(attribution["by_strategy"].items(), 
                              key=lambda x: x[1]["pnl"])
            insights.append(f"Best strategy: {best_strategy[0]} with {best_strategy[1]['pnl']:.2f} P&L")
        
        # Best performing symbol
        if attribution["by_symbol"]:
            best_symbol = max(attribution["by_symbol"].items(), 
                            key=lambda x: x[1]["pnl"])
            insights.append(f"Best symbol: {best_symbol[0]} with {best_symbol[1]['pnl']:.2f} P&L")
        
        # Best time of day
        if attribution["by_hour"]:
            best_hour = max(attribution["by_hour"].items(), 
                          key=lambda x: x[1]["pnl"])
            insights.append(f"Best time: {best_hour[0]} with {best_hour[1]['pnl']:.2f} P&L")
        
        # Edge vs P&L correlation
        if attribution["by_edge"]:
            high_edge = attribution["by_edge"].get("VeryHigh", {})
            low_edge = attribution["by_edge"].get("Low", {})
            if high_edge.get("avg_pnl", 0) > low_edge.get("avg_pnl", 0):
                insights.append("Higher edge correlates with better P&L")
            else:
                insights.append("Edge not strongly correlated with P&L - check execution")
        
        # Latency impact
        if attribution["by_latency"]:
            fast = attribution["by_latency"].get("Fast", {})
            slow = attribution["by_latency"].get("VerySlow", {})
            if fast.get("win_rate", 0) > slow.get("win_rate", 0) * 1.2:
                insights.append("Low latency significantly improves win rate")
        
        # Worst performers to avoid
        if attribution["by_strategy"]:
            worst_strategy = min(attribution["by_strategy"].items(), 
                               key=lambda x: x[1]["pnl"])
            if worst_strategy[1]["pnl"] < -100:
                insights.append(f"WARNING: {worst_strategy[0]} losing money ({worst_strategy[1]['pnl']:.2f})")
        
        return insights
    
    def generate_report(self) -> Dict:
        """Generate complete attribution report"""
        
        # Load data
        trades = self.load_audit_logs()
        daily_scores = self.load_daily_scores()
        
        # Analyze attribution
        attribution = self.analyze_attribution(trades)
        
        # Find insights
        insights = self.find_insights(attribution)
        
        # Create report
        report = {
            "generated_at": datetime.now().isoformat(),
            "period": "last_24h",
            "summary": {
                "total_pnl": attribution["total_pnl"],
                "total_trades": attribution["total_trades"],
                "avg_pnl_per_trade": attribution["total_pnl"] / max(attribution["total_trades"], 1)
            },
            "attribution": attribution,
            "insights": insights,
            "recommendations": self.generate_recommendations(attribution, insights)
        }
        
        # Save report
        self.save_report(report)
        
        return report
    
    def generate_recommendations(self, attribution: Dict, insights: List[str]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Strategy recommendations
        if attribution["by_strategy"]:
            sorted_strategies = sorted(attribution["by_strategy"].items(), 
                                     key=lambda x: x[1]["pnl"], reverse=True)
            if sorted_strategies:
                recommendations.append(f"Focus on {sorted_strategies[0][0]} strategy")
                if len(sorted_strategies) > 1 and sorted_strategies[-1][1]["pnl"] < 0:
                    recommendations.append(f"Consider pausing {sorted_strategies[-1][0]} strategy")
        
        # Time recommendations
        if attribution["by_hour"]:
            best_time = max(attribution["by_hour"].items(), key=lambda x: x[1]["pnl"])
            recommendations.append(f"Increase position sizes during {best_time[0]} sessions")
        
        # Symbol recommendations
        if attribution["by_symbol"]:
            sorted_symbols = sorted(attribution["by_symbol"].items(), 
                                  key=lambda x: x[1]["pnl"], reverse=True)
            if len(sorted_symbols) >= 3:
                top_3 = [s[0] for s in sorted_symbols[:3]]
                recommendations.append(f"Focus on top performers: {', '.join(top_3)}")
        
        # Edge recommendations
        low_edge_pnl = attribution["by_edge"].get("Low", {}).get("pnl", 0)
        if low_edge_pnl < 0:
            recommendations.append("Increase minimum edge threshold - low edge trades losing money")
        
        # Latency recommendations
        slow_win_rate = attribution["by_latency"].get("VerySlow", {}).get("win_rate", 0)
        if slow_win_rate < 0.4:
            recommendations.append("Optimize latency - slow trades have poor win rate")
        
        return recommendations
    
    def save_report(self, report: Dict):
        """Save attribution report"""
        report_file = Path("reports/profit_attribution.json")
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Profit attribution report saved to {report_file}")
    
    def print_report(self, report: Dict):
        """Print formatted report"""
        
        print("\n" + "="*60)
        print(" PROFIT ATTRIBUTION REPORT")
        print("="*60)
        print(f"Generated: {report['generated_at']}")
        print(f"Period: {report['period']}")
        print("-"*60)
        
        summary = report["summary"]
        print("\nSUMMARY:")
        print(f"  Total P&L: {summary['total_pnl']:.2f}")
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Avg P&L/Trade: {summary['avg_pnl_per_trade']:.2f}")
        
        attr = report["attribution"]
        
        # By Strategy
        print("\nBY STRATEGY:")
        for strategy, data in sorted(attr["by_strategy"].items(), 
                                    key=lambda x: x[1]["pnl"], reverse=True):
            print(f"  {strategy:10} P&L: {data['pnl']:8.2f} | Trades: {data['trades']:3} | Win: {data['win_rate']:.1%}")
        
        # By Symbol
        print("\nBY SYMBOL:")
        for symbol, data in sorted(attr["by_symbol"].items(), 
                                  key=lambda x: x[1]["pnl"], reverse=True)[:5]:
            print(f"  {symbol:10} P&L: {data['pnl']:8.2f} | Trades: {data['trades']:3} | Win: {data['win_rate']:.1%}")
        
        # By Time
        print("\nBY TIME:")
        for hour, data in sorted(attr["by_hour"].items(), 
                                key=lambda x: x[1]["pnl"], reverse=True):
            print(f"  {hour:10} P&L: {data['pnl']:8.2f} | Trades: {data['trades']:3} | Win: {data['win_rate']:.1%}")
        
        # By Edge
        print("\nBY EDGE:")
        for edge, data in attr["by_edge"].items():
            print(f"  {edge:10} P&L: {data['pnl']:8.2f} | Trades: {data['trades']:3} | Win: {data['win_rate']:.1%}")
        
        # Insights
        if report["insights"]:
            print("\nINSIGHTS:")
            for insight in report["insights"]:
                print(f"  • {insight}")
        
        # Recommendations
        if report["recommendations"]:
            print("\nRECOMMENDATIONS:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")
        
        print("="*60)
    
    def create_visual_charts(self, report: Dict):
        """Create visual charts (ASCII for terminal)"""
        
        print("\n" + "="*60)
        print(" VISUAL CHARTS")
        print("="*60)
        
        # P&L by Strategy Bar Chart
        print("\nP&L by Strategy:")
        attr = report["attribution"]
        
        if attr["by_strategy"]:
            max_pnl = max(abs(d["pnl"]) for d in attr["by_strategy"].values())
            scale = 40 / max(max_pnl, 1)
            
            for strategy, data in sorted(attr["by_strategy"].items(), 
                                        key=lambda x: x[1]["pnl"], reverse=True):
                pnl = data["pnl"]
                bar_len = int(abs(pnl) * scale)
                if pnl >= 0:
                    bar = "+" * bar_len
                    print(f"  {strategy:10} {bar:40} {pnl:8.2f}")
                else:
                    bar = "-" * bar_len
                    print(f"  {strategy:10} {bar:>40} {pnl:8.2f}")
        
        # Win Rate by Hour
        print("\nWin Rate by Hour:")
        for hour, data in attr["by_hour"].items():
            win_rate = data["win_rate"]
            bar_len = int(win_rate * 40)
            bar = "#" * bar_len
            print(f"  {hour:10} {bar:40} {win_rate:.1%}")
        
        print("="*60)


def main():
    """Run profit attribution analysis"""
    
    analyzer = ProfitAttribution()
    report = analyzer.generate_report()
    analyzer.print_report(report)
    analyzer.create_visual_charts(report)


if __name__ == "__main__":
    main()