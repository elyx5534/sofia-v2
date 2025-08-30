import typer
import uvicorn
from sofia_datahub.pipeline import fetch_symbol
from sofia_backtest.engine import sma_cross_backtest
from sofia_registry.store import add_run

app = typer.Typer()

@app.command()
def fetch(symbol: str, period: str = "1y", interval: str = "1d"):
    """Fetch symbol data and display recent prices"""
    import pandas as pd
    df = fetch_symbol(symbol, period=period, interval=interval)
    typer.echo(df.tail().to_string())

@app.command()
def backtest(symbol: str, fast: int = 10, slow: int = 20):
    """Run SMA crossover backtest"""
    df = fetch_symbol(symbol)
    res = sma_cross_backtest(df, fast, slow)
    add_run(symbol, "sma_cross", {"fast": fast, "slow": slow}, res["pnl"], res["sharpe"], res["artifact"])
    typer.echo(res)

@app.command()
def ui(host: str = "0.0.0.0", port: int = 8009):
    """Start UI server"""
    uvicorn.run("sofia_ui.server:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    app()