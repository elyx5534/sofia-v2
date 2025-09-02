"""
Symbol Selector for Time-of-Day Trading
Selects optimal symbols based on liquidity, spread, latency for AM/PM sessions
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SymbolSelector:
    """Selects optimal symbols for different trading sessions"""

    def __init__(self):
        # Feature weights (tunable)
        self.weights = {
            "spread": -0.3,  # Lower spread is better (negative weight)
            "volume": 0.3,  # Higher volume is better
            "latency": -0.2,  # Lower latency is better (negative weight)
            "volatility": 0.2,  # Moderate volatility is good
        }

        # Session definitions (Istanbul time)
        self.sessions = {
            "AM": {"start": 10, "end": 14, "description": "Morning Session"},
            "PM": {"start": 14, "end": 18, "description": "Afternoon Session"},
        }

        # Default symbols to evaluate
        self.candidate_symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "BNBUSDT",
            "SOLUSDT",
            "ADAUSDT",
            "DOTUSDT",
            "AVAXUSDT",
            "MATICUSDT",
            "LINKUSDT",
            "UNIUSDT",
            "ATOMUSDT",
            "NEARUSDT",
        ]

        self.top_n = 3  # Select top 3 symbols per session

    def load_orderbook_data(self) -> Dict:
        """Load orderbook snapshots for spread analysis"""
        orderbook_data = {}

        # Look for orderbook snapshots
        snapshot_dir = Path("logs/orderbook_snapshots")
        if snapshot_dir.exists():
            for file in snapshot_dir.glob("*.jsonl"):
                try:
                    with open(file) as f:
                        for line in f:
                            data = json.loads(line)
                            symbol = data.get("symbol")
                            if symbol:
                                if symbol not in orderbook_data:
                                    orderbook_data[symbol] = []
                                orderbook_data[symbol].append(data)
                except:
                    continue

        # Generate mock data if no snapshots
        if not orderbook_data:
            for symbol in self.candidate_symbols:
                orderbook_data[symbol] = self._generate_mock_orderbook(symbol)

        return orderbook_data

    def _generate_mock_orderbook(self, symbol: str) -> List[Dict]:
        """Generate mock orderbook data for testing"""
        data = []

        # Different characteristics for different symbols
        if "BTC" in symbol:
            base_spread = 5
            base_volume = 1000000
        elif "ETH" in symbol:
            base_spread = 7
            base_volume = 500000
        elif "SOL" in symbol:
            base_spread = 10
            base_volume = 300000
        else:
            base_spread = 15
            base_volume = 100000

        for hour in range(24):
            # Simulate intraday patterns
            if 10 <= hour < 14:  # AM session
                volume_mult = 1.2
                spread_mult = 0.9
            elif 14 <= hour < 18:  # PM session
                volume_mult = 1.5
                spread_mult = 0.8
            else:
                volume_mult = 0.8
                spread_mult = 1.2

            data.append(
                {
                    "symbol": symbol,
                    "hour": hour,
                    "spread_bps": base_spread * spread_mult * np.random.uniform(0.8, 1.2),
                    "volume": base_volume * volume_mult * np.random.uniform(0.7, 1.3),
                    "bid_depth": np.random.uniform(10000, 100000),
                    "ask_depth": np.random.uniform(10000, 100000),
                }
            )

        return data

    def load_latency_data(self) -> Dict:
        """Load latency heatmap data"""
        latency_file = Path("logs/latency_heatmap.json")

        if latency_file.exists():
            try:
                with open(latency_file) as f:
                    return json.load(f)
            except:
                pass

        # Generate mock latency data
        latency_data = {}
        for symbol in self.candidate_symbols:
            latency_data[symbol] = {
                "p50": np.random.uniform(20, 100),
                "p95": np.random.uniform(50, 200),
            }

        return latency_data

    def load_performance_data(self) -> Dict:
        """Load historical performance data"""
        performance = {}

        # Load daily scores
        daily_score_file = Path("reports/daily_score.json")
        if daily_score_file.exists():
            try:
                with open(daily_score_file) as f:
                    daily_score = json.load(f)
                    # Extract symbol-specific metrics if available
                    # For now, use aggregate metrics
            except:
                pass

        # Load strategy lab results
        for symbol in self.candidate_symbols:
            # Mock performance metrics
            performance[symbol] = {
                "win_rate": np.random.uniform(0.4, 0.7),
                "avg_pnl_pct": np.random.uniform(-0.5, 2.0),
                "trades": np.random.randint(0, 50),
            }

        return performance

    def calculate_features(self, symbol: str, session: str) -> Dict:
        """Calculate features for a symbol in a specific session"""

        features = {
            "symbol": symbol,
            "session": session,
            "spread": 0,
            "volume": 0,
            "latency": 0,
            "volatility": 0,
        }

        # Load data
        orderbook_data = self.load_orderbook_data()
        latency_data = self.load_latency_data()

        # Calculate spread for session hours
        if symbol in orderbook_data:
            session_hours = range(self.sessions[session]["start"], self.sessions[session]["end"])
            spreads = []
            volumes = []

            for data_point in orderbook_data[symbol]:
                if data_point.get("hour", 0) in session_hours:
                    spreads.append(data_point.get("spread_bps", 20))
                    volumes.append(data_point.get("volume", 0))

            if spreads:
                features["spread"] = np.median(spreads)
                features["volume"] = np.mean(volumes)

                # Calculate volatility (std of spreads)
                features["volatility"] = np.std(spreads) if len(spreads) > 1 else 0

        # Get latency
        if symbol in latency_data:
            features["latency"] = latency_data[symbol].get("p50", 100)

        return features

    def calculate_score(self, features: Dict) -> float:
        """Calculate composite score for a symbol"""

        # Normalize features
        normalized = {}

        # Spread: lower is better (0-100 bps range)
        normalized["spread"] = 1 - min(features["spread"] / 100, 1)

        # Volume: higher is better (log scale)
        normalized["volume"] = np.log10(max(features["volume"], 1)) / 7  # Normalize to ~0-1

        # Latency: lower is better (0-200ms range)
        normalized["latency"] = 1 - min(features["latency"] / 200, 1)

        # Volatility: moderate is best (target ~10 bps std)
        vol_target = 10
        vol_diff = abs(features["volatility"] - vol_target)
        normalized["volatility"] = 1 - min(vol_diff / vol_target, 1)

        # Calculate weighted score
        score = 0
        for feature, weight in self.weights.items():
            score += normalized.get(feature, 0) * abs(weight)

        return score

    def select_symbols(self) -> Dict:
        """Select optimal symbols for each session"""

        plan = {
            "generated_at": datetime.now().isoformat(),
            "sessions": {},
            "features": {},
            "rankings": {},
        }

        for session_name, session_config in self.sessions.items():
            # Calculate scores for all symbols
            symbol_scores = []

            for symbol in self.candidate_symbols:
                features = self.calculate_features(symbol, session_name)
                score = self.calculate_score(features)

                symbol_scores.append({"symbol": symbol, "score": score, "features": features})

                # Store features for reporting
                if symbol not in plan["features"]:
                    plan["features"][symbol] = {}
                plan["features"][symbol][session_name] = features

            # Sort by score
            symbol_scores.sort(key=lambda x: x["score"], reverse=True)

            # Select top N
            selected = symbol_scores[: self.top_n]

            # Store in plan
            plan["sessions"][session_name] = {
                "start": session_config["start"],
                "end": session_config["end"],
                "description": session_config["description"],
                "symbols": [s["symbol"] for s in selected],
                "scores": {s["symbol"]: s["score"] for s in selected},
            }

            # Store full rankings
            plan["rankings"][session_name] = [
                {"symbol": s["symbol"], "score": s["score"]} for s in symbol_scores
            ]

        # Add recommendations
        plan["recommendations"] = self._generate_recommendations(plan)

        # Save plan
        self.save_plan(plan)

        return plan

    def _generate_recommendations(self, plan: Dict) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Check if AM and PM selections differ
        am_symbols = set(plan["sessions"]["AM"]["symbols"])
        pm_symbols = set(plan["sessions"]["PM"]["symbols"])

        if am_symbols != pm_symbols:
            recommendations.append(
                f"Switch symbols between sessions: AM {am_symbols} → PM {pm_symbols}"
            )

        # Check for low-scoring symbols
        for session, rankings in plan["rankings"].items():
            if rankings and rankings[0]["score"] < 0.5:
                recommendations.append(
                    f"Warning: Low scores in {session} session, consider wider symbol search"
                )

        # Volume recommendations
        recommendations.append("Monitor actual fill rates during selected sessions")
        recommendations.append("Adjust weights if fill rates don't improve")

        return recommendations

    def save_plan(self, plan: Dict):
        """Save symbol plan to file"""

        plan_file = Path("reports/symbol_plan.json")
        plan_file.parent.mkdir(exist_ok=True)

        with open(plan_file, "w") as f:
            json.dump(plan, f, indent=2)

        logger.info(f"Symbol plan saved to {plan_file}")

    def print_plan(self, plan: Dict):
        """Print formatted plan"""

        print("\n" + "=" * 60)
        print(" SYMBOL SELECTION PLAN")
        print("=" * 60)
        print(f"Generated: {plan['generated_at']}")
        print("-" * 60)

        for session_name, session_data in plan["sessions"].items():
            print(f"\n{session_name} SESSION ({session_data['start']}:00-{session_data['end']}:00)")
            print("-" * 30)

            for i, symbol in enumerate(session_data["symbols"], 1):
                score = session_data["scores"][symbol]
                features = plan["features"][symbol][session_name]

                print(f"  {i}. {symbol:10} Score: {score:.3f}")
                print(f"     Spread: {features['spread']:.1f} bps")
                print(f"     Volume: {features['volume']:.0f}")
                print(f"     Latency: {features['latency']:.0f} ms")
                print(f"     Volatility: {features['volatility']:.1f}")

        if plan.get("recommendations"):
            print("\nRECOMMENDATIONS:")
            for rec in plan["recommendations"]:
                print(f"  • {rec}")

        print("=" * 60)


def main():
    """Run symbol selector"""

    selector = SymbolSelector()
    plan = selector.select_symbols()
    selector.print_plan(plan)


if __name__ == "__main__":
    main()
