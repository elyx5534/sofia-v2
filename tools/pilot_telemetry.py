"""
Pilot Telemetry - Live monitoring during pilot trading
Collects metrics every 5 seconds
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PilotTelemetry:
    """Real-time telemetry during pilot trading"""

    def __init__(self):
        self.telemetry_file = Path("logs/pilot_telemetry.json")
        self.telemetry_file.parent.mkdir(exist_ok=True)

        self.live_config_file = Path("config/live.yaml")
        self.running = False
        self.thread = None

        # Metrics storage
        self.metrics = {"session_start": None, "last_update": None, "current": {}, "history": []}

    def load_live_config(self) -> Dict:
        """Load live trading configuration"""
        if not self.live_config_file.exists():
            return {}

        import yaml

        with open(self.live_config_file) as f:
            return yaml.safe_load(f)

    def collect_metrics(self) -> Dict:
        """Collect current metrics"""
        timestamp = datetime.now()
        config = self.load_live_config()

        # Mock metrics - in production, connect to actual trading system

        metrics = {
            "timestamp": timestamp.isoformat(),
            "caps_usage": self.get_caps_usage(config),
            "tl_pnl_live": self.get_live_pnl(),
            "ev_rejected": self.get_ev_rejects(),
            "latency": self.get_latency_metrics(),
            "active_positions": self.get_position_count(),
            "health": self.check_health(),
        }

        return metrics

    def get_caps_usage(self, config: Dict) -> Dict:
        """Get capital usage metrics"""
        max_notional = config.get("max_notional_tl", 1000)

        # Mock current usage
        import random

        current_notional = random.uniform(0, max_notional * 0.8)

        return {
            "current_notional_tl": round(current_notional, 2),
            "max_notional_tl": max_notional,
            "usage_pct": round((current_notional / max_notional) * 100, 1),
            "per_trade_cap_tl": config.get("per_trade_tl_cap", 250),
        }

    def get_live_pnl(self) -> Dict:
        """Get live P&L metrics"""
        # Mock P&L data - in production, read from trading engine
        import random

        gross_pnl = random.uniform(-50, 150)
        fees = abs(gross_pnl) * 0.002  # 0.2% fees
        tax = max(0, gross_pnl * 0.1) if gross_pnl > 0 else 0  # 10% tax on profit

        return {
            "gross_tl": round(gross_pnl, 2),
            "fees_tl": round(fees, 2),
            "tax_tl": round(tax, 2),
            "net_tl": round(gross_pnl - fees - tax, 2),
        }

    def get_ev_rejects(self) -> Dict:
        """Get EV gate rejection metrics"""
        # Mock data
        import random

        total_evaluated = random.randint(50, 200)
        rejected = random.randint(5, 30)

        return {
            "total_evaluated": total_evaluated,
            "rejected_count": rejected,
            "rejection_rate": round(rejected / max(total_evaluated, 1), 3),
            "last_hour_rejects": random.randint(2, 10),
        }

    def get_latency_metrics(self) -> Dict:
        """Get latency metrics"""
        import numpy as np

        # Generate mock latencies
        latencies = np.random.gamma(2, 30, 100)  # Gamma distribution for realistic latency

        return {
            "p50_ms": round(np.percentile(latencies, 50), 0),
            "p95_ms": round(np.percentile(latencies, 95), 0),
            "p99_ms": round(np.percentile(latencies, 99), 0),
            "mean_ms": round(np.mean(latencies), 0),
        }

    def get_position_count(self) -> int:
        """Get active position count"""
        import random

        return random.randint(0, 5)

    def check_health(self) -> str:
        """Check system health"""
        # Mock health check
        import random

        if random.random() > 0.95:
            return "DEGRADED"
        elif random.random() > 0.99:
            return "CRITICAL"
        return "OK"

    def update_telemetry(self):
        """Update telemetry data"""
        metrics = self.collect_metrics()

        # Update current metrics
        self.metrics["current"] = metrics
        self.metrics["last_update"] = datetime.now().isoformat()

        # Add to history (keep last 1000 entries)
        self.metrics["history"].append(metrics)
        if len(self.metrics["history"]) > 1000:
            self.metrics["history"] = self.metrics["history"][-1000:]

        # Save to file
        self.save_telemetry()

        # Log summary
        pnl = metrics["tl_pnl_live"]["net_tl"]
        usage = metrics["caps_usage"]["usage_pct"]
        ev_rate = metrics["ev_rejected"]["rejection_rate"]

        logger.info(f"Telemetry: P&L={pnl:.2f} TL | Usage={usage:.1f}% | EV_reject={ev_rate:.1%}")

    def save_telemetry(self):
        """Save telemetry to file"""
        with open(self.telemetry_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def telemetry_loop(self):
        """Main telemetry collection loop"""
        logger.info("Pilot telemetry started")

        while self.running:
            try:
                self.update_telemetry()
            except Exception as e:
                logger.error(f"Telemetry error: {e}")

            # Wait 5 seconds
            time.sleep(5)

        logger.info("Pilot telemetry stopped")

    def start(self):
        """Start telemetry collection"""
        if self.running:
            logger.warning("Telemetry already running")
            return

        self.running = True
        self.metrics["session_start"] = datetime.now().isoformat()

        # Start collection thread
        self.thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.thread.start()

        logger.info("Telemetry collection started")

    def stop(self):
        """Stop telemetry collection"""
        self.running = False

        if self.thread:
            self.thread.join(timeout=10)

        # Final save
        self.save_telemetry()
        logger.info("Telemetry collection stopped")

    def get_summary(self) -> Dict:
        """Get telemetry summary"""
        if not self.metrics["history"]:
            return {}

        # Calculate summary statistics
        pnls = [m["tl_pnl_live"]["net_tl"] for m in self.metrics["history"]]
        latencies_p50 = [m["latency"]["p50_ms"] for m in self.metrics["history"]]
        ev_rejects = [m["ev_rejected"]["rejected_count"] for m in self.metrics["history"]]

        import numpy as np

        return {
            "duration_minutes": len(self.metrics["history"]) * 5 / 60,
            "pnl": {
                "current": pnls[-1] if pnls else 0,
                "min": min(pnls) if pnls else 0,
                "max": max(pnls) if pnls else 0,
                "mean": np.mean(pnls) if pnls else 0,
            },
            "latency": {
                "mean_p50": np.mean(latencies_p50) if latencies_p50 else 0,
                "max_p50": max(latencies_p50) if latencies_p50 else 0,
            },
            "ev_rejects": {
                "total": sum(ev_rejects) if ev_rejects else 0,
                "rate": (
                    np.mean([m["ev_rejected"]["rejection_rate"] for m in self.metrics["history"]])
                    if self.metrics["history"]
                    else 0
                ),
            },
        }

    def print_status(self):
        """Print current telemetry status"""
        if not self.metrics.get("current"):
            print("No telemetry data available")
            return

        current = self.metrics["current"]

        print("\n" + "=" * 60)
        print(" PILOT TELEMETRY STATUS")
        print("=" * 60)
        print(f"Last Update: {current['timestamp']}")
        print(f"Health: {current['health']}")

        print("\nP&L Status:")
        pnl = current["tl_pnl_live"]
        print(f"  Net P&L: {pnl['net_tl']:.2f} TL")
        print(f"  Gross: {pnl['gross_tl']:.2f} TL")
        print(f"  Fees: {pnl['fees_tl']:.2f} TL")
        print(f"  Tax: {pnl['tax_tl']:.2f} TL")

        print("\nCapital Usage:")
        caps = current["caps_usage"]
        print(f"  Current: {caps['current_notional_tl']:.2f} / {caps['max_notional_tl']} TL")
        print(f"  Usage: {caps['usage_pct']:.1f}%")

        print("\nEV Gate:")
        ev = current["ev_rejected"]
        print(f"  Evaluated: {ev['total_evaluated']}")
        print(f"  Rejected: {ev['rejected_count']} ({ev['rejection_rate']:.1%})")

        print("\nLatency:")
        lat = current["latency"]
        print(f"  p50: {lat['p50_ms']:.0f}ms")
        print(f"  p95: {lat['p95_ms']:.0f}ms")

        print("=" * 60)


def main():
    """Run telemetry or show status"""
    import sys

    telemetry = PilotTelemetry()

    if len(sys.argv) > 1 and sys.argv[1] == "start":
        print("Starting pilot telemetry...")
        telemetry.start()

        try:
            # Run for demonstration (normally runs until stopped)
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopping telemetry...")

        telemetry.stop()

        # Print summary
        summary = telemetry.get_summary()
        print("\nSession Summary:")
        print(f"  Duration: {summary.get('duration_minutes', 0):.1f} minutes")
        print(f"  Final P&L: {summary.get('pnl', {}).get('current', 0):.2f} TL")
        print(f"  Total EV Rejects: {summary.get('ev_rejects', {}).get('total', 0)}")
    else:
        # Just show current status
        telemetry.print_status()


if __name__ == "__main__":
    main()
