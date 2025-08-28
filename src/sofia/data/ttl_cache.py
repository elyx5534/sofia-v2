"""TTL (Time To Live) Cache implementation for price data"""
import time
from typing import Any, Optional, Dict, Tuple

class TTLCache:
    """Simple TTL cache for storing time-sensitive data"""
    
    def __init__(self, ttl: int = 5):
        """Initialize cache with TTL in seconds"""
        self.ttl = ttl
        self.store: Dict[str, Tuple[Any, float]] = {}
    
    def set(self, key: str, value: Any) -> None:
        """Store value with current timestamp"""
        self.store[key] = (value, time.time())
    
    def get(self, key: str) -> Optional[Any]:
        """Get value if not expired, remove if stale"""
        item = self.store.get(key)
        if not item:
            return None
        
        value, timestamp = item
        if time.time() - timestamp > self.ttl:
            self.store.pop(key, None)
            return None
        
        return value
    
    def clear(self) -> None:
        """Clear all cached items"""
        self.store.clear()
    
    def cleanup(self) -> None:
        """Remove all expired items"""
        current_time = time.time()
        expired_keys = [
            k for k, (_, ts) in self.store.items()
            if current_time - ts > self.ttl
        ]
        for key in expired_keys:
            self.store.pop(key, None)