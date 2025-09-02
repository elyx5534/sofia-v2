#!/usr/bin/env python3
"""
Test Binance Funding Rate Farmer
Delta-neutral strategy that harvests funding rates
"""

import asyncio
import time
from decimal import Decimal

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from src.strategies.funding_farmer import (
    FundingRateFarmer,
)

console = Console()


async def test_funding_farmer():
    """Test the funding rate farmer"""

    # Configuration
    config = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "testnet": True,
        "min_funding_rate": -0.0001,  # -0.01% minimum negative funding
        "max_positions": 5,
        "position_size_pct": 0.06,  # 6% of capital per position
        "max_total_exposure": 0.30,  # 30% max total exposure
        "rebalance_threshold": 0.02,  # 2% deviation triggers rebalance
        "close_on_positive": True,  # Close when funding turns positive
        "compound_earnings": True,  # Reinvest funding earnings
        "funding_lookback_hours": 168,  # 7 days for prediction
        "min_volume_24h": 10000000,  # $10M minimum daily volume
        "max_leverage": 2,  # Conservative leverage
        "scan_interval": 300,  # Scan every 5 minutes
        "rebalance_check_interval": 900,  # Check rebalance every 15 minutes
    }

    # Initialize farmer
    farmer = FundingRateFarmer(config)
    await farmer.initialize()

    console.print("[green]Funding Rate Farmer initialized[/green]")
    console.print("=" * 60)

    # Test 1: Configuration Display
    console.print("\n[cyan]Test 1: Farmer Configuration[/cyan]")

    config_table = Table(title="Funding Strategy Parameters")
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="yellow")

    config_table.add_row("Min Funding Rate", f"{float(farmer.min_funding_rate)*100:.3f}%")
    config_table.add_row("Max Positions", str(farmer.max_positions))
    config_table.add_row("Position Size", f"{float(farmer.position_size_pct)*100:.1f}% of capital")
    config_table.add_row("Max Exposure", f"{float(farmer.max_total_exposure)*100:.0f}%")
    config_table.add_row("Rebalance Threshold", f"{float(farmer.rebalance_threshold)*100:.1f}%")
    config_table.add_row("Close on Positive", "Yes" if farmer.close_on_positive else "No")
    config_table.add_row("Compound Earnings", "Yes" if farmer.compound_earnings else "No")
    config_table.add_row("Max Leverage", f"{farmer.max_leverage}x")

    console.print(config_table)

    # Test 2: Scan for Opportunities
    console.print("\n[cyan]Test 2: Scanning for Funding Opportunities[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[yellow]Scanning all Binance perpetuals...", total=100)

        # Simulate scanning
        opportunities = await farmer.scan_funding_opportunities()
        progress.update(task, completed=100)

    if opportunities:
        opp_table = Table(title="Top Funding Opportunities")
        opp_table.add_column("Symbol", style="cyan")
        opp_table.add_column("Current Rate", style="red")
        opp_table.add_column("Next Rate", style="yellow")
        opp_table.add_column("Avg 7D", style="blue")
        opp_table.add_column("Volume 24h", style="green")
        opp_table.add_column("Predicted", style="magenta")
        opp_table.add_column("Score", style="white")

        for opp in opportunities[:10]:  # Top 10
            rate_color = "red" if opp.current_rate < 0 else "green"
            opp_table.add_row(
                opp.symbol,
                f"[{rate_color}]{opp.current_rate*100:.4f}%[/{rate_color}]",
                f"{opp.next_rate*100:.4f}%",
                f"{opp.avg_rate_7d*100:.4f}%",
                f"${opp.volume_24h/1e6:.1f}M",
                f"{opp.predicted_rate*100:.4f}%",
                f"{opp.opportunity_score:.2f}",
            )

        console.print(opp_table)
    else:
        console.print("[yellow]No funding opportunities found[/yellow]")

    # Test 3: Open Delta-Neutral Positions
    console.print("\n[cyan]Test 3: Opening Delta-Neutral Positions[/cyan]")

    # Open positions for top opportunities
    positions_opened = []
    for opp in opportunities[:3]:  # Open top 3
        console.print(f"Opening position for {opp.symbol}...")
        position = await farmer.open_position(opp)

        if position:
            positions_opened.append(position)
            console.print(
                f"[green]✓[/green] Opened: LONG {position.perp_symbol} + SHORT {position.spot_symbol}"
            )
            console.print(
                f"  Size: {position.position_size:.4f} ({position.position_value:.2f} USDT)"
            )
            console.print(f"  Funding Rate: {position.funding_rate*100:.4f}%")
        else:
            console.print(f"[red]✗[/red] Failed to open position for {opp.symbol}")

    await asyncio.sleep(2)

    # Test 4: Display Active Positions
    console.print("\n[cyan]Test 4: Active Delta-Neutral Positions[/cyan]")

    if farmer.positions:
        positions_table = Table(title="Delta-Neutral Positions")
        positions_table.add_column("Pair", style="cyan")
        positions_table.add_column("Size", style="yellow")
        positions_table.add_column("Value", style="green")
        positions_table.add_column("Funding", style="red")
        positions_table.add_column("Earned", style="magenta")
        positions_table.add_column("Delta", style="blue")
        positions_table.add_column("Time", style="white")

        for pos_id, position in farmer.positions.items():
            delta_color = "green" if abs(position.delta) < 0.01 else "yellow"
            positions_table.add_row(
                f"{position.perp_symbol}/{position.spot_symbol}",
                f"{position.position_size:.4f}",
                f"${position.position_value:.2f}",
                f"{position.funding_rate*100:.4f}%",
                f"${position.funding_earned:.2f}",
                f"[{delta_color}]{position.delta:.4f}[/{delta_color}]",
                f"{(time.time() - position.entry_time)/3600:.1f}h",
            )

        console.print(positions_table)

    # Test 5: Simulate Funding Collection
    console.print("\n[cyan]Test 5: Simulating Funding Collection (8 hours)[/cyan]")

    # Simulate 8-hour funding period
    for hour in range(1, 9):
        console.print(f"\nHour {hour}:")

        # Collect funding every 8 hours
        if hour == 8:
            total_collected = Decimal("0")
            for position in farmer.positions.values():
                funding = position.position_value * abs(position.funding_rate)
                position.funding_earned += funding
                total_collected += funding
                console.print(f"  {position.perp_symbol}: Collected {funding:.2f} USDT")

            console.print(f"[green]Total collected: {total_collected:.2f} USDT[/green]")

        # Check for rebalancing
        if hour % 4 == 0:
            console.print("  Checking position deltas for rebalancing...")
            await farmer.check_rebalancing()

        await asyncio.sleep(0.5)  # Simulate time passing

    # Test 6: Rebalancing
    console.print("\n[cyan]Test 6: Position Rebalancing[/cyan]")

    # Force a rebalance by simulating price movement
    if farmer.positions:
        position = list(farmer.positions.values())[0]
        position.perp_price *= Decimal("1.03")  # 3% price increase

        console.print(f"Price moved: {position.perp_symbol} +3%")
        console.print(f"Delta before: {position.delta:.4f}")

        rebalanced = await farmer.rebalance_position(position)

        if rebalanced:
            console.print("[green]Rebalanced successfully[/green]")
            console.print(f"Delta after: {position.delta:.4f}")
        else:
            console.print("[yellow]Rebalancing not needed or failed[/yellow]")

    # Test 7: Funding Rate Prediction
    console.print("\n[cyan]Test 7: Funding Rate Prediction[/cyan]")

    prediction_table = Table(title="Funding Rate Predictions")
    prediction_table.add_column("Symbol", style="cyan")
    prediction_table.add_column("Current", style="yellow")
    prediction_table.add_column("Predicted Next", style="green")
    prediction_table.add_column("Confidence", style="magenta")
    prediction_table.add_column("Trend", style="blue")

    for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
        prediction = await farmer.predict_funding_rate(symbol)

        if prediction:
            trend = "↑" if prediction["predicted"] > prediction["current"] else "↓"
            trend_color = "green" if prediction["predicted"] < 0 else "red"

            prediction_table.add_row(
                symbol,
                f"{prediction['current']*100:.4f}%",
                f"{prediction['predicted']*100:.4f}%",
                f"{prediction['confidence']:.1f}%",
                f"[{trend_color}]{trend}[/{trend_color}]",
            )

    console.print(prediction_table)

    # Test 8: Close Positions (Funding turns positive)
    console.print("\n[cyan]Test 8: Closing Positions (Funding Positive)[/cyan]")

    # Simulate funding turning positive
    closed_positions = []
    for position in list(farmer.positions.values()):
        position.funding_rate = Decimal("0.0002")  # Positive funding

        console.print(f"Funding turned positive for {position.perp_symbol}")
        result = await farmer.close_position(position)

        if result["success"]:
            closed_positions.append(result)
            console.print(f"[green]✓[/green] Closed with profit: {result['total_pnl']:.2f} USDT")

    # Test 9: Statistics
    console.print("\n[cyan]Test 9: Farming Statistics[/cyan]")

    stats = farmer.get_statistics()

    stats_table = Table(title="Performance Metrics", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")

    stats_table.add_row("Total Funding Earned", f"${stats['total_funding_earned']:.2f}")
    stats_table.add_row("Active Positions", f"{stats['active_positions']}/{farmer.max_positions}")
    stats_table.add_row("Total Exposure", f"{stats['total_exposure']*100:.1f}%")
    stats_table.add_row("Average Delta", f"{stats['avg_delta']:.4f}")
    stats_table.add_row("Positions Opened", str(stats["positions_opened"]))
    stats_table.add_row("Positions Closed", str(stats["positions_closed"]))
    stats_table.add_row("Rebalances", str(stats["total_rebalances"]))
    stats_table.add_row("Failed Rebalances", str(stats["failed_rebalances"]))

    console.print(stats_table)

    # Test 10: Historical Analysis
    console.print("\n[cyan]Test 10: Historical Funding Analysis[/cyan]")

    history_table = Table(title="7-Day Funding History")
    history_table.add_column("Symbol", style="cyan")
    history_table.add_column("Avg Rate", style="yellow")
    history_table.add_column("Min Rate", style="red")
    history_table.add_column("Max Rate", style="green")
    history_table.add_column("Negative %", style="magenta")
    history_table.add_column("Total Earned", style="blue")

    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        history = await farmer.get_funding_history(symbol, days=7)

        if history:
            negative_pct = (history["negative_count"] / history["total_count"]) * 100

            history_table.add_row(
                symbol,
                f"{history['avg_rate']*100:.4f}%",
                f"{history['min_rate']*100:.4f}%",
                f"{history['max_rate']*100:.4f}%",
                f"{negative_pct:.1f}%",
                f"${history.get('theoretical_earnings', 0):.2f}",
            )

    console.print(history_table)

    # Final Summary
    console.print("\n[cyan]Final Summary[/cyan]")

    summary = Panel(
        f"""[green]Funding Rate Farmer Performance[/green]

Strategy: Delta-neutral positions to harvest negative funding rates
Risk: Minimal directional risk through spot/perp hedging

Total Funding Earned: [green]${stats['total_funding_earned']:.2f}[/green]
Positions Opened: {stats['positions_opened']}
Positions Closed: {stats['positions_closed']}
Average Delta: {stats['avg_delta']:.4f} (near-perfect hedge)
Rebalance Success: {((stats['total_rebalances'] - stats['failed_rebalances']) / max(stats['total_rebalances'], 1)) * 100:.1f}%

[yellow]Key Features:[/yellow]
• Automatic funding rate scanning
• Delta-neutral position management
• Dynamic rebalancing every 4 hours
• Funding rate prediction
• Compound earnings option""",
        title="Funding Farmer Summary",
        border_style="green",
    )

    console.print(summary)

    # Cleanup
    await farmer.shutdown()
    console.print("\n[green]Funding Rate Farmer test completed![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]Binance Funding Rate Farmer[/bold cyan]")
    console.print("[yellow]Delta-neutral strategy for harvesting funding rates[/yellow]")
    console.print("=" * 60)

    try:
        await test_funding_farmer()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
