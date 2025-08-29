"""
AI News Sentiment Analysis with FinBERT/VADER
"""

import os
import logging
import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import pandas as pd
import numpy as np

# Sentiment analysis libraries
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    import torch
    FINBERT_AVAILABLE = True
except ImportError:
    FINBERT_AVAILABLE = False

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """News article item"""
    title: str
    summary: str
    url: str
    source: str
    timestamp: datetime
    symbol: Optional[str] = None
    sentiment_score: Optional[float] = None
    confidence: Optional[float] = None
    keywords: List[str] = None


@dataclass
class SentimentScore:
    """Aggregated sentiment score"""
    symbol: str
    score_1h: float
    score_24h: float
    volume_1h: int
    volume_24h: int
    confidence_1h: float
    confidence_24h: float
    last_update: datetime


class NewsSentimentAnalyzer:
    """News sentiment analysis with multiple models"""
    
    def __init__(self):
        self.enabled = os.getenv('AI_NEWS_ENABLED', 'true').lower() == 'true'
        self.use_finbert = FINBERT_AVAILABLE and os.getenv('USE_FINBERT', 'true').lower() == 'true'
        self.cache_ttl = 300  # 5 minutes cache
        
        # Initialize analyzers
        self.vader_analyzer = SentimentIntensityAnalyzer()
        self.finbert_analyzer = None
        
        if self.use_finbert and FINBERT_AVAILABLE:
            try:
                self._initialize_finbert()
            except Exception as e:
                logger.warning(f"Failed to initialize FinBERT: {e}, falling back to VADER")
                self.use_finbert = False
        
        # News sources and feeds
        self.news_feeds = [
            {
                'name': 'CoinDesk',
                'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
                'symbol_mapping': ['BTC', 'ETH', 'crypto']
            },
            {
                'name': 'Reuters Business',
                'url': 'https://feeds.reuters.com/reuters/businessNews',
                'symbol_mapping': ['AAPL', 'MSFT', 'stock', 'market']
            },
            {
                'name': 'Yahoo Finance',
                'url': 'https://finance.yahoo.com/news/rssindex',
                'symbol_mapping': ['AAPL', 'MSFT', 'market']
            }
        ]
        
        # Symbol keywords for filtering
        self.symbol_keywords = {
            'BTC/USDT': ['bitcoin', 'btc', 'cryptocurrency', 'crypto'],
            'ETH/USDT': ['ethereum', 'eth', 'crypto', 'blockchain'],
            'AAPL': ['apple', 'iphone', 'ios', 'mac', 'tim cook'],
            'MSFT': ['microsoft', 'windows', 'azure', 'office', 'satya nadella']
        }
        
        # Cache
        self.news_cache: Dict[str, List[NewsItem]] = {}
        self.sentiment_cache: Dict[str, SentimentScore] = {}
        self.last_fetch = datetime.min
        
        # Anomaly detection
        self.baseline_scores: Dict[str, List[float]] = defaultdict(list)
        self.baseline_window = 100  # Keep 100 historical scores
    
    def _initialize_finbert(self):
        """Initialize FinBERT model"""
        logger.info("Initializing FinBERT model...")
        
        model_name = "ProsusAI/finbert"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        
        self.finbert_analyzer = pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1
        )
        
        logger.info("FinBERT initialized successfully")
    
    async def update_news_sentiment(self, symbols: List[str] = None) -> Dict[str, SentimentScore]:
        """Update news sentiment for symbols"""
        if not self.enabled:
            return {}
        
        if symbols is None:
            symbols = list(self.symbol_keywords.keys())
        
        # Fetch news if cache is stale
        if datetime.now() - self.last_fetch > timedelta(seconds=self.cache_ttl):
            await self._fetch_news()
        
        # Calculate sentiment scores
        sentiment_scores = {}
        for symbol in symbols:
            score = await self._calculate_symbol_sentiment(symbol)
            if score:
                sentiment_scores[symbol] = score
                self.sentiment_cache[symbol] = score
        
        return sentiment_scores
    
    async def _fetch_news(self):
        """Fetch news from all feeds"""
        logger.info("Fetching news from feeds...")
        
        all_news = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed in self.news_feeds:
                task = self._fetch_feed(session, feed)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Feed fetch error: {result}")
        
        # Deduplicate news
        unique_news = self._deduplicate_news(all_news)
        
        # Analyze sentiment for each news item
        for news_item in unique_news:
            try:
                sentiment = await self._analyze_text_sentiment(news_item.title + " " + news_item.summary)
                news_item.sentiment_score = sentiment['score']
                news_item.confidence = sentiment['confidence']
            except Exception as e:
                logger.error(f"Sentiment analysis failed for news item: {e}")
                news_item.sentiment_score = 0.0
                news_item.confidence = 0.0
        
        # Store in cache by symbol
        self.news_cache.clear()
        for symbol, keywords in self.symbol_keywords.items():
            self.news_cache[symbol] = self._filter_news_by_symbol(unique_news, keywords)
        
        self.last_fetch = datetime.now()
        logger.info(f"Fetched and processed {len(unique_news)} unique news items")
    
    async def _fetch_feed(self, session: aiohttp.ClientSession, feed: Dict[str, Any]) -> List[NewsItem]:
        """Fetch news from single feed"""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(feed['url'], timeout=timeout) as response:
                if response.status == 200:
                    content = await response.text()
                    return self._parse_rss_feed(content, feed['name'])
                else:
                    logger.warning(f"Feed {feed['name']} returned status {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch feed {feed['name']}: {e}")
            return []
    
    def _parse_rss_feed(self, content: str, source: str) -> List[NewsItem]:
        """Parse RSS feed content"""
        news_items = []
        
        try:
            # Simple RSS parsing (in production would use feedparser)
            # For now, return mock news items
            mock_news = [
                NewsItem(
                    title="Bitcoin ETF Sees Record Inflows",
                    summary="Bitcoin exchange-traded funds attracted record inflows this week...",
                    url="https://example.com/btc-etf-inflows",
                    source=source,
                    timestamp=datetime.now() - timedelta(hours=1),
                    keywords=['bitcoin', 'etf', 'inflows']
                ),
                NewsItem(
                    title="Apple Reports Strong Q4 Earnings",
                    summary="Apple Inc. reported better-than-expected earnings for Q4...",
                    url="https://example.com/aapl-earnings",
                    source=source,
                    timestamp=datetime.now() - timedelta(hours=2),
                    keywords=['apple', 'earnings', 'q4']
                ),
                NewsItem(
                    title="Microsoft Azure Growth Accelerates",
                    summary="Microsoft's cloud computing division showed accelerating growth...",
                    url="https://example.com/msft-azure",
                    source=source,
                    timestamp=datetime.now() - timedelta(hours=3),
                    keywords=['microsoft', 'azure', 'cloud']
                )
            ]
            news_items.extend(mock_news)
            
        except Exception as e:
            logger.error(f"Failed to parse RSS feed from {source}: {e}")
        
        return news_items
    
    def _deduplicate_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """Remove duplicate news items"""
        seen_titles = set()
        unique_items = []
        
        for item in news_items:
            # Simple deduplication by title similarity
            title_key = item.title.lower().replace(' ', '')[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_items.append(item)
        
        return unique_items
    
    def _filter_news_by_symbol(self, news_items: List[NewsItem], keywords: List[str]) -> List[NewsItem]:
        """Filter news items relevant to symbol"""
        filtered_items = []
        
        for item in news_items:
            text = (item.title + " " + item.summary).lower()
            
            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in text:
                    item.symbol = keywords  # Mark with matching keywords
                    filtered_items.append(item)
                    break
        
        return filtered_items
    
    async def _analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text"""
        if not text.strip():
            return {'score': 0.0, 'confidence': 0.0}
        
        try:
            if self.use_finbert and self.finbert_analyzer:
                return await self._analyze_finbert(text)
            else:
                return self._analyze_vader(text)
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {'score': 0.0, 'confidence': 0.0}
    
    async def _analyze_finbert(self, text: str) -> Dict[str, float]:
        """Analyze sentiment using FinBERT"""
        try:
            # Truncate text if too long
            if len(text) > 512:
                text = text[:512]
            
            result = self.finbert_analyzer(text)[0]
            
            # Convert to score (-1 to +1)
            label = result['label'].lower()
            confidence = result['score']
            
            if label == 'positive':
                score = confidence
            elif label == 'negative':
                score = -confidence
            else:  # neutral
                score = 0.0
            
            return {'score': score, 'confidence': confidence}
            
        except Exception as e:
            logger.error(f"FinBERT analysis failed: {e}")
            return self._analyze_vader(text)
    
    def _analyze_vader(self, text: str) -> Dict[str, float]:
        """Analyze sentiment using VADER"""
        try:
            scores = self.vader_analyzer.polarity_scores(text)
            
            # Use compound score as main sentiment
            sentiment_score = scores['compound']
            
            # Confidence based on absolute value and neu score
            confidence = abs(sentiment_score) * (1.0 - scores['neu'])
            
            return {'score': sentiment_score, 'confidence': confidence}
            
        except Exception as e:
            logger.error(f"VADER analysis failed: {e}")
            return {'score': 0.0, 'confidence': 0.0}
    
    async def _calculate_symbol_sentiment(self, symbol: str) -> Optional[SentimentScore]:
        """Calculate aggregated sentiment for symbol"""
        if symbol not in self.news_cache:
            return None
        
        news_items = self.news_cache[symbol]
        if not news_items:
            return None
        
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)
        
        # Filter by time windows
        news_1h = [item for item in news_items if item.timestamp >= hour_ago]
        news_24h = [item for item in news_items if item.timestamp >= day_ago]
        
        # Calculate weighted sentiment scores
        score_1h = self._calculate_weighted_sentiment(news_1h)
        score_24h = self._calculate_weighted_sentiment(news_24h)
        
        # Calculate confidence
        conf_1h = np.mean([item.confidence for item in news_1h if item.confidence is not None]) if news_1h else 0.0
        conf_24h = np.mean([item.confidence for item in news_24h if item.confidence is not None]) if news_24h else 0.0
        
        # Update baseline for anomaly detection
        if score_24h != 0:
            self.baseline_scores[symbol].append(score_24h)
            if len(self.baseline_scores[symbol]) > self.baseline_window:
                self.baseline_scores[symbol].pop(0)
        
        return SentimentScore(
            symbol=symbol,
            score_1h=score_1h,
            score_24h=score_24h,
            volume_1h=len(news_1h),
            volume_24h=len(news_24h),
            confidence_1h=conf_1h,
            confidence_24h=conf_24h,
            last_update=now
        )
    
    def _calculate_weighted_sentiment(self, news_items: List[NewsItem]) -> float:
        """Calculate time-weighted sentiment score"""
        if not news_items:
            return 0.0
        
        now = datetime.now()
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for item in news_items:
            if item.sentiment_score is None:
                continue
            
            # Time decay weight (more recent = higher weight)
            hours_ago = (now - item.timestamp).total_seconds() / 3600
            weight = np.exp(-hours_ago / 12)  # 12-hour half-life
            
            # Confidence weight
            confidence_weight = item.confidence if item.confidence else 0.5
            
            total_weight = weight * confidence_weight
            weighted_sum += item.sentiment_score * total_weight
            weight_sum += total_weight
        
        return weighted_sum / weight_sum if weight_sum > 0 else 0.0
    
    def detect_sentiment_anomaly(self, symbol: str, current_score: float) -> Dict[str, Any]:
        """Detect if current sentiment is anomalous"""
        if symbol not in self.baseline_scores or len(self.baseline_scores[symbol]) < 10:
            return {'anomaly': False, 'reason': 'insufficient_data'}
        
        baseline = self.baseline_scores[symbol]
        mean_score = np.mean(baseline)
        std_score = np.std(baseline)
        
        if std_score == 0:
            return {'anomaly': False, 'reason': 'no_variance'}
        
        # Z-score based anomaly detection
        z_score = (current_score - mean_score) / std_score
        
        is_anomaly = abs(z_score) > 2.0  # 2 standard deviations
        
        return {
            'anomaly': is_anomaly,
            'z_score': z_score,
            'baseline_mean': mean_score,
            'baseline_std': std_score,
            'current_score': current_score,
            'anomaly_type': 'positive' if z_score > 2.0 else 'negative' if z_score < -2.0 else 'normal'
        }
    
    def get_strategy_overlay_signals(self, symbol: str, sentiment_score: SentimentScore) -> Dict[str, Any]:
        """Get strategy overlay signals based on sentiment"""
        if not sentiment_score:
            return {'k_factor_adjustment': 0.0, 'strategy_bias': 'neutral'}
        
        # K-factor adjustment based on sentiment confidence
        base_adjustment = 0.0
        strategy_bias = 'neutral'
        
        score_1h = sentiment_score.score_1h
        confidence_1h = sentiment_score.confidence_1h
        
        # Strong positive sentiment
        if score_1h > 0.5 and confidence_1h > 0.6:
            base_adjustment = 0.1  # Increase K-factor by 10%
            strategy_bias = 'trend_following'  # Favor breakout strategies
        
        # Strong negative sentiment  
        elif score_1h < -0.5 and confidence_1h > 0.6:
            base_adjustment = 0.1  # Increase K-factor (volatility opportunity)
            strategy_bias = 'mean_reversion'  # Favor mean reversion strategies
        
        # High volume but neutral sentiment (uncertainty)
        elif sentiment_score.volume_1h > 5 and abs(score_1h) < 0.2:
            base_adjustment = -0.05  # Reduce K-factor (uncertainty)
            strategy_bias = 'defensive'
        
        # Detect anomaly
        anomaly = self.detect_sentiment_anomaly(symbol, score_1h)
        if anomaly['anomaly']:
            # Anomalous sentiment - extra caution or opportunity
            if anomaly['anomaly_type'] == 'positive':
                base_adjustment += 0.05  # Slight increase for positive anomaly
            else:
                base_adjustment -= 0.05  # Slight decrease for negative anomaly
        
        return {
            'k_factor_adjustment': base_adjustment,
            'strategy_bias': strategy_bias,
            'anomaly_detected': anomaly['anomaly'],
            'anomaly_type': anomaly.get('anomaly_type', 'normal'),
            'sentiment_strength': abs(score_1h),
            'confidence': confidence_1h
        }
    
    async def get_sentiment_summary(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get sentiment summary for symbol"""
        if symbol not in self.sentiment_cache:
            return None
        
        sentiment_score = self.sentiment_cache[symbol]
        overlay_signals = self.get_strategy_overlay_signals(symbol, sentiment_score)
        
        # Get recent news headlines
        recent_news = []
        if symbol in self.news_cache:
            recent_items = sorted(self.news_cache[symbol], 
                                key=lambda x: x.timestamp, reverse=True)[:3]
            recent_news = [
                {
                    'title': item.title,
                    'source': item.source,
                    'timestamp': item.timestamp.isoformat(),
                    'sentiment': item.sentiment_score
                }
                for item in recent_items
            ]
        
        return {
            'symbol': symbol,
            'sentiment_1h': sentiment_score.score_1h,
            'sentiment_24h': sentiment_score.score_24h,
            'volume_1h': sentiment_score.volume_1h,
            'volume_24h': sentiment_score.volume_24h,
            'confidence_1h': sentiment_score.confidence_1h,
            'confidence_24h': sentiment_score.confidence_24h,
            'last_update': sentiment_score.last_update.isoformat(),
            'strategy_overlay': overlay_signals,
            'recent_news': recent_news
        }