"""
Test suite for Data Hub Claude service and news provider
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.data_hub.claude_service import (
    ClaudeService,
    MarketAnalysisRequest,
    MarketAnalysisResponse,
    claude_service,
)
from src.data_hub.models import AssetType, OHLCVData
from src.data_hub.news_provider import NewsItem, NewsProvider


class TestMarketAnalysisRequest:
    """Test MarketAnalysisRequest model"""

    def test_market_analysis_request_creation(self):
        """Test MarketAnalysisRequest creation"""
        ohlcv_data = [
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=45000.0,
                high=46000.0,
                low=44500.0,
                close=45500.0,
                volume=100.0,
            )
        ]

        request = MarketAnalysisRequest(
            symbol="BTC/USDT",
            asset_type=AssetType.CRYPTO,
            ohlcv_data=ohlcv_data,
            timeframe="1h",
            analysis_type="technical",
        )

        assert request.symbol == "BTC/USDT"
        assert request.asset_type == AssetType.CRYPTO
        assert len(request.ohlcv_data) == 1
        assert request.timeframe == "1h"
        assert request.analysis_type == "technical"

    def test_market_analysis_request_validation(self):
        """Test MarketAnalysisRequest validation"""
        # Empty OHLCV data should still be valid
        request = MarketAnalysisRequest(
            symbol="AAPL", asset_type=AssetType.EQUITY, ohlcv_data=[], timeframe="1d"
        )

        assert len(request.ohlcv_data) == 0
        assert request.analysis_type == "technical"  # Default value


class TestMarketAnalysisResponse:
    """Test MarketAnalysisResponse model"""

    def test_market_analysis_response_creation(self):
        """Test MarketAnalysisResponse creation"""
        timestamp = datetime.now(timezone.utc)

        response = MarketAnalysisResponse(
            symbol="BTC/USDT",
            analysis_type="technical",
            summary="Strong bullish momentum with RSI oversold",
            key_insights=["BUY signal", "Momentum increasing"],
            risk_level="medium",
            recommendation="buy",
            confidence=0.85,
            timestamp=timestamp,
        )

        assert response.symbol == "BTC/USDT"
        assert response.analysis_type == "technical"
        assert response.summary == "Strong bullish momentum with RSI oversold"
        assert response.confidence == 0.85
        assert response.key_insights == ["BUY signal", "Momentum increasing"]
        assert response.risk_level == "medium"
        assert response.recommendation == "buy"

    def test_market_analysis_response_minimal(self):
        """Test MarketAnalysisResponse with minimal fields"""
        timestamp = datetime.now(timezone.utc)

        response = MarketAnalysisResponse(
            symbol="TEST",
            analysis_type="technical",
            summary="Basic analysis",
            key_insights=[],
            risk_level="medium",
            recommendation="hold",
            confidence=0.5,
            timestamp=timestamp,
        )

        assert response.summary == "Basic analysis"
        assert response.confidence == 0.5
        assert response.key_insights == []

    def test_market_analysis_response_validation_confidence(self):
        """Test MarketAnalysisResponse confidence validation"""
        timestamp = datetime.now(timezone.utc)

        # Valid confidence (0-1)
        response = MarketAnalysisResponse(
            symbol="TEST",
            analysis_type="technical",
            summary="Test analysis",
            key_insights=["test"],
            risk_level="medium",
            recommendation="hold",
            confidence=0.5,
            timestamp=timestamp,
        )
        assert response.confidence == 0.5

        # Edge cases
        response = MarketAnalysisResponse(
            symbol="TEST",
            analysis_type="technical",
            summary="Test analysis",
            key_insights=[],
            risk_level="low",
            recommendation="hold",
            confidence=0.0,
            timestamp=timestamp,
        )
        assert response.confidence == 0.0

        response = MarketAnalysisResponse(
            symbol="TEST",
            analysis_type="technical",
            summary="Test analysis",
            key_insights=["high confidence"],
            risk_level="high",
            recommendation="buy",
            confidence=1.0,
            timestamp=timestamp,
        )
        assert response.confidence == 1.0


class TestClaudeService:
    """Test Claude Service"""

    @pytest.fixture
    def service(self):
        """Create Claude service instance"""
        with patch("src.data_hub.settings.settings.claude_api_key", "test-api-key"):
            return ClaudeService()

    def test_claude_service_initialization(self):
        """Test Claude service initialization"""
        with patch("src.data_hub.settings.settings.claude_api_key", "test-key"):
            service = ClaudeService()
            assert service.client is not None
            assert service.model is not None

    def test_claude_service_initialization_no_key(self):
        """Test Claude service initialization without API key"""
        with patch("src.data_hub.settings.settings.claude_api_key", None):
            with pytest.raises(ValueError, match="Claude API key not configured"):
                ClaudeService()

    @pytest.mark.asyncio
    async def test_analyze_market_data_success(self, service, mock_http_client):
        """Test market analysis - success case"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {
                    "text": "ANALYSIS: Strong bullish momentum\nCONFIDENCE: 0.85\nSIGNALS: BUY,MOMENTUM_UP\nRISK_LEVEL: MEDIUM\nPRICE_TARGET: 50000\nSUPPORT: 44000,43000\nRESISTANCE: 47000,48000"
                }
            ]
        }
        mock_http_client.post.return_value = mock_response

        ohlcv_data = [
            OHLCVData(
                timestamp=datetime.now(timezone.utc),
                open=45000.0,
                high=46000.0,
                low=44500.0,
                close=45500.0,
                volume=100.0,
            )
        ]

        request = MarketAnalysisRequest(
            symbol="BTC/USDT", asset_type=AssetType.CRYPTO, ohlcv_data=ohlcv_data, timeframe="1h"
        )

        with patch.object(service, "_get_client", return_value=mock_http_client):
            response = await service.analyze_market_data(request)

            assert isinstance(response, MarketAnalysisResponse)
            assert "bullish momentum" in response.analysis
            assert response.confidence == 0.85
            assert "BUY" in response.signals
            assert response.price_target == 50000.0

    @pytest.mark.asyncio
    async def test_analyze_market_data_no_api_key(self):
        """Test market analysis without API key"""
        service = ClaudeService(None)

        request = MarketAnalysisRequest(
            symbol="BTC/USDT", asset_type=AssetType.CRYPTO, ohlcv_data=[], timeframe="1h"
        )

        with pytest.raises(ValueError, match="Claude API key not configured"):
            await service.analyze_market_data(request)

    @pytest.mark.asyncio
    async def test_analyze_market_data_api_error(self, service, mock_http_client):
        """Test market analysis with API error"""
        # Mock API error response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_http_client.post.return_value = mock_response

        request = MarketAnalysisRequest(
            symbol="BTC/USDT", asset_type=AssetType.CRYPTO, ohlcv_data=[], timeframe="1h"
        )

        with patch.object(service, "_get_client", return_value=mock_http_client):
            with pytest.raises(Exception, match="Claude API error"):
                await service.analyze_market_data(request)

    @pytest.mark.asyncio
    async def test_analyze_market_data_malformed_response(self, service, mock_http_client):
        """Test market analysis with malformed API response"""
        # Mock malformed response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [{"text": "Invalid response format"}]}
        mock_http_client.post.return_value = mock_response

        request = MarketAnalysisRequest(
            symbol="BTC/USDT", asset_type=AssetType.CRYPTO, ohlcv_data=[], timeframe="1h"
        )

        with patch.object(service, "_get_client", return_value=mock_http_client):
            response = await service.analyze_market_data(request)

            # Should handle gracefully with basic response
            assert isinstance(response, MarketAnalysisResponse)
            assert response.analysis == "Invalid response format"

    def test_format_ohlcv_for_prompt(self, service):
        """Test OHLCV data formatting for prompt"""
        ohlcv_data = [
            OHLCVData(
                timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
                open=45000.0,
                high=46000.0,
                low=44500.0,
                close=45500.0,
                volume=100.0,
            ),
            OHLCVData(
                timestamp=datetime(2023, 1, 1, 13, 0, tzinfo=timezone.utc),
                open=45500.0,
                high=46500.0,
                low=45000.0,
                close=46000.0,
                volume=120.0,
            ),
        ]

        formatted = service._format_ohlcv_for_prompt(ohlcv_data)

        assert "2023-01-01 12:00" in formatted
        assert "45000.0" in formatted
        assert "46000.0" in formatted
        assert len(formatted.split("\n")) >= 3  # Header + data rows

    def test_parse_analysis_response_complete(self, service):
        """Test parsing complete analysis response"""
        response_text = """
        ANALYSIS: Strong bullish momentum with high volume
        CONFIDENCE: 0.85
        SIGNALS: BUY,MOMENTUM_UP,VOLUME_INCREASE
        RISK_LEVEL: MEDIUM
        PRICE_TARGET: 50000
        SUPPORT: 44000,43000,42000
        RESISTANCE: 47000,48000,49000
        """

        parsed = service._parse_analysis_response(response_text)

        assert parsed.analysis == "Strong bullish momentum with high volume"
        assert parsed.confidence == 0.85
        assert parsed.signals == ["BUY", "MOMENTUM_UP", "VOLUME_INCREASE"]
        assert parsed.risk_level == "MEDIUM"
        assert parsed.price_target == 50000.0
        assert parsed.support_levels == [44000.0, 43000.0, 42000.0]
        assert parsed.resistance_levels == [47000.0, 48000.0, 49000.0]

    def test_parse_analysis_response_minimal(self, service):
        """Test parsing minimal analysis response"""
        response_text = "Simple analysis without structured format"

        parsed = service._parse_analysis_response(response_text)

        assert parsed.analysis == response_text
        assert parsed.confidence is None
        assert parsed.signals is None

    def test_parse_analysis_response_partial(self, service):
        """Test parsing partial analysis response"""
        response_text = """
        ANALYSIS: Bearish trend with low confidence
        CONFIDENCE: 0.3
        RISK_LEVEL: HIGH
        """

        parsed = service._parse_analysis_response(response_text)

        assert parsed.analysis == "Bearish trend with low confidence"
        assert parsed.confidence == 0.3
        assert parsed.risk_level == "HIGH"
        assert parsed.signals is None
        assert parsed.price_target is None

    @pytest.mark.asyncio
    async def test_client_management(self, service):
        """Test HTTP client management"""
        # Client should be created on first access
        client1 = await service._get_client()
        assert client1 is not None

        # Should reuse same client
        client2 = await service._get_client()
        assert client1 is client2

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_service_close(self, service):
        """Test service cleanup"""
        # Create client
        await service._get_client()

        # Close service
        await service.close()

        # Client should be None after close
        assert service._client is None


