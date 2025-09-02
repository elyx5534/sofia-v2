#!/usr/bin/env python3
"""
Simple 5-minute Paper Trading Demo
"""

import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


def run_demo(minutes=5):
    """Run simple demo for dashboard."""
    print(f"Starting {minutes}-minute demo...")

    # Setup logs
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Initialize
    trades = []
    equity_curve = []
    initial_equity = 10000
    current_equity = initial_equity

    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=minutes)

    while datetime.now() < end_time:
        # Generate mock trade
        side = random.choice(["buy", "sell"])
        price = 45000 + random.uniform(-500, 500)
        qty = round(random.uniform(0.001, 0.01), 6)

        trade = {
            "ts": datetime.now().isoformat(),
            "symbol": "BTC/USDT",
            "side": side,
            "qty": qty,
            "price": price,
            "source": "demo",
        }
        trades.append(trade)

        # Save trade
        with open(logs_dir / "trades.jsonl", "a") as f:
            f.write(json.dumps(trade) + "\n")

        # Update P&L
        pnl = random.uniform(-50, 100)  # Random P&L for demo
        current_equity += pnl

        # Save P&L summary
        summary = {
            "total_pnl": current_equity - initial_equity,
            "win_rate": random.uniform(45, 65),
            "total_trades": len(trades),
            "session_complete": False,
            "is_running": True,
        }

        with open(logs_dir / "pnl_summary.json", "w") as f:
            json.dump(summary, f)

        # Save timeseries
        equity_curve.append({"ts": datetime.now().isoformat(), "equity": current_equity})

        with open(logs_dir / "pnl_timeseries.json", "w") as f:
            json.dump(equity_curve[-50:], f)  # Keep last 50 points

        print(f"Trade #{len(trades)}: {side} {qty} @ ${price:.2f}")
        time.sleep(5)

    # Mark complete
    summary["session_complete"] = True
    summary["is_running"] = False
    with open(logs_dir / "pnl_summary.json", "w") as f:
        json.dump(summary, f)

    print(f"Demo complete! Total P&L: ${summary['total_pnl']:.2f}")


if __name__ == "__main__":
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_demo(minutes)
