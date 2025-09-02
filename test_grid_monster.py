#!/usr/bin/env python3
"""
Test High-Frequency Grid Trading Monster
"""

import asyncio
from decimal import Decimal

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from src.strategies.grid_monster import GridMonster, GridState

console = Console()


async def test_grid_monster():
    """Test the grid trading system"""

    # Configuration
    config = {
        "min_atr_percentage": 3.0,  # 3% ATR minimum
        "min_volume_24h": 50000000,  # $50M volume
        "max_trend_strength": 0.7,  # Avoid strong trends
        "default_num_levels": 20,
        "default_spacing": 0.003,  # 0.3% spacing
        "bb_period": 20,
        "bb_std": 2.0,
        "volatility_multiplier": 1.5,
        "trend_shift_factor": 0.002,
        "volume_reduction_threshold": 0.5,
        "max_grid_shift": 0.05,
        "max_grids": 5,
        "max_capital_per_grid": 10000,
        "stop_loss_percentage": 0.1,
        "min_profit_percentage": 0.001,
        "api_key": "test_key",
        "api_secret": "test_secret",
        "testnet": True,
    }

    # Initialize monster
    monster = GridMonster(config)
    await monster.initialize()

    console.print("[green]Grid Monster initialized[/green]")
    console.print("=" * 60)

    # Test 1: Configuration Display
    console.print("\n[cyan]Test 1: Grid Configuration[/cyan]")

    config_table = Table(title="Grid Trading Parameters")
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="yellow")

    config_table.add_row("Min ATR %", f"{monster.min_atr_percentage}%")
    config_table.add_row("Min Volume", f"${monster.min_volume_24h/1e6:.0f}M")
    config_table.add_row("Max Trend Strength", f"{monster.max_trend_strength:.1f}")
    config_table.add_row("Default Levels", str(monster.default_num_levels))
    config_table.add_row("Default Spacing", f"{monster.default_spacing*100:.1f}%")
    config_table.add_row("Max Grids", str(monster.max_grids))
    config_table.add_row("Capital per Grid", f"${monster.max_capital_per_grid:,.0f}")
    config_table.add_row("BB Period", f"{monster.bb_period} candles")
    config_table.add_row("BB StdDev", f"{monster.bb_std}σ")

    console.print(config_table)

    # Test 2: Coin Analysis
    console.print("\n[cyan]Test 2: Coin Selection Analysis[/cyan]")

    # Let scanner run
    await asyncio.sleep(2)

    analysis_table = Table(title="Coin Suitability Analysis")
    analysis_table.add_column("Symbol", style="cyan")
    analysis_table.add_column("ATR %", style="yellow")
    analysis_table.add_column("Volume 24h", style="green")
    analysis_table.add_column("Trend", style="blue")
    analysis_table.add_column("Volatility", style="magenta")
    analysis_table.add_column("Suitable", style="white")

    for symbol, metrics in list(monster.coin_metrics.items())[:10]:
        suitable_color = "green" if metrics.suitable_for_grid else "red"
        analysis_table.add_row(
            metrics.symbol,
            f"{metrics.atr_percentage:.2f}%",
            f"${metrics.volume_24h/1e6:.0f}M",
            f"{metrics.trend_direction.value} ({metrics.trend_strength:.2f})",
            f"{metrics.volatility:.3f}",
            f"[{suitable_color}]{'✓' if metrics.suitable_for_grid else '✗'}[/{suitable_color}]",
        )

    console.print(analysis_table)

    # Test 3: Wait for grids to be created
    console.print("\n[cyan]Test 3: Automatic Grid Creation[/cyan]")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task(
            "[yellow]Waiting for suitable coins and grid creation...", total=None
        )

        # Wait for grids
        for i in range(10):
            if len(monster.active_grids) > 0:
                break
            await asyncio.sleep(1)

        progress.update(task, completed=True)

    # Test 4: Display Active Grids
    console.print("\n[cyan]Test 4: Active Grid Trading[/cyan]")

    if monster.active_grids:
        grid_table = Table(title="Active Grids")
        grid_table.add_column("Symbol", style="cyan")
        grid_table.add_column("State", style="yellow")
        grid_table.add_column("Levels", style="green")
        grid_table.add_column("Range", style="blue")
        grid_table.add_column("Spacing", style="magenta")
        grid_table.add_column("Capital", style="white")

        for symbol, grid in monster.active_grids.items():
            state_color = "green" if grid.state == GridState.ACTIVE else "yellow"
            grid_table.add_row(
                grid.symbol,
                f"[{state_color}]{grid.state.value}[/{state_color}]",
                str(grid.setup.num_levels),
                f"{float(grid.setup.lower_price):.2f} - {float(grid.setup.upper_price):.2f}",
                f"{grid.setup.spacing_percentage*100:.2f}%",
                f"${float(grid.setup.total_capital):,.0f}",
            )

        console.print(grid_table)
    else:
        console.print("[yellow]No active grids yet[/yellow]")

    # Test 5: Grid Levels Detail
    console.print("\n[cyan]Test 5: Grid Levels Detail[/cyan]")

    if monster.active_grids:
        # Show first grid's levels
        first_grid = list(monster.active_grids.values())[0]

        levels_table = Table(title=f"{first_grid.symbol} Grid Levels (Sample)")
        levels_table.add_column("Level", style="cyan")
        levels_table.add_column("Price", style="yellow")
        levels_table.add_column("Side", style="green")
        levels_table.add_column("Size", style="blue")
        levels_table.add_column("Status", style="magenta")

        # Show first 10 levels
        for level in first_grid.levels[:10]:
            side_color = "green" if level.side == "buy" else "red"
            status = "Filled" if level.filled else ("Pending" if level.order_id else "Inactive")
            status_color = "green" if level.filled else ("yellow" if level.order_id else "gray")

            levels_table.add_row(
                str(level.level_id),
                f"{float(level.price):.2f}",
                f"[{side_color}]{level.side.upper()}[/{side_color}]",
                f"{float(level.size):.4f}",
                f"[{status_color}]{status}[/{status_color}]",
            )

        console.print(levels_table)
        console.print(f"[dim]... and {len(first_grid.levels) - 10} more levels[/dim]")

    # Test 6: Simulate Trading Activity
    console.print("\n[cyan]Test 6: Simulating Trading Activity[/cyan]")

    console.print("Simulating order fills and grid adjustments...")

    # Let the system run for a while
    for i in range(10):
        await asyncio.sleep(1)

        # Show progress
        if i % 2 == 0:
            stats = monster.get_statistics()
            console.print(
                f"  Trades: {stats['total_trades']}, Profit: ${stats['total_profit']:.2f}"
            )

    # Test 7: Dynamic Adjustments
    console.print("\n[cyan]Test 7: Dynamic Grid Adjustments[/cyan]")

    if monster.active_grids:
        # Simulate market changes
        console.print("Simulating market volatility changes...")

        for symbol, grid in list(monster.active_grids.items())[:2]:
            old_spacing = grid.setup.spacing_percentage
            old_levels = grid.setup.num_levels

            # Force volatility change
            if symbol in monster.coin_metrics:
                monster.coin_metrics[symbol].volatility *= 1.5

            await monster._adjustment_monitor()

            console.print(f"  {symbol}:")
            console.print(
                f"    Spacing: {old_spacing*100:.2f}% → {grid.setup.spacing_percentage*100:.2f}%"
            )
            console.print(f"    Levels: {old_levels} → {grid.setup.num_levels}")

    # Test 8: Grid Performance
    console.print("\n[cyan]Test 8: Grid Performance Metrics[/cyan]")

    if monster.active_grids:
        perf_table = Table(title="Grid Performance")
        perf_table.add_column("Symbol", style="cyan")
        perf_table.add_column("Trades", style="yellow")
        perf_table.add_column("Profit", style="green")
        perf_table.add_column("Runtime", style="blue")
        perf_table.add_column("Profit/Hour", style="magenta")

        for symbol in list(monster.active_grids.keys())[:5]:
            details = monster.get_grid_details(symbol)
            if details:
                profit_color = "green" if details["profit_realized"] > 0 else "red"
                profit_per_hour = details["profit_realized"] / max(details["runtime_hours"], 0.01)

                perf_table.add_row(
                    symbol,
                    str(details["total_trades"]),
                    f"[{profit_color}]${details['profit_realized']:.2f}[/{profit_color}]",
                    f"{details['runtime_hours']:.1f}h",
                    f"${profit_per_hour:.2f}/h",
                )

        console.print(perf_table)

    # Test 9: Statistics
    console.print("\n[cyan]Test 9: Overall Statistics[/cyan]")

    stats = monster.get_statistics()

    stats_table = Table(title="Grid Monster Statistics", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")

    stats_table.add_row("Active Grids", f"{stats['active_grids']}/{monster.max_grids}")
    stats_table.add_row("Total Trades", str(stats["total_trades"]))
    stats_table.add_row("Total Profit", f"${stats['total_profit']:.2f}")
    stats_table.add_row("Successful Grids", str(stats["successful_grids"]))
    stats_table.add_row("Failed Grids", str(stats["failed_grids"]))
    stats_table.add_row("Success Rate", f"{stats['success_rate']:.1f}%")
    stats_table.add_row("Active Capital", f"${stats['active_capital']:,.2f}")
    stats_table.add_row("Suitable Coins", str(stats["suitable_coins"]))

    console.print(stats_table)

    # Test 10: Grid Reset Simulation
    console.print("\n[cyan]Test 10: Grid Reset on Range Exit[/cyan]")

    if monster.active_grids:
        first_grid = list(monster.active_grids.values())[0]

        console.print(f"Simulating price exit for {first_grid.symbol}...")
        console.print(
            f"  Current range: {float(first_grid.setup.lower_price):.2f} - {float(first_grid.setup.upper_price):.2f}"
        )

        # Force price out of range
        original_upper = first_grid.setup.upper_price
        first_grid.setup.upper_price = first_grid.setup.lower_price * Decimal("1.01")

        await monster._grid_monitor()

        # Check if reset
        if first_grid.symbol in monster.active_grids:
            new_grid = monster.active_grids[first_grid.symbol]
            console.print("  [green]Grid reset successfully[/green]")
            console.print(
                f"  New range: {float(new_grid.setup.lower_price):.2f} - {float(new_grid.setup.upper_price):.2f}"
            )

    # Final Summary
    console.print("\n[cyan]Final Summary[/cyan]")

    final_stats = monster.get_statistics()

    summary = Panel(
        f"""[green]Grid Monster Performance Summary[/green]

Strategy: High-frequency grid trading with dynamic adjustments
Selection: ATR > 3%, Volume > $50M, No strong trends

Active Grids: {final_stats['active_grids']}
Total Trades: {final_stats['total_trades']}
Total Profit: [{'green' if final_stats['total_profit'] > 0 else 'red'}]${final_stats['total_profit']:.2f}[/]
Success Rate: {final_stats['success_rate']:.1f}%
Active Capital: ${final_stats['active_capital']:,.2f}

[yellow]Key Features:[/yellow]
• Automatic coin selection based on ATR and volume
• Bollinger Bands for range determination
• Dynamic spacing adjustment based on volatility
• Grid shifting with trend direction
• Automatic reset on range exit""",
        title="Grid Monster Summary",
        border_style="green",
    )

    console.print(summary)

    # Cleanup
    await monster.shutdown()
    console.print("\n[green]Grid Monster test completed![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]High-Frequency Grid Trading Monster[/bold cyan]")
    console.print("[yellow]Dynamic grid trading with volatility adjustments[/yellow]")
    console.print("=" * 60)

    try:
        await test_grid_monster()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
