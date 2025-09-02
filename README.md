# Sofia V2

**Quantitative Trading Platform**

## Quick Start

```powershell
# Setup
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# Run API
uvicorn src.api.main:app --reload

# Access
# Dashboard: http://127.0.0.1:8000/dashboard
# Studio: http://127.0.0.1:8000/backtest-studio
# API Docs: http://127.0.0.1:8000/docs
```

## Documentation

- [Architecture](docs/architecture.md) - System design and components
- [DataHub](docs/datahub.md) - Market data management
- [Backtester](docs/backtester.md) - Strategy testing and optimization
- [Execution](docs/execution.md) - Live and paper trading
- [Arbitrage](docs/arbitrage.md) - Turkish market arbitrage
- [Operations](docs/operations.md) - Deployment and monitoring

## Development

```bash
# Setup virtual environment (first time only)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/smoke -v

# Start API server
uvicorn src.api.main:app --reload --port 8000
```

## 📍 API Endpoints

### Core Endpoints
- `http://localhost:8000/docs` - Interactive API documentation (Swagger UI)
- `http://localhost:8000/health` - Detailed health with system metrics
- `http://localhost:8000/metrics` - Prometheus metrics endpoint
- `http://localhost:8000/api/health` - Simple health check

### Trading Dashboards
- `http://localhost:8000/dashboard` - **Main Trading Dashboard** with P&L, charts, watchlists
- `http://localhost:8000/backtest-studio` - **Backtest Studio** for strategy testing

### Paper Trading
- `POST /api/paper/start` - Start paper trading session
- `POST /api/paper/stop` - Stop paper trading
- `GET /api/paper/status` - Get current status and P&L
- `GET /api/paper/trades` - List all trades

### Live Trading
- `POST /api/live/mode` - Switch between paper/live mode
- `POST /api/live/order` - Place an order
- `GET /api/live/balance` - Get account balance
- `GET /api/live/positions` - Get open positions
- `POST /api/live/risk/config` - Configure risk limits

### Arbitrage Monitoring
- `POST /api/arb/start` - Start arbitrage radar
- `GET /api/arb/opportunities` - Get current opportunities
- `POST /api/arb/stop` - Stop monitoring

## 🌟 Key Features

### 📊 Portfolio Backtesting
- **Walk-Forward Optimization** - Out-of-sample validation
- **Genetic Algorithm** - Automatic parameter optimization
- **Grid Search** - Exhaustive parameter exploration
- **Transaction Costs** - Commission, slippage, funding fees
- **Multiple Strategies** - SMA, RSI, Breakout, Pairs trading

### 🚀 Live Trading
- **Paper/Live Mode** - Seamless switching with safety checks
- **Risk Management** - Position limits, daily loss limits, kill-switch
- **Order Routing** - Smart routing to multiple exchanges
- **State Persistence** - Resume trading after restarts

### 🎯 Turkish Arbitrage
- **Multi-Exchange** - Monitor BtcTurk, Paribu, Binance
- **Real-time Detection** - Sub-second opportunity scanning
- **Fee Calculation** - Account for exchange fees and spreads
- **Threshold Alerts** - Configurable profit thresholds

### 📈 Production Monitoring
- **Prometheus Metrics** - Export metrics in Prometheus format
- **Health Checks** - Comprehensive health endpoints
- **Grafana Dashboards** - Pre-configured visualization
- **Alert System** - Slack/email notifications

### 🏆 Strategy Leaderboard
- **Nightly Optimization** - Automatic parameter tuning
- **Performance Ranking** - Sort by Sharpe, returns, drawdown
- **HTML Reports** - Beautiful leaderboard reports
- **Parameter History** - Track optimal parameters over time

## 🧪 Testing

### Run All Tests
```bash
# Full test suite with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Quick smoke tests
pytest tests/smoke -v

# Specific module tests
pytest tests/test_backtester.py -v
pytest tests/test_execution.py -v
pytest tests/test_metrics_health.py -v
```

### Test Coverage Goals
- Overall: ≥70%
- New modules: ≥80%
- Critical paths: 100%

## 🚢 Production Deployment

### Using Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Scale workers
docker-compose up -d --scale worker=3

# Backup database
docker-compose exec postgres pg_dump -U sofia sofia > backup.sql
```

### Monitoring Setup
```bash
# Access monitoring dashboards
open http://localhost:3000     # Grafana
open http://localhost:9090     # Prometheus
open http://localhost:15672    # RabbitMQ Management
```

### Nightly Leaderboard
```powershell
# Run strategy optimization and generate leaderboard
.\scripts\nightly_leaderboard.ps1

# Schedule for 2 AM daily (Windows Task Scheduler)
schtasks /create /tn "Sofia Leaderboard" /tr "powershell.exe -File D:\BORSA2\sofia-v2\scripts\nightly_leaderboard.ps1" /sc daily /st 02:00
```

## 🔒 Security & Best Practices

### Environment Variables
```bash
# Required for production
DATABASE_URL=postgresql://user:pass@localhost/sofia
REDIS_URL=redis://localhost:6379
API_KEY=your_exchange_api_key
API_SECRET=your_exchange_api_secret

