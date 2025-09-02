"""
Binance Real-Time Data Provider
Direct integration with Binance public API
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class BinanceDataProvider:
    """Real-time data from Binance public API (no API key needed)"""

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self.session = None
        self.prices = {}
        self.klines = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            # Convert format if needed (BTC/USDT -> BTCUSDT)
            binance_symbol = symbol.replace("/", "").replace("-", "")

            async with self.session.get(
                f"{self.BASE_URL}/ticker/price?symbol={binance_symbol}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    self.prices[symbol] = price
                    return price
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        return None

    async def get_all_prices(self) -> Dict[str, float]:
        """Get all current prices"""
        try:
            async with self.session.get(f"{self.BASE_URL}/ticker/price") as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    for item in data:
                        # Convert BTCUSDT to BTC/USDT format
                        if item["symbol"].endswith("USDT"):
                            base = item["symbol"][:-4]
                            symbol = f"{base}/USDT"
                            prices[symbol] = float(item["price"])
                    self.prices.update(prices)
                    return prices
        except Exception as e:
            logger.error(f"Error fetching all prices: {e}")
        return {}

    async def get_24hr_stats(self, symbol: str) -> Optional[Dict]:
        """Get 24hr statistics for a symbol"""
        try:
            binance_symbol = symbol.replace("/", "").replace("-", "")

            async with self.session.get(
                f"{self.BASE_URL}/ticker/24hr?symbol={binance_symbol}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "symbol": symbol,
                        "price": float(data["lastPrice"]),
                        "change_24h": float(data["priceChange"]),
                        "change_pct_24h": float(data["priceChangePercent"]),
                        "volume_24h": float(data["volume"]),
                        "high_24h": float(data["highPrice"]),
                        "low_24h": float(data["lowPrice"]),
                        "trades_24h": int(data["count"]),
                    }
        except Exception as e:
            logger.error(f"Error fetching 24hr stats for {symbol}: {e}")
        return None

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Dict]:
        """
        Get historical klines/candlestick data
        Intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        """
        try:
            binance_symbol = symbol.replace("/", "").replace("-", "")

            async with self.session.get(
                f"{self.BASE_URL}/klines",
                params={"symbol": binance_symbol, "interval": interval, "limit": limit},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    klines = []
                    for k in data:
                        klines.append(
                            {
                                "timestamp": k[0],
                                "open": float(k[1]),
                                "high": float(k[2]),
                                "low": float(k[3]),
                                "close": float(k[4]),
                                "volume": float(k[5]),
                                "close_time": k[6],
                                "quote_volume": float(k[7]),
                                "trades": k[8],
                                "taker_buy_volume": float(k[9]),
                                "taker_buy_quote": float(k[10]),
                            }
                        )
                    self.klines[symbol] = klines
                    return klines
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
        return []

    async def get_order_book(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        """Get order book depth"""
        try:
            binance_symbol = symbol.replace("/", "").replace("-", "")

            async with self.session.get(
                f"{self.BASE_URL}/depth", params={"symbol": binance_symbol, "limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "bids": [[float(p), float(q)] for p, q in data["bids"]],
                        "asks": [[float(p), float(q)] for p, q in data["asks"]],
                        "lastUpdateId": data["lastUpdateId"],
                    }
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
        return None

    async def get_recent_trades(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Get recent trades"""
        try:
            binance_symbol = symbol.replace("/", "").replace("-", "")

            async with self.session.get(
                f"{self.BASE_URL}/trades", params={"symbol": binance_symbol, "limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = []
                    for t in data:
                        trades.append(
                            {
                                "id": t["id"],
                                "price": float(t["price"]),
                                "qty": float(t["qty"]),
                                "quoteQty": float(t["quoteQty"]),
                                "time": t["time"],
                                "isBuyerMaker": t["isBuyerMaker"],
                                "isBestMatch": t["isBestMatch"],
                            }
                        )
                    return trades
        except Exception as e:
            logger.error(f"Error fetching recent trades for {symbol}: {e}")
        return []

    async def stream_prices(self, symbols: List[str], callback):
        """Stream real-time prices using WebSocket"""
        import websockets

        # Convert symbols to Binance format
        streams = []
        for symbol in symbols:
            binance_symbol = symbol.replace("/", "").replace("-", "").lower()
            streams.append(f"{binance_symbol}@ticker")

        stream_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"

        try:
            async with websockets.connect(stream_url) as websocket:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if "data" in data:
                        stream_data = data["data"]
                        if "s" in stream_data:  # Symbol
                            # Convert BTCUSDT to BTC/USDT
                            symbol = stream_data["s"]
                            if symbol.endswith("USDT"):
                                base = symbol[:-4]
                                formatted_symbol = f"{base}/USDT"

                                price_data = {
                                    "symbol": formatted_symbol,
                                    "price": float(stream_data["c"]),  # Current price
                                    "bid": float(stream_data["b"]),  # Best bid
                                    "ask": float(stream_data["a"]),  # Best ask
                                    "volume": float(stream_data["v"]),  # Volume
                                    "high": float(stream_data["h"]),  # High
                                    "low": float(stream_data["l"]),  # Low
                                    "change_pct": float(stream_data["P"]),  # Change percent
                                }

                                await callback(price_data)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")


# Example usage
async def main():
    async with BinanceDataProvider() as provider:
        # Get single price
        price = await provider.get_price("BTC/USDT")
        print(f"BTC Price: ${price}")

        # Get 24hr stats
        stats = await provider.get_24hr_stats("ETH/USDT")
        if stats:
            print(f"ETH 24hr Stats: {stats}")

        # Get historical data
        klines = await provider.get_klines("SOL/USDT", "5m", 10)
        if klines:
            print(f"SOL Latest Close: ${klines[-1]['close']}")


if __name__ == "__main__":
    asyncio.run(main())
