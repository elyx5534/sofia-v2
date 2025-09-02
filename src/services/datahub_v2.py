"""
Multi-Market DataHub v2
Crypto + Stock data with fallback chain and caching
"""

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytz
import requests
import yfinance as yf
from src.services.symbols import Asset, AssetType, symbol_registry

logger = logging.getLogger(__name__)


class MarketCalendar:
    """Market hours and timezone handling"""

    MARKET_HOURS = {
        "NASDAQ": {"tz": "America/New_York", "open": "09:30", "close": "16:00"},
        "NYSE": {"tz": "America/New_York", "open": "09:30", "close": "16:00"},
        "BIST": {"tz": "Europe/Istanbul", "open": "10:00", "close": "18:00"},
        "FOREX": {"tz": "UTC", "open": "00:00", "close": "23:59"},
        "BINANCE": {"tz": "UTC", "open": "00:00", "close": "23:59"},
        "BTCTURK": {"tz": "Europe/Istanbul", "open": "00:00", "close": "23:59"},
    }

    @classmethod
    def get_market_tz(cls, venue: str) -> timezone:
        """Get timezone for a venue"""
        market = cls.MARKET_HOURS.get(venue, cls.MARKET_HOURS["FOREX"])
        return pytz.timezone(market["tz"])

    @classmethod
    def to_utc(cls, dt: datetime, venue: str) -> datetime:
        """Convert venue local time to UTC"""
        if dt.tzinfo is None:
            tz = cls.get_market_tz(venue)
            dt = tz.localize(dt)
        return dt.astimezone(pytz.UTC)

    @classmethod
    def is_market_open(cls, venue: str, dt: Optional[datetime] = None) -> bool:
        """Check if market is open"""
        if venue in ["BINANCE", "FOREX", "BTCTURK"]:
            return True  # 24/7 markets

        if dt is None:
            dt = datetime.now(pytz.UTC)

        market = cls.MARKET_HOURS.get(venue)
        if not market:
            return True

        # Convert to market timezone
        tz = pytz.timezone(market["tz"])
        local_dt = dt.astimezone(tz)

        # Check weekday (0=Monday, 6=Sunday)
        if local_dt.weekday() >= 5:  # Weekend
            return False

        # Check time
        open_time = datetime.strptime(market["open"], "%H:%M").time()
        close_time = datetime.strptime(market["close"], "%H:%M").time()

        return open_time <= local_dt.time() <= close_time


