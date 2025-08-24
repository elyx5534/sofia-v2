# Sofia V2 - AI-Powered Trading Platform 🚀

> **Professional-grade algorithmic trading system with real-time data, backtesting, and AI-powered strategies**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Lines of Code](https://img.shields.io/badge/Lines%20of%20Code-50K+-purple.svg)]()

## 🌟 Overview

Sofia V2 is an enterprise-grade algorithmic trading platform that combines:
- **Real-time market data** from multiple sources (YFinance, CCXT)
- **AI-powered trading strategies** with machine learning models
- **Professional backtesting engine** with advanced metrics
- **Modern web UI** with real-time dashboards
- **Risk management system** with position sizing and stop-losses
- **Multi-asset support** (Crypto, Stocks, Forex)

## 🔥 Key Features

### 📊 Trading Engine
- **5+ Built-in Strategies**: SMA, RSI, MACD, Bollinger Bands, Multi-indicator
- **Custom Strategy Framework**: Easy to extend and customize
- **Real-time Execution**: Async trading engine with WebSocket support
- **Risk Management**: Position sizing, stop-loss, take-profit automation

### 📈 Backtesting System
- **Historical Data**: Multi-year datasets with 1-minute resolution
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate, profit factor
- **Portfolio Simulation**: Realistic trading costs and slippage
- **API Integration**: RESTful API for programmatic access

### 🧠 AI/ML Components
- **Price Prediction**: XGBoost and Random Forest models
- **Sentiment Analysis**: Social media and news sentiment integration
- **Genetic Algorithm**: Strategy parameter optimization
- **Technical Indicators**: 20+ custom technical analysis tools

### 🌐 Web Interface
- **Modern Dashboard**: Real-time portfolio tracking
- **Interactive Charts**: Advanced charting with Chart.js
- **Strategy Management**: Deploy and monitor strategies
- **Market Analysis**: Live cryptocurrency and stock data
- **Automated Scheduler**: Background jobs for data fetching, scanning, and news updates
- **Comprehensive CLI**: Full command-line interface for all operations
- **REST API**: Complete API for integration with external tools

## 📋 Requirements

- **Python 3.11+**
- **Node.js 16+** (for UI dependencies)
- **Windows 10/11** (PowerShell scripts provided)

## ⚡ Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd sofia-v2
```

### 2. One-Click Startup (Windows)

```powershell
# Full setup and startup
.\run.ps1

# Skip initial data fetch
.\run.ps1 -SkipFetch

# Skip news updates  
.\run.ps1 -SkipNews

# Custom port
.\run.ps1 -Port 9000
```

### 3. Manual Setup

```bash
# Install Python dependencies
pip install fastapi uvicorn[standard] ccxt pandas pyarrow polars httpx apscheduler loguru python-dotenv jinja2

# Install Node.js dependencies
npm install

# Copy UI libraries
cp node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js static/js/
```

## 🖥️ Web Interface

After startup, access the web interface:

- **Signals Dashboard**: http://127.0.0.1:8000/signals
- **Signal Heatmap**: http://127.0.0.1:8000/heatmap  
- **Interactive Charts**: http://127.0.0.1:8000/chart/BTC/USDT
- **News Aggregation**: http://127.0.0.1:8000/news
- **System Status**: http://127.0.0.1:8000/api/status

## 🔧 Command Line Interface

### Data Management
```bash
# Fetch all USDT pairs data (last 30 days)
python sofia_cli.py fetch-all --days 30

# Update recent data (last 24 hours)  
python sofia_cli.py update --hours 24

# List available symbols
python sofia_cli.py list-symbols --limit 20
```

### Signal Scanning
```bash
# Run signal scan on 1h timeframe
python sofia_cli.py scan --timeframe 1h

# View system status
python sofia_cli.py status
```

### News Updates
```bash
# Update news from all sources
python sofia_cli.py news --hours 24 --symbol-limit 10
```

### Web Server
```bash
# Start web server
python sofia_cli.py web --host 127.0.0.1 --port 8000 --reload

# Production mode
python sofia_cli.py web --host 0.0.0.0 --port 80
```

### Automated Scheduler
```bash
# Start scheduler (runs background jobs)
python sofia_cli.py scheduler start

# Check scheduler status
python sofia_cli.py scheduler status

# Run specific job manually
python sofia_cli.py scheduler run --job fetch_data
```

## 📊 Signal Scanning Rules

The scanner uses 6 different technical analysis rules:

1. **RSI Rebound** (Weight: 2.0): Detects recovery from oversold conditions (RSI < 30)
2. **SMA Cross** (Weight: 1.5): Identifies bullish crossover of SMA 20 over SMA 50
3. **Bollinger Bands Bounce** (Weight: 1.0): Catches bounces from lower Bollinger Band
4. **Volume Breakout** (Weight: 1.0): High volume above 2x average volume
5. **MACD Signal** (Weight: 1.5): Bullish MACD line crossover above signal line
6. **Price Action** (Weight: 1.0): Strong 1h momentum with reasonable 24h performance

**Signal Scoring**: Combines all rule weights for final signal strength (0-10+ scale)

## 📈 Technical Indicators

### Supported Indicators:
- **Trend**: SMA (20, 50), EMA (12, 26), MACD
- **Momentum**: RSI (14), Stochastic (14, 3)  
- **Volatility**: Bollinger Bands (20, 2), ATR (14)
- **Volume**: Volume SMA (20)
- **Price Action**: 1h and 24h percentage changes

## 📰 News Integration

### Sources:
- **CryptoPanic**: Community-driven crypto news with sentiment voting
- **GDELT**: Global news analysis with tone scoring
- **Coverage**: Real-time news for major cryptocurrencies and market events

### Features:
- Sentiment analysis and impact scoring
- Symbol-specific news filtering
- Global market trend detection
- Automatic news updates every 15 minutes

## 🗂️ Project Structure

```
sofia-v2/
├── src/
│   ├── data/           # CCXT exchange interfaces and data pipeline
│   ├── metrics/        # Technical indicators calculation
│   ├── scan/           # Signal scanning rules and engine
│   ├── news/           # News aggregation (CryptoPanic + GDELT)
│   ├── web/            # FastAPI web application
│   ├── scheduler/      # Background job scheduling
│   └── utils/          # Utility functions
├── templates/          # Jinja2 HTML templates
├── static/            # CSS, JS, and static assets
├── data/              # Parquet data storage
├── outputs/           # JSON outputs and logs
├── tests/             # Test suite
├── sofia_cli.py       # Main CLI interface
├── run.ps1           # PowerShell startup script
└── requirements.txt   # Python dependencies
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# CryptoPanic API (optional)
CRYPTOPANIC_TOKEN=your_token_here

# Server settings
HOST=127.0.0.1
PORT=8000
DEBUG=true

# Data storage paths
DATA_DIR=./data
OUTPUTS_DIR=./outputs
```

### Scheduler Jobs (Automatic)

- **Data Fetch**: Every 15 minutes (recent data updates)
- **Signal Scan**: Every 5 minutes (signal detection)
- **News Update**: Every 15 minutes (news aggregation)
- **Health Check**: Every 10 minutes (system monitoring)
- **Full Data Sync**: Daily at 2:00 AM UTC (comprehensive update)
- **Cleanup**: Weekly (maintenance tasks)

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Test specific module
python -m pytest tests/test_indicators.py -v

# Test with coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=html
```

## 🚀 API Reference

### Core Endpoints:
- `GET /api/signals` - Current signal data
- `GET /api/heatmap` - Signal heatmap visualization  
- `GET /api/ohlcv?symbol=BTC/USDT&timeframe=1h` - Chart data
- `GET /api/news?symbol=BTC/USDT&limit=20` - News articles
- `GET /api/status` - System health status
- `GET /api/search?q=BTC` - Symbol search

### Response Format:
```json
{
  "signals": [
    {
      "symbol": "BTC/USDT",
      "score": 3.5,
      "signals": [
        {
          "rule_name": "RSI Rebound",
          "signal_strength": 1.8,
          "message": "RSI rebounding from oversold (28.5)"
        }
      ],
      "indicators": {
        "close": 43250.50,
        "rsi": 28.5,
        "price_change_24h": 2.1
      }
    }
  ]
}
```

## 🛠️ Development

### Adding New Scan Rules:

1. Create rule class in `src/scan/rules.py`:
```python
class MyCustomRule(ScanRule):
    def __init__(self):
        super().__init__("My Rule", weight=1.5)
    
    def evaluate(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        # Your logic here
        return {'signal': strength, 'message': 'Rule triggered'}
```

2. Add to `DEFAULT_RULES` list in same file

### Adding New Indicators:

1. Add function to `src/metrics/indicators.py`:
```python
def my_indicator(df: pd.DataFrame, period: int = 14) -> pd.Series:
    # Your calculation
    return result_series
```

2. Include in `add_all_indicators()` function

## 🔧 Troubleshooting

### Common Issues:

**"No data available"**: Run initial data fetch
```bash
python sofia_cli.py fetch-all --days 30
```

**"Exchange connection failed"**: Check internet connection, exchange status

**"Port already in use"**: Change port in run.ps1 or web command
```bash
python sofia_cli.py web --port 8001
```

**"Module not found"**: Reinstall dependencies
```bash
pip install -r requirements.txt
```

### Performance Tuning:

- Reduce `--max-workers` for data fetching on slower systems
- Increase scan intervals in scheduler for less frequent updates
- Limit symbol count for news updates to reduce API calls

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## ⚠️ Disclaimer

This software is for educational and research purposes only. Not financial advice. Use at your own risk. Always do your own research before making investment decisions.

---

**Sofia V2** - Professional Crypto Signal Scanner 📊⚡
