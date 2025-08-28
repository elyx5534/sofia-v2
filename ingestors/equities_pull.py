"""
Equities data ingester with multiple fallback sources
Primary: Alpaca/IEX/Polygon, Fallback-1: Yahoo Finance, Fallback-2: TwelveData/Stooq
"""

import asyncio
import logging
import os
import time
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List, Union
from datetime import datetime, timedelta
import aiohttp
import yfinance as yf
import pandas as pd
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
from cachetools import TTLCache
import hashlib
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
EQUITY_FETCHES = Counter('equity_fetches_total', 'Total equity data fetches', ['source', 'symbol'])
FETCH_ERRORS = Counter('equity_fetch_errors_total', 'Fetch errors by source', ['source', 'error_type'])
FETCH_LATENCY = Histogram('equity_fetch_latency_seconds', 'Fetch latency by source', ['source'])
CACHE_HITS = Counter('equity_cache_hits_total', 'Cache hits', ['source'])
CACHE_SIZE = Gauge('equity_cache_size', 'Cache size', ['source'])
RATE_LIMIT_HITS = Counter('equity_rate_limit_hits_total', 'Rate limit hits', ['source'])
SOURCE_HEALTH = Gauge('equity_source_health', 'Source health (0-1)', ['source'])


@dataclass
class EquityQuote:
    """Standardized equity quote structure"""
    symbol: str
    source: str
    timestamp: float
    price: float
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    
    def to_redis_key(self) -> str:
        """Generate Redis key for publishing"""
        return f"equities.{self.source}.{self.symbol}"


class RateLimiter:
    """Simple rate limiter with leaky bucket algorithm"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old requests
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            # Calculate wait time
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            
            if wait_time > 0:
                logger.debug(f"Rate limit hit, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        self.requests.append(time.time())


class BaseEquityProvider:
    """Base class for equity data providers"""
    
    def __init__(self, name: str):
        self.name = name
        self.session = None
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute TTL
        self.rate_limiter = None
        self.healthy = True
        self.last_error = None
        self.error_count = 0
        
        # User agent rotation for web scraping protection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        ]
    
    def get_random_user_agent(self) -> str:
        """Get random user agent"""
        return random.choice(self.user_agents)
    
    async def start(self):
        """Initialize provider"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': self.get_random_user_agent()}
        )
        logger.info(f"Started {self.name} provider")
    
    async def stop(self):
        """Cleanup provider"""
        if self.session:
            await self.session.close()
        logger.info(f"Stopped {self.name} provider")
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote for symbol - implemented by subclasses"""
        raise NotImplementedError
    
    def _cache_key(self, symbol: str) -> str:
        """Generate cache key"""
        return f"{self.name}:{symbol}"
    
    def _update_health(self, success: bool):
        """Update provider health status"""
        if success:
            self.error_count = max(0, self.error_count - 1)
        else:
            self.error_count += 1
        
        # Health score based on recent errors
        self.healthy = self.error_count < 5
        health_score = max(0, 1 - (self.error_count / 10))
        SOURCE_HEALTH.labels(source=self.name).set(health_score)


class AlpacaProvider(BaseEquityProvider):
    """Alpaca Markets data provider"""
    
    def __init__(self):
        super().__init__("alpaca")
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        self.rate_limiter = RateLimiter(200, 60)  # 200 requests per minute
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote from Alpaca"""
        if not self.api_key or not self.secret_key:
            return None
        
        cache_key = self._cache_key(symbol)
        if cache_key in self.cache:
            CACHE_HITS.labels(source=self.name).inc()
            return self.cache[cache_key]
        
        try:
            await self.rate_limiter.acquire()
            
            headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.secret_key
            }
            
            url = f"{self.base_url}/v2/stocks/{symbol}/quotes/latest"
            
            start_time = time.time()
            async with self.session.get(url, headers=headers) as response:
                if response.status == 429:
                    RATE_LIMIT_HITS.labels(source=self.name).inc()
                    return None
                
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
                quote_data = data['quote']
                
                quote = EquityQuote(
                    symbol=symbol,
                    source=self.name,
                    timestamp=time.time(),
                    price=(float(quote_data['bp']) + float(quote_data['ap'])) / 2,  # Mid price
                    bid=float(quote_data['bp']),
                    ask=float(quote_data['ap']),
                    bid_size=int(quote_data['bs']),
                    ask_size=int(quote_data['as'])
                )
                
                self.cache[cache_key] = quote
                CACHE_SIZE.labels(source=self.name).set(len(self.cache))
                EQUITY_FETCHES.labels(source=self.name, symbol=symbol).inc()
                FETCH_LATENCY.labels(source=self.name).observe(time.time() - start_time)
                self._update_health(True)
                
                return quote
                
        except Exception as e:
            logger.error(f"Alpaca fetch error for {symbol}: {e}")
            FETCH_ERRORS.labels(source=self.name, error_type=type(e).__name__).inc()
            self.last_error = str(e)
            self._update_health(False)
            return None


