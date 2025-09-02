"""
Realistic Fill Engine with Maker-Only, Partial Fills, and Timeout
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Represents an order in the fill engine"""

    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'limit' or 'market'
    quantity: Decimal
    price: Decimal
    maker_only: bool = True
    cancel_unfilled_sec: int = 60
    taker_fallback: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    filled_quantity: Decimal = field(default=Decimal("0"))
    status: str = "pending"  # pending, partial, filled, cancelled
    fills: List[Dict] = field(default_factory=list)


@dataclass
class OrderBook:
    """Simulated order book for realistic fills"""

    bids: List[Tuple[Decimal, Decimal]]  # [(price, size), ...]
    asks: List[Tuple[Decimal, Decimal]]
    last_update: datetime = field(default_factory=datetime.now)


class RealisticFillEngine:
    """Simulates realistic order fills with maker-only logic"""

    def __init__(self):
        self.active_orders: Dict[str, Order] = {}
        self.fill_history: List[Dict] = []
        self.orderbooks: Dict[str, OrderBook] = {}
        self.metrics = {
            "maker_fills": 0,
            "taker_fills": 0,
            "partial_fills": 0,
            "cancelled_orders": 0,
            "total_fill_time_ms": 0,
            "fill_count": 0,
            "cancelled_quantity": Decimal("0"),
            "price_strategy_join": 0,
            "price_strategy_step_in": 0,
        }
        self._running = False
        self._tasks = []

        # Initialize price placement
        try:
            from src.paper_trading.price_placement import PricePlacement

            self.price_placement = PricePlacement()
        except ImportError:
            logger.warning("Price placement module not available")
            self.price_placement = None

    async def start(self):
        """Start the fill engine"""
        self._running = True
        # Start order monitoring task
        monitor_task = asyncio.create_task(self._monitor_orders())
        self._tasks.append(monitor_task)

    async def stop(self):
        """Stop the fill engine"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def submit_order(self, order: Order) -> str:
        """Submit an order to the fill engine"""
        self.active_orders[order.order_id] = order
        return order.order_id

    async def _monitor_orders(self):
        """Monitor orders for fills and timeouts"""
        while self._running:
            current_time = datetime.now()

            for order_id, order in list(self.active_orders.items()):
                if order.status in ["filled", "cancelled"]:
                    continue

                # Check timeout
                if (current_time - order.timestamp).seconds > order.cancel_unfilled_sec:
                    self._cancel_order(order)
                    continue

                # Try to fill order
                await self._attempt_fill(order)

            await asyncio.sleep(0.5)  # Check every 500ms

    async def _attempt_fill(self, order: Order):
        """Attempt to fill an order based on market conditions"""
        # Get or simulate orderbook
        orderbook = self._get_orderbook(order.symbol)

        if order.maker_only:
            # Maker-only: only fill if our price is better than market
            if not self._can_fill_as_maker(order, orderbook):
                return

        # Calculate available liquidity
        available_liquidity = self._get_available_liquidity(order, orderbook)

        if available_liquidity <= 0:
            return

        # Determine fill quantity (partial or full)
        fill_quantity = min(order.quantity - order.filled_quantity, available_liquidity)

        # Simulate realistic delay
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Execute fill
        self._execute_fill(order, fill_quantity, order.price)

    def _can_fill_as_maker(self, order: Order, orderbook: OrderBook) -> bool:
        """Check if order can be filled as maker"""
        if order.side == "buy":
            # Buy order: our price must be <= best bid (providing liquidity)
            best_bid = orderbook.bids[0][0] if orderbook.bids else Decimal("0")
            return order.price <= best_bid
        else:
            # Sell order: our price must be >= best ask
            best_ask = orderbook.asks[0][0] if orderbook.asks else Decimal("999999999")
            return order.price >= best_ask

    def _get_available_liquidity(self, order: Order, orderbook: OrderBook) -> Decimal:
        """Calculate available liquidity at order price"""
        liquidity = Decimal("0")

        if order.side == "buy":
            # Check asks for sellers at or below our price
            for ask_price, ask_size in orderbook.asks:
                if ask_price <= order.price:
                    liquidity += ask_size
                else:
                    break
        else:
            # Check bids for buyers at or above our price
            for bid_price, bid_size in orderbook.bids:
                if bid_price >= order.price:
                    liquidity += bid_size
                else:
                    break

        # Simulate partial liquidity (more realistic)
        return liquidity * Decimal(str(random.uniform(0.3, 1.0)))

    def _execute_fill(self, order: Order, fill_quantity: Decimal, fill_price: Decimal):
        """Execute a fill for the order"""
        fill_time_ms = int((datetime.now() - order.timestamp).total_seconds() * 1000)

        fill = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": float(fill_quantity),
            "price": float(fill_price),
            "timestamp": datetime.now().isoformat(),
            "fill_type": "maker" if order.maker_only else "taker",
            "fill_time_ms": fill_time_ms,
        }

        order.filled_quantity += fill_quantity
        order.fills.append(fill)
        self.fill_history.append(fill)

        # Update metrics
        if order.maker_only:
            self.metrics["maker_fills"] += 1
        else:
            self.metrics["taker_fills"] += 1

        if order.filled_quantity < order.quantity:
            order.status = "partial"
            self.metrics["partial_fills"] += 1
        else:
            order.status = "filled"

        self.metrics["total_fill_time_ms"] += fill_time_ms
        self.metrics["fill_count"] += 1

        # Write fill to JSONL
        self._write_fill_to_jsonl(fill)

    def _cancel_order(self, order: Order):
        """Cancel an order due to timeout"""
        unfilled_quantity = order.quantity - order.filled_quantity

        order.status = "cancelled"
        self.metrics["cancelled_orders"] += 1
        self.metrics["cancelled_quantity"] += unfilled_quantity

        # Log cancellation
        cancel_log = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "cancelled_quantity": float(unfilled_quantity),
            "filled_quantity": float(order.filled_quantity),
            "timestamp": datetime.now().isoformat(),
            "reason": "timeout",
        }

        self._write_cancel_to_jsonl(cancel_log)

    def _get_orderbook(self, symbol: str) -> OrderBook:
        """Get or simulate orderbook for a symbol"""
        # In production, fetch real orderbook
        # For simulation, generate realistic orderbook

        if (
            symbol not in self.orderbooks
            or (datetime.now() - self.orderbooks[symbol].last_update).seconds > 1
        ):
            # Simulate orderbook with realistic spread
            mid_price = Decimal("108000") if "BTC" in symbol else Decimal("100")
            spread = mid_price * Decimal("0.0001")  # 0.01% spread

            bids = []
            asks = []

            # Generate 10 levels
            for i in range(10):
                bid_price = mid_price - spread * (i + 1)
                ask_price = mid_price + spread * (i + 1)

                # Random size between 0.001 and 0.1 BTC
                bid_size = Decimal(str(random.uniform(0.001, 0.1)))
                ask_size = Decimal(str(random.uniform(0.001, 0.1)))

                bids.append((bid_price, bid_size))
                asks.append((ask_price, ask_size))

            self.orderbooks[symbol] = OrderBook(bids=bids, asks=asks)

        return self.orderbooks[symbol]

    def _write_fill_to_jsonl(self, fill: Dict):
        """Write fill to JSONL file"""
        jsonl_path = Path("logs/paper_fills.jsonl")
        jsonl_path.parent.mkdir(exist_ok=True)

        with open(jsonl_path, "a") as f:
            f.write(json.dumps(fill) + "\n")
            f.flush()

    def _write_cancel_to_jsonl(self, cancel_log: Dict):
        """Write cancellation to JSONL file"""
        jsonl_path = Path("logs/paper_cancels.jsonl")
        jsonl_path.parent.mkdir(exist_ok=True)

        with open(jsonl_path, "a") as f:
            f.write(json.dumps(cancel_log) + "\n")
            f.flush()

    def get_metrics(self) -> Dict:
        """Get fill engine metrics"""
        avg_fill_time = (
            self.metrics["total_fill_time_ms"] / self.metrics["fill_count"]
            if self.metrics["fill_count"] > 0
            else 0
        )

        maker_fill_rate = (
            self.metrics["maker_fills"] / self.metrics["fill_count"] * 100
            if self.metrics["fill_count"] > 0
            else 0
        )

        return {
            "maker_fill_rate": round(maker_fill_rate, 1),
            "avg_time_to_fill_ms": round(avg_fill_time, 0),
            "partial_fill_count": self.metrics["partial_fills"],
            "cancelled_orders": self.metrics["cancelled_orders"],
            "cancelled_quantity": float(self.metrics["cancelled_quantity"]),
            "total_fills": self.metrics["fill_count"],
        }

    def save_metrics(self):
        """Save metrics to JSON file"""
        metrics_path = Path("logs/paper_metrics.json")
        metrics_path.parent.mkdir(exist_ok=True)

        with open(metrics_path, "w") as f:
            json.dump(self.get_metrics(), f, indent=2)
