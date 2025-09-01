"""
Paper Trading Engine with REAL Crypto Prices
Simulates trading with real market data - no actual money at risk!
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import uuid

from ..data.real_time_fetcher import fetcher

logger = logging.getLogger(__name__)

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    current_price: float = 0.0
    
    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized P&L based on current price"""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.avg_price) * self.quantity

@dataclass 
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    fee: float = 0.0
    
    def to_dict(self):
        return {
            **asdict(self),
            'side': self.side.value,
            'order_type': self.order_type.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None
        }

@dataclass
class Portfolio:
    user_id: str
    balance: float = 10000.0  # Start with $10k virtual money
    positions: Dict[str, Position] = None
    orders: List[Order] = None
    total_value: float = 10000.0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = {}
        if self.orders is None:
            self.orders = []
    
    def update_portfolio_value(self, market_prices: Dict[str, float]):
        """Update total portfolio value based on current market prices"""
        position_value = 0.0
        total_unrealized_pnl = 0.0
        
        for symbol, position in self.positions.items():
            current_price = market_prices.get(symbol, position.avg_price)
            position.update_unrealized_pnl(current_price)
            position_value += position.quantity * current_price
            total_unrealized_pnl += position.unrealized_pnl
        
        self.total_value = self.balance + position_value
        self.total_pnl = sum(pos.realized_pnl for pos in self.positions.values()) + total_unrealized_pnl
        
        return self.total_value

