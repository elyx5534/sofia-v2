"""
Binance Exchange Implementation
Supports both Spot and Futures trading
"""

import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import ccxt.pro as ccxt
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


class BinanceExchange(BaseExchange):
    """Binance exchange connector with WebSocket support"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.exchange_type = config.get("type", "spot")  # spot or future

        # Initialize CCXT exchange
        exchange_config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": self.exchange_type,
                "adjustForTimeDifference": True,
            },
        }

        if self.testnet:
            exchange_config["urls"] = {
                "api": {
                    "public": "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                },
            }

        self.exchange = ccxt.binance(exchange_config)
        self.ws_subscriptions = set()

    async def connect(self) -> bool:
        """Connect to Binance API"""
        try:
            self.status = ExchangeStatus.CONNECTING

            # Test connection
            await self.exchange.load_markets()

            # Get account info to verify credentials
            if self.api_key and self.api_secret:
                balance = await self.exchange.fetch_balance()
                logger.info(
                    f"Binance connected. Account has {len(balance['info']['balances'])} assets"
                )

            self.status = ExchangeStatus.CONNECTED
            return True

        except Exception as e:
            logger.error(f"Binance connection failed: {e}")
            self.status = ExchangeStatus.ERROR
            self.error_count += 1
            return False

    async def disconnect(self):
        """Disconnect from Binance"""
        try:
            await self.exchange.close()
            self.status = ExchangeStatus.DISCONNECTED
            logger.info("Binance disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Binance: {e}")

    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, Balance]:
        """Get account balance"""
        try:
            await self.rate_limiter.acquire()

            raw_balance = await self.exchange.fetch_balance()
            balances = {}

            for curr, info in raw_balance["total"].items():
                if info > 0:  # Only return non-zero balances
                    if currency and curr != currency:
                        continue

                    balances[curr] = Balance(
                        currency=curr,
                        free=Decimal(str(raw_balance["free"].get(curr, 0))),
                        used=Decimal(str(raw_balance["used"].get(curr, 0))),
                        total=Decimal(str(info)),
                    )

            self.balance_cache = balances
            return balances

        except Exception as e:
            logger.error(f"Failed to get Binance balance: {e}")
            self.error_count += 1
            raise

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for symbol"""
        try:
            await self.rate_limiter.acquire()

            ticker = await self.exchange.fetch_ticker(symbol)

            result = Ticker(
                symbol=symbol,
                timestamp=ticker["timestamp"],
                bid=Decimal(str(ticker["bid"])) if ticker["bid"] else Decimal(0),
                ask=Decimal(str(ticker["ask"])) if ticker["ask"] else Decimal(0),
                last=Decimal(str(ticker["last"])),
                volume_24h=Decimal(str(ticker["baseVolume"])),
                change_24h=Decimal(str(ticker["percentage"])),
                high_24h=Decimal(str(ticker["high"])) if ticker["high"] else Decimal(0),
                low_24h=Decimal(str(ticker["low"])) if ticker["low"] else Decimal(0),
                vwap=Decimal(str(ticker["vwap"])) if ticker.get("vwap") else None,
            )

            self.ticker_cache[symbol] = result
            return result

        except Exception as e:
            logger.error(f"Failed to get Binance ticker {symbol}: {e}")
            self.error_count += 1
            raise

    async def get_orderbook(self, symbol: str, limit: int = 20) -> OrderBook:
        """Get order book for symbol"""
        try:
            await self.rate_limiter.acquire()

            orderbook = await self.exchange.fetch_order_book(symbol, limit)

            result = OrderBook(
                symbol=symbol,
                timestamp=orderbook["timestamp"],
                bids=[
                    [Decimal(str(price)), Decimal(str(amount))]
                    for price, amount in orderbook["bids"]
                ],
                asks=[
                    [Decimal(str(price)), Decimal(str(amount))]
                    for price, amount in orderbook["asks"]
                ],
            )

            self.orderbook_cache[symbol] = result
            return result

        except Exception as e:
            logger.error(f"Failed to get Binance orderbook {symbol}: {e}")
            self.error_count += 1
            raise

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: Decimal,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> Order:
        """Place an order on Binance"""
        try:
            await self.rate_limiter.acquire(weight=2)

            # Convert to CCXT format
            ccxt_side = side.value
            ccxt_type = order_type.value

            params = {}
            if order_type == OrderType.STOP_LOSS:
                ccxt_type = "stop_loss_limit" if price else "stop_loss"
                params["stopPrice"] = kwargs.get("stop_price", price)

            # Place order
            if order_type == OrderType.MARKET:
                result = await self.exchange.create_order(
                    symbol, ccxt_type, ccxt_side, float(amount), params=params
                )
            else:
                result = await self.exchange.create_order(
                    symbol, ccxt_type, ccxt_side, float(amount), float(price), params=params
                )

            # Parse response
            order = Order(
                id=result["id"],
                exchange=self.name,
                symbol=symbol,
                type=order_type,
                side=side,
                price=Decimal(str(result.get("price", 0))) if result.get("price") else None,
                amount=Decimal(str(result["amount"])),
                filled=Decimal(str(result.get("filled", 0))),
                status=self._parse_order_status(result["status"]),
                timestamp=result["timestamp"],
                fee=Decimal(str(result["fee"]["cost"])) if result.get("fee") else None,
                fee_currency=result["fee"]["currency"] if result.get("fee") else None,
                client_order_id=result.get("clientOrderId"),
            )

            logger.info(f"Binance order placed: {order.id} {side.value} {amount} {symbol}")
            return order

        except Exception as e:
            logger.error(f"Failed to place Binance order: {e}")
            self.error_count += 1
            raise

    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an order"""
        try:
            await self.rate_limiter.acquire()

            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Binance order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel Binance order {order_id}: {e}")
            self.error_count += 1
            return False

    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Order:
        """Get order status"""
        try:
            await self.rate_limiter.acquire()

            result = await self.exchange.fetch_order(order_id, symbol)

            return Order(
                id=result["id"],
                exchange=self.name,
                symbol=result["symbol"],
                type=OrderType(result["type"]),
                side=OrderSide(result["side"]),
                price=Decimal(str(result["price"])) if result["price"] else None,
                amount=Decimal(str(result["amount"])),
                filled=Decimal(str(result["filled"])),
                status=self._parse_order_status(result["status"]),
                timestamp=result["timestamp"],
                fee=Decimal(str(result["fee"]["cost"])) if result.get("fee") else None,
                fee_currency=result["fee"]["currency"] if result.get("fee") else None,
            )

        except Exception as e:
            logger.error(f"Failed to get Binance order {order_id}: {e}")
            self.error_count += 1
            raise

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders"""
        try:
            await self.rate_limiter.acquire()

            orders = await self.exchange.fetch_open_orders(symbol)

            return [
                Order(
                    id=o["id"],
                    exchange=self.name,
                    symbol=o["symbol"],
                    type=OrderType(o["type"]),
                    side=OrderSide(o["side"]),
                    price=Decimal(str(o["price"])) if o["price"] else None,
                    amount=Decimal(str(o["amount"])),
                    filled=Decimal(str(o["filled"])),
                    status=self._parse_order_status(o["status"]),
                    timestamp=o["timestamp"],
                )
                for o in orders
            ]

        except Exception as e:
            logger.error(f"Failed to get Binance open orders: {e}")
            self.error_count += 1
            raise

    async def get_order_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[Order]:
        """Get order history"""
        try:
            await self.rate_limiter.acquire()

            orders = await self.exchange.fetch_closed_orders(symbol, limit=limit)

            return [
                Order(
                    id=o["id"],
                    exchange=self.name,
                    symbol=o["symbol"],
                    type=OrderType(o["type"]),
                    side=OrderSide(o["side"]),
                    price=Decimal(str(o["price"])) if o["price"] else None,
                    amount=Decimal(str(o["amount"])),
                    filled=Decimal(str(o["filled"])),
                    status=self._parse_order_status(o["status"]),
                    timestamp=o["timestamp"],
                    fee=Decimal(str(o["fee"]["cost"])) if o.get("fee") else None,
                    fee_currency=o["fee"]["currency"] if o.get("fee") else None,
                )
                for o in orders
            ]

        except Exception as e:
            logger.error(f"Failed to get Binance order history: {e}")
            self.error_count += 1
            raise

    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Get trade history"""
        try:
            await self.rate_limiter.acquire()

            trades = await self.exchange.fetch_my_trades(symbol, limit=limit)

            return [
                Trade(
                    id=t["id"],
                    order_id=t["order"],
                    symbol=t["symbol"],
                    side=OrderSide(t["side"]),
                    price=Decimal(str(t["price"])),
                    amount=Decimal(str(t["amount"])),
                    fee=Decimal(str(t["fee"]["cost"])) if t.get("fee") else Decimal(0),
                    fee_currency=t["fee"]["currency"] if t.get("fee") else "USDT",
                    timestamp=t["timestamp"],
                )
                for t in trades
            ]

        except Exception as e:
            logger.error(f"Failed to get Binance trades: {e}")
            self.error_count += 1
            raise

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to ticker updates via WebSocket"""
        try:
            self.ws_subscriptions.add(("ticker", symbol))

            while symbol in [s for t, s in self.ws_subscriptions if t == "ticker"]:
                ticker = await self.exchange.watch_ticker(symbol)

                # Convert to our format
                formatted_ticker = Ticker(
                    symbol=symbol,
                    timestamp=ticker["timestamp"],
                    bid=Decimal(str(ticker["bid"])) if ticker["bid"] else Decimal(0),
                    ask=Decimal(str(ticker["ask"])) if ticker["ask"] else Decimal(0),
                    last=Decimal(str(ticker["last"])),
                    volume_24h=Decimal(str(ticker["baseVolume"])),
                    change_24h=Decimal(str(ticker["percentage"])),
                    high_24h=Decimal(str(ticker["high"])) if ticker["high"] else Decimal(0),
                    low_24h=Decimal(str(ticker["low"])) if ticker["low"] else Decimal(0),
                )

                await callback(formatted_ticker)

        except Exception as e:
            logger.error(f"Binance ticker subscription error: {e}")
            self.ws_subscriptions.discard(("ticker", symbol))

    async def subscribe_orderbook(self, symbol: str, callback: Callable):
        """Subscribe to order book updates via WebSocket"""
        try:
            self.ws_subscriptions.add(("orderbook", symbol))

            while symbol in [s for t, s in self.ws_subscriptions if t == "orderbook"]:
                orderbook = await self.exchange.watch_order_book(symbol)

                # Convert to our format
                formatted_orderbook = OrderBook(
                    symbol=symbol,
                    timestamp=orderbook["timestamp"],
                    bids=[
                        [Decimal(str(price)), Decimal(str(amount))]
                        for price, amount in orderbook["bids"][:20]
                    ],
                    asks=[
                        [Decimal(str(price)), Decimal(str(amount))]
                        for price, amount in orderbook["asks"][:20]
                    ],
                )

                await callback(formatted_orderbook)

        except Exception as e:
            logger.error(f"Binance orderbook subscription error: {e}")
            self.ws_subscriptions.discard(("orderbook", symbol))

    async def subscribe_trades(self, symbol: str, callback: Callable):
        """Subscribe to trade updates via WebSocket"""
        try:
            self.ws_subscriptions.add(("trades", symbol))

            while symbol in [s for t, s in self.ws_subscriptions if t == "trades"]:
                trades = await self.exchange.watch_trades(symbol)

                for trade in trades:
                    formatted_trade = Trade(
                        id=trade["id"],
                        order_id=trade.get("order", ""),
                        symbol=symbol,
                        side=OrderSide(trade["side"]),
                        price=Decimal(str(trade["price"])),
                        amount=Decimal(str(trade["amount"])),
                        fee=Decimal(0),  # Public trades don't have fee info
                        fee_currency="",
                        timestamp=trade["timestamp"],
                    )

                    await callback(formatted_trade)

        except Exception as e:
            logger.error(f"Binance trades subscription error: {e}")
            self.ws_subscriptions.discard(("trades", symbol))

    async def _ping_exchange(self):
        """Binance-specific ping implementation"""
        await self.exchange.fetch_time()

    def _parse_order_status(self, status: str) -> OrderStatus:
        """Parse CCXT order status to our format"""
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
        }
        return status_map.get(status.lower(), OrderStatus.PENDING)
