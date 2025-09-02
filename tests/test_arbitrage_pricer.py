"""
Test Arbitrage Pricer
"""

from unittest.mock import patch

import pytest
from src.trading.arbitrage_pricer import ArbitragePricer


class TestArbitragePricer:
    @pytest.fixture
    def pricer(self):
        """Create pricer instance"""
        with patch("src.trading.arbitrage_pricer.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            return ArbitragePricer()

    @pytest.fixture
    def sample_orderbook(self):
        """Sample orderbook data"""
        return {
            "bids": [[108000, 0.5], [107990, 1.0], [107980, 1.5]],
            "asks": [[108010, 0.5], [108020, 1.0], [108030, 1.5]],
        }

    def test_calculate_vwap_buy(self, pricer):
        """Test VWAP calculation for buy orders"""
        orderbook = [[100, 1.0], [101, 2.0], [102, 3.0]]

        # Buy 2.5 units
        vwap, amount = pricer.calculate_vwap(orderbook, 2.5, "buy")

        # Expected: 1.0 @ 100 + 1.5 @ 101 = 251.5 / 2.5 = 100.6
        assert abs(vwap - 100.6) < 0.01
        assert amount == 2.5

    def test_calculate_vwap_insufficient_depth(self, pricer):
        """Test VWAP with insufficient depth"""
        orderbook = [[100, 1.0], [101, 0.5]]

        # Try to buy 3 units (only 1.5 available)
        vwap, amount = pricer.calculate_vwap(orderbook, 3.0, "buy")

        # Should return what's available
        assert amount == 1.5
        assert abs(vwap - (100 * 1.0 + 101 * 0.5) / 1.5) < 0.01

    def test_get_effective_price_buy(self, pricer, sample_orderbook):
        """Test effective price calculation for buy"""
        result = pricer.get_effective_price(
            "binance", sample_orderbook, 1.0, "buy", use_maker=False
        )

        assert result["raw_price"] == 108010
        # VWAP will be higher since we need to buy from multiple levels
        assert result["vwap_price"] >= 108010
        assert result["fee_pct"] == 0.10  # Taker fee
        assert result["slippage_bps"] >= 0  # May have slippage
        assert result["effective_price"] > result["vwap_price"]  # Includes fee

    def test_get_effective_price_sell(self, pricer, sample_orderbook):
        """Test effective price calculation for sell"""
        result = pricer.get_effective_price(
            "btcturk", sample_orderbook, 1.0, "sell", use_maker=False
        )

        assert result["raw_price"] == 108000
        # VWAP will be lower since we need to sell to multiple levels
        assert result["vwap_price"] <= 108000
        assert result["fee_pct"] == 0.12  # BTCTurk taker fee
        assert result["effective_price"] < result["vwap_price"]  # Fee deducted

    def test_calculate_arbitrage_profit_profitable(self, pricer):
        """Test profitable arbitrage calculation"""
        binance_book = {"asks": [[40000, 10]], "bids": [[39990, 10]]}  # Buy BTC at $40k

        btcturk_book = {"bids": [[1400000, 10]], "asks": [[1400100, 10]]}  # Sell BTC at 1.4M TL

        fx_rate = 34.0  # USDTRY

        result = pricer.calculate_arbitrage_profit(binance_book, btcturk_book, 1000, fx_rate)

        # With these prices, should be profitable
        assert "profitable" in result
        assert "profit_pct" in result
        assert "spread_bps" in result

    def test_calculate_arbitrage_no_depth(self, pricer):
        """Test arbitrage with no depth"""
        binance_book = {"asks": [], "bids": []}
        btcturk_book = {"asks": [], "bids": []}

        result = pricer.calculate_arbitrage_profit(binance_book, btcturk_book, 1000, 34.0)

        assert result["profitable"] == False
        assert "reason" in result

    def test_find_optimal_size(self, pricer):
        """Test optimal size finding"""
        binance_book = {"asks": [[40000, 0.1], [40010, 0.2], [40020, 0.5]]}

        btcturk_book = {"bids": [[1400000, 0.1], [1399000, 0.2], [1398000, 0.5]]}

        result = pricer.find_optimal_size(binance_book, btcturk_book, 34.0, max_size=5000)

        assert "optimal_size" in result
        assert "expected_profit" in result
        assert result["optimal_size"] <= 5000

    def test_get_depth_analysis(self, pricer, sample_orderbook):
        """Test depth analysis"""
        analysis = pricer.get_depth_analysis(sample_orderbook)

        assert "bid" in analysis
        assert "ask" in analysis
        assert "spread_bps" in analysis

        # Check bid levels
        assert len(analysis["bid"]["levels"]) == 3
        assert analysis["bid"]["levels"][0]["price"] == 108000

        # Check ask levels
        assert len(analysis["ask"]["levels"]) == 3
        assert analysis["ask"]["levels"][0]["price"] == 108010

        # Check spread
        expected_spread = ((108010 - 108000) / 108000) * 10000
        assert abs(analysis["spread_bps"] - expected_spread) < 0.1

    def test_maker_vs_taker_fees(self, pricer, sample_orderbook):
        """Test difference between maker and taker fees"""
        maker_result = pricer.get_effective_price(
            "binance", sample_orderbook, 1.0, "buy", use_maker=True
        )

        taker_result = pricer.get_effective_price(
            "binance", sample_orderbook, 1.0, "buy", use_maker=False
        )

        # Both should have same VWAP
        assert maker_result["vwap_price"] == taker_result["vwap_price"]

        # Maker should have same or lower fee
        assert maker_result["fee_pct"] <= taker_result["fee_pct"]

        # Effective price should be better for maker
        assert maker_result["effective_price"] <= taker_result["effective_price"]
