"""
Paper trading Order Management System (OMS)
Includes fees, slippage simulation, risk caps, PnL tracking, and AI signal execution
"""

import asyncio
import logging
import os
import time
import json
import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional, Any, List, Tuple
from enum import Enum
from datetime import datetime, timedelta
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
ORDERS_PLACED = Counter('paper_orders_placed_total', 'Orders placed', ['symbol', 'side', 'order_type'])
ORDERS_FILLED = Counter('paper_orders_filled_total', 'Orders filled', ['symbol', 'side'])
ORDERS_REJECTED = Counter('paper_orders_rejected_total', 'Orders rejected', ['symbol', 'reason'])
TRADE_PNL = Histogram('paper_trade_pnl_usdt', 'Trade PnL in USDT', ['symbol', 'side'])
PORTFOLIO_VALUE = Gauge('paper_portfolio_value_usdt', 'Portfolio value in USDT')
PORTFOLIO_PNL = Gauge('paper_portfolio_pnl_usdt', 'Portfolio PnL in USDT')
ACTIVE_POSITIONS = Gauge('paper_active_positions', 'Number of active positions')
ORDER_LATENCY = Histogram('paper_order_latency_seconds', 'Order processing latency')


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Order:
    """Order structure"""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    fees_paid: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    filled_at: Optional[float] = None
    client_order_id: Optional[str] = None
    
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity
    
    def is_complete(self) -> bool:
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Position:
    """Position structure"""
    symbol: str
    side: PositionSide
    quantity: float
    average_entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def update_pnl(self, current_price: float):
        """Update unrealized PnL based on current price"""
        self.current_price = current_price
        self.updated_at = time.time()
        
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.average_entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.average_entry_price - current_price) * self.quantity
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Trade:
    """Executed trade structure"""
    id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fees: float
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskManager:
    """Risk management for paper trading"""
    
    def __init__(self):
        # Risk parameters from environment
        self.max_position_size_pct = float(os.getenv('PAPER_MAX_POSITION_SIZE_PCT', '10.0'))  # 10% max
        self.max_total_exposure_pct = float(os.getenv('PAPER_MAX_TOTAL_EXPOSURE_PCT', '80.0'))  # 80% max
        self.max_daily_loss_pct = float(os.getenv('PAPER_MAX_DAILY_LOSS_PCT', '5.0'))  # 5% max daily loss
        self.max_orders_per_symbol = int(os.getenv('PAPER_MAX_ORDERS_PER_SYMBOL', '5'))
        self.min_order_value = float(os.getenv('PAPER_MIN_ORDER_VALUE', '10.0'))  # $10 minimum
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_reset_time = 0.0
        
    def check_order_risk(self, order: Order, portfolio_value: float, positions: Dict[str, Position], 
                        active_orders: Dict[str, Order]) -> Tuple[bool, str]:
        """Check if order passes risk management"""
        
        # Reset daily PnL at start of new day
        current_time = time.time()
        if current_time - self.daily_reset_time > 86400:  # 24 hours
            self.daily_pnl = 0.0
            self.daily_reset_time = current_time
        
        # Check minimum order value
        if order.order_type == OrderType.MARKET:
            estimated_value = order.quantity * (order.price or 0)
        else:
            estimated_value = order.quantity * (order.price or 0)
        
        if estimated_value < self.min_order_value:
            return False, f"Order value ${estimated_value:.2f} below minimum ${self.min_order_value}"
        
        # Check maximum position size
        position_value = estimated_value
        max_position_value = portfolio_value * (self.max_position_size_pct / 100)
        
        if position_value > max_position_value:
            return False, f"Position size ${position_value:.2f} exceeds maximum ${max_position_value:.2f}"
        
        # Check total exposure
        current_exposure = sum(abs(pos.quantity * pos.current_price) for pos in positions.values())
        new_exposure = current_exposure + position_value
        max_exposure = portfolio_value * (self.max_total_exposure_pct / 100)
        
        if new_exposure > max_exposure:
            return False, f"Total exposure ${new_exposure:.2f} would exceed maximum ${max_exposure:.2f}"
        
        # Check daily loss limit
        if self.daily_pnl < 0:
            max_daily_loss = portfolio_value * (self.max_daily_loss_pct / 100)
            if abs(self.daily_pnl) > max_daily_loss:
                return False, f"Daily loss limit exceeded: ${abs(self.daily_pnl):.2f} > ${max_daily_loss:.2f}"
        
        # Check maximum orders per symbol
        symbol_orders = sum(1 for o in active_orders.values() if o.symbol == order.symbol and not o.is_complete())
        if symbol_orders >= self.max_orders_per_symbol:
            return False, f"Maximum orders per symbol exceeded: {symbol_orders} >= {self.max_orders_per_symbol}"
        
        return True, "OK"
    
    def update_daily_pnl(self, pnl_change: float):
        """Update daily PnL tracking"""
        self.daily_pnl += pnl_change


