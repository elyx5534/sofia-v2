"""
Data Hub Service - Single source of truth for all market data.

This module provides a unified interface for fetching OHLCV data from multiple sources
with automatic fallback. It serves as the canonical data provider for the entire Sofia platform.

Fallback order: yfinance → Binance → Coinbase → Stooq

Example:
    >>> hub = DataHub()
    >>> data = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-07")
    >>> print(f"Got {len(data)} candles")
    Got 168 candles
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


class DataHub:
    """Multi-source data provider with fallback chain"""

    def __init__(self):
        self.cache_dir = Path(".cache/ohlcv")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=24)
        self.timeout = 10
        self.retry_count = 2

    def get_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> List[List]:
        """
        Get OHLCV data with automatic fallback chain.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT", "ETH/USD", "AAPL")
            timeframe: Candle period ("1m", "5m", "1h", "1d")
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format

        Returns:
            List of OHLCV candles: [[timestamp, open, high, low, close, volume], ...]

        Example:
            >>> hub = DataHub()
            >>> candles = hub.get_ohlcv("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
            >>> for candle in candles[:2]:
            ...     print(f"Time: {candle[0]}, Close: {candle[4]}")
        """
        # Check cache first
        cached_data = self._load_cache(symbol, timeframe, start, end)
        if cached_data is not None:
            logger.info(f"Using cached data for {symbol}")
            return cached_data

        # Try each source in order
        data = None

        # 1. Try yfinance
        try:
            logger.info(f"Trying yfinance for {symbol}")
            data = self._fetch_yfinance(symbol, timeframe, start, end)
            if data:
                logger.info(f"Got data from yfinance: {len(data)} bars")
        except Exception as e:
            logger.warning(f"yfinance failed: {e}")

        # 2. Try Binance
        if not data and "USDT" in symbol.upper():
            try:
                logger.info(f"Trying Binance for {symbol}")
                data = self._fetch_binance(symbol, timeframe, start, end)
                if data:
                    logger.info(f"Got data from Binance: {len(data)} bars")
            except Exception as e:
                logger.warning(f"Binance failed: {e}")

        # 3. Try Coinbase
        if not data and "/" in symbol:
            try:
                logger.info(f"Trying Coinbase for {symbol}")
                data = self._fetch_coinbase(symbol, timeframe, start, end)
                if data:
                    logger.info(f"Got data from Coinbase: {len(data)} bars")
            except Exception as e:
                logger.warning(f"Coinbase failed: {e}")

        # 4. Try Stooq (for stocks)
        if not data and not any(x in symbol.upper() for x in ["USDT", "USD", "BTC", "ETH"]):
            try:
                logger.info(f"Trying Stooq for {symbol}")
                data = self._fetch_stooq(symbol, timeframe, start, end)
                if data:
                    logger.info(f"Got data from Stooq: {len(data)} bars")
            except Exception as e:
                logger.warning(f"Stooq failed: {e}")

        # Cache if we got data
        if data:
            self._save_cache(symbol, timeframe, start, end, data)

        return data or []

    def _fetch_yfinance(self, symbol: str, timeframe: str, start: str, end: str) -> List[List]:
        """Fetch from yfinance"""
        # Convert symbol format
        yf_symbol = symbol.replace("/", "-").replace("USDT", "-USD")
        if "BTC" in yf_symbol and not yf_symbol.startswith("BTC"):
            yf_symbol = "BTC-USD"
        elif "ETH" in yf_symbol and not yf_symbol.startswith("ETH"):
            yf_symbol = "ETH-USD"

        # Convert timeframe
        tf_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "1h",
            "1d": "1d",
            "1w": "1wk",
        }
        yf_interval = tf_map.get(timeframe, "1d")

        # Fetch data
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(start=start, end=end, interval=yf_interval)

        if df.empty:
            return []

        # Convert to standard format
        result = []
        for idx, row in df.iterrows():
            timestamp = int(idx.timestamp() * 1000)
            result.append(
                [
                    timestamp,
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                ]
            )

        return result

    def _fetch_binance(self, symbol: str, timeframe: str, start: str, end: str) -> List[List]:
        """Fetch from Binance public API"""
        # Convert symbol
        binance_symbol = symbol.replace("/", "").replace("-", "")

        # Convert timeframe
        tf_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
        }
        interval = tf_map.get(timeframe, "1d")

        # Convert dates to timestamps
        start_ts = int(datetime.fromisoformat(start).timestamp() * 1000)
        end_ts = int(datetime.fromisoformat(end).timestamp() * 1000)

        # Binance klines endpoint
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1000,
        }

        all_data = []
        while start_ts < end_ts:
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            all_data.extend(data)

            # Update start time for next batch
            if data:
                start_ts = data[-1][0] + 1
                params["startTime"] = start_ts
            else:
                break

        # Convert to standard format
        result = []
        for candle in all_data:
            result.append(
                [
                    int(candle[0]),  # timestamp
                    float(candle[1]),  # open
                    float(candle[2]),  # high
                    float(candle[3]),  # low
                    float(candle[4]),  # close
                    float(candle[5]),  # volume
                ]
            )

        return result

    def _fetch_coinbase(self, symbol: str, timeframe: str, start: str, end: str) -> List[List]:
        """Fetch from Coinbase public API"""
        # Convert symbol
        cb_symbol = symbol.replace("/", "-").replace("USDT", "USD")

        # Convert timeframe to granularity in seconds
        tf_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        granularity = tf_map.get(timeframe, 86400)

        # Coinbase candles endpoint
        url = f"https://api.exchange.coinbase.com/products/{cb_symbol}/candles"
        params = {"start": start, "end": end, "granularity": granularity}

        response = requests.get(url, params=params, timeout=self.timeout)
        if response.status_code != 200:
            return []

        data = response.json()

        # Convert to standard format (Coinbase returns newest first)
        result = []
        for candle in reversed(data):
            result.append(
                [
                    int(candle[0]) * 1000,  # timestamp (convert to ms)
                    float(candle[3]),  # open
                    float(candle[2]),  # high
                    float(candle[1]),  # low
                    float(candle[4]),  # close
                    float(candle[5]),  # volume
                ]
            )

        return result

    def _fetch_stooq(self, symbol: str, timeframe: str, start: str, end: str) -> List[List]:
        """Fetch from Stooq (mainly for stocks)"""
        # Stooq uses different symbol format
        stooq_symbol = symbol.lower()

        # Only daily data from Stooq
        if timeframe not in ["1d", "1w"]:
            return []

        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        response = requests.get(url, timeout=self.timeout)

        if response.status_code != 200:
            return []

        # Parse CSV data
        lines = response.text.strip().split("\n")
        if len(lines) < 2:
            return []

        result = []
        for line in lines[1:]:  # Skip header
            parts = line.split(",")
            if len(parts) >= 6:
                date_str = parts[0]
                dt = datetime.strptime(date_str, "%Y-%m-%d")

                # Filter by date range
                if start <= date_str <= end:
                    timestamp = int(dt.timestamp() * 1000)
                    result.append(
                        [
                            timestamp,
                            float(parts[1]),  # open
                            float(parts[2]),  # high
                            float(parts[3]),  # low
                            float(parts[4]),  # close
                            float(parts[5]),  # volume
                        ]
                    )

        return result

    def _load_cache(
        self, symbol: str, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Load data from cache if exists and not expired"""
        cache_file = self.cache_dir / f"{symbol}_{timeframe}_{start}_{end}.parquet".replace(
            "/", "_"
        )

        if not cache_file.exists():
            return None

        # Check if cache is expired
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age > self.cache_ttl:
            cache_file.unlink()  # Delete expired cache
            return None

        try:
            # Read parquet file
            table = pq.read_table(cache_file)
            df = table.to_pandas()

            # Convert to list format
            result = []
            for _, row in df.iterrows():
                result.append(
                    [
                        int(row["timestamp"]),
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume"]),
                    ]
                )
            return result
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def _save_cache(self, symbol: str, timeframe: str, start: str, end: str, data: List[List]):
        """Save data to cache"""
        if not data:
            return

        cache_file = self.cache_dir / f"{symbol}_{timeframe}_{start}_{end}.parquet".replace(
            "/", "_"
        )

        try:
            # Convert to DataFrame
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])

            # Save as parquet
            table = pa.Table.from_pandas(df)
            pq.write_table(table, cache_file)

            logger.info(f"Cached {len(data)} bars to {cache_file}")
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def get_latest_price(self, symbol: str) -> Dict:
        """Get latest price for a symbol"""
        # Try to get last 1 day of 1m data
        end = datetime.now().isoformat()
        start = (datetime.now() - timedelta(days=1)).isoformat()

        data = self.get_ohlcv(symbol, "1m", start, end)

        if data:
            latest = data[-1]
            return {
                "symbol": symbol,
                "price": latest[4],  # close price
                "timestamp": latest[0],
                "volume": latest[5],
            }
        else:
            # Fallback to a simple ticker request
            return self._fetch_ticker(symbol)

    def _fetch_ticker(self, symbol: str) -> Dict:
        """Quick ticker fetch from Binance"""
        try:
            binance_symbol = symbol.replace("/", "").replace("-", "")
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return {
                    "symbol": symbol,
                    "price": float(data["price"]),
                    "timestamp": int(time.time() * 1000),
                    "volume": 0,
                }
        except:
            pass

        return {"symbol": symbol, "price": 0, "timestamp": int(time.time() * 1000), "volume": 0}


# Global instance
datahub = DataHub()
