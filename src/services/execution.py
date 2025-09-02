"""
Execution Service - Order Router, Paper Broker, and Risk Guard
Handles both paper and live trading with CCXT integration
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional

import ccxt

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """Order representation"""

    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = None
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    fees: float = 0.0

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Position:
    """Position tracking"""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def update_pnl(self, current_price: float):
        """Update unrealized PnL"""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.entry_price) * self.quantity


class RiskGuard:
    """Risk management and safety controls"""

    def __init__(self, config: Dict[str, Any]):
        self.daily_loss_limit = config.get("daily_loss_limit_pct", 2.0)  # 2% daily loss limit
        self.position_limit = config.get("position_limit", 10)
        self.max_position_size = config.get("max_position_size_pct", 20.0)  # 20% per position
        self.notional_cap = config.get("notional_cap", 100000)  # $100k max notional
        self.kill_switch_active = False
        self.daily_pnl = 0.0
        self.start_of_day = datetime.now().replace(hour=0, minute=0, second=0)
        self.positions_count = 0

    def check_order(self, order: Order, account_balance: float) -> tuple[bool, str]:
        """Check if order passes risk controls"""

        # Kill switch check
        if self.kill_switch_active:
            return False, "Kill switch is active"

        # Daily loss check
        if self.daily_pnl < -(self.daily_loss_limit / 100 * account_balance):
            self.kill_switch_active = True
            return False, f"Daily loss limit exceeded: {self.daily_pnl:.2f}"

        # Position limit check
        if order.side == "buy" and self.positions_count >= self.position_limit:
            return False, f"Position limit reached: {self.position_limit}"

        # Position size check
        order_value = order.quantity * (order.price or 0)
        if order_value > (self.max_position_size / 100 * account_balance):
            return (
                False,
                f"Position too large: {order_value:.2f} > {self.max_position_size}% of account",
            )

        # Notional cap check
        if order_value > self.notional_cap:
            return False, f"Exceeds notional cap: {order_value:.2f} > {self.notional_cap}"

        return True, "OK"

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking"""
        # Reset if new day
        now = datetime.now()
        if now.date() > self.start_of_day.date():
            self.daily_pnl = 0.0
            self.start_of_day = now.replace(hour=0, minute=0, second=0)
            self.kill_switch_active = False

        self.daily_pnl += pnl

    def reset_kill_switch(self):
        """Manual reset of kill switch"""
        self.kill_switch_active = False
        logger.info("Kill switch manually reset")


class PaperBroker:
    """Paper trading broker for simulation"""

    def __init__(self, initial_balance: float = 10000):
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.trade_history = []

    def place_order(self, order: Order) -> str:
        """Place a paper order"""
        # Generate order ID
        self.order_counter += 1
        order.id = f"PAPER-{self.order_counter:06d}"

        # Store order
        self.orders[order.id] = order
        order.status = OrderStatus.OPEN

        # Simulate immediate fill for market orders
        if order.type == OrderType.MARKET:
            self._fill_order(order)

        logger.info(
            f"Paper order placed: {order.id} - {order.side} {order.quantity} {order.symbol}"
        )
        return order.id

    def _fill_order(self, order: Order):
        """Simulate order fill"""
        # Get current market price (simulated)
        fill_price = order.price or self._get_market_price(order.symbol)

        # Calculate fees (0.1% taker fee)
        fees = order.quantity * fill_price * 0.001

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_qty = order.quantity
        order.avg_fill_price = fill_price
        order.fees = fees

        # Update position
        if order.side == "buy":
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                # Average in
                total_qty = pos.quantity + order.quantity
                pos.entry_price = (
                    pos.entry_price * pos.quantity + fill_price * order.quantity
                ) / total_qty
                pos.quantity = total_qty
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    current_price=fill_price,
                )
            self.balance -= fill_price * order.quantity + fees
        else:  # sell
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self.positions[order.symbol]
            self.balance += fill_price * order.quantity - fees

        # Record trade
        self.trade_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": fill_price,
                "fees": fees,
            }
        )

    def _get_market_price(self, symbol: str) -> float:
        """Get simulated market price"""
        # In real implementation, fetch from data provider
        # For now, return a dummy price
        prices = {"BTC/USDT": 50000, "ETH/USDT": 3000, "SOL/USDT": 100, "BNB/USDT": 300}
        return prices.get(symbol, 100)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order"""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status == OrderStatus.OPEN:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        return self.positions.copy()

    def get_balance(self) -> float:
        """Get account balance"""
        return self.balance

    def get_equity(self) -> float:
        """Get total equity (balance + positions)"""
        equity = self.balance
        for pos in self.positions.values():
            equity += pos.quantity * pos.current_price
        return equity


class OrderRouter:
    """Routes orders to appropriate exchange or paper broker"""

    def __init__(self, config: Dict[str, Any]):
        self.mode: Literal["paper", "live"] = config.get("mode", "paper")
        self.paper_broker = PaperBroker(config.get("initial_balance", 10000))
        self.risk_guard = RiskGuard(config.get("risk", {}))
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.active_exchange: Optional[str] = None

        # Initialize exchanges if in live mode
        if self.mode == "live":
            self._init_exchanges(config.get("exchanges", {}))

    def _init_exchanges(self, exchange_configs: Dict):
        """Initialize CCXT exchange connections"""
        for name, config in exchange_configs.items():
            try:
                exchange_class = getattr(ccxt, config["exchange"])
                self.exchanges[name] = exchange_class(
                    {
                        "apiKey": config.get("api_key"),
                        "secret": config.get("secret"),
                        "enableRateLimit": True,
                        "options": config.get("options", {}),
                    }
                )
                logger.info(f"Initialized exchange: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize exchange {name}: {e}")

        # Set default active exchange
        if self.exchanges:
            self.active_exchange = list(self.exchanges.keys())[0]

    def switch_mode(self, mode: Literal["paper", "live"]) -> bool:
        """Switch between paper and live trading"""
        if mode == "live" and not self.exchanges:
            logger.error("Cannot switch to live mode: no exchanges configured")
            return False

        old_mode = self.mode
        self.mode = mode
        logger.info(f"Switched from {old_mode} to {mode} mode")
        return True

    async def place_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Place an order (paper or live)"""

        # Create order object
        order = Order(
            id="",  # Will be set by broker
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )

        # Risk checks
        account_balance = self._get_account_balance()
        passed, reason = self.risk_guard.check_order(order, account_balance)
        if not passed:
            logger.warning(f"Order rejected by risk guard: {reason}")
            order.status = OrderStatus.REJECTED
            return {"success": False, "order_id": None, "reason": reason}

        # Route to appropriate broker
        if self.mode == "paper":
            order_id = self.paper_broker.place_order(order)
        else:
            order_id = await self._place_live_order(order)

        return {"success": True, "order_id": order_id, "order": asdict(order)}

    async def _place_live_order(self, order: Order) -> str:
        """Place order on live exchange via CCXT"""
        if not self.active_exchange:
            raise ValueError("No active exchange configured")

        exchange = self.exchanges[self.active_exchange]

        try:
            # Prepare order parameters
            order_params = {
                "symbol": order.symbol,
                "type": order.type.value,
                "side": order.side,
                "amount": order.quantity,
            }

            if order.price:
                order_params["price"] = order.price
            if order.stop_price:
                order_params["stopPrice"] = order.stop_price

            # Place order
            result = await exchange.create_order(**order_params)
            order_id = result["id"]

            logger.info(f"Live order placed: {order_id} on {self.active_exchange}")
            return order_id

        except Exception as e:
            logger.error(f"Failed to place live order: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if self.mode == "paper":
            return self.paper_broker.cancel_order(order_id)
        else:
            return self._cancel_live_order(order_id)

    def _cancel_live_order(self, order_id: str) -> bool:
        """Cancel order on live exchange"""
        if not self.active_exchange:
            return False

        exchange = self.exchanges[self.active_exchange]

        try:
            exchange.cancel_order(order_id)
            logger.info(f"Live order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        if self.mode == "paper":
            return self.paper_broker.get_positions()
        else:
            return self._get_live_positions()

    def _get_live_positions(self) -> Dict[str, Position]:
        """Get positions from live exchange"""
        if not self.active_exchange:
            return {}

        exchange = self.exchanges[self.active_exchange]

        try:
            # Fetch balance
            balance = exchange.fetch_balance()
            positions = {}

            for currency, info in balance["total"].items():
                if info > 0 and currency != "USDT":
                    symbol = f"{currency}/USDT"
                    ticker = exchange.fetch_ticker(symbol)

                    positions[symbol] = Position(
                        symbol=symbol,
                        quantity=info,
                        entry_price=0,  # Unknown for spot
                        current_price=ticker["last"],
                    )

            return positions

        except Exception as e:
            logger.error(f"Failed to fetch live positions: {e}")
            return {}

    def _get_account_balance(self) -> float:
        """Get account balance for risk checks"""
        if self.mode == "paper":
            return self.paper_broker.get_balance()
        else:
            if self.active_exchange:
                exchange = self.exchanges[self.active_exchange]
                try:
                    balance = exchange.fetch_balance()
                    return balance["USDT"]["free"] if "USDT" in balance else 0
                except:
                    return 10000  # Default fallback
            return 10000

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics"""
        return {
            "mode": self.mode,
            "balance": self._get_account_balance(),
            "positions_count": len(self.get_positions()),
            "daily_pnl": self.risk_guard.daily_pnl,
            "kill_switch": self.risk_guard.kill_switch_active,
            "active_exchange": self.active_exchange,
        }


# Global instance
execution_service = None


def init_execution_service(config: Dict[str, Any]):
    """Initialize the execution service"""
    global execution_service
    execution_service = OrderRouter(config)
    logger.info(f"Execution service initialized in {config.get('mode', 'paper')} mode")
    return execution_service


def get_execution_service() -> OrderRouter:
    """Get the execution service instance"""
    if execution_service is None:
        # Initialize with default config
        return init_execution_service({"mode": "paper"})
    return execution_service
