"""
Anomaly Detector
Detects feed anomalies, P&L spikes, and clock drift
"""

import json
import logging
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects various anomalies in trading system"""

    def __init__(self, config: Dict = None):
        if config is None:
            config = self.load_config()
        self.z_threshold = config.get("z_threshold", 3.0)
        self.spike_threshold = config.get("spike_threshold", 5.0)
        self.clock_drift_tolerance_ms = config.get("clock_drift_tolerance_ms", 1000)
        self.price_window = config.get("price_window", 100)
        self.pnl_window = config.get("pnl_window", 50)
        self.price_history = {}
        self.pnl_history = deque(maxlen=self.pnl_window)
        self.latency_history = deque(maxlen=100)
        self.clock_offsets = deque(maxlen=20)
        self.anomaly_counts = {
            "price_spike": 0,
            "pnl_spike": 0,
            "clock_drift": 0,
            "stale_feed": 0,
            "latency_spike": 0,
        }
        self.auto_pause_threshold = config.get("auto_pause_threshold", 3)
        self.recent_anomalies = deque(maxlen=10)

    def load_config(self) -> Dict:
        """Load anomaly detection config"""
        config_file = Path("config/anomaly.yaml")
        if config_file.exists():
            import yaml

            with open(config_file) as f:
                return yaml.safe_load(f)
        return {
            "z_threshold": 3.0,
            "spike_threshold": 5.0,
            "clock_drift_tolerance_ms": 1000,
            "price_window": 100,
            "pnl_window": 50,
            "auto_pause_threshold": 3,
        }

    def calculate_z_score(self, value: float, history: List[float]) -> float:
        """Calculate z-score for outlier detection"""
        if len(history) < 3:
            return 0
        mean = np.mean(history)
        std = np.std(history)
        if std == 0:
            return 0
        return abs((value - mean) / std)

    def detect_price_anomaly(
        self, symbol: str, price: float, timestamp: datetime
    ) -> Optional[Dict]:
        """Detect price feed anomalies"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.price_window)
        history = self.price_history[symbol]
        if len(history) < 10:
            history.append(price)
            return None
        z_score = self.calculate_z_score(price, list(history))
        if z_score > self.spike_threshold:
            anomaly = {
                "type": "price_spike",
                "symbol": symbol,
                "price": price,
                "z_score": z_score,
                "mean": np.mean(list(history)),
                "std": np.std(list(history)),
                "timestamp": timestamp.isoformat(),
                "severity": "HIGH" if z_score > self.spike_threshold * 1.5 else "MEDIUM",
            }
            self.anomaly_counts["price_spike"] += 1
            self.recent_anomalies.append(anomaly)
            logger.warning(f"Price anomaly detected: {symbol} at {price} (z={z_score:.2f})")
            history.append(price)
            return anomaly
        if len(history) >= 5:
            last_5 = list(history)[-5:]
            if len(set(last_5)) == 1 and price == last_5[0]:
                anomaly = {
                    "type": "stale_feed",
                    "symbol": symbol,
                    "price": price,
                    "repeated_count": 6,
                    "timestamp": timestamp.isoformat(),
                    "severity": "MEDIUM",
                }
                self.anomaly_counts["stale_feed"] += 1
                self.recent_anomalies.append(anomaly)
                logger.warning(f"Stale feed detected: {symbol} stuck at {price}")
                return anomaly
        history.append(price)
        return None

    def detect_pnl_anomaly(self, pnl: float, timestamp: datetime) -> Optional[Dict]:
        """Detect P&L spikes"""
        if len(self.pnl_history) < 5:
            self.pnl_history.append(pnl)
            return None
        z_score = self.calculate_z_score(pnl, list(self.pnl_history))
        if z_score > self.z_threshold:
            anomaly = {
                "type": "pnl_spike",
                "pnl": pnl,
                "z_score": z_score,
                "mean": np.mean(list(self.pnl_history)),
                "std": np.std(list(self.pnl_history)),
                "timestamp": timestamp.isoformat(),
                "severity": "HIGH" if abs(pnl) > 1000 else "MEDIUM",
            }
            self.anomaly_counts["pnl_spike"] += 1
            self.recent_anomalies.append(anomaly)
            logger.warning(f"P&L anomaly detected: {pnl} (z={z_score:.2f})")
            self.pnl_history.append(pnl)
            return anomaly
        self.pnl_history.append(pnl)
        return None

    def detect_clock_drift(
        self, exchange_timestamp: datetime, local_timestamp: Optional[datetime] = None
    ) -> Optional[Dict]:
        """Detect clock drift between exchange and local time"""
        if local_timestamp is None:
            local_timestamp = datetime.now()
        offset_ms = (exchange_timestamp - local_timestamp).total_seconds() * 1000
        self.clock_offsets.append(offset_ms)
        if abs(offset_ms) > self.clock_drift_tolerance_ms:
            anomaly = {
                "type": "clock_drift",
                "offset_ms": offset_ms,
                "exchange_time": exchange_timestamp.isoformat(),
                "local_time": local_timestamp.isoformat(),
                "severity": "HIGH" if abs(offset_ms) > 5000 else "MEDIUM",
            }
            self.anomaly_counts["clock_drift"] += 1
            self.recent_anomalies.append(anomaly)
            logger.warning(f"Clock drift detected: {offset_ms:.0f}ms offset")
            return anomaly
        return None

    def detect_latency_anomaly(self, latency_ms: float, endpoint: str) -> Optional[Dict]:
        """Detect latency spikes"""
        if len(self.latency_history) < 10:
            self.latency_history.append(latency_ms)
            return None
        z_score = self.calculate_z_score(latency_ms, list(self.latency_history))
        if z_score > self.z_threshold or latency_ms > 1000:
            anomaly = {
                "type": "latency_spike",
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "z_score": z_score,
                "mean": np.mean(list(self.latency_history)),
                "timestamp": datetime.now().isoformat(),
                "severity": "HIGH" if latency_ms > 2000 else "MEDIUM",
            }
            self.anomaly_counts["latency_spike"] += 1
            self.recent_anomalies.append(anomaly)
            logger.warning(f"Latency anomaly: {endpoint} at {latency_ms:.0f}ms")
            self.latency_history.append(latency_ms)
            return anomaly
        self.latency_history.append(latency_ms)
        return None

    def should_auto_pause(self) -> Tuple[bool, str]:
        """Check if trading should be auto-paused"""
        high_severity_count = sum(1 for a in self.recent_anomalies if a.get("severity") == "HIGH")
        if high_severity_count >= self.auto_pause_threshold:
            reason = f"Too many high-severity anomalies: {high_severity_count}"
            return (True, reason)
        recent_types = [a["type"] for a in self.recent_anomalies]
        if recent_types.count("price_spike") >= 3:
            return (True, "Multiple price feed anomalies detected")
        if recent_types.count("clock_drift") >= 2:
            return (True, "Persistent clock drift detected")
        if any(
            a["type"] == "pnl_spike" and abs(a.get("pnl", 0)) > 2000 for a in self.recent_anomalies
        ):
            return (True, "Extreme P&L spike detected")
        return (False, "")

    def get_status(self) -> Dict:
        """Get current anomaly detector status"""
        should_pause, pause_reason = self.should_auto_pause()
        return {
            "timestamp": datetime.now().isoformat(),
            "anomaly_counts": dict(self.anomaly_counts),
            "recent_anomalies": list(self.recent_anomalies)[-5:],
            "buffers": {
                "price_symbols": len(self.price_history),
                "pnl_history": len(self.pnl_history),
                "latency_history": len(self.latency_history),
                "clock_offsets": len(self.clock_offsets),
            },
            "should_pause": should_pause,
            "pause_reason": pause_reason,
            "health": "CRITICAL" if should_pause else "OK",
        }

    def save_anomaly_log(self):
        """Save anomaly log to file"""
        log_file = Path("logs/anomalies.json")
        log_file.parent.mkdir(exist_ok=True)
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "counts": dict(self.anomaly_counts),
            "recent": list(self.recent_anomalies),
            "status": self.get_status(),
        }
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

    def reset_counts(self):
        """Reset anomaly counts (for new session)"""
        self.anomaly_counts = {k: 0 for k in self.anomaly_counts}
        self.recent_anomalies.clear()

    def print_report(self):
        """Print anomaly report"""
        status = self.get_status()
        print("\n" + "=" * 60)
        print(" ANOMALY DETECTOR STATUS")
        print("=" * 60)
        print(f"Timestamp: {status['timestamp']}")
        print(f"Health: {status['health']}")
        print("\nAnomaly Counts:")
        for anomaly_type, count in status["anomaly_counts"].items():
            if count > 0:
                print(f"  {anomaly_type}: {count}")
        if status["recent_anomalies"]:
            print("\nRecent Anomalies:")
            for anomaly in status["recent_anomalies"]:
                print(f"  [{anomaly['type']}] Severity: {anomaly.get('severity', 'LOW')}")
                if anomaly["type"] == "price_spike":
                    print(f"    Symbol: {anomaly['symbol']}, Z-score: {anomaly['z_score']:.2f}")
                elif anomaly["type"] == "pnl_spike":
                    print(f"    P&L: {anomaly['pnl']:.2f}, Z-score: {anomaly['z_score']:.2f}")
        if status["should_pause"]:
            print(f"\n[WARNING] AUTO-PAUSE TRIGGERED: {status['pause_reason']}")
        print("=" * 60)


