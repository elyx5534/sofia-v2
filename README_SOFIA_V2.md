# 🚀 Sofia V2 - AI-Powered Crypto Trading Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

> **The most advanced AI-powered crypto trading platform with real-time data, machine learning predictions, and professional portfolio management.**

## ✨ Key Features

### 🤖 AI-Powered Trading
- **Multi-Model ML Predictions**: Ensemble of Random Forest, Gradient Boosting, and Linear Regression
- **Advanced Technical Analysis**: RSI, MACD, Bollinger Bands, Moving Averages
- **Real-Time Signal Detection**: 12+ trading strategies with confidence scoring
- **Auto-Trading Engine**: Automated execution with risk management

### 📊 Professional Analytics  
- **Portfolio Management**: Sharpe ratio, Alpha, Beta, VaR calculations
- **Risk Metrics**: Sortino ratio, Maximum Drawdown, Correlation analysis
- **Performance Tracking**: Win rate, P&L analysis, trade history
- **Real-Time Monitoring**: Live portfolio updates and alerts

### 💹 Real-Time Data
- **Live Crypto Prices**: Direct integration with CoinGecko & Binance APIs
- **Paper Trading**: Risk-free trading with real market prices
- **WebSocket Streaming**: Sub-second data updates
- **Market Scanner**: Top gainers/losers, volume surges, breakouts

### 🎨 Beautiful Interface
- **Glassmorphism Design**: Modern UI with particle animations
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Real-Time Charts**: Interactive price charts with technical indicators
- **Live Notifications**: Trading signals and portfolio alerts

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/sofia-v2.git
cd sofia-v2

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch Sofia V2

```bash
# Start the platform
python run_sofia_v2.py
```

### 3. Access the Platform

- **Main Application**: http://localhost:8000
- **Trading Interface**: http://localhost:8000/trading  
- **API Documentation**: http://localhost:8000/docs

## 🏗️ Architecture

```
Sofia V2
├── 📊 Real-Time Data Layer
│   ├── CoinGecko API Integration
│   ├── Binance API Integration  
│   └── WebSocket Data Streaming
│
├── 🧠 AI Engine
│   ├── Multi-Model ML Pipeline
│   ├── Technical Indicator Calculations
│   └── Prediction Ensemble System
│
├── 💼 Trading Engine
│   ├── Paper Trading Execution
│   ├── Order Management System
│   ├── Risk Management Framework
│   └── Portfolio Analytics
│
├── 🔍 Market Scanner
│   ├── Signal Detection Algorithms
│   ├── Pattern Recognition
│   └── Opportunity Identification
│
└── 🌐 Web Interface
    ├── Real-Time Dashboard
    ├── Trading Interface
    ├── Portfolio Management
    └── API Endpoints
```

## 🔧 Configuration

### Environment Variables
```bash
# Optional API keys for higher rate limits
COINGECKO_API_KEY=your_key_here
BINANCE_API_KEY=your_key_here

# Database configuration (optional)
DATABASE_URL=sqlite:///./sofia_v2.db

# Security
SECRET_KEY=your_secret_key_here
```

### Trading Configuration
```python
# Auto-trading configuration
config = AutoTradingConfig(
    enabled=True,
    max_position_size=0.1,  # Max 10% per position
    risk_tolerance=0.02,    # Max 2% risk per trade
    min_confidence=0.7,     # Minimum 70% confidence
    stop_loss_percent=0.05, # 5% stop loss
    take_profit_percent=0.1 # 10% take profit
)
```

## 📊 AI Models & Strategies

### Machine Learning Models
- **Random Forest**: Ensemble decision tree model for price prediction
- **Gradient Boosting**: Sequential learning for trend identification  
- **Linear Regression**: Statistical analysis for correlation detection

### Trading Strategies
- **Momentum Trading**: Price and volume momentum detection
- **Mean Reversion**: Overbought/oversold condition identification
- **Breakout Trading**: Support/resistance level breakthrough detection
- **Pattern Recognition**: Technical chart pattern identification

