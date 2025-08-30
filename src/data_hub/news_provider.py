"""News provider for fetching financial news from various sources."""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import feedparser
import httpx
from bs4 import BeautifulSoup
import yfinance as yf
import json

class NewsItem:
    """Represents a single news item."""
    
    def __init__(self, title: str, summary: str, url: str, source: str, published: Optional[datetime] = None):
        self.title = title
        self.summary = summary
        self.url = url
        self.source = source
        self.published = published or datetime.now(timezone.utc)
    
    def to_dict(self):
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published": self.published.isoformat() if self.published else None
        }

class NewsProvider:
    """Provider for fetching financial news."""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def fetch_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """
        Fetch news for a given symbol from multiple sources.
        
        Args:
            symbol: Stock or crypto symbol (e.g., "AAPL", "BTC-USD")
            limit: Maximum number of news items to return
            
        Returns:
            List of NewsItem objects
        """
        # Check cache
        cache_key = f"{symbol}_{limit}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now(timezone.utc) - timestamp < timedelta(seconds=self.cache_ttl):
                return cached_data
        
        news_items = []
        
        # Try Yahoo Finance first
        try:
            yahoo_news = await self._fetch_yahoo_news(symbol, limit)
            news_items.extend(yahoo_news)
        except Exception as e:
            print(f"Error fetching Yahoo news: {e}")
        
        # Try RSS feeds
        try:
            rss_news = await self._fetch_rss_news(symbol, limit)
            news_items.extend(rss_news)
        except Exception as e:
            print(f"Error fetching RSS news: {e}")
        
        # Remove duplicates and limit
        seen_titles = set()
        unique_news = []
        for item in news_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                unique_news.append(item)
                if len(unique_news) >= limit:
                    break
        
        # Update cache
        self.cache[cache_key] = (unique_news, datetime.now(timezone.utc))
        
        return unique_news
    
    async def _fetch_yahoo_news(self, symbol: str, limit: int) -> List[NewsItem]:
        """Fetch news from Yahoo Finance."""
        news_items = []
        
        try:
            # Use yfinance to get ticker info
            ticker = yf.Ticker(symbol)
            
            # Get news from yfinance (if available)
            if hasattr(ticker, 'news'):
                yahoo_news = ticker.news[:limit] if ticker.news else []
                
                for article in yahoo_news:
                    news_items.append(NewsItem(
                        title=article.get('title', 'No title'),
                        summary=article.get('summary', article.get('title', '')),
                        url=article.get('link', '#'),
                        source='Yahoo Finance',
                        published=datetime.fromtimestamp(article.get('providerPublishTime', 0), tz=timezone.utc)
                    ))
        except Exception as e:
            print(f"Yahoo Finance news fetch error: {e}")
            # Fallback to mock data for demo
            news_items = self._get_mock_news(symbol, limit)
        
        return news_items
    
    async def _fetch_rss_news(self, symbol: str, limit: int) -> List[NewsItem]:
        """Fetch news from RSS feeds."""
        news_items = []
        
        # Financial RSS feeds
        rss_feeds = {
            "MarketWatch": f"https://feeds.content.dowjones.io/public/rss/mw_bulletins",
            "Investing.com": "https://www.investing.com/rss/news.rss",
        }
        
        for source, feed_url in rss_feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:5]:  # Get top 5 from each source
                    # Check if symbol is mentioned in title or summary
                    if symbol.upper() in entry.title.upper() or symbol.upper() in entry.get('summary', '').upper():
                        news_items.append(NewsItem(
                            title=entry.title,
                            summary=entry.get('summary', entry.title)[:200],
                            url=entry.link,
                            source=source,
                            published=datetime(*entry.published_parsed[:6], tzinfo=timezone.utc) if hasattr(entry, 'published_parsed') else None
                        ))
            except Exception as e:
                print(f"RSS feed error for {source}: {e}")
        
        return news_items
    
    def _get_mock_news(self, symbol: str, limit: int) -> List[NewsItem]:
        """Get mock news for testing/demo purposes."""
        mock_news = [
            NewsItem(
                f"{symbol} Shows Strong Momentum Amid Market Rally",
                f"Technical indicators suggest {symbol} is entering a bullish phase with increasing volume.",
                "#",
                "Market Analysis",
                datetime.now(timezone.utc) - timedelta(hours=1)
            ),
            NewsItem(
                f"Analysts Upgrade {symbol} Price Target",
                f"Major investment firms raise their price targets for {symbol} citing strong fundamentals.",
                "#",
                "Analyst Reports",
                datetime.now(timezone.utc) - timedelta(hours=3)
            ),
            NewsItem(
                f"{symbol} Trading Volume Surges 50%",
                f"Unusual trading activity detected in {symbol} as institutional investors increase positions.",
                "#",
                "Trading News",
                datetime.now(timezone.utc) - timedelta(hours=5)
            ),
            NewsItem(
                f"Breaking: {symbol} Announces Strategic Partnership",
                f"Company behind {symbol} reveals new partnership that could boost revenue by 20%.",
                "#",
                "Corporate News",
                datetime.now(timezone.utc) - timedelta(hours=8)
            ),
            NewsItem(
                f"Technical Analysis: {symbol} Forms Bullish Pattern",
                f"Chart analysis shows {symbol} forming a cup and handle pattern, signaling potential upside.",
                "#",
                "Technical Analysis",
                datetime.now(timezone.utc) - timedelta(hours=12)
            )
        ]
        
        return mock_news[:limit]

# Singleton instance
news_provider = NewsProvider()