# Public API Contract v1

## Overview

The Public API Contract v1 provides stable, versioned interfaces for core services in the Sofia v2 trading platform. These functions guarantee backward compatibility and consistent behavior across updates.

## Contract Principles

1. **Stability**: Function signatures will not change within v1
2. **Predictability**: Return formats are standardized
3. **Simplicity**: Single dict input, single dict output
4. **Compatibility**: Tests written against v1 will continue to work

## Service Contracts

### 1. Backtester Service (`src.services.backtester`)

#### `run_backtest(spec: dict) -> dict`
Run a single backtest with specified parameters.

**Input Schema:**
```python
{
    "symbol": str,           # e.g., "BTC/USDT"
    "timeframe": str,        # e.g., "1h", "1d"
    "start_date": str,       # YYYY-MM-DD format
    "end_date": str,         # YYYY-MM-DD format
    "strategy": str,         # Strategy name
    "params": dict,          # Strategy parameters
    "config": dict           # Optional backtest config
}
```

**Output Schema:**
```python
{
    "run_id": str,
    "equity_curve": [[timestamp, value], ...],
    "drawdown": [[timestamp, value], ...],
    "trades": [trade_dict, ...],
    "stats": {
        "total_return": float,
        "sharpe_ratio": float,
        "max_drawdown": float,
        "win_rate": float,
        "num_trades": int
    }
}
```

#### `run_grid(spec: dict) -> dict`
Run grid search optimization.

**Input Schema:**
```python
{
    "symbol": str,
    "timeframe": str,
    "start_date": str,
    "end_date": str,
    "strategy": str,
    "param_grid": {
        "param_name": [value1, value2, ...],
        ...
    }
}
```

**Output Schema:**
```python
{
    "best_params": dict,
    "best_sharpe": float,
    "all_results": [result_dict, ...],
    "optimization_stats": dict
}
```

#### `run_ga(spec: dict) -> dict`
Run genetic algorithm optimization.

**Input Schema:**
```python
{
    "symbol": str,
    "timeframe": str,
    "start_date": str,
    "end_date": str,
    "strategy": str,
    "param_ranges": {
        "param_name": [min, max],
        ...
    },
    "population_size": int,
    "generations": int,
    "elite_size": int
}
```

**Output Schema:**
```python
{
    "best_params": dict,
    "best_fitness": float,
    "evolution_history": [...],
    "final_population": [...]
}
```

#### `run_wfo(spec: dict) -> dict`
Run walk-forward optimization.

**Input Schema:**
```python
{
    "symbol": str,
    "timeframe": str,
    "start_date": str,
    "end_date": str,
    "strategy": str,
    "param_grid": dict,
    "n_splits": int,
    "train_ratio": float
}
```

**Output Schema:**
```python
{
    "avg_oos_sharpe": float,
    "oos_results": [...],
    "best_params_per_split": [...],
    "robustness_score": float
}
```

### 2. DataHub Service (`src.services.datahub`)

#### `get_ohlcv(asset: str, tf: str, start: str, end: str) -> list`
Get OHLCV data with automatic fallback chain.

**Input:**
- `asset`: Trading symbol (e.g., "BTC/USDT")
- `tf`: Timeframe (e.g., "1h", "1d")
- `start`: Start date (YYYY-MM-DD)
- `end`: End date (YYYY-MM-DD)

**Output:**
```python
[
    [timestamp, open, high, low, close, volume],
    ...
]
```

#### `get_ticker(asset: str) -> dict`
Get latest price information.

**Input:**
- `asset`: Trading symbol

**Output:**
```python
{
    "symbol": str,
    "price": float,
    "timestamp": int,
    "volume": float
}
```

### 3. Paper Engine Service (`src.services.paper_engine`)

#### `start(session_type: str, symbol: str, params: dict = None) -> dict`
Start a paper trading session.

**Input:**
- `session_type`: Strategy type ("grid", "mean_revert", "simple")
- `symbol`: Trading symbol
- `params`: Optional strategy parameters

**Output:**
```python
{
    "status": "started",
    "session": str,
    "symbol": str
}
```

#### `stop() -> dict`
Stop the current paper trading session.

**Output:**
```python
{
    "status": "stopped",
    "final_pnl": float,
    "num_trades": int
}
```

#### `status() -> dict`
Get current session status.

**Output:**
```python
{
    "running": bool,
    "session": str,
    "symbol": str,
    "pnl": float,
    "position": float,
    "cash": float,
    "num_trades": int,
    "current_value": float
}
```

#### `reset_day() -> dict`
Reset for a new trading day.

