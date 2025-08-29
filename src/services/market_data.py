"""
Market Data Service with WebSocket -> REST -> yfinance fallback
"""

import asyncio
import json
import time
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Data source types"""
    WEBSOCKET = "websocket"
    REST_CCXT = "ccxt"
    YFINANCE = "yfinance"
    CACHE = "cache"
    MOCK = "mock"


@dataclass
class MarketQuote:
    """Market quote data"""
    symbol: str
    price: str  # Decimal string
    change_24h: str
    change_percent_24h: str
    volume_24h: str
    high_24h: str
    low_24h: str
    timestamp: str
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class OHLCVBar:
    """OHLCV bar data"""
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MarketDataCache:
    """Simple TTL cache for market data"""
    
    def __init__(self):
        self.quotes_cache: Dict[str, Tuple[MarketQuote, float]] = {}
        self.ohlcv_cache: Dict[str, Tuple[List[OHLCVBar], float]] = {}
        self.quotes_ttl = 5  # 5 seconds for quotes
        self.ohlcv_ttl = 30  # 30 seconds for OHLCV
        
    def get_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Get cached quote if valid"""
        if symbol in self.quotes_cache:
            quote, timestamp = self.quotes_cache[symbol]
            if time.time() - timestamp < self.quotes_ttl:
                return quote
        return None
    
    def set_quote(self, symbol: str, quote: MarketQuote):
        """Cache a quote"""
        self.quotes_cache[symbol] = (quote, time.time())
    
    def get_ohlcv(self, key: str) -> Optional[List[OHLCVBar]]:
        """Get cached OHLCV if valid"""
        if key in self.ohlcv_cache:
            bars, timestamp = self.ohlcv_cache[key]
            if time.time() - timestamp < self.ohlcv_ttl:
                return bars
        return None
    
    def set_ohlcv(self, key: str, bars: List[OHLCVBar]):
        """Cache OHLCV bars"""
        self.ohlcv_cache[key] = (bars, time.time())
    
    def clear(self):
        """Clear all cache"""
        self.quotes_cache.clear()
        self.ohlcv_cache.clear()


