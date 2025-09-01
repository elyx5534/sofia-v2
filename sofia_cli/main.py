"""Sofia V2 CLI - Main command-line interface"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(
    name="sofia",
    help="Sofia V2 Trading Platform CLI",
    add_completion=False
)
console = Console()

@app.command()
def fetch(
    symbol: str = typer.Argument(..., help="Symbol to fetch (e.g., BTCUSDT)"),
    period: str = typer.Option("1d", help="Time period (1d, 7d, 30d, 90d)"),
    interval: str = typer.Option("1h", help="Candle interval (1m, 5m, 1h, 1d)")
):
    """Fetch and display market data for a symbol"""
    try:
        # This would normally fetch from DataHub
        console.print(f"[green]Fetching {symbol} data...[/green]")
        console.print(f"Period: {period}, Interval: {interval}")
        
        # Mock data for demonstration
        table = Table(title=f"{symbol} Recent Data")
        table.add_column("Time", style="cyan")
        table.add_column("Open", style="green")
        table.add_column("High", style="green")
        table.add_column("Low", style="red")
        table.add_column("Close", style="yellow")
        table.add_column("Volume", style="magenta")
        
        # Add mock rows
        for i in range(5):
            table.add_row(
                f"2024-01-{20+i} 12:00",
                "50000.00",
                "50500.00",
                "49500.00",
                "50250.00",
                "1234.56"
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def backtest(
    symbol: str = typer.Argument(..., help="Symbol to backtest"),
    strategy: str = typer.Option("trend", help="Strategy type (grid, trend)"),
    fast: int = typer.Option(20, help="Fast MA period"),
    slow: int = typer.Option(60, help="Slow MA period"),
    days: int = typer.Option(90, help="Number of days to backtest")
):
    """Run a backtest on historical data"""
    console.print(f"[cyan]Running {strategy} backtest on {symbol}...[/cyan]")
    console.print(f"Parameters: fast={fast}, slow={slow}, days={days}")
    
    # Mock backtest results
    results = {
        "total_trades": 42,
        "win_rate": 57.8,
        "total_pnl": 1234.56,
        "sharpe_ratio": 1.25,
        "max_drawdown": -8.5
    }
    
    # Display results table
    table = Table(title="Backtest Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Total Trades", str(results["total_trades"]))
    table.add_row("Win Rate", f"{results['win_rate']:.1f}%")
    table.add_row("Total P&L", f"${results['total_pnl']:.2f}")
    table.add_row("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
    table.add_row("Max Drawdown", f"{results['max_drawdown']:.1f}%")
    
    console.print(table)
    console.print("[green]✓ Backtest completed successfully[/green]")

@app.command()
def portfolio(
    action: str = typer.Argument(..., help="Action: apply, show, rebalance"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Portfolio config file")
):
    """Manage paper trading portfolio"""
    if action == "apply":
        if not file:
            console.print("[red]Error: --file required for apply action[/red]")
            raise typer.Exit(1)
        
        config_path = Path(file)
        if not config_path.exists():
            console.print(f"[red]Error: Config file not found: {file}[/red]")
            raise typer.Exit(1)
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        console.print(f"[cyan]Applying portfolio configuration from {file}...[/cyan]")
        
        # Display portfolio allocation
        allocations = config.get("allocations", {})
        table = Table(title="Portfolio Allocation")
        table.add_column("Symbol", style="cyan")
        table.add_column("Weight", style="yellow")
        table.add_column("Strategy", style="green")
        table.add_column("Profile", style="magenta")
        
        for symbol, alloc in allocations.items():
            table.add_row(
                symbol,
                f"{alloc['weight']*100:.0f}%",
                alloc.get("strategy", "grid"),
                alloc.get("config_profile", "default")
            )
        
        console.print(table)
        console.print("[green]✓ Portfolio configuration applied[/green]")
        
    elif action == "show":
        console.print("[cyan]Current Portfolio Status[/cyan]")
        
        # Mock portfolio data
        table = Table(title="Active Positions")
        table.add_column("Symbol", style="cyan")
        table.add_column("Quantity", style="yellow")
        table.add_column("Avg Price", style="green")
        table.add_column("Current Price", style="green")
        table.add_column("P&L", style="red")
        
        table.add_row("BTCUSDT", "0.0015", "$51,234", "$51,500", "+$399.00")
        table.add_row("ETHUSDT", "0.234", "$3,234", "$3,250", "+$37.44")
        
        console.print(table)
        
    elif action == "rebalance":
        console.print("[cyan]Rebalancing portfolio...[/cyan]")
        console.print("[green]✓ Portfolio rebalanced successfully[/green]")
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Valid actions: apply, show, rebalance")
        raise typer.Exit(1)

@app.command()
def ui(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload")
):
    """Start the web UI server"""
    console.print(f"[cyan]Starting Sofia V2 Web UI...[/cyan]")
    console.print(f"Server: http://{host}:{port}")
    
    try:
        import uvicorn
        uvicorn.run(
            "sofia_ui.server_v2:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except ImportError:
        console.print("[red]Error: uvicorn not installed[/red]")
        console.print("Run: pip install uvicorn")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error starting UI: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def status():
    """Check system status"""
    console.print("[cyan]Checking Sofia V2 system status...[/cyan]")
    
    # Check services
    services = {
        "ClickHouse": check_clickhouse(),
        "NATS": check_nats(),
        "Redis": check_redis(),
        "DataHub": check_datahub(),
        "Paper Trading": check_paper_trading()
    }
    
    table = Table(title="System Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    
    for service, (status, details) in services.items():
        status_icon = "✓" if status else "✗"
        status_color = "green" if status else "red"
        table.add_row(
            service,
            f"[{status_color}]{status_icon}[/{status_color}]",
            details
        )
    
    console.print(table)

def check_clickhouse():
    """Check ClickHouse status"""
    try:
        import requests
        resp = requests.get("http://localhost:8123/ping", timeout=2)
        if resp.text.strip() == "Ok.":
            return True, "Connected"
    except:
        pass
    return False, "Not reachable"

def check_nats():
    """Check NATS status"""
    try:
        import requests
        resp = requests.get("http://localhost:8222/varz", timeout=2)
        if resp.status_code == 200:
            return True, "Connected"
    except:
        pass
    return False, "Not reachable"

def check_redis():
    """Check Redis status"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        r.ping()
        return True, "Connected"
    except:
        pass
    return False, "Not reachable"

def check_datahub():
    """Check DataHub status"""
    # Would check actual DataHub process
    return False, "Not running"

def check_paper_trading():
    """Check Paper Trading status"""
    # Would check actual paper trading process
    return False, "Not running"

@app.command()
def version():
    """Show version information"""
    console.print("[cyan]Sofia V2 Trading Platform[/cyan]")
    console.print("Version: 2.0.0-alpha")
    console.print("Python: 3.11+")
    console.print("Author: Sofia Team")

if __name__ == "__main__":
    app()