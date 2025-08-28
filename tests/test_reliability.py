import time
import pytest
from src.sofia.data.ttl_cache import TTLCache
from src.sofia.data.realtime import PriceTick, ReliabilityFeed

def test_ttl_cache_basic():
    """Test basic TTL cache functionality"""
    cache = TTLCache(ttl=1)
    cache.set("key1", "value1")
    
    # Should get value immediately
    assert cache.get("key1") == "value1"
    
    # Wait for expiration
    time.sleep(1.2)
    assert cache.get("key1") is None

def test_ttl_cache_cleanup():
    """Test cache cleanup functionality"""
    cache = TTLCache(ttl=1)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    
    time.sleep(1.2)
    cache.cleanup()
    
    assert len(cache.store) == 0

def test_price_tick_creation():
    """Test PriceTick dataclass creation"""
    tick = PriceTick(
        symbol_ui="BTC/USDT",
        price=67000.0,
        ts=time.time(),
        source="websocket"
    )
    
    assert tick.symbol_ui == "BTC/USDT"
    assert tick.price == 67000.0
    assert tick.source == "websocket"
    assert tick.volume is None

def test_reliability_feed_init():
    """Test ReliabilityFeed initialization"""
    feed = ReliabilityFeed()
    
    assert feed.cache is not None
    assert feed.metrics["ws_connected"] == 0
    assert feed.metrics["rest_hits"] == 0
    assert feed.is_connected() is False

def test_reliability_feed_metrics():
    """Test metrics retrieval"""
    feed = ReliabilityFeed()
    metrics = feed.get_metrics()
    
    assert "ws_connected" in metrics
    assert "reconnect_count" in metrics
    assert "rest_hits" in metrics
    assert isinstance(metrics, dict)