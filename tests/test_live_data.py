"""
Sofia V2 Live Data Service Tests
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Sofia UI modülünü import edebilmek için path ekle
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'sofia_ui'))

from live_data import LiveDataService

class TestLiveDataService:
    """Live Data Service testleri"""
    
    def setup_method(self):
        """Her test için yeni service instance"""
        self.service = LiveDataService()
    
    def test_service_initialization(self):
        """Servis doğru başlatılıyor mu"""
        assert self.service.cache == {}
        assert self.service.cache_duration == 60
    
    def test_format_volume(self):
        """Volume formatlamayı test et"""
        assert self.service._format_volume(1000) == "1.0K"
        assert self.service._format_volume(1000000) == "1.0M"
        assert self.service._format_volume(1000000000) == "1.0B"
        assert self.service._format_volume(1000000000000) == "1.0T"
        assert self.service._format_volume(500) == "500"
    
    def test_fallback_data_btc(self):
        """BTC fallback verisi"""
        data = self.service._get_fallback_data("BTC-USD")
        assert data["symbol"] == "BTC-USD"
        assert data["name"] == "Bitcoin"
        assert "price" in data
        assert "change" in data
        assert "last_updated" in data
    
    def test_fallback_data_unknown_symbol(self):
        """Bilinmeyen sembol için fallback"""
        data = self.service._get_fallback_data("UNKNOWN-SYMBOL")
        assert data["symbol"] == "UNKNOWN-SYMBOL"
        assert data["price"] == 100.0  # Default price
        assert "last_updated" in data
    
    def test_fallback_fear_greed(self):
        """Fear & Greed fallback"""
        data = self.service._get_fallback_fear_greed()
        assert data["value"] == 72
        assert data["value_classification"] == "Greed"
        assert "timestamp" in data
    
    def test_fallback_crypto_data(self):
        """Crypto market fallback"""
        data = self.service._get_fallback_crypto_data()
        assert "total_market_cap" in data
        assert "total_volume" in data
        assert "btc_dominance" in data
        assert "market_cap_change_24h" in data
    
    def test_cache_functionality(self):
        """Cache mekanizması"""
        # Cache boş
        assert not self.service._is_cached("test_key")
        
        # Veri cache'le
        test_data = {"test": "data"}
        self.service._cache_data("test_key", test_data)
        
        # Cache'de var mı kontrol et
        assert self.service._is_cached("test_key")
        assert self.service.cache["test_key"]["data"] == test_data
    
    @patch('yfinance.Ticker')
    def test_get_live_price_success(self, mock_ticker):
        """Başarılı fiyat çekme"""
        # Mock setup
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        # Mock history data
        import pandas as pd
        mock_history = pd.DataFrame({
            'Close': [50000, 51000],
            'Volume': [1000000, 1100000]
        })
        mock_instance.history.return_value = mock_history
        
        # Mock info data
        mock_instance.info = {
            'longName': 'Bitcoin',
            'marketCap': 1000000000000,
            'currency': 'USD',
            'sector': 'Cryptocurrency'
        }
        
        # Test
        result = self.service.get_live_price("BTC-USD")
        
        assert result["symbol"] == "BTC-USD"
        assert result["name"] == "Bitcoin"
        assert result["price"] == 51000
        assert result["change"] == 1000
        assert result["change_percent"] == 2.0  # (1000/50000)*100
    
    @patch('yfinance.Ticker')
    def test_get_live_price_failure(self, mock_ticker):
        """Başarısız fiyat çekme - fallback kullanılmalı"""
        # Mock to raise exception
        mock_ticker.side_effect = Exception("API Error")
        
        result = self.service.get_live_price("BTC-USD")
        
        # Fallback data dönmeli
        assert result["symbol"] == "BTC-USD"
        assert "price" in result
        assert "last_updated" in result
    
    @patch('yfinance.Tickers')
    def test_get_multiple_prices(self, mock_tickers):
        """Çoklu fiyat çekme"""
        # Mock setup
        mock_instance = MagicMock()
        mock_tickers.return_value = mock_instance
        
        # Mock ticker instances
        mock_btc = MagicMock()
        mock_eth = MagicMock()
        
        import pandas as pd
        mock_btc.history.return_value = pd.DataFrame({
            'Close': [50000, 51000]
        })
        mock_eth.history.return_value = pd.DataFrame({
            'Close': [3000, 3100]
        })
        
        mock_instance.tickers = {
            'BTC-USD': mock_btc,
            'ETH-USD': mock_eth
        }
        
        # Test
        result = self.service.get_multiple_prices(['BTC-USD', 'ETH-USD'])
        
        assert 'BTC-USD' in result
        assert 'ETH-USD' in result
        assert result['BTC-USD']['price'] == 51000
        assert result['ETH-USD']['price'] == 3100
    
    @patch('requests.get')
    def test_get_crypto_fear_greed_success(self, mock_get):
        """Fear & Greed Index başarılı çekme"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [{
                'value': '75',
                'value_classification': 'Greed',
                'timestamp': '1640995200'
            }]
        }
        mock_get.return_value = mock_response
        
        result = self.service.get_crypto_fear_greed_index()
        
        assert result['value'] == 75
        assert result['value_classification'] == 'Greed'
        assert 'last_updated' in result
    
    @patch('requests.get')
    def test_get_crypto_fear_greed_failure(self, mock_get):
        """Fear & Greed Index başarısız çekme"""
        mock_get.side_effect = Exception("Network Error")
        
        result = self.service.get_crypto_fear_greed_index()
        
        # Fallback data dönmeli
        assert result['value'] == 72
        assert result['value_classification'] == 'Greed'
    
    @patch('requests.get')
    def test_get_crypto_market_data_success(self, mock_get):
        """Crypto market data başarılı çekme"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'total_market_cap': {'usd': 2000000000000},
                'total_volume': {'usd': 100000000000},
                'market_cap_percentage': {'btc': 55.0},
                'market_cap_change_percentage_24h_usd': 2.5
            }
        }
        mock_get.return_value = mock_response
        
        result = self.service._get_crypto_market_data()
        
        assert result['total_market_cap'] == 2000000000000
        assert result['btc_dominance'] == 55.0
        assert result['market_cap_change_24h'] == 2.5
    
    def test_get_market_summary(self):
        """Market summary testi"""
        with patch.object(self.service, 'get_multiple_prices') as mock_prices, \
             patch.object(self.service, '_get_crypto_market_data') as mock_crypto:
            
            mock_prices.return_value = {'BTC-USD': {'price': 50000}}
            mock_crypto.return_value = {'total_market_cap': 2000000000000}
            
            result = self.service.get_market_summary()
            
            assert 'indices' in result
            assert 'crypto' in result
            assert 'last_updated' in result

if __name__ == "__main__":
    pytest.main([__file__])