class IEXProvider(BaseEquityProvider):
    """IEX Cloud data provider"""
    
    def __init__(self):
        super().__init__("iex")
        self.api_key = os.getenv('IEX_API_KEY')
        self.base_url = "https://cloud.iexapis.com/stable"
        self.rate_limiter = RateLimiter(100, 60)  # 100 requests per minute
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote from IEX"""
        if not self.api_key:
            return None
        
        cache_key = self._cache_key(symbol)
        if cache_key in self.cache:
            CACHE_HITS.labels(source=self.name).inc()
            return self.cache[cache_key]
        
        try:
            await self.rate_limiter.acquire()
            
            url = f"{self.base_url}/stock/{symbol}/quote?token={self.api_key}"
            
            start_time = time.time()
            async with self.session.get(url) as response:
                if response.status == 429:
                    RATE_LIMIT_HITS.labels(source=self.name).inc()
                    return None
                
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
                
                quote = EquityQuote(
                    symbol=symbol,
                    source=self.name,
                    timestamp=time.time(),
                    price=float(data['latestPrice']),
                    volume=int(data.get('latestVolume', 0)),
                    high_52w=float(data.get('week52High', 0)) if data.get('week52High') else None,
                    low_52w=float(data.get('week52Low', 0)) if data.get('week52Low') else None,
                    market_cap=float(data.get('marketCap', 0)) if data.get('marketCap') else None,
                    pe_ratio=float(data.get('peRatio', 0)) if data.get('peRatio') else None
                )
                
                self.cache[cache_key] = quote
                CACHE_SIZE.labels(source=self.name).set(len(self.cache))
                EQUITY_FETCHES.labels(source=self.name, symbol=symbol).inc()
                FETCH_LATENCY.labels(source=self.name).observe(time.time() - start_time)
                self._update_health(True)
                
                return quote
                
        except Exception as e:
            logger.error(f"IEX fetch error for {symbol}: {e}")
            FETCH_ERRORS.labels(source=self.name, error_type=type(e).__name__).inc()
            self.last_error = str(e)
            self._update_health(False)
            return None


class YahooFinanceProvider(BaseEquityProvider):
    """Yahoo Finance data provider (fallback-1)"""
    
    def __init__(self):
        super().__init__("yahoo")
        self.rate_limiter = RateLimiter(50, 60)  # 50 requests per minute
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote from Yahoo Finance"""
        cache_key = self._cache_key(symbol)
        if cache_key in self.cache:
            CACHE_HITS.labels(source=self.name).inc()
            return self.cache[cache_key]
        
        try:
            await self.rate_limiter.acquire()
            
            start_time = time.time()
            
            # Use yfinance in async context
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, symbol)
            info = await loop.run_in_executor(None, lambda: ticker.info)
            
            if not info or 'regularMarketPrice' not in info:
                raise Exception("No price data available")
            
            quote = EquityQuote(
                symbol=symbol,
                source=self.name,
                timestamp=time.time(),
                price=float(info['regularMarketPrice']),
                volume=int(info.get('regularMarketVolume', 0)),
                bid=float(info.get('bid', 0)) if info.get('bid') else None,
                ask=float(info.get('ask', 0)) if info.get('ask') else None,
                high_52w=float(info.get('fiftyTwoWeekHigh', 0)) if info.get('fiftyTwoWeekHigh') else None,
                low_52w=float(info.get('fiftyTwoWeekLow', 0)) if info.get('fiftyTwoWeekLow') else None,
                market_cap=float(info.get('marketCap', 0)) if info.get('marketCap') else None,
                pe_ratio=float(info.get('forwardPE', 0)) if info.get('forwardPE') else None,
                dividend_yield=float(info.get('dividendYield', 0)) if info.get('dividendYield') else None
            )
            
            self.cache[cache_key] = quote
            CACHE_SIZE.labels(source=self.name).set(len(self.cache))
            EQUITY_FETCHES.labels(source=self.name, symbol=symbol).inc()
            FETCH_LATENCY.labels(source=self.name).observe(time.time() - start_time)
            self._update_health(True)
            
            return quote
            
        except Exception as e:
            logger.error(f"Yahoo Finance fetch error for {symbol}: {e}")
            FETCH_ERRORS.labels(source=self.name, error_type=type(e).__name__).inc()
            self.last_error = str(e)
            self._update_health(False)
            return None


