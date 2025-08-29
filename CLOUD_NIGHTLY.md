# Sofia V2 - Cloud Overnight Optimizer

## Overview

This system provides automated overnight optimization and paper trading for Sofia V2, designed to run continuously in cloud infrastructure to find the highest risk-adjusted profitable strategies.

## Architecture

### Components

1. **Strategy Zoo** (`src/strategies/`)
   - Trend: Donchian Breakout, SuperTrend
   - Mean Reversion: Bollinger Revert, RSI Mean Reversion  
   - Volatility: ATR-based exits and sizing
   - Pairs Trading: Cointegration-based pairs strategies

2. **Optimization Engine** (`src/optimization/`)
   - Bayesian optimization with Optuna
   - Genetic Algorithm with DEAP
   - Walk-Forward validation with Purged K-Fold CV
   - Multi-objective scoring (MAR, Sharpe, Profit Factor)

3. **Parallel Paper Runners** (`src/paper/parallel_runner.py`)
   - Per-strategy ledgers and P&L tracking
   - K-factor ramping (0.25 → 0.5 → 1.0 over 3 days)
   - Auto-gates with downgrade/kill-switch
   - Hourly replay divergence monitoring

4. **AI News Sentiment** (`src/ai/`)
   - FinBERT/VADER sentiment analysis
   - Strategy overlay with K-factor adjustments
   - Anomaly detection and event classification

5. **Observability** (`scripts/generate_morning_report.py`)
   - Comprehensive morning reports
   - Prometheus metrics integration
   - System health monitoring

## Cloud Deployment

### Docker Compose

```bash
cd infra/cloud
docker-compose -f docker-compose.cloud.yml up -d
```

**Services:**
- `api`: Main API service (port 8023)
- `ui`: Web interface (port 4173)  
- `optimizer`: Strategy optimization engine
- `paper_runner`: Parallel paper trading runners
- `rayhead`: Distributed computing for optimization
- `prometheus`: Metrics collection
- `scheduler`: Cron jobs for nightly automation

### Nightly Schedule

- **21:00 UTC**: Start optimization (GA + Bayesian)
- **22:30 UTC**: Start paper trading with optimized parameters
- **07:00 UTC**: Generate morning summary report

## Usage

### Manual Optimization

```bash
# Bayesian optimization (recommended)
python scripts/optimize.py --method bayesian --trials 100

# Genetic Algorithm
python scripts/optimize.py --method genetic

# Both methods (takes best from each)
python scripts/optimize.py --method both --trials 50

# Specific symbols/strategies
python scripts/optimize.py --symbols BTC/USDT ETH/USDT --strategies supertrend bollinger_revert
```

### Paper Trading Control

```bash
# Start paper trading
curl -X POST http://localhost:8023/api/paper/settings/trading_mode -H "Content-Type: application/json" -d '{"mode":"paper"}'

# Get status
curl http://localhost:8023/api/paper/state

# Run replay simulation
curl -X POST http://localhost:8023/api/paper/replay -H "Content-Type: application/json" -d '{"hours":24}'

# Emergency stop
curl -X POST http://localhost:8023/api/paper/kill-switch
```

### Morning Report

```bash
python scripts/generate_morning_report.py
```

Report saved to: `reports/nightly/summary_YYYYMMDD/morning_summary.html`

## Configuration

### Environment Variables

```env
# Paper Trading
MODE=paper
PAPER_INITIAL_BALANCE=10000
K_FACTOR=0.25
MAX_DAILY_LOSS=200
MAX_POSITION_USD=1000

# AI Features
AI_NEWS_ENABLED=true
USE_FINBERT=true
ML_PREDICTOR_ENABLED=false

# Optimization
RAY_ADDRESS=ray://rayhead:10001
OPTUNA_DB=sqlite:///data/optuna.db

# Ports
API_PORT=8023
UI_PORT=4173
```

## Key Features

### Risk Management
- K-factor ramping with auto-gates
- Daily loss limits and position sizing
- Real-time risk violation monitoring
- Kill-switch activation on breach

### Signal Fusion  
- Weighted voting across strategies
- Confidence-based position sizing
- News sentiment overlay
- ML predictor integration (optional)

### Performance Analysis
- Out-of-sample metrics (Sharpe, MAR, MaxDD)
- Walk-forward validation
- Divergence analysis (expected vs actual)
- Strategy attribution and breakdown

## Monitoring

### Key Metrics
- Paper trading P&L and win rate
- Strategy performance by symbol
- News sentiment scores and anomalies
- System resource utilization

### Alerts
- Risk limit violations
- Strategy gate triggers  
- Kill-switch activation
- Data feed failures

### Reports

**Daily:**
- Morning summary with executive overview
- Strategy performance breakdown
- News sentiment analysis
- Risk violation alerts

**Real-time:**
- Dashboard with live P&L
- Position monitoring
- News impact analysis

## Expected Results

### Success Criteria
- Top-3 parameter sets with OOS MAR > 0.5, Sharpe > 1.2, MaxDD < 10%
- 24h paper trading: P&L ≥ 0, MaxDD < target, error < 1%, slippage < 50bps  
- 72h completion: 2/3 strategies positive P&L

### Profitability Analysis
The system answers "Is it profitable?" through:
1. Optimization finds best parameter combinations
2. Paper trading validates with live market data
3. Hourly replay compares expected vs actual performance
4. Morning report provides comprehensive analysis

## Troubleshooting

### Common Issues

**Optimization fails:**
- Check Ray cluster connectivity
- Verify Optuna database access
- Ensure sufficient memory/CPU resources

**Paper trading not starting:**
- Check risk engine initialization
- Verify data feed connectivity
- Review K-factor and balance settings

**News sentiment unavailable:**
- Check AI_NEWS_ENABLED flag
- Verify internet connectivity for RSS feeds
- Review FinBERT model loading

### Logs

View logs with:
```bash
docker-compose -f docker-compose.cloud.yml logs [service-name]
```

## Development

### Adding New Strategies

1. Inherit from `BaseStrategy` in `src/strategies/base.py`
2. Implement required methods: `_calculate_strategy_indicators()`, `get_signal()`
3. Add to `strategy_configs` in optimization engine
4. Update signal hub imports

### Testing

```bash
# Unit tests
python -m pytest tests/test_paper_trading.py -v

# E2E tests  
python -m pytest tests/e2e/test_paper_trading_e2e.py --headed

# Chaos tests
python -m pytest tests/chaos/test_paper_chaos.py -v
```

## License

This is proprietary trading software for Sofia V2. Unauthorized use is prohibited.