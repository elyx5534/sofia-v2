"""
Sofia V2 Realtime DataHub - CryptoPanic RSS Ingestor
RSS-based news ingestion with intelligent polling and deduplication
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
import xml.etree.ElementTree as ET

import aiofiles
import feedparser
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ..bus import EventBus, EventType
from ..config import Settings

logger = structlog.get_logger(__name__)

class CryptoPanicRSSIngestor:
    """
    CryptoPanic RSS feed ingestor with intelligent polling
    Features: ETag/Last-Modified support, deduplication, adaptive polling
    """
    
    def __init__(self, event_bus: EventBus, settings: Settings):
        self.event_bus = event_bus
        self.settings = settings
        self.client: Optional[httpx.AsyncClient] = None
        self.is_running = False
        
        # Polling state
        self.last_etag: Optional[str] = None
        self.last_modified: Optional[str] = None
        self.last_poll_time: Optional[datetime] = None
        
        # Deduplication
        self.seen_guids: Set[str] = set()
        self.seen_urls: Set[str] = set()
        self.seen_title_hashes: Set[str] = set()
        
        # News configuration from YAML
        self.news_config = settings.get_news_config()
        self.currencies = self.news_config.get('params', {}).get('currencies', [])
        self.filter_params = self.news_config.get('params', {}).get('filter', '')
        self.region = self.news_config.get('params', {}).get('region', 'en')
        
        # RSS URL construction
        self.base_url = self.news_config.get('endpoints', {}).get('rss_base', 'https://cryptopanic.com/news/rss/')
        self.rss_url = self._build_rss_url()
        
        # Deduplication window
        dedup_config = self.news_config.get('deduplication', {})
        self.dedup_window_minutes = dedup_config.get('window_minutes', 60)
        self.dedup_methods = dedup_config.get('methods', ['guid', 'url', 'title_similarity'])
        
        logger.info("CryptoPanic RSS ingestor initialized",
                   rss_url=self.rss_url,
                   currencies=self.currencies,
                   dedup_window=self.dedup_window_minutes)
    
    def _build_rss_url(self) -> str:
        """Build RSS URL with parameters"""
        params = []
        
        if self.filter_params:
            params.append(f"filter={self.filter_params}")
        
        if self.currencies:
            currencies_str = ",".join(self.currencies)
            params.append(f"currencies={currencies_str}")
        
        if self.region:
            params.append(f"region={self.region}")
        
        url = self.base_url
        if params:
            url += "?" + "&".join(params)
        
        return url
    
    def _is_night_hours(self) -> bool:
        """Check if current time is in night hours (UTC)"""
        current_hour = datetime.now(timezone.utc).hour
        night_hours = self.news_config.get('night_hours', [22, 23, 0, 1, 2, 3, 4, 5, 6, 7])
        return current_hour in night_hours
    
    def _get_poll_interval(self) -> int:
        """Get polling interval based on time of day"""
        if self._is_night_hours():
            return self.settings.news_poll_seconds_night
        return self.settings.news_poll_seconds_day
    
    def _title_hash(self, title: str) -> str:
        """Generate hash for title similarity detection"""
        # Normalize title: lowercase, remove extra spaces, basic cleanup
        normalized = " ".join(title.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _is_duplicate(self, item: Dict[str, Any]) -> bool:
        """Check if news item is duplicate using configured methods"""
        if 'guid' in self.dedup_methods and item.get('guid'):
            if item['guid'] in self.seen_guids:
                return True
            self.seen_guids.add(item['guid'])
        
        if 'url' in self.dedup_methods and item.get('url'):
            if item['url'] in self.seen_urls:
                return True
            self.seen_urls.add(item['url'])
        
        if 'title_similarity' in self.dedup_methods and item.get('title'):
            title_hash = self._title_hash(item['title'])
            if title_hash in self.seen_title_hashes:
                return True
            self.seen_title_hashes.add(title_hash)
        
        return False
    
    def _cleanup_old_entries(self):
        """Clean up old deduplication entries"""
        # For simplicity, clear all entries periodically
        # In production, you might want time-based cleanup
        max_entries = 10000  # Arbitrary limit
        
        if len(self.seen_guids) > max_entries:
            self.seen_guids.clear()
            self.seen_urls.clear()
            self.seen_title_hashes.clear()
            logger.info("Cleaned up deduplication cache")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _fetch_rss(self) -> Optional[str]:
        """Fetch RSS feed with retry logic and conditional requests"""
        headers = {
            'User-Agent': 'Sofia-v2-DataHub/0.1.0',
            'Accept': 'application/rss+xml, application/xml, text/xml'
        }
        
        # Add conditional request headers
        if self.last_etag:
            headers['If-None-Match'] = self.last_etag
        if self.last_modified:
            headers['If-Modified-Since'] = self.last_modified
        
        try:
            response = await self.client.get(self.rss_url, headers=headers, timeout=30.0)
            
            # Handle 304 Not Modified
            if response.status_code == 304:
                logger.debug("RSS feed not modified (304)")
                return None
            
            response.raise_for_status()
            
            # Update ETag and Last-Modified for next request
            self.last_etag = response.headers.get('ETag')
            self.last_modified = response.headers.get('Last-Modified')
            
            logger.debug("RSS feed fetched successfully",
                        status_code=response.status_code,
                        content_length=len(response.content),
                        etag=self.last_etag)
            
            return response.text
            
        except httpx.TimeoutException:
            logger.warning("RSS fetch timeout")
            raise
        except httpx.HTTPStatusError as e:
            logger.error("RSS fetch HTTP error", status_code=e.response.status_code, url=self.rss_url)
            raise
        except Exception as e:
            logger.error("RSS fetch failed", error=str(e))
            raise
    
    def _parse_rss_item(self, entry) -> Optional[Dict[str, Any]]:
        """Parse RSS entry into standardized news item"""
        try:
            # Extract timestamp
            published_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_time = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).isoformat()
            
            item = {
                'guid': getattr(entry, 'id', None) or getattr(entry, 'guid', None),
                'title': getattr(entry, 'title', ''),
                'summary': getattr(entry, 'summary', ''),
                'url': getattr(entry, 'link', ''),
                'published_at': published_time,
                'source': 'cryptopanic',
                'tags': [tag.term for tag in getattr(entry, 'tags', [])],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Validate required fields
            if not item['title'] or not item['url']:
                logger.warning("RSS item missing required fields", item=item)
                return None
            
            return item
            
        except Exception as e:
            logger.error("Failed to parse RSS entry", error=str(e))
            return None
    
    async def _process_rss_feed(self, rss_content: str):
        """Process RSS feed content and emit news events"""
        try:
            # Parse RSS with feedparser
            feed = feedparser.parse(rss_content)
            
            if feed.bozo:
                logger.warning("RSS feed has parsing issues", bozo_exception=str(feed.bozo_exception))
            
            new_items = 0
            duplicate_items = 0
            
            for entry in feed.entries:
                item = self._parse_rss_item(entry)
                if not item:
                    continue
                
                # Check for duplicates
                if self._is_duplicate(item):
                    duplicate_items += 1
                    continue
                
                # Emit news event
                await self.event_bus.publish(EventType.NEWS, item)
                new_items += 1
                
                logger.debug("New news item", title=item['title'][:100], url=item['url'])
            
            logger.info("RSS feed processed",
                       total_entries=len(feed.entries),
                       new_items=new_items,
                       duplicates=duplicate_items)
            
            # Cleanup old deduplication entries periodically
            self._cleanup_old_entries()
            
        except Exception as e:
            logger.error("Failed to process RSS feed", error=str(e))
    
    async def _poll_loop(self):
        """Main polling loop"""
        logger.info("Starting RSS polling loop")
        
        while self.is_running:
            try:
                poll_interval = self._get_poll_interval()
                
                # Fetch and process RSS feed
                rss_content = await self._fetch_rss()
                
                if rss_content:
                    await self._process_rss_feed(rss_content)
                
                self.last_poll_time = datetime.now(timezone.utc)
                
                # Wait for next poll
                await asyncio.sleep(poll_interval)
                
            except asyncio.CancelledError:
                logger.info("RSS polling cancelled")
                break
            except Exception as e:
                logger.error("RSS polling error", error=str(e))
                # Back off on error
                await asyncio.sleep(60)
    
    async def start(self):
        """Start the RSS ingestor"""
        if self.is_running:
            return
        
        self.is_running = True
        self.client = httpx.AsyncClient()
        
        logger.info("Starting CryptoPanic RSS ingestor")
        await self._poll_loop()
    
    async def stop(self):
        """Stop the RSS ingestor"""
        self.is_running = False
        if self.client:
            await self.client.aclose()
        logger.info("CryptoPanic RSS ingestor stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get ingestor status"""
        return {
            'running': self.is_running,
            'last_poll': self.last_poll_time.isoformat() if self.last_poll_time else None,
            'poll_interval': self._get_poll_interval(),
            'night_mode': self._is_night_hours(),
            'dedup_cache_size': {
                'guids': len(self.seen_guids),
                'urls': len(self.seen_urls),
                'title_hashes': len(self.seen_title_hashes)
            },
            'rss_url': self.rss_url
        }