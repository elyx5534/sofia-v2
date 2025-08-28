"""Sofia CLI tool for data management and monitoring"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any, Dict

from .config import SYMBOLS
from .data.realtime import ReliabilityFeed

def cmd_data(args: argparse.Namespace) -> int:
    """Display real-time data status"""
    feed = ReliabilityFeed()
    feed.start()
    time.sleep(0.5)  # Allow time for initial connection
    
    output: Dict[str, Any] = {}
    
    for symbol in SYMBOLS:
        tick = feed.get_price(symbol)
        if tick:
            output[symbol] = {
                "price": tick.price,
                "ts": tick.ts,
                "source": tick.source,
                "freshness": round(time.time() - tick.ts, 2)
            }
        else:
            output[symbol] = None
    
    # Add metrics
    metrics = feed.get_metrics()
    output["_metrics"] = {
        "ws_connected": metrics.get("ws_connected", 0),
        "rest_hits": metrics.get("rest_hits", 0),
        "errors": metrics.get("ws_errors", 0) + metrics.get("rest_errors", 0)
    }
    
    print(json.dumps(output, indent=2))
    
    feed.stop()
    return 0

def cmd_status(args: argparse.Namespace) -> int:
    """Display system status in one line"""
    feed = ReliabilityFeed()
    feed.start()
    time.sleep(0.2)
    
    status_parts = []
    for symbol in args.symbols.split(",") if args.symbols else SYMBOLS[:3]:
        tick = feed.get_price(symbol.strip())
        if tick:
            status_parts.append(f"{symbol}: ${tick.price:.2f}")
        else:
            status_parts.append(f"{symbol}: N/A")
    
    metrics = feed.get_metrics()
    ws_status = "WS:ON" if metrics.get("ws_connected") else "WS:OFF"
    
    print(f"[{ws_status}] {' | '.join(status_parts)}")
    
    feed.stop()
    return 0

def main() -> int:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="sofia",
        description="Sofia V2 CLI - AI Trading Platform"
    )
    
    subparsers = parser.add_subparsers(dest="cmd", required=True, help="Commands")
    
    # Data command
    data_parser = subparsers.add_parser("data", help="Display data status")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="One-line status display")
    status_parser.add_argument(
        "--symbols",
        help="Comma-separated symbols to display",
        default=None
    )
    
    args = parser.parse_args()
    
    if args.cmd == "data":
        return cmd_data(args)
    elif args.cmd == "status":
        return cmd_status(args)
    
    return 1

if __name__ == "__main__":
    sys.exit(main())