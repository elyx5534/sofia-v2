"""Social sentiment analysis and Google Trends integration."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pytrends.request import TrendReq
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


class SentimentSource(str, Enum):
    """Available sentiment data sources."""

    GOOGLE_TRENDS = "google_trends"
    REDDIT = "reddit"
    TWITTER = "twitter"
    NEWS = "news"


@dataclass
class SentimentData:
    """Container for sentiment data."""

    source: SentimentSource
    symbol: str
    timestamp: datetime
    score: float
    volume: int
    metadata: Dict[str, Any]


class GoogleTrendsAnalyzer:
    """Analyze Google Trends data for trading signals."""

    def __init__(self):
        """Initialize Google Trends analyzer."""
        self.pytrends = TrendReq(hl="en-US", tz=360)
        self.cache = {}
        self.cache_duration = timedelta(hours=1)

    def get_trend_data(
        self, keywords: List[str], timeframe: str = "today 3-m", geo: str = ""
    ) -> pd.DataFrame:
        """
        Fetch Google Trends data for keywords.

        Args:
            keywords: List of keywords to search (max 5)
            timeframe: Time range ('today 3-m', 'today 12-m', etc.)
            geo: Geographic location ('' for worldwide)

        Returns:
            DataFrame with trend data
        """
        try:
            cache_key = f"{'-'.join(keywords)}_{timeframe}_{geo}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if datetime.now() - cached_time < self.cache_duration:
                    return cached_data
            self.pytrends.build_payload(keywords[:5], cat=0, timeframe=timeframe, geo=geo, gprop="")
            data = self.pytrends.interest_over_time()
            if not data.empty:
                if "isPartial" in data.columns:
                    data = data.drop("isPartial", axis=1)
                self.cache[cache_key] = (data, datetime.now())
            return data
        except Exception as e:
            logger.error(f"Error fetching Google Trends: {e}")
            return pd.DataFrame()

    def get_crypto_trends(self, symbol: str) -> pd.DataFrame:
        """
        Get Google Trends data for a cryptocurrency.

        Args:
            symbol: Crypto symbol (BTC, ETH, etc.)

        Returns:
            DataFrame with trend data
        """
        keywords = [
            f"{symbol} price",
            f"buy {symbol}",
            f"{symbol} crypto",
            f"{symbol} news",
            f"{symbol} prediction",
        ]
        return self.get_trend_data(keywords, timeframe="today 3-m")

    def get_stock_trends(self, symbol: str, company_name: Optional[str] = None) -> pd.DataFrame:
        """
        Get Google Trends data for a stock.

        Args:
            symbol: Stock ticker
            company_name: Company name (optional)

        Returns:
            DataFrame with trend data
        """
        keywords = [f"{symbol} stock"]
        if company_name:
            keywords.extend([company_name, f"{company_name} stock", f"{company_name} news"])
        else:
            keywords.extend([f"buy {symbol}", f"{symbol} price", f"{symbol} forecast"])
        return self.get_trend_data(keywords, timeframe="today 3-m")

    def calculate_trend_momentum(self, trends_data: pd.DataFrame) -> pd.Series:
        """
        Calculate momentum from trends data.

        Args:
            trends_data: DataFrame from get_trend_data

        Returns:
            Series with momentum scores
        """
        if trends_data.empty:
            return pd.Series()
        avg_trend = trends_data.mean(axis=1)
        momentum = pd.Series(index=avg_trend.index)
        momentum["roc"] = avg_trend.pct_change(periods=7)
        ema_short = avg_trend.ewm(span=7).mean()
        ema_long = avg_trend.ewm(span=30).mean()
        momentum["macd"] = (ema_short - ema_long) / ema_long
        momentum["strength"] = avg_trend
        rolling_mean = avg_trend.rolling(30).mean()
        rolling_std = avg_trend.rolling(30).std()
        momentum["spike"] = (avg_trend - rolling_mean) / rolling_std
        return momentum

    def get_related_queries(self, keyword: str) -> Dict[str, pd.DataFrame]:
        """
        Get related queries and topics.

        Args:
            keyword: Main keyword to analyze

        Returns:
            Dictionary with 'top' and 'rising' queries
        """
        try:
            self.pytrends.build_payload([keyword], timeframe="today 3-m")
            related = self.pytrends.related_queries()
            result = {}
            if keyword in related:
                if related[keyword]["top"] is not None:
                    result["top"] = related[keyword]["top"]
                if related[keyword]["rising"] is not None:
                    result["rising"] = related[keyword]["rising"]
            return result
        except Exception as e:
            logger.error(f"Error fetching related queries: {e}")
            return {}


class SentimentAnalyzer:
    """Analyze sentiment from text using VADER."""

    def __init__(self):
        """Initialize sentiment analyzer."""
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze_text(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with sentiment scores
        """
        scores = self.analyzer.polarity_scores(text)
        return scores

    def analyze_texts(self, texts: List[str]) -> pd.DataFrame:
        """
        Analyze multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            DataFrame with sentiment scores
        """
        results = []
        for text in texts:
            scores = self.analyze_text(text)
            results.append(scores)
        return pd.DataFrame(results)

    def get_overall_sentiment(self, texts: List[str]) -> float:
        """
        Get overall sentiment from multiple texts.

        Args:
            texts: List of texts

        Returns:
            Overall sentiment score (-1 to 1)
        """
        if not texts:
            return 0.0
        df = self.analyze_texts(texts)
        return df["compound"].mean()


