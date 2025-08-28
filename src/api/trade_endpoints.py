"""
Paper Trading Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
from datetime import datetime

router = APIRouter(prefix="/trade", tags=["trading"])

# Global paper trading state
class PaperBroker:
    def __init__(self):
        self.balance = 100000.0  # Starting balance
        self.positions = {}
        self.trades = []
        self.realized_pnl = 0.0
        self.fee_rate = 0.001  # 0.1%
        self.slippage = 0.0005  # 0.05%
        
    def execute_trade(self, symbol: str, price: float, score: float):
        """Execute trade based on AI score"""
        threshold = 70.0  # Score threshold for buying
        
        if score >= threshold and symbol not in self.positions:
            # Buy signal
            size = min(10000, self.balance * 0.1)  # Max 10% per position
            qty = size / price
            fee = size * self.fee_rate
            slippage_cost = size * self.slippage
            total_cost = size + fee + slippage_cost
            
            if total_cost <= self.balance:
                self.balance -= total_cost
                self.positions[symbol] = {
                    "qty": qty,
                    "entry_price": price * (1 + self.slippage),
                    "current_price": price,
                    "unrealized_pnl": 0.0
                }
                self.trades.append({
                    "symbol": symbol,
                    "side": "BUY",
                    "price": price,
                    "qty": qty,
                    "fee": fee,
                    "timestamp": datetime.now().isoformat()
                })
                return {"action": "BUY", "symbol": symbol, "qty": qty, "price": price}
                
        elif score < 50 and symbol in self.positions:
            # Sell signal
            pos = self.positions[symbol]
            value = pos["qty"] * price
            fee = value * self.fee_rate
            slippage_cost = value * self.slippage
            proceeds = value - fee - slippage_cost
            
            pnl = proceeds - (pos["qty"] * pos["entry_price"])
            self.realized_pnl += pnl
            self.balance += proceeds
            
            del self.positions[symbol]
            self.trades.append({
                "symbol": symbol,
                "side": "SELL",
                "price": price,
                "qty": pos["qty"],
                "fee": fee,
                "pnl": pnl,
                "timestamp": datetime.now().isoformat()
            })
            return {"action": "SELL", "symbol": symbol, "qty": pos["qty"], "price": price, "pnl": pnl}
            
        return {"action": "HOLD", "symbol": symbol}
    
    def update_prices(self, prices: dict):
        """Update position prices"""
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos["current_price"] = prices[symbol]
                pos["unrealized_pnl"] = (pos["current_price"] - pos["entry_price"]) * pos["qty"]
    
    def get_account_summary(self):
        """Get account status"""
        total_position_value = sum(
            pos["qty"] * pos["current_price"] 
            for pos in self.positions.values()
        )
        equity = self.balance + total_position_value
        unrealized_pnl = sum(pos["unrealized_pnl"] for pos in self.positions.values())
        
        return {
            "cash": round(self.balance, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_pnl": round(self.realized_pnl + unrealized_pnl, 2),
            "positions": len(self.positions),
            "n_trades": len(self.trades)
        }

# Global broker instance
broker = PaperBroker()

class TradeRequest(BaseModel):
    symbol: str
    price: float
    score: float

@router.post("/on_tick")
async def on_tick(request: TradeRequest):
    """Execute trade on new tick/score"""
    result = broker.execute_trade(request.symbol, request.price, request.score)
    return result

@router.get("/account")
async def get_account():
    """Get paper trading account status"""
    return broker.get_account_summary()

@router.get("/positions")
async def get_positions():
    """Get current positions"""
    return broker.positions

@router.get("/history")
async def get_trade_history():
    """Get trade history"""
    return {"trades": broker.trades[-50:]}  # Last 50 trades

@router.post("/reset")
async def reset_account():
    """Reset paper trading account"""
    global broker
    broker = PaperBroker()
    return {"message": "Account reset", "balance": broker.balance}