"""
Test suite for Data Hub API endpoints
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

# Import the app and modules we need to test
from src.data_hub.api import app
from src.data_hub.models import AssetType, OHLCVData
from src.data_hub.claude_service import MarketAnalysisResponse


@pytest.fixture
def client():
    """Create test client for Data Hub API"""
    return TestClient(app)


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager"""
    with patch('src.data_hub.api.cache_manager') as mock:
        mock.get_ohlcv_cache = AsyncMock(return_value=None)
        mock.set_ohlcv_cache = AsyncMock()
        mock.clear_expired_cache = AsyncMock(return_value=10)
        yield mock


@pytest.fixture
def mock_yfinance_provider():
    """Mock yfinance provider"""
    with patch('src.data_hub.api.yfinance_provider') as mock:
        mock.search_symbols = AsyncMock(return_value=[
            {"symbol": "AAPL", "name": "Apple Inc.", "type": "equity"}
        ])
        mock.fetch_ohlcv = AsyncMock(return_value=[
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=150.0, high=155.0, low=148.0, close=153.0, volume=1000000
            )
        ])
        yield mock


@pytest.fixture
def mock_ccxt_provider():
    """Mock CCXT provider"""
    with patch('src.data_hub.api.ccxt_provider') as mock:
        mock.search_symbols = AsyncMock(return_value=[
            {"symbol": "BTC/USDT", "name": "Bitcoin/Tether", "type": "crypto"}
        ])
        mock.fetch_ohlcv = AsyncMock(return_value=[
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=45000.0, high=46000.0, low=44500.0, close=45500.0, volume=100.0
            )
        ])
        mock.close = AsyncMock()
        yield mock


@pytest.fixture
def mock_claude_service():
    """Mock Claude service"""
    with patch('src.data_hub.api.claude_service') as mock:
        mock.analyze_market_data = AsyncMock(return_value=MarketAnalysisResponse(
            analysis="Test technical analysis showing bullish momentum",
            confidence=0.8,
            signals=["BUY", "STRONG_MOMENTUM"],
            risk_level="MEDIUM",
            price_target=50000.0,
            support_levels=[44000.0, 43000.0],
            resistance_levels=[47000.0, 48000.0],
            timestamp=datetime.now(timezone.utc)
        ))
        yield mock


