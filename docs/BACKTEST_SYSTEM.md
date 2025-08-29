# Sofia V2 Backtesting System

## Overview

Complete backtesting infrastructure with job queue architecture, parameter optimization (GA & Grid Search), and HTML report generation.

## Architecture

### Components

1. **Database Models** (`src/models/backtest.py`)
   - `BacktestJob`: Job queue for backtest tasks
   - `BacktestResult`: Stores backtest metrics and file paths
   - `OptimizationJob`: Parameter optimization jobs

2. **Strategies** (`src/strategies/`)
   - `SmaCross`: Simple Moving Average crossover
   - `EmaBreakout`: EMA with ATR-based volatility bands
   - `RSIMeanReversion`: RSI-based mean reversion

3. **Backtest Runner** (`src/backtest/runner.py`)
   - Realistic execution with fees (0.1%) and slippage (0.05%)
   - Stop loss and take profit support
   - Position sizing control
   - Comprehensive metrics calculation

4. **Workers** (`workers/`)
   - `backtest_worker.py`: Processes backtest jobs from queue
   - `optimization_worker.py`: Handles GA and Grid optimization

5. **Optimizers** (`src/optimization/`)
   - `ga_optimizer.py`: Genetic Algorithm for large parameter spaces
   - `grid_optimizer.py`: Exhaustive grid search with adaptive refinement

6. **Report Generator** (`src/reports/generator.py`)
   - Beautiful HTML reports with Chart.js visualizations
   - Equity curves, drawdown charts, trade history
   - Performance metrics dashboard

7. **API Endpoints** (`src/api/backtest_endpoints.py`)
   - `POST /backtests/run`: Submit new backtest
   - `GET /backtests/{id}/status`: Check job status
   - `GET /backtests/{id}/result`: Retrieve results
   - `GET /backtests/list`: List all jobs
   - `GET /backtests/strategies`: Available strategies

8. **Frontend** (`sofia_ui/templates/`)
   - `backtests.html`: Job management interface
   - `strategies_list.html`: Strategy showcase

## Quick Start

### 1. Start Workers

```bash
# Terminal 1: Start backtest worker
python workers/backtest_worker.py

# Terminal 2: Start optimization worker (optional)
python workers/optimization_worker.py
```

### 2. Start API Server

```bash
# Terminal 3: Start FastAPI server
uvicorn src.api.main:app --reload --port 8023
```

### 3. Access UI

```bash
# Terminal 4: Start UI server
cd sofia_ui
python server.py
```

Navigate to: http://localhost:8004/backtests

## Usage Examples

### Run a Backtest

```python
import requests

response = requests.post('http://localhost:8023/backtests/run', json={
    'strategy': 'sma_cross',
    'params': {
        'fast': 10,
        'slow': 30,
        'signal_mode': 'cross'
    },
    'symbol': 'BTC/USDT',
    'timeframe': '1h',
    'limit': 1000
})

job_id = response.json()['job_id']
print(f"Backtest job {job_id} submitted")
```

### Check Status

```python
status = requests.get(f'http://localhost:8023/backtests/{job_id}/status')
print(status.json())
```

### Get Results

```python
result = requests.get(f'http://localhost:8023/backtests/{job_id}/result')
metrics = result.json()['metrics']
print(f"Total Return: {metrics['total_return']}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']}")
print(f"Max Drawdown: {metrics['max_drawdown']}%")
```

## Strategy Parameters

### SMA Cross
- `fast`: Fast SMA period (5-50)
- `slow`: Slow SMA period (20-200)
- `signal_mode`: 'cross' or 'position'

### EMA Breakout
- `ema_period`: EMA period (10-100)
- `atr_period`: ATR period (7-28)
- `atr_multiplier`: Band width (1.0-4.0)
- `use_volume`: Volume filter (true/false)

### RSI Mean Reversion
- `rsi_period`: RSI period (7-28)
- `oversold`: Oversold level (20-40)
- `overbought`: Overbought level (60-80)
- `exit_at_mean`: Exit at RSI 50 (true/false)

## Performance Metrics

- **Total Return**: Overall percentage gain/loss
- **CAGR**: Compound Annual Growth Rate
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Maximum peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Average Trade**: Mean return per trade
- **Profit Factor**: Gross profit / Gross loss
- **MAR Ratio**: CAGR / Max Drawdown
- **Exposure Time**: Percentage of time in market

## Optimization

### Genetic Algorithm (GA)
Best for large parameter spaces or when computation time is limited.

```python
# Configure GA optimization
ga_params = {
    'population_size': 50,
    'generations': 30,
    'crossover_rate': 0.8,
    'mutation_rate': 0.1,
    'elite_size': 5
}
```

### Grid Search
Exhaustive search for smaller parameter spaces.

```python
# Configure Grid Search
grid_params = {
    'adaptive': True,  # Use adaptive refinement
    'iterations': 3,
    'initial_grid_size': 10,
    'refinement_factor': 0.5
}
```

## Output Files

All outputs are stored in the `outputs/` directory:

```
outputs/
├── equity/         # Equity curve CSV files
├── trades/         # Trade history CSV files
├── logs/           # Execution logs
├── reports/        # HTML reports
└── optimization/   # Optimization results JSON
```

## Testing

Run the test suite:

```bash
# All backtest tests
pytest tests/test_backtest_runner.py tests/test_strategies.py tests/test_optimization.py -v

# Specific test
pytest tests/test_strategies.py::TestSmaCross -v

# With coverage
pytest tests/ --cov=src.backtest --cov=src.strategies --cov=src.optimization
```

## Production Deployment

1. **Database**: Use PostgreSQL instead of SQLite
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost/backtests"
   ```

2. **Workers**: Use supervisor or systemd for process management

3. **Scaling**: Run multiple workers for parallel processing
   ```bash
   # Start 4 backtest workers
   for i in {1..4}; do
     python workers/backtest_worker.py &
   done
   ```

4. **Monitoring**: Integrate with Prometheus/Grafana for metrics

## Troubleshooting

### Worker not processing jobs
- Check database connection
- Verify job status in database
- Check worker logs in `outputs/logs/`

### Backtest fails with error
- Check strategy parameters are valid
- Verify symbol format (e.g., BTC/USDT)
- Check data availability for timeframe

### Reports not generating
- Ensure Jinja2 is installed
- Check write permissions for `outputs/reports/`
- Verify equity/trades data exists

## Future Enhancements

- [ ] Real-time backtesting with live data
- [ ] Multi-asset portfolio backtesting
- [ ] Walk-forward analysis
- [ ] Monte Carlo simulation
- [ ] Custom indicator support
- [ ] Strategy combination/ensemble
- [ ] Risk management overlays
- [ ] Performance attribution analysis