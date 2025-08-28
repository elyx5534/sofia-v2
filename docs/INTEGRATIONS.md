# Sofia V2 - Integration Documentation

## 🏗️ Architecture Overview

Sofia V2 is a real-time trading platform with multi-source data ingestion, AI-powered analysis, and paper trading capabilities.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│  (Protected Templates + Purple Gradient Theme)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     API Gateway                              │
│  FastAPI (Port 8009) + WebSocket + REST                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Data Bus Layer                             │
│  Redis Streams / NATS (Pub/Sub + Message Queue)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Data Ingestion Layer                            │
├──────────────────────────────────────────────────────────────┤
│ • Crypto WS (Binance, OKX, Coinbase, Bybit)                 │
│ • Equities (Alpaca → Yahoo → TwelveData)                    │
│ • News RSS (Coindesk, Cointelegraph, etc)                   │
│ • Whale Alerts (>100k USDT trades)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Storage & Processing                            │
├──────────────────────────────────────────────────────────────┤
│ • QuestDB / TimescaleDB (Time Series)                       │
│ • Redis (Cache + Real-time)                                 │
│ • MongoDB (News + Alerts)                                   │
│ • AI Models (LightGBM + Calibration)                        │
└──────────────────────────────────────────────────────────────┘
```

## 📦 Component Details

### 1. UI Protection System
- **Location**: `sofia_ui/`
- **Protection**: Pre-commit hooks + CI guards + CODEOWNERS
- **Theme**: Purple gradient (UNTOUCHABLE)
- **Extensions**: Only via `sofia_ui/extensions/`

### 2. Real-time Data Bus
- **File**: `ingestors/crypto_ws.py`
- **Exchanges**: Binance, OKX, Coinbase, Bybit
- **Protocol**: WebSocket with exponential backoff
- **Topics**: `ticks.<EXCHANGE>.<SYMBOL>`
- **Metrics**: lag_ms, reconnects, stale_ratio

### 3. Equity Data System  
- **File**: `ingestors/equities_pull.py`
- **Primary**: Alpaca/IEX/Polygon (optional paid)
- **Fallback Chain**:
  1. Yahoo Finance (yfinance)
  2. TwelveData (15min delay)
  3. Stooq (EOD)
- **Cache**: TTL with aggressive caching

### 4. News & Sentiment
- **File**: `news/rss_agg.py`
- **Sources**: 
  - Coindesk, Cointelegraph, Decrypt
  - TheBlock, CryptoSlate, Bitcoin Magazine
- **Features**: ETag caching, UA rotation, sentiment scoring
- **Storage**: MongoDB with full-text search

### 5. Whale Tracking
- **File**: `alerts/whale_trade.py`
- **Threshold**: 100k USDT (configurable)
- **Alerts**: Email, Telegram, Webhook
- **Patterns**: Single trades, accumulation, distribution

### 6. AI Score Engine
- **Files**: `src/ai/featurizer.py`, `src/ai/model.py`
- **Features**: 
  - Returns: r_1m, r_5m, r_1h
  - Technical: zscore_20, ATR%, RSI, momentum
  - Volume: vol_σ_1h, OBV_30
  - Sentiment: news_score, whale_activity
- **Model**: LightGBM + Isotonic Calibration
- **Performance**: P95 < 150ms
- **Endpoint**: `/api/ai/score`

### 7. Paper Trading OMS
- **File**: `src/trade/paper.py`
- **Features**:
  - Realistic fees (0.1% default)
  - Slippage simulation (0.05%)
  - Risk caps (position size, daily loss)
  - PnL tracking (realized + unrealized)
- **Endpoints**:
  - POST `/trade/on_tick` - Execute trades
  - GET `/trade/account` - Portfolio status

### 8. Monitoring
- **Prometheus**: Port 8000 `/metrics`
- **Grafana**: Import `monitoring/grafana_dashboard.json`
- **Alerts**: `monitoring/alert_rules.yml`
- **Health**: `/health` endpoint

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.9+
python --version

# Redis
redis-server --version

# PostgreSQL (for TimescaleDB)
psql --version
```

### Installation
```bash
# Clone repository
git clone https://github.com/elyx5534/sofia-v2.git
cd sofia-v2

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Install pre-commit hooks
pre-commit install
```

### Configuration (.env)
```env
# Data Bus
SOFIA_BUS=redis
REDIS_URL=redis://localhost:6379

# Exchanges
SOFIA_EXCHANGES=binance,okx,coinbase,bybit
SOFIA_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT

# Database
SOFIA_DB=questdb
QUESTDB_TCP=localhost:8812

# Equity Data (Optional)
EQUITY_PRIMARY=yahoo  # or alpaca if you have API keys
ALPACA_KEY=your_key_here
ALPACA_SECRET=your_secret_here

# AI Model
AI_MODEL_PATH=models/ai_score_v1.bin
AI_CACHE_TTL=5

# Paper Trading
PAPER_INITIAL_BALANCE=100000
PAPER_FEE_RATE=0.001
PAPER_SLIPPAGE=0.0005

# Monitoring
PROMETHEUS_PORT=8000
METRICS_ENABLED=true
```