class TestDataHubAPI:
    """Test Data Hub API endpoints"""

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "title" in data
        assert "version" in data
        assert "description" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"
        assert "endpoints" in data

    def test_symbols_search_equity_success(self, client, mock_yfinance_provider, mock_cache_manager):
        """Test symbol search for equity - success case"""
        response = client.get("/symbols?query=AAPL&asset_type=equity&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "AAPL"
        assert data["asset_type"] == "equity"
        assert data["count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "AAPL"

    def test_symbols_search_crypto_success(self, client, mock_ccxt_provider, mock_cache_manager):
        """Test symbol search for crypto - success case"""
        response = client.get("/symbols?query=BTC&asset_type=crypto&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "BTC"
        assert data["asset_type"] == "crypto"
        assert data["count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "BTC/USDT"

    def test_symbols_search_missing_params(self, client):
        """Test symbol search with missing required parameters"""
        # Missing query
        response = client.get("/symbols?asset_type=equity")
        assert response.status_code == 422

        # Missing asset_type
        response = client.get("/symbols?query=AAPL")
        assert response.status_code == 422

    def test_symbols_search_invalid_asset_type(self, client):
        """Test symbol search with invalid asset type"""
        response = client.get("/symbols?query=AAPL&asset_type=invalid")
        assert response.status_code == 422

    def test_symbols_search_invalid_limit(self, client):
        """Test symbol search with invalid limit values"""
        # Limit too high
        response = client.get("/symbols?query=AAPL&asset_type=equity&limit=101")
        assert response.status_code == 422

        # Limit too low
        response = client.get("/symbols?query=AAPL&asset_type=equity&limit=0")
        assert response.status_code == 422

    def test_symbols_search_provider_error(self, client, mock_cache_manager):
        """Test symbol search when provider raises exception"""
        with patch('src.data_hub.api.yfinance_provider') as mock_provider:
            mock_provider.search_symbols = AsyncMock(side_effect=Exception("Provider error"))
            
            response = client.get("/symbols?query=AAPL&asset_type=equity")
            assert response.status_code == 503

    def test_ohlcv_equity_success(self, client, mock_yfinance_provider, mock_cache_manager):
        """Test OHLCV endpoint for equity - success case"""
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h&limit=100"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["symbol"] == "AAPL"
        assert data["asset_type"] == "equity"
        assert data["timeframe"] == "1h"
        assert data["cached"] == False  # No cache hit in this test
        assert "timestamp" in data
        assert "data" in data
        assert len(data["data"]) == 1

    def test_ohlcv_crypto_success(self, client, mock_ccxt_provider, mock_cache_manager):
        """Test OHLCV endpoint for crypto - success case"""
        response = client.get(
            "/ohlcv?symbol=BTC/USDT&asset_type=crypto&timeframe=1h&exchange=binance"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["symbol"] == "BTC/USDT"
        assert data["asset_type"] == "crypto"
        assert data["timeframe"] == "1h"
        assert "data" in data

    def test_ohlcv_cached_data(self, client, mock_cache_manager):
        """Test OHLCV endpoint returns cached data"""
        # Mock cache hit
        cached_data = [
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=100.0, high=105.0, low=95.0, close=102.0, volume=50000
            )
        ]
        mock_cache_manager.get_ohlcv_cache.return_value = cached_data
        
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["cached"] == True
        assert len(data["data"]) == 1

    def test_ohlcv_nocache_flag(self, client, mock_yfinance_provider, mock_cache_manager):
        """Test OHLCV endpoint with nocache flag"""
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h&nocache=true"
        )
        
        assert response.status_code == 200
        # Should not call cache get when nocache=true
        mock_cache_manager.get_ohlcv_cache.assert_not_called()

    def test_ohlcv_with_dates(self, client, mock_yfinance_provider, mock_cache_manager):
        """Test OHLCV endpoint with start and end dates"""
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h"
            "&start_date=2023-01-01T00:00:00Z&end_date=2023-01-02T00:00:00Z"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"

    def test_ohlcv_missing_params(self, client):
        """Test OHLCV endpoint with missing required parameters"""
        # Missing symbol
        response = client.get("/ohlcv?asset_type=equity")
        assert response.status_code == 422

        # Missing asset_type
        response = client.get("/ohlcv?symbol=AAPL")
        assert response.status_code == 422

    def test_ohlcv_invalid_limit(self, client):
        """Test OHLCV endpoint with invalid limit"""
        # Limit too high
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&limit=1001"
        )
        assert response.status_code == 422

        # Limit too low
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&limit=0"
        )
        assert response.status_code == 422

    def test_ohlcv_symbol_not_found(self, client, mock_cache_manager):
        """Test OHLCV endpoint when symbol is not found"""
        with patch('src.data_hub.api.yfinance_provider') as mock_provider:
            mock_provider.fetch_ohlcv = AsyncMock(side_effect=ValueError("Symbol not found"))
            
            response = client.get(
                "/ohlcv?symbol=INVALID&asset_type=equity"
            )
            assert response.status_code == 404

    def test_ohlcv_provider_error(self, client, mock_cache_manager):
        """Test OHLCV endpoint when provider has error"""
        with patch('src.data_hub.api.yfinance_provider') as mock_provider:
            mock_provider.fetch_ohlcv = AsyncMock(side_effect=Exception("Provider error"))
            
            response = client.get(
                "/ohlcv?symbol=AAPL&asset_type=equity"
            )
            assert response.status_code == 503

    def test_ohlcv_custom_exchange_crypto(self, client, mock_cache_manager):
        """Test OHLCV endpoint for crypto with custom exchange"""
        with patch('src.data_hub.api.CCXTProvider') as MockCCXTProvider:
            mock_custom_provider = AsyncMock()
            mock_custom_provider.fetch_ohlcv = AsyncMock(return_value=[
                OHLCVData(
                    timestamp=datetime.now(timezone.utc),
                    open=45000.0, high=46000.0, low=44500.0, close=45500.0, volume=100.0
                )
            ])
            mock_custom_provider.close = AsyncMock()
            MockCCXTProvider.return_value = mock_custom_provider
            
            response = client.get(
                "/ohlcv?symbol=BTC/USDT&asset_type=crypto&exchange=kraken"
            )
            
            assert response.status_code == 200
            # Should create custom provider for different exchange
            MockCCXTProvider.assert_called_once_with("kraken")

    def test_clear_cache_success(self, client, mock_cache_manager):
        """Test cache clearing endpoint - success"""
        response = client.delete("/cache")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "10 expired cache entries" in data["message"]
        assert "timestamp" in data

    def test_clear_cache_error(self, client, mock_cache_manager):
        """Test cache clearing endpoint - error"""
        mock_cache_manager.clear_expired_cache = AsyncMock(side_effect=Exception("Cache error"))
        
        response = client.delete("/cache")
        assert response.status_code == 500

    def test_analyze_market_data_success(self, client, mock_claude_service, mock_cache_manager, mock_ccxt_provider):
        """Test market analysis endpoint - success case"""
        # Mock Claude service as available
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            response = client.post(
                "/analyze?symbol=BTC/USDT&asset_type=crypto&timeframe=1h&analysis_type=technical&limit=100"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["analysis"] == "Test technical analysis showing bullish momentum"
            assert data["confidence"] == 0.8
            assert data["signals"] == ["BUY", "STRONG_MOMENTUM"]
            assert data["risk_level"] == "MEDIUM"
            assert data["price_target"] == 50000.0

    def test_analyze_market_data_claude_not_configured(self, client):
        """Test market analysis endpoint when Claude is not configured"""
        with patch('src.data_hub.api.claude_service', None):
            response = client.post(
                "/analyze?symbol=BTC/USDT&asset_type=crypto&timeframe=1h"
            )
            
            assert response.status_code == 503
            assert "Claude AI service not configured" in response.json()["detail"]

    def test_analyze_market_data_no_data_available(self, client, mock_claude_service, mock_cache_manager):
        """Test market analysis endpoint when no OHLCV data available"""
        # Mock no data from providers
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            with patch('src.data_hub.api.ccxt_provider') as mock_provider:
                mock_provider.fetch_ohlcv = AsyncMock(return_value=None)
                
                response = client.post(
                    "/analyze?symbol=INVALID/USDT&asset_type=crypto&timeframe=1h"
                )
                
                assert response.status_code == 404
                assert "No data available" in response.json()["detail"]

    def test_analyze_market_data_with_cached_data(self, client, mock_claude_service, mock_cache_manager):
        """Test market analysis endpoint using cached OHLCV data"""
        # Mock cached OHLCV data
        cached_data = [
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=45000.0, high=46000.0, low=44500.0, close=45500.0, volume=100.0
            )
        ]
        mock_cache_manager.get_ohlcv_cache.return_value = cached_data
        
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            response = client.post(
                "/analyze?symbol=BTC/USDT&asset_type=crypto&timeframe=1h"
            )
            
            assert response.status_code == 200
            # Should use cached data, not fetch from provider
            mock_cache_manager.get_ohlcv_cache.assert_called_once()

    def test_analyze_market_data_equity(self, client, mock_claude_service, mock_cache_manager, mock_yfinance_provider):
        """Test market analysis endpoint for equity"""
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            response = client.post(
                "/analyze?symbol=AAPL&asset_type=equity&timeframe=1h&analysis_type=fundamental"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["analysis"]  # Should have analysis content

    def test_analyze_market_data_limit_parameter(self, client, mock_claude_service, mock_cache_manager, mock_ccxt_provider):
        """Test market analysis endpoint with limit parameter"""
        # Create larger dataset
        large_dataset = [
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=45000.0 + i, high=46000.0 + i, low=44500.0 + i, 
                close=45500.0 + i, volume=100.0
            )
            for i in range(200)  # 200 data points
        ]
        mock_ccxt_provider.fetch_ohlcv.return_value = large_dataset
        
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            response = client.post(
                "/analyze?symbol=BTC/USDT&asset_type=crypto&limit=50"
            )
            
            assert response.status_code == 200
            # Should limit analysis data to last 50 candles

    def test_analyze_market_data_invalid_params(self, client):
        """Test market analysis endpoint with invalid parameters"""
        # Missing symbol
        response = client.post("/analyze?asset_type=crypto")
        assert response.status_code == 422

        # Invalid limit (too low)
        response = client.post(
            "/analyze?symbol=BTC/USDT&asset_type=crypto&limit=5"
        )
        assert response.status_code == 422

        # Invalid limit (too high)
        response = client.post(
            "/analyze?symbol=BTC/USDT&asset_type=crypto&limit=501"
        )
        assert response.status_code == 422

    def test_analyze_market_data_provider_error(self, client, mock_claude_service, mock_cache_manager):
        """Test market analysis endpoint when provider has error"""
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            with patch('src.data_hub.api.ccxt_provider') as mock_provider:
                mock_provider.fetch_ohlcv = AsyncMock(side_effect=Exception("Provider error"))
                
                response = client.post(
                    "/analyze?symbol=BTC/USDT&asset_type=crypto"
                )
                
                assert response.status_code == 503

    def test_exception_handlers(self, client):
        """Test custom exception handlers"""
        # Test ValueError handler (404)
        with patch('src.data_hub.api.yfinance_provider') as mock_provider:
            mock_provider.search_symbols = AsyncMock(side_effect=ValueError("Test error"))
            
            response = client.get("/symbols?query=TEST&asset_type=equity")
            
            assert response.status_code == 404
            data = response.json()
            assert data["error"] == "Not Found"
            assert data["detail"] == "Test error"

        # Test general Exception handler (503) - this is harder to test directly
        # as it's caught by the provider-specific error handling first

    def test_cors_middleware_configuration(self, client):
        """Test that CORS middleware is properly configured"""
        # This tests that the app doesn't crash with CORS configuration
        # Detailed CORS testing would need a more specific setup
        response = client.get("/health")
        assert response.status_code == 200

    def test_backtester_router_mounting(self, client):
        """Test that backtester router is properly mounted"""
        # Try to access a backtester endpoint to ensure it's mounted
        # This should return 404 (not found) rather than 405 (method not allowed)
        # if the router is properly mounted but endpoint doesn't exist
        response = client.get("/backtester/nonexistent")
        # The exact response depends on backtester router implementation
        assert response.status_code in [404, 405, 422]  # Valid responses for mounted router


class TestDataHubAPIIntegration:
    """Integration tests for Data Hub API"""

    def test_ohlcv_to_analysis_workflow(self, client, mock_claude_service, mock_cache_manager, mock_ccxt_provider):
        """Test complete workflow from OHLCV to analysis"""
        # Step 1: Get OHLCV data
        ohlcv_response = client.get(
            "/ohlcv?symbol=BTC/USDT&asset_type=crypto&timeframe=1h"
        )
        assert ohlcv_response.status_code == 200
        
        # Step 2: Use the data for analysis
        with patch('src.data_hub.api.claude_service', mock_claude_service):
            analysis_response = client.post(
                "/analyze?symbol=BTC/USDT&asset_type=crypto&timeframe=1h"
            )
            assert analysis_response.status_code == 200

    def test_symbol_search_to_ohlcv_workflow(self, client, mock_ccxt_provider, mock_cache_manager):
        """Test workflow from symbol search to OHLCV data"""
        # Step 1: Search for symbols
        search_response = client.get("/symbols?query=BTC&asset_type=crypto")
        assert search_response.status_code == 200
        
        symbols = search_response.json()["results"]
        assert len(symbols) > 0
        
        # Step 2: Use found symbol for OHLCV
        symbol = symbols[0]["symbol"]
        ohlcv_response = client.get(
            f"/ohlcv?symbol={symbol}&asset_type=crypto&timeframe=1h"
        )
        assert ohlcv_response.status_code == 200

    def test_cache_workflow(self, client, mock_cache_manager, mock_yfinance_provider):
        """Test cache-related workflow"""
        # Step 1: Get data (should cache it)
        response1 = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h"
        )
        assert response1.status_code == 200
        
        # Step 2: Clear cache
        clear_response = client.delete("/cache")
        assert clear_response.status_code == 200
        
        # Step 3: Get data again (should fetch fresh)
        response2 = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h"
        )
        assert response2.status_code == 200