# Optional monitoring
SENTRY_DSN=your_sentry_dsn
SLACK_WEBHOOK=your_slack_webhook
GRAFANA_PASSWORD=secure_password
```

### Security Checklist
- ✅ Never commit `.env` files or secrets
- ✅ Use read-only API keys for paper trading
- ✅ Enable 2FA on exchange accounts
- ✅ Set up IP whitelisting on exchanges
- ✅ Rotate API keys monthly
- ✅ Monitor for abnormal trading patterns
- ✅ Use kill-switch for risk management

## 📂 Project Structure

```
sofia-v2/
├── src/
│   ├── api/            # FastAPI application and routes
│   │   ├── main.py     # Main API with health/metrics
│   │   └── routes/     # API route modules
│   ├── services/       # Core business logic
│   │   ├── backtester.py      # Portfolio backtesting engine
│   │   ├── execution.py       # Order routing and risk management
│   │   ├── paper_engine.py    # Paper trading simulator
│   │   └── arb_tl_radar.py   # Turkish arbitrage monitor
│   ├── ui/             # Web UI templates
│   │   └── templates/  # HTML dashboards
│   └── utils/          # Utility functions
├── tests/              # Test suite
│   ├── smoke/          # Quick validation tests
│   └── test_*.py       # Module tests
├── scripts/            # Automation scripts
│   ├── prod_run.ps1    # Production launcher
│   └── nightly_leaderboard.ps1  # Strategy optimizer
├── docker/             # Container configuration
│   └── Dockerfile      # Application image
├── monitoring/         # Observability configs
│   ├── prometheus.yml  # Metrics collection
│   └── grafana/        # Dashboard definitions
└── reports/            # Generated reports

## 🛠️ Development Guide

### Adding New Strategies

```python
# src/services/backtester.py
class MyStrategy(Strategy):
    def __init__(self, param1: float = 10):
        self.param1 = param1

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        # Your logic here
        signals = pd.Series(0, index=data.index)
        signals[condition] = 1  # Buy
        signals[other_condition] = -1  # Sell
        return signals
```

### Creating API Endpoints

```python
# src/api/routes/myroute.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/custom")

@router.get("/endpoint")
async def my_endpoint():
    return {"message": "Hello"}

# Register in src/api/main.py
from src.api.routes.myroute import router as custom_router
app.include_router(custom_router)
```

### Writing Tests

```python
# tests/test_mymodule.py
import pytest

def test_my_function():
    result = my_function(input_data)
    assert result.expected_field == expected_value
```

## 📚 Documentation

### Example: Running a Backtest

```python
from src.services.backtester import Backtester, BacktestConfig
from src.services.backtester import SMAStrategy

# Configure backtest
config = BacktestConfig(
    symbol="BTC/USDT",
    start_date="2024-01-01",
    end_date="2024-03-01",
    initial_capital=10000,
    commission_bps=10,  # 0.10%
    slippage_bps=5
)

# Run backtest
backtester = Backtester(config)
results = backtester.run(SMAStrategy(fast=20, slow=50))

print(f"Total Return: {results['total_return']:.2%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.2%}")
```

### Example: Starting Paper Trading

```python
import requests

# Start paper trading
response = requests.post("http://localhost:8000/api/paper/start", json={
    "session": "grid",
    "symbol": "BTC/USDT",
    "params": {
        "grid_spacing": 0.01,
        "grid_levels": 5
    }
})

# Check status
status = requests.get("http://localhost:8000/api/paper/status")
print(status.json())
```

## 🔧 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| API won't start | Check port availability: `netstat -an \| findstr 8000` |
| Tests failing | Run `pip install -r requirements-dev.txt` |
| Memory issues | Reduce `batch_size` in backtester config |
| Slow backtests | Use smaller date ranges or fewer strategies |
| Docker build fails | Ensure Docker Desktop is running |

### Performance Optimization

- **Backtesting**: Use parallel processing with `n_jobs=-1`
- **Data Loading**: Cache frequently used data in Redis
- **API Response**: Enable response caching for read endpoints
- **Database**: Add indexes on frequently queried columns

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**IMPORTANT**: This software is for educational and research purposes only.

- Not financial advice
- No warranty provided
- Use at your own risk
- Past performance doesn't guarantee future results
- Always do your own research before trading
- Never risk more than you can afford to lose

## 📞 Support

- **Documentation**: [https://docs.sofia-v2.io](https://docs.sofia-v2.io)
- **Issues**: [GitHub Issues](https://github.com/yourusername/sofia-v2/issues)
- **Discord**: [Join our community](https://discord.gg/sofia-v2)

---

Built with ❤️ by the Sofia Team | **Sofia V2** - Enterprise Quantitative Trading Platform