class FeeCalculator:
    """Calculate trading fees"""
    
    def __init__(self):
        # Fee structure from environment
        self.maker_fee_bps = float(os.getenv('PAPER_MAKER_FEE_BPS', '10'))  # 0.1% (10 bps)
        self.taker_fee_bps = float(os.getenv('PAPER_TAKER_FEE_BPS', '20'))  # 0.2% (20 bps)
        
    def calculate_fee(self, quantity: float, price: float, is_maker: bool = False) -> float:
        """Calculate trading fee"""
        notional_value = quantity * price
        fee_rate = self.maker_fee_bps if is_maker else self.taker_fee_bps
        return notional_value * (fee_rate / 10000)


class SlippageSimulator:
    """Simulate market slippage"""
    
    def __init__(self):
        # Slippage parameters from environment
        self.base_slippage_bps = float(os.getenv('PAPER_BASE_SLIPPAGE_BPS', '5'))  # 0.05% base slippage
        self.max_slippage_bps = float(os.getenv('PAPER_MAX_SLIPPAGE_BPS', '50'))  # 0.5% max slippage
        self.slippage_impact_factor = float(os.getenv('PAPER_SLIPPAGE_IMPACT_FACTOR', '0.1'))
        
    def calculate_slippage_price(self, order: Order, market_price: float, order_book_depth: float = 100000) -> float:
        """Calculate execution price with slippage"""
        if order.order_type == OrderType.LIMIT:
            # Limit orders don't have slippage (assuming they get filled at limit price)
            return order.price or market_price
        
        # Calculate slippage based on order size relative to order book depth
        order_impact = (order.quantity * market_price) / order_book_depth
        impact_slippage = min(order_impact * self.slippage_impact_factor * 10000, self.max_slippage_bps)
        
        total_slippage_bps = self.base_slippage_bps + impact_slippage
        slippage_factor = total_slippage_bps / 10000
        
        if order.side == OrderSide.BUY:
            # Buy orders slip upward (pay more)
            return market_price * (1 + slippage_factor)
        else:
            # Sell orders slip downward (receive less)
            return market_price * (1 - slippage_factor)


