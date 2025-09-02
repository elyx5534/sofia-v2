"""
Route Optimizer for Exchange Endpoints
Selects fastest route based on recent latency metrics
"""

import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """Optimizes route selection based on latency and error rates"""

    def __init__(self, prefer_fastest: bool = False, min_health_score: float = 0.7):
        self.prefer_fastest = prefer_fastest
        self.min_health_score = min_health_score

        # Track recent metrics
        self.latency_window = deque(maxlen=100)  # Last 100 measurements
        self.error_window = deque(maxlen=100)

        # Cache selected routes
        self.selected_routes = {}
        self.route_cache_ttl = 60  # seconds
        self.last_route_update = {}

        # Load latest heatmap
        self.load_heatmap()

    def load_heatmap(self) -> Dict:
        """Load latest latency heatmap"""
        heatmap_file = Path("logs/latency_heatmap.json")

        if heatmap_file.exists():
            try:
                with open(heatmap_file) as f:
                    self.heatmap = json.load(f)
                    return self.heatmap
            except Exception as e:
                logger.error(f"Failed to load heatmap: {e}")

        self.heatmap = {}
        return {}

    def calculate_health_score(self, exchange: str, endpoint: str) -> float:
        """Calculate health score for an endpoint"""
        score = 1.0

        # Get latency stats from heatmap
        if exchange in self.heatmap.get("exchanges", {}):
            endpoints = self.heatmap["exchanges"][exchange].get("endpoints", {})

            if endpoint in endpoints:
                stats = endpoints[endpoint]

                # Penalize high p50 (>100ms)
                if stats["p50"] > 100:
                    score *= 100 / stats["p50"]

                # Penalize high p95 (>500ms)
                if stats["p95"] > 500:
                    score *= 500 / stats["p95"]

                # Penalize high variance
                if stats["p95"] > 2 * stats["p50"]:
                    score *= 0.8

        # Factor in recent errors
        recent_errors = sum(
            1 for e in self.error_window if e["exchange"] == exchange and e["endpoint"] == endpoint
        )
        error_rate = recent_errors / max(len(self.error_window), 1)

        score *= 1 - error_rate

        return max(0, min(1, score))

    def get_endpoint(self, exchange: str) -> Tuple[str, Dict]:
        """Get optimal endpoint for an exchange"""

        # Check cache
        cache_key = exchange
        if cache_key in self.selected_routes:
            last_update = self.last_route_update.get(cache_key, 0)
            if time.time() - last_update < self.route_cache_ttl:
                return self.selected_routes[cache_key]

        # Default endpoints
        default_endpoints = {"binance": "rest", "btcturk": "rest", "binance_tr": "rest"}

        if not self.prefer_fastest:
            # Use default
            endpoint = default_endpoints.get(exchange, "rest")
            details = {"reason": "default", "health_score": 1.0, "p50": 0}

            result = (endpoint, details)
            self.selected_routes[cache_key] = result
            self.last_route_update[cache_key] = time.time()

            return result

        # Select fastest healthy endpoint
        best_endpoint = None
        best_score = 0
        best_p50 = float("inf")

        if exchange in self.heatmap.get("exchanges", {}):
            endpoints = self.heatmap["exchanges"][exchange].get("endpoints", {})

            for endpoint, stats in endpoints.items():
                health_score = self.calculate_health_score(exchange, endpoint)

                # Skip unhealthy endpoints
                if health_score < self.min_health_score:
                    continue

                # Prefer lower p50 with healthy score
                if stats["p50"] < best_p50:
                    best_endpoint = endpoint
                    best_score = health_score
                    best_p50 = stats["p50"]

        # Fallback to default if no healthy endpoint found
        if not best_endpoint:
            best_endpoint = default_endpoints.get(exchange, "rest")
            best_score = 0.5
            best_p50 = 100

        details = {
            "reason": "optimized" if best_score >= self.min_health_score else "fallback",
            "health_score": best_score,
            "p50": best_p50,
        }

        result = (best_endpoint, details)

        # Cache result
        self.selected_routes[cache_key] = result
        self.last_route_update[cache_key] = time.time()

        logger.info(
            f"Selected {best_endpoint} for {exchange} (score: {best_score:.2f}, p50: {best_p50:.1f}ms)"
        )

        return result

    def record_latency(self, exchange: str, endpoint: str, latency_ms: float):
        """Record observed latency"""
        self.latency_window.append(
            {
                "exchange": exchange,
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            }
        )

    def record_error(self, exchange: str, endpoint: str, error: str):
        """Record endpoint error"""
        self.error_window.append(
            {"exchange": exchange, "endpoint": endpoint, "error": error, "timestamp": time.time()}
        )

    def should_fallback(self, exchange: str, endpoint: str) -> bool:
        """Check if should fallback to alternative endpoint"""

        # Count recent errors
        recent_errors = sum(
            1
            for e in self.error_window
            if e["exchange"] == exchange
            and e["endpoint"] == endpoint
            and time.time() - e["timestamp"] < 300  # Last 5 minutes
        )

        # Fallback if too many errors
        if recent_errors >= 3:
            return True

        # Check recent latencies
        recent_latencies = [
            l["latency_ms"]
            for l in self.latency_window
            if l["exchange"] == exchange
            and l["endpoint"] == endpoint
            and time.time() - l["timestamp"] < 300
        ]

        if recent_latencies:
            avg_latency = sum(recent_latencies) / len(recent_latencies)

            # Fallback if latency too high
            if avg_latency > 1000:  # 1 second
                return True

        return False

    def get_status(self) -> Dict:
        """Get optimizer status"""
        status = {
            "prefer_fastest": self.prefer_fastest,
            "min_health_score": self.min_health_score,
            "selected_routes": {},
            "recent_metrics": {
                "latency_samples": len(self.latency_window),
                "error_samples": len(self.error_window),
            },
        }

        # Add selected routes with details
        for exchange, (endpoint, details) in self.selected_routes.items():
            status["selected_routes"][exchange] = {"endpoint": endpoint, **details}

        return status


def test_optimizer():
    """Test route optimizer"""

    # Create optimizer
    optimizer = RouteOptimizer(prefer_fastest=True)

    print("=" * 60)
    print(" ROUTE OPTIMIZER TEST")
    print("=" * 60)

    # Test endpoint selection
    for exchange in ["binance", "btcturk", "binance_tr"]:
        endpoint, details = optimizer.get_endpoint(exchange)
        print(f"\n{exchange}:")
        print(f"  Endpoint: {endpoint}")
        print(f"  Reason: {details['reason']}")
        print(f"  Health Score: {details['health_score']:.2f}")
        print(f"  P50: {details['p50']:.1f}ms")

    # Simulate some errors
    optimizer.record_error("binance", "rest", "timeout")
    optimizer.record_error("binance", "rest", "connection refused")
    optimizer.record_error("binance", "rest", "rate limited")

    # Check if should fallback
    should_fallback = optimizer.should_fallback("binance", "rest")
    print(f"\nShould fallback for binance/rest: {should_fallback}")

    # Get status
    status = optimizer.get_status()
    print("\nOptimizer Status:")
    print(json.dumps(status, indent=2))

    print("=" * 60)


if __name__ == "__main__":
    test_optimizer()