def test_anomaly_detector():
    """Test anomaly detector"""
    print("=" * 60)
    print(" ANOMALY DETECTOR TEST")
    print("=" * 60)
    detector = AnomalyDetector()
    print("\nTest 1: Price Spike Detection")
    symbol = "BTCUSDT"
    for i in range(20):
        price = 50000 + np.random.normal(0, 100)
        anomaly = detector.detect_price_anomaly(symbol, price, datetime.now())
        if anomaly:
            print(f"  Anomaly: {anomaly}")
    spike_price = 55000
    anomaly = detector.detect_price_anomaly(symbol, spike_price, datetime.now())
    if anomaly:
        print(f"  [DETECTED] Price spike: {anomaly['z_score']:.2f} sigma")
    print("\nTest 2: P&L Spike Detection")
    for i in range(10):
        pnl = np.random.normal(10, 20)
        anomaly = detector.detect_pnl_anomaly(pnl, datetime.now())
    spike_pnl = 500
    anomaly = detector.detect_pnl_anomaly(spike_pnl, datetime.now())
    if anomaly:
        print(f"  [DETECTED] P&L spike: {anomaly['z_score']:.2f} sigma")
    print("\nTest 3: Clock Drift Detection")
    local_time = datetime.now()
    exchange_time = local_time + timedelta(milliseconds=100)
    anomaly = detector.detect_clock_drift(exchange_time, local_time)
    if anomaly:
        print(f"  Anomaly: {anomaly}")
    else:
        print("  Normal clock sync")
    exchange_time = local_time + timedelta(milliseconds=5000)
    anomaly = detector.detect_clock_drift(exchange_time, local_time)
    if anomaly:
        print(f"  [DETECTED] Clock drift: {anomaly['offset_ms']:.0f}ms")
    print("\nTest 4: Latency Spike Detection")
    for i in range(15):
        latency = np.random.uniform(20, 80)
        anomaly = detector.detect_latency_anomaly(latency, "binance")
    spike_latency = 2000
    anomaly = detector.detect_latency_anomaly(spike_latency, "binance")
    if anomaly:
        print(f"  [DETECTED] Latency spike: {anomaly['latency_ms']:.0f}ms")
    print("\nTest 5: Auto-Pause Check")
    for i in range(3):
        detector.detect_price_anomaly("ETHUSDT", 10000, datetime.now())
    should_pause, reason = detector.should_auto_pause()
    if should_pause:
        print(f"  [TRIGGERED] Auto-pause: {reason}")
    else:
        print("  System OK, no auto-pause needed")
    detector.print_report()
    detector.save_anomaly_log()
    print("\nAnomaly log saved to logs/anomalies.json")
    print("=" * 60)


if __name__ == "__main__":
    test_anomaly_detector()
