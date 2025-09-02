"""
Smoke test for live proof endpoint
"""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_live_proof_endpoint():
    """Test live proof endpoint returns valid data"""
    response = client.get("/live-proof?symbol=BTC/USDT")

    assert response.status_code == 200

    data = response.json()

    # Check required fields
    assert "symbol" in data
    assert "bid" in data
    assert "ask" in data
    assert "last" in data
    assert "exchange" in data
    assert "exchange_server_time_ms" in data
    assert "local_time_ms" in data

    # Check last price is positive
    if "error" not in data:
        assert data["last"] > 0
        assert data["bid"] > 0
        assert data["ask"] > 0
        assert data["ask"] >= data["bid"]  # Ask should be >= bid


def test_live_proof_different_symbol():
    """Test with different symbol"""
    response = client.get("/live-proof?symbol=ETH/USDT")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "ETH/USDT"