class MarketDataService:
    """Market data service with multiple fallback sources"""
    
    def __init__(self):
        self.cache = MarketDataCache()
        self.ws_connected = False
        self.last_source = DataSource.MOCK
        self.stats = {
            'ws_hits': 0,
            'rest_hits': 0,
            'yf_hits': 0,
            'cache_hits': 0,
            'mock_hits': 0
        }
    
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get market quote with fallback chain:
        Cache -> WebSocket -> REST (CCXT) -> yfinance -> Mock
        """
        # Check cache first
        cached = self.cache.get_quote(symbol)
        if cached:
            self.stats['cache_hits'] += 1
            self.last_source = DataSource.CACHE
            result = cached.to_dict()
            result['hit'] = 'cache'
            return result
        
        # Try WebSocket (if available)
        if self.ws_connected:
            try:
                quote = await self._fetch_ws_quote(symbol)
                if quote:
                    self.cache.set_quote(symbol, quote)
                    self.stats['ws_hits'] += 1
                    self.last_source = DataSource.WEBSOCKET
                    result = quote.to_dict()
                    result['hit'] = 'live'
                    return result
            except Exception as e:
                logger.warning(f"WebSocket quote failed: {e}")
                self.ws_connected = False
        
        # Try REST (CCXT)
        try:
            quote = await self._fetch_rest_quote(symbol)
            if quote:
                self.cache.set_quote(symbol, quote)
                self.stats['rest_hits'] += 1
                self.last_source = DataSource.REST_CCXT
                result = quote.to_dict()
                result['hit'] = 'live'
                return result
        except Exception as e:
            logger.warning(f"REST quote failed: {e}")
        
        # Try yfinance
        try:
            quote = await self._fetch_yfinance_quote(symbol)
            if quote:
                self.cache.set_quote(symbol, quote)
                self.stats['yf_hits'] += 1
                self.last_source = DataSource.YFINANCE
                result = quote.to_dict()
                result['hit'] = 'live'
                return result
        except Exception as e:
            logger.warning(f"yfinance quote failed: {e}")
        
        # Fallback to mock data
        quote = self._generate_mock_quote(symbol)
        self.cache.set_quote(symbol, quote)
        self.stats['mock_hits'] += 1
        self.last_source = DataSource.MOCK
        result = quote.to_dict()
        result['hit'] = 'mock'
        return result
    
    async def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict[str, Any]:
        """
        Get OHLCV data with fallback chain
        """
        cache_key = f"{symbol}_{timeframe}_{limit}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'bars': [bar.to_dict() for bar in cached],
                'source': 'cache',
                'count': len(cached)
            }
        
        # Try REST (CCXT)
        try:
            bars = await self._fetch_rest_ohlcv(symbol, timeframe, limit)
            if bars:
                self.cache.set_ohlcv(cache_key, bars)
                self.stats['rest_hits'] += 1
                return {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'bars': [bar.to_dict() for bar in bars],
                    'source': 'ccxt',
                    'count': len(bars)
                }
        except Exception as e:
            logger.warning(f"REST OHLCV failed: {e}")
        
        # Try yfinance
        try:
            bars = await self._fetch_yfinance_ohlcv(symbol, timeframe, limit)
            if bars:
                self.cache.set_ohlcv(cache_key, bars)
                self.stats['yf_hits'] += 1
                return {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'bars': [bar.to_dict() for bar in bars],
                    'source': 'yfinance',
                    'count': len(bars)
                }
        except Exception as e:
            logger.warning(f"yfinance OHLCV failed: {e}")
        
        # Generate mock data
        bars = self._generate_mock_ohlcv(symbol, timeframe, limit)
        self.cache.set_ohlcv(cache_key, bars)
        self.stats['mock_hits'] += 1
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'bars': [bar.to_dict() for bar in bars],
            'source': 'mock',
            'count': len(bars)
        }
    
    async def _fetch_ws_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetch quote from WebSocket (placeholder)"""
        # This would connect to actual WebSocket
        return None
    
    async def _fetch_rest_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetch quote from REST API (CCXT)"""
        try:
            import ccxt.async_support as ccxt
            
            exchange = ccxt.binance()
            ticker = await exchange.fetch_ticker(symbol.replace('/', ''))
            await exchange.close()
            
            return MarketQuote(
                symbol=symbol,
                price=str(Decimal(str(ticker['last']))),
                change_24h=str(Decimal(str(ticker['change']))),
                change_percent_24h=str(Decimal(str(ticker['percentage']))),
                volume_24h=str(Decimal(str(ticker['baseVolume']))),
                high_24h=str(Decimal(str(ticker['high']))),
                low_24h=str(Decimal(str(ticker['low']))),
                timestamp=datetime.now().isoformat(),
                source='ccxt'
            )
        except Exception as e:
            logger.error(f"CCXT error: {e}")
            return None
    
    async def _fetch_yfinance_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetch quote from yfinance"""
        try:
            import yfinance as yf
            
            # Convert symbol format
            ticker_symbol = symbol.replace('/USDT', '-USD').replace('/', '-')
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            price = info.get('regularMarketPrice', info.get('ask', 0))
            prev_close = info.get('regularMarketPreviousClose', price)
            
            return MarketQuote(
                symbol=symbol,
                price=str(Decimal(str(price))),
                change_24h=str(Decimal(str(price - prev_close))),
                change_percent_24h=str(Decimal(str((price - prev_close) / prev_close * 100))),
                volume_24h=str(Decimal(str(info.get('regularMarketVolume', 0)))),
                high_24h=str(Decimal(str(info.get('regularMarketDayHigh', price)))),
                low_24h=str(Decimal(str(info.get('regularMarketDayLow', price)))),
                timestamp=datetime.now().isoformat(),
                source='yfinance'
            )
        except Exception as e:
            logger.error(f"yfinance error: {e}")
            return None
    
    async def _fetch_rest_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[List[OHLCVBar]]:
        """Fetch OHLCV from REST API (CCXT)"""
        try:
            import ccxt.async_support as ccxt
            
            exchange = ccxt.binance()
            ohlcv = await exchange.fetch_ohlcv(symbol.replace('/', ''), timeframe, limit=limit)
            await exchange.close()
            
            bars = []
            for candle in ohlcv:
                bars.append(OHLCVBar(
                    timestamp=datetime.fromtimestamp(candle[0]/1000).isoformat(),
                    open=str(Decimal(str(candle[1]))),
                    high=str(Decimal(str(candle[2]))),
                    low=str(Decimal(str(candle[3]))),
                    close=str(Decimal(str(candle[4]))),
                    volume=str(Decimal(str(candle[5])))
                ))
            
            return bars
        except Exception as e:
            logger.error(f"CCXT OHLCV error: {e}")
            return None
    
    async def _fetch_yfinance_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[List[OHLCVBar]]:
        """Fetch OHLCV from yfinance"""
        try:
            import yfinance as yf
            
            # Convert timeframe
            period_map = {
                '1m': '7d',
                '5m': '1mo',
                '15m': '1mo',
                '1h': '3mo',
                '4h': '1y',
                '1d': '2y'
            }
            
            interval_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '1h': '60m',
                '4h': '1d',
                '1d': '1d'
            }
            
            ticker_symbol = symbol.replace('/USDT', '-USD').replace('/', '-')
            ticker = yf.Ticker(ticker_symbol)
            
            df = ticker.history(
                period=period_map.get(timeframe, '3mo'),
                interval=interval_map.get(timeframe, '60m')
            )
            
            if df.empty:
                return None
            
            # Limit rows
            df = df.tail(limit)
            
            bars = []
            for idx, row in df.iterrows():
                bars.append(OHLCVBar(
                    timestamp=idx.isoformat(),
                    open=str(Decimal(str(row['Open']))),
                    high=str(Decimal(str(row['High']))),
                    low=str(Decimal(str(row['Low']))),
                    close=str(Decimal(str(row['Close']))),
                    volume=str(Decimal(str(row['Volume'])))
                ))
            
            return bars
        except Exception as e:
            logger.error(f"yfinance OHLCV error: {e}")
            return None
    
    def _generate_mock_quote(self, symbol: str) -> MarketQuote:
        """Generate mock quote data"""
        import random
        
        base_prices = {
            'BTC/USDT': 67000,
            'ETH/USDT': 3500,
            'BNB/USDT': 600,
            'SOL/USDT': 150,
            'AAPL': 180,
            'TSLA': 250
        }
        
        base_price = base_prices.get(symbol, 100)
        price = base_price * (1 + random.uniform(-0.02, 0.02))
        change_pct = random.uniform(-5, 5)
        
        return MarketQuote(
            symbol=symbol,
            price=str(Decimal(str(price))[:10]),
            change_24h=str(Decimal(str(price * change_pct / 100))[:10]),
            change_percent_24h=str(Decimal(str(change_pct))[:5]),
            volume_24h=str(Decimal(str(random.randint(1000000, 100000000)))),
            high_24h=str(Decimal(str(price * 1.02))[:10]),
            low_24h=str(Decimal(str(price * 0.98))[:10]),
            timestamp=datetime.now().isoformat(),
            source='mock'
        )
    
    def _generate_mock_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[OHLCVBar]:
        """Generate mock OHLCV data"""
        import random
        import numpy as np
        
        bars = []
        base_price = 100
        
        # Generate random walk
        for i in range(limit):
            # Time calculation
            if timeframe == '1h':
                timestamp = datetime.now() - timedelta(hours=limit-i)
            elif timeframe == '1d':
                timestamp = datetime.now() - timedelta(days=limit-i)
            else:
                timestamp = datetime.now() - timedelta(minutes=(limit-i)*5)
            
            # Price movement
            change = random.uniform(-0.02, 0.02)
            base_price *= (1 + change)
            
            high = base_price * (1 + abs(random.uniform(0, 0.01)))
            low = base_price * (1 - abs(random.uniform(0, 0.01)))
            open_price = base_price * (1 + random.uniform(-0.005, 0.005))
            
            bars.append(OHLCVBar(
                timestamp=timestamp.isoformat(),
                open=str(Decimal(str(open_price))[:10]),
                high=str(Decimal(str(high))[:10]),
                low=str(Decimal(str(low))[:10]),
                close=str(Decimal(str(base_price))[:10]),
                volume=str(Decimal(str(random.randint(100000, 10000000))))
            ))
        
        return bars
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status and statistics"""
        return {
            'last_source': self.last_source.value,
            'ws_connected': self.ws_connected,
            'cache_size': {
                'quotes': len(self.cache.quotes_cache),
                'ohlcv': len(self.cache.ohlcv_cache)
            },
            'stats': self.stats,
            'timestamp': datetime.now().isoformat()
        }


# Singleton instance
market_data_service = MarketDataService()