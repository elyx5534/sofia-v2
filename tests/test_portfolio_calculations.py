"""
Unit tests for portfolio calculations and Total Balance
"""
import pytest
from decimal import Decimal
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.api.portfolio_endpoints import calculate_total_balance


class TestTotalBalanceCalculation:
    """Test Total Balance calculation with various scenarios"""
    
    def test_single_currency_calculation(self):
        """Test TB calculation with single currency (USD)"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "50000.00",
            "fees_accrued": "100.00",
            "positions": [
                {
                    "symbol": "AAPL",
                    "qty": "100",
                    "mark_price": "150.50",
                    "currency": "USD"
                }
            ],
            "fx_rates": {}
        }
        
        # TB = 50000 + (100 * 150.50) - 100 = 50000 + 15050 - 100 = 64950
        result = calculate_total_balance(summary)
        assert result == "64950.00"
    
    def test_multi_currency_with_fx(self):
        """Test TB with multiple currencies and FX conversion"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "50000.00",
            "fees_accrued": "125.50",
            "positions": [
                {
                    "symbol": "BTCUSDT",
                    "qty": "0.5",
                    "mark_price": "67500.00",
                    "currency": "USDT"
                },
                {
                    "symbol": "ETHUSDT",
                    "qty": "10",
                    "mark_price": "3200.00",
                    "currency": "USDT"
                }
            ],
            "fx_rates": {
                "USDTUSD": "1.00"
            }
        }
        
        # Position values:
        # BTC: 0.5 * 67500 = 33750 USDT = 33750 USD
        # ETH: 10 * 3200 = 32000 USDT = 32000 USD
        # TB = 50000 + 33750 + 32000 - 125.50 = 115624.50
        result = calculate_total_balance(summary)
        assert result == "115624.50"
    
    def test_negative_pnl_positions(self):
        """Test TB with positions that have negative value"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "100000.00",
            "fees_accrued": "500.00",
            "positions": [
                {
                    "symbol": "LOSS",
                    "qty": "1000",
                    "mark_price": "5.00",
                    "currency": "USD"
                }
            ],
            "fx_rates": {}
        }
        
        # TB = 100000 + (1000 * 5) - 500 = 100000 + 5000 - 500 = 104500
        result = calculate_total_balance(summary)
        assert result == "104500.00"
    
    def test_zero_positions(self):
        """Test TB with no positions"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "75000.00",
            "fees_accrued": "0.00",
            "positions": [],
            "fx_rates": {}
        }
        
        # TB = 75000 + 0 - 0 = 75000
        result = calculate_total_balance(summary)
        assert result == "75000.00"
    
    def test_high_fees_impact(self):
        """Test TB with significant fees"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "50000.00",
            "fees_accrued": "5000.00",
            "positions": [
                {
                    "symbol": "TEST",
                    "qty": "100",
                    "mark_price": "100.00",
                    "currency": "USD"
                }
            ],
            "fx_rates": {}
        }
        
        # TB = 50000 + (100 * 100) - 5000 = 50000 + 10000 - 5000 = 55000
        result = calculate_total_balance(summary)
        assert result == "55000.00"
    
    def test_decimal_precision(self):
        """Test TB calculation maintains precision with small decimals"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "12345.67",
            "fees_accrued": "0.05",
            "positions": [
                {
                    "symbol": "PRECISE",
                    "qty": "0.12345678",
                    "mark_price": "9876.54321",
                    "currency": "USD"
                }
            ],
            "fx_rates": {}
        }
        
        # Position value: 0.12345678 * 9876.54321 = 1219.32631
        # TB = 12345.67 + 1219.33 - 0.05 = 13564.95
        result = calculate_total_balance(summary)
        # Should round to 2 decimal places
        expected = Decimal("12345.67") + (Decimal("0.12345678") * Decimal("9876.54321")) - Decimal("0.05")
        expected_str = str(expected.quantize(Decimal("0.01")))
        assert result == expected_str
    
    def test_fx_conversion_with_multiple_rates(self):
        """Test TB with complex FX conversions"""
        summary = {
            "base_currency": "USD",
            "cash_balance": "10000.00",
            "fees_accrued": "50.00",
            "positions": [
                {
                    "symbol": "EURSTOCK",
                    "qty": "50",
                    "mark_price": "100.00",
                    "currency": "EUR"
                }
            ],
            "fx_rates": {
                "EURUSD": "1.08"
            }
        }
        
        # Position value: 50 * 100 = 5000 EUR
        # In USD: 5000 * 1.08 = 5400 USD
        # TB = 10000 + 5400 - 50 = 15350
        result = calculate_total_balance(summary)
        assert result == "15350.00"


class TestPortfolioAPIContract:
    """Test the portfolio API contract structure"""
    
    def test_portfolio_summary_structure(self):
        """Test that portfolio summary has all required fields"""
        from src.api.portfolio_endpoints import PortfolioSummary
        
        summary = PortfolioSummary(
            base_currency="USD",
            cash_balance="50000.00",
            fees_accrued="100.00",
            positions=[],
            fx_rates={}
        )
        
        assert summary.base_currency == "USD"
        assert summary.cash_balance == "50000.00"
        assert summary.fees_accrued == "100.00"
        assert summary.positions == []
        assert summary.fx_rates == {}
        assert summary.timestamp is not None
    
    def test_position_structure(self):
        """Test that position has all required fields"""
        from src.api.portfolio_endpoints import Position
        
        position = Position(
            symbol="BTCUSDT",
            qty="0.5",
            mark_price="67500.00",
            currency="USDT"
        )
        
        assert position.symbol == "BTCUSDT"
        assert position.qty == "0.5"
        assert position.mark_price == "67500.00"
        assert position.currency == "USDT"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])