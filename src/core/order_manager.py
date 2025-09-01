"""Order management module."""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Time in force."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    DAY = "day"  # Day Order


class Order(BaseModel):
    """Order model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0
    average_fill_price: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    def cancel(self) -> None:
        """Cancel the order."""
        if self.is_active():
            self.status = OrderStatus.CANCELLED
            self.updated_at = datetime.utcnow()


class OrderManager:
    """Manages orders."""
    
    def __init__(self):
        """Initialize order manager."""
        self.orders: dict[str, Order] = {}
        self.active_orders: List[Order] = []
        self.order_history: List[Order] = []
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> Order:
        """Create a new order."""
        order = Order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )
        
        self.orders[order.id] = order
        self.active_orders.append(order)
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.is_active():
                order.cancel()
                self.active_orders.remove(order)
                self.order_history.append(order)
                return True
        return False
    
    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: Optional[float] = None,
        average_fill_price: Optional[float] = None,
    ) -> bool:
        """Update order status."""
        if order_id in self.orders:
            order = self.orders[order_id]
            order.status = status
            
            if filled_quantity is not None:
                order.filled_quantity = filled_quantity
            
            if average_fill_price is not None:
                order.average_fill_price = average_fill_price
            
            order.updated_at = datetime.utcnow()
            
            # Move to history if completed
            if not order.is_active() and order in self.active_orders:
                self.active_orders.remove(order)
                self.order_history.append(order)
            
            return True
        return False
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get active orders."""
        if symbol:
            return [o for o in self.active_orders if o.symbol == symbol]
        return self.active_orders.copy()
    
    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Order]:
        """Get order history."""
        history = self.order_history
        if symbol:
            history = [o for o in history if o.symbol == symbol]
        return history[-limit:]
