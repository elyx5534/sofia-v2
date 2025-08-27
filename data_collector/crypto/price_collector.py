"""
Free Crypto Price Collector
Collects real-time crypto prices from multiple free sources without API limits
"""

import asyncio
import aiohttp
import ccxt.async_support as ccxt
import websockets
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
import random

logger = logging.getLogger(__name__)

class FreeCryptoPriceCollector:
    """Comprehensive free crypto price collection system"""
    
    def __init__(self, config):
        self.config = config
        self.exchanges = {}
        self.websocket_connections = {}
        self.price_cache = {}
        self.session = None
        
    async def start(self):
        """Initialize all price collection methods"""
        self.session = aiohttp.ClientSession()
        await self.init_exchanges()
        await self.start_websocket_streams()
        logger.info("Free Crypto Price Collector started")
        
    async def stop(self):
        """Cleanup connections"""
        if self.session:
            await self.session.close()
        for exchange in self.exchanges.values():
            await exchange.close()
        logger.info("Free Crypto Price Collector stopped")
        
    async def init_exchanges(self):
        """Initialize free exchange APIs"""
        try:
            # Free exchanges with good rate limits
            self.exchanges = {
                'binance': ccxt.binance({'enableRateLimit': True, 'sandbox': False}),
                'coinbase': ccxt.coinbasepro({'enableRateLimit': True}),
                'kraken': ccxt.kraken({'enableRateLimit': True}),
                'kucoin': ccxt.kucoin({'enableRateLimit': True}),
                'bybit': ccxt.bybit({'enableRateLimit': True})
            }
            logger.info(f"Initialized {len(self.exchanges)} free exchanges")
        except Exception as e:
            logger.error(f"Error initializing exchanges: {e}")
            
    async def get_coingecko_data(self, coin_ids: List[str]) -> Dict:
        """CoinGecko free API - 10-30 calls/minute"""
        try:
            # Use simple price endpoint (higher rate limit)
            ids = ",".join(coin_ids[:250])  # Max 250 per request
            url = f"{self.config.COINGECKO_BASE_URL}/simple/price"
            params = {
                "ids": ids,
                "vs_currencies": "usd,eur,btc",
                "include_market_cap": "true",
                "include_24hr_vol": "true", 
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"CoinGecko: Got {len(data)} coins")
                    return data
                elif response.status == 429:
                    logger.warning("CoinGecko rate limit hit")
                    return {}
                    
        except Exception as e:
            logger.error(f"CoinGecko error: {e}")
            return {}
            
    async def get_coinmarketcap_free(self) -> Dict:
        """CoinMarketCap'in free endpoints'lerini kullan"""
        try:
            # Public endpoints that don't require API key
            url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
            params = {
                "start": "1",
                "limit": "100", 
                "sortBy": "market_cap",
                "sortType": "desc",
                "convert": "USD",
                "cryptoType": "all",
                "tagType": "all"
            }
            
            headers = {
                'User-Agent': self.config.get_random_user_agent()
            }
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("CoinMarketCap free data collected")
                    return data.get('data', {}).get('cryptoCurrencyList', [])
                    
        except Exception as e:
            logger.error(f"CoinMarketCap free error: {e}")
            return []
            
    async def start_binance_websocket(self):
        """Binance WebSocket - Completely free, real-time"""
        symbols = self.config.TRACKED_SYMBOLS[:50]  # Max 50 streams
        streams = [f"{symbol.lower()}usdt@ticker" for symbol in symbols]
        
        stream_names = "/".join(streams)
        ws_url = f"{self.config.BINANCE_WS_URL}/{stream_names}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info(f"Binance WebSocket connected: {len(streams)} streams")
                
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=30)
                        ticker_data = json.loads(data)
                        
                        symbol = ticker_data.get('s', '').replace('USDT', '')
                        if symbol:
                            price_data = {
                                'symbol': symbol,
                                'price': float(ticker_data.get('c', 0)),
                                'change_24h': float(ticker_data.get('P', 0)),
                                'volume_24h': float(ticker_data.get('v', 0)),
                                'high_24h': float(ticker_data.get('h', 0)),
                                'low_24h': float(ticker_data.get('l', 0)),
                                'source': 'binance_ws',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            
                            self.price_cache[symbol] = price_data
                            yield price_data
                            
                    except asyncio.TimeoutError:
                        await websocket.ping()
                    except Exception as e:
                        logger.error(f"Binance WebSocket error: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Binance WebSocket connection failed: {e}")
            
    async def get_exchange_prices(self, exchange_name: str) -> Dict:
        """Get prices from CCXT exchanges"""
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return {}
                
            # Fetch tickers (free for most exchanges)
            tickers = await exchange.fetch_tickers()
            
            processed_data = {}
            for symbol, ticker in tickers.items():
                # Convert to standard format
                base_symbol = symbol.split('/')[0]  # BTC/USDT -> BTC
                
                processed_data[base_symbol] = {
                    'symbol': base_symbol,
                    'price': ticker.get('last', 0),
                    'change_24h': ticker.get('percentage', 0),
                    'volume_24h': ticker.get('quoteVolume', 0),
                    'high_24h': ticker.get('high', 0),
                    'low_24h': ticker.get('low', 0),
                    'source': exchange_name,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
            logger.info(f"{exchange_name}: Got {len(processed_data)} prices")
            return processed_data
            
        except Exception as e:
            logger.error(f"Exchange {exchange_name} error: {e}")
            return {}
            
    async def get_crypto_fear_greed(self) -> Dict:
        """Alternative.me Fear & Greed Index (Free)"""
        try:
            url = "https://api.alternative.me/fng/"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [{}])[0]
        except Exception as e:
            logger.error(f"Fear & Greed error: {e}")
            return {}
            
    async def collect_all_prices(self) -> Dict:
        """Collect prices from all free sources"""
        all_data = {}
        
        # Parallel collection from multiple sources
        tasks = []
        
        # CoinGecko (primary source)
        coingecko_coins = ['bitcoin', 'ethereum', 'binancecoin', 'ripple', 'cardano', 
                          'solana', 'polkadot', 'dogecoin', 'avalanche-2', 'polygon']
        tasks.append(self.get_coingecko_data(coingecko_coins))
        
        # CCXT exchanges
        for exchange_name in ['binance', 'coinbase', 'kraken']:
            if exchange_name in self.exchanges:
                tasks.append(self.get_exchange_prices(exchange_name))
        
        # CoinMarketCap free
        tasks.append(self.get_coinmarketcap_free())
        
        # Fear & Greed Index
        tasks.append(self.get_crypto_fear_greed())
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge results
        merged_data = self.merge_price_sources(results)
        
        logger.info(f"Collected data for {len(merged_data)} cryptocurrencies")
        return merged_data
        
    def merge_price_sources(self, results: List) -> Dict:
        """Merge data from multiple sources with conflict resolution"""
        merged = {}
        
        for result in results:
            if isinstance(result, Exception):
                continue
                
            if isinstance(result, dict):
                for symbol, data in result.items():
                    if symbol not in merged:
                        merged[symbol] = data
                    else:
                        # Merge with priority: newer timestamp wins
                        existing_time = merged[symbol].get('timestamp', '')
                        new_time = data.get('timestamp', '')
                        
                        if new_time > existing_time:
                            merged[symbol] = {**merged[symbol], **data}
                            
        return merged
        
    async def start_websocket_streams(self):
        """Start all WebSocket streams in background"""
        # Start Binance WebSocket
        asyncio.create_task(self._binance_ws_task())
        
    async def _binance_ws_task(self):
        """Background task for Binance WebSocket"""
        while True:
            try:
                async for price_update in self.start_binance_websocket():
                    # Cache the update
                    symbol = price_update['symbol']
                    self.price_cache[symbol] = price_update
                    
            except Exception as e:
                logger.error(f"Binance WebSocket task error: {e}")
                await asyncio.sleep(30)  # Wait before reconnecting