### Starting Services

```bash
# Start infrastructure
python start_infrastructure.py

# Or start individually:

# 1. Start Redis
redis-server

# 2. Start API
uvicorn src.api.main:app --port 8009 --reload

# 3. Start data ingestion
python ingestors/crypto_ws.py &
python ingestors/equities_pull.py &

# 4. Start writers
python writers/ts_writer.py &

# 5. Start monitoring
python monitoring/metrics_server.py &
```

## 📊 API Endpoints

### Public Endpoints
- `GET /` - Homepage
- `GET /ai-trading` - AI Trading Analysis
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

### Data Endpoints
- `GET /api/price/{symbol}` - Get latest price
- `GET /api/symbols` - List available symbols
- `GET /api/news?symbol={symbol}` - Get news for symbol

### AI Endpoints
- `POST /api/ai/score` - Get AI score for symbol
- `GET /api/ai/features/{symbol}` - Get feature values

### Trading Endpoints
- `POST /trade/on_tick` - Execute paper trade
- `GET /trade/account` - Get account status
- `GET /trade/positions` - List positions
- `GET /trade/history` - Trade history

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tests/

# E2E tests (requires running server)
python tests/e2e/test_ui_theme.py

# Theme regression
playwright test tests/e2e/theme_regression.spec.ts

# Load testing
locust -f tests/load/locustfile.py --host http://localhost:8009
```

### Acceptance Criteria
- ✅ Data bus lag < 300ms for 10 symbols
- ✅ Zero drops in normal operation
- ✅ Equity fallback usage < 10%
- ✅ AI Score AUC > 0.55, ECE < 0.05
- ✅ API P95 latency < 150ms
- ✅ UI theme diff = 0 (protected)
- ✅ 72h paper trading with metrics

## 🔧 Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find process using port
lsof -i :8009
# Or on Windows
netstat -ano | findstr :8009

# Kill process
kill -9 <PID>
```

#### Redis Connection Error
```bash
# Check Redis is running
redis-cli ping
# Should return PONG

# Start Redis if not running
redis-server
```

#### WebSocket Disconnections
- Check `SOFIA_RECONNECT_DELAY` in .env (default: 5)
- Monitor reconnect metrics at `/metrics`
- Check exchange API status pages

#### UI Theme Issues
- NEVER modify files in `sofia_ui/`
- Use `git restore --source=origin/main -- sofia_ui` if changed
- Extensions only in `sofia_ui/extensions/`

## 📈 Performance Tuning

### Database Optimization
```sql
-- QuestDB: Partition by day for better performance
CREATE TABLE ticks (
    symbol STRING,
    price DOUBLE,
    volume DOUBLE,
    timestamp TIMESTAMP
) PARTITION BY DAY;

-- TimescaleDB: Create hypertable
SELECT create_hypertable('ticks', 'timestamp');
```

### Redis Optimization
```redis
# Set max memory
CONFIG SET maxmemory 2gb
CONFIG SET maxmemory-policy allkeys-lru

# Enable persistence
CONFIG SET save "900 1 300 10 60 10000"
```

### AI Model Caching
```python
# In .env
AI_CACHE_TTL=5  # Cache for 5 seconds
AI_BATCH_SIZE=10  # Batch predictions
```

## 🔒 Security

### API Keys
- Never commit `.env` file
- Use `.env.example` as template
- Rotate keys regularly
- Use read-only keys where possible

### Rate Limiting
- Implemented per-IP for `/api/ai/score`
- Default: 10 requests/second
- Configurable via `RATE_LIMIT_QPS`

### CORS Configuration
```python
# In src/api/main.py
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://yourdomain.com"
]
```

## 📝 Credits & Licenses

### Open Source Components
- **ccxt**: MIT License - Cryptocurrency exchange library
- **yfinance**: Apache 2.0 - Yahoo Finance data
- **LightGBM**: MIT License - Gradient boosting framework
- **Redis**: BSD License - In-memory data store
- **QuestDB**: Apache 2.0 - Time-series database
- **FastAPI**: MIT License - Web framework

### Data Sources
- Binance, OKX, Coinbase, Bybit - Exchange APIs
- Yahoo Finance - Market data
- RSS Feeds - News aggregation

## 🤝 Contributing

1. Never modify UI templates directly
2. Use feature branches: `feat/`, `fix/`, `docs/`
3. Run pre-commit hooks before pushing
4. Include tests for new features
5. Update documentation

## 📞 Support

- GitHub Issues: https://github.com/elyx5534/sofia-v2/issues
- Documentation: This file
- Monitoring: Grafana dashboard

---

**Last Updated**: 2025-08-28
**Version**: 2.0.0
**Maintained by**: @elyx5534