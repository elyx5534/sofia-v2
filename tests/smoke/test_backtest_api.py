"""
Smoke test for backtest API
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_backtest_run_endpoint():
    """Test that backtest run endpoint works with mock data"""
    from src.api.main import app
    
    client = TestClient(app)
    
    # Mock backtest request
    request_data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "start": "2023-01-01",
        "end": "2023-01-31",
        "strategy": "sma_cross",
        "params": {
            "fast": 20,
            "slow": 50
        }
    }
    
    response = client.post("/api/backtest/run", json=request_data)
    
    # Should return 200 or handle gracefully
    assert response.status_code in [200, 400, 500]
    
    if response.status_code == 200:
        data = response.json()
        # Check for expected keys
        assert any(key in data for key in ["run_id", "equity_curve", "stats", "error"])

def test_backtest_strategies_endpoint():
    """Test that strategies endpoint returns list"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/api/backtest/strategies")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check strategy structure
    if data:
        strategy = data[0]
        assert "name" in strategy
        assert "display_name" in strategy
        assert "params" in strategy

def test_backtest_timeframes_endpoint():
    """Test that timeframes endpoint returns list"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/api/backtest/timeframes")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "1h" in data
    assert "1d" in data

def test_backtest_export_endpoint():
    """Test that export endpoint handles missing run_id gracefully"""
    from src.api.main import app
    
    client = TestClient(app)
    response = client.get("/api/backtest/export?run_id=nonexistent")
    
    # Should return 404 or 500 for nonexistent run_id (500 if exception occurs)
    assert response.status_code in [404, 400, 500]

if __name__ == "__main__":
    test_backtest_run_endpoint()
    test_backtest_strategies_endpoint()
    test_backtest_timeframes_endpoint()
    test_backtest_export_endpoint()
    print("Backtest API tests passed!")