"""
Net Edge Calibrator
Auto-calibrates min_edge_bps based on realized slippage and fees
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class EdgeCalibrator:
    """Calibrate minimum edge based on realized performance"""

    def __init__(self):
        self.safety_bps = 2
        self.lookback_trades = 100

    def load_trade_history(self) -> List[Dict]:
        """Load recent trade history"""
        trades = []
        paper_audit = Path("logs/paper_audit.jsonl")
        if paper_audit.exists():
            with open(paper_audit) as f:
                for line in f:
                    try:
                        trade = json.loads(line)
                        trades.append(trade)
                    except:
                        continue
        arb_audit = Path("logs/tr_arb_audit.log")
        if arb_audit.exists():
            with open(arb_audit) as f:
                for line in f:
                    if "TRADE_COMPLETE" in line:
                        try:
                            json_start = line.index("{")
                            trade_data = json.loads(line[json_start:])
                            trades.append(trade_data)
                        except:
                            continue
        return trades[-self.lookback_trades :]

    def calculate_realized_edge(self, trade: Dict) -> float:
        """Calculate realized edge for a single trade"""
        entry_price = trade.get("entry_price", trade.get("price_in", 0))
        exit_price = trade.get("exit_price", trade.get("price_out", 0))
        if not entry_price or not exit_price:
            return 0
        mid_price = (entry_price + exit_price) / 2
        if trade.get("side") == "buy":
            raw_edge_bps = (exit_price - entry_price) / mid_price * 10000
        else:
            raw_edge_bps = (entry_price - exit_price) / mid_price * 10000
        fee_bps = trade.get("fee_bps", trade.get("total_fee_pct", 0.1)) * 100
        realized_edge_bps = raw_edge_bps - fee_bps
        if "slippage_bps" in trade:
            realized_edge_bps -= trade["slippage_bps"]
        return realized_edge_bps

    def calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        if index >= len(sorted_values):
            return sorted_values[-1]
        return sorted_values[index]

    def calibrate_min_edge(self) -> Dict:
        """Calibrate minimum edge based on realized performance"""
        trades = self.load_trade_history()
        if not trades:
            logger.warning("No trade history found for calibration")
            return {
                "status": "insufficient_data",
                "min_edge_bps": 5,
                "reason": "No trade history available",
            }
        realized_edges = []
        for trade in trades:
            edge = self.calculate_realized_edge(trade)
            if edge != 0:
                realized_edges.append(edge)
        if not realized_edges:
            return {
                "status": "insufficient_data",
                "min_edge_bps": 5,
                "reason": "No valid edge calculations",
            }
        mean_edge = np.mean(realized_edges)
        std_edge = np.std(realized_edges)
        p5_edge = self.calculate_percentile(realized_edges, 5)
        p25_edge = self.calculate_percentile(realized_edges, 25)
        p50_edge = self.calculate_percentile(realized_edges, 50)
        p95_edge = self.calculate_percentile(realized_edges, 95)
        calibrated_min_edge = p95_edge + self.safety_bps
        calibrated_min_edge = max(3, min(calibrated_min_edge, 15))
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "calibrated",
            "trades_analyzed": len(realized_edges),
            "statistics": {
                "mean_edge_bps": round(mean_edge, 2),
                "std_edge_bps": round(std_edge, 2),
                "p5_edge_bps": round(p5_edge, 2),
                "p25_edge_bps": round(p25_edge, 2),
                "p50_edge_bps": round(p50_edge, 2),
                "p95_edge_bps": round(p95_edge, 2),
            },
            "calibration": {
                "old_min_edge_bps": self._get_current_min_edge(),
                "new_min_edge_bps": round(calibrated_min_edge, 2),
                "safety_bps": self.safety_bps,
                "method": "p95 + safety_margin",
            },
            "recommendation": self._get_recommendation(calibrated_min_edge),
        }
        report_file = Path("logs/edge_calibration_report.json")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Edge calibrated: {calibrated_min_edge:.2f} bps")
        return report

    def _get_current_min_edge(self) -> float:
        """Get current min_edge_bps from config"""
        config_file = Path("config/execution.yaml")
        if config_file.exists():
            import yaml

            with open(config_file) as f:
                config = yaml.safe_load(f)
                return config.get("min_edge_bps", 5)
        return 5

    def _get_recommendation(self, new_edge: float) -> str:
        """Generate recommendation based on calibration"""
        current = self._get_current_min_edge()
        if abs(new_edge - current) < 0.5:
            return "No change needed"
        elif new_edge > current:
            return f"Increase min_edge to {new_edge:.1f} bps for better profitability"
        else:
            return f"Decrease min_edge to {new_edge:.1f} bps for more opportunities"

    def apply_calibration(self, report: Dict) -> bool:
        """Apply calibrated min_edge to config"""
        if report["status"] != "calibrated":
            return False
        new_edge = report["calibration"]["new_min_edge_bps"]
        config_file = Path("config/execution.yaml")
        if config_file.exists():
            import yaml

            with open(config_file) as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        config["min_edge_bps"] = new_edge
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f"Applied calibration: min_edge_bps = {new_edge}")
        return True


def main():
    """Run edge calibration"""
    calibrator = EdgeCalibrator()
    report = calibrator.calibrate_min_edge()
    print("=" * 60)
    print("EDGE CALIBRATION REPORT")
    print("=" * 60)
    if report["status"] == "calibrated":
        stats = report["statistics"]
        calib = report["calibration"]
        print(f"\nTrades Analyzed: {report['trades_analyzed']}")
        print("\nEdge Statistics (bps):")
        print(f"  Mean: {stats['mean_edge_bps']:.2f}")
        print(f"  P5:   {stats['p5_edge_bps']:.2f}")
        print(f"  P50:  {stats['p50_edge_bps']:.2f}")
        print(f"  P95:  {stats['p95_edge_bps']:.2f}")
        print("\nCalibration:")
        print(f"  Current: {calib['old_min_edge_bps']:.2f} bps")
        print(f"  New:     {calib['new_min_edge_bps']:.2f} bps")
        print(f"  Method:  {calib['method']}")
        print(f"\nRecommendation: {report['recommendation']}")
        if abs(calib["new_min_edge_bps"] - calib["old_min_edge_bps"]) > 0.5:
            calibrator.apply_calibration(report)
            print("\n[APPLIED] Configuration updated")
    else:
        print(f"\nStatus: {report['status']}")
        print(f"Reason: {report['reason']}")
    print("\nReport saved to: logs/edge_calibration_report.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
