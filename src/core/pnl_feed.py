"""
P&L Feed using FIFO Accounting
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from src.core.accounting import FIFOAccounting, Fill
import time


class PnLFeed:
    """Manages P&L tracking and timeseries generation"""
    
    def __init__(self, initial_capital: Decimal = Decimal("1000.0")):
        self.accounting = FIFOAccounting(initial_capital)
        self.initial_capital = initial_capital
        self.timeseries_data: List[Dict] = []
        self.start_time = time.time()
        self.session_active = False
        
        # Initialize with starting point
        self.timeseries_data.append({
            "ts_ms": int(self.start_time * 1000),
            "equity": float(initial_capital)
        })
    
    def process_fill(self, symbol: str, side: str, quantity: float, price: float, fee_pct: float = 0.1):
        """Process a trade fill through accounting"""
        fill = Fill(
            symbol=symbol,
            side=side,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            fee_pct=Decimal(str(fee_pct)),
            timestamp=datetime.now(),
            fill_id=f"{symbol}_{int(time.time() * 1000)}"
        )
        
        return self.accounting.update_on_fill(fill)
    
    def update_timeseries(self, market_prices: Dict[str, float]):
        """Update timeseries with current equity"""
        prices_decimal = {
            symbol: Decimal(str(price)) 
            for symbol, price in market_prices.items()
        }
        
        equity = self.accounting.get_equity(prices_decimal)
        
        self.timeseries_data.append({
            "ts_ms": int(time.time() * 1000),
            "equity": float(equity)
        })
        
        # Keep last 100 points
        if len(self.timeseries_data) > 100:
            self.timeseries_data = self.timeseries_data[-100:]
        
        return float(equity)
    
    def write_feeds(self, market_prices: Dict[str, float], session_complete: bool = False):
        """Write timeseries and summary JSON files"""
        prices_decimal = {
            symbol: Decimal(str(price)) 
            for symbol, price in market_prices.items()
        }
        
        # Calculate current values
        equity = self.accounting.get_equity(prices_decimal)
        realized_pnl = self.accounting.get_realized()
        unrealized_pnl = self.accounting.get_unrealized(prices_decimal)
        total_pnl = equity - self.initial_capital
        pnl_percentage = (total_pnl / self.initial_capital * Decimal("100")) if self.initial_capital > 0 else Decimal("0")
        
        # Write timeseries
        timeseries_path = Path("logs/pnl_timeseries.json")
        timeseries_path.parent.mkdir(exist_ok=True)
        with open(timeseries_path, 'w') as f:
            json.dump(self.timeseries_data, f, indent=2)
        
        # Write summary
        summary = {
            "initial_capital": float(self.initial_capital),
            "final_capital": float(equity),
            "realized_pnl": float(realized_pnl),
            "unrealized_pnl": float(unrealized_pnl),
            "total_pnl": float(total_pnl),
            "pnl_percentage": float(pnl_percentage),
            "total_trades": len(self.accounting.fill_history),
            "total_fees_paid": float(self.accounting.total_fees_paid),
            "start_timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_timestamp": datetime.now().isoformat(),
            "is_running": not session_complete,
            "session_complete": session_complete,
            "accounting_state": self.accounting.to_dict()
        }
        
        summary_path = Path("logs/pnl_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save accounting state
        self.accounting.save_state(Path("logs/accounting_state.json"))
        
        return summary
    
    async def run_feed_loop(self, update_interval: int = 5, duration_minutes: int = 5):
        """Run feed loop for specified duration"""
        self.session_active = True
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time and self.session_active:
            # Simulate market prices (in production, fetch real prices)
            market_prices = {
                "BTC/USDT": 108000 + (time.time() % 100) * 10  # Simulate price movement
            }
            
            # Update timeseries
            self.update_timeseries(market_prices)
            
            # Write feeds
            self.write_feeds(market_prices, session_complete=False)
            
            await asyncio.sleep(update_interval)
        
        # Final update
        market_prices = {"BTC/USDT": 108000}
        self.write_feeds(market_prices, session_complete=True)
        self.session_active = False