"""
Price service with WebSocket-first, REST fallback architecture.
"""

import asyncio
import time
import logging
from typing import Dict, Optional
from src.adapters.binance_ws import BinanceWSConsumer

logger = logging.getLogger(__name__)

class PriceService:
    """Unified price service with WebSocket-first, REST fallback."""
    
    def __init__(self, symbols: list = None):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.cache = {}  # symbol -> {price, timestamp}
        self.cache_ttl = 10  # seconds
        self.running = False
        self.ws_consumer = BinanceWSConsumer(symbols=self.symbols)
        self.ws_enabled = True
        
    async def start(self):
        """Start the price service with WebSocket and fallback."""
        logger.info("Starting price service with WebSocket support")
        self.running = True
        
        # Try to start WebSocket first
        try:
            await self.ws_consumer.start_background_consumer()
            if self.ws_consumer.connected:
                logger.info("WebSocket consumer started successfully")
            else:
                logger.warning("WebSocket failed, using REST fallback")
                self.ws_enabled = False
        except Exception as e:
            logger.error(f"WebSocket startup failed: {e}")
            self.ws_enabled = False
        
        # Populate initial prices via REST
        await self._populate_initial_prices()
    
    async def _populate_initial_prices(self):
        """Populate initial prices via REST API."""
        import requests
        
        for symbol in self.symbols:
            try:
                response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price = float(data["price"])
                    
                    self.cache[symbol] = {
                        "price": price,
                        "timestamp": time.time(),
                        "source": "rest_binance"
                    }
                    logger.info(f"Initial price for {symbol}: ${price:,.2f}")
            except Exception as e:
                logger.error(f"Initial price fetch failed for {symbol}: {e}")
    
    async def get_price(self, symbol: str) -> Optional[Dict]:
        """Get current price with WebSocket-first, REST fallback."""
        # Try WebSocket first
        if self.ws_enabled and self.ws_consumer.connected:
            ws_price = self.ws_consumer.get_latest_price(symbol)
            if ws_price and ws_price["freshness_seconds"] < 15:
                # Update cache
                self.cache[symbol] = {
                    "price": ws_price["price"],
                    "timestamp": ws_price["timestamp"],
                    "source": "binance_ws"
                }
                return ws_price
        
        # Check cache for recent REST data
        if symbol in self.cache:
            cached = self.cache[symbol]
            freshness = time.time() - cached["timestamp"]
            
            if freshness <= self.cache_ttl:
                return {
                    "symbol": symbol,
                    "price": cached["price"],
                    "timestamp": cached["timestamp"],
                    "freshness_seconds": freshness,
                    "source": cached["source"]
                }
        
        # Fallback to REST
        import requests
        try:
            response = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = float(data["price"])
                
                self.cache[symbol] = {
                    "price": price,
                    "timestamp": time.time(),
                    "source": "rest_fallback"
                }
                
                return {
                    "symbol": symbol,
                    "price": price,
                    "timestamp": self.cache[symbol]["timestamp"],
                    "freshness_seconds": 0.0,
                    "source": "rest_fallback"
                }
        except Exception as e:
            logger.error(f"REST price fetch failed for {symbol}: {e}")
        
        return None
    
    def get_cached_price(self, symbol: str) -> Optional[float]:
        """Get cached price without freshness check."""
        if symbol in self.cache:
            return self.cache[symbol]["price"]
        return None
    
    def get_freshness_metrics(self) -> Dict:
        """Get freshness metrics for all symbols."""
        current_time = time.time()
        metrics = {}
        
        for symbol in self.symbols:
            if symbol in self.cache:
                freshness = current_time - self.cache[symbol]["timestamp"]
                metrics[symbol] = freshness
            else:
                metrics[symbol] = 999.0  # No data
        
        return metrics
    
    def get_metrics(self) -> Dict:
        """Get service metrics with WebSocket integration."""
        freshness_metrics = self.get_freshness_metrics()
        ws_metrics = self.ws_consumer.get_metrics() if self.ws_enabled else {}
        
        return {
            "service_running": self.running,
            "websocket_connected": self.ws_consumer.connected if self.ws_enabled else False,
            "websocket_enabled": self.ws_enabled,
            "symbols_tracked": len(self.symbols),
            "cached_prices": len(self.cache),
            "freshness_seconds": freshness_metrics,
            "tick_counts": ws_metrics.get("tick_counts", {}),
            "error_count": ws_metrics.get("error_count", 0)
        }
    
    async def stop(self):
        """Stop the price service."""
        self.running = False
        if self.ws_enabled:
            await self.ws_consumer.close()
        logger.info("Price service stopped")


# Global instance
_price_service = None

async def get_price_service():
    """Get or create the global price service instance."""
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
        await _price_service.start()
    return _price_service