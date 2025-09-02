#!/usr/bin/env python3
"""
Test the production-ready exchange system
"""

import asyncio
import logging
from decimal import Decimal

from rich.console import Console
from rich.table import Table
from src.exchanges.base import OrderSide, OrderType
from src.exchanges.manager import ExchangeManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()


async def test_exchange_system():
    """Test the exchange system with mock exchanges"""

    # Configuration
    config = {
        "test_mode": True,
        "prefer_low_fees": True,
        "max_slippage": "0.002",
        "min_arbitrage_profit": "0.001",
        "arbitrage_enabled": True,
        "exchanges": {
            "binance": {
                "mock": True,
                "api_key": "test_key",
                "api_secret": "test_secret",
                "maker_fee": "0.001",
                "taker_fee": "0.001",
                "min_latency": 50,
                "max_latency": 150,
                "fail_rate": 0.01,
            },
            "gateio": {
                "mock": True,
                "api_key": "test_key",
                "api_secret": "test_secret",
                "maker_fee": "0.002",
                "taker_fee": "0.002",
                "min_latency": 100,
                "max_latency": 300,
                "fail_rate": 0.02,
            },
            "bybit": {
                "mock": True,
                "api_key": "test_key",
                "api_secret": "test_secret",
                "maker_fee": "0.0006",
                "taker_fee": "0.001",
                "min_latency": 70,
                "max_latency": 200,
                "fail_rate": 0.015,
            },
        },
        "arbitrage_symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
    }

    # Initialize manager
    manager = ExchangeManager(config)
    await manager.initialize()

    console.print("[green]Exchange Manager initialized[/green]")

    # Test 1: Check connections and latency
    console.print("\n[cyan]Test 1: Exchange Connections and Latency[/cyan]")
    latencies = await manager.get_latency_report()

    table = Table(title="Exchange Status")
    table.add_column("Exchange", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Latency (ms)", style="yellow")

    for exchange_name, latency in latencies.items():
        status = manager.exchanges[exchange_name].status.value
        table.add_row(exchange_name, status, str(latency))

    console.print(table)

    # Test 2: Get aggregated balance
    console.print("\n[cyan]Test 2: Aggregated Balance[/cyan]")
    total_balance = await manager.get_aggregated_balance()

    balance_table = Table(title="Total Balance Across Exchanges")
    balance_table.add_column("Currency", style="cyan")
    balance_table.add_column("Amount", style="green")

    for currency, amount in total_balance.items():
        balance_table.add_row(currency, f"{amount:.8f}")

    console.print(balance_table)

    # Test 3: Best price routing
    console.print("\n[cyan]Test 3: Best Price Routing[/cyan]")

    symbol = "BTC/USDT"
    amount = Decimal("0.01")

    buy_route = await manager.get_best_price(symbol, OrderSide.BUY, amount)
    sell_route = await manager.get_best_price(symbol, OrderSide.SELL, amount)

    if buy_route:
        console.print(f"Best BUY route for {amount} BTC:")
        console.print(f"  Exchange: [green]{buy_route.exchange}[/green]")
        console.print(f"  Price: ${buy_route.price:.2f}")
        console.print(f"  Fee: {buy_route.fee:.4%}")
        console.print(f"  Effective Price: ${buy_route.effective_price:.2f}")

    if sell_route:
        console.print(f"\nBest SELL route for {amount} BTC:")
        console.print(f"  Exchange: [green]{sell_route.exchange}[/green]")
        console.print(f"  Price: ${sell_route.price:.2f}")
        console.print(f"  Fee: {sell_route.fee:.4%}")
        console.print(f"  Effective Price: ${sell_route.effective_price:.2f}")

    # Test 4: Place orders
    console.print("\n[cyan]Test 4: Order Placement[/cyan]")

    try:
        # Place a market buy order
        buy_order = await manager.route_order(
            symbol="ETH/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=Decimal("0.1"),
        )

        console.print("[green]Market BUY order placed:[/green]")
        console.print(f"  Order ID: {buy_order.id}")
        console.print(f"  Exchange: {buy_order.exchange}")
        console.print(f"  Price: ${buy_order.price:.2f}")
        console.print(f"  Status: {buy_order.status.value}")

        # Place a limit sell order
        sell_order = await manager.route_order(
            symbol="BNB/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            amount=Decimal("1"),
            price=Decimal("450"),
        )

        console.print("\n[green]Limit SELL order placed:[/green]")
        console.print(f"  Order ID: {sell_order.id}")
        console.print(f"  Exchange: {sell_order.exchange}")
        console.print(f"  Price: ${sell_order.price:.2f}")
        console.print(f"  Status: {sell_order.status.value}")

    except Exception as e:
        console.print(f"[red]Order failed: {e}[/red]")

    # Test 5: Arbitrage scanning
    console.print("\n[cyan]Test 5: Arbitrage Opportunities[/cyan]")

    opportunities = await manager.scan_arbitrage(["BTC/USDT", "ETH/USDT"])

    if opportunities:
        arb_table = Table(title="Arbitrage Opportunities")
        arb_table.add_column("Symbol", style="cyan")
        arb_table.add_column("Buy Exchange", style="green")
        arb_table.add_column("Buy Price", style="yellow")
        arb_table.add_column("Sell Exchange", style="green")
        arb_table.add_column("Sell Price", style="yellow")
        arb_table.add_column("Profit %", style="magenta")
        arb_table.add_column("Est. Profit", style="magenta")

        for opp in opportunities[:5]:
            arb_table.add_row(
                opp.symbol,
                opp.buy_exchange,
                f"${opp.buy_price:.2f}",
                opp.sell_exchange,
                f"${opp.sell_price:.2f}",
                f"{opp.profit_percentage:.3%}",
                f"${opp.estimated_profit:.2f}",
            )

        console.print(arb_table)
    else:
        console.print("[yellow]No arbitrage opportunities found[/yellow]")

    # Test 6: WebSocket subscriptions
    console.print("\n[cyan]Test 6: Real-time Data Streams[/cyan]")

    # Track ticker updates
    ticker_updates = []

    async def ticker_callback(ticker):
        ticker_updates.append(ticker)
        if len(ticker_updates) <= 3:
            console.print(f"Ticker update: {ticker.symbol} ${ticker.last:.2f}")

    # Subscribe to BTC ticker
    if "binance" in manager.exchanges:
        exchange = manager.exchanges["binance"]
        task = asyncio.create_task(exchange.subscribe_ticker("BTC/USDT", ticker_callback))

        # Wait for a few updates
        await asyncio.sleep(5)
        task.cancel()

        console.print(f"[green]Received {len(ticker_updates)} ticker updates[/green]")

    # Test 7: Emergency functions
    console.print("\n[cyan]Test 7: Emergency Functions[/cyan]")

    # Cancel all open orders
    cancelled = await manager.emergency_cancel_all()

    total_cancelled = sum(len(orders) for orders in cancelled.values())
    console.print(f"[yellow]Cancelled {total_cancelled} orders across all exchanges[/yellow]")

    # Test 8: Performance metrics
    console.print("\n[cyan]Test 8: Exchange Metrics[/cyan]")

    metrics_table = Table(title="Exchange Performance Metrics")
    metrics_table.add_column("Exchange", style="cyan")
    metrics_table.add_column("Latency (ms)", style="yellow")
    metrics_table.add_column("Success Rate", style="green")
    metrics_table.add_column("Total Volume", style="blue")
    metrics_table.add_column("Total Fees", style="red")

    for name, metrics in manager.metrics.items():
        metrics_table.add_row(
            name,
            str(metrics.latency_ms),
            f"{metrics.success_rate:.1f}%",
            f"${metrics.total_volume:.2f}",
            f"${metrics.total_fees:.2f}",
        )

    console.print(metrics_table)

    # Cleanup
    await manager.shutdown()
    console.print("\n[green]Test completed successfully![/green]")


async def main():
    """Main entry point"""
    console.print("[bold cyan]Sofia V2 - Production-Ready Exchange System Test[/bold cyan]")
    console.print("=" * 60)

    try:
        await test_exchange_system()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        logger.exception("Test error")


if __name__ == "__main__":
    asyncio.run(main())
