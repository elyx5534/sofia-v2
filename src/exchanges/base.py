"""
Sofia V2 - Unified Exchange Interface
Production-ready base class for all exchanges
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExchangeStatus(Enum):
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class Balance:
    """Account balance information"""

    currency: str
    free: Decimal
    used: Decimal
    total: Decimal

    @property
    def available(self) -> Decimal:
        return self.free


@dataclass
class Ticker:
    """Market ticker data"""

    symbol: str
    timestamp: int
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    change_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    vwap: Optional[Decimal] = None

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def spread_percentage(self) -> Decimal:
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 100
        return Decimal(0)


@dataclass
class OrderBook:
    """Order book data"""

    symbol: str
    timestamp: int
    bids: List[List[Decimal]]  # [[price, amount], ...]
    asks: List[List[Decimal]]  # [[price, amount], ...]

    @property
    def best_bid(self) -> Optional[Decimal]:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Decimal]:
        return self.asks[0][0] if self.asks else None

    @property
    def spread(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    def get_depth(self, side: str, price_levels: int = 5) -> Decimal:
        """Calculate total volume at given price levels"""
        orders = self.bids if side == "bid" else self.asks
        total = Decimal(0)
        for i, (price, amount) in enumerate(orders):
            if i >= price_levels:
                break
            total += amount
        return total


@dataclass
class Order:
    """Order information"""

    id: str
    exchange: str
    symbol: str
    type: OrderType
    side: OrderSide
    price: Optional[Decimal]
    amount: Decimal
    filled: Decimal = Decimal(0)
    remaining: Decimal = field(init=False)
    status: OrderStatus = OrderStatus.PENDING
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    trades: List[Dict] = field(default_factory=list)
    client_order_id: Optional[str] = None

    def __post_init__(self):
        self.remaining = self.amount - self.filled

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_open(self) -> bool:
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]

    @property
    def fill_percentage(self) -> Decimal:
        if self.amount > 0:
            return (self.filled / self.amount) * 100
        return Decimal(0)


@dataclass
class Trade:
    """Trade execution information"""

    id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    amount: Decimal
    fee: Decimal
    fee_currency: str
    timestamp: int

    @property
    def cost(self) -> Decimal:
        return self.price * self.amount


class RateLimiter:
    """Rate limiter to prevent API bans"""

    def __init__(self, requests_per_second: int = 10, burst: int = 20):
        self.requests_per_second = requests_per_second
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, weight: int = 1):
        """Acquire permission to make a request"""
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.requests_per_second)
            self.last_update = now

            if self.tokens < weight:
                sleep_time = (weight - self.tokens) / self.requests_per_second
                await asyncio.sleep(sleep_time)
                self.tokens = weight

            self.tokens -= weight


class BaseExchange(ABC):
    """Base class for all exchange implementations"""

    def __init__(self, config: Dict[str, Any]):
        self.name = self.__class__.__name__.replace("Exchange", "").lower()
        self.config = config
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.testnet = config.get("testnet", False)
        self.status = ExchangeStatus.DISCONNECTED
        self.rate_limiter = RateLimiter(
            requests_per_second=config.get("rate_limit", 10), burst=config.get("burst_limit", 20)
        )
        self.websocket_handlers: Dict[str, List[Callable]] = {}
        self.last_ping = 0
        self.latency_ms = 0
        self.error_count = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.get("max_reconnect", 5)
        self.reconnect_delay = config.get("reconnect_delay", 5)

        # Fee structure
        self.maker_fee = Decimal(str(config.get("maker_fee", "0.001")))
        self.taker_fee = Decimal(str(config.get("taker_fee", "0.001")))

        # WebSocket connection
        self.ws_connection = None
        self.ws_connected = False

        # Cache
        self.ticker_cache: Dict[str, Ticker] = {}
        self.orderbook_cache: Dict[str, OrderBook] = {}
        self.balance_cache: Dict[str, Balance] = {}
        self.cache_ttl = config.get("cache_ttl", 1000)  # milliseconds

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange API"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from exchange"""
        pass

    @abstractmethod
    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, Balance]:
        """Get account balance"""
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for symbol"""
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderBook:
        """Get order book for symbol"""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> Order:
        """Place an order"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an order"""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Order:
        """Get order status"""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders"""
        pass

    @abstractmethod
    async def get_order_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[Order]:
        """Get order history"""
        pass

    @abstractmethod
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Get trade history"""
        pass

    @abstractmethod
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to ticker updates via WebSocket"""
        pass

    @abstractmethod
    async def subscribe_orderbook(self, symbol: str, callback: Callable):
        """Subscribe to order book updates via WebSocket"""
        pass

    @abstractmethod
    async def subscribe_trades(self, symbol: str, callback: Callable):
        """Subscribe to trade updates via WebSocket"""
        pass

    async def ping(self) -> int:
        """Measure exchange latency"""
        start = time.time()
        try:
            # Implementation specific ping
            await self._ping_exchange()
            self.latency_ms = int((time.time() - start) * 1000)
            self.last_ping = int(time.time())
            return self.latency_ms
        except Exception as e:
            logger.error(f"{self.name} ping failed: {e}")
            return -1

    async def _ping_exchange(self):
        """Exchange-specific ping implementation"""
        # Default: get server time
        pass

    def calculate_fee(self, amount: Decimal, price: Decimal, is_maker: bool = False) -> Decimal:
        """Calculate trading fee"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        return amount * price * fee_rate

    def is_cache_valid(self, timestamp: int) -> bool:
        """Check if cached data is still valid"""
        return (int(time.time() * 1000) - timestamp) < self.cache_ttl

    async def reconnect_websocket(self):
        """Reconnect WebSocket with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"{self.name}: Max reconnection attempts reached")
            self.status = ExchangeStatus.ERROR
            return False

        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))

        logger.info(
            f"{self.name}: Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        try:
            await self.disconnect()
            success = await self.connect()
            if success:
                self.reconnect_attempts = 0
                self.status = ExchangeStatus.CONNECTED
                logger.info(f"{self.name}: Reconnected successfully")
                return True
        except Exception as e:
            logger.error(f"{self.name}: Reconnection failed: {e}")

        return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        latency = await self.ping()

        return {
            "exchange": self.name,
            "status": self.status.value,
            "latency_ms": latency,
            "last_ping": self.last_ping,
            "error_count": self.error_count,
            "ws_connected": self.ws_connected,
            "cached_symbols": len(self.ticker_cache),
            "open_orders": 0,  # Override in implementation
            "testnet": self.testnet,
        }

    def format_symbol(self, base: str, quote: str) -> str:
        """Format trading pair symbol for this exchange"""
        # Default format: BTCUSDT
        # Override in specific exchanges if different
        return f"{base}{quote}"

    def parse_symbol(self, symbol: str) -> tuple[str, str]:
        """Parse symbol into base and quote currencies"""
        # Simple parser for common formats
        # Override for specific exchanges
        if "/" in symbol:
            return tuple(symbol.split("/"))
        # Assume last 3-4 chars are quote currency
        for i in [4, 3]:
            if len(symbol) > i:
                quote = symbol[-i:]
                if quote in ["USDT", "USD", "BTC", "ETH", "BNB", "TRY"]:
                    return symbol[:-i], quote
        return symbol, "USDT"  # Default
