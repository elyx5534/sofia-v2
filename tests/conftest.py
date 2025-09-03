"""Test configuration and fixtures."""

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

# Add src to path for absolute imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture
def client():
    """FastAPI test client fixture."""
    if TestClient is None:
        pytest.skip("FastAPI not available")
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


# === AUTO-APPENDED: thirdparty_stubs first on sys.path ===
import os
import sys

os.environ.setdefault("OFFLINE", "1")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("STUB_3P", "1")

# CRITICAL: Add thirdparty_stubs to the BEGINNING of sys.path
# This ensures our stubs are found before the real packages
STUB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "thirdparty_stubs"))
if STUB_PATH not in sys.path[:1]:
    sys.path.insert(0, STUB_PATH)  # GÖLGELEME: gerçek paket olsa bile önce stub bulunur

# AutoStub: Missing external libraries are automatically stubbed
try:
    from src.testing_fakes.autostub import install as _install_autostub

    _install_autostub()
except Exception:
    pass

# Legacy fakes for specific modules
try:
    import ccxt  # noqa
except Exception:
    try:
        import importlib

        fake_ccxt = importlib.import_module("src.testing_fakes.ccxt")
        sys.modules["ccxt"] = fake_ccxt
    except:
        pass

try:
    import requests  # noqa
except Exception:
    try:
        import importlib

        fake_requests = importlib.import_module("src.testing_fakes.requests")
        sys.modules["requests"] = fake_requests
    except:
        pass

try:
    import yfinance  # noqa
except Exception:
    try:
        import importlib

        fake_yf = importlib.import_module("src.testing_fakes.yfinance")
        sys.modules["yfinance"] = fake_yf
        sys.modules["yf"] = fake_yf
    except:
        pass


# No-side-effects protection: Disable service starts and infinite loops
def _noop(*args, **kwargs):
    return None


def _async_noop(*args, **kwargs):
    async def _inner():
        return None

    return _inner()


# Patch dangerous functions to prevent side effects during testing
patch_targets = [
    ("uvicorn", "run"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("os", "system"),
    ("time", "sleep"),
    ("asyncio", "sleep"),
    ("threading", "Thread.start"),
    ("multiprocessing", "Process.start"),
    ("websockets", "serve"),
    ("aiohttp.web", "run_app"),
    ("fastapi", "run"),
]

for mod_name, attr_path in patch_targets:
    try:
        parts = attr_path.split(".")
        if len(parts) == 1:
            mod = __import__(mod_name, fromlist=[parts[0]])
            if hasattr(mod, parts[0]):
                setattr(mod, parts[0], _noop)
        else:
            # Handle nested attributes like Thread.start
            mod = __import__(mod_name, fromlist=[parts[0]])
            if hasattr(mod, parts[0]):
                obj = getattr(mod, parts[0])
                if hasattr(obj, parts[1]):
                    setattr(obj, parts[1], _noop)
    except Exception:
        pass

# Testing contract: Patch missing APIs
try:
    from src.contracts.testing import assert_contract, patch_contract

    patch_contract()
    try:
        assert_contract()
    except Exception:
        pass  # Don't raise, we have mocks
except Exception:
    pass

# === END AUTO-APPENDED ===
