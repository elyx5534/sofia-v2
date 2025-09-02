"""
Run Liquidation Hunter Strategy in Paper Mode
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.liquidation_hunter import LiquidationHunterBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_paper_test(duration_mins: int = 15):
    """Run liquidation hunter in paper mode"""
    
    # Configuration for paper trading
    config = {
        "testnet": True,  # Always use testnet for paper
        "min_liquidation_value": 50000,  # Lower for paper testing
        "cascade_wait_min": 2,
        "cascade_wait_max": 5,
        "take_profit_pct": 0.015,  # 1.5%
        "stop_loss_pct": 0.005,  # 0.5%
        "max_hold_minutes": 5,
        "max_leverage": 3,
        "allowed_symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
        "max_funding_rate": 0.0001,
        "max_daily_trades": 20,  # More trades for testing
        "min_cascade_value": 200000,  # Lower for testing
        "min_cascade_count": 2,  # Lower for testing
        "position_size_multiplier": 0.001,
        "max_position_size": 5000  # $5K max for paper
    }
    
    # Create bot
    bot = LiquidationHunterBot(config)
    
    # Initialize
    await bot.initialize()
    logger.info(f"Starting {duration_mins}-minute paper test")
    
    # Run test with simulated cascades
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_mins)
    
    # Simulate cascades periodically
    cascade_task = asyncio.create_task(simulate_cascades(bot, duration_mins))
    
    # Run until duration
    while datetime.now() < end_time:
        # Log status every minute
        stats = bot.get_statistics()
        logger.info(
            f"Status: Positions={len(stats['active_positions'])} "
            f"PnL=${stats['total_pnl']:.2f} "
            f"WinRate={stats['win_rate']:.1f}%"
        )
        
        await asyncio.sleep(60)
    
    # Cancel cascade simulation
    cascade_task.cancel()
    
    # Shutdown bot
    await bot.shutdown()
    
    # Get final stats
    final_stats = bot.get_statistics()
    
    # Calculate metrics
    total_trades = final_stats['win_count'] + final_stats['loss_count']
    win_rate = final_stats['win_rate'] if total_trades > 0 else 0
    pnl_pct = (final_stats['total_pnl'] / 10000) * 100 if final_stats['total_pnl'] else 0  # Assume $10K capital
    
    # Prepare result
    result = {
        "timestamp": datetime.now().isoformat(),
        "duration_mins": duration_mins,
        "metrics": {
            "pnl_pct": float(pnl_pct),
            "pnl_usdt": float(final_stats['total_pnl']),
            "win_rate": float(win_rate),
            "total_trades": total_trades,
            "win_count": final_stats['win_count'],
            "loss_count": final_stats['loss_count'],
            "cascades_detected": final_stats['total_cascades_detected']
        },
        "positions": final_stats['active_positions'],
        "cascade_analysis": bot.analyze_cascade_patterns() if hasattr(bot, 'analyze_cascade_patterns') else {}
    }
    
    # Save result
    result_file = Path("logs/liquidation_hunter_last_run.json")
    result_file.parent.mkdir(exist_ok=True)
    
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Test complete. Results saved to {result_file}")
    logger.info(f"Final P&L: ${final_stats['total_pnl']:.2f} ({pnl_pct:.2f}%)")
    logger.info(f"Win Rate: {win_rate:.1f}% ({final_stats['win_count']}W/{final_stats['loss_count']}L)")
    
    return result


async def simulate_cascades(bot: LiquidationHunterBot, duration_mins: int):
    """Simulate liquidation cascades for testing"""
    try:
        # Number of cascades to simulate
        num_cascades = max(3, duration_mins // 3)  # One cascade every 3 minutes
        
        for i in range(num_cascades):
            # Random symbol
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
            symbol = symbols[i % len(symbols)]
            
            # Random side
            side = "LONG" if i % 2 == 0 else "SHORT"
            
            # Simulate cascade
            logger.info(f"Simulating {side} cascade for {symbol}")
            await bot.simulate_cascade(symbol, side, num_liquidations=5)
            
            # Wait before next cascade
            await asyncio.sleep(180)  # 3 minutes
            
    except asyncio.CancelledError:
        logger.info("Cascade simulation stopped")
    except Exception as e:
        logger.error(f"Cascade simulation error: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run Liquidation Hunter Paper Test")
    parser.add_argument("--mins", type=int, default=15, help="Test duration in minutes")
    parser.add_argument("--paper", action="store_true", default=True, help="Run in paper mode")
    
    args = parser.parse_args()
    
    # Run async test
    result = asyncio.run(run_paper_test(args.mins))
    
    # Exit with success/fail code
    if result['metrics']['pnl_pct'] > 0 and result['metrics']['win_rate'] >= 52:
        sys.exit(0)  # PASS
    else:
        sys.exit(1)  # FAIL


if __name__ == "__main__":
    main()