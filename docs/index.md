# Sofia V2 Documentation

## Quick Links

- [Architecture Overview](architecture.md) - System design and components
- [Data Hub](datahub.md) - Data layer and market data management
- [Backtester](backtester.md) - Backtesting engine with WFO/GA optimization
- [Execution](execution.md) - Live trading, paper mode, and risk management
- [Arbitrage](arbitrage.md) - Turkish arbitrage monitoring (BtcTurk/Paribu)
- [Operations](operations.md) - Production deployment and monitoring

## Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Start API**: `uvicorn src.api.main:app --reload`
3. **Access dashboards**:
   - Trading Dashboard: http://localhost:8000/dashboard
   - Backtest Studio: http://localhost:8000/backtest-studio
   - API Docs: http://localhost:8000/docs

## Project Structure

```
sofia-v2/
├── src/
│   ├── api/        # FastAPI routes and endpoints
│   ├── services/   # Business logic and core services
│   └── ui/         # Web interface templates
├── tests/          # Test suite
├── scripts/        # Automation and deployment
└── docs/           # Documentation (you are here)
```
