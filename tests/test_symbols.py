"""Tests for the symbols endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.data_hub.api import app
from src.data_hub.models import AssetType, SymbolInfo


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_symbols_search_missing_params(client):
    """Test symbols endpoint with missing required parameters."""
    response = client.get("/symbols")
    assert response.status_code == 422


def test_symbols_search_invalid_asset_type(client):
    """Test symbols endpoint with invalid asset type."""
    response = client.get("/symbols?query=AAPL&asset_type=invalid")
    assert response.status_code == 422


@patch("src.data_hub.api.yfinance_provider.search_symbols")
def test_symbols_search_equity(mock_search, client):
    """Test searching for equity symbols."""
    # Setup mock
    mock_search.return_value = [
        SymbolInfo(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.EQUITY,
            currency="USD",
            active=True,
        ),
        SymbolInfo(
            symbol="AAPL.L",
            name="Apple Inc. London",
            asset_type=AssetType.EQUITY,
            currency="GBP",
            active=True,
        ),
    ]

    # Make request
    response = client.get("/symbols?query=AAPL&asset_type=equity")
    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["query"] == "AAPL"
    assert data["asset_type"] == "equity"
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["symbol"] == "AAPL"
    assert data["results"][0]["name"] == "Apple Inc."


@patch("src.data_hub.api.ccxt_provider.search_symbols")
def test_symbols_search_crypto(mock_search, client):
    """Test searching for crypto symbols."""
    # Setup mock
    mock_search.return_value = [
        SymbolInfo(
            symbol="BTC/USDT",
            name="Bitcoin/Tether",
            asset_type=AssetType.CRYPTO,
            exchange="binance",
            currency="USDT",
            active=True,
        ),
        SymbolInfo(
            symbol="BTC/BUSD",
            name="Bitcoin/Binance USD",
            asset_type=AssetType.CRYPTO,
            exchange="binance",
            currency="BUSD",
            active=True,
        ),
    ]

    # Make request
    response = client.get("/symbols?query=BTC&asset_type=crypto")
    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["query"] == "BTC"
    assert data["asset_type"] == "crypto"
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["symbol"] == "BTC/USDT"
    assert data["results"][0]["exchange"] == "binance"


def test_symbols_search_with_limit(client):
    """Test symbols search with limit parameter."""
    with patch("src.data_hub.api.yfinance_provider.search_symbols") as mock_search:
        mock_search.return_value = [
            SymbolInfo(
                symbol=f"TEST{i}",
                name=f"Test Company {i}",
                asset_type=AssetType.EQUITY,
                currency="USD",
                active=True,
            )
            for i in range(5)
        ]

        response = client.get("/symbols?query=TEST&asset_type=equity&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 5
        assert len(data["results"]) == 5


def test_symbols_search_no_results(client):
    """Test symbols search with no results."""
    with patch("src.data_hub.api.yfinance_provider.search_symbols") as mock_search:
        mock_search.return_value = []

        response = client.get("/symbols?query=INVALID&asset_type=equity")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 0
        assert len(data["results"]) == 0


@patch("src.data_hub.api.yfinance_provider.search_symbols")
def test_symbols_search_provider_error(mock_search, client):
    """Test symbols search when provider raises an error."""
    mock_search.side_effect = Exception("Provider error")

    response = client.get("/symbols?query=AAPL&asset_type=equity")
    assert response.status_code == 503

    data = response.json()
    assert "detail" in data
    assert "Provider error" in data["detail"]
