# Sofia v2 - Trading Platform

A modern trading platform with modular architecture for financial data processing and analysis.

## Modules

### Data Hub v0

FastAPI service providing OHLCV (Open, High, Low, Close, Volume) data with intelligent caching.

**Features:**
- 📊 Equity data via Yahoo Finance (yfinance)
- 🪙 Cryptocurrency data via CCXT (multiple exchanges)
- 💾 SQLite caching with configurable TTL (default: 10 minutes)
- ⚡ Async/await architecture for high performance
- 🔍 Symbol search and metadata
- 🛡️ Comprehensive error handling
- ✅ Full test coverage

## Installation

### Prerequisites
- Python 3.11+
- pip or poetry

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sofia-v2.git
cd sofia-v2
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Running the Data Hub

### Development Mode

```bash
uvicorn src.data_hub.api:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn src.data_hub.api:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Search Symbols

Search for equity symbols:
```bash
curl "http://localhost:8000/symbols?query=AAPL&asset_type=equity"
```

Search for crypto symbols:
```bash
curl "http://localhost:8000/symbols?query=BTC&asset_type=crypto"
```

### Get OHLCV Data

Fetch equity data:
```bash
curl "http://localhost:8000/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1d"
```

Fetch crypto data:
```bash
curl "http://localhost:8000/ohlcv?symbol=BTC/USDT&asset_type=crypto&timeframe=1h&exchange=binance"
```

Bypass cache:
```bash
curl "http://localhost:8000/ohlcv?symbol=AAPL&asset_type=equity&nocache=true"
```

With date range:
```bash
curl "http://localhost:8000/ohlcv?symbol=AAPL&asset_type=equity&start_date=2024-01-01T00:00:00&end_date=2024-01-31T23:59:59"
```

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

Run specific test file:
```bash
pytest tests/test_health.py -v
```

## Code Quality

Run linting:
```bash
ruff check src tests
```

Run type checking:
```bash
mypy src
```

Run security scan:
```bash
bandit -r src
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_TTL` | Cache TTL in seconds | 600 (10 min) |
| `DATABASE_URL` | SQLite database URL | sqlite+aiosqlite:///./data_hub.db |
| `DEFAULT_EXCHANGE` | Default crypto exchange | binance |
| `PROVIDER_TIMEOUT` | Provider timeout in seconds | 30 |
| `LOG_LEVEL` | Logging level | INFO |

## Known Limitations

1. **Yahoo Finance Rate Limiting**: yfinance may be rate-limited by Yahoo. Consider adding delays for bulk requests.
2. **Exchange API Keys**: Currently using public endpoints only. Private endpoints would require API key configuration.
3. **Historical Data**: Limited by provider capabilities (yfinance: varies by timeframe, CCXT: typically 500-1000 candles).
4. **Cache Size**: SQLite database grows with cached data. Consider periodic cleanup for production.

## Architecture

```
src/data_hub/
├── __init__.py          # Module exports
├── api.py               # FastAPI application and routes
├── models.py            # Pydantic and SQLModel schemas
├── cache.py             # Cache management layer
├── settings.py          # Configuration management
└── providers/           # Data provider implementations
    ├── __init__.py
    ├── yfinance_provider.py  # Yahoo Finance integration
    └── ccxt_provider.py      # Cryptocurrency exchange integration
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)

## Support

For issues and questions, please use the GitHub issue tracker.
