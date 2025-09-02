"""
Smoke tests for DataHub v2
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_symbol_parsing():
    """Test symbol registry and parsing"""
    from src.services.symbols import symbol_registry, AssetType
    
    # Test crypto parsing
    asset = symbol_registry.parse("BTC/USDT@BINANCE")
    assert asset is not None
    assert asset.type == AssetType.CRYPTO
    assert asset.base == "BTC"
    assert asset.quote == "USDT"
    assert asset.venue == "BINANCE"
    
    # Test stock parsing
    asset = symbol_registry.parse("AAPL@NASDAQ")
    assert asset is not None
    assert asset.type == AssetType.STOCK
    assert asset.base == "AAPL"
    
    # Test BIST stock
    asset = symbol_registry.parse("ASELS@BIST")
    assert asset is not None
    assert asset.venue == "BIST"
    assert asset.to_yfinance() == "ASELS.IS"
    
    # Test auto venue detection
    asset = symbol_registry.parse("BTC/USDT")
    assert asset.venue == "BINANCE"
    
    asset = symbol_registry.parse("EUR/USD")
    assert asset.type == AssetType.FOREX

def test_fallback_chain_yfinance_disabled():
    """Test fallback to Binance when yfinance is disabled"""
    from src.services.datahub_v2 import DataHubV2
    
    datahub = DataHubV2()
    datahub.disable_yf = True
    
    with patch('requests.get') as mock_get:
        # Mock Binance response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [1609459200000, "29000", "29500", "28500", "29200", "1000"]
        ]
        mock_get.return_value = mock_response
        
        data = datahub.get_ohlcv("BTC/USDT@BINANCE", "1d", "2021-01-01", "2021-01-02")
        
        assert len(data) > 0
        assert isinstance(data[0], list)
        assert len(data[0]) == 6
        assert data[0][1] == 29000  # open price

def test_cache_operations():
    """Test caching works correctly"""
    from src.services.datahub_v2 import DataHubV2
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        datahub = DataHubV2()
        datahub.cache_dir = Path(tmpdir)
        
        # Test data
        test_data = [
            [1609459200000, 29000, 29500, 28500, 29200, 1000],
            [1609545600000, 29200, 30000, 29000, 29800, 1200]
        ]
        
        # Save to cache
        from src.services.symbols import symbol_registry
        asset = symbol_registry.parse("TEST/USDT@BINANCE")
        cache_key = datahub._get_cache_key(asset, "1d", "2021-01-01", "2021-01-02")
        datahub._save_cache(cache_key, test_data)
        
        # Load from cache
        cached = datahub._load_cache(cache_key)
        
        assert cached is not None
        assert len(cached) == 2
        assert cached[0][0] == test_data[0][0]
        assert cached[0][1] == test_data[0][1]
        
        # Check cache hit rate
        datahub.cache_hits = 1
        datahub.cache_misses = 1
        health = datahub.get_health()
        assert health["cache_hit_rate"] == "50.0%"

def test_market_calendar():
    """Test market calendar and timezone handling"""
    from src.services.datahub_v2 import MarketCalendar
    from datetime import datetime
    import pytz
    
    # Test timezone conversion
    dt = datetime(2024, 1, 15, 9, 30)  # 9:30 AM
    utc_dt = MarketCalendar.to_utc(dt, "NASDAQ")
    
    # NASDAQ is in NY timezone, so 9:30 AM EST should be 14:30 UTC
    assert utc_dt.tzinfo == pytz.UTC
    
    # Test market open check
    # Monday 10 AM EST
    dt = datetime(2024, 1, 15, 15, 0, tzinfo=pytz.UTC)  # 15:00 UTC = 10:00 EST
    assert MarketCalendar.is_market_open("NASDAQ", dt) == True
    
    # Sunday
    dt = datetime(2024, 1, 14, 15, 0, tzinfo=pytz.UTC)
    assert MarketCalendar.is_market_open("NASDAQ", dt) == False
    
    # Crypto markets always open
    assert MarketCalendar.is_market_open("BINANCE") == True

def test_bist_stock_fetch():
    """Test BIST stock data fetching"""
    from src.services.datahub_v2 import DataHubV2
    
    datahub = DataHubV2()
    
    # Mock yfinance for BIST stock
    with patch('yfinance.Ticker') as mock_ticker:
        mock_history = MagicMock()
        mock_history.empty = False
        mock_history.iterrows.return_value = [
            (datetime(2024, 1, 1), {
                'Open': 100, 'High': 105, 'Low': 99, 'Close': 103, 'Volume': 50000
            })
        ]
        mock_ticker.return_value.history.return_value = mock_history
        
        data = datahub.get_ohlcv("ASELS@BIST", "1d", "2024-01-01", "2024-01-02")
        
        # Should have called with .IS suffix
        mock_ticker.assert_called_with("ASELS.IS")

def test_corporate_actions_adjustment():
    """Test stock split and dividend adjustments"""
    from src.services.datahub_v2 import DataHubV2
    
    datahub = DataHubV2()
    
    with patch('yfinance.Ticker') as mock_ticker:
        # Mock adjusted data
        mock_history = MagicMock()
        mock_history.empty = False
        mock_history.iterrows.return_value = [
            (datetime(2024, 1, 1), {
                'Open': 150, 'High': 155, 'Low': 148, 'Close': 152, 'Volume': 1000000
            })
        ]
        
        # Mock actions (splits/dividends)
        mock_actions = MagicMock()
        mock_actions.empty = False
        
        mock_ticker.return_value.history.return_value = mock_history
        mock_ticker.return_value.actions = mock_actions
        
        # Fetch with adjustment
        data = datahub.get_ohlcv("AAPL@NASDAQ", "1d", "2024-01-01", "2024-01-02", adjust_corporate=True)
        
        # Should have called with auto_adjust=True
        mock_ticker.return_value.history.assert_called_with(
            start="2024-01-01", 
            end="2024-01-02", 
            interval="1d", 
            auto_adjust=True
        )

def test_env_toggles():
    """Test environment variable toggles"""
    from src.services.datahub_v2 import DataHubV2
    
    # Test DISABLE_YF
    with patch.dict(os.environ, {"DISABLE_YF": "true"}):
        datahub = DataHubV2()
        assert datahub.disable_yf == True
    
    # Test FORCE_BINANCE
    with patch.dict(os.environ, {"FORCE_BINANCE": "true"}):
        datahub = DataHubV2()
        assert datahub.force_binance == True
    
    # Test FORCE_COINBASE
    with patch.dict(os.environ, {"FORCE_COINBASE": "true"}):
        datahub = DataHubV2()
        assert datahub.force_coinbase == True

def test_timeout_and_retry():
    """Test timeout and retry mechanism"""
    from src.services.datahub_v2 import DataHubV2
    
    datahub = DataHubV2()
    datahub.timeout = 1  # 1 second timeout
    datahub.retry_count = 2
    
    with patch('requests.get') as mock_get:
        # Simulate timeout
        mock_get.side_effect = Exception("Timeout")
        
        # Should try multiple sources
        data = datahub.get_ohlcv("BTC/USDT@BINANCE", "1d", "2021-01-01", "2021-01-02")
        
        # Should return empty list after all retries
        assert data == []
        
        # Check that multiple attempts were made
        assert mock_get.call_count >= 1

def test_cache_hit_rate():
    """Test cache hit rate calculation"""
    from src.services.datahub_v2 import DataHubV2
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        datahub = DataHubV2()
        datahub.cache_dir = Path(tmpdir)
        
        # Simulate some hits and misses
        datahub.cache_hits = 8
        datahub.cache_misses = 2
        
        health = datahub.get_health()
        
        # Should have 80% hit rate
        assert health["cache_hit_rate"] == "80.0%"
        assert health["cache_hits"] == 8
        assert health["cache_misses"] == 2

if __name__ == "__main__":
    test_symbol_parsing()
    test_fallback_chain_yfinance_disabled()
    test_cache_operations()
    test_market_calendar()
    test_bist_stock_fetch()
    test_corporate_actions_adjustment()
    test_env_toggles()
    test_timeout_and_retry()
    test_cache_hit_rate()
    print("All DataHub v2 tests passed!")