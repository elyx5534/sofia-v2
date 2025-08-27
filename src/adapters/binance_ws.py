"""
Lightweight Binance WebSocket consumer for real-time price data.
"""

import asyncio
import json
import time
import logging
from typing import Dict, Optional, AsyncGenerator
from datetime import datetime, timezone
import websockets
import requests

logger = logging.getLogger(__name__)

class BinanceWSConsumer:
    """WebSocket consumer for Binance real-time data."""
    
    def __init__(self, symbols: list = None):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.rest_url = "https://api.binance.com/api/v3/ticker/price"
        
        # Price storage with rolling metrics
        self.prices = {}  # symbol -> latest_price
        self.timestamps = {}  # symbol -> last_update_time
        self.tick_counts = {}  # symbol -> total_ticks
        self.error_count = 0
        self.rolling_mid = {}  # symbol -> simple moving average
        self.ema = {}  # symbol -> exponential moving average
        
        # State
        self.connected = False
        self.ws = None
        self.background_task = None
        
    async def connect(self):
        """Connect to Binance WebSocket stream."""
        try:
            # Build stream URL for multiple symbols
            streams = [f"{symbol.lower()}@trade" for symbol in self.symbols]
            stream_url = f"{self.ws_url}/{'/'.join(streams)}"
            
            logger.info(f"Connecting to Binance WS: {len(self.symbols)} symbols")
            
            self.ws = await websockets.connect(stream_url)
            self.connected = True
            
            logger.info("Binance WebSocket connected")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connected = False
            return False
    
    async def listen(self) -> AsyncGenerator[Dict, None]:
        """Listen for real-time trade updates."""
        while self.connected and self.ws:
            try:
                message = await asyncio.wait_for(self.ws.recv(), timeout=30)
                data = json.loads(message)
                
                # Handle single stream or combined stream
                if "stream" in data:
                    # Combined stream format
                    stream_data = data["data"]
                    symbol = stream_data["s"]
                    price = float(stream_data["p"])
                else:
                    # Single stream format
                    symbol = data["s"]
                    price = float(data["p"])
                
                # Update price storage
                self.prices[symbol] = price
                self.timestamps[symbol] = time.time()
                self.tick_counts[symbol] = self.tick_counts.get(symbol, 0) + 1
                
                # Update rolling metrics
                self._update_rolling_metrics(symbol, price)
                
                yield {
                    "symbol": symbol,
                    "price": price,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "binance_ws",
                    "rolling_mid": self.rolling_mid.get(symbol),
                    "ema": self.ema.get(symbol)
                }
                
            except asyncio.TimeoutError:
                logger.warning("WebSocket timeout - attempting reconnect")
                await self._reconnect()
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed - attempting reconnect")
                await self._reconnect()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.error_count += 1
                await asyncio.sleep(1)
    
    async def _reconnect(self):
        """Attempt to reconnect WebSocket."""
        self.connected = False
        if self.ws:
            await self.ws.close()
        
        await asyncio.sleep(5)
        await self.connect()
    
    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """Get latest price for symbol."""
        if symbol not in self.prices:
            return None
        
        return {
            "symbol": symbol,
            "price": self.prices[symbol],
            "timestamp": self.timestamps.get(symbol, 0),
            "freshness_seconds": time.time() - self.timestamps.get(symbol, 0)
        }
    
    async def get_rest_price(self, symbol: str) -> Optional[float]:
        """Fallback to REST API for price."""
        try:
            response = requests.get(f"{self.rest_url}?symbol={symbol}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = float(data["price"])
                
                # Update cache
                self.prices[symbol] = price
                self.timestamps[symbol] = time.time()
                
                return price
        except Exception as e:
            logger.error(f"REST price fetch failed for {symbol}: {e}")
            self.error_count += 1
        
        return None
    
    def get_metrics(self) -> Dict:
        """Get consumer metrics."""
        current_time = time.time()
        freshness_metrics = {}
        
        for symbol in self.symbols:
            if symbol in self.timestamps:
                freshness = current_time - self.timestamps[symbol]
                freshness_metrics[symbol] = freshness
        
        return {
            "connected": self.connected,
            "symbols_tracked": len(self.symbols),
            "prices_cached": len(self.prices),
            "freshness_seconds": freshness_metrics,
            "tick_counts": self.tick_counts.copy(),
            "error_count": self.error_count
        }
    
    def _update_rolling_metrics(self, symbol: str, price: float):
        """Update rolling metrics for symbol."""
        # Simple moving average (last 10 ticks)
        if symbol not in self.rolling_mid:
            self.rolling_mid[symbol] = []
        
        self.rolling_mid[symbol].append(price)
        if len(self.rolling_mid[symbol]) > 10:
            self.rolling_mid[symbol] = self.rolling_mid[symbol][-10:]
        
        # EMA with alpha 0.1
        if symbol not in self.ema:
            self.ema[symbol] = price
        else:
            self.ema[symbol] = 0.1 * price + 0.9 * self.ema[symbol]
    
    async def start_background_consumer(self):
        """Start background WebSocket consumer task."""
        if self.background_task is not None:
            return
        
        await self.connect()
        if self.connected:
            self.background_task = asyncio.create_task(self._consume_forever())
            logger.info("Background WebSocket consumer started")
    
    async def _consume_forever(self):
        """Background consumer task."""
        async for update in self.listen():
            # Updates are stored in memory, no action needed
            pass
    
    async def close(self):
        """Close WebSocket connection."""
        self.connected = False
        if self.background_task:
            self.background_task.cancel()
            self.background_task = None
        if self.ws:
            await self.ws.close()
        logger.info("Binance WebSocket closed")