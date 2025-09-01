#!/usr/bin/env python3
"""
Simple Paper Trading Demo without emojis
"""

import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
import random

async def run_simple_demo(duration_minutes=5):
    """Run a simple paper trading demo"""
    
    print("=" * 60)
    print("SOFIA V2 - PAPER TRADING DEMO")
    print("=" * 60)
    print(f"Start Time: {datetime.now()}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Initial Capital: 1000 USDT")
    print("=" * 60)
    
    initial_capital = 1000.0
    current_capital = initial_capital
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    total_trades = 0
    win_trades = 0
    timeseries_data = []
    
    # Initial timeseries point
    timeseries_data.append({
        "ts_ms": int(start_time * 1000),
        "equity": current_capital
    })
    
    print("\nStarting simulated trading...")
    print("-" * 40)
    
    check_interval = 5  # Update every 5 seconds
    display_interval = 30  # Display every 30 seconds
    last_display = time.time()
    
    # Open JSONL file for trades
    jsonl_path = Path("logs/paper_audit.jsonl")
    jsonl_path.parent.mkdir(exist_ok=True)
    
    while time.time() < end_time:
        # Simulate trading activity
        if random.random() > 0.3:  # 70% chance of trade
            # Generate random P&L
            trade_pnl = random.uniform(-5, 10)  # Between -$5 and +$10
            current_capital += trade_pnl
            total_trades += 1
            
            # Determine trade side and price
            side = "buy" if random.random() > 0.5 else "sell"
            base_price = 42000 + random.uniform(-1000, 1000)  # BTC price simulation
            qty = abs(trade_pnl) / base_price  # Calculate quantity
            
            # Write to JSONL file
            trade_record = {
                "ts_ms": int(time.time() * 1000),
                "symbol": "BTC/USDT",
                "side": side,
                "qty": round(qty, 8),
                "price": round(base_price, 2),
                "price_source": "simulated"
            }
            
            with open(jsonl_path, 'a') as f:
                f.write(json.dumps(trade_record) + '\n')
                f.flush()  # Ensure immediate write
            
            if trade_pnl > 0:
                win_trades += 1
        
        # Calculate current P&L
        total_pnl = current_capital - initial_capital
        pnl_percentage = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Add timeseries point
        timeseries_data.append({
            "ts_ms": int(time.time() * 1000),
            "equity": current_capital
        })
        
        # Write timeseries file
        Path("logs").mkdir(exist_ok=True)
        with open("logs/pnl_timeseries.json", 'w') as f:
            json.dump(timeseries_data[-50:], f, indent=2)  # Keep last 50 points
        
        # Write/update pnl_summary.json
        summary = {
            "initial_capital": initial_capital,
            "final_capital": current_capital,
            "realized_pnl": total_pnl,
            "unrealized_pnl": 0,
            "total_pnl": total_pnl,
            "pnl_percentage": pnl_percentage,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "start_timestamp": datetime.fromtimestamp(start_time).isoformat(),
            "end_timestamp": datetime.now().isoformat(),
            "is_running": True,
            "session_complete": False
        }
        
        with open("logs/pnl_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Display progress
        remaining_minutes = int((end_time - time.time()) / 60)
        if time.time() - last_display >= display_interval:
            print(f"\nTime Remaining: {remaining_minutes} minutes")
            print(f"Current Equity: ${current_capital:.2f}")
            print(f"Total P&L: ${total_pnl:.2f} ({pnl_percentage:+.2f}%)")
            print(f"Total Trades: {total_trades}")
            print(f"Win Rate: {win_rate:.1f}%")
            last_display = time.time()
        
        # Wait before next update
        await asyncio.sleep(check_interval)
    
    # Final update
    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print("=" * 60)
    
    final_pnl = current_capital - initial_capital
    final_pnl_pct = (final_pnl / initial_capital * 100) if initial_capital > 0 else 0
    
    print(f"\nFINAL RESULTS:")
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Final Capital: ${current_capital:.2f}")
    print(f"Total P&L: ${final_pnl:.2f} ({final_pnl_pct:+.2f}%)")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    
    # Write final summary
    final_summary = {
        "initial_capital": initial_capital,
        "final_capital": current_capital,
        "realized_pnl": final_pnl,
        "unrealized_pnl": 0,
        "total_pnl": final_pnl,
        "pnl_percentage": final_pnl_pct,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "start_timestamp": datetime.fromtimestamp(start_time).isoformat(),
        "end_timestamp": datetime.now().isoformat(),
        "is_running": False,
        "session_complete": True
    }
    
    with open("logs/pnl_summary.json", 'w') as f:
        json.dump(final_summary, f, indent=2)
    
    # Add final timeseries point
    timeseries_data.append({
        "ts_ms": int(time.time() * 1000),
        "equity": current_capital
    })
    
    with open("logs/pnl_timeseries.json", 'w') as f:
        json.dump(timeseries_data[-50:], f, indent=2)
    
    print("\nFiles written:")
    print("  - logs/pnl_summary.json")
    print("  - logs/pnl_timeseries.json")
    
    return final_summary

async def main():
    """Main entry point"""
    try:
        duration = 1  # 1 minute demo for quick testing
        print(f"Running {duration}-minute demo session...")
        summary = await run_simple_demo(duration)
        print("\nDemo complete! Check the dashboard at http://localhost:8000/dashboard")
        return 0
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)