"""
Yahoo Finance free data provider - no API key required
"""

import asyncio
import httpx
import logging
from typing import Dict, Optional, List
import re
import json

logger = logging.getLogger(__name__)

class YahooFreeAdapter:
    """Yahoo Finance free data provider"""
    
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com"
        self.timeout = 10
        self.cache = {}
        
    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time quote"""
        try:
            # Convert symbol format (BTC-USD stays, ETH-USD stays)
            yahoo_symbol = symbol.upper()
            
            async with httpx.AsyncClient() as client:
                # Use the chart API which doesn't require authentication
                url = f"{self.base_url}/v8/finance/chart/{yahoo_symbol}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = await client.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    chart = data.get('chart', {}).get('result', [{}])[0]
                    meta = chart.get('meta', {})
                    
                    if meta:
                        price = meta.get('regularMarketPrice', 0)
                        prev_close = meta.get('previousClose', price)
                        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                        
                        return {
                            'symbol': symbol,
                            'price': price,
                            'change_percent': round(change_pct, 2),
                            'volume': meta.get('regularMarketVolume', 0),
                            'source': 'yahoo'
                        }
        except Exception as e:
            logger.error(f"Yahoo quote error for {symbol}: {e}")
        
        return None
    
    async def get_historical(self, symbol: str, period: str = "1mo") -> Optional[List[Dict]]:
        """Get historical data"""
        try:
            yahoo_symbol = symbol.upper()
            
            # Convert period to interval
            interval_map = {
                "1d": "1h",
                "5d": "1h", 
                "1mo": "1d",
                "3mo": "1d",
                "1y": "1wk"
            }
            interval = interval_map.get(period, "1d")
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/v8/finance/chart/{yahoo_symbol}"
                params = {
                    "range": period,
                    "interval": interval
                }
                
                response = await client.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    chart = data.get('chart', {}).get('result', [{}])[0]
                    
                    timestamps = chart.get('timestamp', [])
                    quote = chart.get('indicators', {}).get('quote', [{}])[0]
                    
                    ohlcv = []
                    for i, ts in enumerate(timestamps):
                        ohlcv.append({
                            'timestamp': ts * 1000,  # Convert to milliseconds
                            'open': quote.get('open', [])[i],
                            'high': quote.get('high', [])[i],
                            'low': quote.get('low', [])[i],
                            'close': quote.get('close', [])[i],
                            'volume': quote.get('volume', [])[i]
                        })
                    
                    return ohlcv
        except Exception as e:
            logger.error(f"Yahoo historical error for {symbol}: {e}")
        
        return None
    
    async def search(self, query: str) -> List[Dict]:
        """Search for symbols"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/v1/finance/search"
                params = {
                    "q": query,
                    "quotesCount": 10
                }
                
                response = await client.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    quotes = data.get('quotes', [])
                    
                    results = []
                    for quote in quotes:
                        results.append({
                            'symbol': quote.get('symbol'),
                            'name': quote.get('shortname') or quote.get('longname'),
                            'type': quote.get('quoteType'),
                            'exchange': quote.get('exchange')
                        })
                    
                    return results
        except Exception as e:
            logger.error(f"Yahoo search error: {e}")
        
        return []

# Global instance
yahoo_adapter = YahooFreeAdapter()