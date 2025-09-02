#!/usr/bin/env python3
"""
Test Turkish Arbitrage System
BTCTurk vs Binance TR vs Paribu
"""

import asyncio
from decimal import Decimal

from rich.console import Console
from rich.table import Table
from src.strategies.turkish_arbitrage import TurkishArbitrageSystem

console = Console()


async def test_turkish_arbitrage():
    """Test the Turkish arbitrage system"""

    # Configuration
    config = {
        "btcturk_api_key": "mock_key",
        "btcturk_api_secret": "mock_secret",
        "binance_tr_api_key": "mock_key",
        "binance_tr_api_secret": "mock_secret",
        "paribu_api_key": "mock_key",
        "paribu_api_secret": "mock_secret",
        "min_profit_tl": 100,  # Minimum 100 TL profit
        "max_position_tl": 20000,  # Maximum 20,000 TL per trade
        "max_daily_trades": 50,
        "cooldown_seconds": 30,
        "min_spread_percentage": 0.003,  # 0.3% minimum spread
        "execution_timeout": 10,
        "max_slippage": 0.002,  # 0.2% maximum slippage
        "min_liquidity": 10000,  # Minimum 10,000 TL liquidity
        "partial_fill_threshold": 0.95,  # 95% fill required
    }

    # Initialize system
    arbitrage = TurkishArbitrageSystem(config)
    await arbitrage.initialize()

    console.print("[green]Turkish Arbitrage System initialized[/green]")
    console.print("=" * 60)

    # Test 1: Exchange Setup
    console.print("\n[cyan]Test 1: Exchange Configuration[/cyan]")

    exchange_table = Table(title="Turkish Exchanges")
    exchange_table.add_column("Exchange", style="cyan")
    exchange_table.add_column("Maker Fee", style="yellow")
    exchange_table.add_column("Taker Fee", style="yellow")
    exchange_table.add_column("API URL", style="green")

    for exchange, config in arbitrage.exchanges.items():
        exchange_table.add_row(
            exchange.value,
            f"{float(config.maker_fee)*100:.2f}%",
            f"{float(config.taker_fee)*100:.2f}%",
            config.api_url,
        )

    console.print(exchange_table)

    # Test 2: Fetch Order Books
    console.print("\n[cyan]Test 2: Order Book Fetching[/cyan]")

    symbols = ["BTCTRY", "ETHTRY", "USDTTRY"]

    for symbol in symbols:
        orderbook_table = Table(title=f"{symbol} Order Books")
        orderbook_table.add_column("Exchange", style="cyan")
        orderbook_table.add_column("Best Bid", style="green")
        orderbook_table.add_column("Best Ask", style="red")
        orderbook_table.add_column("Spread", style="yellow")
        orderbook_table.add_column("Liquidity (3 levels)", style="blue")

        for exchange in arbitrage.exchanges:
            book = await arbitrage.fetch_orderbook(exchange, symbol)
            if book:
                orderbook_table.add_row(
                    exchange.value,
                    f"{book.best_bid:,.2f} TL" if book.best_bid else "N/A",
                    f"{book.best_ask:,.2f} TL" if book.best_ask else "N/A",
                    f"{book.spread:,.2f} TL" if book.spread else "N/A",
                    f"{book.get_liquidity('bid', 3):,.0f} TL",
                )

        console.print(orderbook_table)

    # Test 3: Calculate Arbitrage Opportunities
    console.print("\n[cyan]Test 3: Arbitrage Opportunity Detection[/cyan]")

    opportunities_found = []

    for symbol in ["BTCTRY", "ETHTRY"]:
        # Fetch orderbooks
        orderbooks = {}
        for exchange in arbitrage.exchanges:
            book = await arbitrage.fetch_orderbook(exchange, symbol)
            if book:
                orderbooks[exchange] = book

        # Calculate opportunities
        opportunities = arbitrage.calculate_arbitrage(symbol, orderbooks)
        opportunities_found.extend(opportunities)

    if opportunities_found:
        opp_table = Table(title="Arbitrage Opportunities")
        opp_table.add_column("Symbol", style="cyan")
        opp_table.add_column("Buy Exchange", style="green")
        opp_table.add_column("Buy Price", style="green")
        opp_table.add_column("Sell Exchange", style="red")
        opp_table.add_column("Sell Price", style="red")
        opp_table.add_column("Spread %", style="yellow")
        opp_table.add_column("Net Profit", style="magenta")

        for opp in opportunities_found[:5]:  # Show top 5
            profit_color = "green" if opp.net_profit > 0 else "red"
            opp_table.add_row(
                opp.symbol,
                opp.buy_exchange.value,
                f"{opp.buy_price:,.2f} TL",
                opp.sell_exchange.value,
                f"{opp.sell_price:,.2f} TL",
                f"{opp.spread_percentage:.3f}%",
                f"[{profit_color}]{opp.net_profit:,.2f} TL[/{profit_color}]",
            )

        console.print(opp_table)
    else:
        console.print("[yellow]No arbitrage opportunities found[/yellow]")

    # Test 4: Execute Arbitrage (Simulation)
    console.print("\n[cyan]Test 4: Arbitrage Execution Simulation[/cyan]")

    if opportunities_found and opportunities_found[0].net_profit > 0:
        opp = opportunities_found[0]
        console.print(f"Executing arbitrage for {opp.symbol}...")
        console.print(
            f"  Buy {opp.max_amount:.4f} from {opp.buy_exchange.value} @ {opp.buy_price:,.2f} TL"
        )
        console.print(
            f"  Sell {opp.max_amount:.4f} to {opp.sell_exchange.value} @ {opp.sell_price:,.2f} TL"
        )

        result = await arbitrage.execute_arbitrage(opp)

        if result.success:
            console.print(f"[green]SUCCESS![/green] Actual profit: {result.actual_profit:,.2f} TL")
            console.print(f"  Execution time: {result.execution_time:.2f} seconds")
            console.print(f"  Buy filled: {result.buy_filled:.4f}")
            console.print(f"  Sell filled: {result.sell_filled:.4f}")
        else:
            console.print(f"[red]FAILED![/red] Error: {result.error}")

    # Test 5: Spread Monitoring
    console.print("\n[cyan]Test 5: Real-time Spread Monitoring[/cyan]")

    # Let it monitor for a few seconds
    await asyncio.sleep(3)

    spread_table = Table(title="Spread History Summary")
    spread_table.add_column("Symbol", style="cyan")
    spread_table.add_column("Samples", style="yellow")
    spread_table.add_column("Max Spread %", style="green")
    spread_table.add_column("Avg Spread %", style="blue")

    for symbol, history in arbitrage.spread_history.items():
        if history:
            recent = list(history)
            max_spread = max(h["max_spread"] for h in recent)
            avg_spread = sum(h["avg_spread"] for h in recent) / len(recent)

            spread_table.add_row(
                symbol, str(len(recent)), f"{max_spread:.3f}%", f"{avg_spread:.3f}%"
            )

    console.print(spread_table)

    # Test 6: System Statistics
    console.print("\n[cyan]Test 6: System Statistics[/cyan]")

    stats = arbitrage.get_statistics()

    stats_table = Table(title="Trading Statistics", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")

    stats_table.add_row("Opportunities Found", str(stats["opportunities_found"]))
    stats_table.add_row("Trades Executed", str(stats["trades_executed"]))
    stats_table.add_row("Successful Trades", str(stats["trades_successful"]))
    stats_table.add_row("Success Rate", f"{stats['success_rate']:.1f}%")
    stats_table.add_row("Total Profit", f"{stats['total_profit']:,.2f} TL")
    stats_table.add_row("Total Volume", f"{stats['total_volume']:,.2f} TL")
    stats_table.add_row("Daily Trades", f"{stats['daily_trades']}/{arbitrage.max_daily_trades}")

    console.print(stats_table)

    # Test 7: Backtest
    console.print("\n[cyan]Test 7: Backtest Simulation[/cyan]")

    console.print("Running backtest with 1000 historical opportunities...")
    backtest_results = await arbitrage.backtest(num_opportunities=1000)

    backtest_table = Table(title="Backtest Results", show_header=False)
    backtest_table.add_column("Metric", style="cyan")
    backtest_table.add_column("Value", style="yellow")

    backtest_table.add_row("Total Opportunities", str(backtest_results["total_opportunities"]))
    backtest_table.add_row(
        "Profitable Opportunities", str(backtest_results["profitable_opportunities"])
    )
    backtest_table.add_row("Executed Trades", str(backtest_results["executed_trades"]))
    backtest_table.add_row("Successful Trades", str(backtest_results["successful_trades"]))
    backtest_table.add_row("Success Rate", f"{backtest_results['success_rate']:.2f}%")
    backtest_table.add_row("Total Profit", f"{backtest_results['total_profit']:,.2f} TL")
    backtest_table.add_row("Average Profit", f"{backtest_results['avg_profit']:,.2f} TL")
    backtest_table.add_row("Max Profit", f"{backtest_results['max_profit']:,.2f} TL")
    backtest_table.add_row("Min Profit", f"{backtest_results['min_profit']:,.2f} TL")
    backtest_table.add_row("Total Volume", f"{backtest_results['total_volume']:,.2f} TL")

    console.print(backtest_table)

    # Test 8: Fee Comparison
    console.print("\n[cyan]Test 8: Fee Impact Analysis[/cyan]")

    fee_table = Table(title="Fee Impact on 10,000 TL Trade")
    fee_table.add_column("Exchange", style="cyan")
    fee_table.add_column("Buy Fee", style="yellow")
    fee_table.add_column("Sell Fee", style="yellow")
    fee_table.add_column("Total Cost", style="red")
    fee_table.add_column("Min Spread Needed", style="green")

    trade_amount = Decimal("10000")

    for exchange, config in arbitrage.exchanges.items():
        buy_fee = trade_amount * config.taker_fee
        sell_fee = trade_amount * config.taker_fee
        total_cost = buy_fee + sell_fee
        min_spread = (config.taker_fee * 2) * 100  # As percentage

        fee_table.add_row(
            exchange.value,
            f"{buy_fee:.2f} TL",
            f"{sell_fee:.2f} TL",
            f"{total_cost:.2f} TL",
            f"{float(min_spread):.3f}%",
        )

    console.print(fee_table)

    # Cleanup
    await arbitrage.shutdown()
    console.print("\n[green]Turkish Arbitrage System test completed![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]Turkish Cryptocurrency Arbitrage System[/bold cyan]")
    console.print("[yellow]BTCTurk vs Binance TR vs Paribu[/yellow]")
    console.print("=" * 60)

    try:
        await test_turkish_arbitrage()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
