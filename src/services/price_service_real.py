"""
Real price service with WebSocket-first and REST fallback
"""

import asyncio
import logging
import os
import time
from typing import Dict, Optional, Any
import httpx

from src.adapters.binance_ws import ws_adapter
from src.services.symbols import get_ws_sym, get_rest_sym

logger = logging.getLogger(__name__)


class PriceServiceReal:
    """Price service with WebSocket priority and REST fallback"""
    
    def __init__(self):
        # Configuration
        self.ws_enabled = os.getenv('SOFIA_WS_ENABLED', 'true').lower() == 'true'
        self.cache_ttl = int(os.getenv('SOFIA_PRICE_CACHE_TTL', '10'))
        self.rest_timeout = float(os.getenv('SOFIA_REST_TIMEOUT_SEC', '5'))
        
        # REST cache
        self.rest_cache = {}  # {symbol: {'price': float, 'timestamp': float}}
        
        # REST failure tracking
        self.consecutive_rest_failures = {}
        self.rest_last_ok_ts = {}
        
        # Start WebSocket if enabled
        self.ws_task = None
        self._ws_started = False
    
    async def start_websocket(self):
        """Start WebSocket connection"""
        if not self.ws_enabled:
            return
        try:
            if not self._ws_started:
                self._ws_started = True
                self.ws_task = asyncio.create_task(ws_adapter.connect())
                logger.info("WebSocket connection started")
        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
    
    async def get_price(self, ui_symbol: str) -> Optional[Dict[str, Any]]:
        """Get price with WebSocket priority and REST fallback"""
        # Start WebSocket on first use if enabled
        if self.ws_enabled and not self._ws_started:
            await self.start_websocket()
            # Give WebSocket a moment to connect
            await asyncio.sleep(0.1)
        
        ws_symbol = get_ws_sym(ui_symbol)
        rest_symbol = get_rest_sym(ui_symbol) or ws_symbol
        
        if not ws_symbol and not rest_symbol:
            logger.error(f"No symbol mapping for: {ui_symbol}")
            return None
        
        # Try WebSocket first if enabled and connected
        if self.ws_enabled and ws_adapter.connected and ws_symbol:
            freshness = ws_adapter.get_freshness(ws_symbol)
            
            if freshness is not None and freshness < 15:
                price = ws_adapter.get_price(ws_symbol)
                if price:
                    logger.debug(f"WebSocket price for {ui_symbol}: {price} (freshness: {freshness:.1f}s)")
                    return {
                        'symbol': ui_symbol,
                        'price': price,
                        'source': 'websocket',
                        'freshness': freshness
                    }
            elif freshness is not None:
                logger.warning(f"WebSocket data stale for {ui_symbol}: {freshness:.1f}s")
        
        # Fallback to REST
        return await self.get_price_rest(ui_symbol, rest_symbol)
    
    async def get_price_rest(self, ui_symbol: str, rest_symbol: str) -> Optional[Dict[str, Any]]:
        """Get price via REST API with caching"""
        # Check cache
        if rest_symbol in self.rest_cache:
            cache_entry = self.rest_cache[rest_symbol]
            age = time.time() - cache_entry['timestamp']
            
            if age < self.cache_ttl:
                return {
                    'symbol': ui_symbol,
                    'price': cache_entry['price'],
                    'source': 'rest_cache',
                    'freshness': age
                }
        
        # Fetch from REST API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.binance.com/api/v3/ticker/price?symbol={rest_symbol}",
                    timeout=self.rest_timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    price = float(data['price'])
                    
                    # Update cache
                    self.rest_cache[rest_symbol] = {
                        'price': price,
                        'timestamp': time.time()
                    }
                    
                    # Reset failure counter
                    self.consecutive_rest_failures[rest_symbol] = 0
                    self.rest_last_ok_ts[rest_symbol] = time.time()
                    
                    logger.debug(f"REST price for {ui_symbol}: {price}")
                    return {
                        'symbol': ui_symbol,
                        'price': price,
                        'source': 'rest',
                        'freshness': 0
                    }
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
        except Exception as e:
            # Track failure
            if rest_symbol not in self.consecutive_rest_failures:
                self.consecutive_rest_failures[rest_symbol] = 0
            self.consecutive_rest_failures[rest_symbol] += 1
            
            logger.error(f"REST API failed for {rest_symbol}: {e}")
            return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        metrics = {
            'websocket_enabled': self.ws_enabled,
            'websocket_connected': ws_adapter.connected if self.ws_enabled else False,
            'cache_ttl': self.cache_ttl,
            'rest_timeout': self.rest_timeout
        }
        
        # Add WebSocket metrics if enabled
        if self.ws_enabled:
            ws_metrics = ws_adapter.get_metrics()
            metrics['websocket_metrics'] = ws_metrics
            
            # Identify stale symbols
            stale_symbols = []
            for symbol, data in ws_metrics.get('symbols', {}).items():
                freshness = data.get('freshness')
                if freshness is not None and freshness > 15:
                    stale_symbols.append(symbol)
            metrics['stale_symbols'] = stale_symbols
        else:
            metrics['stale_symbols'] = []
        
        # Add REST metrics
        metrics['rest_failures'] = self.consecutive_rest_failures
        metrics['rest_last_ok'] = self.rest_last_ok_ts
        
        return metrics
    
    async def shutdown(self):
        """Shutdown service"""
        if self.ws_enabled and self.ws_task:
            await ws_adapter.disconnect()
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
            logger.info("Price service shutdown complete")


# Global instance
price_service = PriceServiceReal()