"""
Single source of truth for P&L calculations.
"""

from typing import Dict, Optional

def calculate_pnl(
    quantity: float,
    entry_price: float, 
    mark_price: float,
    realized_pnl: float = 0.0,
    fees: float = 0.0
) -> Dict[str, float]:
    """
    Single P&L calculation function used across all Sofia components.
    
    Formula: pnl = realized + (mark - entry) * qty - fees
    
    Args:
        quantity: Position size (positive for long, negative for short)
        entry_price: Average entry price
        mark_price: Current market price
        realized_pnl: Already realized P&L from previous trades
        fees: Total fees paid
    
    Returns:
        Dict with unrealized_pnl, total_pnl, and pnl_percent
    """
    
    # Calculate unrealized P&L
    if quantity != 0:
        unrealized_pnl = (mark_price - entry_price) * quantity
    else:
        unrealized_pnl = 0.0
    
    # Total P&L = realized + unrealized - fees
    total_pnl = realized_pnl + unrealized_pnl - fees
    
    # Calculate percentage (based on position value at entry)
    position_value = abs(quantity * entry_price) if quantity != 0 else 1.0
    pnl_percent = (total_pnl / position_value) * 100 if position_value > 0 else 0.0
    
    return {
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "total_pnl": total_pnl,
        "pnl_percent": pnl_percent,
        "fees": fees
    }

def calculate_portfolio_pnl(positions: Dict, prices: Dict) -> Dict[str, float]:
    """
    Calculate total portfolio P&L from positions.
    
    Args:
        positions: Dict of {symbol: {quantity, entry_price, realized_pnl, fees}}
        prices: Dict of {symbol: current_price}
    
    Returns:
        Portfolio-level P&L metrics
    """
    total_unrealized = 0.0
    total_realized = 0.0
    total_fees = 0.0
    total_value = 0.0
    
    for symbol, position in positions.items():
        quantity = position.get("quantity", 0)
        entry_price = position.get("entry_price", 0)
        realized_pnl = position.get("realized_pnl", 0)
        fees = position.get("fees", 0)
        
        if quantity != 0 and symbol in prices:
            mark_price = prices[symbol]
            
            pnl_data = calculate_pnl(
                quantity=quantity,
                entry_price=entry_price,
                mark_price=mark_price,
                realized_pnl=realized_pnl,
                fees=fees
            )
            
            total_unrealized += pnl_data["unrealized_pnl"]
            total_realized += pnl_data["realized_pnl"]
            total_fees += fees
            
            # Add position value to portfolio
            total_value += abs(quantity * mark_price)
    
    total_pnl = total_realized + total_unrealized - total_fees
    
    return {
        "total_unrealized_pnl": total_unrealized,
        "total_realized_pnl": total_realized,
        "total_pnl": total_pnl,
        "total_fees": total_fees,
        "total_position_value": total_value
    }