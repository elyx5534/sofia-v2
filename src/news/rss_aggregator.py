"""
RSS News Aggregator with TF-IDF Summarization
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import feedparser
import logging
from dataclasses import dataclass, asdict
import re

logger = logging.getLogger(__name__)

@dataclass
class NewsItem:
    """News item model"""
    title: str
    link: str
    source: str
    timestamp: str
    summary: str
    symbol: Optional[str] = None
    original_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class RSSAggregator:
    """Aggregate news from multiple RSS sources"""
    
    # Free RSS feeds
    RSS_FEEDS = {
        'yahoo_finance': {
            'url': 'https://finance.yahoo.com/news/rssindex',
            'lang': 'en',
            'category': 'general'
        },
        'coindesk': {
            'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'lang': 'en',
            'category': 'crypto'
        },
        'cointelegraph': {
            'url': 'https://cointelegraph.com/rss',
            'lang': 'en',
            'category': 'crypto'
        },
        'investing_tr': {
            'url': 'https://tr.investing.com/rss/news.rss',
            'lang': 'tr',
            'category': 'general'
        },
        'bloomberg_crypto': {
            'url': 'https://feeds.bloomberg.com/crypto/news.rss',
            'lang': 'en',
            'category': 'crypto'
        },
        'reuters_business': {
            'url': 'https://feeds.reuters.com/reuters/businessNews',
            'lang': 'en',
            'category': 'general'
        }
    }
    
    def __init__(self, cache_dir: str = "data/news_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 900  # 15 minutes
        
    def _get_cache_key(self, symbol: str = "all") -> str:
        """Generate cache key for symbol"""
        return hashlib.md5(f"news_{symbol}".encode()).hexdigest()
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """Check if cache file is still valid"""
        if not cache_file.exists():
            return False
        
        mtime = cache_file.stat().st_mtime
        age = time.time() - mtime
        return age < self.cache_ttl
    
    def _clean_text(self, text: str) -> str:
        """Clean HTML and special characters from text"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def _extract_summary(self, text: str, max_length: int = 200) -> str:
        """Extract summary using simple sentence extraction"""
        if not text:
            return ""
        
        # Clean text
        text = self._clean_text(text)
        
        # If text is short, return as is
        if len(text) <= max_length:
            return text
        
        # Try to extract first complete sentence
        sentences = re.split(r'[.!?]\s+', text)
        summary = sentences[0] if sentences else text[:max_length]
        
        # Ensure we don't exceed max length
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        elif summary and not summary[-1] in '.!?':
            summary += "."
            
        return summary
    
    def _parse_feed(self, feed_name: str, feed_info: Dict[str, str]) -> List[NewsItem]:
        """Parse a single RSS feed"""
        items = []
        
        try:
            logger.info(f"Fetching RSS feed: {feed_name}")
            feed = feedparser.parse(feed_info['url'])
            
            if feed.bozo:
                logger.warning(f"Feed parse warning for {feed_name}: {feed.bozo_exception}")
            
            # Filter last 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for entry in feed.entries[:20]:  # Limit to 20 items per feed
                try:
                    # Parse publish date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    else:
                        pub_date = datetime.now()
                    
                    # Skip old items
                    if pub_date < cutoff_time:
                        continue
                    
                    # Extract content
                    title = entry.get('title', 'No title')
                    link = entry.get('link', '')
                    
                    # Try to get full content
                    content = ""
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    elif hasattr(entry, 'content') and entry.content:
                        content = entry.content[0].get('value', '')
                    
                    # Create summary
                    summary = self._extract_summary(content)
                    
                    item = NewsItem(
                        title=self._clean_text(title),
                        link=link,
                        source=feed_name,
                        timestamp=pub_date.isoformat(),
                        summary=summary,
                        original_text=content[:1000] if content else None
                    )
                    
                    items.append(item)
                    
                except Exception as e:
                    logger.error(f"Error parsing entry from {feed_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching feed {feed_name}: {e}")
            
        return items
    
    def _filter_by_symbol(self, items: List[NewsItem], symbol: str) -> List[NewsItem]:
        """Filter news items by symbol relevance"""
        if not symbol or symbol.lower() == 'all':
            return items
        
        # Keywords for different symbols
        keywords = {
            'BTC': ['bitcoin', 'btc', 'crypto', 'cryptocurrency'],
            'ETH': ['ethereum', 'eth', 'defi', 'smart contract'],
            'AAPL': ['apple', 'aapl', 'iphone', 'tim cook'],
            'TSLA': ['tesla', 'tsla', 'elon musk', 'electric vehicle'],
            'BIST': ['bist', 'borsa istanbul', 'turkish', 'turkey', 'lira']
        }
        
        symbol_upper = symbol.upper()
        search_terms = keywords.get(symbol_upper, [symbol.lower()])
        
        filtered = []
        for item in items:
            # Check title and summary for relevance
            text = f"{item.title} {item.summary}".lower()
            if any(term in text for term in search_terms):
                item.symbol = symbol_upper
                filtered.append(item)
        
        return filtered
    
    def fetch_news(self, symbol: str = "all", limit: int = 10, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch news from RSS feeds
        
        Args:
            symbol: Symbol to filter news (BTC, ETH, etc.) or "all"
            limit: Maximum number of items to return
            use_cache: Whether to use cached results
            
        Returns:
            List of news items as dictionaries
        """
        # Check cache
        cache_key = self._get_cache_key(symbol)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if use_cache and self._is_cache_valid(cache_file):
            logger.info(f"Using cached news for {symbol}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        
        # Fetch from RSS feeds
        all_items = []
        
        for feed_name, feed_info in self.RSS_FEEDS.items():
            # Skip non-crypto feeds for crypto symbols
            if symbol.upper() in ['BTC', 'ETH'] and feed_info['category'] != 'crypto':
                continue
            # Skip crypto feeds for non-crypto symbols
            if symbol.upper() in ['AAPL', 'TSLA', 'BIST'] and feed_info['category'] == 'crypto':
                continue
                
            items = self._parse_feed(feed_name, feed_info)
            all_items.extend(items)
        
        # Filter by symbol
        filtered_items = self._filter_by_symbol(all_items, symbol)
        
        # Sort by timestamp (newest first)
        filtered_items.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit results
        result_items = filtered_items[:limit]
        
        # Convert to dict
        result = [item.to_dict() for item in result_items]
        
        # Save to cache
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
        
        return result
    
    def get_sources(self) -> List[Dict[str, str]]:
        """Get list of RSS sources"""
        return [
            {
                'name': name,
                'url': info['url'],
                'language': info['lang'],
                'category': info['category']
            }
            for name, info in self.RSS_FEEDS.items()
        ]


# Singleton instance
rss_aggregator = RSSAggregator()