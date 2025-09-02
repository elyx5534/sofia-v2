"""
Paper Trading Demo - 5 minute quick test
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from src.paper_trading.fill_engine import RealisticFillEngine, Order
from src.core.watchdog import Watchdog
from src.core.profit_guard import ProfitGuard
from src.core.accounting import FIFOAccounting
from decimal import Decimal
import random
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    print("=" * 60)
    print("PAPER TRADING DEMO - 5 MINUTE TEST")
    print("=" * 60)
    print(f"Start: {datetime.now()}")
    print("-" * 60)
    
    # Initialize systems
    fill_engine = RealisticFillEngine()
    watchdog = Watchdog()
    profit_guard = ProfitGuard()
    accounting = FIFOAccounting()
    
    # Start systems
    await fill_engine.start()
    await watchdog.start()
    await profit_guard.start_monitoring()
    
    trades_executed = 0
    total_pnl = Decimal("0")
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=5)
    
    print("Systems started. Running for 5 minutes...")
    print("-" * 60)
    
    try:
        while datetime.now() < end_time:
            # Check system status
            if watchdog.state.status == "PAUSED":
                print(f"System paused: {watchdog.state.pause_reason}")
                await asyncio.sleep(5)
                continue
                
            # Execute trades
            for symbol in ["BTC/USDT", "ETH/USDT"]:
                if random.random() < 0.4:  # 40% chance
                    # Create order
                    side = "buy" if random.random() < 0.5 else "sell"
                    price = 108000 if symbol == "BTC/USDT" else 3800
                    price *= (1 + random.uniform(-0.01, 0.01))
                    
                    order = Order(
                        order_id=f"demo_{trades_executed}",
                        symbol=symbol,
                        side=side,
                        order_type="limit",
                        quantity=Decimal("0.001"),
                        price=Decimal(str(price)),
                        maker_only=True,
                        cancel_unfilled_sec=10
                    )
                    
                    fill_engine.submit_order(order)
                    trades_executed += 1
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Order: {symbol} {side} @ ${price:.2f}")
                    
                    # Wait for fill
                    await asyncio.sleep(1)
                    
                    # Process fills
                    if order.fills:
                        for fill in order.fills:
                            print(f"  -> Filled: {fill['quantity']} @ ${fill['price']:.2f} (type: {fill['fill_type']})")
                            
            # Update metrics every 30 seconds
            elapsed = (datetime.now() - start_time).total_seconds()
            if int(elapsed) % 30 == 0 and elapsed > 0:
                metrics = fill_engine.get_metrics()
                print(f"\n[{elapsed:.0f}s] Trades: {trades_executed} | Maker Fill Rate: {metrics['maker_fill_rate']:.1f}%")
                
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        
    finally:
        # Stop systems
        await fill_engine.stop()
        await watchdog.stop()
        await profit_guard.stop_monitoring()
        
        # Final report
        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        
        duration = (datetime.now() - start_time).total_seconds() / 60
        metrics = fill_engine.get_metrics()
        
        print(f"Duration: {duration:.1f} minutes")
        print(f"Orders Submitted: {trades_executed}")
        print(f"Maker Fill Rate: {metrics['maker_fill_rate']:.1f}%")
        print(f"Avg Fill Time: {metrics['avg_time_to_fill_ms']:.0f}ms")
        print(f"Partial Fills: {metrics['partial_fill_count']}")
        print(f"Cancelled Orders: {metrics['cancelled_orders']}")
        
        # Save report
        report = {
            'duration_minutes': duration,
            'orders_submitted': trades_executed,
            'fill_metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        report_path = Path("logs/demo_report.json")
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nReport saved to: {report_path}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())