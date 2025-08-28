"""
CoinGecko free API provider for cryptocurrency prices
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any
import httpx

logger = logging.getLogger(__name__)


class CoinGeckoFreeProvider:
    """Free CoinGecko API provider (no API key required)"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_ttl = 30  # 30 seconds cache
        
        # CoinGecko IDs mapping
        self.coin_ids = {
            'BTC-USD': 'bitcoin',
            'ETH-USD': 'ethereum',
            'SOL-USD': 'solana',
            'BNB-USD': 'binancecoin',
            'ADA-USD': 'cardano',
            'XRP-USD': 'ripple',
            'DOT-USD': 'polkadot',
            'DOGE-USD': 'dogecoin',
            'AVAX-USD': 'avalanche-2',
            'SHIB-USD': 'shiba-inu',
            'MATIC-USD': 'polygon',
            'LTC-USD': 'litecoin',
            'UNI-USD': 'uniswap',
            'LINK-USD': 'chainlink',
            'ATOM-USD': 'cosmos',
            'XLM-USD': 'stellar',
            'ALGO-USD': 'algorand',
            'VET-USD': 'vechain',
            'FTM-USD': 'fantom',
            'FIL-USD': 'filecoin'
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2  # 2 seconds between requests (free tier limit)
    
    async def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get price for a symbol"""
        coin_id = self.coin_ids.get(symbol)
        if not coin_id:
            logger.warning(f"No CoinGecko mapping for symbol: {symbol}")
            return None
        
        # Check cache
        cache_key = f"{coin_id}_usd"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            age = time.time() - cached['timestamp']
            if age < self.cache_ttl:
                return {
                    'symbol': symbol,
                    'price': cached['price'],
                    'source': 'coingecko_cache',
                    'freshness': age
                }
        
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        # Fetch from API
        try:
            self.last_request_time = time.time()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/simple/price",
                    params={
                        'ids': coin_id,
                        'vs_currencies': 'usd',
                        'include_24hr_change': 'true'
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if coin_id in data and 'usd' in data[coin_id]:
                        price = data[coin_id]['usd']
                        change_24h = data[coin_id].get('usd_24h_change', 0)
                        
                        # Update cache
                        self.cache[cache_key] = {
                            'price': price,
                            'change_24h': change_24h,
                            'timestamp': time.time()
                        }
                        
                        logger.info(f"CoinGecko price for {symbol}: ${price:.2f} ({change_24h:+.2f}%)")
                        
                        return {
                            'symbol': symbol,
                            'price': price,
                            'change_percent': change_24h,
                            'source': 'coingecko',
                            'freshness': 0
                        }
                    else:
                        logger.error(f"No price data in CoinGecko response for {coin_id}")
                        return None
                        
                elif response.status_code == 429:
                    logger.warning("CoinGecko rate limit hit - backing off")
                    self.min_request_interval *= 2  # Double the interval
                    return None
                else:
                    logger.error(f"CoinGecko API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"CoinGecko fetch error for {symbol}: {e}")
            return None
    
    async def get_multiple_prices(self, symbols: list) -> Dict[str, Dict[str, Any]]:
        """Get prices for multiple symbols"""
        # Map symbols to coin IDs
        coin_ids_list = []
        symbol_map = {}
        
        for symbol in symbols:
            coin_id = self.coin_ids.get(symbol)
            if coin_id:
                coin_ids_list.append(coin_id)
                symbol_map[coin_id] = symbol
        
        if not coin_ids_list:
            return {}
        
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        
        try:
            self.last_request_time = time.time()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/simple/price",
                    params={
                        'ids': ','.join(coin_ids_list),
                        'vs_currencies': 'usd',
                        'include_24hr_change': 'true'
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = {}
                    
                    for coin_id, symbol in symbol_map.items():
                        if coin_id in data and 'usd' in data[coin_id]:
                            price = data[coin_id]['usd']
                            change_24h = data[coin_id].get('usd_24h_change', 0)
                            
                            # Update cache
                            cache_key = f"{coin_id}_usd"
                            self.cache[cache_key] = {
                                'price': price,
                                'change_24h': change_24h,
                                'timestamp': time.time()
                            }
                            
                            results[symbol] = {
                                'symbol': symbol,
                                'price': price,
                                'change_percent': change_24h,
                                'source': 'coingecko',
                                'freshness': 0
                            }
                    
                    logger.info(f"CoinGecko fetched {len(results)} prices")
                    return results
                    
                elif response.status_code == 429:
                    logger.warning("CoinGecko rate limit hit - backing off")
                    self.min_request_interval *= 2
                    return {}
                else:
                    logger.error(f"CoinGecko API error: {response.status_code}")
                    return {}
                    
        except Exception as e:
            logger.error(f"CoinGecko batch fetch error: {e}")
            return {}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get provider metrics"""
        return {
            'cache_size': len(self.cache),
            'cache_ttl': self.cache_ttl,
            'rate_limit_interval': self.min_request_interval,
            'last_request_time': self.last_request_time,
            'supported_symbols': len(self.coin_ids)
        }


# Global instance
coingecko_provider = CoinGeckoFreeProvider()