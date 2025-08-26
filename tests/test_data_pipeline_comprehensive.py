"""
Comprehensive tests for data pipeline and exchanges modules
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import json

@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
    return pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(40000, 50000, 100),
        'high': np.random.uniform(41000, 51000, 100),
        'low': np.random.uniform(39000, 49000, 100),
        'close': np.random.uniform(40000, 50000, 100),
        'volume': np.random.uniform(100, 1000, 100)
    })

class TestDataPipeline:
    """Test data pipeline functionality"""
    
    @patch('src.data.pipeline.ccxt.binance')
    def test_pipeline_initialization(self, mock_exchange):
        """Test data pipeline initialization"""
        from src.data.pipeline import DataPipeline
        
        pipeline = DataPipeline(data_dir="./test_data")
        
        assert pipeline is not None
        assert pipeline.data_dir == Path("./test_data")
        assert pipeline.outputs_dir == Path("./outputs")
    
    @patch('src.data.pipeline.ccxt.binance')
    def test_fetch_ohlcv_success(self, mock_exchange, sample_ohlcv_data):
        """Test successful OHLCV data fetch"""
        from src.data.pipeline import DataPipeline
        
        mock_exchange_instance = MagicMock()
        mock_exchange.return_value = mock_exchange_instance
        mock_exchange_instance.fetch_ohlcv.return_value = [
            [1234567890000, 45000, 46000, 44000, 45500, 100]
        ]
        
        pipeline = DataPipeline()
        df = pipeline.fetch_ohlcv("BTC/USDT", "1h", limit=100)
        
        assert df is not None
        mock_exchange_instance.fetch_ohlcv.assert_called()
    
    @patch('src.data.pipeline.DataPipeline.fetch_ohlcv')
    def test_get_symbol_data(self, mock_fetch, sample_ohlcv_data, tmp_path):
        """Test getting symbol data"""
        from src.data.pipeline import DataPipeline
        
        mock_fetch.return_value = sample_ohlcv_data
        
        pipeline = DataPipeline(data_dir=str(tmp_path))
        
        # First call should fetch
        df = pipeline.get_symbol_data("BTC-USD", "1h")
        assert df is not None
        assert len(df) == 100
        
        # Check if cached file was created
        cached_file = tmp_path / "BTC-USD_1h.parquet"
        assert cached_file.exists()
    
    def test_get_available_symbols(self, tmp_path):
        """Test getting available symbols"""
        from src.data.pipeline import DataPipeline
        
        # Create test files
        (tmp_path / "BTC-USD_1h.parquet").touch()
        (tmp_path / "ETH-USD_1h.parquet").touch()
        (tmp_path / "SOL-USD_1d.parquet").touch()
        
        pipeline = DataPipeline(data_dir=str(tmp_path))
        symbols = pipeline.get_available_symbols()
        
        assert len(symbols) >= 2
        assert "BTC-USD" in symbols
        assert "ETH-USD" in symbols
    
    @patch('src.data.pipeline.DataPipeline.fetch_ohlcv')
    def test_update_recent_data(self, mock_fetch, sample_ohlcv_data):
        """Test updating recent data"""
        from src.data.pipeline import DataPipeline
        
        mock_fetch.return_value = sample_ohlcv_data
        
        pipeline = DataPipeline()
        
        with patch.object(pipeline, 'get_available_symbols', return_value=["BTC-USD", "ETH-USD"]):
            results = pipeline.update_recent_data(hours_back=24)
            
            assert "symbols_updated" in results
            assert results["symbols_updated"] > 0
    
    @patch('src.data.pipeline.DataPipeline.fetch_ohlcv')
    def test_fetch_universe_data(self, mock_fetch, sample_ohlcv_data):
        """Test fetching universe data"""
        from src.data.pipeline import DataPipeline
        
        mock_fetch.return_value = sample_ohlcv_data
        
        pipeline = DataPipeline()
        
        with patch('src.data.pipeline.UNIVERSE_SYMBOLS', ["BTC-USD", "ETH-USD"]):
            results = pipeline.fetch_universe_data(
                timeframes=["1h"],
                days_back=7,
                max_workers=2
            )
            
            assert results is not None

class TestExchanges:
    """Test exchanges module"""
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_exchange_manager_init(self, mock_binance):
        """Test exchange manager initialization"""
        from src.data.exchanges import ExchangeManager
        
        manager = ExchangeManager()
        
        assert manager is not None
        assert hasattr(manager, 'exchanges')
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_get_exchange(self, mock_binance):
        """Test getting exchange instance"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        
        manager = ExchangeManager()
        exchange = manager.get_exchange("binance")
        
        assert exchange is not None
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_fetch_ticker(self, mock_binance):
        """Test fetching ticker data"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.fetch_ticker.return_value = {
            'symbol': 'BTC/USDT',
            'last': 45000,
            'bid': 44990,
            'ask': 45010,
            'volume': 1000
        }
        
        manager = ExchangeManager()
        ticker = manager.fetch_ticker("binance", "BTC/USDT")
        
        assert ticker is not None
        assert ticker['symbol'] == 'BTC/USDT'
        assert ticker['last'] == 45000
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_fetch_order_book(self, mock_binance):
        """Test fetching order book"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.fetch_order_book.return_value = {
            'bids': [[44990, 10], [44980, 20]],
            'asks': [[45010, 10], [45020, 20]],
            'timestamp': 1234567890000
        }
        
        manager = ExchangeManager()
        order_book = manager.fetch_order_book("binance", "BTC/USDT")
        
        assert order_book is not None
        assert len(order_book['bids']) > 0
        assert len(order_book['asks']) > 0
    
    @patch('src.data.exchanges.ccxt')
    def test_list_supported_exchanges(self, mock_ccxt):
        """Test listing supported exchanges"""
        from src.data.exchanges import ExchangeManager
        
        mock_ccxt.exchanges = ['binance', 'coinbase', 'kraken']
        
        manager = ExchangeManager()
        exchanges = manager.list_supported_exchanges()
        
        assert len(exchanges) > 0
        assert 'binance' in exchanges
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_get_markets(self, mock_binance):
        """Test getting markets"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.load_markets.return_value = {
            'BTC/USDT': {'symbol': 'BTC/USDT', 'active': True},
            'ETH/USDT': {'symbol': 'ETH/USDT', 'active': True}
        }
        
        manager = ExchangeManager()
        markets = manager.get_markets("binance")
        
        assert markets is not None
        assert 'BTC/USDT' in markets
    
    @patch('src.data.exchanges.ccxt.binance')
    def test_error_handling(self, mock_binance):
        """Test error handling in exchanges"""
        from src.data.exchanges import ExchangeManager
        
        mock_exchange = MagicMock()
        mock_binance.return_value = mock_exchange
        mock_exchange.fetch_ticker.side_effect = Exception("Network error")
        
        manager = ExchangeManager()
        
        with pytest.raises(Exception) as exc_info:
            manager.fetch_ticker("binance", "BTC/USDT")
        
        assert "Network error" in str(exc_info.value)

class TestDataIntegration:
    """Integration tests for data modules"""
    
    @patch('src.data.pipeline.ccxt.binance')
    @patch('src.data.exchanges.ccxt.binance')
    def test_pipeline_with_exchanges(self, mock_ex_binance, mock_pip_binance):
        """Test data pipeline with exchanges integration"""
        from src.data.pipeline import DataPipeline
        from src.data.exchanges import ExchangeManager
        
        # Setup mocks
        mock_exchange = MagicMock()
        mock_ex_binance.return_value = mock_exchange
        mock_pip_binance.return_value = mock_exchange
        
        mock_exchange.fetch_ohlcv.return_value = [
            [1234567890000, 45000, 46000, 44000, 45500, 100]
        ]
        mock_exchange.fetch_ticker.return_value = {
            'last': 45500,
            'volume': 1000
        }
        
        pipeline = DataPipeline()
        manager = ExchangeManager()
        
        # Fetch data through pipeline
        ohlcv = pipeline.fetch_ohlcv("BTC/USDT", "1h")
        
        # Fetch ticker through manager
        ticker = manager.fetch_ticker("binance", "BTC/USDT")
        
        assert ohlcv is not None
        assert ticker is not None
        assert ticker['last'] == 45500

class TestDataPipelineHelpers:
    """Test data pipeline helper functions"""
    
    def test_normalize_symbol(self):
        """Test symbol normalization"""
        from src.data.pipeline import normalize_symbol
        
        assert normalize_symbol("BTC/USDT") == "BTC-USDT"
        assert normalize_symbol("ETH/USD") == "ETH-USD"
        assert normalize_symbol("BTC-USD") == "BTC-USD"
    
    def test_denormalize_symbol(self):
        """Test symbol denormalization"""
        from src.data.pipeline import denormalize_symbol
        
        assert denormalize_symbol("BTC-USDT") == "BTC/USDT"
        assert denormalize_symbol("ETH-USD") == "ETH/USD"
        assert denormalize_symbol("BTC/USD") == "BTC/USD"
    
    def test_timeframe_to_minutes(self):
        """Test timeframe conversion"""
        from src.data.pipeline import timeframe_to_minutes
        
        assert timeframe_to_minutes("1m") == 1
        assert timeframe_to_minutes("5m") == 5
        assert timeframe_to_minutes("1h") == 60
        assert timeframe_to_minutes("1d") == 1440
        assert timeframe_to_minutes("1w") == 10080