class TestNewsProvider:
    """Test News Provider"""

    @pytest.fixture
    def provider(self):
        """Create news provider instance"""
        return NewsProvider()

    @pytest.fixture
    def mock_response_data(self):
        """Mock news API response data"""
        return {
            "articles": [
                {
                    "title": "Bitcoin Reaches New High",
                    "description": "Bitcoin price surges to new all-time high",
                    "url": "https://example.com/news1",
                    "publishedAt": "2023-01-01T12:00:00Z",
                    "source": {"name": "CryptoNews"},
                },
                {
                    "title": "Market Analysis Update",
                    "description": "Weekly market analysis shows bullish trend",
                    "url": "https://example.com/news2",
                    "publishedAt": "2023-01-01T10:00:00Z",
                    "source": {"name": "MarketWatch"},
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_fetch_news_success(self, provider, mock_response_data):
        """Test news fetching - success case"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            news = await provider.fetch_news(symbol="BTC", limit=10)

            assert len(news) == 2
            assert isinstance(news[0], NewsItem)
            assert news[0].title == "Bitcoin Reaches New High"
            assert news[0].source == "CryptoNews"

    @pytest.mark.asyncio
    async def test_fetch_news_with_limit(self, provider, mock_response_data):
        """Test news fetching with limit"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            news = await provider.fetch_news(symbol="BTC", limit=1)

            assert len(news) == 1

    @pytest.mark.asyncio
    async def test_fetch_news_no_symbol(self, provider, mock_response_data):
        """Test news fetching without specific symbol"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            news = await provider.fetch_news(limit=5)

            assert len(news) == 2

    @pytest.mark.asyncio
    async def test_fetch_news_api_error(self, provider):
        """Test news fetching with API error"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="News API error"):
                await provider.fetch_news(symbol="BTC")

    @pytest.mark.asyncio
    async def test_fetch_news_empty_response(self, provider):
        """Test news fetching with empty response"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"articles": []}
            mock_get.return_value = mock_response

            news = await provider.fetch_news(symbol="NONEXISTENT")

            assert len(news) == 0

    @pytest.mark.asyncio
    async def test_fetch_news_malformed_response(self, provider):
        """Test news fetching with malformed response"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"invalid": "format"}
            mock_get.return_value = mock_response

            news = await provider.fetch_news(symbol="BTC")

            assert len(news) == 0

    @pytest.mark.asyncio
    async def test_fetch_news_with_incomplete_articles(self, provider):
        """Test news fetching with incomplete article data"""
        incomplete_data = {
            "articles": [
                {
                    "title": "Complete Article",
                    "description": "Full description",
                    "url": "https://example.com/news1",
                    "publishedAt": "2023-01-01T12:00:00Z",
                    "source": {"name": "NewsSource"},
                },
                {
                    "title": "Incomplete Article",
                    # Missing description and other fields
                    "url": "https://example.com/news2",
                    "publishedAt": "2023-01-01T11:00:00Z",
                },
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = incomplete_data
            mock_get.return_value = mock_response

            news = await provider.fetch_news(symbol="BTC")

            # Should handle incomplete articles gracefully
            assert len(news) >= 1  # At least the complete article should be parsed
            complete_article = next((n for n in news if n.title == "Complete Article"), None)
            assert complete_article is not None

    def test_parse_published_date(self, provider):
        """Test published date parsing"""
        # Valid ISO format
        date_str = "2023-01-01T12:00:00Z"
        parsed = provider._parse_published_date(date_str)
        assert parsed.year == 2023
        assert parsed.month == 1
        assert parsed.day == 1

        # Invalid format should return current time
        invalid_date = "invalid-date"
        parsed_invalid = provider._parse_published_date(invalid_date)
        assert isinstance(parsed_invalid, datetime)

    def test_clean_description(self, provider):
        """Test description cleaning"""
        # Normal description
        clean_desc = provider._clean_description("This is a normal description.")
        assert clean_desc == "This is a normal description."

        # Description with HTML tags
        html_desc = provider._clean_description("This has <b>HTML</b> tags.")
        assert "<b>" not in html_desc
        assert "HTML" in html_desc

        # Very long description
        long_desc = "A" * 1000
        cleaned_long = provider._clean_description(long_desc)
        assert len(cleaned_long) <= 500  # Should be truncated

    @pytest.mark.asyncio
    async def test_provider_close(self, provider):
        """Test provider cleanup"""
        # Should not raise exception
        await provider.close()


class TestGlobalClaudeService:
    """Test global Claude service instance"""

    def test_global_service_creation(self):
        """Test global service is created correctly"""
        # The global service should be created or None based on environment
        assert claude_service is None or isinstance(claude_service, ClaudeService)

    @patch.dict("os.environ", {"CLAUDE_API_KEY": "test-key"})
    def test_global_service_with_env_key(self):
        """Test global service creation with environment variable"""
        # Re-import to get new instance with env var
        import importlib

        from src.data_hub import claude_service as cs_module

        importlib.reload(cs_module)

        assert cs_module.claude_service is not None
        assert cs_module.claude_service.api_key == "test-key"