class TwelveDataProvider(BaseEquityProvider):
    """TwelveData API provider (fallback-2)"""
    
    def __init__(self):
        super().__init__("twelvedata")
        self.api_key = os.getenv('TWELVEDATA_API_KEY')
        self.base_url = "https://api.twelvedata.com"
        self.rate_limiter = RateLimiter(8, 60)  # 8 requests per minute (free tier)
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote from TwelveData"""
        if not self.api_key:
            return None
        
        cache_key = self._cache_key(symbol)
        if cache_key in self.cache:
            CACHE_HITS.labels(source=self.name).inc()
            return self.cache[cache_key]
        
        try:
            await self.rate_limiter.acquire()
            
            url = f"{self.base_url}/quote?symbol={symbol}&apikey={self.api_key}"
            
            start_time = time.time()
            async with self.session.get(url) as response:
                if response.status == 429:
                    RATE_LIMIT_HITS.labels(source=self.name).inc()
                    return None
                
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
                
                if 'code' in data and data['code'] != 200:
                    raise Exception(f"API error: {data.get('message', 'Unknown error')}")
                
                quote = EquityQuote(
                    symbol=symbol,
                    source=self.name,
                    timestamp=time.time(),
                    price=float(data['close']),
                    volume=int(data.get('volume', 0)) if data.get('volume') else None,
                    high_52w=float(data.get('fifty_two_week', {}).get('high', 0)) if data.get('fifty_two_week') else None,
                    low_52w=float(data.get('fifty_two_week', {}).get('low', 0)) if data.get('fifty_two_week') else None
                )
                
                self.cache[cache_key] = quote
                CACHE_SIZE.labels(source=self.name).set(len(self.cache))
                EQUITY_FETCHES.labels(source=self.name, symbol=symbol).inc()
                FETCH_LATENCY.labels(source=self.name).observe(time.time() - start_time)
                self._update_health(True)
                
                return quote
                
        except Exception as e:
            logger.error(f"TwelveData fetch error for {symbol}: {e}")
            FETCH_ERRORS.labels(source=self.name, error_type=type(e).__name__).inc()
            self.last_error = str(e)
            self._update_health(False)
            return None


class StooqProvider(BaseEquityProvider):
    """Stooq data provider (fallback-2 alternative)"""
    
    def __init__(self):
        super().__init__("stooq")
        self.base_url = "https://stooq.com/q/l/"
        self.rate_limiter = RateLimiter(60, 60)  # 60 requests per minute
    
    async def get_quote(self, symbol: str) -> Optional[EquityQuote]:
        """Get quote from Stooq"""
        cache_key = self._cache_key(symbol)
        if cache_key in self.cache:
            CACHE_HITS.labels(source=self.name).inc()
            return self.cache[cache_key]
        
        try:
            await self.rate_limiter.acquire()
            
            # Stooq uses different symbol format for US stocks
            stooq_symbol = f"{symbol.lower()}.us"
            url = f"{self.base_url}?s={stooq_symbol}&f=sl1c1&h&e=csv"
            
            start_time = time.time()
            headers = {'User-Agent': self.get_random_user_agent()}
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                text = await response.text()
                lines = text.strip().split('\n')
                
                if len(lines) < 2:
                    raise Exception("Invalid CSV response")
                
                # Parse CSV: Symbol,Last,Change
                data_line = lines[1].split(',')
                if len(data_line) < 2:
                    raise Exception("Invalid data format")
                
                price = float(data_line[1])
                
                quote = EquityQuote(
                    symbol=symbol,
                    source=self.name,
                    timestamp=time.time(),
                    price=price
                )
                
                self.cache[cache_key] = quote
                CACHE_SIZE.labels(source=self.name).set(len(self.cache))
                EQUITY_FETCHES.labels(source=self.name, symbol=symbol).inc()
                FETCH_LATENCY.labels(source=self.name).observe(time.time() - start_time)
                self._update_health(True)
                
                return quote
                
        except Exception as e:
            logger.error(f"Stooq fetch error for {symbol}: {e}")
            FETCH_ERRORS.labels(source=self.name, error_type=type(e).__name__).inc()
            self.last_error = str(e)
            self._update_health(False)
            return None


class EquityDataManager:
    """Main equity data manager with provider fallback"""
    
    def __init__(self):
        self.redis_client = None
        self.providers = []
        self.symbols = []
        self.running = False
        
        # Configuration
        self.fetch_interval = int(os.getenv('EQUITY_FETCH_INTERVAL', '60'))  # seconds
        self.max_concurrent = int(os.getenv('EQUITY_MAX_CONCURRENT', '10'))
        self.retry_delay = int(os.getenv('EQUITY_RETRY_DELAY', '5'))
        
        # Initialize providers in priority order
        self._setup_providers()
        
        # Load symbols
        self._load_symbols()
    
    def _setup_providers(self):
        """Setup providers in fallback order"""
        # Primary providers
        if os.getenv('ALPACA_API_KEY'):
            self.providers.append(AlpacaProvider())
        
        if os.getenv('IEX_API_KEY'):
            self.providers.append(IEXProvider())
        
        # Fallback providers
        self.providers.append(YahooFinanceProvider())
        
        if os.getenv('TWELVEDATA_API_KEY'):
            self.providers.append(TwelveDataProvider())
        
        self.providers.append(StooqProvider())
        
        logger.info(f"Initialized {len(self.providers)} equity data providers")
    
    def _load_symbols(self):
        """Load symbols from configuration"""
        symbols_env = os.getenv('EQUITY_SYMBOLS', 'AAPL,MSFT,GOOGL,AMZN,TSLA')
        self.symbols = [s.strip().upper() for s in symbols_env.split(',')]
        logger.info(f"Loaded {len(self.symbols)} equity symbols: {self.symbols}")
    
    async def start(self):
        """Start equity data fetching"""
        # Connect to Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        # Start all providers
        for provider in self.providers:
            await provider.start()
        
        self.running = True
        logger.info("Starting equity data fetching")
        
        # Start fetching loop
        fetch_task = asyncio.create_task(self.fetch_loop())
        await fetch_task
    
    async def fetch_loop(self):
        """Main fetching loop"""
        while self.running:
            try:
                start_time = time.time()
                
                # Create semaphore for concurrent fetching
                semaphore = asyncio.Semaphore(self.max_concurrent)
                
                # Fetch all symbols concurrently
                tasks = []
                for symbol in self.symbols:
                    task = asyncio.create_task(self.fetch_symbol(symbol, semaphore))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.fetch_interval - elapsed)
                
                logger.info(f"Fetch cycle completed in {elapsed:.1f}s, sleeping for {sleep_time:.1f}s")
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Fetch loop error: {e}")
                await asyncio.sleep(self.retry_delay)
    
    async def fetch_symbol(self, symbol: str, semaphore: asyncio.Semaphore):
        """Fetch quote for single symbol with provider fallback"""
        async with semaphore:
            quote = None
            
            # Try providers in order until success
            for provider in self.providers:
                if not provider.healthy:
                    continue
                
                try:
                    quote = await provider.get_quote(symbol)
                    if quote:
                        # Normalize symbol to ensure consistency
                        quote.symbol = symbol
                        
                        # Publish to Redis
                        await self.publish_quote(quote)
                        
                        logger.debug(f"Fetched {symbol} from {provider.name}: ${quote.price}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Provider {provider.name} failed for {symbol}: {e}")
                    continue
            
            if not quote:
                logger.error(f"All providers failed for {symbol}")
    
    async def publish_quote(self, quote: EquityQuote):
        """Publish quote to Redis Stream"""
        try:
            stream_key = quote.to_redis_key()
            quote_data = asdict(quote)
            
            # Add to Redis Stream with MAXLEN to prevent unbounded growth
            max_len = int(os.getenv('REDIS_STREAM_MAXLEN', '1000'))
            await self.redis_client.xadd(stream_key, quote_data, maxlen=max_len, approximate=True)
            
            logger.debug(f"Published quote: {stream_key} -> ${quote.price}")
            
        except Exception as e:
            logger.error(f"Redis publish error: {e}")
    
    async def stop(self):
        """Stop fetching and cleanup"""
        self.running = False
        
        # Stop all providers
        for provider in self.providers:
            await provider.stop()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Stopped equity data manager")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all providers"""
        status = {
            'healthy': any(p.healthy for p in self.providers),
            'symbols': self.symbols,
            'providers': {}
        }
        
        for provider in self.providers:
            status['providers'][provider.name] = {
                'healthy': provider.healthy,
                'error_count': provider.error_count,
                'last_error': provider.last_error,
                'cache_size': len(provider.cache)
            }
        
        return status


async def main():
    """Main entry point"""
    logger.info("Starting Equity Data Ingester")
    
    manager = EquityDataManager()
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())