class DataHubV2:
    """Enhanced multi-market data provider"""

    def __init__(self):
        self.cache_dir = Path(".cache/ohlcv")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=24)
        self.timeout = 10
        self.retry_count = 2
        self.cache_hits = 0
        self.cache_misses = 0
        self.source_latencies = {}

        # Environment toggles
        self.disable_yf = os.getenv("DISABLE_YF", "").lower() == "true"
        self.force_binance = os.getenv("FORCE_BINANCE", "").lower() == "true"
        self.force_coinbase = os.getenv("FORCE_COINBASE", "").lower() == "true"

    def get_ohlcv(
        self, asset: str, timeframe: str, start: str, end: str, adjust_corporate: bool = True
    ) -> List[List]:
        """
        Get OHLCV data with fallback chain
        Returns: [[timestamp_ms, open, high, low, close, volume], ...]
        All timestamps in UTC milliseconds
        """
        # Parse asset
        asset_obj = symbol_registry.parse(asset)
        if not asset_obj:
            logger.error(f"Unknown asset: {asset}")
            return []

        # Check cache first
        cache_key = self._get_cache_key(asset_obj, timeframe, start, end)
        cached_data = self._load_cache(cache_key)
        if cached_data is not None:
            self.cache_hits += 1
            logger.info(f"Cache hit for {asset}")
            return cached_data

        self.cache_misses += 1
        data = None

        # Fallback chain based on asset type
        if asset_obj.type == AssetType.CRYPTO:
            data = self._fetch_crypto_data(asset_obj, timeframe, start, end)
        elif asset_obj.type == AssetType.STOCK:
            data = self._fetch_stock_data(asset_obj, timeframe, start, end, adjust_corporate)
        elif asset_obj.type == AssetType.FOREX:
            data = self._fetch_forex_data(asset_obj, timeframe, start, end)

        # Cache if we got data
        if data:
            self._save_cache(cache_key, data)

        return data or []

    def _fetch_crypto_data(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch crypto data with fallback chain"""

        # Force options
        if self.force_binance:
            return self._fetch_binance(asset, timeframe, start, end)
        if self.force_coinbase:
            return self._fetch_coinbase(asset, timeframe, start, end)

        # Try each source
        sources = [
            ("yfinance", self._fetch_yfinance),
            ("binance", self._fetch_binance),
            ("coinbase", self._fetch_coinbase),
        ]

        if self.disable_yf:
            sources = sources[1:]

        for source_name, fetch_func in sources:
            try:
                start_time = time.time()
                data = fetch_func(asset, timeframe, start, end)
                latency = time.time() - start_time
                self.source_latencies[source_name] = latency

                if data:
                    logger.info(
                        f"Got crypto data from {source_name}: {len(data)} bars in {latency:.2f}s"
                    )
                    return data
            except Exception as e:
                logger.warning(f"{source_name} failed for {asset}: {e}")

        return None

    def _fetch_stock_data(
        self, asset: Asset, timeframe: str, start: str, end: str, adjust: bool = True
    ) -> Optional[List[List]]:
        """Fetch stock data with fallback chain"""

        sources = [
            ("yfinance", lambda: self._fetch_yfinance_stock(asset, timeframe, start, end, adjust)),
            ("stooq", lambda: self._fetch_stooq(asset, timeframe, start, end)),
        ]

        if self.disable_yf:
            sources = sources[1:]

        for source_name, fetch_func in sources:
            try:
                start_time = time.time()
                data = fetch_func()
                latency = time.time() - start_time
                self.source_latencies[source_name] = latency

                if data:
                    logger.info(
                        f"Got stock data from {source_name}: {len(data)} bars in {latency:.2f}s"
                    )
                    return data
            except Exception as e:
                logger.warning(f"{source_name} failed for {asset}: {e}")

        return None

    def _fetch_forex_data(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch forex data"""
        return self._fetch_yfinance(asset, timeframe, start, end)

    def _fetch_yfinance(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch from yfinance"""
        try:
            symbol = asset.to_yfinance()

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
            interval = tf_map.get(timeframe, "1d")

            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)

            if df.empty:
                return None

            # Convert to standard format (UTC milliseconds)
            result = []
            for idx, row in df.iterrows():
                # Ensure UTC
                if idx.tzinfo is None:
                    idx = pytz.UTC.localize(idx)
                else:
                    idx = idx.astimezone(pytz.UTC)

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
        except Exception as e:
            logger.error(f"yfinance error: {e}")
            return None

    def _fetch_yfinance_stock(
        self, asset: Asset, timeframe: str, start: str, end: str, adjust: bool = True
    ) -> Optional[List[List]]:
        """Fetch stock data from yfinance with corporate action adjustments"""
        try:
            symbol = asset.to_yfinance()
            ticker = yf.Ticker(symbol)

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
            interval = tf_map.get(timeframe, "1d")

            # Fetch with auto_adjust for splits/dividends
            df = ticker.history(start=start, end=end, interval=interval, auto_adjust=adjust)

            if df.empty:
                return None

            # Get splits and dividends if needed
            if adjust and timeframe == "1d":
                try:
                    actions = ticker.actions
                    if not actions.empty:
                        logger.info(f"Corporate actions found for {symbol}: {len(actions)} events")
                except:
                    pass

            # Convert to standard format
            result = []
            for idx, row in df.iterrows():
                # Convert to UTC
                if idx.tzinfo is None:
                    market_tz = MarketCalendar.get_market_tz(asset.venue)
                    idx = market_tz.localize(idx)
                idx = idx.astimezone(pytz.UTC)

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
        except Exception as e:
            logger.error(f"yfinance stock error: {e}")
            return None

    def _fetch_binance(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch from Binance public API"""
        try:
            symbol = asset.to_binance()

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

            url = "https://api.binance.com/api/v3/klines"
            all_data = []

            while start_ts < end_ts:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": start_ts,
                    "endTime": end_ts,
                    "limit": 1000,
                }

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
                else:
                    break

            # Convert to standard format
            result = []
            for candle in all_data:
                result.append(
                    [
                        int(candle[0]),  # timestamp already in ms
                        float(candle[1]),  # open
                        float(candle[2]),  # high
                        float(candle[3]),  # low
                        float(candle[4]),  # close
                        float(candle[5]),  # volume
                    ]
                )

            return result
        except Exception as e:
            logger.error(f"Binance error: {e}")
            return None

    def _fetch_coinbase(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch from Coinbase public API"""
        try:
            # Convert symbol (BTC/USDT -> BTC-USD)
            base = asset.base
            quote = "USD" if asset.quote == "USDT" else asset.quote
            symbol = f"{base}-{quote}"

            # Convert timeframe to granularity
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

            url = f"https://api.exchange.coinbase.com/products/{symbol}/candles"
            params = {"start": start, "end": end, "granularity": granularity}

            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                return None

            data = response.json()

            # Convert to standard format (Coinbase returns newest first)
            result = []
            for candle in reversed(data):
                result.append(
                    [
                        int(candle[0]) * 1000,  # timestamp to ms
                        float(candle[3]),  # open
                        float(candle[2]),  # high
                        float(candle[1]),  # low
                        float(candle[4]),  # close
                        float(candle[5]),  # volume
                    ]
                )

            return result
        except Exception as e:
            logger.error(f"Coinbase error: {e}")
            return None

    def _fetch_stooq(
        self, asset: Asset, timeframe: str, start: str, end: str
    ) -> Optional[List[List]]:
        """Fetch from Stooq (stocks only, daily data)"""
        if timeframe not in ["1d", "1w"]:
            return None

        try:
            symbol = asset.to_stooq()
            url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"

            response = requests.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return None

            lines = response.text.strip().split("\n")
            if len(lines) < 2:
                return None

            result = []
            for line in lines[1:]:  # Skip header
                parts = line.split(",")
                if len(parts) >= 6:
                    date_str = parts[0]
                    dt = datetime.strptime(date_str, "%Y-%m-%d")

                    # Convert to UTC
                    market_tz = MarketCalendar.get_market_tz(asset.venue)
                    dt = market_tz.localize(dt.replace(hour=16))  # Close time
                    dt = dt.astimezone(pytz.UTC)

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
        except Exception as e:
            logger.error(f"Stooq error: {e}")
            return None

    def get_ticker(self, asset: str) -> Dict:
        """Get latest ticker data"""
        asset_obj = symbol_registry.parse(asset)
        if not asset_obj:
            return {"error": "Unknown asset"}

        # Try to get last 1 day of data
        end = datetime.now().isoformat()[:10]
        start = (datetime.now() - timedelta(days=1)).isoformat()[:10]

        data = self.get_ohlcv(asset, "1m", start, end)

        if data:
            latest = data[-1]
            return {
                "symbol": str(asset_obj),
                "price": latest[4],  # close price
                "timestamp": latest[0],
                "volume": latest[5],
                "venue": asset_obj.venue,
            }

        # Fallback to simple ticker
        return self._fetch_ticker_direct(asset_obj)

    def _fetch_ticker_direct(self, asset: Asset) -> Dict:
        """Direct ticker fetch"""
        if asset.type == AssetType.CRYPTO and asset.venue == "BINANCE":
            try:
                symbol = asset.to_binance()
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "symbol": str(asset),
                        "price": float(data["price"]),
                        "timestamp": int(time.time() * 1000),
                        "venue": asset.venue,
                    }
            except:
                pass

        return {
            "symbol": str(asset),
            "price": 0,
            "timestamp": int(time.time() * 1000),
            "venue": asset.venue,
            "error": "No data available",
        }

    def _get_cache_key(self, asset: Asset, timeframe: str, start: str, end: str) -> str:
        """Generate cache key"""
        key_str = f"{asset}_{timeframe}_{start}_{end}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _load_cache(self, cache_key: str) -> Optional[List[List]]:
        """Load from cache if exists and not expired"""
        cache_file = self.cache_dir / f"{cache_key}.parquet"

        if not cache_file.exists():
            return None

        # Check if expired
        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age > self.cache_ttl:
            cache_file.unlink()
            return None

        try:
            table = pq.read_table(cache_file)
            df = table.to_pandas()

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

    def _save_cache(self, cache_key: str, data: List[List]):
        """Save to cache"""
        if not data:
            return

        cache_file = self.cache_dir / f"{cache_key}.parquet"

        try:
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
            table = pa.Table.from_pandas(df)
            pq.write_table(table, cache_file)
            logger.info(f"Cached {len(data)} bars to {cache_key}")
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def get_health(self) -> Dict:
        """Get health metrics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "source_latencies": self.source_latencies,
            "cache_size_mb": sum(f.stat().st_size for f in self.cache_dir.glob("*.parquet"))
            / 1024
            / 1024,
            "disable_yf": self.disable_yf,
            "force_binance": self.force_binance,
            "force_coinbase": self.force_coinbase,
        }


# Global instance
datahub_v2 = DataHubV2()
