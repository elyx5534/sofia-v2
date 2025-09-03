"""
Real-Time Crypto Data Fetcher
Fetches real crypto prices from public APIs without API keys
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class RealTimeDataFetcher:
    """Fetches real crypto data from multiple sources"""

    def __init__(self):
        self.session = None
        self.cache = {}
        self.last_update = {}
        self.endpoints = {
            "coingecko": "https://api.coingecko.com/api/v3",
            "binance": "https://api.binance.com/api/v3",
            "coinbase": "https://api.exchange.coinbase.com",
            "kraken": "https://api.kraken.com/0/public",
        }

    async def start(self):
        """Initialize session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def stop(self):
        """Close session"""
        if self.session:
            await self.session.close()

    async def get_price(self, symbol: str, vs_currency: str = "usd") -> Optional[float]:
        """Get current price for a symbol"""
        try:
            url = f"{self.endpoints['coingecko']}/simple/price"
            params = {
                "ids": symbol.lower(),
                "vs_currencies": vs_currency.lower(),
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            }
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if symbol.lower() in data:
                        return data[symbol.lower()][vs_currency.lower()]
            binance_symbol = f"{symbol.upper()}USDT"
            url = f"{self.endpoints['binance']}/ticker/price"
            params = {"symbol": binance_symbol}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data["price"])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    async def get_market_data(self, symbols: List[str]) -> Dict:
        """Get market data for multiple symbols"""
        await self.start()
        market_data = {}
        try:
            ids = ",".join([s.lower() for s in symbols])
            url = f"{self.endpoints['coingecko']}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ids,
                "order": "market_cap_desc",
                "sparkline": "true",
                "price_change_percentage": "1h,24h,7d",
            }
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for coin in data:
                        market_data[coin["symbol"].upper()] = {
                            "price": coin["current_price"],
                            "market_cap": coin["market_cap"],
                            "volume_24h": coin["total_volume"],
                            "change_24h": coin["price_change_percentage_24h"],
                            "change_7d": coin.get("price_change_percentage_7d_in_currency", 0),
                            "high_24h": coin["high_24h"],
                            "low_24h": coin["low_24h"],
                            "sparkline": coin.get("sparkline_in_7d", {}).get("price", [])[-24:],
                            "last_updated": datetime.now(timezone.utc).isoformat(),
                        }
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
        return market_data

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book data"""
        try:
            binance_symbol = f"{symbol.upper()}USDT"
            url = f"{self.endpoints['binance']}/depth"
            params = {"symbol": binance_symbol, "limit": limit}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "bids": [[float(p), float(q)] for p, q in data["bids"]],
                        "asks": [[float(p), float(q)] for p, q in data["asks"]],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return {"bids": [], "asks": [], "timestamp": datetime.now(timezone.utc).isoformat()}

    async def get_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        try:
            binance_symbol = f"{symbol.upper()}USDT"
            url = f"{self.endpoints['binance']}/trades"
            params = {"symbol": binance_symbol, "limit": limit}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = []
                    for trade in data:
                        trades.append(
                            {
                                "price": float(trade["price"]),
                                "quantity": float(trade["qty"]),
                                "time": datetime.fromtimestamp(
                                    trade["time"] / 1000, tz=timezone.utc
                                ).isoformat(),
                                "is_buyer": trade["isBuyerMaker"],
                            }
                        )
                    return trades
        except Exception as e:
            logger.error(f"Error fetching trades for {symbol}: {e}")
            return []

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
        """Get candlestick data"""
        try:
            binance_symbol = f"{symbol.upper()}USDT"
            url = f"{self.endpoints['binance']}/klines"
            params = {"symbol": binance_symbol, "interval": interval, "limit": limit}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    klines = []
                    for k in data:
                        klines.append(
                            {
                                "time": datetime.fromtimestamp(
                                    k[0] / 1000, tz=timezone.utc
                                ).isoformat(),
                                "open": float(k[1]),
                                "high": float(k[2]),
                                "low": float(k[3]),
                                "close": float(k[4]),
                                "volume": float(k[5]),
                            }
                        )
                    return klines
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []

    async def get_top_gainers_losers(self, limit: int = 10) -> Dict:
        """Get top gainers and losers"""
        try:
            url = f"{self.endpoints['coingecko']}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "price_change_percentage": "24h",
            }
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    sorted_data = sorted(
                        data,
                        key=lambda x: x.get("price_change_percentage_24h", 0) or 0,
                        reverse=True,
                    )
                    gainers = []
                    losers = []
                    for coin in sorted_data[:limit]:
                        if coin.get("price_change_percentage_24h", 0) > 0:
                            gainers.append(
                                {
                                    "symbol": coin["symbol"].upper(),
                                    "name": coin["name"],
                                    "price": coin["current_price"],
                                    "change_24h": coin["price_change_percentage_24h"],
                                    "volume": coin["total_volume"],
                                }
                            )
                    for coin in sorted_data[-limit:]:
                        if coin.get("price_change_percentage_24h", 0) < 0:
                            losers.append(
                                {
                                    "symbol": coin["symbol"].upper(),
                                    "name": coin["name"],
                                    "price": coin["current_price"],
                                    "change_24h": coin["price_change_percentage_24h"],
                                    "volume": coin["total_volume"],
                                }
                            )
                    return {"gainers": gainers, "losers": losers}
        except Exception as e:
            logger.error(f"Error fetching top gainers/losers: {e}")
            return {"gainers": [], "losers": []}

    async def stream_prices(self, symbols: List[str], callback):
        """Stream real-time prices"""
        await self.start()
        while True:
            try:
                market_data = await self.get_market_data(symbols)
                if market_data:
                    await callback(market_data)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error in price stream: {e}")
                await asyncio.sleep(5)


fetcher = RealTimeDataFetcher()
