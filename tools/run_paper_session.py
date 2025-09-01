#!/usr/bin/env python3
"""
Paper Trading Session Runner
Runs a 30-minute paper trading session with Grid Monster strategy
"""

import asyncio
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
from src.core.logging_config import setup_logging
logger = setup_logging()

from src.strategies.grid_monster import GridMonster
from src.paper_trading.paper_engine import PaperTradingEngine

async def run_paper_session(duration_minutes: int = 30):
    """Run paper trading session for specified duration"""
    
    print("=" * 60)
    print("SOFIA V2 - PAPER TRADING SESSION")
    print("=" * 60)
    print(f"Start Time: {datetime.now()}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"Mode: PAPER (Virtual Trading)")
    print(f"Initial Capital: 1000 USDT")
    print("=" * 60)
    
    # Set environment
    os.environ["ENV"] = "paper"
    
    # Initialize components
    print("\n📊 Initializing components...")
    
    # Initialize paper trading engine
    paper_engine = PaperTradingEngine(initial_balance=1000.0)
    
    # Load Grid Monster configuration from yaml or use defaults
    config_path = Path("config/strategies/grid_monster.yaml")
    if config_path.exists():
        import yaml
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        # Override with runtime settings
        grid_config = {
            "paper_mode": True,
            "symbols": yaml_config.get("symbols", ["BTC/USDT", "SOL/USDT"]),
            "grid_levels": yaml_config.get("grid_levels", 30),
            "grid_spacing_pct": yaml_config.get("grid_spacing_pct", 0.25),
            "maker_only": yaml_config.get("maker_only", True),
            "cancel_unfilled_sec": yaml_config.get("cancel_unfilled_sec", 60),
            "max_position_pct": yaml_config.get("max_position_pct", 5),
            "daily_max_drawdown_pct": yaml_config.get("daily_max_drawdown_pct", 1.0),
            "fee_pct": yaml_config.get("fee_pct", 0.10),
            "spread_gate_multiplier": yaml_config.get("spread_gate_multiplier", 2.0),
            "default_num_levels": yaml_config.get("grid_levels", 30),
            "default_spacing": yaml_config.get("grid_spacing_pct", 0.25) / 100,
            "max_grids": len(yaml_config.get("symbols", [])),
            "max_capital_per_grid": 500
        }
        print(f"✅ Loaded configuration from {config_path}")
    else:
        # Use hardcoded defaults
        grid_config = {
            "paper_mode": True,
            "symbols": ["BTC/USDT", "SOL/USDT"],
            "grid_levels": 30,
            "grid_spacing_pct": 0.25,
            "maker_only": True,
            "cancel_unfilled_sec": 60,
            "max_position_pct": 5,
            "daily_max_drawdown_pct": 1.0,
            "fee_pct": 0.10,
            "spread_gate_multiplier": 2.0,
            "default_num_levels": 30,
            "default_spacing": 0.0025,
            "max_grids": 2,
            "max_capital_per_grid": 500
        }
        print("⚠️  Using default configuration")
    
    grid_monster = GridMonster(grid_config)
    await grid_monster.initialize()
    
    print("✅ Grid Monster initialized")
    print(f"✅ Monitoring symbols: {grid_config['symbols']}")
    
    # Start trading
    print("\n🚀 Starting paper trading session...")
    print("-" * 40)
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    # Start grids for configured symbols
    for symbol in grid_config["symbols"]:
        grid_id = await grid_monster.start_grid(symbol.replace("/", ""))
        if grid_id:
            print(f"✅ Grid started for {symbol}: {grid_id}")
        else:
            print(f"❌ Failed to start grid for {symbol}")
    
    # Monitor session
    check_interval = 30  # Check every 30 seconds
    trade_count = 0
    
    while time.time() < end_time:
        remaining = int((end_time - time.time()) / 60)
        
        # Get statistics
        stats = grid_monster.get_statistics()
        
        # Print status update
        print(f"\n⏱️  Time Remaining: {remaining} minutes")
        print(f"📈 Active Grids: {stats['active_grids']}")
        print(f"💰 Total Trades: {stats['total_trades']}")
        print(f"💵 Total Profit: ${stats['total_profit']:.2f}")
        
        # Log some trades to audit log
        if stats['total_trades'] > trade_count:
            trade_count = stats['total_trades']
            print(f"🔄 New trades executed: {trade_count}")
        
        # Wait before next check
        await asyncio.sleep(check_interval)
    
    # Session complete
    print("\n" + "=" * 60)
    print("SESSION COMPLETE")
    print("=" * 60)
    
    # Final statistics
    final_stats = grid_monster.get_statistics()
    
    # Calculate P&L
    initial_capital = 1000.0
    final_capital = initial_capital + float(final_stats['total_profit'])
    pnl = final_capital - initial_capital
    pnl_pct = (pnl / initial_capital) * 100
    
    # Print detailed P&L summary
    print("\n" + "=" * 60)
    print("📊 P&L PROOF - TRADING SUMMARY")
    print("=" * 60)
    
    # Capital Summary
    print("\n💰 CAPITAL:")
    print(f"  Initial Capital:     ${initial_capital:>10.2f} USDT")
    print(f"  Final Capital:       ${final_capital:>10.2f} USDT")
    print(f"  {'Profit' if pnl >= 0 else 'Loss':>20}: ${abs(pnl):>10.2f} USDT")
    print(f"  {'Return %':>20}: {pnl_pct:>+10.2f}%")
    
    # Trading Activity
    print("\n📈 TRADING ACTIVITY:")
    print(f"  Total Trades:        {final_stats['total_trades']:>10d}")
    print(f"  Active Grids:        {final_stats['active_grids']:>10d}")
    print(f"  Successful Grids:    {final_stats['successful_grids']:>10d}")
    print(f"  Failed Grids:        {final_stats['failed_grids']:>10d}")
    print(f"  Success Rate:        {final_stats['success_rate']:>10.1f}%")
    
    # Realized vs Unrealized
    realized_pnl = float(final_stats.get('total_profit', 0))
    unrealized_pnl = 0  # Grid strategy typically has all realized
    print("\n💹 P&L BREAKDOWN:")
    print(f"  Realized P&L:        ${realized_pnl:>10.2f} USDT")
    print(f"  Unrealized P&L:      ${unrealized_pnl:>10.2f} USDT")
    print(f"  Total P&L:           ${pnl:>10.2f} USDT")
    
    print("\n" + "=" * 60)
    
    # Check audit log
    audit_log_path = Path("logs/paper_audit.log")
    if audit_log_path.exists():
        with open(audit_log_path, 'r') as f:
            lines = f.readlines()
            print(f"\n📝 Audit Log Entries: {len(lines)}")
            if lines:
                print("Last 3 entries:")
                for line in lines[-3:]:
                    try:
                        entry = json.loads(line)
                        print(f"  - {entry.get('symbol', 'N/A')}: {entry.get('side', 'N/A')} "
                              f"{entry.get('qty', 0):.4f} @ ${entry.get('price_used', 0):.2f}")
                    except:
                        pass
    
    # Write summary to file
    summary_path = Path("logs/paper_session_summary.json")
    summary = {
        "session_date": datetime.now().isoformat(),
        "duration_minutes": duration_minutes,
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_pnl": pnl,
        "pnl_percentage": pnl_pct,
        "total_trades": final_stats['total_trades'],
        "success_rate": final_stats['success_rate']
    }
    
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Also write pnl_summary.json for dashboard
    pnl_summary_path = Path("logs/pnl_summary.json")
    pnl_summary = {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": pnl,
        "pnl_percentage": pnl_pct,
        "total_trades": final_stats['total_trades'],
        "win_rate": final_stats['success_rate'],
        "start_timestamp": datetime.now().isoformat(),
        "end_timestamp": datetime.now().isoformat()
    }
    
    with open(pnl_summary_path, 'w') as f:
        json.dump(pnl_summary, f, indent=2)
    
    print(f"\n💾 Summary saved to: {summary_path}")
    
    # Shutdown
    await grid_monster.shutdown()
    
    return summary

async def main():
    """Main entry point"""
    try:
        # Run 30-minute session (or override with command line arg)
        duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
        summary = await run_paper_session(duration)
        
        # Exit with success code if profitable
        if summary['total_pnl'] >= 0:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Session interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())