"""
Sofia V2 Server Tests
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Sofia UI modülünü import edebilmek için path ekle
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sofia_ui'))

from server import app

client = TestClient(app)

class TestHomepage:
    """Ana sayfa testleri"""
    
    def test_homepage_loads(self):
        """Ana sayfa yükleniyor mu"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Sofia V2" in response.text
        assert "Trading Strategy Platform" in response.text
    
    def test_homepage_contains_btc_data(self):
        """Ana sayfada BTC verisi var mı"""
        response = client.get("/")
        assert response.status_code == 200
        assert "BTC" in response.text or "Bitcoin" in response.text

class TestAssetPages:
    """Asset sayfaları testleri"""
    
    def test_assets_btc_page(self):
        """BTC asset sayfası"""
        response = client.get("/assets/BTC-USD")
        assert response.status_code == 200
        assert "BTC" in response.text
        
    def test_assets_eth_page(self):
        """ETH asset sayfası"""
        response = client.get("/assets/ETH-USD")
        assert response.status_code == 200
        assert "ETH" in response.text

class TestBacktestPage:
    """Backtest sayfası testleri"""
    
    def test_backtest_page_loads(self):
        """Backtest sayfası yükleniyor mu"""
        response = client.get("/backtest")
        assert response.status_code == 200
        assert "Backtest Strategy" in response.text
        assert "Run Backtest" in response.text

class TestStrategiesPage:
    """Stratejiler sayfası testleri"""
    
    def test_strategies_page_loads(self):
        """Stratejiler sayfası yükleniyor mu"""
        response = client.get("/strategies")
        assert response.status_code == 200
        assert "Trading Strategies" in response.text

class TestCardsPage:
    """Cards sayfası testleri"""
    
    def test_cards_page_loads(self):
        """Cards sayfası yükleniyor mu"""
        response = client.get("/cards")
        assert response.status_code == 200
        assert "Strategy Cards" in response.text

class TestAPIEndpoints:
    """API endpoint testleri"""
    
    def test_quote_api_btc(self):
        """BTC fiyat API'si"""
        response = client.get("/api/quote/BTC-USD")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "price" in data
        assert data["symbol"] == "BTC-USD"
    
    def test_quote_api_multiple(self):
        """Çoklu fiyat API'si"""
        response = client.get("/api/quotes?symbols=BTC-USD,ETH-USD")
        assert response.status_code == 200
        data = response.json()
        assert "BTC-USD" in data or len(data) > 0
    
    def test_news_api(self):
        """Haber API'si"""
        response = client.get("/api/news/BTC-USD")
        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert "news" in data
    
    def test_market_summary_api(self):
        """Piyasa özeti API'si"""
        response = client.get("/api/market-summary")
        assert response.status_code == 200
        # API hata verse bile status 200 dönmeli
        
    def test_fear_greed_api(self):
        """Fear & Greed API'si"""
        response = client.get("/api/fear-greed")
        assert response.status_code == 200
        data = response.json()
        assert "value" in data

class TestBacktestAPI:
    """Backtest API testleri"""
    
    def test_backtest_api_post(self):
        """Backtest POST API'si"""
        payload = {
            "symbol": "BTC-USD",
            "strategy": "sma_cross",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31"
        }
        response = client.post("/api/backtest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "results" in data

class TestErrorHandling:
    """Hata yönetimi testleri"""
    
    def test_invalid_page_404(self):
        """Olmayan sayfa 404 döner"""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
    
    def test_invalid_symbol_fallback(self):
        """Geçersiz sembol için fallback"""
        response = client.get("/api/quote/INVALID-SYMBOL")
        assert response.status_code == 200  # Fallback veri dönmeli
        data = response.json()
        assert "symbol" in data

class TestStaticFiles:
    """Static dosya testleri"""
    
    def test_static_css_accessible(self):
        """Static CSS dosyaları erişilebilir"""
        # Bu test static dosya varsa çalışır
        pass  # Skip for now
    
    def test_favicon_request(self):
        """Favicon isteği"""
        response = client.get("/favicon.ico")
        # 404 olabilir, bu normal
        assert response.status_code in [200, 404]

if __name__ == "__main__":
    pytest.main([__file__])
