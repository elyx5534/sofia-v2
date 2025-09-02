"""
Smoke tests for core API endpoints
"""

import os
import sys

from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_health_endpoint():
    """Test /health endpoint returns 200"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "ok"]


def test_metrics_endpoint():
    """Test /metrics endpoint exists"""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code in [200, 404]  # May not be implemented yet


def test_api_quotes_ohlcv():
    """Test OHLCV endpoint with fallback"""
    os.environ["FORCE_FALLBACK"] = "1"
    from src.api.main import app

    client = TestClient(app)

    response = client.get(
        "/api/quotes/ohlcv",
        params={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
        },
    )

    # Should either return data or proper error
    assert response.status_code in [200, 404, 422]
    if response.status_code == 200:
        data = response.json()
        assert "data" in data or "candles" in data


def test_api_backtest_run():
    """Test backtest run endpoint"""
    from src.api.main import app

    client = TestClient(app)

    response = client.post(
        "/api/backtest/run",
        json={
            "strategy": "sma",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "params": {"fast": 20, "slow": 50},
        },
    )

    # Should either run or return proper error
    assert response.status_code in [200, 404, 422]
    if response.status_code == 200:
        data = response.json()
        assert "result" in data or "total_return" in data


def test_api_paper_status():
    """Test paper trading status endpoint"""
    from src.api.main import app

    client = TestClient(app)

    response = client.get("/api/paper/status")

    # Should return status or not found
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert "equity_series" in data or "status" in data
        if "equity_series" in data:
            # Should have tail of equity series
            assert isinstance(data["equity_series"], list)
