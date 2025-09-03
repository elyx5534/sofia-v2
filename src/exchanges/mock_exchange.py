"""
Mock Exchange for Testing
Simulates real exchange behavior with configurable latency and errors
"""

import asyncio
import logging
import random
import time
import uuid
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from src.exchanges.base import (
    Balance,
    BaseExchange,
    ExchangeStatus,
    Order,
    OrderBook,
    OrderSide,
    OrderStatus,
    OrderType,
    Ticker,
    Trade,
)

logger = logging.getLogger(__name__)


class MockExchange(BaseExchange):
    """Mock exchange for testing and development"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.min_latency = config.get("min_latency", 50)
        self.max_latency = config.get("max_latency", 500)
        self.fail_rate = config.get("fail_rate", 0.01)
        self.slippage_rate = config.get("slippage_rate", 0.001)
        self.mock_balances = {
            "USDT": Balance("USDT", Decimal("10000"), Decimal("0"), Decimal("10000")),
            "BTC": Balance("BTC", Decimal("0.5"), Decimal("0"), Decimal("0.5")),
            "ETH": Balance("ETH", Decimal("10"), Decimal("0"), Decimal("10")),
            "BNB": Balance("BNB", Decimal("50"), Decimal("0"), Decimal("50")),
        }
        self.base_prices = {
            "BTC/USDT": Decimal("45000"),
            "ETH/USDT": Decimal("3000"),
            "BNB/USDT": Decimal("400"),
            "SOL/USDT": Decimal("100"),
            "ADA/USDT": Decimal("0.5"),
        }
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.ws_tasks = []

    async def connect(self) -> bool:
        """Simulate connection with random latency"""
        await self._simulate_latency()
        if random.random() < self.fail_rate:
            self.status = ExchangeStatus.ERROR
            logger.error(f"Mock exchange {self.name} connection failed (simulated)")
            return False
        self.status = ExchangeStatus.CONNECTED
        logger.info(f"Mock exchange {self.name} connected")
        return True

    async def disconnect(self):
        """Disconnect mock exchange"""
        for task in self.ws_tasks:
            task.cancel()
        self.status = ExchangeStatus.DISCONNECTED
        logger.info(f"Mock exchange {self.name} disconnected")

    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, Balance]:
        """Get mock balance"""
        await self._simulate_latency()
        await self._simulate_error()
        if currency:
            if currency in self.mock_balances:
                return {currency: self.mock_balances[currency]}
            return {}
        return self.mock_balances.copy()

    async def get_ticker(self, symbol: str) -> Ticker:
        """Generate mock ticker"""
        await self._simulate_latency()
        await self._simulate_error()
        base_price = self.base_prices.get(symbol, Decimal("100"))
        variation = Decimal(str(random.uniform(0.98, 1.02)))
        price = base_price * variation
        spread = price * Decimal("0.001")
        return Ticker(
            symbol=symbol,
            timestamp=int(time.time() * 1000),
            bid=price - spread / 2,
            ask=price + spread / 2,
            last=price,
            volume_24h=Decimal(str(random.uniform(1000, 10000))),
            change_24h=Decimal(str(random.uniform(-5, 5))),
            high_24h=price * Decimal("1.05"),
            low_24h=price * Decimal("0.95"),
            vwap=price,
        )

    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderBook:
        """Generate mock orderbook"""
        await self._simulate_latency()
        await self._simulate_error()
        base_price = self.base_prices.get(symbol, Decimal("100"))
        bids = []
        asks = []
        for i in range(limit):
            bid_price = base_price * (Decimal("1") - Decimal(str(0.0001 * (i + 1))))
            bid_amount = Decimal(str(random.uniform(0.1, 10)))
            bids.append([bid_price, bid_amount])
            ask_price = base_price * (Decimal("1") + Decimal(str(0.0001 * (i + 1))))
            ask_amount = Decimal(str(random.uniform(0.1, 10)))
            asks.append([ask_price, ask_amount])
        return OrderBook(symbol=symbol, timestamp=int(time.time() * 1000), bids=bids, asks=asks)

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> Order:
        """Simulate order placement"""
        await self._simulate_latency()
        await self._simulate_error()
        self.order_counter += 1
        order_id = f"MOCK-{self.order_counter}-{uuid.uuid4().hex[:8]}"
        if order_type == OrderType.MARKET:
            ticker = await self.get_ticker(symbol)
            if side == OrderSide.BUY:
                price = ticker.ask * (1 + Decimal(str(self.slippage_rate)))
            else:
                price = ticker.bid * (1 - Decimal(str(self.slippage_rate)))
        base, quote = self.parse_symbol(symbol)
        if side == OrderSide.BUY:
            required = amount * price
            currency = quote
        else:
            required = amount
            currency = base
        if currency in self.mock_balances:
            if self.mock_balances[currency].free < required:
                raise Exception(f"Insufficient balance: need {required} {currency}")
            self.mock_balances[currency] = Balance(
                currency=currency,
                free=self.mock_balances[currency].free - required,
                used=self.mock_balances[currency].used + required,
                total=self.mock_balances[currency].total,
            )
        order = Order(
            id=order_id,
            exchange=self.name,
            symbol=symbol,
            type=order_type,
            side=side,
            price=price,
            amount=amount,
            filled=amount if order_type == OrderType.MARKET else Decimal(0),
            status=OrderStatus.FILLED if order_type == OrderType.MARKET else OrderStatus.OPEN,
            timestamp=int(time.time() * 1000),
            fee=self.calculate_fee(amount, price),
            fee_currency=quote if side == OrderSide.BUY else base,
            client_order_id=kwargs.get("client_order_id"),
        )
        self.orders[order_id] = order
        if order_type == OrderType.MARKET:
            if side == OrderSide.BUY:
                if base not in self.mock_balances:
                    self.mock_balances[base] = Balance(base, Decimal(0), Decimal(0), Decimal(0))
                self.mock_balances[base] = Balance(
                    currency=base,
                    free=self.mock_balances[base].free + amount,
                    used=self.mock_balances[base].used,
                    total=self.mock_balances[base].total + amount,
                )
                self.mock_balances[quote] = Balance(
                    currency=quote,
                    free=self.mock_balances[quote].free,
                    used=self.mock_balances[quote].used - amount * price,
                    total=self.mock_balances[quote].total,
                )
            else:
                received = amount * price * (1 - self.taker_fee)
                if quote not in self.mock_balances:
                    self.mock_balances[quote] = Balance(quote, Decimal(0), Decimal(0), Decimal(0))
                self.mock_balances[quote] = Balance(
                    currency=quote,
                    free=self.mock_balances[quote].free + received,
                    used=self.mock_balances[quote].used,
                    total=self.mock_balances[quote].total + received,
                )
                self.mock_balances[base] = Balance(
                    currency=base,
                    free=self.mock_balances[base].free,
                    used=self.mock_balances[base].used - amount,
                    total=self.mock_balances[base].total,
                )
        logger.info(f"Mock order placed: {order_id} {side.value} {amount} {symbol} @ {price}")
        return order

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel mock order"""
        await self._simulate_latency()
        await self._simulate_error()
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                order.status = OrderStatus.CANCELLED
                base, quote = self.parse_symbol(order.symbol)
                if order.side == OrderSide.BUY:
                    currency = quote
                    amount = order.remaining * order.price
                else:
                    currency = base
                    amount = order.remaining
                if currency in self.mock_balances:
                    self.mock_balances[currency] = Balance(
                        currency=currency,
                        free=self.mock_balances[currency].free + amount,
                        used=self.mock_balances[currency].used - amount,
                        total=self.mock_balances[currency].total,
                    )
                logger.info(f"Mock order cancelled: {order_id}")
                return True
        return False

    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Order:
        """Get mock order"""
        await self._simulate_latency()
        await self._simulate_error()
        if order_id in self.orders:
            return self.orders[order_id]
        raise Exception(f"Order {order_id} not found")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open mock orders"""
        await self._simulate_latency()
        await self._simulate_error()
        open_orders = [
            order
            for order in self.orders.values()
            if order.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
        ]
        if symbol:
            open_orders = [o for o in open_orders if o.symbol == symbol]
        return open_orders

    async def get_order_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[Order]:
        """Get mock order history"""
        await self._simulate_latency()
        await self._simulate_error()
        orders = list(self.orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        orders.sort(key=lambda x: x.timestamp, reverse=True)
        return orders[:limit]

    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Get mock trades"""
        await self._simulate_latency()
        await self._simulate_error()
        trades = []
        for order in self.orders.values():
            if order.filled > 0:
                if symbol and order.symbol != symbol:
                    continue
                trades.append(
                    Trade(
                        id=f"TRADE-{order.id}",
                        order_id=order.id,
                        symbol=order.symbol,
                        side=order.side,
                        price=order.price,
                        amount=order.filled,
                        fee=order.fee or Decimal(0),
                        fee_currency=order.fee_currency or "USDT",
                        timestamp=order.timestamp,
                    )
                )
        trades.sort(key=lambda x: x.timestamp, reverse=True)
        return trades[:limit]

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Simulate ticker WebSocket stream"""

        async def ticker_generator():
            while True:
                try:
                    await asyncio.sleep(random.uniform(0.5, 2))
                    ticker = await self.get_ticker(symbol)
                    await callback(ticker)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Mock ticker stream error: {e}")

        task = asyncio.create_task(ticker_generator())
        self.ws_tasks.append(task)

    async def subscribe_orderbook(self, symbol: str, callback: Callable):
        """Simulate orderbook WebSocket stream"""

        async def orderbook_generator():
            while True:
                try:
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    orderbook = await self.get_orderbook(symbol, 10)
                    await callback(orderbook)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Mock orderbook stream error: {e}")

        task = asyncio.create_task(orderbook_generator())
        self.ws_tasks.append(task)

    async def subscribe_trades(self, symbol: str, callback: Callable):
        """Simulate trades WebSocket stream"""

        async def trades_generator():
            trade_id = 0
            while True:
                try:
                    await asyncio.sleep(random.uniform(0.5, 3))
                    ticker = await self.get_ticker(symbol)
                    trade_id += 1
                    trade = Trade(
                        id=f"MOCK-TRADE-{trade_id}",
                        order_id="",
                        symbol=symbol,
                        side=random.choice([OrderSide.BUY, OrderSide.SELL]),
                        price=ticker.last,
                        amount=Decimal(str(random.uniform(0.01, 1))),
                        fee=Decimal(0),
                        fee_currency="",
                        timestamp=int(time.time() * 1000),
                    )
                    await callback(trade)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Mock trades stream error: {e}")

        task = asyncio.create_task(trades_generator())
        self.ws_tasks.append(task)

    async def _simulate_latency(self):
        """Simulate network latency"""
        latency = random.uniform(self.min_latency, self.max_latency) / 1000
        await asyncio.sleep(latency)
        self.latency_ms = int(latency * 1000)

    async def _simulate_error(self):
        """Randomly simulate errors"""
        if random.random() < self.fail_rate:
            self.error_count += 1
            raise Exception(f"Simulated error from {self.name}")

    async def _ping_exchange(self):
        """Mock ping"""
        await self._simulate_latency()