class PaperTradingEngine:
    """Main paper trading engine"""
    
    def __init__(self, initial_balance: float = 100000):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions = {}  # {symbol: Position}
        self.orders = {}  # {order_id: Order}
        self.trades = {}  # {trade_id: Trade}
        
        # Components
        self.risk_manager = RiskManager()
        self.fee_calculator = FeeCalculator()
        self.slippage_simulator = SlippageSimulator()
        
        # Market data cache
        self.market_prices = {}  # {symbol: price}
        self.last_price_update = {}  # {symbol: timestamp}
        
        # Redis client
        self.redis_client = None
        
        # Metrics
        self.total_trades = 0
        self.total_fees_paid = 0.0
        self.total_pnl = 0.0
        
    async def start(self):
        """Initialize paper trading engine"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        logger.info(f"Paper trading engine started with ${self.initial_balance:,.2f} initial balance")
    
    def get_portfolio_value(self) -> float:
        """Calculate current portfolio value"""
        total_value = self.current_balance
        
        for position in self.positions.values():
            position_value = position.quantity * position.current_price
            total_value += position_value + position.get_total_pnl()
        
        return total_value
    
    def place_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                   quantity: float, price: Optional[float] = None, 
                   stop_price: Optional[float] = None,
                   client_order_id: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """Place a new order"""
        
        start_time = time.time()
        
        try:
            # Create order
            order = Order(
                id=str(uuid.uuid4()),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                client_order_id=client_order_id
            )
            
            # Risk management check
            portfolio_value = self.get_portfolio_value()
            risk_ok, risk_reason = self.risk_manager.check_order_risk(
                order, portfolio_value, self.positions, self.orders
            )
            
            if not risk_ok:
                order.status = OrderStatus.REJECTED
                self.orders[order.id] = order
                ORDERS_REJECTED.labels(symbol=symbol, reason=risk_reason).inc()
                return False, risk_reason, order.id
            
            # Check sufficient balance for buy orders
            if side == OrderSide.BUY:
                required_balance = quantity * (price or self.market_prices.get(symbol, 0))
                if required_balance > self.current_balance:
                    order.status = OrderStatus.REJECTED
                    self.orders[order.id] = order
                    ORDERS_REJECTED.labels(symbol=symbol, reason='insufficient_balance').inc()
                    return False, f"Insufficient balance: need ${required_balance:.2f}, have ${self.current_balance:.2f}", order.id
            
            # Check position for sell orders
            if side == OrderSide.SELL:
                if symbol not in self.positions:
                    order.status = OrderStatus.REJECTED
                    self.orders[order.id] = order
                    ORDERS_REJECTED.labels(symbol=symbol, reason='no_position').inc()
                    return False, f"No position to sell for {symbol}", order.id
                
                available_quantity = self.positions[symbol].quantity
                if quantity > available_quantity:
                    order.status = OrderStatus.REJECTED
                    self.orders[order.id] = order
                    ORDERS_REJECTED.labels(symbol=symbol, reason='insufficient_quantity').inc()
                    return False, f"Insufficient quantity: need {quantity}, have {available_quantity}", order.id
            
            # Set order status to open
            order.status = OrderStatus.OPEN
            self.orders[order.id] = order
            
            # Try to fill immediately if market order or conditions are met
            if order_type == OrderType.MARKET:
                self._try_fill_order(order.id)
            elif order_type == OrderType.LIMIT and symbol in self.market_prices:
                self._check_limit_order_fill(order.id)
            
            # Record metrics
            ORDERS_PLACED.labels(symbol=symbol, side=side.value, order_type=order_type.value).inc()
            ORDER_LATENCY.labels().observe(time.time() - start_time)
            
            logger.info(f"Order placed: {order.id} - {side.value} {quantity} {symbol} at {price or 'market'}")
            return True, "Order placed successfully", order.id
            
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return False, str(e), None
    
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """Cancel an existing order"""
        if order_id not in self.orders:
            return False, "Order not found"
        
        order = self.orders[order_id]
        
        if order.is_complete():
            return False, f"Order already {order.status.value}"
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = time.time()
        
        logger.info(f"Order cancelled: {order_id}")
        return True, "Order cancelled successfully"
    
    def _try_fill_order(self, order_id: str):
        """Try to fill a market order immediately"""
        order = self.orders[order_id]
        
        if order.symbol not in self.market_prices:
            logger.warning(f"No market price available for {order.symbol}")
            return
        
        market_price = self.market_prices[order.symbol]
        
        # Calculate execution price with slippage
        execution_price = self.slippage_simulator.calculate_slippage_price(order, market_price)
        
        # Calculate fees
        fees = self.fee_calculator.calculate_fee(order.quantity, execution_price, is_maker=False)
        
        # Execute the trade
        self._execute_trade(order, order.quantity, execution_price, fees)
    
    def _check_limit_order_fill(self, order_id: str):
        """Check if a limit order should be filled based on current market price"""
        order = self.orders[order_id]
        
        if order.symbol not in self.market_prices or not order.price:
            return
        
        market_price = self.market_prices[order.symbol]
        should_fill = False
        
        if order.side == OrderSide.BUY and market_price <= order.price:
            should_fill = True
        elif order.side == OrderSide.SELL and market_price >= order.price:
            should_fill = True
        
        if should_fill:
            # Calculate fees (maker fee since it's a limit order that got filled)
            fees = self.fee_calculator.calculate_fee(order.quantity, order.price, is_maker=True)
            
            # Execute the trade at limit price
            self._execute_trade(order, order.quantity, order.price, fees)
    
    def _execute_trade(self, order: Order, quantity: float, price: float, fees: float):
        """Execute a trade"""
        trade_id = str(uuid.uuid4())
        
        # Create trade record
        trade = Trade(
            id=trade_id,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            fees=fees
        )
        
        self.trades[trade_id] = trade
        
        # Update order
        order.filled_quantity += quantity
        order.filled_price = price  # Simple average (could be more sophisticated)
        order.fees_paid += fees
        order.updated_at = time.time()
        
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = time.time()
        else:
            order.status = OrderStatus.PARTIALLY_FILLED
        
        # Update balances and positions
        if order.side == OrderSide.BUY:
            # Deduct cost from balance
            total_cost = quantity * price + fees
            self.current_balance -= total_cost
            
            # Update or create position
            if order.symbol in self.positions:
                position = self.positions[order.symbol]
                # Calculate new average entry price
                total_quantity = position.quantity + quantity
                total_cost_basis = (position.quantity * position.average_entry_price) + (quantity * price)
                position.average_entry_price = total_cost_basis / total_quantity
                position.quantity = total_quantity
                position.fees_paid += fees
                position.updated_at = time.time()
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side=PositionSide.LONG,
                    quantity=quantity,
                    average_entry_price=price,
                    fees_paid=fees
                )
                
        else:  # SELL
            # Add proceeds to balance
            proceeds = quantity * price - fees
            self.current_balance += proceeds
            
            # Update position
            if order.symbol in self.positions:
                position = self.positions[order.symbol]
                
                # Calculate realized PnL
                realized_pnl = (price - position.average_entry_price) * quantity - fees
                position.realized_pnl += realized_pnl
                position.quantity -= quantity
                position.fees_paid += fees
                position.updated_at = time.time()
                
                # Remove position if quantity is zero
                if position.quantity <= 0:
                    final_pnl = position.get_total_pnl()
                    self.total_pnl += final_pnl
                    self.risk_manager.update_daily_pnl(final_pnl)
                    del self.positions[order.symbol]
        
        # Update metrics
        self.total_trades += 1
        self.total_fees_paid += fees
        
        ORDERS_FILLED.labels(symbol=order.symbol, side=order.side.value).inc()
        
        # Calculate trade PnL for metrics
        if order.side == OrderSide.SELL and order.symbol in self.positions:
            trade_pnl = (price - self.positions[order.symbol].average_entry_price) * quantity - fees
            TRADE_PNL.labels(symbol=order.symbol, side=order.side.value).observe(trade_pnl)
        
        logger.info(f"Trade executed: {trade_id} - {order.side.value} {quantity} {order.symbol} at ${price:.4f}, fees: ${fees:.4f}")
    
    def update_market_price(self, symbol: str, price: float):
        """Update market price for a symbol"""
        self.market_prices[symbol] = price
        self.last_price_update[symbol] = time.time()
        
        # Update position PnL
        if symbol in self.positions:
            self.positions[symbol].update_pnl(price)
        
        # Check limit orders for fills
        for order_id, order in self.orders.items():
            if (order.symbol == symbol and order.status == OrderStatus.OPEN and 
                order.order_type == OrderType.LIMIT):
                self._check_limit_order_fill(order_id)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary"""
        portfolio_value = self.get_portfolio_value()
        total_pnl = portfolio_value - self.initial_balance
        
        # Update Prometheus metrics
        PORTFOLIO_VALUE.set(portfolio_value)
        PORTFOLIO_PNL.set(total_pnl)
        ACTIVE_POSITIONS.set(len(self.positions))
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'portfolio_value': portfolio_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': (total_pnl / self.initial_balance) * 100,
            'total_trades': self.total_trades,
            'total_fees_paid': self.total_fees_paid,
            'active_positions': len(self.positions),
            'active_orders': len([o for o in self.orders.values() if not o.is_complete()]),
            'positions': {symbol: pos.to_dict() for symbol, pos in self.positions.items()},
            'recent_trades': [trade.to_dict() for trade in list(self.trades.values())[-10:]],
            'risk_metrics': {
                'daily_pnl': self.risk_manager.daily_pnl,
                'max_position_size_pct': self.risk_manager.max_position_size_pct,
                'current_exposure_pct': sum(
                    abs(pos.quantity * pos.current_price) for pos in self.positions.values()
                ) / portfolio_value * 100 if portfolio_value > 0 else 0
            }
        }
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status"""
        if order_id not in self.orders:
            return None
        
        return self.orders[order_id].to_dict()
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for symbol"""
        if symbol not in self.positions:
            return None
        
        return self.positions[symbol].to_dict()


