# Sofia V2 - Real-Time Data Infrastructure

## Overview

Sofia V2 is a comprehensive real-time data infrastructure for cryptocurrency and equity trading with advanced AI-powered features, whale trade monitoring, news aggregation, and paper trading capabilities.

## 🏗️ Architecture

The system is built with a microservices architecture using Redis Streams for inter-service communication:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data Ingestors │    │  Time Series DB │    │   AI Models     │
│                 │    │                 │    │                 │
│ • Crypto WS     │───▶│ • QuestDB       │───▶│ • LightGBM      │
│ • Equities API  │    │ • TimescaleDB   │    │ • LogRegression │
│ • RSS News      │    │ • Redis Streams │    │ • Feature Eng   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Whale Monitor  │    │  Paper Trading  │    │   Monitoring    │
│                 │    │                 │    │                 │
│ • Alert System  │    │ • Order Mgmt    │    │ • Prometheus    │
│ • Notifications │    │ • Risk Mgmt     │    │ • Grafana       │
│ • Pattern Det   │    │ • AI Signals    │    │ • Health Checks │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Components

### 1. Data Ingestors

#### Crypto WebSocket (`ingestors/crypto_ws.py`)
- **Exchanges**: Binance, OKX, Coinbase, Bybit
- **Features**: 
  - Exponential backoff with jitter
  - Deduplication (>15s stale detection)
  - Redis Streams publishing
  - miniTicker and trade streams

#### Equities Puller (`ingestors/equities_pull.py`)
- **Primary**: Alpaca, IEX, Polygon
- **Fallback-1**: Yahoo Finance
- **Fallback-2**: TwelveData, Stooq
- **Features**: TTL cache, rate limiting, normalization

#### News RSS Aggregator (`news/rss_agg.py`)
- **Sources**: Coindesk, Cointelegraph, Decrypt, TheBlock
- **Features**: ETag/If-Modified-Since optimization, user-agent rotation

### 2. Time Series Writer (`writers/ts_writer.py`)
- **Primary DB**: QuestDB
- **Fallback DB**: TimescaleDB
- **Features**: 1s/1m OHLCV aggregation, append-only writes
- **Metrics**: bus_lag_ms, writer_queue, reconnects, stale_ratio

### 3. AI System

#### Feature Extractor (`src/ai/featurizer.py`)
- **Features**: r_1m, r_5m, r_1h, zscore_20, ATR%, RV, mom_14, vol_σ_1h
- **Indicators**: SMA, EMA, Bollinger Bands, RSI, MACD
- **Real-time**: Streaming feature computation

#### ML Models (`src/ai/model.py`)
- **Models**: LightGBM, Logistic Regression
- **Calibration**: Isotonic Calibration
- **Performance**: P95 < 150ms response time
- **Features**: Auto-retraining, ensemble predictions

### 4. Paper Trading OMS (`src/trade/paper.py`)
- **Features**: Fees, slippage simulation, risk caps
- **Risk Management**: Position size limits, daily loss limits
- **AI Integration**: Signal-based execution
- **Metrics**: PnL tracking, Sharpe ratio, win rate

### 5. Whale Trade Monitor (`alerts/whale_trade.py`)
- **Detection**: Trades ≥100k USDT
- **Patterns**: Accumulation, unusual activity
- **Alerts**: Email, Telegram, webhooks
- **Thresholds**: Configurable volume thresholds

### 6. Monitoring (`monitoring/`)
- **Prometheus**: Custom metrics collection
- **Grafana**: Real-time dashboards
- **Alerts**: System health, performance degradation
- **Health Checks**: Component status monitoring

## 📊 Metrics & Monitoring

### Key Metrics
- **Data Ingestion**: Tick rates, latency, stale ratios
- **Database**: Write rates, latency, queue sizes
- **AI Models**: Prediction latency, accuracy, feature importance
- **Trading**: PnL, positions, order fill rates
- **System**: CPU, memory, disk usage

### Grafana Dashboard
Import the dashboard from `monitoring/grafana_dashboard.json` to visualize:
- System overview and health
- Data ingestion rates and latency
- Database performance
- AI model performance
- Paper trading metrics
- News and whale trade alerts

## 🛠️ Installation & Setup

### 1. Prerequisites
```bash
# Install Redis
sudo apt-get install redis-server

# Install QuestDB (optional, can use TimescaleDB)
curl -L https://github.com/questdb/questdb/releases/download/7.3.0/questdb-7.3.0-rt-linux-amd64.tar.gz | tar -xz
cd questdb-7.3.0-rt-linux-amd64 && ./questdb.sh start

# Install TimescaleDB (optional, PostgreSQL extension)
sudo apt-get install timescaledb-postgresql-14
```

