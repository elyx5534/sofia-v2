# Sofia V2 Realtime DataHub

Production-grade real-time crypto data aggregation with anomaly detection and multi-exchange support.

## 🚀 Quick Start (Windows)

### One-Command Setup & Start
```powershell
cd backend
.\scripts\run.ps1 -CreateEnv -InstallDeps
```

### Start Development Server
```powershell
.\scripts\run.ps1
```

The DataHub will be available at:
- **WebSocket**: `ws://localhost:8000/ws`
- **REST API**: `http://localhost:8000`
- **Health Check**: `http://localhost:8000/health`
- **Metrics**: `http://localhost:8000/metrics`

## 📋 Features

### Real-Time Data Ingestion
- **Exchanges**: Binance (Spot/Futures), OKX, Bybit, Coinbase
- **Data Types**: Trades, Order Books, Liquidations
- **News**: CryptoPanic RSS feed integration
- **Reconnection**: Exponential backoff with gap detection

### Anomaly Detection
- **Big Trade Detection**: Z-score based analysis (>$250k USD)
- **Liquidation Spikes**: Statistical volume/frequency analysis
- **Volume Surges**: Real-time volume anomaly detection
- **Configurable Thresholds**: YAML-based configuration

### Storage Systems
- **Parquet Files**: High-performance columnar storage with rotation
- **TimescaleDB**: Optional time-series database (requires PostgreSQL)
- **Automatic Retention**: Configurable data retention policies

### Production Features
- **WebSocket Broadcasting**: Real-time data distribution
- **Prometheus Metrics**: Production monitoring
- **Windows Service**: NSSM-based service installation
- **Structured Logging**: JSON-formatted logs
- **Configuration Validation**: Startup-time validation

## 🛠️ Installation

### Prerequisites
- **Python 3.8+** (Tested with Python 3.13)
- **Windows 11** (PowerShell scripts optimized)
- **Optional**: PostgreSQL + TimescaleDB extension

### Manual Installation
```bash
# Clone the repository
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate

# Install dependencies
python -m pip install -r requirements.txt

# Copy configuration
copy .env.tpl .env

# Run system tests
python test_system.py
```

## ⚙️ Configuration

### Environment Variables (.env)
```env
# Core symbols (comma-separated)
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,ADAUSDT

# Exchange toggles
BINANCE_SPOT=true
BINANCE_FUTURES=true
OKX_ENABLED=true
BYBIT_ENABLED=true
COINBASE_ENABLED=true

# News configuration
CRYPTOPANIC_ENABLED=true
NEWS_POLL_SECONDS_DAY=30
NEWS_POLL_SECONDS_NIGHT=90

# Detection thresholds
BIG_TRADE_USD_MIN=250000
LIQ_SPIKE_SIGMA=3.0

# Storage
DATA_DIR=./data
USE_TIMESCALE=false
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sofia

# Server
HOST=0.0.0.0
PORT=8000
```

### YAML Configuration (config.yml)
The system uses `config.yml` for detailed exchange endpoints, feature configuration, and advanced settings. See the existing file for full options.

## 🚀 Running the DataHub

### Development Mode
```powershell
.\scripts\run.ps1
```

### Production Mode
```powershell
.\scripts\run.ps1 -Environment production
```

### Windows Service
```powershell
# Install as service (requires Admin)
.\scripts\install_service.ps1

# Start/stop/status
.\scripts\install_service.ps1 -Action start
.\scripts\install_service.ps1 -Action stop
.\scripts\install_service.ps1 -Action status
```

### Manual Start
```bash
# Activate virtual environment
.\.venv\Scripts\Activate

# Start with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 API Endpoints

### REST API
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed component status
- `GET /config` - Configuration summary
- `GET /symbols` - Configured trading symbols
- `GET /exchanges` - Enabled exchanges
- `GET /detectors` - Anomaly detector status
- `GET /storage` - Storage system status
- `GET /metrics` - Prometheus metrics

### WebSocket API
Connect to `ws://localhost:8000/ws` to receive real-time events:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Event:', data.type, data.data);
};

// Send ping
ws.send('ping');
```

### Event Types
- `trade` - Real-time trade data
- `orderbook` - Order book snapshots
- `liquidation` - Liquidation events
- `news` - News articles from CryptoPanic
- `alert` - Anomaly detection alerts
  - `big_trade` - Large trade detected
  - `liq_spike` - Liquidation spike detected
  - `volume_surge` - Volume surge detected

## 📁 Data Storage

### Parquet Files (Default)
```
data/
├── trades/trades_20250825_00.parquet
├── orderbook/orderbook_20250825_00.parquet
├── liquidations/liquidations_20250825_00.parquet
├── news/news_20250825_00.parquet
└── alerts/alerts_20250825_00.parquet
```

### TimescaleDB (Optional)
Enable by setting `USE_TIMESCALE=true` and providing `DATABASE_URL`. The system will automatically create hypertables with compression and retention policies.

## 🔧 Development

### System Tests
```bash
python test_system.py
```

### Adding New Exchanges
1. Create new ingestor in `app/ingestors/new_exchange.py`
2. Inherit from `BaseExchangeIngestor`
3. Implement required methods
4. Add to `main.py` startup routine
5. Configure in `config.yml`

### Adding New Detectors
1. Create detector in `app/features/detectors.py`
2. Subscribe to relevant events
3. Add to `DetectorManager`
4. Configure thresholds in `config.yml`

## 📈 Monitoring

### Prometheus Metrics
- `websocket_connections_total` - Active WebSocket connections
- `events_processed_total` - Events processed by type/source
- `event_processing_seconds` - Event processing latency
- `rss_fetch_total` - RSS fetch attempts/status

### Health Checks
The `/health/detailed` endpoint provides component status:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T00:00:00Z",
  "components": {
    "event_bus": "healthy",
    "websocket_connections": 5,
    "enabled_exchanges": ["binance", "okx"],
    "ingestors": {
      "binance": "connected",
      "okx": "connected"
    }
  }
}
```

## 🔒 Security

### Data Sources
- **RSS Feeds Only**: No paid API keys required
- **Public WebSockets**: Read-only market data connections
- **No Trading**: Pure data aggregation, no trading functionality

### Network Security
- **CORS Enabled**: Configure origins in production
- **Health Checks**: Monitor component status
- **Error Isolation**: Component failures don't affect others

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Install missing dependencies
   python -m pip install -r requirements.txt
   ```

2. **WebSocket Connection Failures**
   - Check internet connectivity
   - Verify exchange endpoints in `config.yml`
   - Monitor logs for reconnection attempts

3. **Storage Issues**
   - Ensure `DATA_DIR` is writable
   - Check disk space for Parquet files
   - Verify PostgreSQL connection for TimescaleDB

4. **Unicode Errors (Windows)**
   - System handles encoding automatically
   - Check Windows code page settings if issues persist

### Logs
- **Development**: Console output with structured logging
- **Service**: Logs written to `logs/` directory
- **Format**: JSON-structured for production parsing

## 📝 License

This is part of the Sofia V2 trading platform. See project root for license information.

## 🤝 Contributing

1. Follow existing code patterns
2. Add tests for new features
3. Update configuration examples
4. Test on Windows 11 environment
5. Document API changes

## 📞 Support

For issues:
1. Check logs for error details
2. Verify configuration with `python test_system.py`
3. Review health check endpoints
4. Check component status via API

---

**Built for Windows 11 • Production Ready • Real-Time Data • Zero Trading Risk**