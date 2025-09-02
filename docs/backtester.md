# Backtester Documentation

## Overview
The Sofia V2 backtesting engine provides comprehensive historical strategy testing with support for multiple strategies, risk management, and performance analytics.

## Features
- **Strategy Registry**: Pluggable strategy system
- **Multi-timeframe**: Support for 1m to 1M candles
- **Risk Management**: Position sizing, stop-loss, take-profit
- **Performance Metrics**: Sharpe, Sortino, max drawdown, win rate
- **Walk-Forward Optimization**: Out-of-sample testing
- **Genetic Algorithm**: Parameter optimization

## Usage

### Basic Backtest
```python
from src.backtest.engine import BacktestEngine
from src.backtest.strategies.sma import SMAStrategy

engine = BacktestEngine()
result = engine.run(
    strategy=SMAStrategy(fast=20, slow=50),
    symbol="BTC/USDT",
    timeframe="1h",
    start="2024-01-01",
    end="2024-01-31"
)
print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe:.2f}")
```

### Strategy Development
```python
from src.backtest.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, threshold=0.02):
        self.threshold = threshold

    def on_bar(self, bar):
        # bar = [timestamp, open, high, low, close, volume]
        if self.position == 0:
            if bar[4] > bar[1] * (1 + self.threshold):  # close > open * threshold
                self.buy(size=1.0)
        elif bar[4] < self.entry_price * 0.98:  # 2% stop loss
            self.sell()
```

### Walk-Forward Optimization
```python
from src.optimization.runner import OptimizationRunner

runner = OptimizationRunner()
best_params = runner.walk_forward(
    strategy_class=SMAStrategy,
    param_ranges={"fast": (10, 50), "slow": (50, 200)},
    symbol="ETH/USDT",
    in_sample_months=3,
    out_sample_months=1
)
```

## Strategies

| Strategy | Description | Parameters | Best For |
|----------|-------------|------------|----------|
| SMA | Simple Moving Average Crossover | fast, slow | Trending markets |
| RSI | Relative Strength Index | period, oversold, overbought | Range-bound |
| MACD | Moving Average Convergence | fast, slow, signal | Momentum |
| Bollinger | Bollinger Bands Reversion | period, std_dev | Volatility |
| MultiIndicator | Combined signals | rsi_period, bb_period | All market conditions |

## Performance Metrics

- **Total Return**: Overall profit/loss percentage
- **Sharpe Ratio**: Risk-adjusted return (target > 1.0)
- **Sortino Ratio**: Downside risk-adjusted return
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss (target > 1.5)
- **Calmar Ratio**: Annual return / max drawdown

## Quick Verify

```powershell
# Run quick backtest
python -c "from src.backtest.engine import BacktestEngine; e = BacktestEngine(); r = e.run_quick('BTC/USDT'); print(f'Return: {r:.2%}')"

# List available strategies
python -c "from src.backtest.strategies.registry import StrategyRegistry; print(StrategyRegistry().list_strategies())"

# Test strategy registration
python -c "from src.backtest.strategies.registry import StrategyRegistry; r = StrategyRegistry(); r.register('test', lambda: None); print('OK' if 'test' in r.strategies else 'FAIL')"
```
