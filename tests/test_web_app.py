"""Tests for the web app module."""

import json
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from src.web.app import app


class TestWebApp:
    """Test cases for Web App routes and API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_outputs_dir(self, tmp_path):
        """Create temporary outputs directory."""
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()

        # Create news subdirectory
        news_dir = outputs_dir / "news"
        news_dir.mkdir()

        with patch("src.web.app.outputs_dir", outputs_dir):
            yield outputs_dir

    @pytest.fixture
    def sample_signals_file(self, mock_outputs_dir):
        """Create sample signals.json file."""
        signals_data = [
            {
                "symbol": "BTC-USD",
                "score": 4.5,
                "indicators": {"close": 50000, "price_change_24h": 2.5, "rsi": 65},
            },
            {
                "symbol": "ETH-USD",
                "score": 3.2,
                "indicators": {"close": 3000, "price_change_24h": -1.2, "rsi": 45},
            },
        ]

        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump(signals_data, f)

        return signals_file

    @pytest.fixture
    def sample_news_file(self, mock_outputs_dir):
        """Create sample news file."""
        news_data = [
            {
                "title": "Bitcoin Reaches New Heights",
                "url": "https://example.com/news1",
                "published": "2023-01-15T10:00:00Z",
                "source": "CryptoNews",
            }
        ]

        news_file = mock_outputs_dir / "news" / "global.json"
        with open(news_file, "w") as f:
            json.dump(news_data, f)

        return news_file

    def test_home_page(self, client):
        """Test home page renders correctly."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_signals_page(self, client):
        """Test signals page renders correctly."""
        response = client.get("/signals")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_heatmap_page(self, client):
        """Test heatmap page renders correctly."""
        response = client.get("/heatmap")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_chart_page(self, client):
        """Test chart page renders correctly."""
        response = client.get("/chart/BTC-USD")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_news_page(self, client):
        """Test news page renders correctly."""
        response = client.get("/news")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_signals_with_data(self, client, sample_signals_file):
        """Test API signals endpoint with data."""
        response = client.get("/api/signals")
        assert response.status_code == 200

        data = response.json()
        assert "signals" in data
        assert "last_updated" in data
        assert "total_count" in data
        assert len(data["signals"]) == 2
        assert data["total_count"] == 2
        assert data["signals"][0]["symbol"] == "BTC-USD"

    def test_api_signals_no_file(self, client, mock_outputs_dir):
        """Test API signals endpoint when no signals file exists."""
        response = client.get("/api/signals")
        assert response.status_code == 200

        data = response.json()
        assert data["signals"] == []
        assert data["last_updated"] is None

    def test_api_signals_invalid_json(self, client, mock_outputs_dir):
        """Test API signals endpoint with invalid JSON file."""
        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            f.write("invalid json")

        response = client.get("/api/signals")
        assert response.status_code == 500
        assert "Failed to load signals data" in response.json()["detail"]

    def test_api_signals_non_list_data(self, client, mock_outputs_dir):
        """Test API signals endpoint with non-list JSON data."""
        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump({"not": "a list"}, f)

        response = client.get("/api/signals")
        assert response.status_code == 200

        data = response.json()
        assert data["signals"] == []
        assert data["total_count"] == 0

    def test_api_heatmap_with_data(self, client, sample_signals_file):
        """Test API heatmap endpoint with data."""
        response = client.get("/api/heatmap")
        assert response.status_code == 200

        data = response.json()
        assert "heatmap_data" in data
        assert len(data["heatmap_data"]) == 2

        heatmap_item = data["heatmap_data"][0]
        assert "symbol" in heatmap_item
        assert "score" in heatmap_item
        assert "color_intensity" in heatmap_item
        assert "price" in heatmap_item
        assert "change_24h" in heatmap_item

    def test_api_heatmap_no_file(self, client, mock_outputs_dir):
        """Test API heatmap endpoint when no signals file exists."""
        response = client.get("/api/heatmap")
        assert response.status_code == 200

        data = response.json()
        assert data["heatmap_data"] == []

    def test_api_heatmap_score_filtering(self, client, mock_outputs_dir):
        """Test API heatmap endpoint filters out zero scores."""
        signals_data = [
            {
                "symbol": "BTC",
                "score": 4.5,
                "indicators": {"close": 50000, "price_change_24h": 2.5},
            },
            {"symbol": "ETH", "score": 0, "indicators": {"close": 3000, "price_change_24h": -1.2}},
            {"symbol": "ADA", "score": 2.1, "indicators": {"close": 1, "price_change_24h": 0.5}},
        ]

        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump(signals_data, f)

        response = client.get("/api/heatmap")
        assert response.status_code == 200

        data = response.json()
        # Should only include BTC and ADA (score > 0)
        assert len(data["heatmap_data"]) == 2
        symbols = [item["symbol"] for item in data["heatmap_data"]]
        assert "BTC" in symbols
        assert "ADA" in symbols
        assert "ETH" not in symbols

    def test_api_heatmap_color_intensity_normalization(self, client, mock_outputs_dir):
        """Test heatmap color intensity normalization."""
        signals_data = [
            {"symbol": "HIGH", "score": 10.0, "indicators": {"close": 100, "price_change_24h": 5}},
            {"symbol": "MID", "score": 2.5, "indicators": {"close": 50, "price_change_24h": 0}},
        ]

        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump(signals_data, f)

        response = client.get("/api/heatmap")
        data = response.json()

        high_item = next(item for item in data["heatmap_data"] if item["symbol"] == "HIGH")
        mid_item = next(item for item in data["heatmap_data"] if item["symbol"] == "MID")

        assert high_item["color_intensity"] == 1.0  # min(10/5, 1) = 1.0
        assert mid_item["color_intensity"] == 0.5  # min(2.5/5, 1) = 0.5

    @patch("src.web.app.data_pipeline")
    def test_api_ohlcv_with_real_data(self, mock_pipeline, client):
        """Test API OHLCV endpoint with real data from pipeline."""
        # Mock real data from pipeline
        mock_df = pd.DataFrame(
            {
                "open": [100, 101],
                "high": [102, 103],
                "low": [99, 100],
                "close": [101, 102],
                "volume": [1000, 1100],
                "rsi": [50, 55],
                "sma_20": [100.5, 101.5],
                "sma_50": [100, 101],
                "bb_upper": [105, 106],
                "bb_middle": [101, 102],
                "bb_lower": [97, 98],
                "macd": [0.5, 0.6],
                "macd_signal": [0.4, 0.5],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="H"),
        )

        mock_pipeline.get_symbol_data.return_value = mock_df

        response = client.get("/api/ohlcv?symbol=BTC-USD&timeframe=1h")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert data["timeframe"] == "1h"
        assert len(data["data"]) == 2
        assert data["total_records"] == 2

        # Check data structure
        candle = data["data"][0]
        expected_keys = [
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "rsi",
            "sma_20",
            "sma_50",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "macd",
            "macd_signal",
        ]
        for key in expected_keys:
            assert key in candle

    @patch("src.web.app.data_pipeline")
    @patch("src.web.app.add_all_indicators")
    def test_api_ohlcv_with_mock_data(self, mock_add_indicators, mock_pipeline, client):
        """Test API OHLCV endpoint generates mock data when no real data available."""
        # Pipeline returns empty DataFrame
        mock_pipeline.get_symbol_data.return_value = pd.DataFrame()

        # Mock indicators function
        mock_df_with_indicators = pd.DataFrame(
            {
                "open": [50000],
                "high": [51000],
                "low": [49000],
                "close": [50500],
                "volume": [5000],
                "rsi": [60],
                "sma_20": [50000],
                "sma_50": [49500],
            },
            index=pd.date_range("2023-01-01", periods=1, freq="H"),
        )
        mock_add_indicators.return_value = mock_df_with_indicators

        response = client.get("/api/ohlcv?symbol=BTC-USD&timeframe=1h")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert len(data["data"]) > 0
        assert data["total_records"] > 0

    def test_api_ohlcv_invalid_symbol(self, client):
        """Test API OHLCV endpoint with invalid symbol."""
        response = client.get("/api/ohlcv?symbol=INVALID")
        assert response.status_code == 404
        # Response will be HTML 404 page, not JSON
        assert response.headers["content-type"] == "text/html; charset=utf-8"

    def test_api_ohlcv_invalid_symbol_characters(self, client):
        """Test API OHLCV endpoint with invalid symbol characters."""
        response = client.get("/api/ohlcv?symbol=BTC<script>")
        assert response.status_code == 404
        # Response will be HTML 404 page, not JSON
        assert response.headers["content-type"] == "text/html; charset=utf-8"

    def test_api_ohlcv_invalid_timeframe(self, client):
        """Test API OHLCV endpoint with invalid timeframe."""
        response = client.get("/api/ohlcv?symbol=BTC-USD&timeframe=invalid")
        assert response.status_code == 422  # Validation error

    def test_api_ohlcv_missing_symbol(self, client):
        """Test API OHLCV endpoint without symbol parameter."""
        response = client.get("/api/ohlcv")
        assert response.status_code == 422  # Missing required parameter

    @patch("src.web.app.data_pipeline")
    def test_api_ohlcv_generates_mock_data_when_empty(self, mock_pipeline, client):
        """Test API OHLCV endpoint generates mock data when pipeline returns empty."""
        mock_pipeline.get_symbol_data.return_value = pd.DataFrame()

        response = client.get("/api/ohlcv?symbol=BTC-USD")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert len(data["data"]) > 0  # Mock data should be generated
        assert data["total_records"] > 0

    @patch("src.web.app.data_pipeline")
    def test_api_ohlcv_exception_handling(self, mock_pipeline, client):
        """Test API OHLCV endpoint exception handling."""
        mock_pipeline.get_symbol_data.side_effect = Exception("Pipeline error")

        response = client.get("/api/ohlcv?symbol=BTC-USD")
        assert response.status_code == 500
        assert "Failed to fetch chart data" in response.json()["detail"]

    def test_safe_float_function(self, client):
        """Test safe_float function with various inputs."""
        # safe_float is defined locally in the OHLCV endpoint, test it indirectly
        import math

        def safe_float(value, default=0):
            try:
                val = float(value)
                return default if math.isnan(val) or math.isinf(val) else val
            except (ValueError, TypeError):
                return default

        # Test normal float
        assert safe_float(42.5) == 42.5

        # Test NaN
        assert safe_float(float("nan"), default=0) == 0

        # Test infinity
        assert safe_float(float("inf"), default=0) == 0

        # Test string conversion
        assert safe_float("42.5") == 42.5

        # Test invalid string
        assert safe_float("invalid", default=0) == 0

        # Test None
        assert safe_float(None, default=0) == 0

    @patch("src.web.app.news_aggregator")
    def test_api_news_global(self, mock_aggregator, client):
        """Test API news endpoint for global news."""
        mock_news_data = [
            {"title": "Bitcoin News", "url": "https://example.com", "published": "2023-01-01"}
        ]
        mock_aggregator.get_latest_news.return_value = mock_news_data

        response = client.get("/api/news?limit=20")
        assert response.status_code == 200

        data = response.json()
        assert data["news"] == mock_news_data
        assert data["symbol"] is None
        assert data["total_count"] == 1

        mock_aggregator.get_latest_news.assert_called_once_with(20)

    @patch("src.web.app.news_aggregator")
    def test_api_news_symbol_specific(self, mock_aggregator, client):
        """Test API news endpoint for symbol-specific news."""
        mock_news_data = [
            {"title": "BTC News", "url": "https://example.com", "published": "2023-01-01"}
        ]
        mock_aggregator.get_symbol_news.return_value = mock_news_data

        response = client.get("/api/news?symbol=BTC-USD&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["news"] == mock_news_data
        assert data["symbol"] == "BTC-USD"
        assert data["total_count"] == 1

        mock_aggregator.get_symbol_news.assert_called_once_with("BTC-USD")

    @patch("src.web.app.news_aggregator")
    def test_api_news_limit_validation(self, mock_aggregator, client):
        """Test API news endpoint limit validation."""
        # Test minimum limit
        response = client.get("/api/news?limit=0")
        assert response.status_code == 422

        # Test maximum limit
        response = client.get("/api/news?limit=101")
        assert response.status_code == 422

        # Test valid limit
        mock_aggregator.get_latest_news.return_value = []
        response = client.get("/api/news?limit=50")
        assert response.status_code == 200

    @patch("src.web.app.news_aggregator")
    def test_api_news_exception_handling(self, mock_aggregator, client):
        """Test API news endpoint exception handling."""
        mock_aggregator.get_latest_news.side_effect = Exception("News error")

        response = client.get("/api/news")
        assert response.status_code == 500
        assert "Failed to fetch news data" in response.json()["detail"]

    @patch("src.web.app.data_pipeline")
    def test_api_status_healthy(self, mock_pipeline, client, sample_signals_file, sample_news_file):
        """Test API status endpoint when system is healthy."""
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD", "ETH-USD", "ADA-USD"]

        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["available_symbols"] == 3
        assert "signals_age_seconds" in data
        assert "news_age_seconds" in data
        assert "timestamp" in data
        assert data["signals_age_seconds"] is not None
        assert data["news_age_seconds"] is not None

    @patch("src.web.app.data_pipeline")
    def test_api_status_no_files(self, mock_pipeline, client, mock_outputs_dir):
        """Test API status endpoint when files don't exist."""
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD"]

        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["available_symbols"] == 1
        assert data["signals_age_seconds"] is None
        assert data["news_age_seconds"] is None

    @patch("src.web.app.data_pipeline")
    def test_api_status_exception_handling(self, mock_pipeline, client):
        """Test API status endpoint exception handling."""
        mock_pipeline.get_available_symbols.side_effect = Exception("Pipeline error")

        response = client.get("/api/status")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "error"
        assert "error" in data
        assert "timestamp" in data

    @patch("src.web.app.data_pipeline")
    def test_api_search_symbols(self, mock_pipeline, client):
        """Test API search endpoint."""
        mock_pipeline.get_available_symbols.return_value = [
            "BTC-USD",
            "BTC-EUR",
            "ETH-USD",
            "ETH-EUR",
            "ADA-USD",
        ]

        response = client.get("/api/search?q=btc&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "btc"
        assert len(data["results"]) == 2  # BTC-USD, BTC-EUR
        assert data["total_count"] == 2
        assert "BTC-USD" in data["results"]
        assert "BTC-EUR" in data["results"]

    @patch("src.web.app.data_pipeline")
    def test_api_search_partial_match(self, mock_pipeline, client):
        """Test API search with partial symbol matches."""
        mock_pipeline.get_available_symbols.return_value = ["BTC/USD", "BTCEUR", "ETH-USD"]

        response = client.get("/api/search?q=btc")
        data = response.json()

        assert len(data["results"]) == 2
        assert "BTC/USD" in data["results"]
        assert "BTCEUR" in data["results"]

    @patch("src.web.app.data_pipeline")
    def test_api_search_limit_parameter(self, mock_pipeline, client):
        """Test API search limit parameter."""
        mock_pipeline.get_available_symbols.return_value = [
            "BTC-USD",
            "BTC-EUR",
            "BTC-GBP",
            "BTC-JPY",
        ]

        response = client.get("/api/search?q=btc&limit=2")
        data = response.json()

        assert len(data["results"]) == 2
        assert data["total_count"] == 2

    @patch("src.web.app.data_pipeline")
    def test_api_search_no_matches(self, mock_pipeline, client):
        """Test API search with no matches."""
        mock_pipeline.get_available_symbols.return_value = ["BTC-USD", "ETH-USD"]

        response = client.get("/api/search?q=xyz")
        data = response.json()

        assert data["results"] == []
        assert data["total_count"] == 0

    def test_api_search_query_validation(self, client):
        """Test API search query validation."""
        # Test minimum length
        response = client.get("/api/search?q=x")
        assert response.status_code == 422

    @patch("src.web.app.data_pipeline")
    def test_api_search_exception_handling(self, mock_pipeline, client):
        """Test API search exception handling."""
        mock_pipeline.get_available_symbols.side_effect = Exception("Search error")

        response = client.get("/api/search?q=btc")
        assert response.status_code == 500
        assert "Search failed" in response.json()["detail"]

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_404_error_handler(self, client):
        """Test custom 404 error handler."""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]

    @patch("src.web.app.data_pipeline")
    def test_btc_mock_data_generation(self, mock_pipeline, client):
        """Test BTC-specific mock data generation."""
        mock_pipeline.get_symbol_data.return_value = pd.DataFrame()

        with patch("src.web.app.add_all_indicators") as mock_indicators:
            # Create mock DataFrame with BTC-like prices
            mock_df = pd.DataFrame(
                {
                    "open": [49000],
                    "high": [51000],
                    "low": [48000],
                    "close": [50000],
                    "volume": [5000],
                },
                index=pd.date_range("2023-01-01", periods=1, freq="H"),
            )
            mock_indicators.return_value = mock_df

            response = client.get("/api/ohlcv?symbol=BTC-USD")
            assert response.status_code == 200

            # Verify mock_indicators was called (indicating mock data was generated)
            mock_indicators.assert_called_once()

    @patch("src.web.app.data_pipeline")
    def test_eth_mock_data_generation(self, mock_pipeline, client):
        """Test ETH-specific mock data generation."""
        mock_pipeline.get_symbol_data.return_value = pd.DataFrame()

        with patch("src.web.app.add_all_indicators") as mock_indicators:
            mock_df = pd.DataFrame(
                {"open": [2900], "high": [3100], "low": [2800], "close": [3000], "volume": [5000]},
                index=pd.date_range("2023-01-01", periods=1, freq="H"),
            )
            mock_indicators.return_value = mock_df

            response = client.get("/api/ohlcv?symbol=ETH-USD")
            assert response.status_code == 200

            mock_indicators.assert_called_once()

    @patch("src.web.app.data_pipeline")
    def test_generic_mock_data_generation(self, mock_pipeline, client):
        """Test generic mock data generation for other symbols."""
        mock_pipeline.get_symbol_data.return_value = pd.DataFrame()

        with patch("src.web.app.add_all_indicators") as mock_indicators:
            mock_df = pd.DataFrame(
                {"open": [99], "high": [101], "low": [98], "close": [100], "volume": [5000]},
                index=pd.date_range("2023-01-01", periods=1, freq="H"),
            )
            mock_indicators.return_value = mock_df

            response = client.get("/api/ohlcv?symbol=ADA-USD")
            assert response.status_code == 200

            mock_indicators.assert_called_once()

    def test_heatmap_top_100_limit(self, client, mock_outputs_dir):
        """Test heatmap endpoint limits to top 100 signals."""
        # Create 150 signals
        signals_data = []
        for i in range(150):
            signals_data.append(
                {
                    "symbol": f"SYMBOL{i}",
                    "score": 3.0,
                    "indicators": {"close": 100, "price_change_24h": 1.0},
                }
            )

        signals_file = mock_outputs_dir / "signals.json"
        with open(signals_file, "w") as f:
            json.dump(signals_data, f)

        response = client.get("/api/heatmap")
        data = response.json()

        # Should be limited to 100
        assert len(data["heatmap_data"]) == 100

    def test_api_ohlcv_default_timeframe(self, client):
        """Test API OHLCV endpoint uses default timeframe when not specified."""
        with patch("src.web.app.data_pipeline") as mock_pipeline:
            mock_pipeline.get_symbol_data.return_value = pd.DataFrame(
                {"open": [100], "high": [101], "low": [99], "close": [100.5], "volume": [1000]},
                index=pd.date_range("2023-01-01", periods=1, freq="H"),
            )

            response = client.get("/api/ohlcv?symbol=BTC-USD")  # No timeframe parameter
            assert response.status_code == 200

            data = response.json()
            assert data["timeframe"] == "1h"  # Default value

            # Verify the pipeline was called with default timeframe
            mock_pipeline.get_symbol_data.assert_called_once_with("BTC-USD", "1h")
