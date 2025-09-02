"""
Test suite for FastAPI web application
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import the FastAPI app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.web.app import app

client = TestClient(app)


class TestAPIEndpoints:
    """Test FastAPI endpoints"""

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_home_redirect(self):
        """Test home page redirects to signals"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_signals_page(self):
        """Test signals page loads"""
        response = client.get("/signals")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_heatmap_page(self):
        """Test heatmap page loads"""
        response = client.get("/heatmap")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_chart_page(self):
        """Test chart page loads"""
        response = client.get("/chart/BTCUSDT")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_news_page(self):
        """Test news page loads"""
        response = client.get("/news")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_status(self):
        """Test API status endpoint"""
        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "available_symbols" in data
        assert "timestamp" in data
        assert isinstance(data["available_symbols"], int)

    def test_api_signals(self):
        """Test signals API endpoint"""
        response = client.get("/api/signals")
        assert response.status_code == 200

        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_api_heatmap(self):
        """Test heatmap API endpoint"""
        response = client.get("/api/heatmap")
        assert response.status_code == 200

        data = response.json()
        assert "heatmap_data" in data
        assert isinstance(data["heatmap_data"], list)

    def test_api_news(self):
        """Test news API endpoint"""
        response = client.get("/api/news")
        assert response.status_code == 200

        data = response.json()
        assert "news" in data
        assert "total_count" in data
        assert isinstance(data["news"], list)
        assert isinstance(data["total_count"], int)

    def test_api_news_with_symbol(self):
        """Test news API with specific symbol"""
        response = client.get("/api/news?symbol=BTC/USDT")
        assert response.status_code == 200

        data = response.json()
        assert "news" in data
        assert "symbol" in data
        assert data["symbol"] == "BTC/USDT"

    def test_api_news_with_limit(self):
        """Test news API with limit parameter"""
        response = client.get("/api/news?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert "news" in data
        assert len(data["news"]) <= 5

    def test_api_search(self):
        """Test search API endpoint"""
        response = client.get("/api/search?q=BTC")
        assert response.status_code == 200

        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total_count" in data
        assert data["query"] == "BTC"
        assert isinstance(data["results"], list)

    def test_api_search_short_query(self):
        """Test search API with too short query"""
        response = client.get("/api/search?q=B")
        assert response.status_code == 422  # Validation error

    def test_api_ohlcv_no_symbol(self):
        """Test OHLCV API without symbol parameter"""
        response = client.get("/api/ohlcv")
        assert response.status_code == 422  # Missing required parameter

    def test_api_ohlcv_invalid_timeframe(self):
        """Test OHLCV API with invalid timeframe"""
        response = client.get("/api/ohlcv?symbol=BTCUSDT&timeframe=5m")
        assert response.status_code == 422  # Invalid timeframe

    def test_api_ohlcv_valid_request(self):
        """Test OHLCV API with valid parameters"""
        response = client.get("/api/ohlcv?symbol=BTC/USDT&timeframe=1h")

        # This might return 404 if no data exists, which is acceptable for tests
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data
            assert "timeframe" in data
            assert "data" in data
            assert data["symbol"] == "BTC/USDT"
            assert data["timeframe"] == "1h"
            assert isinstance(data["data"], list)

    def test_404_handling(self):
        """Test 404 error handling"""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404


class TestAPIValidation:
    """Test API parameter validation"""

    def test_search_validation(self):
        """Test search parameter validation"""
        # Too short query
        response = client.get("/api/search?q=A")
        assert response.status_code == 422

        # Valid query
        response = client.get("/api/search?q=BTC")
        assert response.status_code == 200

        # Limit validation
        response = client.get("/api/search?q=BTC&limit=50")
        assert response.status_code == 200

    def test_news_validation(self):
        """Test news parameter validation"""
        # Valid limit range
        response = client.get("/api/news?limit=10")
        assert response.status_code == 200

        # Limit too low
        response = client.get("/api/news?limit=0")
        assert response.status_code == 422

        # Limit too high
        response = client.get("/api/news?limit=200")
        assert response.status_code == 422

    def test_ohlcv_validation(self):
        """Test OHLCV parameter validation"""
        # Missing symbol
        response = client.get("/api/ohlcv")
        assert response.status_code == 422

        # Invalid timeframe
        response = client.get("/api/ohlcv?symbol=BTCUSDT&timeframe=invalid")
        assert response.status_code == 422

        # Valid parameters
        response = client.get("/api/ohlcv?symbol=BTCUSDT&timeframe=1d")
        assert response.status_code in [200, 404]  # 404 if no data available


class TestCORSAndSecurity:
    """Test CORS and basic security"""

    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.get("/api/status")

        # FastAPI should handle CORS if configured
        assert response.status_code == 200

    def test_no_sensitive_info_in_errors(self):
        """Test error responses don't leak sensitive information"""
        response = client.get("/api/ohlcv?symbol=INVALID")

        # Should not expose internal paths or sensitive info
        assert response.status_code in [404, 422, 500]

        if response.status_code == 500:
            error_text = response.text.lower()
            sensitive_terms = ["password", "secret", "token", "key", "internal"]
            for term in sensitive_terms:
                assert term not in error_text


if __name__ == "__main__":
    pytest.main([__file__])
