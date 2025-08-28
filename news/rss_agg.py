"""
RSS aggregator for crypto news sources
Supports Coindesk, Cointelegraph, Decrypt, TheBlock with ETag/If-Modified-Since optimization
"""

import asyncio
import logging
import os
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Set
from datetime import datetime, timezone
from urllib.parse import urlparse
import aiohttp
import feedparser
import redis.asyncio as redis
from bs4 import BeautifulSoup
from prometheus_client import Counter, Histogram, Gauge
import json
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
NEWS_FETCHES = Counter('news_fetches_total', 'Total news fetches', ['source'])
FETCH_ERRORS = Counter('news_fetch_errors_total', 'Fetch errors by source', ['source', 'error_type'])
FETCH_LATENCY = Histogram('news_fetch_latency_seconds', 'Fetch latency by source', ['source'])
ARTICLES_PROCESSED = Counter('news_articles_processed_total', 'Articles processed', ['source'])
CACHE_HITS = Counter('news_cache_hits_total', 'Cache hits (ETag/Last-Modified)', ['source'])
DUPLICATE_ARTICLES = Counter('news_duplicates_total', 'Duplicate articles filtered', ['source'])
SOURCE_HEALTH = Gauge('news_source_health', 'Source health (0-1)', ['source'])


@dataclass
class NewsArticle:
    """Standardized news article structure"""
    title: str
    url: str
    source: str
    timestamp: float
    published: str  # ISO format
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = None
    sentiment_score: Optional[float] = None  # -1 to 1
    crypto_mentioned: List[str] = None  # Detected crypto symbols
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.crypto_mentioned is None:
            self.crypto_mentioned = []
    
    def get_hash(self) -> str:
        """Generate unique hash for deduplication"""
        content = f"{self.title}:{self.url}:{self.published}"
        return hashlib.md5(content.encode()).hexdigest()


class RSSSource:
    """RSS feed source configuration"""
    
    def __init__(self, name: str, url: str, **kwargs):
        self.name = name
        self.url = url
        self.enabled = kwargs.get('enabled', True)
        self.fetch_interval = kwargs.get('fetch_interval', 300)  # 5 minutes
        self.timeout = kwargs.get('timeout', 30)
        self.user_agent = kwargs.get('user_agent', 'Mozilla/5.0 (compatible; NewsBot/1.0)')
        self.max_articles = kwargs.get('max_articles', 50)
        
        # HTTP caching headers
        self.etag = None
        self.last_modified = None
        
        # Health tracking
        self.healthy = True
        self.error_count = 0
        self.last_error = None
        self.last_fetch = 0
        self.last_success = 0


class CryptoKeywordDetector:
    """Detect cryptocurrency mentions in text"""
    
    def __init__(self):
        # Major cryptocurrencies and their aliases
        self.crypto_keywords = {
            'BTC': ['bitcoin', 'btc', 'satoshi'],
            'ETH': ['ethereum', 'eth', 'ether'],
            'SOL': ['solana', 'sol'],
            'ADA': ['cardano', 'ada'],
            'DOT': ['polkadot', 'dot'],
            'LINK': ['chainlink', 'link'],
            'MATIC': ['polygon', 'matic'],
            'AVAX': ['avalanche', 'avax'],
            'ALGO': ['algorand', 'algo'],
            'ATOM': ['cosmos', 'atom'],
            'XRP': ['ripple', 'xrp'],
            'LTC': ['litecoin', 'ltc'],
            'BCH': ['bitcoin cash', 'bch'],
            'DOGE': ['dogecoin', 'doge'],
            'SHIB': ['shiba inu', 'shib'],
            'UNI': ['uniswap', 'uni'],
            'AAVE': ['aave'],
            'COMP': ['compound', 'comp'],
            'MKR': ['maker', 'mkr'],
            'CRV': ['curve', 'crv'],
            'SUSHI': ['sushiswap', 'sushi'],
            'YFI': ['yearn', 'yfi'],
            'SNX': ['synthetix', 'snx']
        }
        
        # DeFi and Web3 keywords
        self.defi_keywords = [
            'defi', 'decentralized finance', 'yield farming', 'liquidity mining',
            'staking', 'smart contract', 'dapp', 'dao', 'nft', 'web3', 'metaverse'
        ]
    
    def detect_cryptos(self, text: str) -> List[str]:
        """Detect cryptocurrency mentions in text"""
        text_lower = text.lower()
        detected = set()
        
        for crypto, keywords in self.crypto_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected.add(crypto)
                    break
        
        return list(detected)
    
    def calculate_sentiment_score(self, text: str) -> float:
        """Simple sentiment analysis (placeholder for more sophisticated model)"""
        text_lower = text.lower()
        
        positive_words = [
            'bullish', 'moon', 'pump', 'surge', 'rally', 'breakout', 'gain',
            'profit', 'up', 'rise', 'increase', 'growth', 'adoption', 'partnership'
        ]
        
        negative_words = [
            'bearish', 'dump', 'crash', 'fall', 'drop', 'decline', 'loss',
            'down', 'decrease', 'hack', 'scam', 'regulation', 'ban', 'fear'
        ]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Normalize to -1 to 1 range
        return (positive_count - negative_count) / total


