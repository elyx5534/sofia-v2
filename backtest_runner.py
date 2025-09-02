"""
Sofia V2 - Comprehensive Backtest Runner
Test all strategies with real historical data
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

import ccxt
import numpy as np
import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.progress import track
from rich.table import Table

# Import our strategies
from src.strategies.grid_trading import GridConfig, GridTradingStrategy
from src.strategy_engine.strategies import (
    BollingerBandsStrategy,
    MACDStrategy,
    MultiIndicatorStrategy,
    RSIStrategy,
    SMAStrategy,
)

console = Console()


class BacktestEngine:
    """
    High-performance backtesting engine for all strategies
    """

    def __init__(self):
        self.results = {}
        self.data_cache = {}

    async def fetch_historical_data(
        self, symbol: str, days: int = 30, interval: str = "1h"
    ) -> pd.DataFrame:
        """Fetch historical data from multiple sources"""

        cache_key = f"{symbol}_{days}_{interval}"
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]

        console.print(f"[yellow]Fetching {symbol} data ({days} days)...[/yellow]")

        try:
            # Try yfinance first
            ticker = symbol.replace("USDT", "-USD")
            df = yf.download(
                ticker,
                start=datetime.now() - timedelta(days=days),
                interval=interval,
                progress=False,
            )

            if df.empty:
                # Fallback to CCXT
                exchange = ccxt.binance()
                since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
                ohlcv = exchange.fetch_ohlcv(symbol, interval, since)
                df = pd.DataFrame(
                    ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)

            # Add technical indicators
            df = self.add_indicators(df)

            self.data_cache[cache_key] = df
            return df

        except Exception as e:
            console.print(f"[red]Error fetching data: {e}[/red]")
            return pd.DataFrame()

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators"""

        # SMA
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()

        # EMA
        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + (std * 2)
        df["bb_lower"] = df["bb_middle"] - (std * 2)

        # Volume indicators
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]

        # Price changes
        df["price_change"] = df["close"].pct_change()
        df["high_low_ratio"] = (df["high"] - df["low"]) / df["close"]

        return df

    async def backtest_strategy(
        self, strategy_name: str, strategy: Any, data: pd.DataFrame, initial_balance: float = 10000
    ) -> Dict:
        """Run backtest for a single strategy"""

        console.print(f"\n[cyan]Testing {strategy_name}...[/cyan]")

        balance = initial_balance
        position = 0
        trades = []
        equity_curve = [initial_balance]

        for i in track(range(20, len(data)), description=f"Backtesting {strategy_name}"):
            row = data.iloc[i]
            prev_rows = data.iloc[max(0, i - 100) : i]  # Last 100 candles for indicators

            # Prepare market data
            market_data = {
                "close": row["close"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "volume": row["volume"],
                "sma_20": row.get("sma_20", 0),
                "sma_50": row.get("sma_50", 0),
                "rsi": row.get("rsi", 50),
                "macd": row.get("macd", 0),
                "macd_signal": row.get("macd_signal", 0),
                "bb_upper": row.get("bb_upper", 0),
                "bb_lower": row.get("bb_lower", 0),
                "price_history": prev_rows["close"].tolist(),
            }

            # Get signal from strategy
            signal = strategy.analyze(market_data)

            # Execute trade
            if signal["action"] == "buy" and position == 0:
                position = balance / row["close"]
                balance = 0
                trades.append(
                    {
                        "type": "buy",
                        "price": row["close"],
                        "time": data.index[i],
                        "balance": balance + position * row["close"],
                    }
                )

            elif signal["action"] == "sell" and position > 0:
                balance = position * row["close"] * 0.999  # 0.1% fee
                trades.append(
                    {
                        "type": "sell",
                        "price": row["close"],
                        "time": data.index[i],
                        "balance": balance,
                        "pnl": balance - initial_balance,
                    }
                )
                position = 0

            # Track equity
            current_equity = balance + position * row["close"]
            equity_curve.append(current_equity)

        # Calculate metrics
        final_balance = balance + position * data.iloc[-1]["close"]
        total_return = (final_balance - initial_balance) / initial_balance * 100

        # Win rate
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

        # Max drawdown
        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max * 100
        max_drawdown = abs(drawdown.min())

        # Sharpe ratio (simplified)
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        return {
            "strategy": strategy_name,
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "total_return": total_return,
            "num_trades": len(trades),
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "trades": trades,
            "equity_curve": equity_curve,
        }

    async def run_all_backtests(self, symbols: List[str], days: int = 30) -> None:
        """Run backtests for all strategies on all symbols"""

        console.print("\n[bold green]Starting Comprehensive Backtest[/bold green]")
        console.print(f"Symbols: {symbols}")
        console.print(f"Period: {days} days")
        console.print("Initial Balance: $10,000\n")

        all_results = []

        for symbol in symbols:
            # Fetch data
            data = await self.fetch_historical_data(symbol, days)
            if data.empty:
                continue

            # Initialize strategies
            strategies = {
                "Grid Trading": GridTradingStrategy(
                    GridConfig(
                        symbol=symbol, grid_levels=10, grid_spacing=0.005, quantity_per_grid=100
                    )
                ),
                "SMA Crossover": SMAStrategy(),
                "RSI Reversal": RSIStrategy(),
                "MACD Momentum": MACDStrategy(),
                "Bollinger Bands": BollingerBandsStrategy(),
                "Multi-Indicator": MultiIndicatorStrategy(),
            }

            # Test each strategy
            for name, strategy in strategies.items():
                try:
                    result = await self.backtest_strategy(name, strategy, data)
                    result["symbol"] = symbol
                    all_results.append(result)
                except Exception as e:
                    console.print(f"[red]Error testing {name}: {e}[/red]")

        # Display results
        self.display_results(all_results)

        # Save results
        self.save_results(all_results)

        # Find best strategy
        self.find_best_strategy(all_results)

    def display_results(self, results: List[Dict]) -> None:
        """Display backtest results in a nice table"""

        table = Table(title="Backtest Results", show_header=True)
        table.add_column("Symbol", style="cyan")
        table.add_column("Strategy", style="magenta")
        table.add_column("Return %", style="green")
        table.add_column("Win Rate %", style="yellow")
        table.add_column("Max DD %", style="red")
        table.add_column("Sharpe", style="blue")
        table.add_column("Trades", style="white")

        for r in results:
            color = "green" if r["total_return"] > 0 else "red"
            table.add_row(
                r["symbol"],
                r["strategy"],
                f"[{color}]{r['total_return']:.2f}%[/{color}]",
                f"{r['win_rate']:.1f}%",
                f"{r['max_drawdown']:.1f}%",
                f"{r['sharpe_ratio']:.2f}",
                str(r["num_trades"]),
            )

        console.print(table)

    def save_results(self, results: List[Dict]) -> None:
        """Save results to JSON file"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_results_{timestamp}.json"

        # Remove non-serializable data
        clean_results = []
        for r in results:
            clean_r = r.copy()
            clean_r["trades"] = [
                {k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in t.items()}
                for t in r["trades"]
            ]
            clean_r["equity_curve"] = []  # Too large
            clean_results.append(clean_r)

        with open(filename, "w") as f:
            json.dump(clean_results, f, indent=2)

        console.print(f"\n[green]Results saved to {filename}[/green]")

    def find_best_strategy(self, results: List[Dict]) -> None:
        """Find and display the best strategy"""

        if not results:
            return

        # Sort by return
        best_return = max(results, key=lambda x: x["total_return"])
        best_sharpe = max(results, key=lambda x: x["sharpe_ratio"])
        best_winrate = max(results, key=lambda x: x["win_rate"])

        console.print("\n[bold yellow]🏆 BEST STRATEGIES[/bold yellow]")
        console.print(
            f"Highest Return: {best_return['strategy']} on {best_return['symbol']} = {best_return['total_return']:.2f}%"
        )
        console.print(
            f"Best Sharpe: {best_sharpe['strategy']} on {best_sharpe['symbol']} = {best_sharpe['sharpe_ratio']:.2f}"
        )
        console.print(
            f"Best Win Rate: {best_winrate['strategy']} on {best_winrate['symbol']} = {best_winrate['win_rate']:.1f}%"
        )

        # Overall recommendation
        console.print("\n[bold green]💰 RECOMMENDATION:[/bold green]")
        if best_return["total_return"] > 10 and best_return["max_drawdown"] < 15:
            console.print(f"✅ Use {best_return['strategy']} for {best_return['symbol']}")
            console.print(f"   Expected monthly return: {best_return['total_return']:.1f}%")
            console.print(
                f"   Risk level: {'Low' if best_return['max_drawdown'] < 10 else 'Medium'}"
            )
        else:
            console.print("⚠️  More optimization needed. Consider:")
            console.print("   - Adjusting strategy parameters")
            console.print("   - Combining multiple strategies")
            console.print("   - Adding more risk management")


async def main():
    """Main backtest runner"""

    console.print(
        """
    ╔══════════════════════════════════════════════╗
    ║     Sofia V2 - Backtest & Optimization      ║
    ║          Finding Profitable Strategies       ║
    ╚══════════════════════════════════════════════╝
    """,
        style="bold blue",
    )

    # Top symbols to test
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

    # Run backtests
    engine = BacktestEngine()
    await engine.run_all_backtests(symbols, days=30)

    console.print("\n[bold green]Backtest complete! Check results above.[/bold green]")
    console.print("[yellow]Next step: Use best strategies in paper trading[/yellow]")


if __name__ == "__main__":
    asyncio.run(main())
