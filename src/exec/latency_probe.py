"""
Latency Probe for Exchange Endpoints
Measures p50, p95, max latency for each exchange/endpoint
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp
import numpy as np

logger = logging.getLogger(__name__)


class LatencyProbe:
    """Probes exchange endpoints for latency metrics"""

    def __init__(self):
        self.endpoints = {
            "binance": {
                "rest": "https://api.binance.com",
                "rest_alt": "https://api1.binance.com",
                "ping": "/api/v3/ping",
                "orderbook": "/api/v3/depth?symbol=BTCUSDT&limit=5",
            },
            "btcturk": {
                "rest": "https://api.btcturk.com",
                "ping": "/api/v1/ping",
                "orderbook": "/api/v2/orderbook?pairSymbol=BTCUSDT&limit=5",
            },
            "binance_tr": {
                "rest": "https://trbinance.com",
                "rest_alt": "https://api.trbinance.com",
                "ping": "/api/v3/ping",
                "orderbook": "/api/v3/depth?symbol=BTCTRY&limit=5",
            },
        }
        self.samples_per_endpoint = 20
        self.timeout = 5.0
        self.results = {}

    async def measure_endpoint(self, exchange: str, endpoint_type: str, url: str) -> List[float]:
        """Measure latency for a single endpoint"""
        latencies = []
        async with aiohttp.ClientSession() as session:
            for _ in range(self.samples_per_endpoint):
                try:
                    start = time.perf_counter()
                    async with session.get(url, timeout=self.timeout) as response:
                        await response.text()
                    latency_ms = (time.perf_counter() - start) * 1000
                    latencies.append(latency_ms)
                    await asyncio.sleep(0.1)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout for {exchange}/{endpoint_type}")
                    latencies.append(self.timeout * 1000)
                except Exception as e:
                    logger.error(f"Error probing {exchange}/{endpoint_type}: {e}")
                    latencies.append(self.timeout * 1000)
        return latencies

    def calculate_stats(self, latencies: List[float]) -> Dict:
        """Calculate latency statistics"""
        if not latencies:
            return {"p50": 0, "p95": 0, "max": 0, "mean": 0, "samples": 0}
        return {
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
            "max": float(max(latencies)),
            "mean": float(np.mean(latencies)),
            "samples": len(latencies),
        }

    async def probe_all(self) -> Dict:
        """Probe all endpoints and collect metrics"""
        self.results = {"timestamp": datetime.now().isoformat(), "exchanges": {}}
        for exchange, config in self.endpoints.items():
            logger.info(f"Probing {exchange}...")
            self.results["exchanges"][exchange] = {"endpoints": {}}
            if "ping" in config:
                ping_url = config["rest"] + config["ping"]
                latencies = await self.measure_endpoint(exchange, "ping", ping_url)
                self.results["exchanges"][exchange]["endpoints"]["ping"] = self.calculate_stats(
                    latencies
                )
                if "rest_alt" in config:
                    alt_ping_url = config["rest_alt"] + config["ping"]
                    alt_latencies = await self.measure_endpoint(exchange, "ping_alt", alt_ping_url)
                    self.results["exchanges"][exchange]["endpoints"]["ping_alt"] = (
                        self.calculate_stats(alt_latencies)
                    )
            if "orderbook" in config:
                orderbook_url = config["rest"] + config["orderbook"]
                latencies = await self.measure_endpoint(exchange, "orderbook", orderbook_url)
                self.results["exchanges"][exchange]["endpoints"]["orderbook"] = (
                    self.calculate_stats(latencies)
                )
        self.save_heatmap()
        return self.results

    def save_heatmap(self):
        """Save latency heatmap to file"""
        heatmap_file = Path("logs/latency_heatmap.json")
        heatmap_file.parent.mkdir(exist_ok=True)
        with open(heatmap_file, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Latency heatmap saved to {heatmap_file}")

    def print_heatmap(self):
        """Print formatted heatmap"""
        print("\n" + "=" * 60)
        print(" LATENCY HEATMAP")
        print("=" * 60)
        print(f"Timestamp: {self.results['timestamp']}")
        print("-" * 60)
        for exchange, data in self.results["exchanges"].items():
            print(f"\n{exchange.upper()}")
            print("-" * 30)
            for endpoint, stats in data["endpoints"].items():
                print(
                    f"  {endpoint:12} p50:{stats['p50']:6.1f}ms  p95:{stats['p95']:6.1f}ms  max:{stats['max']:6.1f}ms"
                )
        print("=" * 60)

    def get_fastest_endpoint(self, exchange: str) -> Tuple[str, float]:
        """Get fastest endpoint for an exchange based on p50"""
        if exchange not in self.results.get("exchanges", {}):
            return (None, float("inf"))
        endpoints = self.results["exchanges"][exchange]["endpoints"]
        if not endpoints:
            return (None, float("inf"))
        fastest = None
        min_p50 = float("inf")
        for endpoint, stats in endpoints.items():
            if stats["p50"] < min_p50:
                min_p50 = stats["p50"]
                fastest = endpoint
        return (fastest, min_p50)


async def main():
    """Run latency probe"""
    probe = LatencyProbe()
    print("Starting latency probe...")
    await probe.probe_all()
    probe.print_heatmap()
    print("\nFastest Endpoints:")
    for exchange in ["binance", "btcturk", "binance_tr"]:
        endpoint, p50 = probe.get_fastest_endpoint(exchange)
        if endpoint:
            print(f"  {exchange}: {endpoint} ({p50:.1f}ms)")


if __name__ == "__main__":
    asyncio.run(main())
