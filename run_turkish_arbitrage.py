"""
Run Turkish Arbitrage Paper Trading System
"""

import asyncio
import logging
from datetime import datetime
from src.trading.turkish_arbitrage import turkish_arbitrage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    """Run Turkish arbitrage system"""
    print("=" * 60)
    print("TURKISH ARBITRAGE PAPER TRADING")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print("Mode: PAPER TRADING")
    print("Exchanges: Binance <-> BTCTurk")
    print("Min Profit Threshold: 0.3%")
    print("TL Gateway Fee: 0.1%")
    print("-" * 60)
    
    try:
        # Start arbitrage monitoring
        await turkish_arbitrage.start()
        print("Arbitrage system started. Monitoring for opportunities...")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        # Run for specified duration or until interrupted
        start_time = datetime.now()
        
        while True:
            # Print status every 30 seconds
            await asyncio.sleep(30)
            
            status = turkish_arbitrage.get_status()
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status Update:")
            print(f"  Runtime: {elapsed:.1f} minutes")
            print(f"  Opportunities Found: {status['opportunities_found']}")
            print(f"  Trades Executed: {status['trades_executed']}")
            print(f"  Total Profit: ${status['total_profit_usdt']:.2f}")
            
            # Show current opportunities
            if status['current_opportunities']:
                print("\n  Current Opportunities:")
                for opp in status['current_opportunities'][:3]:
                    print(f"    - {opp['symbol']}: {opp['profit_pct']:.2f}% ({opp['direction']})")
                    
            # Show recent trades
            if status['recent_trades']:
                print("\n  Recent Trades:")
                for trade in status['recent_trades'][-3:]:
                    print(f"    - {trade['opportunity']['symbol']}: +${trade['profit_usdt']:.2f}")
                    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        
    finally:
        # Stop the system
        await turkish_arbitrage.stop()
        
        # Print final summary
        final_status = turkish_arbitrage.get_status()
        
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"Total Opportunities Found: {final_status['opportunities_found']}")
        print(f"Total Trades Executed: {final_status['trades_executed']}")
        print(f"Total Profit (USDT): ${final_status['total_profit_usdt']:.2f}")
        
        if final_status['trades_executed'] > 0:
            avg_profit = final_status['total_profit_usdt'] / final_status['trades_executed']
            print(f"Average Profit per Trade: ${avg_profit:.2f}")
            
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())