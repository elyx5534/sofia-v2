"""
Paper Trading Simulation API
Provides simulated trading with realistic fees and slippage
"""
from decimal import Decimal
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import json

router = APIRouter(prefix="/paper", tags=["paper-trading"])

# Paper Trading Configuration
INITIAL_BALANCE = Decimal("100000.00")
FEE_RATE = Decimal("0.001")  # 0.1% fee
SLIPPAGE_RATE = Decimal("0.0005")  # 0.05% slippage

# In-memory storage (replace with database in production)
_paper_state = {
    "balance": str(INITIAL_BALANCE),
    "positions": {},
    "orders": [],
    "trades": [],
    "total_fees": "0.00",
    "realized_pnl": "0.00",
    "start_time": datetime.utcnow().isoformat()
}

# Models
class PaperOrder(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    quantity: str
    order_type: str = "market"
    price: Optional[str] = None
    
class PaperOrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    quantity: str
    executed_price: str
    fee: str
    total_cost: str
    timestamp: str
    status: str = "filled"

class PaperPosition(BaseModel):
    symbol: str
    quantity: str
    avg_price: str
    current_price: str
    unrealized_pnl: str
    realized_pnl: str
    value: str

class PaperPortfolio(BaseModel):
    cash_balance: str
    positions: List[PaperPosition]
    total_value: str
    total_pnl: str
    total_fees: str
    win_rate: str
    trade_count: int
    start_time: str

def get_market_price(symbol: str) -> Decimal:
    """
    Get current market price (mock implementation)
    In production, this would fetch from real data source
    """
    # Mock prices
    prices = {
        "BTCUSDT": Decimal("67500.00"),
        "ETHUSDT": Decimal("3200.00"),
        "SOLUSDT": Decimal("145.50"),
        "ADAUSDT": Decimal("0.68"),
        "BNBUSDT": Decimal("580.00")
    }
    return prices.get(symbol, Decimal("100.00"))

def apply_slippage(price: Decimal, side: str) -> Decimal:
    """Apply slippage to execution price"""
    if side == "buy":
        return price * (Decimal("1") + SLIPPAGE_RATE)
    else:
        return price * (Decimal("1") - SLIPPAGE_RATE)

def calculate_fee(quantity: Decimal, price: Decimal) -> Decimal:
    """Calculate trading fee"""
    return quantity * price * FEE_RATE

@router.post("/orders", response_model=PaperOrderResponse)
async def place_paper_order(order: PaperOrder):
    """
    Place a simulated paper trading order
    """
    try:
        # Get market price
        market_price = get_market_price(order.symbol)
        
        # Apply slippage
        executed_price = apply_slippage(market_price, order.side)
        
        # Calculate values
        quantity = Decimal(order.quantity)
        fee = calculate_fee(quantity, executed_price)
        total_cost = quantity * executed_price + fee
        
        # Check balance for buy orders
        if order.side == "buy":
            balance = Decimal(_paper_state["balance"])
            if balance < total_cost:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient balance. Required: {total_cost}, Available: {balance}"
                )
            
            # Update balance
            _paper_state["balance"] = str(balance - total_cost)
            
            # Update position
            if order.symbol not in _paper_state["positions"]:
                _paper_state["positions"][order.symbol] = {
                    "quantity": "0",
                    "avg_price": "0",
                    "realized_pnl": "0"
                }
            
            pos = _paper_state["positions"][order.symbol]
            old_qty = Decimal(pos["quantity"])
            old_avg = Decimal(pos["avg_price"]) if old_qty > 0 else Decimal("0")
            
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_avg) + (quantity * executed_price)) / new_qty if new_qty > 0 else Decimal("0")
            
            pos["quantity"] = str(new_qty)
            pos["avg_price"] = str(new_avg)
            
        else:  # sell
            if order.symbol not in _paper_state["positions"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"No position in {order.symbol}"
                )
            
            pos = _paper_state["positions"][order.symbol]
            pos_qty = Decimal(pos["quantity"])
            
            if pos_qty < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient position. Have: {pos_qty}, Selling: {quantity}"
                )
            
            # Calculate realized P&L
            avg_price = Decimal(pos["avg_price"])
            realized_pnl = quantity * (executed_price - avg_price) - fee
            
            # Update position
            new_qty = pos_qty - quantity
            if new_qty == 0:
                del _paper_state["positions"][order.symbol]
            else:
                pos["quantity"] = str(new_qty)
            
            # Update realized P&L
            pos["realized_pnl"] = str(Decimal(pos.get("realized_pnl", "0")) + realized_pnl)
            _paper_state["realized_pnl"] = str(Decimal(_paper_state["realized_pnl"]) + realized_pnl)
            
            # Update balance
            balance = Decimal(_paper_state["balance"])
            _paper_state["balance"] = str(balance + (quantity * executed_price) - fee)
        
        # Update total fees
        _paper_state["total_fees"] = str(Decimal(_paper_state["total_fees"]) + fee)
        
        # Create order record
        order_id = str(uuid.uuid4())[:8]
        order_record = {
            "order_id": order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": str(quantity),
            "executed_price": str(executed_price),
            "fee": str(fee),
            "total_cost": str(total_cost),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "filled"
        }
        
        _paper_state["orders"].append(order_record)
        _paper_state["trades"].append(order_record)
        
        return PaperOrderResponse(**order_record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_paper_orders(limit: int = 50):
    """Get recent paper trading orders"""
    orders = _paper_state["orders"][-limit:]
    return {"orders": orders, "total": len(_paper_state["orders"])}

@router.get("/positions")
async def get_paper_positions():
    """Get current paper trading positions"""
    positions = []
    for symbol, pos_data in _paper_state["positions"].items():
        current_price = get_market_price(symbol)
        quantity = Decimal(pos_data["quantity"])
        avg_price = Decimal(pos_data["avg_price"])
        
        unrealized_pnl = quantity * (current_price - avg_price)
        value = quantity * current_price
        
        positions.append({
            "symbol": symbol,
            "quantity": str(quantity),
            "avg_price": str(avg_price),
            "current_price": str(current_price),
            "unrealized_pnl": str(unrealized_pnl),
            "realized_pnl": pos_data.get("realized_pnl", "0"),
            "value": str(value)
        })
    
    return {"positions": positions}

@router.get("/portfolio")
async def get_paper_portfolio():
    """Get complete paper trading portfolio summary"""
    # Calculate position values
    positions = []
    total_position_value = Decimal("0")
    total_unrealized_pnl = Decimal("0")
    
    for symbol, pos_data in _paper_state["positions"].items():
        current_price = get_market_price(symbol)
        quantity = Decimal(pos_data["quantity"])
        avg_price = Decimal(pos_data["avg_price"])
        
        unrealized_pnl = quantity * (current_price - avg_price)
        value = quantity * current_price
        
        total_position_value += value
        total_unrealized_pnl += unrealized_pnl
        
        positions.append(PaperPosition(
            symbol=symbol,
            quantity=str(quantity),
            avg_price=str(avg_price),
            current_price=str(current_price),
            unrealized_pnl=str(unrealized_pnl),
            realized_pnl=pos_data.get("realized_pnl", "0"),
            value=str(value)
        ))
    
    # Calculate totals
    cash_balance = Decimal(_paper_state["balance"])
    total_value = cash_balance + total_position_value
    realized_pnl = Decimal(_paper_state["realized_pnl"])
    total_pnl = realized_pnl + total_unrealized_pnl
    
    # Calculate win rate
    winning_trades = sum(1 for t in _paper_state["trades"] if t.get("pnl", 0) > 0)
    total_trades = len(_paper_state["trades"])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return PaperPortfolio(
        cash_balance=str(cash_balance),
        positions=positions,
        total_value=str(total_value),
        total_pnl=str(total_pnl),
        total_fees=_paper_state["total_fees"],
        win_rate=f"{win_rate:.1f}",
        trade_count=total_trades,
        start_time=_paper_state["start_time"]
    )

@router.post("/reset")
async def reset_paper_trading():
    """Reset paper trading to initial state"""
    global _paper_state
    _paper_state = {
        "balance": str(INITIAL_BALANCE),
        "positions": {},
        "orders": [],
        "trades": [],
        "total_fees": "0.00",
        "realized_pnl": "0.00",
        "start_time": datetime.utcnow().isoformat()
    }
    return {"message": "Paper trading reset successful", "initial_balance": str(INITIAL_BALANCE)}

@router.get("/config")
async def get_paper_config():
    """Get paper trading configuration"""
    return {
        "initial_balance": str(INITIAL_BALANCE),
        "fee_rate": str(FEE_RATE),
        "slippage_rate": str(SLIPPAGE_RATE),
        "available_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "BNBUSDT"]
    }