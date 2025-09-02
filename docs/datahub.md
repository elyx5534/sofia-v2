# DataHub Documentation

## Overview
DataHub is the single source of truth for all market data in Sofia V2. It provides a unified interface with automatic fallback across multiple data sources.

## Features
- **Multi-source fallback**: yfinance → Binance → Coinbase → Stooq
- **Intelligent caching**: 24-hour TTL with Parquet storage
- **Symbol normalization**: Automatic format conversion
- **Rate limit handling**: Built-in retry logic
- **Type safety**: Full type hints

## Usage

### Basic OHLCV Fetch
```python
from src.services.datahub import DataHub

hub = DataHub()
candles = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-07")
print(f"Got {len(candles)} candles")
```

### With Symbol Registry
```python
from src.services.symbols import symbol_registry
from src.services.datahub import DataHub

# Parse any symbol format
asset = symbol_registry.parse("BTC/USDT@BINANCE")
hub = DataHub()
data = hub.get_ohlcv(str(asset), "1d", "2024-01-01", "2024-01-31")
```

### Fallback Chain Example
```python
# If yfinance fails, automatically tries Binance
data = hub.get_ohlcv("ETH/USDT", "1h", "2024-01-01", "2024-01-02")
# Logs will show: "yfinance failed: ...", "Trying Binance..."
```

## Data Sources

| Source | Symbols | Timeframes | Notes |
|--------|---------|------------|-------|
| yfinance | Stocks, Crypto, Forex | 1m-1mo | Free, reliable |
| Binance | Crypto (USDT pairs) | 1m-1M | Rate limited |
| Coinbase | Major crypto | 1m-1d | Good for USD pairs |
| Stooq | BIST stocks | 1d | Turkish market data |

## Configuration

Environment variables:
- `DATAHUB_CACHE_DIR`: Cache directory (default: `.cache/ohlcv`)
- `DATAHUB_CACHE_TTL`: Cache TTL in hours (default: 24)
- `DATAHUB_TIMEOUT`: Request timeout in seconds (default: 10)

## Quick Verify

```powershell
# Test DataHub with different symbols
python -c "from src.services.datahub import DataHub; h = DataHub(); print(len(h.get_ohlcv('BTC/USDT', '1h', '2024-01-01', '2024-01-02')))"

# Check cache is working
python -c "import os; print('Cache OK' if os.path.exists('.cache/ohlcv') else 'No cache')"

# Test fallback chain
python -c "import os; os.environ['FORCE_FALLBACK'] = '1'; from src.services.datahub import DataHub; DataHub().get_ohlcv('XXX/YYY', '1h', '2024-01-01', '2024-01-02')"
```
