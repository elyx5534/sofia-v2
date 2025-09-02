"""
Smoke test for data fallback chain
"""

import os
import sys
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_datahub_fallback_to_binance():
    """Test that datahub falls back to Binance when yfinance fails"""
    from src.services.datahub import DataHub

    datahub = DataHub()

    # Mock yfinance to fail
    with patch("src.services.datahub.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value.empty = True

        # Mock Binance to succeed
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                [1609459200000, "29000", "29500", "28500", "29200", "1000"]
            ]
            mock_get.return_value = mock_response

            data = datahub.get_ohlcv("BTC/USDT", "1d", "2021-01-01", "2021-01-02")

            # Should have gotten data from Binance
            assert len(data) > 0
            assert isinstance(data[0], list)
            assert len(data[0]) == 6  # timestamp, o, h, l, c, v


def test_datahub_caching():
    """Test that datahub caches data"""
    import tempfile
    from pathlib import Path

    from src.services.datahub import DataHub

    # Use temp directory for cache
    with tempfile.TemporaryDirectory() as tmpdir:
        datahub = DataHub()
        datahub.cache_dir = Path(tmpdir)

        # Mock successful fetch
        test_data = [[1609459200000, 29000, 29500, 28500, 29200, 1000]]

        # Save to cache
        datahub._save_cache("TEST/USDT", "1d", "2021-01-01", "2021-01-02", test_data)

        # Load from cache
        cached = datahub._load_cache("TEST/USDT", "1d", "2021-01-01", "2021-01-02")

        assert cached is not None
        assert len(cached) == 1
        assert cached[0][0] == test_data[0][0]


def test_quotes_api_fallback():
    """Test that quotes API handles fallback gracefully"""
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)

    # Test with a symbol that might not be in yfinance
    response = client.get("/api/quotes/ticker?symbol=RANDOM/USDT")

    # Should handle gracefully
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert "symbol" in data
        assert "price" in data


def test_multiple_source_attempts():
    """Test that multiple sources are attempted"""
    from src.services.datahub import DataHub

    datahub = DataHub()

    with (
        patch("src.services.datahub.DataHub._fetch_yfinance") as mock_yf,
        patch("src.services.datahub.DataHub._fetch_binance") as mock_binance,
        patch("src.services.datahub.DataHub._fetch_coinbase") as mock_cb,
    ):
        # All sources fail
        mock_yf.return_value = []
        mock_binance.return_value = []
        mock_cb.return_value = []

        data = datahub.get_ohlcv("BTC/USDT", "1d", "2021-01-01", "2021-01-02")

        # Should have tried yfinance and Binance at least
        assert mock_yf.called
        assert mock_binance.called

        # Should return empty list when all fail
        assert data == []


if __name__ == "__main__":
    test_datahub_fallback_to_binance()
    test_datahub_caching()
    test_quotes_api_fallback()
    test_multiple_source_attempts()
    print("Fallback chain tests passed!")
