"""
FIFO-based P&L Accounting with Fees and Mark-to-Market
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
import json
from pathlib import Path


@dataclass
class Lot:
    """Represents a FIFO lot for position tracking"""
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    fee_paid: Decimal
    timestamp: datetime
    lot_id: str
    
    def remaining_value(self) -> Decimal:
        """Value of remaining quantity including fees"""
        return self.quantity * self.entry_price + self.fee_paid


@dataclass
class Fill:
    """Represents a trade fill"""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: Decimal
    price: Decimal
    fee_pct: Decimal
    timestamp: datetime
    fill_id: str


class FIFOAccounting:
    """FIFO-based accounting for P&L tracking"""
    
    def __init__(self, initial_cash: Decimal = Decimal("1000.0")):
        self.cash: Decimal = initial_cash
        self.lots: Dict[str, List[Lot]] = {}  # symbol -> list of lots
        self.realized_pnl: Decimal = Decimal("0")
        self.total_fees_paid: Decimal = Decimal("0")
        self.fill_history: List[Fill] = []
        
    def update_on_fill(self, fill: Fill) -> Dict[str, Decimal]:
        """Update accounting on trade fill"""
        self.fill_history.append(fill)
        
        fee_amount = fill.quantity * fill.price * (fill.fee_pct / Decimal("100"))
        self.total_fees_paid += fee_amount
        
        if fill.side == "buy":
            return self._process_buy(fill, fee_amount)
        else:  # sell
            return self._process_sell(fill, fee_amount)
    
    def _process_buy(self, fill: Fill, fee_amount: Decimal) -> Dict[str, Decimal]:
        """Process buy order - add to lots"""
        # Deduct cash for purchase
        total_cost = fill.quantity * fill.price + fee_amount
        self.cash -= total_cost
        
        # Create new lot
        lot = Lot(
            symbol=fill.symbol,
            quantity=fill.quantity,
            entry_price=fill.price,
            fee_paid=fee_amount,
            timestamp=fill.timestamp,
            lot_id=fill.fill_id
        )
        
        if fill.symbol not in self.lots:
            self.lots[fill.symbol] = []
        self.lots[fill.symbol].append(lot)
        
        return {
            "cash": self.cash,
            "realized_pnl": Decimal("0"),
            "position_change": fill.quantity
        }
    
    def _process_sell(self, fill: Fill, fee_amount: Decimal) -> Dict[str, Decimal]:
        """Process sell order - FIFO matching"""
        if fill.symbol not in self.lots or not self.lots[fill.symbol]:
            # No position to sell - shouldn't happen in practice
            return {
                "cash": self.cash,
                "realized_pnl": Decimal("0"),
                "position_change": Decimal("0")
            }
        
        remaining_qty = fill.quantity
        realized_on_fill = Decimal("0")
        lots = self.lots[fill.symbol]
        
        while remaining_qty > 0 and lots:
            lot = lots[0]
            
            if lot.quantity <= remaining_qty:
                # Consume entire lot
                qty_from_lot = lot.quantity
                lots.pop(0)
            else:
                # Partial consumption
                qty_from_lot = remaining_qty
                lot.quantity -= qty_from_lot
                # Adjust lot's fee proportionally
                lot.fee_paid *= (lot.quantity / (lot.quantity + qty_from_lot))
            
            # Calculate realized P&L for this portion
            sell_proceeds = qty_from_lot * fill.price
            cost_basis = qty_from_lot * lot.entry_price
            lot_fee_portion = lot.fee_paid * (qty_from_lot / (qty_from_lot + lot.quantity))
            
            realized_on_fill += sell_proceeds - cost_basis - lot_fee_portion - (fee_amount * qty_from_lot / fill.quantity)
            remaining_qty -= qty_from_lot
        
        # Update cash and realized P&L
        self.cash += fill.quantity * fill.price - fee_amount
        self.realized_pnl += realized_on_fill
        
        return {
            "cash": self.cash,
            "realized_pnl": realized_on_fill,
            "position_change": -fill.quantity
        }
    
    def get_realized(self) -> Decimal:
        """Get total realized P&L"""
        return self.realized_pnl
    
    def get_unrealized(self, prices: Dict[str, Decimal], mid_or_bidask: str = "mid") -> Decimal:
        """Calculate unrealized P&L using current market prices"""
        unrealized = Decimal("0")
        
        for symbol, symbol_lots in self.lots.items():
            if symbol not in prices:
                continue
                
            market_price = prices[symbol]
            
            for lot in symbol_lots:
                # Market value - (cost basis + fees)
                market_value = lot.quantity * market_price
                cost_with_fees = lot.quantity * lot.entry_price + lot.fee_paid
                unrealized += market_value - cost_with_fees
        
        return unrealized
    
    def get_equity(self, prices: Optional[Dict[str, Decimal]] = None) -> Decimal:
        """Get total equity (cash + unrealized P&L)"""
        if prices:
            return self.cash + self.get_unrealized(prices)
        return self.cash
    
    def get_position(self, symbol: str) -> Decimal:
        """Get total position size for a symbol"""
        if symbol not in self.lots:
            return Decimal("0")
        return sum(lot.quantity for lot in self.lots[symbol])
    
    def get_average_entry(self, symbol: str) -> Optional[Decimal]:
        """Get weighted average entry price for a symbol"""
        if symbol not in self.lots or not self.lots[symbol]:
            return None
        
        total_value = Decimal("0")
        total_quantity = Decimal("0")
        
        for lot in self.lots[symbol]:
            total_value += lot.quantity * lot.entry_price
            total_quantity += lot.quantity
        
        if total_quantity == 0:
            return None
        
        return total_value / total_quantity
    
    def to_dict(self) -> Dict:
        """Export state to dictionary"""
        return {
            "cash": float(self.cash),
            "realized_pnl": float(self.realized_pnl),
            "total_fees_paid": float(self.total_fees_paid),
            "positions": {
                symbol: {
                    "quantity": float(self.get_position(symbol)),
                    "avg_entry": float(self.get_average_entry(symbol) or 0),
                    "lots": len(lots)
                }
                for symbol, lots in self.lots.items()
                if lots
            }
        }
    
    def save_state(self, filepath: Path):
        """Save accounting state to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)