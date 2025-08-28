"""
Stooq EOD data provider - free historical data
"""

import asyncio
import httpx
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import csv
from io import StringIO

logger = logging.getLogger(__name__)

class StooqEODAdapter:
    """Stooq End-of-Day data provider"""
    
    def __init__(self):
        self.base_url = "https://stooq.com/q/d/l/"
        self.timeout = 10
        
    async def get_historical(self, symbol: str, days: int = 30) -> Optional[List[Dict]]:
        """Get historical EOD data"""
        try:
            # Stooq symbol format
            stooq_symbol = self._convert_symbol(symbol)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            async with httpx.AsyncClient() as client:
                params = {
                    's': stooq_symbol,
                    'd1': start_date.strftime('%Y%m%d'),
                    'd2': end_date.strftime('%Y%m%d'),
                    'f': 'd',
                    'q': 'd'
                }
                
                response = await client.get(self.base_url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    # Parse CSV response
                    csv_data = StringIO(response.text)
                    reader = csv.DictReader(csv_data)
                    
                    ohlcv = []
                    for row in reader:
                        try:
                            ohlcv.append({
                                'date': row['Date'],
                                'open': float(row['Open']),
                                'high': float(row['High']),
                                'low': float(row['Low']),
                                'close': float(row['Close']),
                                'volume': float(row.get('Volume', 0))
                            })
                        except (KeyError, ValueError) as e:
                            logger.debug(f"Row parse error: {e}")
                            continue
                    
                    # Reverse to get chronological order
                    return list(reversed(ohlcv))
                    
        except Exception as e:
            logger.error(f"Stooq error for {symbol}: {e}")
        
        return None
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol to Stooq format"""
        # Common conversions
        conversions = {
            'BTC-USD': 'BTCUSD',
            'ETH-USD': 'ETHUSD',
            'AAPL': 'AAPL.US',
            'GOOGL': 'GOOGL.US',
            'MSFT': 'MSFT.US',
            'TSLA': 'TSLA.US',
            'SPY': 'SPY.US',
            'QQQ': 'QQQ.US',
            'EUR-USD': 'EURUSD',
            'GBP-USD': 'GBPUSD',
            'USD-JPY': 'USDJPY',
            'GOLD': 'GC.F',
            'SILVER': 'SI.F',
            'OIL': 'CL.F'
        }
        
        return conversions.get(symbol.upper(), symbol.upper())
    
    async def get_latest_eod(self, symbol: str) -> Optional[Dict]:
        """Get latest EOD price"""
        try:
            data = await self.get_historical(symbol, days=5)
            if data and len(data) > 0:
                latest = data[-1]
                return {
                    'symbol': symbol,
                    'price': latest['close'],
                    'date': latest['date'],
                    'source': 'stooq_eod'
                }
        except Exception as e:
            logger.error(f"Stooq latest error for {symbol}: {e}")
        
        return None

# Global instance
stooq_adapter = StooqEODAdapter()