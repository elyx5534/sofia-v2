"""
Paper Trading Engine for Sofia V2.
Simulates order execution with fees and slippage.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

import httpx  # Use HTTP client instead of driver
import orjson
import redis.asyncio as redis
from nats.aio.client import Client as NATS

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Position:
    """Represents a trading position"""

    symbol: str
    quantity: float
    avg_price: float
    side: OrderSide
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def value(self) -> float:
        return self.quantity * self.avg_price

    def update_pnl(self, current_price: float):
        """Update unrealized PnL based on current price"""
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (current_price - self.avg_price) * self.quantity
        else:
            self.unrealized_pnl = (self.avg_price - current_price) * self.quantity


@dataclass
class Order:
    """Represents a trading order"""

    order_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    price: float = 0.0
    quantity: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    strategy: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    filled_price: float = 0.0
    filled_quantity: float = 0.0
    fee: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0


class RiskManager:
    """Risk management for paper trading"""

    def __init__(self, config: Dict):
        self.max_position_usd = config.get("max_position_usd", 100)
        self.max_drawdown_pct = config.get("max_drawdown_pct", 15.0)
        self.risk_pair_pct = config.get("risk_pair_pct", 1.0)
        self.total_risk_pct = config.get("total_risk_pct", 10.0)
        self.leverage = config.get("leverage", 1.0)

    def check_order(
        self, order: Order, positions: Dict[str, Position], balance: float
    ) -> tuple[bool, str]:
        """Check if order passes risk checks"""
        # Check position size limit
        symbol_position = positions.get(order.symbol)
        current_value = symbol_position.value if symbol_position else 0
        order_value = order.quantity * order.price

        if current_value + order_value > self.max_position_usd:
            return (
                False,
                f"Position size limit exceeded: {current_value + order_value:.2f} > {self.max_position_usd}",
            )

        # Check balance
        if order_value > balance * (self.risk_pair_pct / 100):
            return (
                False,
                f"Order exceeds risk limit: {order_value:.2f} > {balance * self.risk_pair_pct / 100:.2f}",
            )

        # Check total exposure
        total_exposure = sum(p.value for p in positions.values()) + order_value
        if total_exposure > balance * (self.total_risk_pct / 100):
            return False, f"Total exposure limit exceeded: {total_exposure:.2f}"

        return True, "OK"


class PaperTradingEngine:
    """Paper trading engine with order simulation"""

    def __init__(self, config: Dict):
        self.config = config
        self.initial_balance = config.get("paper_balance_usd", 10000)
        self.balance = self.initial_balance
        self.fee_bps = config.get("fee_bps", 10)  # 0.1% = 10 bps
        self.slippage_bps = config.get("slippage_bps", 3)  # 0.03% = 3 bps

        # State management
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.pending_orders: Dict[str, Order] = {}
        self.current_prices: Dict[str, float] = {}

        # Risk manager
        self.risk_manager = RiskManager(config.get("risk", {}))

        # External connections
        self.nats: Optional[NATS] = None
        self.redis: Optional[redis.Redis] = None
        self.ch_url: str = "http://localhost:8123"
        self.ch_client = None  # Will use HTTP API

        # Statistics
        self.stats = {
            "total_orders": 0,
            "filled_orders": 0,
            "rejected_orders": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "start_time": time.time(),
        }

        self.running = False

    async def initialize(
        self, nats_client: NATS, redis_client: redis.Redis, ch_url: str = "http://localhost:8123"
    ):
        """Initialize connections"""
        self.nats = nats_client
        self.redis = redis_client
        self.ch_url = ch_url
        logger.info("Paper trading engine initialized")

    async def submit_order(self, order: Order) -> bool:
        """Submit an order for execution"""
        try:
            # Risk checks
            passed, reason = self.risk_manager.check_order(order, self.positions, self.balance)

            if not passed:
                logger.warning(f"Order rejected by risk manager: {reason}")
                order.status = OrderStatus.REJECTED
                self.stats["rejected_orders"] += 1
                return False

            # Add to pending orders
            self.pending_orders[order.order_id] = order
            self.stats["total_orders"] += 1

            # Store in Redis for tracking
            await self.redis.hset(
                "paper:orders",
                order.order_id,
                orjson.dumps(
                    {
                        "symbol": order.symbol,
                        "side": order.side,
                        "price": order.price,
                        "quantity": order.quantity,
                        "status": order.status,
                        "strategy": order.strategy,
                        "timestamp": order.timestamp.isoformat(),
                    }
                ),
            )

            logger.info(
                f"Order submitted: {order.order_id} {order.side} {order.quantity} {order.symbol} @ {order.price}"
            )
            return True

        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return False

    async def execute_order(self, order: Order, market_price: float):
        """Execute a pending order"""
        try:
            # Calculate slippage
            slippage_pct = self.slippage_bps / 10000
            if order.side == OrderSide.BUY:
                filled_price = market_price * (1 + slippage_pct)
            else:
                filled_price = market_price * (1 - slippage_pct)

            # Calculate fee
            order_value = order.quantity * filled_price
            fee = order_value * (self.fee_bps / 10000)

            # Update order
            order.filled_price = filled_price
            order.filled_quantity = order.quantity
            order.fee = fee
            order.slippage = abs(filled_price - market_price) * order.quantity
            order.status = OrderStatus.FILLED

            # Update position
            symbol = order.symbol
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0,
                    side=order.side,
                    entry_time=datetime.now(UTC),
                )

            position = self.positions[symbol]

            if order.side == OrderSide.BUY:
                # Update average price for buy
                total_value = position.quantity * position.avg_price + order_value
                position.quantity += order.quantity
                position.avg_price = (
                    total_value / position.quantity if position.quantity > 0 else filled_price
                )
                self.balance -= order_value + fee
            else:
                # Calculate PnL for sell
                if position.quantity > 0:
                    pnl = (filled_price - position.avg_price) * min(
                        order.quantity, position.quantity
                    )
                    order.pnl = pnl
                    position.realized_pnl += pnl
                    self.stats["total_pnl"] += pnl

                position.quantity -= order.quantity
                self.balance += order_value - fee

            # Remove from pending
            del self.pending_orders[order.order_id]
            self.orders.append(order)
            self.stats["filled_orders"] += 1

            # Store execution in ClickHouse via HTTP
            async with httpx.AsyncClient() as client:
                query = f"""
                INSERT INTO paper_orders
                (order_id, ts, symbol, side, price, quantity, status, strategy, pnl)
                VALUES
                ('{order.order_id}', '{order.timestamp.isoformat()}', '{order.symbol}',
                 '{order.side}', {order.filled_price}, {order.filled_quantity},
                 '{order.status}', '{order.strategy}', {order.pnl})
                """
                try:
                    await client.post(self.ch_url, params={"query": query})
                except:
                    pass  # Log but don't fail on storage errors

            logger.info(
                f"Order executed: {order.order_id} filled @ {filled_price:.4f}, fee: {fee:.4f}, PnL: {order.pnl:.2f}"
            )

        except Exception as e:
            logger.error(f"Error executing order: {e}")

    async def process_tick(self, msg):
        """Process market tick and check pending orders"""
        try:
            data = orjson.loads(msg.data)
            symbol = data["symbol"]
            price = data["price"]

            # Update current price
            self.current_prices[symbol] = price

            # Update position PnL
            if symbol in self.positions:
                self.positions[symbol].update_pnl(price)

            # Check pending orders for this symbol
            for order_id, order in list(self.pending_orders.items()):
                if order.symbol != symbol:
                    continue

                # Simple execution logic - execute at market price
                # In real trading, would check limit price conditions
                should_execute = False

                if order.side == OrderSide.BUY and price <= order.price:
                    should_execute = True
                elif order.side == OrderSide.SELL and price >= order.price:
                    should_execute = True

                if should_execute:
                    await self.execute_order(order, price)

            # Update stats in Redis
            await self.update_redis_state()

        except Exception as e:
            logger.error(f"Error processing tick: {e}")

    async def update_redis_state(self):
        """Update current state in Redis"""
        try:
            # Calculate metrics
            total_value = sum(p.value for p in self.positions.values())
            unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
            realized_pnl = sum(p.realized_pnl for p in self.positions.values())

            current_balance = self.balance + total_value
            drawdown = (self.initial_balance - current_balance) / self.initial_balance * 100
            self.stats["max_drawdown"] = max(self.stats["max_drawdown"], drawdown)

            # Calculate win rate
            winning_trades = sum(1 for o in self.orders if o.pnl > 0)
            total_trades = len([o for o in self.orders if o.pnl != 0])
            self.stats["win_rate"] = winning_trades / total_trades * 100 if total_trades > 0 else 0

            # Store in Redis
            state = {
                "balance": self.balance,
                "total_value": total_value,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "positions": len(self.positions),
                "pending_orders": len(self.pending_orders),
                "win_rate": self.stats["win_rate"],
                "max_drawdown": self.stats["max_drawdown"],
                "timestamp": datetime.now(UTC).isoformat(),
            }

            await self.redis.set("paper:state", orjson.dumps(state))

            # Store positions
            for symbol, position in self.positions.items():
                await self.redis.hset(
                    "paper:positions",
                    symbol,
                    orjson.dumps(
                        {
                            "quantity": position.quantity,
                            "avg_price": position.avg_price,
                            "unrealized_pnl": position.unrealized_pnl,
                            "realized_pnl": position.realized_pnl,
                        }
                    ),
                )

        except Exception as e:
            logger.error(f"Error updating Redis state: {e}")

    async def run(self):
        """Main run loop"""
        self.running = True

        # Subscribe to market ticks
        subscription = await self.nats.subscribe("ticks.*", cb=self.process_tick)
        logger.info("Paper trading engine started")

        try:
            while self.running:
                await asyncio.sleep(1)

                # Periodic metrics update
                if int(time.time()) % 30 == 0:
                    await self.log_metrics()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            await subscription.unsubscribe()
            self.running = False

    async def log_metrics(self):
        """Log current metrics"""
        metrics = {
            "balance": self.balance,
            "positions": len(self.positions),
            "pending_orders": len(self.pending_orders),
            "total_orders": self.stats["total_orders"],
            "filled_orders": self.stats["filled_orders"],
            "rejected_orders": self.stats["rejected_orders"],
            "total_pnl": self.stats["total_pnl"],
            "win_rate": self.stats["win_rate"],
            "max_drawdown": self.stats["max_drawdown"],
        }
        logger.info(f"Paper trading metrics: {json.dumps(metrics, indent=2)}")

    async def stop(self):
        """Stop the engine"""
        self.running = False
        await self.log_metrics()
