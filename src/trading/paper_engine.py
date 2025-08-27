"""
Paper trading engine using real prices and single P&L calculation.
"""

import time
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from src.database.models import get_database
from src.portfolio.pnl import calculate_pnl
from src.services.price_service_real import get_price_service

logger = logging.getLogger(__name__)

class PaperTradingEngine:
    """Paper trading engine with real price execution."""
    
    def __init__(self):
        self.db = get_database()
        self.fee_rate = 0.001  # 0.1% fee per trade
        
    async def place_order(self, symbol: str, side: str, usd_amount: float, 
                         strategy: str = "manual") -> Dict:
        """
        Place paper trading order in USD amount.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: "buy" or "sell"  
            usd_amount: Dollar amount to trade
            strategy: Strategy name for audit
        """
        
        # Get current price
        price_service = await get_price_service()
        price_data = await price_service.get_price(symbol)
        
        if not price_data:
            return {
                "status": "error",
                "message": f"Could not get price for {symbol}"
            }
        
        current_price = price_data["price"]
        
        # Calculate quantity based on USD amount
        if side.lower() == "buy":
            quantity = usd_amount / current_price
        elif side.lower() == "sell":
            # For sells, usd_amount represents the USD value to sell
            quantity = usd_amount / current_price
        else:
            return {
                "status": "error", 
                "message": "Invalid side. Use 'buy' or 'sell'"
            }
        
        # Calculate fees
        fees = usd_amount * self.fee_rate
        
        # Get current account state
        account = self.db.get_account_state()
        if not account:
            return {
                "status": "error",
                "message": "Account not initialized"
            }
        
        # Validate order
        if side.lower() == "buy":
            total_cost = usd_amount + fees
            if total_cost > account["cash_balance"]:
                return {
                    "status": "error",
                    "message": f"Insufficient funds. Need ${total_cost:.2f}, have ${account['cash_balance']:.2f}"
                }
        elif side.lower() == "sell":
            # Check position exists
            positions = self.db.get_positions()
            position = positions.get(symbol)
            if not position or position["quantity"] < quantity:
                available = position["quantity"] if position else 0
                return {
                    "status": "error",
                    "message": f"Insufficient {symbol}. Need {quantity:.6f}, have {available:.6f}"
                }
        
        # Execute trade
        trade_id = f"{symbol}_{side}_{int(time.time() * 1000)}"
        
        # Add to trades table
        self.db.add_trade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            fees=fees,
            strategy=strategy
        )
        
        # Update positions
        await self._update_position_after_trade(symbol, side, quantity, current_price, fees)
        
        # Update account state
        await self._update_account_state()
        
        logger.info(f"Paper trade executed: {side.upper()} {quantity:.6f} {symbol} @ ${current_price:.2f}")
        
        return {
            "status": "success",
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": current_price,
            "usd_value": usd_amount,
            "fees": fees,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _update_position_after_trade(self, symbol: str, side: str, quantity: float, 
                                         price: float, fees: float):
        """Update position after trade execution."""
        positions = self.db.get_positions()
        position = positions.get(symbol)
        
        if not position:
            # New position
            if side.lower() == "buy":
                new_quantity = quantity
                new_avg_price = price
                new_realized_pnl = 0.0
                new_fees = fees
            else:
                # Can't sell what we don't have (should be caught in validation)
                return
        else:
            # Existing position
            if side.lower() == "buy":
                # Add to position - update average price
                total_value = (position["quantity"] * position["avg_entry_price"]) + (quantity * price)
                new_quantity = position["quantity"] + quantity
                new_avg_price = total_value / new_quantity if new_quantity != 0 else price
                new_realized_pnl = position["realized_pnl"]
                new_fees = position["total_fees"] + fees
                
            elif side.lower() == "sell":
                # Reduce position - realize P&L
                realized_gain = (price - position["avg_entry_price"]) * quantity
                new_quantity = position["quantity"] - quantity
                new_avg_price = position["avg_entry_price"]  # Keep same avg price for remaining
                new_realized_pnl = position["realized_pnl"] + realized_gain
                new_fees = position["total_fees"] + fees
        
        # Update database
        self.db.update_position(
            symbol=symbol,
            quantity=new_quantity,
            avg_entry_price=new_avg_price,
            realized_pnl=new_realized_pnl,
            fees=new_fees
        )
    
    async def _update_account_state(self):
        """Update account state with current portfolio value."""
        # Get current positions
        positions = self.db.get_positions()
        
        # Get current prices
        price_service = await get_price_service()
        total_equity = 0.0
        total_pnl = 0.0
        
        for symbol, position in positions.items():
            if position["quantity"] != 0:
                price_data = await price_service.get_price(symbol)
                if price_data:
                    current_price = price_data["price"]
                    position_value = position["quantity"] * current_price
                    total_equity += position_value
                    
                    # Calculate P&L using single source of truth
                    pnl_data = calculate_pnl(
                        quantity=position["quantity"],
                        entry_price=position["avg_entry_price"],
                        mark_price=current_price,
                        realized_pnl=position["realized_pnl"],
                        fees=position["total_fees"]
                    )
                    
                    total_pnl += pnl_data["total_pnl"]
        
        # Get current cash balance (calculate from starting balance and trades)
        account = self.db.get_account_state()
        starting_cash = 100000.0  # Default starting balance
        
        if account:
            # Calculate cash from trades
            trades = self.db.get_recent_trades(limit=1000)  # Get all trades
            cash_spent = 0.0
            cash_received = 0.0
            total_fees = 0.0
            
            for trade in trades:
                if trade["side"] == "buy":
                    cash_spent += trade["value"] + trade["fees"]
                elif trade["side"] == "sell":
                    cash_received += trade["value"] - trade["fees"]
                total_fees += trade["fees"]
            
            current_cash = starting_cash - cash_spent + cash_received
        else:
            current_cash = starting_cash
        
        total_equity += current_cash
        
        # Update database
        self.db.update_account_state(current_cash, total_equity, total_pnl)
    
    async def get_portfolio_summary(self) -> Dict:
        """Get complete portfolio summary with live prices."""
        # Update account state first
        await self._update_account_state()
        
        # Get account state
        account = self.db.get_account_state()
        if not account:
            return {"error": "Account not initialized"}
        
        # Get positions with live prices
        positions = self.db.get_positions()
        price_service = await get_price_service()
        
        positions_with_pnl = {}
        total_unrealized = 0.0
        total_realized = 0.0
        total_fees = 0.0
        
        for symbol, position in positions.items():
            if position["quantity"] != 0:
                price_data = await price_service.get_price(symbol)
                current_price = price_data["price"] if price_data else 0.0
                
                if current_price > 0:
                    pnl_data = calculate_pnl(
                        quantity=position["quantity"],
                        entry_price=position["avg_entry_price"],
                        mark_price=current_price,
                        realized_pnl=position["realized_pnl"],
                        fees=position["total_fees"]
                    )
                    
                    positions_with_pnl[symbol] = {
                        "quantity": position["quantity"],
                        "avg_entry_price": position["avg_entry_price"],
                        "current_price": current_price,
                        "market_value": position["quantity"] * current_price,
                        "unrealized_pnl": pnl_data["unrealized_pnl"],
                        "realized_pnl": pnl_data["realized_pnl"],
                        "total_pnl": pnl_data["total_pnl"],
                        "pnl_percent": pnl_data["pnl_percent"],
                        "fees": pnl_data["fees"]
                    }
                    
                    total_unrealized += pnl_data["unrealized_pnl"]
                    total_realized += pnl_data["realized_pnl"]
                    total_fees += pnl_data["fees"]
        
        return {
            "cash_balance": account["cash_balance"],
            "total_equity": account["total_equity"],
            "total_pnl": account["total_pnl"],
            "unrealized_pnl": total_unrealized,
            "realized_pnl": total_realized,
            "total_fees": total_fees,
            "positions": positions_with_pnl,
            "updated_at": account["updated_at"]
        }


# Global engine instance
_paper_engine = None

def get_paper_engine() -> PaperTradingEngine:
    """Get or create the global paper trading engine."""
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperTradingEngine()
    return _paper_engine