class AISignalExecutor:
    """Execute trades based on AI model signals"""
    
    def __init__(self, trading_engine: PaperTradingEngine):
        self.trading_engine = trading_engine
        self.redis_client = None
        self.running = False
        
        # Configuration
        self.min_signal_confidence = float(os.getenv('AI_MIN_SIGNAL_CONFIDENCE', '0.6'))
        self.position_size_pct = float(os.getenv('AI_POSITION_SIZE_PCT', '2.0'))  # 2% of portfolio per signal
        self.consumer_group = os.getenv('AI_SIGNAL_CONSUMER_GROUP', 'signal_executors')
        self.consumer_name = os.getenv('AI_SIGNAL_CONSUMER_NAME', f'executor_{os.getpid()}')
    
    async def start(self):
        """Start AI signal execution"""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(redis_url)
        
        self.running = True
        logger.info("Starting AI signal executor")
        
        # Start signal consumer
        await self.consume_ai_signals()
    
    async def consume_ai_signals(self):
        """Consume AI signals from Redis streams"""
        while self.running:
            try:
                # Discover prediction streams
                prediction_streams = {}
                async for key in self.redis_client.scan_iter(match="predictions.*"):
                    key_str = key.decode()
                    prediction_streams[key_str] = '>'
                
                if not prediction_streams:
                    await asyncio.sleep(5)
                    continue
                
                # Create consumer groups
                for stream_key in prediction_streams.keys():
                    try:
                        await self.redis_client.xgroup_create(
                            stream_key, self.consumer_group, '$', mkstream=True
                        )
                    except redis.RedisError:
                        pass
                
                # Read from streams
                stream_list = [(k, '>') for k in prediction_streams.keys()]
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams=dict(stream_list),
                    count=10,
                    block=1000
                )
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            await self.process_ai_signal(stream_str, fields)
                            
                            # Acknowledge message
                            await self.redis_client.xack(stream, self.consumer_group, msg_id)
                            
                        except Exception as e:
                            logger.error(f"AI signal processing error: {e}")
                
            except Exception as e:
                logger.error(f"AI signal consumer error: {e}")
                await asyncio.sleep(5)
    
    async def process_ai_signal(self, stream: str, fields: Dict[bytes, bytes]):
        """Process AI prediction signal"""
        try:
            # Parse signal data
            data = {k.decode(): v.decode() for k, v in fields.items()}
            
            symbol = data.get('symbol', '').upper()
            confidence = float(data.get('confidence', 0))
            calibrated_score = float(data.get('calibrated_score', 0.5))
            prediction_class = int(data.get('prediction_class', 0))
            
            # Check signal quality
            if confidence < self.min_signal_confidence:
                logger.debug(f"Signal confidence too low for {symbol}: {confidence}")
                return
            
            # Determine trade direction
            if prediction_class == 1 and calibrated_score > 0.6:
                # Strong buy signal
                await self.execute_signal_trade(symbol, OrderSide.BUY, confidence)
            elif prediction_class == 0 and calibrated_score < 0.4:
                # Strong sell signal
                await self.execute_signal_trade(symbol, OrderSide.SELL, confidence)
            
        except Exception as e:
            logger.error(f"AI signal processing error: {e}")
    
    async def execute_signal_trade(self, symbol: str, side: OrderSide, confidence: float):
        """Execute trade based on AI signal"""
        try:
            portfolio_value = self.trading_engine.get_portfolio_value()
            
            # Calculate position size based on confidence and risk parameters
            base_position_size = portfolio_value * (self.position_size_pct / 100)
            confidence_multiplier = min(confidence * 1.5, 1.0)  # Scale with confidence
            position_value = base_position_size * confidence_multiplier
            
            # Get current market price
            if symbol not in self.trading_engine.market_prices:
                logger.warning(f"No market price available for {symbol}")
                return
            
            current_price = self.trading_engine.market_prices[symbol]
            quantity = position_value / current_price
            
            # Place market order
            success, message, order_id = self.trading_engine.place_order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                client_order_id=f"AI_SIGNAL_{int(time.time())}"
            )
            
            if success:
                logger.info(f"AI signal trade executed: {side.value} {quantity:.6f} {symbol} (confidence: {confidence:.3f})")
            else:
                logger.warning(f"AI signal trade failed: {message}")
                
        except Exception as e:
            logger.error(f"Signal trade execution error: {e}")
    
    async def stop(self):
        """Stop AI signal executor"""
        self.running = False
        
        if self.redis_client:
            await self.redis_client.close()


