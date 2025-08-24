# 🚀 Sofia V2 - Developer Setup Guide

Complete setup guide for Sofia V2 development environment.

## 📋 Prerequisites

### System Requirements
- **Python 3.9+** (Recommended: 3.11)
- **Git** (Latest version)
- **4GB+ RAM** (8GB recommended)
- **2GB+ Storage** for dependencies and data

### Operating System Support
- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Ubuntu 20.04+
- ✅ Other Linux distributions

## 🛠️ Step-by-Step Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/sofia-v2.git
cd sofia-v2
```

### 2. Python Environment Setup

#### Option A: venv (Recommended)
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate
```

#### Option B: conda
```bash
# Create conda environment
conda create -n sofia-v2 python=3.11
conda activate sofia-v2
```

### 3. Install Dependencies
```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies
pip install -r requirements-dev.txt
```

### 4. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration (use your preferred editor)
notepad .env  # Windows
nano .env     # Linux/macOS
```

#### .env Configuration
```bash
# Database
DATABASE_URL=sqlite:///sofia.db

# API Keys (Optional - will use mock data if not provided)
ALPHA_VANTAGE_API_KEY=your_key_here
POLYGON_API_KEY=your_key_here
CRYPTOPANIC_API_KEY=your_key_here

# Trading Configuration
DEFAULT_INITIAL_CAPITAL=10000
MAX_POSITIONS=10
RISK_PER_TRADE=0.02

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/sofia.log
```

### 5. Database Setup
```bash
# Initialize database
python -c "from src.data_hub.models import init_db; init_db()"

# Verify database creation
ls -la *.db  # Should see sofia.db
```

### 6. Verify Installation
```bash
# Run health check
python -c "import src; print('✅ Core modules loaded')"

# Test data fetching
python -c "from src.data_hub.data_fetcher import DataFetcher; df = DataFetcher(); print('✅ Data fetcher ready')"

# Test strategies
python -c "from src.backtester.strategies.sma import SMAStrategy; s = SMAStrategy(); print('✅ Strategies loaded')"
```

## 🧪 Testing Setup

### Run Test Suite
```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_backtester.py

# Run with coverage
coverage run -m pytest
coverage report
coverage html  # Creates htmlcov/ directory
```

### Test Configuration
```bash
# Create test environment file
cp .env.example .env.test

# Run tests with test environment
python -m pytest --env-file=.env.test
```

## 🌐 Web Interface Setup

### Start Development Server
```bash
# Method 1: Direct server start
cd sofia_ui
python server.py

# Method 2: Using uvicorn
uvicorn sofia_ui.server:app --reload --host 127.0.0.1 --port 8000
```

### Verify Web Interface
- **Main Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Backtest Interface**: http://localhost:8000/backtest

## 🔧 Development Tools Setup

### Code Formatting (Black)
```bash
# Install black
pip install black

# Format all Python files
black .

# Check what would be formatted
black --check .
```

### Linting (Flake8)
```bash
# Install flake8
pip install flake8

# Run linting
flake8 src/ tests/

# Configure in setup.cfg
[flake8]
max-line-length = 88
extend-ignore = E203, W503
```

### Type Checking (mypy)
```bash
# Install mypy
pip install mypy

# Run type checking
mypy src/

# Configure in mypy.ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
```

## 🚀 CLI Tools Setup

### Sofia CLI
```bash
# Make CLI executable
chmod +x sofia_cli.py  # Linux/macOS

# Run CLI commands
python sofia_cli.py --help
python sofia_cli.py scan --symbol BTC-USD
python sofia_cli.py backtest --strategy sma_cross
```

### PowerShell Scripts (Windows)
```powershell
# Set execution policy (run as administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run Sofia
.\start_sofia.ps1

# Run with parameters
.\start_sofia.ps1 -Port 8080 -Debug $true
```

### Batch Scripts (Windows)
```cmd
# Quick start
start_sofia.bat

# Development mode
start_sofia_dev.bat
```

## 📊 Data Setup

### Initialize Market Data
```bash
# Fetch initial data (optional)
python -c "
from src.data_hub.data_fetcher import DataFetcher
fetcher = DataFetcher()
# This will create cache directory and initial data files
data = fetcher.fetch_historical('BTC-USD', '2023-01-01', '2024-01-01')
print(f'Downloaded {len(data)} data points')
"
```

### Verify Data Sources
```bash
# Test YFinance
python -c "import yfinance as yf; print(yf.Ticker('BTC-USD').info['regularMarketPrice'])"

# Test CCXT (if configured)
python -c "from src.data_hub.providers.ccxt_provider import CCXTProvider; print('✅ CCXT available')"
```

## 🐛 Troubleshooting

### Common Issues

#### Python Module Not Found
```bash
# Solution 1: Install in development mode
pip install -e .

# Solution 2: Add to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)  # Linux/macOS
set PYTHONPATH=%PYTHONPATH%;%cd%       # Windows
```

#### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000          # macOS/Linux
netstat -ano | find "8000"  # Windows

# Kill process
kill -9 <PID>          # macOS/Linux
taskkill /F /PID <PID> # Windows
```

#### Database Locked
```bash
# Remove database and recreate
rm sofia.db
python -c "from src.data_hub.models import init_db; init_db()"
```

#### SSL Certificate Errors
```bash
# Install certificates (macOS)
/Applications/Python\ 3.11/Install\ Certificates.command

# Disable SSL verification (not recommended for production)
export PYTHONHTTPSVERIFY=0
```

### Performance Optimization

#### Speed up tests
```bash
# Run tests in parallel
pip install pytest-xdist
python -m pytest -n auto
```

#### Optimize data loading
```bash
# Use faster JSON library
pip install orjson

# Enable data caching
echo "ENABLE_CACHE=true" >> .env
```

## 📝 Development Workflow

### Daily Development
```bash
# 1. Update code
git pull origin develop

# 2. Activate environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 3. Install any new dependencies
pip install -r requirements.txt

# 4. Run tests
python -m pytest

# 5. Start development server
cd sofia_ui && python server.py
```

### Before Committing
```bash
# Format code
black .

# Run linting
flake8 src/ tests/

# Run full test suite
python -m pytest

# Check coverage
coverage run -m pytest && coverage report
```

## 🆘 Getting Help

### Resources
- **Documentation**: `/docs` directory
- **API Docs**: http://localhost:8000/docs (when server is running)
- **GitHub Issues**: https://github.com/your-username/sofia-v2/issues
- **GitHub Discussions**: https://github.com/your-username/sofia-v2/discussions

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG  # Linux/macOS
set LOG_LEVEL=DEBUG     # Windows

# Run with debug output
python sofia_cli.py --debug scan
```

### Log Files
```bash
# View recent logs
tail -f logs/sofia.log  # Linux/macOS
Get-Content logs/sofia.log -Wait  # Windows PowerShell
```

## ✅ Verification Checklist

After setup, verify these work:
- [ ] Python imports: `import src`
- [ ] Web interface: http://localhost:8000
- [ ] API docs: http://localhost:8000/docs
- [ ] Tests pass: `python -m pytest`
- [ ] CLI works: `python sofia_cli.py --help`
- [ ] Data fetching: Basic market data retrieval
- [ ] Backtesting: Run sample backtest
- [ ] Database: SQLite file created

🎉 **Setup Complete!** You're ready to develop with Sofia V2!

---

*Need help? Create an issue on GitHub or join our discussions.*