#!/usr/bin/env python3
"""
Portfolio seeding script for Sofia V2 test harness.
Seeds $100k starting balance and resets all positions/trades.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import get_database

def seed_portfolio(balance: float = 100000.0, reset: bool = True):
    """Seed portfolio with starting balance."""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)
    
    # Get database
    db = get_database()
    
    # Reset if requested
    if reset:
        logger.info("Resetting database to clean state...")
        db.reset_database()
    
    # Check current state
    account = db.get_account_state()
    if account:
        logger.info(f"Current balance: ${account['cash_balance']:,.2f}")
        logger.info(f"Current equity: ${account['total_equity']:,.2f}")
        logger.info(f"Current P&L: ${account['total_pnl']:,.2f}")
    else:
        logger.info("No account found, seeding fresh...")
        db.seed_initial_balance(balance)
        logger.info(f"Portfolio seeded with ${balance:,.2f}")
    
    # Show positions
    positions = db.get_positions()
    if positions:
        logger.info(f"Current positions: {len(positions)}")
        for symbol, pos in positions.items():
            logger.info(f"  {symbol}: {pos['quantity']:.6f} @ ${pos['avg_entry_price']:.2f}")
    else:
        logger.info("No active positions")
    
    # Show recent trades
    trades = db.get_recent_trades(limit=5)
    if trades:
        logger.info(f"Recent trades: {len(trades)}")
        for trade in trades[:3]:
            logger.info(f"  {trade['side'].upper()} {trade['quantity']:.6f} {trade['symbol']} @ ${trade['price']:.2f}")
    else:
        logger.info("No trades executed")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed Sofia V2 portfolio")
    parser.add_argument("--balance", type=float, default=100000.0, help="Starting balance (default: $100k)")
    parser.add_argument("--no-reset", action="store_true", help="Don't reset existing data")
    
    args = parser.parse_args()
    
    seed_portfolio(balance=args.balance, reset=not args.no_reset)