class PaperTradingEngine:
    """Advanced Paper Trading Engine with real crypto prices"""
    
    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
        self.market_prices: Dict[str, float] = {}
        self.order_book: Dict[str, List[Order]] = {}
        self.trade_history: List[Dict] = []
        self.is_running = False
        
        # Trading fees (like real exchanges)
        self.maker_fee = 0.001  # 0.1%
        self.taker_fee = 0.0015  # 0.15%
        
    async def start(self):
        """Start the paper trading engine"""
        if self.is_running:
            return
            
        self.is_running = True
        await fetcher.start()
        
        # Start price monitoring
        asyncio.create_task(self._monitor_prices())
        asyncio.create_task(self._process_orders())
        
        logger.info("Paper Trading Engine started")
        
    async def stop(self):
        """Stop the paper trading engine"""
        self.is_running = False
        await fetcher.stop()
        logger.info("Paper Trading Engine stopped")
        
    def create_portfolio(self, user_id: str, initial_balance: float = 10000.0) -> Portfolio:
        """Create a new paper trading portfolio"""
        portfolio = Portfolio(user_id=user_id, balance=initial_balance)
        self.portfolios[user_id] = portfolio
        logger.info(f"Created portfolio for user {user_id} with ${initial_balance}")
        return portfolio
        
    def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        """Get user's portfolio"""
        return self.portfolios.get(user_id)
        
    async def place_order(
        self,
        user_id: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None
    ) -> Order:
        """Place a paper trading order"""
        
        # Get or create portfolio
        if user_id not in self.portfolios:
            self.create_portfolio(user_id)
        
        portfolio = self.portfolios[user_id]
        
        # Create order
        order = Order(
            id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        # Validate order
        if not await self._validate_order(portfolio, order):
            order.status = OrderStatus.REJECTED
            return order
            
        # Add to order book
        if symbol not in self.order_book:
            self.order_book[symbol] = []
        self.order_book[symbol].append(order)
        
        portfolio.orders.append(order)
        
        # For market orders, try to fill immediately
        if order_type == OrderType.MARKET:
            await self._try_fill_order(order, portfolio)
            
        logger.info(f"Order placed: {order.symbol} {order.side.value} {order.quantity} @ {order.price or 'market'}")
        return order
        
    async def cancel_order(self, user_id: str, order_id: str) -> bool:
        """Cancel a pending order"""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return False
            
        for order in portfolio.orders:
            if order.id == order_id and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                
                # Remove from order book
                for symbol_orders in self.order_book.values():
                    if order in symbol_orders:
                        symbol_orders.remove(order)
                        break
                        
                logger.info(f"Order cancelled: {order_id}")
                return True
                
        return False
        
    async def get_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        if symbol in self.market_prices:
            return self.market_prices[symbol]
            
        # Fetch from API if not in cache
        price = await fetcher.get_price(symbol.lower())
        if price:
            self.market_prices[symbol] = price
            return price
            
        return None
        
    async def _monitor_prices(self):
        """Monitor real-time prices and update portfolios"""
        symbols = ["bitcoin", "ethereum", "solana", "binancecoin", "cardano", "polkadot", "chainlink", "litecoin"]
        
        while self.is_running:
            try:
                # Get market data
                market_data = await fetcher.get_market_data(symbols)
                
                if market_data:
                    # Update price cache
                    for symbol, data in market_data.items():
                        self.market_prices[symbol] = data["price"]
                    
                    # Update all portfolios
                    for portfolio in self.portfolios.values():
                        portfolio.update_portfolio_value(self.market_prices)
                        
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring prices: {e}")
                await asyncio.sleep(10)
                
    async def _process_orders(self):
        """Process pending orders"""
        while self.is_running:
            try:
                for symbol, orders in self.order_book.items():
                    current_price = await self.get_market_price(symbol)
                    if not current_price:
                        continue
                        
                    for order in orders.copy():
                        if order.status != OrderStatus.PENDING:
                            continue
                            
                        portfolio = self.get_portfolio(order.id.split('-')[0])  # Assuming user_id is part of order id
                        if not portfolio:
                            continue
                            
                        # Check if order should be filled
                        should_fill = False
                        
                        if order.order_type == OrderType.LIMIT:
                            if order.side == OrderSide.BUY and current_price <= order.price:
                                should_fill = True
                            elif order.side == OrderSide.SELL and current_price >= order.price:
                                should_fill = True
                                
                        elif order.order_type == OrderType.STOP_LOSS:
                            if order.side == OrderSide.SELL and current_price <= order.price:
                                should_fill = True
                                
                        elif order.order_type == OrderType.TAKE_PROFIT:
                            if order.side == OrderSide.SELL and current_price >= order.price:
                                should_fill = True
                        
                        if should_fill:
                            await self._try_fill_order(order, portfolio, current_price)
                            
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error processing orders: {e}")
                await asyncio.sleep(5)
                
    async def _validate_order(self, portfolio: Portfolio, order: Order) -> bool:
        """Validate if order can be placed"""
        current_price = await self.get_market_price(order.symbol)
        if not current_price:
            logger.error(f"Could not get price for {order.symbol}")
            return False
            
        if order.side == OrderSide.BUY:
            # Check if user has enough balance
            cost = order.quantity * (order.price or current_price)
            fee = cost * self.taker_fee
            total_cost = cost + fee
            
            if portfolio.balance < total_cost:
                logger.error(f"Insufficient balance. Need ${total_cost:.2f}, have ${portfolio.balance:.2f}")
                return False
                
        elif order.side == OrderSide.SELL:
            # Check if user has enough of the asset
            position = portfolio.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                available = position.quantity if position else 0
                logger.error(f"Insufficient {order.symbol}. Need {order.quantity}, have {available}")
                return False
                
        return True
        
    async def _try_fill_order(self, order: Order, portfolio: Portfolio, fill_price: Optional[float] = None):
        """Try to fill an order"""
        if fill_price is None:
            fill_price = await self.get_market_price(order.symbol)
            
        if not fill_price:
            return
            
        # Calculate fee
        trade_value = order.quantity * fill_price
        fee = trade_value * self.taker_fee
        
        if order.side == OrderSide.BUY:
            # Deduct balance
            total_cost = trade_value + fee
            portfolio.balance -= total_cost
            
            # Add or update position
            if order.symbol in portfolio.positions:
                pos = portfolio.positions[order.symbol]
                total_quantity = pos.quantity + order.quantity
                pos.avg_price = ((pos.avg_price * pos.quantity) + (fill_price * order.quantity)) / total_quantity
                pos.quantity = total_quantity
            else:
                portfolio.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_price=fill_price,
                    entry_time=datetime.now(timezone.utc)
                )
                
        elif order.side == OrderSide.SELL:
            # Add balance (minus fee)
            portfolio.balance += trade_value - fee
            
            # Update position
            if order.symbol in portfolio.positions:
                pos = portfolio.positions[order.symbol]
                pos.quantity -= order.quantity
                
                # Calculate realized P&L
                realized_pnl = (fill_price - pos.avg_price) * order.quantity - fee
                pos.realized_pnl += realized_pnl
                
                # Remove position if fully sold
                if pos.quantity <= 0:
                    del portfolio.positions[order.symbol]
                    
        # Update order
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(timezone.utc)
        order.filled_price = fill_price
        order.filled_quantity = order.quantity
        order.fee = fee
        
        # Update trade statistics
        portfolio.total_trades += 1
        if order.side == OrderSide.SELL:
            # Check if it was a winning trade
            if order.symbol in portfolio.positions:
                pos = portfolio.positions[order.symbol]
                if fill_price > pos.avg_price:
                    portfolio.winning_trades += 1
        
        portfolio.win_rate = portfolio.winning_trades / portfolio.total_trades if portfolio.total_trades > 0 else 0
        
        # Add to trade history
        trade = {
            "id": str(uuid.uuid4()),
            "user_id": portfolio.user_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "price": fill_price,
            "fee": fee,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pnl": realized_pnl if order.side == OrderSide.SELL else 0.0
        }
        self.trade_history.append(trade)
        
        # Remove from order book
        if order.symbol in self.order_book:
            if order in self.order_book[order.symbol]:
                self.order_book[order.symbol].remove(order)
                
        logger.info(f"Order filled: {order.symbol} {order.side.value} {order.quantity} @ ${fill_price:.2f}")
        
    def get_trade_history(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get user's trade history"""
        user_trades = [trade for trade in self.trade_history if trade["user_id"] == user_id]
        return sorted(user_trades, key=lambda x: x["timestamp"], reverse=True)[:limit]
        
    def get_portfolio_summary(self, user_id: str) -> Optional[Dict]:
        """Get portfolio summary"""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return None
            
        # Update portfolio value with current prices
        portfolio.update_portfolio_value(self.market_prices)
        
        return {
            "user_id": user_id,
            "balance": portfolio.balance,
            "total_value": portfolio.total_value,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_percent": (portfolio.total_pnl / 10000.0) * 100,  # Assuming $10k start
            "positions": [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                    "entry_time": pos.entry_time.isoformat()
                }
                for pos in portfolio.positions.values()
            ],
            "open_orders": [
                order.to_dict() for order in portfolio.orders 
                if order.status == OrderStatus.PENDING
            ],
            "total_trades": portfolio.total_trades,
            "winning_trades": portfolio.winning_trades,
            "win_rate": portfolio.win_rate,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

# Global paper trading engine instance
paper_engine = PaperTradingEngine()