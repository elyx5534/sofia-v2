"""
Sofia V2 Realtime DataHub - Event Bus
In-process pub/sub system for event distribution
"""

import asyncio
from enum import Enum
from typing import Dict, List, Callable, Any, Awaitable
import structlog

logger = structlog.get_logger(__name__)

class EventType(Enum):
    """Event types for the pub/sub system"""
    TRADE = "trade"
    ORDERBOOK = "orderbook"
    LIQUIDATION = "liquidation"
    NEWS = "news"
    BIG_TRADE = "big_trade"
    LIQ_SPIKE = "liq_spike"
    VOLUME_SURGE = "volume_surge"
    SPREAD_ANOMALY = "spread_anomaly"
    CONNECTION_STATUS = "connection_status"
    ERROR = "error"

class EventBus:
    """
    Fast in-process event bus for real-time data distribution
    Thread-safe async implementation with error isolation
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}
        self._event_count = 0
        self._error_count = 0
    
    def subscribe(self, event_type: EventType, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Subscribe to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(handler)
        logger.info("Event handler subscribed", 
                   event_type=event_type.value, 
                   handler=handler.__name__,
                   total_handlers=len(self._subscribers[event_type]))
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Unsubscribe from an event type"""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.info("Event handler unsubscribed", 
                       event_type=event_type.value,
                       handler=handler.__name__)
    
    async def publish(self, event_type: EventType, event_data: Dict[str, Any]):
        """
        Publish event to all subscribers
        Error isolation: one handler failure doesn't affect others
        """
        if event_type not in self._subscribers:
            return
        
        self._event_count += 1
        handlers = self._subscribers[event_type].copy()  # Snapshot to avoid race conditions
        
        if not handlers:
            return
        
        # Execute all handlers concurrently with error isolation
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._safe_handler_call(handler, event_data, event_type))
            tasks.append(task)
        
        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_handler_call(self, handler: Callable, event_data: Dict[str, Any], event_type: EventType):
        """Safely execute handler with error isolation"""
        try:
            await handler(event_data)
        except Exception as e:
            self._error_count += 1
            logger.error("Event handler failed", 
                        event_type=event_type.value,
                        handler=handler.__name__,
                        error=str(e),
                        total_errors=self._error_count)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        subscriber_counts = {
            event_type.value: len(handlers) 
            for event_type, handlers in self._subscribers.items()
        }
        
        return {
            "total_events_processed": self._event_count,
            "total_errors": self._error_count,
            "error_rate": self._error_count / max(self._event_count, 1),
            "subscriber_counts": subscriber_counts,
            "total_subscribers": sum(subscriber_counts.values())
        }
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """Get number of subscribers for an event type"""
        return len(self._subscribers.get(event_type, []))
    
    def clear_subscribers(self, event_type: EventType = None):
        """Clear subscribers for specific event type or all"""
        if event_type:
            if event_type in self._subscribers:
                self._subscribers[event_type].clear()
                logger.info("Cleared subscribers", event_type=event_type.value)
        else:
            self._subscribers.clear()
            logger.info("Cleared all subscribers")
    
    def reset_stats(self):
        """Reset statistics counters"""
        self._event_count = 0
        self._error_count = 0
        logger.info("Event bus statistics reset")

# Global event bus instance
_global_bus = None

def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus