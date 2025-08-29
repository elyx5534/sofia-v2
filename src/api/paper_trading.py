"""
Paper Trading Engine for Sofia V2
Simulated broker with fills, positions, PnL tracking
"""

from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper", tags=["paper_trading"])


class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    price: Optional[float] = None  # None for market orders


class Position:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.quantity = Decimal("0")
        self.avg_price = Decimal("0")
        self.total_cost = Decimal("0")
        self.realized_pnl = Decimal("0")
        self.last_price = Decimal("0")
        
    def add_fill(self, qty: Decimal, price: Decimal, side: str, fee: Decimal):
        """Process a fill and update position"""
        if side == "buy":
            total_qty = self.quantity + qty
            if total_qty > 0:
                self.total_cost = self.total_cost + (qty * price) + fee
                self.avg_price = self.total_cost / total_qty if total_qty else Decimal("0")
            self.quantity = total_qty
        else:  # sell
            if qty > self.quantity:
                qty = self.quantity  # Can't sell more than we have
            
            # Calculate realized PnL on the sold portion
            if self.quantity > 0:
                cost_basis = (qty / self.quantity) * self.total_cost
                sale_proceeds = qty * price - fee
                self.realized_pnl += sale_proceeds - cost_basis
                
                # Update remaining position
                self.quantity -= qty
                if self.quantity > 0:
                    self.total_cost = self.total_cost * (self.quantity / (self.quantity + qty))
                else:
                    self.total_cost = Decimal("0")
                    self.avg_price = Decimal("0")
    
    def update_last_price(self, price: Decimal):
        """Update last known price for unrealized PnL calculation"""
        self.last_price = price
        
    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized PnL"""
        if self.quantity == 0:
            return Decimal("0")
        market_value = self.quantity * self.last_price
        return market_value - self.total_cost
        
    def to_dict(self) -> Dict[str, str]:
        """Convert to JSON-serializable dict with string decimals"""
        return {
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "avg_price": str(self.avg_price),
            "last_price": str(self.last_price),
            "total_cost": str(self.total_cost),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "market_value": str(self.quantity * self.last_price)
        }


class Fill:
    def __init__(self, symbol: str, side: str, qty: Decimal, price: Decimal, fee: Decimal):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.price = price
        self.fee = fee
        self.timestamp = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "qty": str(self.qty),
            "price": str(self.price),
            "fee": str(self.fee),
            "timestamp": self.timestamp.isoformat()
        }


class PaperTradingEngine:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.fills: List[Fill] = []
        self.initial_balance = Decimal("100000")
        self.cash_balance = self.initial_balance
        self.max_position_size = Decimal("10000")
        self.max_leverage = Decimal("1")
        self.fee_rate = Decimal("0.001")  # 0.1% fee
        self.slippage_rate = Decimal("0.0005")  # 0.05% slippage
        
    def reset(self):
        """Reset the paper trading account"""
        self.positions.clear()
        self.fills.clear()
        self.cash_balance = self.initial_balance
        logger.info("Paper trading account reset")
        
    def execute_order(self, symbol: str, side: str, qty: Decimal, price: Optional[Decimal] = None) -> Fill:
        """Execute a paper trade order"""
        # Validate side
        if side not in ["buy", "sell"]:
            raise ValueError(f"Invalid side: {side}")
            
        # Apply slippage to price
        if price:
            if side == "buy":
                price = price * (Decimal("1") + self.slippage_rate)
            else:
                price = price * (Decimal("1") - self.slippage_rate)
        else:
            # For market orders, we'd need to fetch current price
            raise ValueError("Market orders require price parameter")
            
        # Calculate fee
        notional = qty * price
        fee = notional * self.fee_rate
        
        # Risk checks
        if side == "buy":
            total_cost = notional + fee
            if total_cost > self.cash_balance:
                raise ValueError(f"Insufficient funds. Required: {total_cost}, Available: {self.cash_balance}")
            if notional > self.max_position_size:
                raise ValueError(f"Position size {notional} exceeds max {self.max_position_size}")
                
            # Update cash
            self.cash_balance -= total_cost
        else:  # sell
            # Check if we have enough to sell
            if symbol not in self.positions:
                raise ValueError(f"No position in {symbol}")
            if self.positions[symbol].quantity < qty:
                raise ValueError(f"Insufficient quantity. Have: {self.positions[symbol].quantity}, Selling: {qty}")
                
            # Update cash
            sale_proceeds = notional - fee
            self.cash_balance += sale_proceeds
            
        # Create fill
        fill = Fill(symbol, side, qty, price, fee)
        self.fills.append(fill)
        
        # Update position
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        self.positions[symbol].add_fill(qty, price, side, fee)
        
        # Clean up empty positions
        if self.positions[symbol].quantity == 0:
            del self.positions[symbol]
            
        logger.info(f"Executed {side} {qty} {symbol} @ {price} (fee: {fee})")
        return fill
        
    def get_total_value(self) -> Decimal:
        """Calculate total account value"""
        positions_value = sum(
            pos.quantity * pos.last_price 
            for pos in self.positions.values()
        )
        return self.cash_balance + positions_value
        
    def get_pnl_summary(self) -> Dict[str, str]:
        """Get PnL summary"""
        total_realized = sum(pos.realized_pnl for pos in self.positions.values())
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_value = self.get_total_value()
        
        return {
            "realized_pnl": str(total_realized),
            "unrealized_pnl": str(total_unrealized),
            "total_pnl": str(total_realized + total_unrealized),
            "total_value": str(total_value),
            "cash_balance": str(self.cash_balance),
            "initial_balance": str(self.initial_balance),
            "return_pct": str(((total_value / self.initial_balance) - 1) * 100)
        }
        
    async def update_prices(self, prices: Dict[str, Decimal]):
        """Update last prices for positions"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_last_price(price)


# Global paper trading engine instance
paper_engine = PaperTradingEngine()


@router.post("/orders")
async def create_order(order: OrderRequest) -> Dict[str, Any]:
    """Create a new paper trading order"""
    try:
        # Convert to Decimal
        qty = Decimal(str(order.qty))
        price = Decimal(str(order.price)) if order.price else None
        
        # Execute order
        fill = paper_engine.execute_order(order.symbol, order.side, qty, price)
        
        return {
            "success": True,
            "fill": fill.to_dict(),
            "message": f"Order executed: {order.side} {qty} {order.symbol}"
        }
    except Exception as e:
        logger.error(f"Order execution failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/positions")
async def get_positions() -> List[Dict[str, str]]:
    """Get all open positions"""
    return [pos.to_dict() for pos in paper_engine.positions.values()]


@router.get("/fills")
async def get_fills(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent fills"""
    # Return most recent fills first
    return [fill.to_dict() for fill in reversed(paper_engine.fills[-limit:])]


@router.get("/pnl")
async def get_pnl() -> Dict[str, str]:
    """Get PnL summary"""
    return paper_engine.get_pnl_summary()


@router.post("/reset")
async def reset_account() -> Dict[str, str]:
    """Reset paper trading account"""
    paper_engine.reset()
    return {
        "success": True,
        "message": "Paper trading account reset",
        "cash_balance": str(paper_engine.cash_balance)
    }


@router.post("/update-prices")
async def update_prices(prices: Dict[str, float]) -> Dict[str, str]:
    """Update last prices for positions (internal use)"""
    decimal_prices = {symbol: Decimal(str(price)) for symbol, price in prices.items()}
    await paper_engine.update_prices(decimal_prices)
    return {"success": True, "updated": len(decimal_prices)}