### 2. Python Environment
```bash
# Create virtual environment
python -m venv sofia-v2-env
source sofia-v2-env/bin/activate  # Linux/Mac
# or
sofia-v2-env\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 4. Database Setup
```sql
-- QuestDB (automatic table creation)
-- TimescaleDB setup
CREATE DATABASE sofia_timeseries;
-- Extension will be installed automatically
```

## 🏃‍♂️ Running the System

### Option 1: Individual Components
```bash
# Start each component separately
python -m ingestors.crypto_ws
python -m writers.ts_writer
python -m ingestors.equities_pull
python -m news.rss_agg
python -m alerts.whale_trade
python -m src.ai.featurizer
python -m src.ai.model
python -m src.trade.paper
python -m monitoring.metrics_server
```

### Option 2: Docker Compose (Recommended)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Option 3: Process Manager
```bash
# Using PM2
pm2 start ecosystem.config.js

# Using systemd
sudo systemctl start sofia-v2
```

## 🔧 Configuration

### Environment Variables

Key configuration sections in `.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379

# Exchanges
CRYPTO_EXCHANGES=binance,okx,coinbase,bybit
CRYPTO_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT

# Database
QUESTDB_HOST=localhost
QUESTDB_PORT=8812

# AI Models
AI_MODEL_TYPES=lightgbm,logistic_regression
AI_MIN_SIGNAL_CONFIDENCE=0.6

# Paper Trading
PAPER_INITIAL_BALANCE=100000
PAPER_MAX_POSITION_SIZE_PCT=10.0

# Notifications
WHALE_WEBHOOK_URL=https://your-webhook-url.com
TELEGRAM_BOT_TOKEN=your_bot_token
```

## 📈 Performance Characteristics

### Throughput
- **Crypto Ticks**: 1,000+ ticks/sec per exchange
- **Database Writes**: 10,000+ writes/sec
- **AI Predictions**: <150ms P95 latency
- **News Processing**: 100+ articles/hour

### Scalability
- **Horizontal**: Redis Streams support multiple consumers
- **Vertical**: Configurable batch sizes and worker counts
- **Storage**: QuestDB handles 1M+ ticks/sec, TimescaleDB for complex queries

### Reliability
- **Failover**: Primary/fallback databases
- **Reconnection**: Exponential backoff with jitter
- **Deduplication**: Hash-based duplicate detection
- **Monitoring**: Comprehensive health checks

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v --cov=src --cov-report=html

# Test specific components
pytest tests/test_crypto_ws.py -v
pytest tests/test_ai_models.py -v
pytest tests/test_paper_trading.py -v

# Integration tests
pytest tests/test_integration.py -v
```

## 🚨 Monitoring & Alerts

### Health Checks
- **Component Status**: Each service reports health to Redis
- **Database Connectivity**: Connection monitoring
- **Data Freshness**: Stale data detection
- **Resource Usage**: CPU, memory, disk monitoring

### Alert Rules
- System component failures
- High latency (>150ms for AI predictions)
- Database write errors
- Whale trade detection
- Model accuracy degradation

## 🔒 Security

### API Keys
Store sensitive keys securely:
```bash
# Use environment variables
export ALPACA_API_KEY="your_key_here"

# Or encrypted files
echo "your_key" | gpg --encrypt > alpaca_key.gpg
```

### Network Security
- Redis: Use AUTH and SSL/TLS
- Databases: Connection encryption
- APIs: Rate limiting and authentication

## 📊 Sample Outputs

### Whale Trade Alert
```json
{
  "alert_type": "whale_trade",
  "severity": "high",
  "message": "🐋 Large buy order: 156.78 BTC ($4,567,890) on Binance",
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "volume_usdt": 4567890.12,
  "timestamp": 1693847234.567
}
```

### AI Prediction
```json
{
  "symbol": "BTCUSDT",
  "model_type": "ensemble",
  "raw_score": 0.73,
  "calibrated_score": 0.68,
  "prediction_class": 1,
  "confidence": 0.85,
  "timestamp": 1693847234.567
}
```

### Paper Trade Execution
```json
{
  "order_id": "uuid-1234-5678",
  "symbol": "BTCUSDT",
  "side": "buy",
  "quantity": 0.1,
  "price": 43250.50,
  "fees": 4.325,
  "status": "filled",
  "timestamp": 1693847234.567
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋‍♂️ Support

For questions and support:
- Open an issue on GitHub
- Check the documentation
- Review the configuration examples

---

**Note**: This is a comprehensive trading infrastructure. Please test thoroughly in a paper trading environment before considering any real trading applications.