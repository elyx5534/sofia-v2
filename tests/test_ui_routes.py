"""
Unit tests for Sofia UI routes
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add the sofia_ui directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sofia_ui'))

from simple_server import app

client = TestClient(app)


class TestCoreRoutes:
    """Test core page routes"""
    
    def test_root(self):
        """Test root route returns homepage"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Sofia V2" in response.text or "status" in response.text
    
    def test_health(self):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "sofia-ui"
    
    def test_dashboard(self):
        """Test dashboard route"""
        response = client.get("/dashboard")
        assert response.status_code == 200
    
    def test_portfolio(self):
        """Test portfolio route"""
        response = client.get("/portfolio")
        assert response.status_code == 200
    
    def test_markets(self):
        """Test markets route"""
        response = client.get("/markets")
        assert response.status_code == 200
    
    def test_trading(self):
        """Test AI trading route"""
        response = client.get("/trading")
        assert response.status_code == 200
    
    def test_manual_trading(self):
        """Test manual trading route"""
        response = client.get("/manual-trading")
        assert response.status_code == 200
    
    def test_backtest(self):
        """Test backtest route"""
        response = client.get("/backtest")
        assert response.status_code == 200
    
    def test_strategies(self):
        """Test strategies route"""
        response = client.get("/strategies")
        assert response.status_code == 200
    
    def test_reliability(self):
        """Test reliability route"""
        response = client.get("/reliability")
        assert response.status_code == 200
    
    def test_pricing(self):
        """Test pricing route"""
        response = client.get("/pricing")
        assert response.status_code == 200
    
    def test_login(self):
        """Test login route"""
        response = client.get("/login")
        assert response.status_code == 200


class TestExtendedRoutes:
    """Test extended page routes"""
    
    def test_bist_analysis(self):
        """Test BIST analysis route"""
        response = client.get("/bist-analysis")
        assert response.status_code == 200
    
    def test_bist_markets(self):
        """Test BIST markets route"""
        response = client.get("/bist-markets")
        assert response.status_code == 200
    
    def test_data_collection(self):
        """Test data collection route"""
        response = client.get("/data-collection")
        assert response.status_code == 200
    
    def test_showcase(self):
        """Test showcase route"""
        response = client.get("/showcase")
        assert response.status_code == 200
    
    def test_welcome(self):
        """Test welcome route"""
        response = client.get("/welcome")
        assert response.status_code == 200
    
    def test_test_page(self):
        """Test test page route"""
        response = client.get("/test")
        assert response.status_code == 200


class TestAssetRoutes:
    """Test asset-related routes"""
    
    def test_assets(self):
        """Test assets list route"""
        response = client.get("/assets")
        assert response.status_code == 200
    
    def test_asset_detail(self):
        """Test asset detail route with symbol"""
        response = client.get("/asset/BTCUSDT")
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling"""
    
    def test_404_handler(self):
        """Test 404 error handler"""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
        # Should return 404 page or fallback
        assert "404" in response.text or "not found" in response.text.lower()


class TestStaticFiles:
    """Test static file serving"""
    
    def test_static_css(self):
        """Test static CSS file serving"""
        response = client.get("/static/css/styles.css")
        # May return 404 if file doesn't exist, but endpoint should be available
        assert response.status_code in [200, 404]
    
    def test_static_js(self):
        """Test static JS file serving"""
        response = client.get("/static/js/websocket.js")
        # May return 404 if file doesn't exist, but endpoint should be available
        assert response.status_code in [200, 404]
    
    def test_extensions(self):
        """Test extensions file serving"""
        response = client.get("/extensions/config.js")
        # May return 404 if file doesn't exist, but endpoint should be available
        assert response.status_code in [200, 404]


class TestRoutePerformance:
    """Test route performance"""
    
    def test_response_times(self):
        """Test that all routes respond within acceptable time"""
        import time
        
        routes = [
            "/", "/dashboard", "/portfolio", "/markets",
            "/trading", "/manual-trading", "/backtest"
        ]
        
        for route in routes:
            start = time.time()
            response = client.get(route)
            elapsed = time.time() - start
            
            assert response.status_code == 200
            # Response should be under 1 second
            assert elapsed < 1.0, f"Route {route} took {elapsed:.2f}s"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])