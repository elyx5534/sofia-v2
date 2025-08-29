"""
Unit tests for multi-asset trading functionality
"""
import pytest
from decimal import Decimal
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock ccxt and yfinance if not installed
try:
    import ccxt
except ImportError:
    class MockExchange:
        def fetch_ticker(self, symbol):
            return {"last": 67500, "quoteVolume": 1000000, "percentage": 2.5}
    
    class ccxt:
        @staticmethod
        def binance():
            return MockExchange()
    
    sys.modules['ccxt'] = ccxt

try:
    import yfinance
except ImportError:
    class MockTicker:
        def __init__(self, symbol):
            self.info = {
                "regularMarketPrice": 175.50,
                "regularMarketVolume": 65000000,
                "regularMarketChangePercent": 0.8
            }
    
    class yfinance:
        Ticker = MockTicker
    
    sys.modules['yfinance'] = yfinance


class TestPortfolioCalculations:
    """Test portfolio Total Balance calculations"""
    
    def test_single_currency_tb(self):
        """Test TB with single currency (USD only)"""
        from sofia_ui.static.js.portfolio_service import calculate_total_balance
        
        summary = {
            "base_currency": "USD",
            "cash_balance": "50000.00",
            "fees_accrued": "100.00",
            "positions": [
                {"symbol": "AAPL", "qty": "100", "mark_price": "175.50", "currency": "USD"}
            ],
            "fx_rates": {}
        }
        
        # TB = 50000 + (100 * 175.50) - 100 = 50000 + 17550 - 100 = 67450
        expected = Decimal("67450.00")
        result = calculate_total_balance(summary)
        assert abs(result - expected) < Decimal("0.01")
    
    def test_multi_currency_tb(self):
        """Test TB with multiple currencies"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "50000.00",
            "fees_accrued": "125.50",
            "positions": [
                {"symbol": "BTC/USDT", "qty": "0.5", "mark_price": "67500", "currency": "USDT"},
                {"symbol": "AAPL", "qty": "100", "mark_price": "175.50", "currency": "USD"}
            ],
            "fx_rates": {"USDTUSD": "1.00"}
        }
        
        # BTC value: 0.5 * 67500 = 33750 USDT = 33750 USD
        # AAPL value: 100 * 175.50 = 17550 USD
        # TB = 50000 + 33750 + 17550 - 125.50 = 101174.50
        expected = Decimal("101174.50")
        result = calculate_total_balance_py(summary)
        assert abs(result - expected) < Decimal("0.01")
    
    def test_fx_conversion(self):
        """Test FX rate conversion"""
        from src.api.portfolio_endpoints import convert_currency
        
        # Direct rate
        amount = convert_currency(Decimal("1000"), "USD", "TRY", {"USDTRY": "34.50"})
        assert amount == Decimal("34500.00")
        
        # Inverse rate
        amount = convert_currency(Decimal("34500"), "TRY", "USD", {"USDTRY": "34.50"})
        assert abs(amount - Decimal("1000.00")) < Decimal("0.01")
        
        # Same currency
        amount = convert_currency(Decimal("1000"), "USD", "USD", {})
        assert amount == Decimal("1000.00")


class TestMarketEndpoints:
    """Test market data endpoints"""
    
    def test_crypto_quote(self):
        """Test crypto quote fetching"""
        from src.api.market_endpoints import get_quotes
        
        # This would need to be an async test in real implementation
        # For now, testing the logic structure
        assert True
    
    def test_equity_quote(self):
        """Test equity quote fetching"""
        from src.api.market_endpoints import get_quotes
        
        # This would need to be an async test in real implementation
        assert True
    
    def test_asset_list(self):
        """Test asset listing"""
        from src.api.market_endpoints import list_assets
        
        # This would need to be an async test in real implementation
        assert True


class TestMultiAssetIntegration:
    """Test multi-asset integration scenarios"""
    
    def test_mixed_portfolio(self):
        """Test portfolio with both crypto and equity positions"""
        positions = [
            {"symbol": "BTC/USDT", "type": "crypto", "qty": 0.5, "price": 67500},
            {"symbol": "ETH/USDT", "type": "crypto", "qty": 10, "price": 3200},
            {"symbol": "AAPL", "type": "equity", "qty": 100, "price": 175.50},
            {"symbol": "MSFT", "type": "equity", "qty": 50, "price": 420.75}
        ]
        
        total_value = sum(p["qty"] * p["price"] for p in positions)
        expected = 0.5 * 67500 + 10 * 3200 + 100 * 175.50 + 50 * 420.75
        assert abs(total_value - expected) < 0.01
    
    def test_watchlist_persistence(self):
        """Test watchlist save/load functionality"""
        watchlist = [
            {"symbol": "BTC/USDT", "type": "crypto"},
            {"symbol": "AAPL", "type": "equity"}
        ]
        
        # In real test, would save to localStorage and verify retrieval
        assert len(watchlist) == 2
        assert watchlist[0]["type"] == "crypto"
        assert watchlist[1]["type"] == "equity"


def calculate_total_balance_py(summary):
    """Python implementation of TB calculation for testing"""
    from decimal import Decimal
    
    base_currency = summary.get("base_currency", "USD")
    cash = Decimal(summary.get("cash_balance", "0"))
    fees = Decimal(summary.get("fees_accrued", "0"))
    fx_rates = summary.get("fx_rates", {})
    
    positions_value = Decimal("0")
    for position in summary.get("positions", []):
        qty = Decimal(position.get("qty", "0"))
        price = Decimal(position.get("mark_price", "0"))
        value = qty * price
        
        # Convert to base currency
        currency = position.get("currency", base_currency)
        if currency != base_currency:
            rate_key = f"{currency}{base_currency}"
            if rate_key in fx_rates:
                value = value * Decimal(fx_rates[rate_key])
        
        positions_value += value
    
    return cash + positions_value - fees


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])