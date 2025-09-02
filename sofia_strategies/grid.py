"""
Grid trading strategy implementation for Sofia V2.
Places layered limit orders around mid-price with inventory management.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import redis.asyncio as redis

from .base import Signal, SignalType, Strategy

logger = logging.getLogger(__name__)


class GridStrategy(Strategy):
    """
    Grid trading strategy with inventory management and risk controls.

    Parameters:
        base_qty: Base quantity per grid level (USD)
        grid_step_pct: Distance between grid levels (%)
        grid_levels: Number of grid levels above and below mid
        take_profit_pct: Take profit threshold (%)
        max_inventory: Maximum inventory in base currency
        cooldown_s: Cooldown between orders (seconds)
        rebalance_threshold: Inventory imbalance threshold for rebalancing
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Grid parameters
        self.base_qty = config.get("base_qty", 20.0)
        self.grid_step_pct = config.get("grid_step_pct", 0.45)
        self.grid_levels = config.get("grid_levels", 5)
        self.take_profit_pct = config.get("take_profit_pct", 2.0)
        self.max_inventory = config.get("max_inventory", 200.0)
        self.cooldown_s = config.get("cooldown_s", 5)
        self.rebalance_threshold = config.get("rebalance_threshold", 0.7)

        # State tracking
        self.mid_price: float = 0.0
        self.grid_orders: Dict[str, Dict] = {}  # order_id -> {price, qty, side}
        self.inventory: float = 0.0
        self.last_order_time: datetime = datetime.now(UTC) - timedelta(seconds=self.cooldown_s)
        self.last_rebalance: datetime = datetime.now(UTC)
        self.price_history: List[float] = []
        self.volatility: float = 0.0

        # Redis client for state persistence
        self.redis_client: Optional[redis.Redis] = None
        self.symbol: str = ""

    def initialize(self, symbol: str, historical_data: Optional[pd.DataFrame] = None):
        """Initialize strategy with historical data"""
        self.symbol = symbol
        self.state["symbol"] = symbol

        if historical_data is not None and len(historical_data) > 0:
            # Calculate initial volatility from historical data
            if "close" in historical_data.columns:
                returns = historical_data["close"].pct_change().dropna()
                self.volatility = returns.std() * np.sqrt(252)  # Annualized
                self.mid_price = historical_data["close"].iloc[-1]
                self.price_history = historical_data["close"].tail(100).tolist()

                logger.info(
                    f"Grid strategy initialized for {symbol}: "
                    f"mid_price={self.mid_price:.2f}, "
                    f"volatility={self.volatility:.4f}"
                )

    async def load_redis_state(self, redis_client: redis.Redis):
        """Load strategy state from Redis"""
        self.redis_client = redis_client

        try:
            # Load grid orders
            grid_key = f"grid:{self.symbol}:orders"
            orders_data = await redis_client.hgetall(grid_key)
            if orders_data:
                import orjson

                self.grid_orders = {k.decode(): orjson.loads(v) for k, v in orders_data.items()}

            # Load inventory
            inv_key = f"grid:{self.symbol}:inventory"
            inv_data = await redis_client.get(inv_key)
            if inv_data:
                self.inventory = float(inv_data)

            logger.info(
                f"Loaded grid state from Redis: "
                f"{len(self.grid_orders)} orders, "
                f"inventory={self.inventory:.2f}"
            )

        except Exception as e:
            logger.error(f"Error loading Redis state: {e}")

    async def save_redis_state(self):
        """Save strategy state to Redis"""
        if not self.redis_client:
            return

        try:
            import orjson

            # Save grid orders
            grid_key = f"grid:{self.symbol}:orders"
            if self.grid_orders:
                await self.redis_client.hset(
                    grid_key,
                    mapping={
                        order_id: orjson.dumps(order_data)
                        for order_id, order_data in self.grid_orders.items()
                    },
                )

            # Save inventory
            inv_key = f"grid:{self.symbol}:inventory"
            await self.redis_client.set(inv_key, str(self.inventory))

            # Set expiry
            await self.redis_client.expire(grid_key, 86400)  # 24 hours
            await self.redis_client.expire(inv_key, 86400)

        except Exception as e:
            logger.error(f"Error saving Redis state: {e}")

    def _calculate_grid_levels(self) -> Dict[str, List[float]]:
        """Calculate grid price levels"""
        if self.mid_price <= 0:
            return {"buy": [], "sell": []}

        buy_levels = []
        sell_levels = []

        for i in range(1, self.grid_levels + 1):
            # Buy levels below mid price
            buy_price = self.mid_price * (1 - i * self.grid_step_pct / 100)
            buy_levels.append(buy_price)

            # Sell levels above mid price
            sell_price = self.mid_price * (1 + i * self.grid_step_pct / 100)
            sell_levels.append(sell_price)

        return {"buy": buy_levels, "sell": sell_levels}

    def _should_rebalance(self) -> bool:
        """Check if inventory needs rebalancing"""
        if abs(self.inventory) > self.max_inventory * self.rebalance_threshold:
            return True

        # Check if it's been too long since last rebalance
        time_since_rebalance = (datetime.now(UTC) - self.last_rebalance).total_seconds()
        if time_since_rebalance > 3600:  # 1 hour
            return abs(self.inventory) > self.max_inventory * 0.5

        return False

    def _calculate_order_size(self, price: float, side: SignalType) -> float:
        """Calculate order size based on inventory and volatility"""
        base_size = self.base_qty / price

        # Adjust for inventory
        inventory_factor = 1.0
        if side == SignalType.BUY and self.inventory > 0:
            # Reduce buy size if long inventory
            inventory_factor = max(0.5, 1 - self.inventory / self.max_inventory)
        elif side == SignalType.SELL and self.inventory < 0:
            # Reduce sell size if short inventory
            inventory_factor = max(0.5, 1 + self.inventory / self.max_inventory)

        # Adjust for volatility
        vol_factor = 1.0
        if self.volatility > 0:
            # Higher volatility = smaller size
            vol_factor = max(0.5, min(1.5, 0.02 / self.volatility))

        return base_size * inventory_factor * vol_factor

    def on_tick(self, tick: Dict[str, Any]) -> List[Signal]:
        """Process tick data and generate grid signals"""
        signals = []

        # Update mid price
        bid = tick.get("bid", 0)
        ask = tick.get("ask", 0)
        if bid > 0 and ask > 0:
            self.mid_price = (bid + ask) / 2
        else:
            self.mid_price = tick.get("price", self.mid_price)

        # Update price history
        self.price_history.append(self.mid_price)
        if len(self.price_history) > 100:
            self.price_history.pop(0)

        # Update volatility
        if len(self.price_history) >= 20:
            returns = np.diff(np.log(self.price_history[-20:]))
            self.volatility = np.std(returns) * np.sqrt(252)

        # Check cooldown
        time_since_last = (datetime.now(UTC) - self.last_order_time).total_seconds()
        if time_since_last < self.cooldown_s:
            return signals

        # Check for rebalancing
        if self._should_rebalance():
            rebalance_signal = self._generate_rebalance_signal()
            if rebalance_signal:
                signals.append(rebalance_signal)
                self.last_rebalance = datetime.now(UTC)
                return signals

        # Generate grid orders if needed
        grid_levels = self._calculate_grid_levels()

        # Check if we need to place new grid orders
        active_buy_prices = {
            order["price"] for order in self.grid_orders.values() if order["side"] == "buy"
        }
        active_sell_prices = {
            order["price"] for order in self.grid_orders.values() if order["side"] == "sell"
        }

        # Place buy orders
        for buy_price in grid_levels["buy"]:
            if buy_price not in active_buy_prices and self.inventory < self.max_inventory:
                quantity = self._calculate_order_size(buy_price, SignalType.BUY)
                signal = Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    strategy=self.name,
                    price=buy_price,
                    quantity=quantity,
                    strength=0.5,
                    reason=f"Grid buy level at {buy_price:.2f}",
                    metadata={
                        "grid_level": grid_levels["buy"].index(buy_price) + 1,
                        "inventory": self.inventory,
                        "volatility": self.volatility,
                    },
                    params_hash=self._params_hash,
                )
                signals.append(signal)

                # Track order
                self.grid_orders[signal.signal_id] = {
                    "price": buy_price,
                    "quantity": quantity,
                    "side": "buy",
                }

        # Place sell orders
        for sell_price in grid_levels["sell"]:
            if sell_price not in active_sell_prices and self.inventory > -self.max_inventory:
                quantity = self._calculate_order_size(sell_price, SignalType.SELL)
                signal = Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    strategy=self.name,
                    price=sell_price,
                    quantity=quantity,
                    strength=0.5,
                    reason=f"Grid sell level at {sell_price:.2f}",
                    metadata={
                        "grid_level": grid_levels["sell"].index(sell_price) + 1,
                        "inventory": self.inventory,
                        "volatility": self.volatility,
                    },
                    params_hash=self._params_hash,
                )
                signals.append(signal)

                # Track order
                self.grid_orders[signal.signal_id] = {
                    "price": sell_price,
                    "quantity": quantity,
                    "side": "sell",
                }

        # Check for take profit
        if abs(self.inventory) > 0:
            tp_signal = self._check_take_profit()
            if tp_signal:
                signals.append(tp_signal)

        if signals:
            self.last_order_time = datetime.now(UTC)
            for signal in signals:
                self.update_metrics(signal)

        return signals

    def on_bar(self, bar: Dict[str, Any]) -> List[Signal]:
        """Process bar data - grid strategy mainly uses ticks"""
        # Update price if no recent ticks
        if "close" in bar:
            self.mid_price = bar["close"]
            self.price_history.append(self.mid_price)
            if len(self.price_history) > 100:
                self.price_history.pop(0)

        # Could trigger rebalancing on bars
        return []

    def _generate_rebalance_signal(self) -> Optional[Signal]:
        """Generate rebalancing signal to reduce inventory"""
        if abs(self.inventory) < self.base_qty / self.mid_price:
            return None

        if self.inventory > 0:
            # Too long, need to sell
            quantity = min(
                self.inventory * 0.3,  # Sell 30% of inventory
                self.base_qty / self.mid_price * 2,  # But not more than 2x base
            )
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.SELL,
                strategy=self.name,
                price=None,  # Market order
                quantity=quantity,
                strength=0.7,
                reason=f"Rebalancing: reducing long inventory {self.inventory:.4f}",
                metadata={"rebalance": True, "inventory": self.inventory},
                params_hash=self._params_hash,
            )
        else:
            # Too short, need to buy
            quantity = min(abs(self.inventory) * 0.3, self.base_qty / self.mid_price * 2)
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.BUY,
                strategy=self.name,
                price=None,  # Market order
                quantity=quantity,
                strength=0.7,
                reason=f"Rebalancing: reducing short inventory {self.inventory:.4f}",
                metadata={"rebalance": True, "inventory": self.inventory},
                params_hash=self._params_hash,
            )

    def _check_take_profit(self) -> Optional[Signal]:
        """Check if we should take profit on current position"""
        if self.inventory == 0 or len(self.price_history) < 2:
            return None

        # Simple take profit based on price movement
        entry_price = (
            np.mean(self.price_history[-20:-10])
            if len(self.price_history) > 20
            else self.price_history[0]
        )
        current_price = self.mid_price

        pnl_pct = (current_price - entry_price) / entry_price * 100

        if self.inventory > 0 and pnl_pct > self.take_profit_pct:
            # Take profit on long position
            quantity = self.inventory * 0.5  # Close half
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.SELL,
                strategy=self.name,
                price=None,
                quantity=quantity,
                strength=0.8,
                reason=f"Take profit: {pnl_pct:.2f}% gain",
                metadata={"take_profit": True, "pnl_pct": pnl_pct},
                params_hash=self._params_hash,
            )
        elif self.inventory < 0 and pnl_pct < -self.take_profit_pct:
            # Take profit on short position
            quantity = abs(self.inventory) * 0.5
            return Signal(
                symbol=self.symbol,
                signal_type=SignalType.BUY,
                strategy=self.name,
                price=None,
                quantity=quantity,
                strength=0.8,
                reason=f"Take profit: {abs(pnl_pct):.2f}% gain on short",
                metadata={"take_profit": True, "pnl_pct": pnl_pct},
                params_hash=self._params_hash,
            )

        return None

    def on_order_fill(self, order: Dict[str, Any]):
        """Update inventory when order is filled"""
        if order["side"] == "buy":
            self.inventory += order["quantity"]
        else:
            self.inventory -= order["quantity"]

        # Remove from grid orders
        order_id = order.get("order_id")
        if order_id in self.grid_orders:
            del self.grid_orders[order_id]

        logger.info(
            f"Grid order filled: {order['side']} {order['quantity']:.4f} "
            f"@ {order['price']:.2f}, inventory={self.inventory:.4f}"
        )
