import pathlib
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ARTIFACTS = pathlib.Path("artifacts")
ARTIFACTS.mkdir(exist_ok=True)


def sma_cross_backtest(df: pd.DataFrame, fast=10, slow=20) -> dict:
    """SMA crossover strategy backtest with PNG chart generation"""
    px = df["Close"].ffill()
    sma_f = px.rolling(fast).mean()
    sma_s = px.rolling(slow).mean()

    # Generate signals: 1 when fast SMA > slow SMA, 0 otherwise
    pos = (sma_f > sma_s).astype(int).shift(1).fillna(0)

    # Calculate strategy returns
    strat = pos * px.pct_change().fillna(0)
    equity = (1 + strat).cumprod()

    # Performance metrics
    pnl = float(equity.iloc[-1] - 1)
    sharpe = float(np.sqrt(252) * strat.mean() / (strat.std() + 1e-9))

    # Generate chart
    fig = plt.figure(figsize=(12, 8))
    ax = plt.gca()

    px.plot(ax=ax, label="Price", color="blue", linewidth=2)
    sma_f.plot(ax=ax, label=f"SMA{fast}", color="red", alpha=0.8)
    sma_s.plot(ax=ax, label=f"SMA{slow}", color="green", alpha=0.8)

    plt.title(f"SMA Crossover Strategy (Fast={fast}, Slow={slow})")
    plt.legend()
    plt.grid(True, alpha=0.3)

    out = ARTIFACTS / f"chart_{int(time.time())}.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return {"pnl": pnl, "sharpe": sharpe, "artifact": str(out)}
