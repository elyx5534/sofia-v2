"""Position management module."""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import uuid


class Position(BaseModel):
    """Position model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def update_price(self, price: float) -> None:
        """Update current price and unrealized PnL."""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity
        self.updated_at = datetime.utcnow()
    
    def close_position(self, exit_price: float) -> float:
        """Close position and return realized PnL."""
        pnl = (exit_price - self.entry_price) * self.quantity
        self.realized_pnl = pnl
        self.quantity = 0
        self.updated_at = datetime.utcnow()
        return pnl
    
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.unrealized_pnl > 0
    
    def get_return_percentage(self) -> float:
        """Get return percentage."""
        if self.entry_price == 0:
            return 0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100


class PositionManager:
    """Manages positions."""
    
    def __init__(self):
        """Initialize position manager."""
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.total_realized_pnl: float = 0
    
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
    ) -> Position:
        """Open a new position or add to existing."""
        if symbol in self.positions:
            # Add to existing position (averaging)
            existing = self.positions[symbol]
            total_quantity = existing.quantity + quantity
            avg_price = ((existing.entry_price * existing.quantity) + 
                        (entry_price * quantity)) / total_quantity
            
            existing.quantity = total_quantity
            existing.entry_price = avg_price
            existing.updated_at = datetime.utcnow()
            return existing
        else:
            # Create new position
            position = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
            )
            self.positions[symbol] = position
            return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        quantity: Optional[float] = None,
    ) -> Optional[float]:
        """Close position fully or partially."""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        if quantity is None or quantity >= position.quantity:
            # Close full position
            pnl = position.close_position(exit_price)
            self.total_realized_pnl += pnl
            self.closed_positions.append(position)
            del self.positions[symbol]
            return pnl
        else:
            # Partial close
            pnl = (exit_price - position.entry_price) * quantity
            position.quantity -= quantity
            position.realized_pnl += pnl
            position.updated_at = datetime.utcnow()
            self.total_realized_pnl += pnl
            return pnl
    
    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update prices for all positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    def get_total_value(self) -> float:
        """Get total position value."""
        return sum(p.current_price * p.quantity for p in self.positions.values())