class PaperTradingManager:
    """Main paper trading manager"""
    
    def __init__(self, initial_balance: float = None):
        initial_balance = initial_balance or float(os.getenv('PAPER_INITIAL_BALANCE', '100000'))
        self.trading_engine = PaperTradingEngine(initial_balance)
        self.signal_executor = AISignalExecutor(self.trading_engine)
        self.running = False
        
        # Market data tracking
        self.symbols = self._get_symbols()
        
    def _get_symbols(self) -> List[str]:
        """Get trading symbols from environment"""
        symbols_env = os.getenv('PAPER_TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT')
        return [s.strip() for s in symbols_env.split(',')]
    
    async def start(self):
        """Start paper trading manager"""
        await self.trading_engine.start()
        
        self.running = True
        logger.info("Starting paper trading manager")
        
        # Start market data consumer and signal executor
        tasks = [
            asyncio.create_task(self.market_data_consumer()),
            asyncio.create_task(self.signal_executor.start()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def market_data_consumer(self):
        """Consume market data to update prices"""
        redis_client = await redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
        
        logger.info("Starting market data consumer for paper trading")
        
        while self.running:
            try:
                # Discover price streams
                price_streams = {}
                async for key in redis_client.scan_iter(match="ticks.*"):
                    key_str = key.decode()
                    # Check if stream is for one of our trading symbols
                    if any(symbol.lower() in key_str.lower() for symbol in self.symbols):
                        price_streams[key_str] = '>'
                
                if not price_streams:
                    await asyncio.sleep(5)
                    continue
                
                # Read from streams
                stream_list = [(k, '$') for k in price_streams.keys()]  # Use '$' to get latest
                messages = await redis_client.xread(streams=dict(stream_list), count=1, block=1000)
                
                for stream, msgs in messages:
                    stream_str = stream.decode()
                    
                    for msg_id, fields in msgs:
                        try:
                            # Parse price data
                            data = {k.decode(): v.decode() for k, v in fields.items()}
                            
                            symbol = data.get('symbol', '').upper()
                            price = float(data.get('price', 0))
                            
                            if symbol in self.symbols and price > 0:
                                self.trading_engine.update_market_price(symbol, price)
                                
                        except Exception as e:
                            logger.error(f"Price update error: {e}")
                
            except Exception as e:
                logger.error(f"Market data consumer error: {e}")
                await asyncio.sleep(5)
        
        await redis_client.close()
    
    async def stop(self):
        """Stop paper trading manager"""
        self.running = False
        await self.signal_executor.stop()
        logger.info("Stopped paper trading manager")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get paper trading health status"""
        portfolio = self.trading_engine.get_portfolio_summary()
        
        return {
            'running': self.running,
            'trading_engine': {
                'initial_balance': self.trading_engine.initial_balance,
                'current_balance': self.trading_engine.current_balance,
                'portfolio_value': portfolio['portfolio_value'],
                'total_pnl': portfolio['total_pnl'],
                'total_trades': self.trading_engine.total_trades,
                'active_positions': len(self.trading_engine.positions),
                'active_orders': len([o for o in self.trading_engine.orders.values() if not o.is_complete()])
            },
            'signal_executor': {
                'running': self.signal_executor.running,
                'min_confidence': self.signal_executor.min_signal_confidence
            },
            'market_data': {
                'tracked_symbols': self.symbols,
                'price_updates': len(self.trading_engine.market_prices)
            }
        }


async def main():
    """Main entry point"""
    logger.info("Starting Paper Trading System")
    
    manager = PaperTradingManager()
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())