"""Unit tests for DataHub service with mocks."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import pandas as pd
from datetime import datetime


class TestDataHubService:
    """Test DataHub service with all fallback chains."""
    
    @patch('src.services.datahub.requests.get')
    @patch('src.services.datahub.yf.Ticker')
    def test_yfinance_primary_success(self, mock_ticker, mock_requests):
        """Test yfinance as primary source."""
        from src.services.datahub import DataHub
        
        # Mock yfinance response
        mock_history = pd.DataFrame({
            'Open': [50000, 50100, 50200],
            'High': [50500, 50600, 50700],
            'Low': [49500, 49600, 49700],
            'Close': [50200, 50300, 50400],
            'Volume': [1000, 1100, 1200]
        }, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03']))
        
        mock_ticker.return_value.history.return_value = mock_history
        
        hub = DataHub()
        data = hub.get_ohlcv("BTC/USDT", "1d", "2024-01-01", "2024-01-03")
        
        assert len(data) == 3
        assert data[0][1] == 50000  # open
        assert data[0][4] == 50200  # close
        # Verify requests.get not called (yfinance succeeded)
        assert not mock_requests.called
    
    @patch('src.services.datahub.requests.get')
    def test_binance_fallback(self, mock_get):
        """Test Binance fallback when yfinance fails."""
        from src.services.datahub import DataHub
        
        # Mock Binance response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [1704067200000, "42000", "42500", "41500", "42300", "1000"],
            [1704070800000, "42300", "42800", "42200", "42700", "1100"]
        ]
        mock_get.return_value = mock_response
        
        hub = DataHub()
        with patch.object(hub, '_fetch_yfinance', side_effect=Exception("yfinance failed")):
            data = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        
        assert len(data) == 2
        assert data[0][4] == 42300.0  # close price
        assert mock_get.called
        assert "binance.com" in mock_get.call_args[0][0]
    
    @patch('src.services.datahub.requests.get')
    def test_coinbase_fallback(self, mock_get):
        """Test Coinbase fallback when both yfinance and Binance fail."""
        from src.services.datahub import DataHub
        
        # First call for Binance fails
        binance_response = Mock()
        binance_response.status_code = 500
        
        # Second call for Coinbase succeeds
        coinbase_response = Mock()
        coinbase_response.status_code = 200
        coinbase_response.json.return_value = [
            [1704067200, 41500, 42200, 42800, 42000, 1000]  # Coinbase format
        ]
        
        mock_get.side_effect = [binance_response, coinbase_response]
        
        hub = DataHub()
        with patch.object(hub, '_fetch_yfinance', side_effect=Exception("yfinance failed")):
            data = hub.get_ohlcv("BTC/USD", "1h", "2024-01-01", "2024-01-02")
        
        assert len(data) == 1
        assert data[0][1] == 42000.0  # open (Coinbase has different order)
    
    @patch('src.services.datahub.Path.exists')
    @patch('src.services.datahub.pq.read_table')
    def test_cache_hit(self, mock_read, mock_exists):
        """Test cache hit scenario."""
        from src.services.datahub import DataHub
        import pyarrow as pa
        
        # Mock cache exists
        mock_exists.return_value = True
        
        # Mock cached data
        cached_df = pd.DataFrame({
            'timestamp': [1704067200000],
            'open': [50000.0],
            'high': [50500.0],
            'low': [49500.0],
            'close': [50200.0],
            'volume': [1000.0]
        })
        mock_table = pa.Table.from_pandas(cached_df)
        mock_read.return_value = mock_table
        
        hub = DataHub()
        # Mock file age check to indicate fresh cache
        with patch('src.services.datahub.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.fromtimestamp.return_value = datetime(2024, 1, 1, 11, 30, 0)
            
            data = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        
        assert len(data) == 1
        assert data[0][1] == 50000.0
        assert mock_read.called
    
    def test_get_latest_price_with_data(self):
        """Test get_latest_price with available OHLCV data."""
        from src.services.datahub import DataHub
        
        hub = DataHub()
        with patch.object(hub, 'get_ohlcv') as mock_ohlcv:
            mock_ohlcv.return_value = [
                [1704067200000, 50000, 50500, 49500, 50200, 1000],
                [1704070800000, 50200, 50700, 50100, 50500, 1100]
            ]
            
            result = hub.get_latest_price("BTC/USDT")
            
            assert result['symbol'] == "BTC/USDT"
            assert result['price'] == 50500  # Latest close
            assert result['volume'] == 1100
    
    @patch('src.services.datahub.requests.get')
    def test_get_latest_price_fallback_ticker(self, mock_get):
        """Test get_latest_price fallback to ticker API."""
        from src.services.datahub import DataHub
        
        # Mock ticker response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "52000.50"}
        mock_get.return_value = mock_response
        
        hub = DataHub()
        with patch.object(hub, 'get_ohlcv') as mock_ohlcv:
            mock_ohlcv.return_value = []  # No OHLCV data
            
            result = hub.get_latest_price("BTC/USDT")
            
            assert result['symbol'] == "BTC/USDT"
            assert result['price'] == 52000.50
            assert mock_get.called