class SocialSentimentAggregator:
    """Aggregate sentiment from multiple social sources."""

    def __init__(self):
        """Initialize aggregator."""
        self.google_trends = GoogleTrendsAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.weights = {
            SentimentSource.GOOGLE_TRENDS: 0.3,
            SentimentSource.REDDIT: 0.2,
            SentimentSource.TWITTER: 0.3,
            SentimentSource.NEWS: 0.2,
        }

    async def get_aggregated_sentiment(
        self, symbol: str, include_sources: Optional[List[SentimentSource]] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated sentiment from multiple sources.

        Args:
            symbol: Trading symbol
            include_sources: Sources to include (all if None)

        Returns:
            Dictionary with aggregated sentiment data
        """
        if include_sources is None:
            include_sources = list(SentimentSource)
        sentiment_data = []
        if SentimentSource.GOOGLE_TRENDS in include_sources:
            trends = (
                self.google_trends.get_crypto_trends(symbol)
                if "/" in symbol
                else self.google_trends.get_stock_trends(symbol)
            )
            if not trends.empty:
                momentum = self.google_trends.calculate_trend_momentum(trends)
                if "spike" in momentum:
                    latest_spike = (
                        momentum["spike"].iloc[-1] if not pd.isna(momentum["spike"].iloc[-1]) else 0
                    )
                    trend_sentiment = np.tanh(latest_spike / 2)
                else:
                    trend_sentiment = 0
                sentiment_data.append(
                    SentimentData(
                        source=SentimentSource.GOOGLE_TRENDS,
                        symbol=symbol,
                        timestamp=datetime.now(),
                        score=trend_sentiment,
                        volume=int(trends.iloc[-1].mean()) if not trends.empty else 0,
                        metadata={"momentum": momentum.to_dict() if not momentum.empty else {}},
                    )
                )
        if SentimentSource.NEWS in include_sources:
            news_sentiment = await self._get_news_sentiment(symbol)
            if news_sentiment:
                sentiment_data.append(news_sentiment)
        if sentiment_data:
            total_weight = sum(self.weights.get(s.source, 0.1) for s in sentiment_data)
            weighted_sum = sum(s.score * self.weights.get(s.source, 0.1) for s in sentiment_data)
            aggregate_score = weighted_sum / total_weight if total_weight > 0 else 0
        else:
            aggregate_score = 0
        return {
            "symbol": symbol,
            "aggregate_score": aggregate_score,
            "sentiment_label": self._score_to_label(aggregate_score),
            "sources": [
                {
                    "source": s.source.value,
                    "score": s.score,
                    "volume": s.volume,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in sentiment_data
            ],
            "timestamp": datetime.now().isoformat(),
        }

    async def _get_news_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get sentiment from news articles."""
        try:
            from src.data_hub.news_provider import news_provider

            news_items = await news_provider.fetch_news(symbol, limit=10)
            if not news_items:
                return None
            texts = []
            for item in news_items:
                texts.append(item.title)
                if item.summary:
                    texts.append(item.summary)
            overall_sentiment = self.sentiment_analyzer.get_overall_sentiment(texts)
            return SentimentData(
                source=SentimentSource.NEWS,
                symbol=symbol,
                timestamp=datetime.now(),
                score=overall_sentiment,
                volume=len(news_items),
                metadata={"articles_analyzed": len(news_items)},
            )
        except Exception as e:
            logger.error(f"Error getting news sentiment: {e}")
            return None

    def _score_to_label(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score >= 0.5:
            return "Very Bullish"
        elif score >= 0.2:
            return "Bullish"
        elif score >= -0.2:
            return "Neutral"
        elif score >= -0.5:
            return "Bearish"
        else:
            return "Very Bearish"

    def calculate_sentiment_signal(
        self, sentiment_history: pd.DataFrame, threshold: float = 0.3
    ) -> int:
        """
        Generate trading signal from sentiment history.

        Args:
            sentiment_history: DataFrame with sentiment scores over time
            threshold: Threshold for generating signals

        Returns:
            Trading signal: 1 (buy), -1 (sell), 0 (hold)
        """
        if sentiment_history.empty or "score" not in sentiment_history.columns:
            return 0
        recent_sentiment = sentiment_history["score"].iloc[-5:].mean()
        if len(sentiment_history) > 10:
            prev_sentiment = sentiment_history["score"].iloc[-10:-5].mean()
            momentum = recent_sentiment - prev_sentiment
        else:
            momentum = 0
        if recent_sentiment > threshold and momentum > 0:
            return 1
        elif recent_sentiment < -threshold and momentum < 0:
            return -1
        else:
            return 0


class CollectiveConsciousnessIndex:
    """
    Advanced sentiment index based on collective market psychology.
    Combines multiple data sources to gauge market sentiment.
    """

    def __init__(self):
        """Initialize the collective consciousness index."""
        self.aggregator = SocialSentimentAggregator()
        self.fear_greed_levels = {
            "extreme_fear": (-1.0, -0.6),
            "fear": (-0.6, -0.2),
            "neutral": (-0.2, 0.2),
            "greed": (0.2, 0.6),
            "extreme_greed": (0.6, 1.0),
        }

    async def calculate_index(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Calculate the collective consciousness index.

        Args:
            symbols: List of symbols to analyze

        Returns:
            Dictionary with index value and components
        """
        sentiments = []
        for symbol in symbols:
            sentiment = await self.aggregator.get_aggregated_sentiment(symbol)
            sentiments.append(sentiment["aggregate_score"])
        if sentiments:
            index_value = np.mean(sentiments)
            for state, (min_val, max_val) in self.fear_greed_levels.items():
                if min_val <= index_value < max_val:
                    market_state = state
                    break
            else:
                market_state = "neutral"
        else:
            index_value = 0
            market_state = "neutral"
        return {
            "index_value": index_value,
            "market_state": market_state,
            "sentiment_distribution": {
                "bullish": sum(1 for s in sentiments if s > 0.2),
                "neutral": sum(1 for s in sentiments if -0.2 <= s <= 0.2),
                "bearish": sum(1 for s in sentiments if s < -0.2),
            },
            "symbols_analyzed": len(symbols),
            "timestamp": datetime.now().isoformat(),
        }