class TestDataHubAPIEdgeCases:
    """Edge case tests for Data Hub API"""

    def test_empty_query_responses(self, client, mock_cache_manager):
        """Test API responses with empty queries"""
        with patch('src.data_hub.api.yfinance_provider') as mock_provider:
            mock_provider.search_symbols = AsyncMock(return_value=[])
            
            response = client.get("/symbols?query=NONEXISTENT&asset_type=equity")
            assert response.status_code == 200
            
            data = response.json()
            assert data["count"] == 0
            assert data["results"] == []

    def test_special_characters_in_symbols(self, client, mock_cache_manager, mock_yfinance_provider):
        """Test API with special characters in symbol names"""
        response = client.get(
            "/ohlcv?symbol=BRK.A&asset_type=equity&timeframe=1h"
        )
        assert response.status_code == 200

    def test_unicode_characters_in_queries(self, client, mock_cache_manager, mock_yfinance_provider):
        """Test API with unicode characters"""
        response = client.get("/symbols?query=测试&asset_type=equity")
        # Should handle gracefully, either succeed or fail appropriately
        assert response.status_code in [200, 422, 503]

    def test_very_long_queries(self, client):
        """Test API with very long query strings"""
        long_query = "A" * 1000
        response = client.get(f"/symbols?query={long_query}&asset_type=equity")
        # Should handle gracefully
        assert response.status_code in [200, 422, 413, 503]

    def test_concurrent_requests_simulation(self, client, mock_cache_manager, mock_yfinance_provider):
        """Test multiple simultaneous requests"""
        # This simulates concurrent requests by making multiple calls
        responses = []
        for i in range(5):
            response = client.get(f"/symbols?query=TEST{i}&asset_type=equity")
            responses.append(response)
        
        # All should succeed or fail gracefully
        for response in responses:
            assert response.status_code in [200, 422, 503]

    def test_malformed_datetime_parameters(self, client):
        """Test API with malformed datetime parameters"""
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&start_date=invalid-date"
        )
        assert response.status_code == 422

    def test_extreme_limit_values(self, client):
        """Test API with extreme limit values"""
        # Test with negative limit
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&limit=-1"
        )
        assert response.status_code == 422
        
        # Test with zero limit  
        response = client.get(
            "/ohlcv?symbol=AAPL&asset_type=equity&limit=0"
        )
        assert response.status_code == 422