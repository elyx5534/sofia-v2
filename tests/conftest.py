"""Test configuration and fixtures."""

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Add src to path for absolute imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    from src.api.main import app

    return TestClient(app)


@pytest.fixture
def freeze_data():
    """Mock OHLCV data fixture."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="1h"),
            "open": [50000 + i * 10 for i in range(100)],
            "high": [50100 + i * 10 for i in range(100)],
            "low": [49900 + i * 10 for i in range(100)],
            "close": [50050 + i * 10 for i in range(100)],
            "volume": [100 + i for i in range(100)],
        }
    )


@pytest.fixture
def mock_datahub(freeze_data):
    """Mock DataHub for fast testing without network calls."""
    with patch("src.services.datahub.datahub") as mock:
        mock.get_ohlcv.return_value = freeze_data.values.tolist()
        mock.get_latest_price.return_value = {
            "symbol": "BTC/USDT",
            "price": 50000,
            "timestamp": 1704067200000,
            "volume": 1000,
        }
        yield mock


@pytest.fixture
def fast_symbol():
    """Fast test symbol."""
    return "BTC/USDT@BINANCE"


@pytest.fixture
def mock_exchange():
    """Mock exchange for testing."""
    exchange = MagicMock()
    exchange.fetch_balance.return_value = {"USDT": {"free": 10000, "used": 0, "total": 10000}}
    exchange.fetch_ticker.return_value = {"bid": 49999, "ask": 50001, "last": 50000}
    exchange.create_order.return_value = {"id": "test-order-123", "status": "closed"}
    return exchange