### Technical Indicators
- **RSI**: Relative Strength Index for momentum
- **MACD**: Moving Average Convergence Divergence
- **Bollinger Bands**: Price volatility and mean reversion
- **Moving Averages**: SMA, EMA trend identification

## 📈 Performance Metrics

### Portfolio Analytics
- **Returns**: Total return, daily return, annualized return
- **Risk Metrics**: Sharpe ratio, Sortino ratio, Maximum Drawdown
- **Market Comparison**: Alpha, Beta vs Bitcoin benchmark
- **Risk Management**: Value at Risk (VaR), Expected Shortfall

### Trading Statistics  
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profits to gross losses
- **Average Win/Loss**: Mean profit per winning/losing trade
- **Risk-Reward Ratio**: Average reward per unit of risk

## 🛡️ Risk Management

### Position Sizing
- Maximum position size per asset (default: 10%)
- Portfolio concentration limits
- Dynamic position sizing based on volatility

### Stop Loss & Take Profit
- Automatic stop-loss orders (default: 5%)
- Take-profit targets (default: 10%) 
- Trailing stops for profit protection

### Risk Monitoring
- Real-time portfolio VaR calculation
- Correlation risk analysis
- Maximum drawdown alerts
- Emergency liquidation triggers

## 🔌 API Reference

### WebSocket Endpoints
```javascript
// Main data stream
ws://localhost:8000/ws/main

// Trading interface
ws://localhost:8000/ws/trading

// Portfolio updates  
ws://localhost:8000/ws/portfolio
```

### REST API Endpoints
```http
GET /api/portfolio/{user_id}     # Portfolio analytics
GET /api/market/overview         # Market overview
GET /api/predictions            # AI predictions
POST /api/trading/order         # Place order
GET /api/scanner/signals        # Trading signals
```

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/ -v

# Test coverage
coverage run -m pytest
coverage report

# Test specific module
python -m pytest tests/test_prediction_engine.py -v
```

## 📝 Development

### Project Structure
```
sofia-v2/
├── src/
│   ├── data/                   # Real-time data fetching
│   ├── ml/                     # AI prediction models  
│   ├── trading/                # Trading engines
│   ├── portfolio/              # Portfolio management
│   ├── scanner/                # Market scanning
│   └── web_ui/                 # Web interface
├── tests/                      # Test suites
├── docs/                       # Documentation
└── requirements.txt            # Dependencies
```

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`  
5. Open a Pull Request

## 📋 Requirements

### System Requirements
- Python 3.8+
- 4GB RAM minimum (8GB recommended)
- Internet connection for real-time data

### Python Dependencies
```
fastapi>=0.68.0
uvicorn>=0.15.0
websockets>=10.0
numpy>=1.21.0
pandas>=1.3.0
scikit-learn>=1.0.0
aiohttp>=3.8.0
python-multipart>=0.0.5
jinja2>=3.0.0
```

## 🔒 Security & Disclaimers

### Security Features
- No API keys required for basic functionality
- All trading is paper money (no real funds)
- Rate limiting and request throttling
- Secure WebSocket connections

### Important Disclaimers
⚠️ **This software is for educational and simulation purposes only**
⚠️ **All trading involves risk - past performance does not guarantee future results**
⚠️ **Never invest more than you can afford to lose**
⚠️ **Always do your own research before making trading decisions**

## 📞 Support

- **Documentation**: [Sofia V2 Docs](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/sofia-v2/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/sofia-v2/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **CoinGecko** for providing free crypto market data
- **Binance** for real-time price feeds
- **FastAPI** for the amazing web framework
- **Chart.js** for beautiful charting capabilities

---

<div align="center">

### 🚀 Ready to start AI-powered crypto trading?

**Made with ❤️ by the Sofia V2 Team**

</div>