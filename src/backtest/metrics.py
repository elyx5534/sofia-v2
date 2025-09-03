"""Performance metrics calculation for backtest results."""

from typing import Any, Dict, List

import numpy as np


def calculate_metrics(
    equity_curve: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    initial_capital: float = 10000.0,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> Dict[str, float]:
    """
    Calculate performance metrics from backtest results.

    Args:
        equity_curve: List of equity values over time
        trades: List of executed trades
        initial_capital: Starting capital
        risk_free_rate: Annual risk-free rate for Sharpe calculation
        periods_per_year: Trading periods per year (252 for daily)

    Returns:
        Dictionary of performance metrics:
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Maximum percentage decline from peak
            - win_rate: Percentage of winning trades
            - cagr: Compound Annual Growth Rate
            - total_trades: Number of trades executed
            - profit_factor: Ratio of gross profit to gross loss
    """
    if not equity_curve:
        return {
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "cagr": 0.0,
            "total_trades": 0,
            "profit_factor": 0.0,
        }
    equity_values = np.array([e["equity"] for e in equity_curve])
    returns = np.diff(equity_values) / equity_values[:-1]
    if len(returns) > 0 and np.std(returns) > 0:
        excess_returns = returns - risk_free_rate / periods_per_year
        sharpe_ratio = np.sqrt(periods_per_year) * (np.mean(excess_returns) / np.std(returns))
    else:
        sharpe_ratio = 0.0
    cumulative_returns = equity_values / initial_capital - 1
    running_max = np.maximum.accumulate(equity_values)
    drawdown = (equity_values - running_max) / running_max
    max_drawdown = abs(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0.0
    if trades:
        trade_pairs = []
        open_trade = None
        for trade in trades:
            if trade["type"] in ["buy", "short"]:
                open_trade = trade
            elif trade["type"] in ["sell", "cover"] and open_trade:
                if open_trade["type"] == "buy":
                    pnl = (trade["price"] - open_trade["price"]) * trade["quantity"]
                else:
                    pnl = (open_trade["price"] - trade["price"]) * trade["quantity"]
                pnl -= open_trade["commission"] + trade["commission"]
                trade_pairs.append(pnl)
                open_trade = None
        if trade_pairs:
            wins = [p for p in trade_pairs if p > 0]
            losses = [p for p in trade_pairs if p < 0]
            win_rate = len(wins) / len(trade_pairs) * 100 if trade_pairs else 0.0
            gross_profit = sum(wins) if wins else 0
            gross_loss = abs(sum(losses)) if losses else 0
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else float("inf")
                if gross_profit > 0
                else 0.0
            )
        else:
            win_rate = 0.0
            profit_factor = 0.0
        total_trades = len([t for t in trades if t["type"] in ["buy", "short"]])
    else:
        win_rate = 0.0
        profit_factor = 0.0
        total_trades = 0
    if len(equity_values) > 1:
        final_value = equity_values[-1]
        num_periods = len(equity_values) - 1
        years = num_periods / periods_per_year
        if years > 0 and final_value > 0 and (initial_capital > 0):
            cagr = ((final_value / initial_capital) ** (1 / years) - 1) * 100
        else:
            cagr = 0.0
    else:
        cagr = 0.0
    return {
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 2),
        "win_rate": round(win_rate, 2),
        "cagr": round(cagr, 2),
        "total_trades": total_trades,
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
    }
