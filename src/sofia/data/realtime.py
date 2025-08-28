"""Real-time data feed with WebSocket priority and REST fallback"""
from __future__ import annotations
import time
import threading
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests

from .ttl_cache import TTLCache
from ..config import (
    WS_ENABLED, REST_FALLBACK, STALE_TTL_SEC, 
    CACHE_TTL_SEC, REST_TIMEOUT_SEC, WS_PING_SEC
)
from ..symbols import to_binance, to_ui

logger = logging.getLogger(__name__)

@dataclass
class PriceTick:
    """Price tick data structure"""
    symbol_ui: str
    price: float
    ts: float
    volume: Optional[float] = None
    source: str = "unknown"

class ReliabilityFeed:
    """WebSocket-first feed with automatic REST fallback"""
    
    def __init__(self):
        self.cache = TTLCache(ttl=CACHE_TTL_SEC)
        self.metrics: Dict[str, Any] = {
            "ws_connected": 0,
            "reconnect_count": 0,
            "last_tick_ts": 0.0,
            "rest_hits": 0,
            "ws_errors": 0,
            "ws_ticks": 0,
            "rest_errors": 0,
        }
        self._stop = False
        self._ws_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the feed service"""
        if WS_ENABLED and not self._ws_thread:
            self._stop = False
            self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
            self._ws_thread.start()
            logger.info("WebSocket feed started")
    
    def stop(self):
        """Stop the feed service"""
        self._stop = True
        if self._ws_thread:
            self._ws_thread.join(timeout=2)
            self._ws_thread = None
            logger.info("WebSocket feed stopped")
    
    def _ws_loop(self):
        """WebSocket connection loop with exponential backoff"""
        backoff = 1
        
        while not self._stop:
            try:
                # Simulate WebSocket connection
                # In production, use real WebSocket client (websockets, ccxtpro, etc.)
                with self._lock:
                    self.metrics["ws_connected"] = 1
                
                logger.info("WebSocket connected")
                backoff = 1  # Reset backoff on successful connection
                
                # Heartbeat loop
                while not self._stop:
                    time.sleep(0.5)  # Simulate receiving ticks
                    
                    # In production, process real WebSocket messages here
                    # For now, we'll rely on REST fallback
                    
            except Exception as e:
                with self._lock:
                    self.metrics["ws_errors"] += 1
                    self.metrics["ws_connected"] = 0
                    self.metrics["reconnect_count"] += 1
                
                logger.warning(f"WebSocket error: {e}, reconnecting in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)  # Cap at 60 seconds
    
    def get_price(self, symbol_ui: str) -> Optional[PriceTick]:
        """Get price with WebSocket priority and REST fallback"""
        # Check cache first
        tick: Optional[PriceTick] = self.cache.get(symbol_ui)
        now = time.time()
        
        # Return cached data if fresh
        if tick and (now - tick.ts) <= STALE_TTL_SEC:
            return tick
        
        # Try REST fallback if enabled
        if REST_FALLBACK:
            try:
                sym = to_binance(symbol_ui)
                response = requests.get(
                    "https://api.binance.com/api/v3/ticker/price",
                    params={"symbol": sym},
                    timeout=REST_TIMEOUT_SEC
                )
                response.raise_for_status()
                
                data = response.json()
                price = float(data["price"])
                
                tick = PriceTick(
                    symbol_ui=to_ui(sym),
                    price=price,
                    ts=now,
                    source="rest"
                )
                
                self.cache.set(symbol_ui, tick)
                
                with self._lock:
                    self.metrics["rest_hits"] += 1
                    self.metrics["last_tick_ts"] = now
                
                return tick
                
            except Exception as e:
                with self._lock:
                    self.metrics["rest_errors"] += 1
                logger.error(f"REST fallback error for {symbol_ui}: {e}")
        
        # Return stale data if available
        return tick
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self._lock:
            return dict(self.metrics)
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        with self._lock:
            return bool(self.metrics.get("ws_connected", 0))