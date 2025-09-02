"""
Sofia V2 - MASTER PROFIT SYSTEM
One script to rule them all!
"""

import asyncio
import os
import subprocess
import sys

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


def show_banner():
    """Show awesome banner"""
    console.print(
        """
    [bold cyan]
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║         💰 SOFIA V2 - PROFIT MAXIMIZER 💰              ║
    ║                                                          ║
    ║            Automated Crypto Trading System              ║
    ║                  Version: 2.0 FINAL                     ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    [/bold cyan]
    """
    )


def check_requirements():
    """Check if all requirements are met"""
    console.print("\n[yellow]Checking system requirements...[/yellow]\n")

    checks = {
        "Python 3.9+": sys.version_info >= (3, 9),
        ".env file": os.path.exists(".env") or os.path.exists(".env.example"),
        "Backend folder": os.path.exists("backend"),
        "Models folder": os.path.exists("models"),
        "Virtual environment": os.path.exists(".venv") or os.path.exists("venv"),
    }

    all_good = True
    for item, status in checks.items():
        if status:
            console.print(f"✅ {item}")
        else:
            console.print(f"❌ {item}")
            all_good = False

    return all_good


def show_menu():
    """Show main menu"""
    table = Table(title="🎯 SELECT YOUR PROFIT MODE", show_header=True)
    table.add_column("Option", style="cyan", width=10)
    table.add_column("Mode", style="magenta", width=25)
    table.add_column("Description", style="white")

    table.add_row("1", "Quick Start", "Paper trading with default settings")
    table.add_row("2", "Backtest First", "Test strategies on historical data")
    table.add_row("3", "Train ML Models", "Train AI prediction models")
    table.add_row("4", "Full Auto Mode", "Everything automated with ML")
    table.add_row("5", "DataHub Only", "Start real-time data streaming")
    table.add_row("6", "Custom Setup", "Configure everything manually")
    table.add_row("0", "Exit", "Close the system")

    console.print(table)

    return Prompt.ask(
        "\n[bold yellow]Select option[/bold yellow]", choices=["0", "1", "2", "3", "4", "5", "6"]
    )


async def quick_start():
    """Quick start paper trading"""
    console.print("\n[bold green]🚀 QUICK START MODE[/bold green]")
    console.print("Starting paper trading with default settings...\n")

    # Check if start_trading.py exists
    if os.path.exists("start_trading.py"):
        subprocess.run([sys.executable, "start_trading.py"], check=False)
    else:
        console.print("[red]start_trading.py not found![/red]")
        console.print("Running auto_trader.py instead...")
        subprocess.run([sys.executable, "auto_trader.py"], check=False)


async def run_backtest():
    """Run comprehensive backtest"""
    console.print("\n[bold blue]📊 BACKTEST MODE[/bold blue]")

    days = Prompt.ask("How many days to backtest?", default="30")

    console.print(f"Running backtest for {days} days...\n")

    if os.path.exists("backtest_runner.py"):
        subprocess.run([sys.executable, "backtest_runner.py"], check=False)
    else:
        console.print("[red]backtest_runner.py not found![/red]")


async def train_models():
    """Train ML models"""
    console.print("\n[bold purple]🤖 ML TRAINING MODE[/bold purple]")
    console.print("Training XGBoost and Random Forest models...\n")

    if os.path.exists("train_ml_models.py"):
        subprocess.run([sys.executable, "train_ml_models.py"], check=False)
    else:
        console.print("[red]train_ml_models.py not found![/red]")


async def full_auto():
    """Full automated mode"""
    console.print("\n[bold red]🔥 FULL AUTO MODE - MAXIMUM PROFIT[/bold red]")

    # Step 1: Train models if needed
    if not os.path.exists("models"):
        if Confirm.ask("ML models not found. Train now?"):
            await train_models()

    # Step 2: Run backtest
    if Confirm.ask("Run backtest first?"):
        await run_backtest()

    # Step 3: Start DataHub
    console.print("\n[yellow]Starting DataHub in background...[/yellow]")
    if os.path.exists("backend/scripts/run.ps1"):
        # Start in new window
        subprocess.Popen(
            ["powershell", "-File", "backend/scripts/run.ps1"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        await asyncio.sleep(5)  # Wait for DataHub to start

    # Step 4: Start auto trader
    console.print("\n[green]Starting automated trading system...[/green]")
    if os.path.exists("auto_trader.py"):
        subprocess.run([sys.executable, "auto_trader.py"], check=False)
    else:
        console.print("[red]auto_trader.py not found![/red]")


async def start_datahub():
    """Start DataHub only"""
    console.print("\n[bold cyan]📡 DATAHUB MODE[/bold cyan]")
    console.print("Starting real-time data streaming service...\n")

    os.chdir("backend")
    subprocess.run(["powershell", "-File", "scripts/run.ps1"], check=False)


async def custom_setup():
    """Custom configuration"""
    console.print("\n[bold yellow]⚙️ CUSTOM SETUP MODE[/bold yellow]")

    config = {}

    config["mode"] = Prompt.ask("Trading mode", choices=["paper", "live"], default="paper")
    config["balance"] = Prompt.ask("Initial balance", default="10000")
    config["max_positions"] = Prompt.ask("Max positions", default="5")
    config["stop_loss"] = Prompt.ask("Stop loss %", default="3")
    config["take_profit"] = Prompt.ask("Take profit %", default="8")

    # Save config
    with open(".env", "w") as f:
        f.write(
            f"""
TRADING_MODE={config['mode']}
INITIAL_BALANCE={config['balance']}
MAX_POSITIONS={config['max_positions']}
STOP_LOSS={float(config['stop_loss'])/100}
TAKE_PROFIT={float(config['take_profit'])/100}
"""
        )

    console.print("\n[green]Configuration saved to .env[/green]")

    if Confirm.ask("Start trading now?"):
        await quick_start()


async def main():
    """Main entry point"""
    show_banner()

    # Check requirements
    if not check_requirements():
        console.print("\n[red]⚠️ Some requirements are missing![/red]")
        if not Confirm.ask("Continue anyway?"):
            return

    while True:
        choice = show_menu()

        if choice == "0":
            console.print("\n[yellow]Exiting Sofia V2...[/yellow]")
            break
        elif choice == "1":
            await quick_start()
        elif choice == "2":
            await run_backtest()
        elif choice == "3":
            await train_models()
        elif choice == "4":
            await full_auto()
        elif choice == "5":
            await start_datahub()
        elif choice == "6":
            await custom_setup()

        if not Confirm.ask("\nReturn to main menu?"):
            break

    console.print(
        """
    [bold green]
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║               Thank you for using Sofia V2!             ║
    ║                   Happy Trading! 💰                     ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    [/bold green]
    """
    )


if __name__ == "__main__":
    try:
        # Install rich if not available
        import rich
    except ImportError:
        console.print("Installing required packages...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "rich", "yfinance", "xgboost", "scikit-learn"],
            check=False,
        )

    asyncio.run(main())
