"""
Comprehensive tests for news modules to increase coverage
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest


@pytest.fixture
def mock_session():
    """Mock aiohttp session"""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def sample_cryptopanic_response():
    """Sample CryptoPanic API response"""
    return {
        "count": 2,
        "results": [
            {
                "id": 1,
                "title": "Bitcoin hits new high",
                "published_at": "2024-01-01T12:00:00Z",
                "url": "https://example.com/news1",
                "source": {"title": "CryptoNews"},
                "currencies": [{"code": "BTC"}],
                "kind": "news",
            },
            {
                "id": 2,
                "title": "Ethereum upgrade announced",
                "published_at": "2024-01-01T11:00:00Z",
                "url": "https://example.com/news2",
                "source": {"title": "EthNews"},
                "currencies": [{"code": "ETH"}],
                "kind": "news",
            },
        ],
    }


@pytest.fixture
def sample_gdelt_response():
    """Sample GDELT API response"""
    return {
        "articles": [
            {
                "title": "Global crypto market analysis",
                "url": "https://example.com/gdelt1",
                "seendate": "20240101T120000",
                "sourcecountry": "US",
                "language": "English",
                "domain": "example.com",
            }
        ]
    }


class TestCryptoPanicClient:
    """Test CryptoPanic news client"""

    def test_client_initialization(self):
        """Test CryptoPanic client initialization"""
        from src.news.cryptopanic import CryptoPanicClient

        client = CryptoPanicClient(api_key="test_key")

        assert client.api_key == "test_key"
        assert client.base_url == "https://cryptopanic.com/api/v1"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_fetch_news_success(self, mock_session_class, sample_cryptopanic_response):
        """Test successful news fetch"""
        from src.news.cryptopanic import CryptoPanicClient

        # Setup mock
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_cryptopanic_response)
        mock_session.get.return_value.__aenter__.return_value = mock_response

        client = CryptoPanicClient(api_key="test_key")
        news = await client.fetch_news()

        assert news is not None
        assert len(news) == 2
        assert news[0]["title"] == "Bitcoin hits new high"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_fetch_news_error(self, mock_session_class):
        """Test news fetch with error"""
        from src.news.cryptopanic import CryptoPanicClient

        # Setup mock to raise exception
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.get.side_effect = aiohttp.ClientError("Network error")

        client = CryptoPanicClient(api_key="test_key")
        news = await client.fetch_news()

        assert news == []

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_fetch_symbol_news(self, mock_session_class, sample_cryptopanic_response):
        """Test fetching news for specific symbol"""
        from src.news.cryptopanic import CryptoPanicClient

        # Setup mock
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_cryptopanic_response)
        mock_session.get.return_value.__aenter__.return_value = mock_response

        client = CryptoPanicClient(api_key="test_key")
        news = await client.fetch_symbol_news("BTC")

        assert news is not None

    def test_parse_news_item(self):
        """Test parsing news item"""
        from src.news.cryptopanic import CryptoPanicClient

        client = CryptoPanicClient(api_key="test_key")

        item = {
            "id": 1,
            "title": "Test news",
            "published_at": "2024-01-01T12:00:00Z",
            "url": "https://example.com",
            "source": {"title": "TestSource"},
            "currencies": [{"code": "BTC"}],
        }

        parsed = client.parse_news_item(item)

        assert parsed["title"] == "Test news"
        assert parsed["source"] == "TestSource"
        assert "BTC" in parsed["currencies"]

    @pytest.mark.asyncio
    async def test_save_news(self, tmp_path):
        """Test saving news to file"""
        from src.news.cryptopanic import CryptoPanicClient

        client = CryptoPanicClient(api_key="test_key", news_dir=str(tmp_path))

        news = [
            {"title": "News 1", "timestamp": "2024-01-01T12:00:00Z"},
            {"title": "News 2", "timestamp": "2024-01-01T11:00:00Z"},
        ]

        await client.save_news(news, "test")

        saved_file = tmp_path / "test.json"
        assert saved_file.exists()

        with open(saved_file) as f:
            saved_data = json.load(f)

        assert len(saved_data) == 2
        assert saved_data[0]["title"] == "News 1"


class TestGDELTClient:
    """Test GDELT news client"""

    def test_client_initialization(self):
        """Test GDELT client initialization"""
        from src.news.gdelt import GDELTClient

        client = GDELTClient()

        assert client.base_url == "https://api.gdeltproject.org/api/v2"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_fetch_crypto_news(self, mock_session_class, sample_gdelt_response):
        """Test fetching crypto news from GDELT"""
        from src.news.gdelt import GDELTClient

        # Setup mock
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_gdelt_response)
        mock_session.get.return_value.__aenter__.return_value = mock_response

        client = GDELTClient()
        news = await client.fetch_crypto_news()

        assert news is not None
        assert len(news) == 1
        assert news[0]["title"] == "Global crypto market analysis"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_search_news(self, mock_session_class):
        """Test searching news with query"""
        from src.news.gdelt import GDELTClient

        # Setup mock
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Article 1\nArticle 2")
        mock_session.get.return_value.__aenter__.return_value = mock_response

        client = GDELTClient()
        results = await client.search_news("bitcoin")

        assert results is not None

    def test_parse_gdelt_date(self):
        """Test parsing GDELT date format"""
        from src.news.gdelt import GDELTClient

        client = GDELTClient()

        date_str = "20240101T120000"
        parsed = client.parse_gdelt_date(date_str)

        assert parsed is not None
        assert isinstance(parsed, datetime)


class TestNewsAggregator:
    """Test news aggregator"""

    @patch("src.news.aggregator.CryptoPanicClient")
    @patch("src.news.aggregator.GDELTClient")
    def test_aggregator_initialization(self, mock_gdelt, mock_cryptopanic):
        """Test news aggregator initialization"""
        from src.news.aggregator import NewsAggregator

        aggregator = NewsAggregator()

        assert aggregator is not None
        assert aggregator.news_dir.exists()

    @pytest.mark.asyncio
    @patch("src.news.aggregator.CryptoPanicClient")
    @patch("src.news.aggregator.GDELTClient")
    async def test_fetch_all_news(self, mock_gdelt_class, mock_cryptopanic_class):
        """Test fetching news from all sources"""
        from src.news.aggregator import NewsAggregator

        # Setup mocks
        mock_cp = MagicMock()
        mock_cp.fetch_news = AsyncMock(
            return_value=[{"title": "CP News 1", "source": "cryptopanic"}]
        )
        mock_cryptopanic_class.return_value = mock_cp

        mock_gd = MagicMock()
        mock_gd.fetch_crypto_news = AsyncMock(
            return_value=[{"title": "GDELT News 1", "source": "gdelt"}]
        )
        mock_gdelt_class.return_value = mock_gd

        aggregator = NewsAggregator()
        news = await aggregator.fetch_all_news()

        assert len(news) == 2
        assert news[0]["source"] == "cryptopanic"
        assert news[1]["source"] == "gdelt"

    @pytest.mark.asyncio
    async def test_save_aggregated_news(self, tmp_path):
        """Test saving aggregated news"""
        from src.news.aggregator import NewsAggregator

        aggregator = NewsAggregator(news_dir=str(tmp_path))

        news = [
            {"title": "News 1", "timestamp": "2024-01-01T12:00:00Z"},
            {"title": "News 2", "timestamp": "2024-01-01T11:00:00Z"},
        ]

        await aggregator.save_news(news, "aggregated")

        saved_file = tmp_path / "aggregated.json"
        assert saved_file.exists()

    @pytest.mark.asyncio
    @patch("src.news.aggregator.CryptoPanicClient")
    async def test_update_all_news(self, mock_cp_class, tmp_path):
        """Test updating all news"""
        from src.news.aggregator import NewsAggregator

        mock_cp = MagicMock()
        mock_cp.fetch_news = AsyncMock(return_value=[])
        mock_cp.fetch_symbol_news = AsyncMock(return_value=[])
        mock_cp_class.return_value = mock_cp

        aggregator = NewsAggregator(news_dir=str(tmp_path))

        await aggregator.update_all_news(symbols=["BTC", "ETH"], hours_back=24)

        # Check that news fetch was attempted
        assert mock_cp.fetch_news.called

    def test_load_cached_news(self, tmp_path):
        """Test loading cached news"""
        from src.news.aggregator import NewsAggregator

        # Create cached file
        cached_news = [{"title": "Cached news", "timestamp": "2024-01-01T12:00:00Z"}]

        news_file = tmp_path / "cached.json"
        with open(news_file, "w") as f:
            json.dump(cached_news, f)

        aggregator = NewsAggregator(news_dir=str(tmp_path))
        loaded = aggregator.load_cached_news("cached")

        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0]["title"] == "Cached news"

    def test_filter_news_by_date(self):
        """Test filtering news by date"""
        from src.news.aggregator import NewsAggregator

        aggregator = NewsAggregator()

        news = [
            {"title": "Old news", "timestamp": "2023-01-01T12:00:00Z"},
            {"title": "Recent news", "timestamp": datetime.now().isoformat()},
        ]

        filtered = aggregator.filter_news_by_date(news, hours_back=24)

        assert len(filtered) == 1
        assert filtered[0]["title"] == "Recent news"
