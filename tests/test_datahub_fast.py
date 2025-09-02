"""Fast tests for DataHub using mocks."""

from unittest.mock import MagicMock, patch


def test_datahub_get_ohlcv_with_mock(mock_datahub):
    """Test DataHub get_ohlcv with mock data."""
    from src.services.datahub import datahub

    # Mock is already set up via fixture
    data = datahub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")

    assert len(data) == 100
    assert mock_datahub.get_ohlcv.called


def test_datahub_get_latest_price_with_mock(mock_datahub):
    """Test DataHub get_latest_price with mock."""
    from src.services.datahub import datahub

    result = datahub.get_latest_price("BTC/USDT")

    assert result["symbol"] == "BTC/USDT"
    assert result["price"] == 50000
    assert mock_datahub.get_latest_price.called


@patch("src.services.datahub.requests.get")
def test_datahub_binance_fallback(mock_get):
    """Test DataHub Binance fallback mechanism."""
    from src.services.datahub import DataHub

    # Mock successful Binance response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [[1704067200000, "42000", "42500", "41500", "42300", "1000"]]
    mock_get.return_value = mock_response

    hub = DataHub()
    with patch.object(hub, "_fetch_yfinance", side_effect=Exception("yfinance failed")):
        data = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")

    assert len(data) > 0
    assert data[0][4] == 42300.0  # close price


@patch("src.services.datahub.yf.Ticker")
def test_datahub_yfinance_success(mock_ticker):
    """Test DataHub yfinance success path."""
    import pandas as pd
    from src.services.datahub import DataHub

    # Mock yfinance response
    mock_history = pd.DataFrame(
        {"Open": [50000], "High": [50500], "Low": [49500], "Close": [50200], "Volume": [1000]},
        index=pd.DatetimeIndex(["2024-01-01"]),
    )

    mock_ticker.return_value.history.return_value = mock_history

    hub = DataHub()
    data = hub._fetch_yfinance("BTC/USDT", "1h", "2024-01-01", "2024-01-02")

    assert len(data) == 1
    assert data[0][1] == 50000  # open
    assert data[0][4] == 50200  # close
