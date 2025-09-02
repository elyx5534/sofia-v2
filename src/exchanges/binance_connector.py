"""
Binance Exchange Connector - Real API Integration

Features:
- Spot trading
- Futures trading
- WebSocket streams
- Order management
- Account management
"""

import asyncio
import hashlib
import hmac
import json
import time
from typing import Dict, List, Optional

import httpx
import websockets
from pydantic import BaseModel


class BinanceConfig(BaseModel):
    """Binance configuration."""

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True  # Start with testnet
    base_url: str = "https://testnet.binance.vision"
    ws_url: str = "wss://testnet.binance.vision/ws"
    futures_url: str = "https://testnet.binancefuture.com"


class BinanceOrder(BaseModel):
    """Binance order structure."""

    symbol: str
    side: str  # BUY, SELL
    type: str  # LIMIT, MARKET, STOP_LOSS_LIMIT
    quantity: float
    price: Optional[float] = None
    timeInForce: Optional[str] = "GTC"  # GTC, IOC, FOK
    stopPrice: Optional[float] = None


class BinanceConnector:
    """
    Binance exchange connector for real trading.

    Supports:
    - Spot trading
    - Futures trading
    - WebSocket market data
    - Account management
    """

    def __init__(self, config: BinanceConfig):
        """Initialize Binance connector."""
        self.config = config
        self.client = httpx.AsyncClient()
        self.ws_connection = None
        self.listen_key = None
        self.is_connected = False

        # Update URLs based on testnet/mainnet
        if not config.testnet:
            self.config.base_url = "https://api.binance.com"
            self.config.ws_url = "wss://stream.binance.com:9443/ws"
            self.config.futures_url = "https://fapi.binance.com"

    async def connect(self) -> bool:
        """Connect to Binance."""
        try:
            # Test connectivity
            response = await self.client.get(f"{self.config.base_url}/api/v3/ping")
            if response.status_code == 200:
                self.is_connected = True

                # Get listen key for user data stream
                if self.config.api_key:
                    await self._get_listen_key()

                return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if self.ws_connection:
            await self.ws_connection.close()
        await self.client.aclose()
        self.is_connected = False

    # === Market Data ===

    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data for a symbol."""
        response = await self.client.get(
            f"{self.config.base_url}/api/v3/ticker/24hr", params={"symbol": symbol}
        )
        return response.json()

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        """Get order book for a symbol."""
        response = await self.client.get(
            f"{self.config.base_url}/api/v3/depth", params={"symbol": symbol, "limit": limit}
        )
        return response.json()

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[List]:
        """Get kline/candlestick data."""
        response = await self.client.get(
            f"{self.config.base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        return response.json()

    async def get_exchange_info(self) -> Dict:
        """Get exchange trading rules and symbol information."""
        response = await self.client.get(f"{self.config.base_url}/api/v3/exchangeInfo")
        return response.json()

    # === Account Management ===

    async def get_account(self) -> Dict:
        """Get account information."""
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        params["signature"] = self._sign(params)

        response = await self.client.get(
            f"{self.config.base_url}/api/v3/account",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def get_balance(self) -> Dict[str, float]:
        """Get account balances."""
        account = await self.get_account()
        balances = {}

        for asset in account.get("balances", []):
            free = float(asset["free"])
            locked = float(asset["locked"])
            if free > 0 or locked > 0:
                balances[asset["asset"]] = {"free": free, "locked": locked, "total": free + locked}

        return balances

    # === Order Management ===

    async def place_order(self, order: BinanceOrder) -> Dict:
        """Place a new order."""
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.type,
            "quantity": order.quantity,
            "timestamp": timestamp,
        }

        if order.price:
            params["price"] = order.price

        if order.timeInForce:
            params["timeInForce"] = order.timeInForce

        if order.stopPrice:
            params["stopPrice"] = order.stopPrice

        params["signature"] = self._sign(params)

        response = await self.client.post(
            f"{self.config.base_url}/api/v3/order",
            data=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an order."""
        timestamp = int(time.time() * 1000)
        params = {"symbol": symbol, "orderId": order_id, "timestamp": timestamp}
        params["signature"] = self._sign(params)

        response = await self.client.delete(
            f"{self.config.base_url}/api/v3/order",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def get_order(self, symbol: str, order_id: int) -> Dict:
        """Get order status."""
        timestamp = int(time.time() * 1000)
        params = {"symbol": symbol, "orderId": order_id, "timestamp": timestamp}
        params["signature"] = self._sign(params)

        response = await self.client.get(
            f"{self.config.base_url}/api/v3/order",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders."""
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        if symbol:
            params["symbol"] = symbol

        params["signature"] = self._sign(params)

        response = await self.client.get(
            f"{self.config.base_url}/api/v3/openOrders",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def get_all_orders(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Get all orders for a symbol."""
        timestamp = int(time.time() * 1000)
        params = {"symbol": symbol, "limit": limit, "timestamp": timestamp}
        params["signature"] = self._sign(params)

        response = await self.client.get(
            f"{self.config.base_url}/api/v3/allOrders",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    # === WebSocket Streams ===

    async def subscribe_ticker(self, symbol: str, callback) -> None:
        """Subscribe to ticker updates."""
        stream = f"{symbol.lower()}@ticker"
        await self._subscribe_stream(stream, callback)

    async def subscribe_kline(self, symbol: str, interval: str, callback) -> None:
        """Subscribe to kline updates."""
        stream = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe_stream(stream, callback)

    async def subscribe_depth(self, symbol: str, callback) -> None:
        """Subscribe to order book updates."""
        stream = f"{symbol.lower()}@depth"
        await self._subscribe_stream(stream, callback)

    async def subscribe_trades(self, symbol: str, callback) -> None:
        """Subscribe to trade updates."""
        stream = f"{symbol.lower()}@trade"
        await self._subscribe_stream(stream, callback)

    async def subscribe_user_data(self, callback) -> None:
        """Subscribe to user data stream (orders, balances)."""
        if not self.listen_key:
            await self._get_listen_key()

        ws_url = f"{self.config.ws_url}/{self.listen_key}"

        async with websockets.connect(ws_url) as websocket:
            self.ws_connection = websocket

            # Keep alive task
            asyncio.create_task(self._keep_alive_listen_key())

            async for message in websocket:
                data = json.loads(message)
                await callback(data)

    async def _subscribe_stream(self, stream: str, callback) -> None:
        """Subscribe to a WebSocket stream."""
        ws_url = f"{self.config.ws_url}/{stream}"

        async with websockets.connect(ws_url) as websocket:
            async for message in websocket:
                data = json.loads(message)
                await callback(data)

    async def _get_listen_key(self) -> None:
        """Get listen key for user data stream."""
        response = await self.client.post(
            f"{self.config.base_url}/api/v3/userDataStream",
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        data = response.json()
        self.listen_key = data.get("listenKey")

    async def _keep_alive_listen_key(self) -> None:
        """Keep listen key alive."""
        while self.listen_key:
            await asyncio.sleep(1800)  # 30 minutes

            await self.client.put(
                f"{self.config.base_url}/api/v3/userDataStream",
                params={"listenKey": self.listen_key},
                headers={"X-MBX-APIKEY": self.config.api_key},
            )

    # === Futures Trading ===

    async def get_futures_account(self) -> Dict:
        """Get futures account information."""
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        params["signature"] = self._sign(params)

        response = await self.client.get(
            f"{self.config.futures_url}/fapi/v2/account",
            params=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    async def place_futures_order(self, order: BinanceOrder) -> Dict:
        """Place a futures order."""
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.type,
            "quantity": order.quantity,
            "timestamp": timestamp,
        }

        if order.price:
            params["price"] = order.price

        params["signature"] = self._sign(params)

        response = await self.client.post(
            f"{self.config.futures_url}/fapi/v1/order",
            data=params,
            headers={"X-MBX-APIKEY": self.config.api_key},
        )
        return response.json()

    # === Utility Methods ===

    def _sign(self, params: Dict) -> str:
        """Sign request with API secret."""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.config.api_secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    async def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            response = await self.client.get(f"{self.config.base_url}/api/v3/ping")
            return response.status_code == 200
        except:
            return False

    async def get_server_time(self) -> int:
        """Get Binance server time."""
        response = await self.client.get(f"{self.config.base_url}/api/v3/time")
        return response.json()["serverTime"]

    async def get_system_status(self) -> Dict:
        """Get system status."""
        response = await self.client.get("https://api.binance.com/sapi/v1/system/status")
        return response.json()
