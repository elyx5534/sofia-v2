"""
Binance WebSocket adapter with robust reconnection and metrics
"""

import asyncio
import json
import logging
import os
import random
import time
from typing import Dict, Optional, Any
import websockets

logger = logging.getLogger(__name__)


class BinanceWebSocketAdapter:
    """WebSocket adapter for Binance with exponential backoff reconnection"""
    
    def __init__(self):
        self.ws = None
        self.running = False
        self.connected = False
        self.stale = False
        
        # Configuration from ENV
        self.ping_sec = int(os.getenv('SOFIA_WS_PING_SEC', '20'))
        self.combined = os.getenv('SOFIA_WS_COMBINED', 'true').lower() == 'true'
        self.symbols = os.getenv('SOFIA_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
        
        # Metrics tracking
        self.last_connect_ts = 0
        self.last_msg_ts = {}  # Per symbol
        self.tick_counts = {}  # Per symbol
        self.error_count = 0
        self.last_error = None
        
        # Price cache
        self.prices = {}
        
        # Technical indicators (SMA/EMA)
        self.price_history = {}  # Store recent prices for each symbol
        self.indicators = {}  # Store calculated indicators
        
        # Reconnection state
        self.reconnect_attempts = 0
        self.max_reconnect_delay = 60  # seconds
        self.reconnect_count = 0  # Total reconnect count for metrics
        
        # Initialize metrics and indicators
        for symbol in self.symbols:
            self.last_msg_ts[symbol] = 0
            self.tick_counts[symbol] = 0
            self.prices[symbol] = None
            self.price_history[symbol] = []  # Store last 20 prices for indicators
            self.indicators[symbol] = {'sma': None, 'ema': None}
    
    def get_ws_url(self) -> str:
        """Generate WebSocket URL based on configuration"""
        base_url = "wss://stream.binance.com:9443"
        
        if self.combined and len(self.symbols) > 1:
            # Combined stream for multiple symbols
            streams = [f"{sym.lower()}@ticker" for sym in self.symbols]
            return f"{base_url}/stream?streams={'/'.join(streams)}"
        elif self.symbols:
            # Single symbol stream
            return f"{base_url}/ws/{self.symbols[0].lower()}@ticker"
        else:
            raise ValueError("No symbols configured")
    
    async def connect(self):
        """Connect to WebSocket with reconnection logic"""
        self.running = True
        
        while self.running:
            try:
                delay = min(2 ** self.reconnect_attempts + random.random(), self.max_reconnect_delay)
                if self.reconnect_attempts > 0:
                    logger.info(f"Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts})")
                    await asyncio.sleep(delay)
                
                url = self.get_ws_url()
                logger.info(f"Connecting to WebSocket: {url}")
                
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    self.connected = True
                    self.stale = False
                    self.last_connect_ts = time.time()
                    if self.reconnect_attempts > 0:
                        self.reconnect_count += 1
                    self.reconnect_attempts = 0
                    
                    logger.info("WebSocket connected successfully")
                    
                    # Cold start fill - fetch initial prices via REST
                    await self.cold_start_fill()
                    
                    # Start ping task and message handler
                    ping_task = asyncio.create_task(self.ping_loop())
                    msg_task = asyncio.create_task(self.message_handler())
                    stale_task = asyncio.create_task(self.stale_checker())
                    
                    try:
                        await asyncio.gather(ping_task, msg_task, stale_task)
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                        ping_task.cancel()
                        msg_task.cancel()
                        stale_task.cancel()
                        raise
                        
            except Exception as e:
                self.connected = False
                self.error_count += 1
                self.last_error = str(e)
                self.reconnect_attempts += 1
                logger.error(f"WebSocket error: {e}")
                
                if not self.running:
                    break
    
    async def cold_start_fill(self):
        """Fetch initial prices via REST API"""
        import httpx
        
        timeout = float(os.getenv('SOFIA_REST_TIMEOUT_SEC', '5'))
        
        for symbol in self.symbols:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                        timeout=timeout
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        price = float(data['price'])
                        self.prices[symbol] = price
                        self.last_msg_ts[symbol] = time.time()
                        logger.info(f"Cold start price for {symbol}: {price}")
                    
            except Exception as e:
                logger.error(f"Cold start fill failed for {symbol}: {e}")
    
    async def ping_loop(self):
        """Send periodic pings to keep connection alive"""
        while self.connected:
            try:
                await asyncio.sleep(self.ping_sec)
                if self.ws:
                    await self.ws.ping()
                    logger.debug("Ping sent")
            except Exception as e:
                logger.error(f"Ping failed: {e}")
                break
    
    async def message_handler(self):
        """Handle incoming WebSocket messages"""
        async for message in self.ws:
            try:
                data = json.loads(message)
                
                # Handle combined stream format
                if 'stream' in data:
                    symbol = data['data']['s']
                    price = float(data['data']['c'])
                else:
                    # Single stream format
                    symbol = data['s']
                    price = float(data['c'])
                
                # Update metrics and cache
                self.prices[symbol] = price
                self.last_msg_ts[symbol] = time.time()
                self.tick_counts[symbol] += 1
                self.stale = False
                
                # Update technical indicators
                await self.update_indicators(symbol, price)
                
                logger.debug(f"Price update: {symbol} = {price}")
                
            except Exception as e:
                logger.error(f"Message processing error: {e}")
    
    async def stale_checker(self):
        """Check for stale data (no messages for 15s)"""
        while self.connected:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            current_time = time.time()
            stale_symbols = []
            
            for symbol in self.symbols:
                if symbol in self.last_msg_ts:
                    age = current_time - self.last_msg_ts[symbol]
                    if age > 15:
                        stale_symbols.append(symbol)
            
            if stale_symbols:
                self.stale = True
                logger.warning(f"Stale symbols detected: {stale_symbols}")
    
    async def disconnect(self):
        """Disconnect WebSocket"""
        self.running = False
        self.connected = False
        if self.ws:
            await self.ws.close()
            self.ws = None
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get cached price for symbol"""
        return self.prices.get(symbol)
    
    def get_freshness(self, symbol: str) -> Optional[float]:
        """Get data freshness in seconds"""
        if symbol in self.last_msg_ts and self.last_msg_ts[symbol] > 0:
            return time.time() - self.last_msg_ts[symbol]
        return None
    
    async def update_indicators(self, symbol: str, price: float):
        """Update SMA and EMA indicators"""
        # Add to price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(price)
        
        # Keep only last 20 prices
        if len(self.price_history[symbol]) > 20:
            self.price_history[symbol] = self.price_history[symbol][-20:]
        
        # Calculate SMA (Simple Moving Average) - last 20 prices
        if len(self.price_history[symbol]) >= 20:
            sma = sum(self.price_history[symbol]) / 20
            self.indicators[symbol]['sma'] = sma
        
        # Calculate EMA (Exponential Moving Average) - 20 period
        if len(self.price_history[symbol]) >= 2:
            alpha = 2 / (20 + 1)  # EMA smoothing factor
            if self.indicators[symbol]['ema'] is None:
                # First EMA = SMA
                self.indicators[symbol]['ema'] = sum(self.price_history[symbol]) / len(self.price_history[symbol])
            else:
                # EMA = alpha * price + (1 - alpha) * previous_EMA
                self.indicators[symbol]['ema'] = (alpha * price) + ((1 - alpha) * self.indicators[symbol]['ema'])
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get adapter metrics"""
        current_time = time.time()
        
        metrics = {
            'connected': self.connected,
            'stale': self.stale,
            'last_connect_ts': self.last_connect_ts,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'reconnect_count': self.reconnect_count,
            'symbols': {}
        }
        
        for symbol in self.symbols:
            metrics['symbols'][symbol] = {
                'last_msg_ts': self.last_msg_ts.get(symbol, 0),
                'tick_count': self.tick_counts.get(symbol, 0),
                'freshness': self.get_freshness(symbol),
                'price': self.prices.get(symbol),
                'sma': self.indicators.get(symbol, {}).get('sma'),
                'ema': self.indicators.get(symbol, {}).get('ema')
            }
        
        return metrics


# Global instance
ws_adapter = BinanceWebSocketAdapter()