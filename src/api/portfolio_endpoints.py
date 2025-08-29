"""
Portfolio API endpoints with proper decimal handling
"""
from decimal import Decimal
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import json

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Pydantic models with string decimals for precision
class Position(BaseModel):
    symbol: str
    qty: str  # String to preserve precision
    mark_price: str  # String decimal
    currency: str
    unrealized_pnl: Optional[str] = "0"
    realized_pnl: Optional[str] = "0"

class PortfolioSummary(BaseModel):
    base_currency: str = "USD"
    cash_balance: str  # String decimal
    fees_accrued: str = "0"
    positions: List[Position]
    fx_rates: Dict[str, str]  # e.g., {"USDTRY": "34.50", "EURUSD": "1.08"}
    total_balance: Optional[str] = None  # Calculated on backend
    pnl_24h: Optional[str] = "0"
    pnl_percentage_24h: Optional[str] = "0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# In-memory state for demo (replace with database)
_portfolio_state = {
    "base_currency": "USD",
    "cash_balance": "50000.00",
    "fees_accrued": "125.50",
    "positions": [
        {
            "symbol": "BTCUSDT",
            "qty": "0.5",
            "mark_price": "67500.00",
            "currency": "USDT",
            "unrealized_pnl": "2500.00",
            "realized_pnl": "1000.00"
        },
        {
            "symbol": "ETHUSDT",
            "qty": "10",
            "mark_price": "3200.00",
            "currency": "USDT",
            "unrealized_pnl": "500.00",
            "realized_pnl": "200.00"
        },
        {
            "symbol": "SOLUSDT",
            "qty": "100",
            "mark_price": "145.50",
            "currency": "USDT",
            "unrealized_pnl": "-250.00",
            "realized_pnl": "50.00"
        }
    ],
    "fx_rates": {
        "USDTRY": "34.50",
        "EURUSD": "1.08",
        "GBPUSD": "1.27",
        "USDTUSDT": "1.00",
        "USDTUSD": "1.00"
    }
}

def calculate_total_balance(summary: dict) -> str:
    """
    Calculate total balance using Decimal for precision
    Formula: TB = cash_balance + Σ(position.qty * position.mark_price) - fees_accrued
    """
    base_currency = summary["base_currency"]
    cash = Decimal(summary["cash_balance"])
    fees = Decimal(summary.get("fees_accrued", "0"))
    fx_rates = summary["fx_rates"]
    
    # Calculate positions value
    positions_value = Decimal("0")
    for pos in summary["positions"]:
        qty = Decimal(pos["qty"])
        price = Decimal(pos["mark_price"])
        position_value = qty * price
        
        # Convert to base currency if needed
        if pos["currency"] != base_currency:
            # Get conversion rate
            fx_key = f"{pos['currency']}{base_currency}"
            if fx_key in fx_rates:
                rate = Decimal(fx_rates[fx_key])
                position_value *= rate
            elif pos["currency"] == "USDT" and base_currency == "USD":
                # USDT = USD for simplicity
                pass
        
        positions_value += position_value
    
    total = cash + positions_value - fees
    return str(total.quantize(Decimal("0.01")))  # 2 decimal places

@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    """
    Get portfolio summary with calculated total balance
    """
    try:
        # Calculate total balance
        total_balance = calculate_total_balance(_portfolio_state)
        
        # Calculate 24h change (mock data for demo)
        yesterday_balance = Decimal(total_balance) * Decimal("0.98")  # Mock: -2%
        pnl_24h = Decimal(total_balance) - yesterday_balance
        pnl_percentage = (pnl_24h / yesterday_balance * Decimal("100"))
        
        summary = PortfolioSummary(
            **_portfolio_state,
            total_balance=total_balance,
            pnl_24h=str(pnl_24h.quantize(Decimal("0.01"))),
            pnl_percentage_24h=str(pnl_percentage.quantize(Decimal("0.01")))
        )
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions():
    """
    Get all positions
    """
    return _portfolio_state["positions"]

@router.get("/balance")
async def get_balance():
    """
    Get current balance info
    """
    total = calculate_total_balance(_portfolio_state)
    return {
        "base_currency": _portfolio_state["base_currency"],
        "cash_balance": _portfolio_state["cash_balance"],
        "total_balance": total,
        "fees_accrued": _portfolio_state["fees_accrued"]
    }

@router.post("/update-position")
async def update_position(position: Position):
    """
    Update or add a position
    """
    # Find and update or append
    positions = _portfolio_state["positions"]
    for i, pos in enumerate(positions):
        if pos["symbol"] == position.symbol:
            positions[i] = position.dict()
            return {"message": "Position updated", "position": position}
    
    # Not found, add new
    positions.append(position.dict())
    return {"message": "Position added", "position": position}

@router.get("/fx-rates")
async def get_fx_rates():
    """
    Get current FX rates
    """
    return _portfolio_state["fx_rates"]

@router.post("/fx-rates")
async def update_fx_rates(rates: Dict[str, str]):
    """
    Update FX rates
    """
    _portfolio_state["fx_rates"].update(rates)
    return {"message": "FX rates updated", "rates": _portfolio_state["fx_rates"]}