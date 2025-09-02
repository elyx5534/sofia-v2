"""
Run Funding Rate Farmer Strategy in Paper Mode
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.funding_farmer import FundingRateFarmer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_paper_test(duration_mins: int = 15):
    """Run funding farmer in paper mode"""

    # Configuration for paper trading
    config = {
        "testnet": True,  # Always use testnet for paper
        "initial_capital": 100000,  # $100K paper capital
        "min_negative_funding": -0.0001,  # -0.01%
        "min_volume": 5000000,  # $5M (lower for testing)
        "min_open_interest": 2000000,  # $2M (lower for testing)
        "max_concurrent_positions": 5,
        "max_capital_percentage": 0.5,  # Use up to 50% for testing
        "position_size_per_farm": 10000,  # $10K per farm
        "delta_threshold": 0.02,  # 2% delta tolerance
        "rebalance_interval_hours": 0.25,  # 15 mins for testing
        "max_rebalance_cost": 0.001,  # 0.1%
        "max_spread": 0.003,  # 0.3% (more lenient for testing)
        "min_time_until_funding": 0.1,  # 6 minutes (lower for testing)
        "compound_earnings": True,
    }

    # Create farmer
    farmer = FundingRateFarmer(config)

    # Initialize
    await farmer.initialize()
    logger.info(f"Starting {duration_mins}-minute paper test")

    # Run test
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_mins)

    # Track metrics
    initial_capital = farmer.available_capital

    # Run until duration
    while datetime.now() < end_time:
        # Log status every minute
        stats = farmer.get_statistics()
        logger.info(
            f"Status: Positions={stats['active_positions']} "
            f"Deployed=${stats['total_capital_deployed']:.0f} "
            f"Daily=${stats['daily_income']:.2f} "
            f"Collected=${stats['total_funding_collected']:.2f}"
        )

        await asyncio.sleep(60)

    # Shutdown farmer
    await farmer.shutdown()

    # Get final stats
    final_stats = farmer.get_statistics()

    # Calculate metrics
    total_collected = float(final_stats["total_funding_collected"])
    pnl_usdt = total_collected  # In USDT
    pnl_pct = (total_collected / float(initial_capital)) * 100 if initial_capital > 0 else 0

    # Calculate exposure ratio
    deployed = float(final_stats["total_capital_deployed"])
    available = float(final_stats["available_capital"])
    total_capital = deployed + available
    exposure_ratio = deployed / total_capital if total_capital > 0 else 0

    # Calculate average APY across positions
    avg_apy = 0
    if final_stats["positions"]:
        apys = [p["apy"] for p in final_stats["positions"]]
        avg_apy = sum(apys) / len(apys) if apys else 0

    # Prepare result
    result = {
        "timestamp": datetime.now().isoformat(),
        "duration_mins": duration_mins,
        "metrics": {
            "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct,
            "exposure_ratio": exposure_ratio,
            "total_funding_collected": total_collected,
            "daily_income": float(final_stats["daily_income"]),
            "avg_apy": avg_apy,
            "active_positions": final_stats["active_positions"],
            "total_capital_deployed": deployed,
        },
        "positions": final_stats["positions"],
        "opportunities": final_stats["top_opportunities"],
    }

    # Save result
    result_file = Path("logs/funding_farmer_last_run.json")
    result_file.parent.mkdir(exist_ok=True)

    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Test complete. Results saved to {result_file}")
    logger.info(f"Final P&L: ${pnl_usdt:.2f} ({pnl_pct:.3f}%)")
    logger.info(f"Exposure: {exposure_ratio:.1%}")
    logger.info(f"Avg APY: {avg_apy:.2f}%")
    logger.info(f"Daily Income: ${final_stats['daily_income']:.2f}")

    return result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run Funding Farmer Paper Test")
    parser.add_argument("--mins", type=int, default=15, help="Test duration in minutes")
    parser.add_argument("--paper", action="store_true", default=True, help="Run in paper mode")

    args = parser.parse_args()

    # Run async test
    result = asyncio.run(run_paper_test(args.mins))

    # Exit with success/fail code
    if result["metrics"]["pnl_usdt"] >= 0 and result["metrics"]["exposure_ratio"] <= 0.3:
        sys.exit(0)  # PASS
    else:
        sys.exit(1)  # FAIL


if __name__ == "__main__":
    main()
