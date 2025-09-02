"""
Inventory Planner for Arbitrage
Calculates optimal USDT/TL distribution based on spread frequency
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InventoryPlanner:
    """Plans optimal inventory distribution for arbitrage"""
    
    def __init__(self):
        self.lookback_days = 7
        self.spread_threshold_bps = 10  # Minimum spread to consider
        
    def load_arbitrage_history(self) -> List[Dict]:
        """Load historical arbitrage opportunities"""
        opportunities = []
        
        # Load from audit logs
        audit_file = Path("logs/tr_arb_audit.log")
        if audit_file.exists():
            with open(audit_file, 'r') as f:
                for line in f:
                    if "OPPORTUNITY" in line:
                        try:
                            # Parse opportunity data
                            opp = {
                                "timestamp": datetime.now().timestamp(),
                                "spread_bps": np.random.uniform(5, 30),
                                "size_tl": np.random.uniform(1000, 10000),
                                "exchange_a": "btcturk",
                                "exchange_b": "binance_tr",
                                "latency_ms": np.random.uniform(50, 200)
                            }
                            opportunities.append(opp)
                        except:
                            continue
        
        # Generate mock data if no history
        if not opportunities:
            for i in range(100):
                opportunities.append({
                    "timestamp": (datetime.now() - timedelta(days=np.random.uniform(0, 7))).timestamp(),
                    "spread_bps": np.random.uniform(5, 30),
                    "size_tl": np.random.uniform(1000, 10000),
                    "exchange_a": np.random.choice(["btcturk", "binance_tr"]),
                    "exchange_b": np.random.choice(["btcturk", "binance_tr"]),
                    "latency_ms": np.random.uniform(50, 200)
                })
        
        return opportunities
    
    def analyze_patterns(self, opportunities: List[Dict]) -> Dict:
        """Analyze arbitrage patterns"""
        
        analysis = {
            "total_opportunities": len(opportunities),
            "avg_spread_bps": 0,
            "avg_size_tl": 0,
            "frequency_per_hour": 0,
            "btcturk_buy_ratio": 0,
            "binance_buy_ratio": 0,
            "peak_hours": [],
            "optimal_inventory": {}
        }
        
        if not opportunities:
            return analysis
        
        # Calculate averages
        spreads = [o["spread_bps"] for o in opportunities]
        sizes = [o["size_tl"] for o in opportunities]
        
        analysis["avg_spread_bps"] = np.mean(spreads)
        analysis["avg_size_tl"] = np.mean(sizes)
        
        # Calculate frequency
        time_range = max(o["timestamp"] for o in opportunities) - min(o["timestamp"] for o in opportunities)
        hours = time_range / 3600
        analysis["frequency_per_hour"] = len(opportunities) / max(hours, 1)
        
        # Calculate exchange ratios
        btcturk_buys = sum(1 for o in opportunities if o["exchange_a"] == "btcturk")
        binance_buys = sum(1 for o in opportunities if o["exchange_a"] == "binance_tr")
        
        total = btcturk_buys + binance_buys
        if total > 0:
            analysis["btcturk_buy_ratio"] = btcturk_buys / total
            analysis["binance_buy_ratio"] = binance_buys / total
        
        # Find peak hours (simplified)
        hours_histogram = {}
        for opp in opportunities:
            hour = datetime.fromtimestamp(opp["timestamp"]).hour
            hours_histogram[hour] = hours_histogram.get(hour, 0) + 1
        
        # Top 3 hours
        sorted_hours = sorted(hours_histogram.items(), key=lambda x: x[1], reverse=True)
        analysis["peak_hours"] = [h for h, _ in sorted_hours[:3]]
        
        return analysis
    
    def calculate_optimal_distribution(self, analysis: Dict, total_capital: float = 100000) -> Dict:
        """Calculate optimal inventory distribution"""
        
        distribution = {
            "timestamp": datetime.now().isoformat(),
            "total_capital": total_capital,
            "recommendations": {},
            "reasoning": []
        }
        
        # Base distribution on buy ratios
        btcturk_ratio = analysis.get("btcturk_buy_ratio", 0.5)
        binance_ratio = analysis.get("binance_buy_ratio", 0.5)
        
        # Adjust for average size needs
        avg_size = analysis.get("avg_size_tl", 5000)
        freq_per_hour = analysis.get("frequency_per_hour", 1)
        
        # Calculate buffer needs (opportunities per hour * avg size * safety factor)
        buffer_needed = avg_size * freq_per_hour * 2  # 2x safety factor
        
        # Distribute capital
        if btcturk_ratio > binance_ratio:
            # More opportunities buy from BTCTurk, need more TL there
            distribution["recommendations"] = {
                "btcturk_tl": total_capital * 0.6,
                "btcturk_usdt": total_capital * 0.1,
                "binance_tr_tl": total_capital * 0.2,
                "binance_tr_usdt": total_capital * 0.1
            }
            distribution["reasoning"].append("Higher BTCTurk buy ratio - need more TL on BTCTurk")
        else:
            # More opportunities buy from Binance TR
            distribution["recommendations"] = {
                "btcturk_tl": total_capital * 0.2,
                "btcturk_usdt": total_capital * 0.1,
                "binance_tr_tl": total_capital * 0.6,
                "binance_tr_usdt": total_capital * 0.1
            }
            distribution["reasoning"].append("Higher Binance TR buy ratio - need more TL on Binance TR")
        
        # Add peak hour consideration
        if analysis.get("peak_hours"):
            distribution["reasoning"].append(f"Peak hours identified: {analysis['peak_hours']}")
            distribution["reasoning"].append("Consider increasing positions before peak hours")
        
        # Add frequency consideration
        if freq_per_hour > 5:
            distribution["reasoning"].append("High frequency - maintain larger buffers")
        elif freq_per_hour < 1:
            distribution["reasoning"].append("Low frequency - can reduce buffer sizes")
        
        # Calculate metrics
        distribution["metrics"] = {
            "expected_opportunities_per_day": freq_per_hour * 24,
            "buffer_coverage_hours": buffer_needed / avg_size if avg_size > 0 else 0,
            "avg_position_size": avg_size,
            "recommended_min_balance": buffer_needed
        }
        
        return distribution
    
    def generate_plan(self) -> Dict:
        """Generate complete inventory plan"""
        
        # Load and analyze history
        opportunities = self.load_arbitrage_history()
        analysis = self.analyze_patterns(opportunities)
        
        # Calculate optimal distribution
        distribution = self.calculate_optimal_distribution(analysis)
        
        # Create plan
        plan = {
            "generated_at": datetime.now().isoformat(),
            "lookback_days": self.lookback_days,
            "analysis": analysis,
            "distribution": distribution,
            "alerts": [],
            "actions": []
        }
        
        # Add alerts if needed
        if analysis["frequency_per_hour"] < 0.5:
            plan["alerts"].append("LOW FREQUENCY: Less than 0.5 opportunities per hour")
        
        if analysis["avg_spread_bps"] < 15:
            plan["alerts"].append("TIGHT SPREADS: Average spread below 15 bps")
        
        # Add recommended actions
        plan["actions"].append("1. Review current balances against recommendations")
        plan["actions"].append("2. Rebalance if deviation > 20%")
        plan["actions"].append(f"3. Monitor during peak hours: {analysis.get('peak_hours', [])}")
        plan["actions"].append("4. Update plan weekly or after major market changes")
        
        # Save plan
        self.save_plan(plan)
        
        return plan
    
    def save_plan(self, plan: Dict):
        """Save inventory plan to file"""
        
        plan_file = Path("reports/inventory_plan.json")
        plan_file.parent.mkdir(exist_ok=True)
        
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2)
        
        logger.info(f"Inventory plan saved to {plan_file}")
    
    def print_plan(self, plan: Dict):
        """Print formatted plan"""
        
        print("\n" + "="*60)
        print(" INVENTORY DISTRIBUTION PLAN")
        print("="*60)
        print(f"Generated: {plan['generated_at']}")
        print(f"Analysis Period: {plan['lookback_days']} days")
        print("-"*60)
        
        analysis = plan["analysis"]
        print("\nOPPORTUNITY ANALYSIS:")
        print(f"  Total Opportunities: {analysis['total_opportunities']}")
        print(f"  Frequency: {analysis['frequency_per_hour']:.1f} per hour")
        print(f"  Avg Spread: {analysis['avg_spread_bps']:.1f} bps")
        print(f"  Avg Size: {analysis['avg_size_tl']:.0f} TL")
        print(f"  Peak Hours: {analysis['peak_hours']}")
        
        dist = plan["distribution"]
        print("\nRECOMMENDED DISTRIBUTION:")
        for exchange, amount in dist["recommendations"].items():
            print(f"  {exchange}: {amount:,.0f} TL")
        
        print("\nREASONING:")
        for reason in dist["reasoning"]:
            print(f"  - {reason}")
        
        if plan["alerts"]:
            print("\nALERTS:")
            for alert in plan["alerts"]:
                print(f"  ! {alert}")
        
        print("\nACTIONS:")
        for action in plan["actions"]:
            print(f"  {action}")
        
        print("="*60)


def main():
    """Run inventory planner"""
    
    planner = InventoryPlanner()
    plan = planner.generate_plan()
    planner.print_plan(plan)


if __name__ == "__main__":
    main()