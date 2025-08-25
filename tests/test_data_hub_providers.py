"""
Test suite for Data Hub providers (CCXT, YFinance, Multi-source)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import pandas as pd

from src.data_hub.providers.ccxt_provider import CCXTProvider
from src.data_hub.providers.yfinance_provider import YFinanceProvider
from src.data_hub.providers.multi_source import MultiSourceDataProvider
from src.data_hub.models import OHLCVData


class TestCCXTProvider:
    """Test CCXT Provider"""

    @pytest.fixture
    def provider(self):
        """Create CCXT provider instance"""
        return CCXTProvider(exchange='binance')

    @pytest.fixture
    def mock_exchange(self):
        """Mock CCXT exchange"""
        mock_exchange = MagicMock()
        mock_exchange.id = 'binance'
        mock_exchange.has = {
            'fetchOHLCV': True,
            'fetchTicker': True,
            'fetchTickers': True
        }
        mock_exchange.timeframes = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w', '1M': '1M'
        }
        mock_exchange.load_markets = AsyncMock()
        mock_exchange.close = AsyncMock()
        return mock_exchange

    def test_provider_initialization_default(self):
        """Test provider initialization with default exchange"""
        provider = CCXTProvider()
        assert provider.exchange_id == 'binance'  # Default exchange

    def test_provider_initialization_custom(self):
        """Test provider initialization with custom exchange"""
        provider = CCXTProvider('kraken')
        assert provider.exchange_id == 'kraken'

    @pytest.mark.asyncio
    async def test_get_exchange(self, provider, mock_exchange):
        """Test exchange initialization"""
        with patch('ccxt.binance', return_value=mock_exchange):
            exchange = await provider._get_exchange()
            assert exchange == mock_exchange
            mock_exchange.load_markets.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_symbols_success(self, provider, mock_exchange):
        """Test symbol search - success"""
        mock_exchange.markets = {
            'BTC/USDT': {'symbol': 'BTC/USDT', 'base': 'BTC', 'quote': 'USDT'},
            'ETH/USDT': {'symbol': 'ETH/USDT', 'base': 'ETH', 'quote': 'USDT'},
            'ADA/USDT': {'symbol': 'ADA/USDT', 'base': 'ADA', 'quote': 'USDT'}
        }
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            results = await provider.search_symbols('BTC', limit=10)
            
            assert len(results) == 1
            assert results[0]['symbol'] == 'BTC/USDT'
            assert results[0]['type'] == 'crypto'

    @pytest.mark.asyncio
    async def test_search_symbols_multiple_matches(self, provider, mock_exchange):
        """Test symbol search with multiple matches"""
        mock_exchange.markets = {
            'BTC/USDT': {'symbol': 'BTC/USDT', 'base': 'BTC', 'quote': 'USDT'},
            'BTC/EUR': {'symbol': 'BTC/EUR', 'base': 'BTC', 'quote': 'EUR'},
            'BTCUP/USDT': {'symbol': 'BTCUP/USDT', 'base': 'BTCUP', 'quote': 'USDT'}
        }
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            results = await provider.search_symbols('BTC', limit=10)
            
            assert len(results) >= 2  # Should find BTC/USDT and BTC/EUR
            symbols = [r['symbol'] for r in results]
            assert 'BTC/USDT' in symbols
            assert 'BTC/EUR' in symbols

    @pytest.mark.asyncio
    async def test_search_symbols_with_limit(self, provider, mock_exchange):
        """Test symbol search with limit"""
        mock_exchange.markets = {
            f'BTC/USDT{i}': {'symbol': f'BTC/USDT{i}', 'base': 'BTC', 'quote': f'USDT{i}'}
            for i in range(20)
        }
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            results = await provider.search_symbols('BTC', limit=5)
            
            assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_symbols_no_matches(self, provider, mock_exchange):
        """Test symbol search with no matches"""
        mock_exchange.markets = {
            'BTC/USDT': {'symbol': 'BTC/USDT', 'base': 'BTC', 'quote': 'USDT'}
        }
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            results = await provider.search_symbols('NONEXISTENT', limit=10)
            
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success(self, provider, mock_exchange):
        """Test OHLCV data fetching - success"""
        # Mock OHLCV data [timestamp, open, high, low, close, volume]
        mock_ohlcv = [
            [1640995200000, 47000.0, 48000.0, 46500.0, 47500.0, 100.5],
            [1640998800000, 47500.0, 48500.0, 47000.0, 48000.0, 95.2]
        ]
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            result = await provider.fetch_ohlcv(
                symbol='BTC/USDT',
                timeframe='1h',
                limit=100
            )
            
            assert len(result) == 2
            assert isinstance(result[0], OHLCVData)
            assert result[0].open == 47000.0
            assert result[0].high == 48000.0
            assert result[0].close == 47500.0

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_with_dates(self, provider, mock_exchange):
        """Test OHLCV data fetching with date range"""
        mock_ohlcv = [
            [1640995200000, 47000.0, 48000.0, 46500.0, 47500.0, 100.5]
        ]
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
        
        start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 1, 2, tzinfo=timezone.utc)
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            result = await provider.fetch_ohlcv(
                symbol='BTC/USDT',
                timeframe='1h',
                start_date=start_date,
                end_date=end_date
            )
            
            mock_exchange.fetch_ohlcv.assert_called_once()
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_invalid_symbol(self, provider, mock_exchange):
        """Test OHLCV data fetching with invalid symbol"""
        mock_exchange.fetch_ohlcv = AsyncMock(side_effect=Exception("Symbol not found"))
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            with pytest.raises(ValueError, match="Failed to fetch OHLCV data"):
                await provider.fetch_ohlcv(
                    symbol='INVALID/PAIR',
                    timeframe='1h'
                )

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_empty_data(self, provider, mock_exchange):
        """Test OHLCV data fetching with empty response"""
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            result = await provider.fetch_ohlcv(
                symbol='BTC/USDT',
                timeframe='1h'
            )
            
            assert result == []

    @pytest.mark.asyncio
    async def test_close_provider(self, provider, mock_exchange):
        """Test provider cleanup"""
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            # Initialize exchange
            await provider._get_exchange()
            
            # Close provider
            await provider.close()
            
            mock_exchange.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeframe_validation(self, provider, mock_exchange):
        """Test timeframe validation"""
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])
        
        with patch.object(provider, '_get_exchange', return_value=mock_exchange):
            # Valid timeframe
            await provider.fetch_ohlcv('BTC/USDT', '1h')
            
            # Invalid timeframe should still work (let exchange handle it)
            await provider.fetch_ohlcv('BTC/USDT', '3h')


class TestYFinanceProvider:
    """Test YFinance Provider"""

    @pytest.fixture
    def provider(self):
        """Create YFinance provider instance"""
        return YFinanceProvider()

    @pytest.mark.asyncio
    async def test_search_symbols_success(self, provider):
        """Test symbol search - success"""
        mock_results = pd.DataFrame({
            'symbol': ['AAPL', 'AAPLW'],
            'shortname': ['Apple Inc.', 'Apple Inc. Warrant'],
            'longname': ['Apple Inc.', 'Apple Inc. Warrant'],
            'quoteType': ['EQUITY', 'WARRANT']
        })
        
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.get_shares_full = MagicMock(return_value=mock_results)
            mock_ticker.return_value = mock_ticker_instance
            
            with patch('pandas.DataFrame.empty', False):
                results = await provider.search_symbols('AAPL', limit=10)
                
                assert len(results) >= 1
                assert any(r['symbol'] == 'AAPL' for r in results)

    @pytest.mark.asyncio
    async def test_search_symbols_no_results(self, provider):
        """Test symbol search with no results"""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.get_shares_full = MagicMock(return_value=pd.DataFrame())
            mock_ticker.return_value = mock_ticker_instance
            
            results = await provider.search_symbols('NONEXISTENT', limit=10)
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_symbols_fallback(self, provider):
        """Test symbol search fallback mechanism"""
        # First attempt fails, fallback succeeds
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.get_shares_full = MagicMock(side_effect=Exception("API Error"))
            mock_ticker.return_value = mock_ticker_instance
            
            with patch.object(provider, '_fallback_search', return_value=[
                {'symbol': 'AAPL', 'name': 'Apple Inc.', 'type': 'equity'}
            ]):
                results = await provider.search_symbols('AAPL', limit=10)
                assert len(results) == 1
                assert results[0]['symbol'] == 'AAPL'

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success(self, provider):
        """Test OHLCV data fetching - success"""
        mock_data = pd.DataFrame({
            'Open': [150.0, 151.0],
            'High': [155.0, 156.0], 
            'Low': [148.0, 149.0],
            'Close': [153.0, 154.0],
            'Volume': [1000000, 1100000]
        }, index=pd.DatetimeIndex([
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2022, 1, 2, tzinfo=timezone.utc)
        ]))
        
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history = MagicMock(return_value=mock_data)
            mock_ticker.return_value = mock_ticker_instance
            
            result = await provider.fetch_ohlcv(
                symbol='AAPL',
                timeframe='1d',
                limit=100
            )
            
            assert len(result) == 2
            assert isinstance(result[0], OHLCVData)
            assert result[0].open == 150.0
            assert result[0].close == 153.0

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_with_dates(self, provider):
        """Test OHLCV data fetching with date range"""
        mock_data = pd.DataFrame({
            'Open': [150.0], 'High': [155.0], 'Low': [148.0],
            'Close': [153.0], 'Volume': [1000000]
        }, index=pd.DatetimeIndex([datetime(2022, 1, 1, tzinfo=timezone.utc)]))
        
        start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2022, 1, 2, tzinfo=timezone.utc)
        
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history = MagicMock(return_value=mock_data)
            mock_ticker.return_value = mock_ticker_instance
            
            result = await provider.fetch_ohlcv(
                symbol='AAPL',
                timeframe='1d',
                start_date=start_date,
                end_date=end_date
            )
            
            assert len(result) == 1
            mock_ticker_instance.history.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_invalid_symbol(self, provider):
        """Test OHLCV data fetching with invalid symbol"""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history = MagicMock(return_value=pd.DataFrame())
            mock_ticker.return_value = mock_ticker_instance
            
            with pytest.raises(ValueError, match="No data found for symbol"):
                await provider.fetch_ohlcv('INVALID', '1d')

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_api_error(self, provider):
        """Test OHLCV data fetching with API error"""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history = MagicMock(side_effect=Exception("API Error"))
            mock_ticker.return_value = mock_ticker_instance
            
            with pytest.raises(ValueError, match="Failed to fetch data"):
                await provider.fetch_ohlcv('AAPL', '1d')

    @pytest.mark.asyncio
    async def test_timeframe_mapping(self, provider):
        """Test timeframe mapping from API format to yfinance format"""
        mock_data = pd.DataFrame({
            'Open': [150.0], 'High': [155.0], 'Low': [148.0],
            'Close': [153.0], 'Volume': [1000000]
        }, index=pd.DatetimeIndex([datetime(2022, 1, 1, tzinfo=timezone.utc)]))
        
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.history = MagicMock(return_value=mock_data)
            mock_ticker.return_value = mock_ticker_instance
            
            # Test various timeframe mappings
            timeframes = ['1d', '1h', '5m', '15m', '30m', '1w', '1M']
            
            for tf in timeframes:
                result = await provider.fetch_ohlcv('AAPL', tf)
                assert len(result) == 1

    def test_fallback_search(self, provider):
        """Test fallback search method"""
        results = provider._fallback_search('AAPL')
        
        # Should return common stock symbols
        assert len(results) > 0
        assert any(r['symbol'] == 'AAPL' for r in results)

    def test_clean_symbol_name(self, provider):
        """Test symbol name cleaning utility"""
        test_cases = [
            ('Apple Inc.', 'Apple Inc.'),
            ('Microsoft Corporation (MSFT)', 'Microsoft Corporation'),
            ('Test Company - Class A', 'Test Company'),
            ('', 'Unknown'),
            (None, 'Unknown')
        ]
        
        for input_name, expected in test_cases:
            result = provider._clean_symbol_name(input_name)
            assert result == expected


class TestMultiSourceProvider:
    """Test Multi-source Provider"""

    @pytest.fixture
    def provider(self):
        """Create multi-source provider instance"""
        return MultiSourceDataProvider()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_success(self, provider):
        """Test OHLCV fetching - success case"""
        with patch('pandas.DataFrame') as mock_df:
            mock_data = MagicMock()
            mock_data.empty = False
            mock_df.return_value = mock_data
            
            with patch.object(provider, '_fetch_yfinance_async', return_value=mock_data) as mock_yf:
                result = await provider.fetch_ohlcv_async('AAPL', '1d')
                
                assert result is not None
                mock_yf.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_crypto_fallback(self, provider):
        """Test OHLCV fetching with crypto fallback"""
        with patch('pandas.DataFrame') as mock_df:
            mock_data = MagicMock()
            mock_data.empty = False
            mock_df.return_value = mock_data
            
            with patch.object(provider, '_fetch_ccxt_async', return_value=mock_data) as mock_ccxt:
                result = await provider.fetch_ohlcv_async('BTC/USDT', '1h')
                
                assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_all_sources_fail(self, provider):
        """Test OHLCV fetching when all sources fail"""
        with patch.object(provider, '_fetch_yfinance_async', side_effect=Exception("API Error")):
            with patch.object(provider, '_fetch_ccxt_async', side_effect=Exception("API Error")):
                result = await provider.fetch_ohlcv_async('INVALID', '1d')
                
                assert result is None

    def test_symbol_conversion_yfinance(self, provider):
        """Test symbol conversion for yfinance"""
        # Crypto symbol
        result = provider._convert_symbol('BTC/USDT', provider.crypto_sources[0])
        assert result == 'BTC/USDT' or result == 'BTC-USD'
        
        # Stock symbol
        result = provider._convert_symbol('AAPL', provider.stock_sources[0])
        assert result == 'AAPL'

    def test_timeframe_conversion(self, provider):
        """Test timeframe conversion"""
        # Test yfinance conversion
        result = provider._convert_timeframe('1w', provider.stock_sources[0])
        assert result in ['1w', '1wk']
        
        # Test CCXT conversion (should remain same)
        result = provider._convert_timeframe('1h', provider.crypto_sources[0])
        assert result == '1h'

    def test_get_available_symbols(self, provider):
        """Test getting available symbols"""
        symbols = provider.get_available_symbols(provider.stock_sources[0])
        assert isinstance(symbols, list)
        assert len(symbols) > 0

    def test_connection_test_yfinance(self, provider):
        """Test connection test for yfinance"""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = {'symbol': 'AAPL'}
            mock_ticker.return_value = mock_ticker_instance
            
            result = provider.test_connection(provider.stock_sources[0])
            assert result == True

    def test_connection_test_failure(self, provider):
        """Test connection test failure"""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker.side_effect = Exception("Connection error")
            
            result = provider.test_connection(provider.stock_sources[0])
            assert result == False

    def test_source_status(self, provider):
        """Test getting source status"""
        with patch.object(provider, 'test_connection', return_value=True):
            status = provider.get_source_status()
            
            assert isinstance(status, dict)
            assert len(status) > 0
            
            # Check that all DataSource values are present
            from src.data_hub.providers.multi_source import DataSource
            for source in DataSource:
                assert source.value in status

    def test_synchronous_wrapper(self, provider):
        """Test synchronous wrapper for async methods"""
        with patch.object(provider, 'fetch_ohlcv_async', return_value=None):
            result = provider.fetch_ohlcv('TEST', '1d')
            assert result is None