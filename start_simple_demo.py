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
    
    # Track positions for unrealized P&L simulation
    open_positions = []
    cash_balance = initial_capital
    
    # Initial timeseries point
    timeseries_data.append({
        "ts_ms": int(start_time * 1000),
        "equity": initial_capital
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
        # Update market prices (simulate volatility)
        current_btc_price = 108000 + random.uniform(-2000, 2000)
        
        # Simulate trading activity
        if random.random() > 0.3:  # 70% chance of trade
            # Generate trade with more realistic P&L
            trade_size = random.uniform(0.00001, 0.0001)  # Small BTC amounts
            trade_pnl = (current_btc_price * trade_size * random.uniform(-0.02, 0.03))  # -2% to +3% per trade
            
            # Update cash from realized trades
            cash_balance += trade_pnl
            total_trades += 1
            
            # Determine trade side
            side = "buy" if random.random() > 0.5 else "sell"
            
            # Simulate position tracking
            if side == "buy":
                open_positions.append({"size": trade_size, "entry_price": current_btc_price})
            elif open_positions and side == "sell":
                # Close oldest position
                position = open_positions.pop(0)
                realized_pnl = (current_btc_price - position["entry_price"]) * position["size"]
                cash_balance += realized_pnl
            
            # Write to JSONL file
            trade_record = {
                "ts_ms": int(time.time() * 1000),
                "symbol": "BTC/USDT",
                "side": side,
                "qty": round(trade_size, 8),
                "price": round(current_btc_price, 2),
                "price_source": "simulated"
            }
            
            with open(jsonl_path, 'a') as f:
                f.write(json.dumps(trade_record) + '\n')
                f.flush()  # Ensure immediate write
            
            if trade_pnl > 0:
                win_trades += 1
        
        # Calculate unrealized P&L from open positions
        unrealized_pnl = sum((current_btc_price - pos["entry_price"]) * pos["size"] 
                            for pos in open_positions)
        
        # Calculate current equity (cash + unrealized)
        current_equity = cash_balance + unrealized_pnl
        
        # Calculate metrics
        total_pnl = current_equity - initial_capital
        pnl_percentage = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Add timeseries point with current equity
        timeseries_data.append({
            "ts_ms": int(time.time() * 1000),
            "equity": round(current_equity, 2)
        })
        
        # Write timeseries file
        Path("logs").mkdir(exist_ok=True)
        with open("logs/pnl_timeseries.json", 'w') as f:
            json.dump(timeseries_data[-50:], f, indent=2)  # Keep last 50 points
        
        # Write/update pnl_summary.json
        summary = {
            "initial_capital": initial_capital,
            "final_capital": round(current_equity, 2),
            "realized_pnl": round(cash_balance - initial_capital, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "pnl_percentage": round(pnl_percentage, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
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
            print(f"Current Equity: ${current_equity:.2f}")
            print(f"Cash Balance: ${cash_balance:.2f}")
            print(f"Unrealized P&L: ${unrealized_pnl:.2f}")
            print(f"Total P&L: ${total_pnl:.2f} ({pnl_percentage:+.2f}%)")
            print(f"Total Trades: {total_trades}")
            print(f"Open Positions: {len(open_positions)}")
            print(f"Win Rate: {win_rate:.1f}%")
            last_display = time.time()
        
        # Wait before next update
        await asyncio.sleep(check_interval)
    
    # Close all positions at market price for final calculation
    final_btc_price = 108000 + random.uniform(-1000, 1000)
    final_unrealized = sum((final_btc_price - pos["entry_price"]) * pos["size"] 
                          for pos in open_positions)
    final_equity = cash_balance + final_unrealized
    
    # Final update
    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print("=" * 60)
    
    final_pnl = final_equity - initial_capital
    final_pnl_pct = (final_pnl / initial_capital * 100) if initial_capital > 0 else 0
    
    print(f"\nFINAL RESULTS:")
    print(f"Initial Capital: ${initial_capital:.2f}")
    print(f"Final Equity: ${final_equity:.2f}")
    print(f"Cash Balance: ${cash_balance:.2f}")
    print(f"Unrealized P&L: ${final_unrealized:.2f}")
    print(f"Total P&L: ${final_pnl:.2f} ({final_pnl_pct:+.2f}%)")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    
    # Write final summary
    final_summary = {
        "initial_capital": initial_capital,
        "final_capital": round(final_equity, 2),
        "realized_pnl": round(cash_balance - initial_capital, 2),
        "unrealized_pnl": round(final_unrealized, 2),
        "total_pnl": round(final_pnl, 2),
        "pnl_percentage": round(final_pnl_pct, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
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
        "equity": round(final_equity, 2)
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