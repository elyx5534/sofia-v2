"""
CoinGecko free API - no key required
"""

import asyncio
import httpx
import logging
from typing import Dict, Optional, List
import time

logger = logging.getLogger(__name__)

class CoinGeckoFreeAdapter:
    """CoinGecko free API adapter"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.timeout = 10
        self.cache = {}
        self.cache_ttl = 60  # 1 minute cache
        self.last_request = 0
        self.min_interval = 1.5  # Rate limit: ~40 req/min
        
    async def _rate_limit(self):
        """Simple rate limiting"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request = time.time()
    
    async def get_price(self, symbol: str) -> Optional[Dict]:
        """Get current price"""
        try:
            # Check cache
            cache_key = f"price_{symbol}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached['timestamp'] < self.cache_ttl:
                    return cached['data']
            
            # Convert symbol to CoinGecko ID
            coin_id = self._symbol_to_id(symbol)
            if not coin_id:
                return None
            
            await self._rate_limit()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/simple/price"
                params = {
                    'ids': coin_id,
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                    'include_24hr_vol': 'true'
                }
                
                response = await client.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        result = {
                            'symbol': symbol,
                            'price': price_data.get('usd', 0),
                            'change_24h': price_data.get('usd_24h_change', 0),
                            'volume_24h': price_data.get('usd_24h_vol', 0),
                            'source': 'coingecko'
                        }
                        
                        # Cache result
                        self.cache[cache_key] = {
                            'data': result,
                            'timestamp': time.time()
                        }
                        
                        return result
                        
        except Exception as e:
            logger.error(f"CoinGecko price error for {symbol}: {e}")
        
        return None
    
    async def get_ohlc(self, symbol: str, days: int = 7) -> Optional[List[Dict]]:
        """Get OHLC data"""
        try:
            coin_id = self._symbol_to_id(symbol)
            if not coin_id:
                return None
            
            await self._rate_limit()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/coins/{coin_id}/ohlc"
                params = {
                    'vs_currency': 'usd',
                    'days': min(days, 30)  # Free tier limit
                }
                
                response = await client.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    ohlc = []
                    
                    for candle in data:
                        # [timestamp, open, high, low, close]
                        ohlc.append({
                            'timestamp': candle[0],
                            'open': candle[1],
                            'high': candle[2],
                            'low': candle[3],
                            'close': candle[4]
                        })
                    
                    return ohlc
                    
        except Exception as e:
            logger.error(f"CoinGecko OHLC error for {symbol}: {e}")
        
        return None
    
    def _symbol_to_id(self, symbol: str) -> Optional[str]:
        """Convert trading symbol to CoinGecko ID"""
        # Common crypto mappings
        mapping = {
            'BTC': 'bitcoin',
            'BTC-USD': 'bitcoin',
            'ETH': 'ethereum',
            'ETH-USD': 'ethereum',
            'BNB': 'binancecoin',
            'BNB-USD': 'binancecoin',
            'XRP': 'ripple',
            'XRP-USD': 'ripple',
            'ADA': 'cardano',
            'ADA-USD': 'cardano',
            'DOGE': 'dogecoin',
            'DOGE-USD': 'dogecoin',
            'SOL': 'solana',
            'SOL-USD': 'solana',
            'DOT': 'polkadot',
            'DOT-USD': 'polkadot',
            'MATIC': 'matic-network',
            'MATIC-USD': 'matic-network',
            'AVAX': 'avalanche-2',
            'AVAX-USD': 'avalanche-2',
            'LINK': 'chainlink',
            'LINK-USD': 'chainlink',
            'UNI': 'uniswap',
            'UNI-USD': 'uniswap',
            'ATOM': 'cosmos',
            'ATOM-USD': 'cosmos',
            'LTC': 'litecoin',
            'LTC-USD': 'litecoin'
        }
        
        # Try exact match first
        if symbol.upper() in mapping:
            return mapping[symbol.upper()]
        
        # Try without -USD suffix
        base = symbol.upper().replace('-USD', '')
        if base in mapping:
            return mapping[base]
        
        return None
    
    async def get_trending(self) -> List[Dict]:
        """Get trending coins"""
        try:
            await self._rate_limit()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/search/trending"
                response = await client.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    coins = data.get('coins', [])
                    
                    trending = []
                    for item in coins[:10]:  # Top 10
                        coin = item.get('item', {})
                        trending.append({
                            'id': coin.get('id'),
                            'symbol': coin.get('symbol'),
                            'name': coin.get('name'),
                            'rank': coin.get('market_cap_rank')
                        })
                    
                    return trending
                    
        except Exception as e:
            logger.error(f"CoinGecko trending error: {e}")
        
        return []

# Global instance
coingecko_adapter = CoinGeckoFreeAdapter()