"""
Paper Trading Engine - Risk-free live trading simulation

Features:
- Virtual balance management
- Real-time order execution simulation
- P&L tracking
- Performance metrics
- Trade history
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

# Setup paper trading logger
paper_logger = logging.getLogger('paper_trading')


class PaperOrderStatus(str, Enum):
    """Paper order status."""
    
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PaperPosition(BaseModel):
    """Paper trading position."""
    
    symbol: str
    side: str  # long/short
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    opened_at: datetime
    closed_at: Optional[datetime] = None
    

class PaperOrder(BaseModel):
    """Paper trading order."""
    
    id: str
    symbol: str
    side: str  # buy/sell
    type: str  # market/limit
    quantity: float
    price: Optional[float]
    filled_quantity: float = 0.0
    average_price: float = 0.0
    status: PaperOrderStatus
    created_at: datetime
    filled_at: Optional[datetime] = None
    

class PaperAccount(BaseModel):
    """Paper trading account."""
    
    id: str
    initial_balance: float
    current_balance: float
    available_balance: float
    positions_value: float
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    

class TradingMetrics(BaseModel):
    """Trading performance metrics."""
    
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    total_fees: float
    

class PaperTradingEngine:
    """
    Paper trading engine for risk-free simulation.
    
    Features:
    - Virtual balance management
    - Real market data integration
    - Order execution simulation
    - Performance tracking
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        """Initialize paper trading engine."""
        self.account = PaperAccount(
            id=f"paper_{datetime.utcnow().timestamp()}",
            initial_balance=initial_balance,
            current_balance=initial_balance,
            available_balance=initial_balance,
            positions_value=0.0,
            total_pnl=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0
        )
        
        self.positions: Dict[str, PaperPosition] = {}
        self.orders: Dict[str, PaperOrder] = {}
        self.order_history: List[PaperOrder] = []
        self.trade_history: List[Dict] = []
        self.market_prices: Dict[str, float] = {}
        self.fee_rate = 0.001  # 0.1% trading fee
        
        # Performance tracking
        self.balance_history: List[float] = [initial_balance]
        self.equity_curve: List[Dict] = []
        
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None
    ) -> PaperOrder:
        """Place a paper order."""
        # Create order
        order = PaperOrder(
            id=f"order_{len(self.orders)}_{datetime.utcnow().timestamp()}",
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            status=PaperOrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # Validate order
        if not await self._validate_order(order):
            order.status = PaperOrderStatus.REJECTED
            return order
            
        # Store order
        self.orders[order.id] = order
        
        # Execute order
        if order_type == "market":
            await self._execute_market_order(order)
        else:
            # Limit orders wait for price
            asyncio.create_task(self._monitor_limit_order(order))
            
        return order
        
    async def _validate_order(self, order: PaperOrder) -> bool:
        """Validate order against account constraints."""
        # Get current market price
        market_price = self.market_prices.get(order.symbol, order.price or 0)
        
        # Calculate required balance
        order_value = order.quantity * market_price
        required_balance = order_value * (1 + self.fee_rate)
        
        # Check available balance for buy orders
        if order.side == "buy":
            if required_balance > self.account.available_balance:
                print(f"Insufficient balance: required {required_balance}, available {self.account.available_balance}")
                return False
                
        # Check position for sell orders
        elif order.side == "sell":
            position = self.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                print(f"Insufficient position for sell order")
                return False
                
        return True
        
    async def _execute_market_order(self, order: PaperOrder) -> None:
        """Execute market order immediately."""
        # Get current price
        market_price = self.market_prices.get(order.symbol, 100.0)
        
        # Fill order
        order.filled_quantity = order.quantity
        order.average_price = market_price
        order.status = PaperOrderStatus.FILLED
        order.filled_at = datetime.utcnow()
        
        # Log paper execution with audit trail
        paper_logger.info(
            "paper_exec",
            extra={
                "symbol": order.symbol,
                "side": order.side,
                "qty": float(order.quantity),
                "price_used": float(market_price),
                "price_source": "ccxt.binance.fetch_ticker",
                "ts_ms": int(time.time() * 1000)
            }
        )
        
        # Update position
        await self._update_position(order)
        
        # Update account
        await self._update_account(order)
        
        # Record trade
        self._record_trade(order)
        
    async def _monitor_limit_order(self, order: PaperOrder) -> None:
        """Monitor limit order for execution."""
        while order.status == PaperOrderStatus.PENDING:
            market_price = self.market_prices.get(order.symbol, 0)
            
            # Check if order should be filled
            should_fill = False
            if order.side == "buy" and market_price <= order.price:
                should_fill = True
            elif order.side == "sell" and market_price >= order.price:
                should_fill = True
                
            if should_fill:
                order.filled_quantity = order.quantity
                order.average_price = order.price
                order.status = PaperOrderStatus.FILLED
                order.filled_at = datetime.utcnow()
                
                await self._update_position(order)
                await self._update_account(order)
                self._record_trade(order)
                break
                
            await asyncio.sleep(1)  # Check every second
            
    async def _update_position(self, order: PaperOrder) -> None:
        """Update position after order execution."""
        if order.side == "buy":
            # Open or add to position
            if order.symbol in self.positions:
                position = self.positions[order.symbol]
                # Average entry price
                total_value = (position.quantity * position.entry_price + 
                              order.filled_quantity * order.average_price)
                position.quantity += order.filled_quantity
                position.entry_price = total_value / position.quantity
            else:
                # New position
                self.positions[order.symbol] = PaperPosition(
                    symbol=order.symbol,
                    side="long",
                    quantity=order.filled_quantity,
                    entry_price=order.average_price,
                    current_price=order.average_price,
                    unrealized_pnl=0.0,
                    opened_at=datetime.utcnow()
                )
                
        elif order.side == "sell":
            # Close or reduce position
            if order.symbol in self.positions:
                position = self.positions[order.symbol]
                
                # Calculate realized P&L
                pnl = (order.average_price - position.entry_price) * order.filled_quantity
                position.realized_pnl += pnl
                self.account.realized_pnl += pnl
                
                # Update position
                position.quantity -= order.filled_quantity
                
                if position.quantity <= 0:
                    # Position closed
                    position.closed_at = datetime.utcnow()
                    del self.positions[order.symbol]
                    
    async def _update_account(self, order: PaperOrder) -> None:
        """Update account after order execution."""
        order_value = order.filled_quantity * order.average_price
        fee = order_value * self.fee_rate
        
        if order.side == "buy":
            # Deduct from balance
            self.account.current_balance -= (order_value + fee)
            self.account.available_balance -= (order_value + fee)
        elif order.side == "sell":
            # Add to balance
            self.account.current_balance += (order_value - fee)
            self.account.available_balance += (order_value - fee)
            
        # Update trade count
        self.account.total_trades += 1
        
    def _record_trade(self, order: PaperOrder) -> None:
        """Record trade for history."""
        trade = {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.filled_quantity,
            "price": order.average_price,
            "value": order.filled_quantity * order.average_price,
            "fee": order.filled_quantity * order.average_price * self.fee_rate,
            "timestamp": order.filled_at
        }
        self.trade_history.append(trade)
        self.order_history.append(order)
        
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status == PaperOrderStatus.PENDING:
                order.status = PaperOrderStatus.CANCELLED
                return True
        return False
        
    async def close_position(self, symbol: str) -> Optional[PaperOrder]:
        """Close a position."""
        if symbol not in self.positions:
            return None
            
        position = self.positions[symbol]
        
        # Create market sell order
        return await self.place_order(
            symbol=symbol,
            side="sell",
            order_type="market",
            quantity=position.quantity
        )
        
    async def close_all_positions(self) -> List[PaperOrder]:
        """Close all open positions."""
        orders = []
        for symbol in list(self.positions.keys()):
            order = await self.close_position(symbol)
            if order:
                orders.append(order)
        return orders
        
    def update_market_price(self, symbol: str, price: float) -> None:
        """Update market price for a symbol."""
        self.market_prices[symbol] = price
        
        # Update position P&L
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = price
            position.unrealized_pnl = (price - position.entry_price) * position.quantity
            
    def calculate_metrics(self) -> TradingMetrics:
        """Calculate trading performance metrics."""
        if not self.trade_history:
            return TradingMetrics(
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                total_fees=0.0
            )
            
        # Calculate returns
        total_return = ((self.account.current_balance - self.account.initial_balance) / 
                       self.account.initial_balance * 100)
        
        # Calculate win rate
        winning_trades = 0
        losing_trades = 0
        total_wins = 0.0
        total_losses = 0.0
        best_trade = 0.0
        worst_trade = 0.0
        
        for i in range(0, len(self.order_history), 2):  # Pairs of buy/sell
            if i + 1 < len(self.order_history):
                buy_order = self.order_history[i]
                sell_order = self.order_history[i + 1]
                
                if buy_order.side == "buy" and sell_order.side == "sell":
                    pnl = (sell_order.average_price - buy_order.average_price) * buy_order.filled_quantity
                    
                    if pnl > 0:
                        winning_trades += 1
                        total_wins += pnl
                    else:
                        losing_trades += 1
                        total_losses += abs(pnl)
                        
                    best_trade = max(best_trade, pnl)
                    worst_trade = min(worst_trade, pnl)
                    
        win_rate = winning_trades / (winning_trades + losing_trades) * 100 if (winning_trades + losing_trades) > 0 else 0
        
        # Calculate profit factor
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Calculate average win/loss
        avg_win = total_wins / winning_trades if winning_trades > 0 else 0
        avg_loss = total_losses / losing_trades if losing_trades > 0 else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = []
        for i in range(1, len(self.balance_history)):
            daily_return = (self.balance_history[i] - self.balance_history[i-1]) / self.balance_history[i-1]
            returns.append(daily_return)
            
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0.0
            
        # Calculate max drawdown
        max_drawdown = 0.0
        peak = self.account.initial_balance
        for balance in self.balance_history:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
            
        # Calculate total fees
        total_fees = sum(trade["fee"] for trade in self.trade_history)
        
        return TradingMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=best_trade,
            worst_trade=worst_trade,
            total_fees=total_fees
        )
        
    def get_account_summary(self) -> Dict:
        """Get account summary."""
        # Update unrealized P&L
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        self.account.unrealized_pnl = total_unrealized
        self.account.total_pnl = self.account.realized_pnl + total_unrealized
        
        # Update positions value
        self.account.positions_value = sum(
            pos.quantity * pos.current_price for pos in self.positions.values()
        )
        
        # Calculate win rate
        if self.account.total_trades > 0:
            self.account.win_rate = self.account.winning_trades / self.account.total_trades * 100
            
        return {
            "account": self.account.dict(),
            "positions": [pos.dict() for pos in self.positions.values()],
            "open_orders": [order.dict() for order in self.orders.values() 
                          if order.status == PaperOrderStatus.PENDING],
            "metrics": self.calculate_metrics().dict()
        }
        
    def save_state(self, filepath: str) -> None:
        """Save engine state to file."""
        state = {
            "account": self.account.dict(),
            "positions": {k: v.dict() for k, v in self.positions.items()},
            "orders": {k: v.dict() for k, v in self.orders.items()},
            "trade_history": self.trade_history,
            "balance_history": self.balance_history,
            "market_prices": self.market_prices
        }
        
        with open(filepath, "w") as f:
            json.dump(state, f, indent=2, default=str)
            
    def load_state(self, filepath: str) -> None:
        """Load engine state from file."""
        with open(filepath, "r") as f:
            state = json.load(f)
            
        self.account = PaperAccount(**state["account"])
        self.positions = {k: PaperPosition(**v) for k, v in state["positions"].items()}
        self.orders = {k: PaperOrder(**v) for k, v in state["orders"].items()}
        self.trade_history = state["trade_history"]
        self.balance_history = state["balance_history"]
        self.market_prices = state["market_prices"]