from datetime import timezone
"""Tests for the OHLCV endpoint."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.data_hub.api import app
from src.data_hub.models import OHLCVData


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data."""
    base_time = datetime.now(timezone.utc)
    return [
        OHLCVData(
            timestamp=base_time - timedelta(hours=2),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000000.0,
        ),
        OHLCVData(
            timestamp=base_time - timedelta(hours=1),
            open=103.0,
            high=107.0,
            low=102.0,
            close=106.0,
            volume=1200000.0,
        ),
        OHLCVData(
            timestamp=base_time,
            open=106.0,
            high=108.0,
            low=105.0,
            close=107.5,
            volume=900000.0,
        ),
    ]


def test_ohlcv_missing_params(client):
    """Test OHLCV endpoint with missing required parameters."""
    response = client.get("/ohlcv")
    assert response.status_code == 422


def test_ohlcv_invalid_asset_type(client):
    """Test OHLCV endpoint with invalid asset type."""
    response = client.get("/ohlcv?symbol=AAPL&asset_type=invalid")
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
@patch("src.data_hub.api.yfinance_provider.fetch_ohlcv")
@patch("src.data_hub.api.cache_manager.set_ohlcv_cache")
async def test_ohlcv_cache_miss(
    mock_set_cache, mock_fetch, mock_get_cache, client, sample_ohlcv_data
):
    """Test OHLCV endpoint with cache miss."""
    # Setup mocks
    mock_get_cache.return_value = None  # Cache miss
    mock_fetch.return_value = sample_ohlcv_data
    mock_set_cache.return_value = None

    # Make request
    response = client.get("/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h")
    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["asset_type"] == "equity"
    assert data["timeframe"] == "1h"
    assert data["cached"] is False
    assert len(data["data"]) == 3
    assert data["data"][0]["open"] == 100.0


@pytest.mark.asyncio
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
async def test_ohlcv_cache_hit(mock_get_cache, client, sample_ohlcv_data):
    """Test OHLCV endpoint with cache hit."""
    # Setup mock
    mock_get_cache.return_value = sample_ohlcv_data

    # Make request
    response = client.get("/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h")
    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["cached"] is True
    assert len(data["data"]) == 3


@pytest.mark.asyncio
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
@patch("src.data_hub.api.yfinance_provider.fetch_ohlcv")
@patch("src.data_hub.api.cache_manager.set_ohlcv_cache")
async def test_ohlcv_nocache_flag(
    mock_set_cache, mock_fetch, mock_get_cache, client, sample_ohlcv_data
):
    """Test OHLCV endpoint with nocache flag."""
    # Setup mocks
    mock_get_cache.return_value = sample_ohlcv_data  # Cache would hit
    mock_fetch.return_value = sample_ohlcv_data

    # Make request with nocache=true
    response = client.get("/ohlcv?symbol=AAPL&asset_type=equity&timeframe=1h&nocache=true")
    assert response.status_code == 200

    # Check that cache was not checked
    mock_get_cache.assert_not_called()

    # Check response
    data = response.json()
    assert data["cached"] is False


@pytest.mark.asyncio
@patch("src.data_hub.api.ccxt_provider.fetch_ohlcv")
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
@patch("src.data_hub.api.cache_manager.set_ohlcv_cache")
async def test_ohlcv_crypto(mock_set_cache, mock_get_cache, mock_fetch, client, sample_ohlcv_data):
    """Test OHLCV endpoint for crypto assets."""
    # Setup mocks
    mock_get_cache.return_value = None
    mock_fetch.return_value = sample_ohlcv_data

    # Make request
    response = client.get("/ohlcv?symbol=BTC/USDT&asset_type=crypto&timeframe=1h&exchange=binance")
    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["symbol"] == "BTC/USDT"
    assert data["asset_type"] == "crypto"
    assert len(data["data"]) == 3


@pytest.mark.asyncio
@patch("src.data_hub.api.yfinance_provider.fetch_ohlcv")
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
async def test_ohlcv_symbol_not_found(mock_get_cache, mock_fetch, client):
    """Test OHLCV endpoint when symbol is not found."""
    # Setup mocks
    mock_get_cache.return_value = None
    mock_fetch.side_effect = ValueError("Symbol INVALID not found")

    # Make request
    response = client.get("/ohlcv?symbol=INVALID&asset_type=equity")
    assert response.status_code == 404

    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
@patch("src.data_hub.api.yfinance_provider.fetch_ohlcv")
@patch("src.data_hub.api.cache_manager.get_ohlcv_cache")
async def test_ohlcv_provider_error(mock_get_cache, mock_fetch, client):
    """Test OHLCV endpoint when provider raises an error."""
    # Setup mocks
    mock_get_cache.return_value = None
    mock_fetch.side_effect = Exception("Provider timeout")

    # Make request
    response = client.get("/ohlcv?symbol=AAPL&asset_type=equity")
    assert response.status_code == 503

    data = response.json()
    assert "detail" in data
    assert "timeout" in data["detail"].lower()


def test_ohlcv_with_dates(client):
    """Test OHLCV endpoint with date parameters."""
    with patch("src.data_hub.api.cache_manager.get_ohlcv_cache") as mock_cache:
        with patch("src.data_hub.api.yfinance_provider.fetch_ohlcv") as mock_fetch:
            mock_cache.return_value = None
            mock_fetch.return_value = []

            start = datetime.now(timezone.utc) - timedelta(days=7)
            end = datetime.now(timezone.utc)

            # Use URL-safe datetime format
            start_str = start.isoformat().replace('+', '%2B')
            end_str = end.isoformat().replace('+', '%2B')

            response = client.get(
                f"/ohlcv?symbol=AAPL&asset_type=equity"
                f"&start_date={start_str}"
                f"&end_date={end_str}"
            )
            assert response.status_code == 200


def test_ohlcv_with_limit(client):
    """Test OHLCV endpoint with limit parameter."""
    with patch("src.data_hub.api.cache_manager.get_ohlcv_cache", new_callable=AsyncMock) as mock_cache:
        with patch("src.data_hub.api.yfinance_provider.fetch_ohlcv", new_callable=AsyncMock) as mock_fetch:
            with patch("src.data_hub.api.cache_manager.set_ohlcv_cache", new_callable=AsyncMock) as mock_set_cache:
                # Create 100 data points
                data = [
                    OHLCVData(
                        timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                        open=100.0 + i,
                        high=105.0 + i,
                        low=99.0 + i,
                        close=103.0 + i,
                        volume=1000000.0,
                    )
                    for i in range(100)
                ]
                
                # Mock the async methods properly
                mock_cache.return_value = None
                mock_fetch.return_value = data[:50]  # Return only 50

                response = client.get("/ohlcv?symbol=AAPL&asset_type=equity&limit=50")
                assert response.status_code == 200

                result = response.json()
                assert len(result["data"]) == 50