**Output:**
```python
{
    "status": "reset",
    "cash": float
}
```

### 4. Arbitrage Radar Service (`src.services.arb_tl_radar`)

#### `start(mode: str = "tl", pairs: list = None, threshold_bps: int = 50) -> dict`
Start arbitrage monitoring.

**Input:**
- `mode`: Monitoring mode ("tl" for Turkish)
- `pairs`: List of trading pairs
- `threshold_bps`: Threshold in basis points

**Output:**
```python
{
    "status": "started",
    "mode": str,
    "pairs": list,
    "threshold_bps": int
}
```

#### `stop() -> dict`
Stop arbitrage monitoring.

**Output:**
```python
{
    "status": "stopped",
    "total_pnl_tl": float,
    "num_opportunities": int,
    "num_trades": int
}
```

#### `snap() -> dict`
Get current radar snapshot.

**Output:**
```python
{
    "running": bool,
    "mode": str,
    "pairs": list,
    "threshold_bps": int,
    "opportunities": [...],
    "paper_trades": [...],
    "total_pnl_tl": float,
    "num_opportunities": int,
    "num_trades": int
}
```

## Usage Examples

### Backtesting
```python
import src.services.backtester as backtester_api

# Simple backtest
result = backtester_api.run_backtest({
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "strategy": "sma_cross",
    "params": {"fast_period": 10, "slow_period": 20}
})
print(f"Sharpe Ratio: {result['stats']['sharpe_ratio']}")

# Grid search
result = backtester_api.run_grid({
    "symbol": "ETH/USDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "strategy": "rsi",
    "param_grid": {
        "rsi_period": [10, 14, 20],
        "overbought": [70, 75, 80],
        "oversold": [20, 25, 30]
    }
})
print(f"Best params: {result['best_params']}")
```

### Data Access
```python
import src.services.datahub as datahub_api

# Get historical data
data = datahub_api.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-07")
print(f"Got {len(data)} candles")

# Get current price
ticker = datahub_api.get_ticker("BTC/USDT")
print(f"Current price: ${ticker['price']}")
```

### Paper Trading
```python
import src.services.paper_engine as paper_api

# Start grid trading
paper_api.start("grid", "BTC/USDT", {"grid_spacing": 0.01, "grid_levels": 5})

# Check status
status = paper_api.status()
print(f"P&L: {status['pnl']}")

# Stop and get results
result = paper_api.stop()
print(f"Final P&L: {result['final_pnl']}")
```

### Arbitrage Monitoring
```python
import src.services.arb_tl_radar as arb_api

# Start monitoring
arb_api.start("tl", ["BTC/USDT", "ETH/USDT"], 100)

# Get snapshot
snap = arb_api.snap()
print(f"Opportunities found: {snap['num_opportunities']}")

# Stop monitoring
result = arb_api.stop()
print(f"Total profit: {result['total_pnl_tl']} TL")
```

## Migration Guide

### From Direct Class Usage to Public API

**Before:**
```python
from src.services.backtester import backtester
result = backtester.run_backtest(
    symbol="BTC/USDT",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-01-31",
    strategy="sma_cross",
    params={"fast": 10, "slow": 20}
)
```

**After:**
```python
import src.services.backtester as backtester_api
result = backtester_api.run_backtest({
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "strategy": "sma_cross",
    "params": {"fast": 10, "slow": 20}
})
```

## Versioning Policy

- **v1.x**: Current stable version, no breaking changes
- **v2.x**: Future version with potential breaking changes
- Functions marked with "Public API Contract v1" in docstrings are guaranteed stable
- Internal implementation may change but interfaces remain constant

## Testing Against the Contract

Tests should import and use only the public API functions:

```python
import pytest
import src.services.backtester as backtester_api

def test_backtest_contract():
    """Test that conforms to Public API Contract v1"""
    spec = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-01-07",
        "strategy": "sma_cross",
        "params": {"fast_period": 10, "slow_period": 20}
    }

    result = backtester_api.run_backtest(spec)

    # Verify contract output
    assert "run_id" in result
    assert "equity_curve" in result
    assert "stats" in result
    assert isinstance(result["stats"]["sharpe_ratio"], (int, float))
```

## Support

For questions about the Public API Contract:
- Check this documentation
- Review the docstrings in the service modules
- See tests in `tests/unit/` for usage examples

## Changelog

### v1.0.0 (2025-09-02)
- Initial Public API Contract v1 release
- Stable interfaces for backtester, datahub, paper_engine, arb_tl_radar
- Standardized input/output schemas
- Backward compatibility guarantee