class RSSAggregator:
    """RSS news aggregator with caching and deduplication"""
    
    def __init__(self):
        self.sources = []
        self.redis_client = None
        self.session = None
        self.keyword_detector = CryptoKeywordDetector()
        self.processed_articles = set()  # Article hashes for deduplication
        self.running = False
        
        # Configuration
        self.max_concurrent = int(os.getenv('NEWS_MAX_CONCURRENT', '5'))
        self.dedup_window = int(os.getenv('NEWS_DEDUP_WINDOW_HOURS', '24')) * 3600
        self.redis_ttl = int(os.getenv('NEWS_REDIS_TTL_HOURS', '48')) * 3600
        
        # User agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        self._setup_sources()
    
    def _setup_sources(self):
        """Setup RSS sources"""
        # Coindesk
        self.sources.append(RSSSource(
            name='coindesk',
            url='https://www.coindesk.com/arc/outboundfeeds/rss/',
            fetch_interval=180  # 3 minutes
        ))
        
        # Cointelegraph
        self.sources.append(RSSSource(
            name='cointelegraph',
            url='https://cointelegraph.com/rss',
            fetch_interval=180
        ))
        
        # Decrypt
        self.sources.append(RSSSource(
            name='decrypt',
            url='https://decrypt.co/feed',
            fetch_interval=300  # 5 minutes
        ))
        
        # The Block
        self.sources.append(RSSSource(
            name='theblock',
            url='https://www.theblockcrypto.com/rss.xml',
            fetch_interval=240  # 4 minutes
        ))
        
        # CryptoSlate
        self.sources.append(RSSSource(
            name='cryptoslate',
            url='https://cryptoslate.com/feed/',
            fetch_interval=300
        ))
        
        # Bitcoin Magazine
        self.sources.append(RSSSource(
            name='bitcoinmagazine',
            url='https://bitcoinmagazine.com/.rss/full/',
            fetch_interval=360  # 6 minutes
        ))
        
        # Filter enabled sources
        enabled_sources = os.getenv('NEWS_ENABLED_SOURCES', 'all').split(',')
        if 'all' not in enabled_sources:
            self.sources = [s for s in self.sources if s.name in enabled_sources]
        
        logger.info(f"Configured {len(self.sources)} RSS sources")
    
    def get_random_user_agent(self) -> str:
        """Get random user agent for requests"""
        return random.choice(self.user_agents)
    
    async def start(self):
        """Start RSS aggregation"""
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        self.running = True
        logger.info("Starting RSS aggregator")
        
        # Start fetching loop
        fetch_task = asyncio.create_task(self.fetch_loop())
        cleanup_task = asyncio.create_task(self.cleanup_loop())
        
        await asyncio.gather(fetch_task, cleanup_task, return_exceptions=True)
    
    async def fetch_loop(self):
        """Main fetching loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # Find sources that need fetching
                sources_to_fetch = [
                    source for source in self.sources
                    if source.enabled and 
                       current_time - source.last_fetch >= source.fetch_interval
                ]
                
                if sources_to_fetch:
                    logger.info(f"Fetching {len(sources_to_fetch)} RSS sources")
                    
                    # Create semaphore for concurrent fetching
                    semaphore = asyncio.Semaphore(self.max_concurrent)
                    
                    # Fetch sources concurrently
                    tasks = []
                    for source in sources_to_fetch:
                        task = asyncio.create_task(self.fetch_source(source, semaphore))
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Sleep for a short interval
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Fetch loop error: {e}")
                await asyncio.sleep(30)
    
    async def fetch_source(self, source: RSSSource, semaphore: asyncio.Semaphore):
        """Fetch articles from RSS source"""
        async with semaphore:
            start_time = time.time()
            source.last_fetch = start_time
            
            try:
                headers = {
                    'User-Agent': self.get_random_user_agent(),
                    'Accept': 'application/rss+xml, application/xml, text/xml'
                }
                
                # Add caching headers if available
                if source.etag:
                    headers['If-None-Match'] = source.etag
                if source.last_modified:
                    headers['If-Modified-Since'] = source.last_modified
                
                async with self.session.get(source.url, headers=headers) as response:
                    # Handle 304 Not Modified
                    if response.status == 304:
                        CACHE_HITS.labels(source=source.name).inc()
                        logger.debug(f"{source.name}: Not modified (304)")
                        self._update_source_health(source, True)
                        return
                    
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    # Update caching headers
                    source.etag = response.headers.get('ETag')
                    source.last_modified = response.headers.get('Last-Modified')
                    
                    # Parse RSS feed
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    if not feed.entries:
                        logger.warning(f"{source.name}: No entries found")
                        return
                    
                    # Process articles
                    articles_processed = 0
                    for entry in feed.entries[:source.max_articles]:
                        article = await self.parse_article(entry, source)
                        if article and await self.process_article(article):
                            articles_processed += 1
                    
                    source.last_success = time.time()
                    
                    NEWS_FETCHES.labels(source=source.name).inc()
                    FETCH_LATENCY.labels(source=source.name).observe(time.time() - start_time)
                    ARTICLES_PROCESSED.labels(source=source.name).inc(articles_processed)
                    
                    self._update_source_health(source, True)
                    logger.info(f"{source.name}: Processed {articles_processed} articles")
                    
            except Exception as e:
                logger.error(f"{source.name} fetch error: {e}")
                FETCH_ERRORS.labels(source=source.name, error_type=type(e).__name__).inc()
                source.last_error = str(e)
                self._update_source_health(source, False)
    
    async def parse_article(self, entry: Any, source: RSSSource) -> Optional[NewsArticle]:
        """Parse RSS entry into NewsArticle"""
        try:
            # Extract basic information
            title = entry.get('title', '').strip()
            url = entry.get('link', '').strip()
            
            if not title or not url:
                return None
            
            # Parse publish date
            published_parsed = entry.get('published_parsed')
            if published_parsed:
                published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                published_iso = published_dt.isoformat()
                timestamp = published_dt.timestamp()
            else:
                # Fallback to current time
                published_dt = datetime.now(timezone.utc)
                published_iso = published_dt.isoformat()
                timestamp = published_dt.timestamp()
            
            # Extract summary/description
            summary = entry.get('summary', '').strip()
            if summary:
                # Clean HTML tags from summary
                soup = BeautifulSoup(summary, 'html.parser')
                summary = soup.get_text().strip()
            
            # Extract author
            author = entry.get('author', '').strip()
            
            # Extract tags
            tags = []
            if 'tags' in entry:
                tags = [tag.get('term', '').strip() for tag in entry.tags if tag.get('term')]
            
            # Create article
            article = NewsArticle(
                title=title,
                url=url,
                source=source.name,
                timestamp=timestamp,
                published=published_iso,
                summary=summary,
                author=author,
                tags=tags
            )
            
            # Detect cryptocurrency mentions
            text_content = f"{title} {summary}".lower()
            article.crypto_mentioned = self.keyword_detector.detect_cryptos(text_content)
            
            # Calculate sentiment score
            article.sentiment_score = self.keyword_detector.calculate_sentiment_score(text_content)
            
            return article
            
        except Exception as e:
            logger.error(f"Article parsing error: {e}")
            return None
    
    async def process_article(self, article: NewsArticle) -> bool:
        """Process and publish article"""
        try:
            # Check for duplicates
            article_hash = article.get_hash()
            
            # Check Redis for existing article
            exists = await self.redis_client.exists(f"news:hash:{article_hash}")
            if exists:
                DUPLICATE_ARTICLES.labels(source=article.source).inc()
                return False
            
            # Check local cache
            if article_hash in self.processed_articles:
                DUPLICATE_ARTICLES.labels(source=article.source).inc()
                return False
            
            # Add to local cache
            self.processed_articles.add(article_hash)
            
            # Limit local cache size
            if len(self.processed_articles) > 10000:
                # Remove oldest 10%
                remove_count = 1000
                for _ in range(remove_count):
                    self.processed_articles.pop()
            
            # Store article in Redis
            article_key = f"news:article:{article_hash}"
            hash_key = f"news:hash:{article_hash}"
            
            # Store article data
            article_data = asdict(article)
            await self.redis_client.hset(article_key, mapping=article_data)
            await self.redis_client.expire(article_key, self.redis_ttl)
            
            # Store hash for deduplication
            await self.redis_client.setex(hash_key, self.dedup_window, "1")
            
            # Publish to streams
            await self.publish_to_streams(article)
            
            logger.debug(f"Processed article: {article.title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Article processing error: {e}")
            return False
    
    async def publish_to_streams(self, article: NewsArticle):
        """Publish article to various Redis streams"""
        try:
            # Main news stream
            main_stream = "news.all"
            await self.redis_client.xadd(
                main_stream, 
                asdict(article), 
                maxlen=int(os.getenv('NEWS_STREAM_MAXLEN', '1000')),
                approximate=True
            )
            
            # Source-specific stream
            source_stream = f"news.{article.source}"
            await self.redis_client.xadd(
                source_stream, 
                asdict(article), 
                maxlen=500, 
                approximate=True
            )
            
            # Crypto-specific streams
            for crypto in article.crypto_mentioned:
                crypto_stream = f"news.crypto.{crypto.lower()}"
                await self.redis_client.xadd(
                    crypto_stream, 
                    asdict(article), 
                    maxlen=200, 
                    approximate=True
                )
            
            # Sentiment streams
            if article.sentiment_score is not None:
                if article.sentiment_score > 0.3:
                    sentiment_stream = "news.sentiment.positive"
                elif article.sentiment_score < -0.3:
                    sentiment_stream = "news.sentiment.negative"
                else:
                    sentiment_stream = "news.sentiment.neutral"
                
                await self.redis_client.xadd(
                    sentiment_stream, 
                    asdict(article), 
                    maxlen=500, 
                    approximate=True
                )
            
        except Exception as e:
            logger.error(f"Stream publishing error: {e}")
    
    def _update_source_health(self, source: RSSSource, success: bool):
        """Update source health status"""
        if success:
            source.error_count = max(0, source.error_count - 1)
        else:
            source.error_count += 1
        
        # Health score based on recent errors
        source.healthy = source.error_count < 5
        health_score = max(0, 1 - (source.error_count / 10))
        SOURCE_HEALTH.labels(source=source.name).set(health_score)
    
    async def cleanup_loop(self):
        """Cleanup old data periodically"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up old articles from Redis
                current_time = time.time()
                cutoff_time = current_time - self.redis_ttl
                
                # Scan for old article keys
                async for key in self.redis_client.scan_iter(match="news:article:*"):
                    # Get article timestamp
                    timestamp = await self.redis_client.hget(key, 'timestamp')
                    if timestamp and float(timestamp) < cutoff_time:
                        await self.redis_client.delete(key)
                
                logger.info("Completed cleanup of old articles")
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def stop(self):
        """Stop aggregation and cleanup"""
        self.running = False
        
        if self.session:
            await self.session.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Stopped RSS aggregator")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all sources"""
        status = {
            'healthy': any(s.healthy for s in self.sources),
            'sources': {},
            'total_processed': len(self.processed_articles)
        }
        
        for source in self.sources:
            status['sources'][source.name] = {
                'healthy': source.healthy,
                'enabled': source.enabled,
                'error_count': source.error_count,
                'last_error': source.last_error,
                'last_fetch': source.last_fetch,
                'last_success': source.last_success,
                'etag': source.etag is not None,
                'last_modified': source.last_modified is not None
            }
        
        return status


async def main():
    """Main entry point"""
    logger.info("Starting RSS News Aggregator")
    
    aggregator = RSSAggregator()
    
    try:
        await aggregator.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await aggregator.stop()


if __name__ == "__main__":
    asyncio.run(main())