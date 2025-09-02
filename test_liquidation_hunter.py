#!/usr/bin/env python3
"""
Test Binance Futures Liquidation Hunter Bot
"""

import asyncio
import time
from decimal import Decimal

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from src.strategies.liquidation_hunter import LiquidationHunterBot

console = Console()


async def test_liquidation_hunter():
    """Test the liquidation hunter bot"""

    # Configuration
    config = {
        "min_liquidation_value": 100000,  # $100K minimum
        "cascade_wait_min": 3,
        "cascade_wait_max": 7,
        "take_profit_pct": 0.015,  # 1.5%
        "stop_loss_pct": 0.005,  # 0.5%
        "max_hold_minutes": 5,
        "max_leverage": 3,
        "allowed_symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
        "max_funding_rate": 0.0001,  # 0.01%
        "max_daily_trades": 10,
        "min_cascade_value": 500000,  # $500K minimum cascade
        "min_cascade_count": 3,
        "position_size_multiplier": 0.001,
        "max_position_size": 10000,
        "api_key": "test_key",
        "api_secret": "test_secret",
        "testnet": True,
    }

    # Initialize bot
    bot = LiquidationHunterBot(config)
    await bot.initialize()

    console.print("[green]Liquidation Hunter Bot initialized[/green]")
    console.print("=" * 60)

    # Test 1: Configuration Display
    console.print("\n[cyan]Test 1: Bot Configuration[/cyan]")

    config_table = Table(title="Trading Parameters")
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="yellow")

    config_table.add_row("Min Liquidation", f"${bot.min_liquidation_value:,.0f}")
    config_table.add_row("Cascade Wait", f"{bot.cascade_wait_min}-{bot.cascade_wait_max} seconds")
    config_table.add_row("Take Profit", f"{float(bot.take_profit_pct)*100:.1f}%")
    config_table.add_row("Stop Loss", f"{float(bot.stop_loss_pct)*100:.1f}%")
    config_table.add_row("Max Hold Time", f"{bot.max_hold_minutes} minutes")
    config_table.add_row("Max Leverage", f"{bot.max_leverage}x")
    config_table.add_row("Max Daily Trades", str(bot.max_daily_trades))
    config_table.add_row("Min Cascade Value", f"${bot.min_cascade_value:,.0f}")

    console.print(config_table)

    # Test 2: Allowed Symbols
    console.print("\n[cyan]Test 2: Monitored Symbols[/cyan]")

    symbols_table = Table(title="Allowed Trading Pairs")
    symbols_table.add_column("Symbol", style="cyan")
    symbols_table.add_column("Current Price", style="green")
    symbols_table.add_column("Status", style="yellow")

    for symbol in bot.allowed_symbols:
        price = await bot._get_current_price(symbol)
        symbols_table.add_row(symbol, f"${price:,.2f}", "Monitoring")

    console.print(symbols_table)

    # Test 3: Simulate Liquidation Cascades
    console.print("\n[cyan]Test 3: Simulating Liquidation Cascades[/cyan]")

    # Create progress bar for simulation
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        # Simulate LONG liquidation cascade (bearish)
        task1 = progress.add_task("[red]Simulating LONG liquidations on BTC...", total=5)
        await bot.simulate_cascade("BTCUSDT", "LONG", 5)
        progress.update(task1, completed=5)

        await asyncio.sleep(2)

        # Simulate SHORT liquidation cascade (bullish)
        task2 = progress.add_task("[green]Simulating SHORT liquidations on ETH...", total=4)
        await bot.simulate_cascade("ETHUSDT", "SHORT", 4)
        progress.update(task2, completed=4)

    # Wait for trades to execute
    console.print("\n[yellow]Waiting for cascade analysis and trade execution...[/yellow]")
    await asyncio.sleep(10)

    # Test 4: Display Active Positions
    console.print("\n[cyan]Test 4: Active Positions[/cyan]")

    if bot.positions:
        positions_table = Table(title="Open Positions")
        positions_table.add_column("Symbol", style="cyan")
        positions_table.add_column("Side", style="yellow")
        positions_table.add_column("Entry", style="green")
        positions_table.add_column("Current", style="blue")
        positions_table.add_column("P&L", style="magenta")
        positions_table.add_column("P&L %", style="magenta")
        positions_table.add_column("Hold Time", style="yellow")

        for position in bot.positions.values():
            pnl_color = "green" if position.pnl >= 0 else "red"
            positions_table.add_row(
                position.symbol,
                position.side,
                f"${position.entry_price:,.2f}",
                f"${position.current_price:,.2f}",
                f"[{pnl_color}]${position.pnl:,.2f}[/{pnl_color}]",
                f"[{pnl_color}]{position.pnl_percentage:.2f}%[/{pnl_color}]",
                f"{(time.time() - position.entry_time)/60:.1f} min",
            )

        console.print(positions_table)
    else:
        console.print("[yellow]No active positions[/yellow]")

    # Test 5: Cascade History
    console.print("\n[cyan]Test 5: Cascade Detection History[/cyan]")

    if bot.cascade_history:
        cascade_table = Table(title="Recent Liquidation Cascades")
        cascade_table.add_column("Symbol", style="cyan")
        cascade_table.add_column("Side", style="yellow")
        cascade_table.add_column("Total Value", style="green")
        cascade_table.add_column("Count", style="blue")
        cascade_table.add_column("Duration", style="magenta")
        cascade_table.add_column("Intensity", style="red")

        for cascade in bot.cascade_history[-5:]:  # Last 5 cascades
            cascade_table.add_row(
                cascade.symbol,
                cascade.side.value,
                f"${cascade.total_value:,.0f}",
                str(cascade.count),
                f"{cascade.duration:.1f}s",
                f"${cascade.intensity:,.0f}/s",
            )

        console.print(cascade_table)

    # Test 6: Statistics
    console.print("\n[cyan]Test 6: Trading Statistics[/cyan]")

    stats = bot.get_statistics()

    stats_table = Table(title="Performance Metrics", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")

    stats_table.add_row("Total P&L", f"${stats['total_pnl']:,.2f}")
    stats_table.add_row("Win Count", str(stats["win_count"]))
    stats_table.add_row("Loss Count", str(stats["loss_count"]))
    stats_table.add_row("Win Rate", f"{stats['win_rate']:.1f}%")
    stats_table.add_row("Daily Trades", f"{stats['daily_trades']}/{bot.max_daily_trades}")
    stats_table.add_row("Cascades Detected", str(stats["total_cascades_detected"]))

    console.print(stats_table)

    # Test 7: Pattern Analysis
    console.print("\n[cyan]Test 7: Cascade Pattern Analysis[/cyan]")

    patterns = bot.analyze_cascade_patterns()

    if patterns:
        pattern_table = Table(title="Cascade Patterns by Symbol")
        pattern_table.add_column("Symbol", style="cyan")
        pattern_table.add_column("Count", style="yellow")
        pattern_table.add_column("Total Value", style="green")
        pattern_table.add_column("Avg Duration", style="blue")
        pattern_table.add_column("Avg Intensity", style="magenta")

        for symbol, stats in patterns.get("by_symbol", {}).items():
            pattern_table.add_row(
                symbol,
                str(stats["count"]),
                f"${stats['total_value']:,.0f}",
                f"{stats['avg_duration']:.1f}s",
                f"${stats['avg_intensity']:,.0f}/s",
            )

        console.print(pattern_table)

        console.print(
            f"\n[yellow]Average cascade value: ${patterns.get('avg_cascade_value', 0):,.0f}[/yellow]"
        )
        console.print(
            f"[yellow]Average cascade duration: {patterns.get('avg_cascade_duration', 0):.1f}s[/yellow]"
        )

    # Test 8: Risk Analysis
    console.print("\n[cyan]Test 8: Risk Analysis[/cyan]")

    risk_table = Table(title="Risk Metrics")
    risk_table.add_column("Metric", style="cyan")
    risk_table.add_column("Value", style="yellow")
    risk_table.add_column("Status", style="green")

    # Calculate risk metrics
    total_exposure = sum(
        pos.size * pos.entry_price * pos.leverage for pos in bot.positions.values()
    )

    max_exposure = Decimal("30000")  # Example max exposure
    exposure_pct = (total_exposure / max_exposure * 100) if max_exposure > 0 else 0

    risk_table.add_row(
        "Total Exposure", f"${total_exposure:,.2f}", "OK" if exposure_pct < 80 else "HIGH"
    )
    risk_table.add_row(
        "Active Positions", str(len(bot.positions)), "OK" if len(bot.positions) < 5 else "HIGH"
    )
    risk_table.add_row(
        "Daily Trades Used",
        f"{bot.daily_trades}/{bot.max_daily_trades}",
        "OK" if bot.daily_trades < bot.max_daily_trades else "LIMIT",
    )
    risk_table.add_row(
        "Max Leverage", f"{bot.max_leverage}x", "SAFE" if bot.max_leverage <= 3 else "RISKY"
    )

    console.print(risk_table)

    # Test 9: Simulate more cascades
    console.print("\n[cyan]Test 9: Continuous Cascade Simulation[/cyan]")

    # Simulate multiple cascades
    cascade_events = [
        ("SOLUSDT", "LONG", 3),
        ("BNBUSDT", "SHORT", 4),
        ("BTCUSDT", "SHORT", 6),
    ]

    for symbol, side, count in cascade_events:
        console.print(f"Simulating {side} cascade on {symbol}...")
        await bot.simulate_cascade(symbol, side, count)
        await asyncio.sleep(3)

    # Wait for processing
    await asyncio.sleep(10)

    # Final statistics
    console.print("\n[cyan]Final Statistics[/cyan]")

    final_stats = bot.get_statistics()

    summary = Panel(
        f"""[green]Liquidation Hunter Bot Summary[/green]

Total P&L: [{'green' if final_stats['total_pnl'] >= 0 else 'red'}]${final_stats['total_pnl']:,.2f}[/]
Win Rate: {final_stats['win_rate']:.1f}%
Total Trades: {final_stats['win_count'] + final_stats['loss_count']}
Cascades Detected: {final_stats['total_cascades_detected']}
Active Positions: {len(final_stats['active_positions'])}

[yellow]Strategy: Hunt liquidation cascades by entering opposite positions[/yellow]
[cyan]Risk: Max 3x leverage, 0.5% stop loss, 5-minute max hold[/cyan]""",
        title="Performance Summary",
        border_style="green",
    )

    console.print(summary)

    # Cleanup
    await bot.shutdown()
    console.print("\n[green]Liquidation Hunter Bot test completed![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]Binance Futures Liquidation Hunter Bot[/bold cyan]")
    console.print("[yellow]Profiting from liquidation cascades[/yellow]")
    console.print("=" * 60)

    try:
        await test_liquidation_hunter()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
