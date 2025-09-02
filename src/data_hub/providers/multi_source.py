"""Multi-source data provider with automatic fallback."""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import ccxt
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Available data sources."""

    YFINANCE = "yfinance"
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BITFINEX = "bitfinex"


class MultiSourceDataProvider:
    """
    Data provider with automatic fallback between multiple sources.
    Priority order: yfinance -> Binance -> Coinbase -> Kraken -> Bitfinex
    """

    def __init__(self, use_sandbox: bool = False):
        """
        Initialize multi-source provider.

        Args:
            use_sandbox: Use sandbox/testnet for exchanges (no real trading)
        """
        self.use_sandbox = use_sandbox
        self.exchanges = {}
        self._init_exchanges()

        # Source priority for different asset types
        self.crypto_sources = [
            DataSource.BINANCE,
            DataSource.COINBASE,
            DataSource.KRAKEN,
            DataSource.BITFINEX,
            DataSource.YFINANCE,
        ]

        self.stock_sources = [DataSource.YFINANCE]

    def _init_exchanges(self):
        """Initialize CCXT exchange connections."""
        try:
            # Binance
            self.exchanges[DataSource.BINANCE] = ccxt.binance(
                {
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot",
                    },
                }
            )

            # Coinbase
            self.exchanges[DataSource.COINBASE] = ccxt.coinbase(
                {
                    "enableRateLimit": True,
                }
            )

            # Kraken
            self.exchanges[DataSource.KRAKEN] = ccxt.kraken(
                {
                    "enableRateLimit": True,
                }
            )

            # Bitfinex
            self.exchanges[DataSource.BITFINEX] = ccxt.bitfinex(
                {
                    "enableRateLimit": True,
                }
            )

            # Set sandbox mode if requested
            if self.use_sandbox:
                for exchange in self.exchanges.values():
                    if hasattr(exchange, "set_sandbox_mode"):
                        exchange.set_sandbox_mode(True)

        except Exception as e:
            logger.error(f"Error initializing exchanges: {e}")

    def _convert_timeframe(self, timeframe: str, source: DataSource) -> str:
        """
        Convert timeframe to source-specific format.

        Args:
            timeframe: Standard timeframe (1m, 5m, 1h, 1d, etc.)
            source: Target data source

        Returns:
            Source-specific timeframe string
        """
        if source == DataSource.YFINANCE:
            # yfinance format
            mapping = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "1h": "1h",
                "4h": "4h",
                "1d": "1d",
                "1w": "1wk",
                "1M": "1mo",
            }
            return mapping.get(timeframe, "1d")
        else:
            # CCXT format (already standard)
            return timeframe

    def _convert_symbol(self, symbol: str, source: DataSource) -> str:
        """
        Convert symbol to source-specific format.

        Args:
            symbol: Standard symbol (BTC/USDT, AAPL, etc.)
            source: Target data source

        Returns:
            Source-specific symbol string
        """
        if source == DataSource.YFINANCE:
            # Convert crypto symbols for yfinance
            if "/" in symbol:
                # BTC/USDT -> BTC-USD
                base, quote = symbol.split("/")
                if quote == "USDT":
                    quote = "USD"
                return f"{base}-{quote}"
            return symbol
        else:
            # CCXT format (already standard for crypto)
            if "/" not in symbol:
                # Assume it's a crypto symbol without pair
                return f"{symbol}/USDT"
            return symbol

    async def fetch_ohlcv_async(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[datetime] = None,
        limit: int = 100,
        sources: Optional[List[DataSource]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data asynchronously with automatic fallback.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            since: Start date
            limit: Number of candles
            sources: List of sources to try (uses defaults if None)

        Returns:
            DataFrame with OHLCV data or None if all sources fail
        """
        # Determine sources to try
        if sources is None:
            if "/" in symbol or symbol in ["BTC", "ETH", "BNB"]:
                sources = self.crypto_sources
            else:
                sources = self.stock_sources

        # Try each source
        for source in sources:
            try:
                logger.info(f"Trying {source} for {symbol}")

                if source == DataSource.YFINANCE:
                    df = await self._fetch_yfinance_async(symbol, timeframe, since, limit)
                else:
                    df = await self._fetch_ccxt_async(source, symbol, timeframe, since, limit)

                if df is not None and not df.empty:
                    logger.info(f"Successfully fetched {len(df)} candles from {source}")
                    return df

            except Exception as e:
                logger.warning(f"Failed to fetch from {source}: {e}")
                continue

        logger.error(f"All sources failed for {symbol}")
        return None

    async def _fetch_yfinance_async(
        self, symbol: str, timeframe: str, since: Optional[datetime], limit: int
    ) -> Optional[pd.DataFrame]:
        """Fetch data from yfinance."""
        try:
            # Convert symbol
            yf_symbol = self._convert_symbol(symbol, DataSource.YFINANCE)

            # Calculate period
            if since:
                period = None
                start = since
                end = datetime.now(timezone.utc)
            else:
                # Use period for simplicity
                period_map = {
                    "1m": "7d",
                    "5m": "1mo",
                    "15m": "1mo",
                    "30m": "1mo",
                    "1h": "2mo",
                    "4h": "6mo",
                    "1d": "1y",
                    "1w": "5y",
                    "1M": "max",
                }
                period = period_map.get(timeframe, "1mo")
                start = None
                end = None

            # Fetch data
            ticker = yf.Ticker(yf_symbol)

            if period:
                df = ticker.history(
                    period=period, interval=self._convert_timeframe(timeframe, DataSource.YFINANCE)
                )
            else:
                df = ticker.history(
                    start=start,
                    end=end,
                    interval=self._convert_timeframe(timeframe, DataSource.YFINANCE),
                )

            if df.empty:
                return None

            # Standardize column names
            df = df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            # Select only OHLCV columns
            df = df[["open", "high", "low", "close", "volume"]]

            # Limit rows
            if len(df) > limit:
                df = df.tail(limit)

            return df

        except Exception as e:
            logger.error(f"yfinance error: {e}")
            return None

    async def _fetch_ccxt_async(
        self, source: DataSource, symbol: str, timeframe: str, since: Optional[datetime], limit: int
    ) -> Optional[pd.DataFrame]:
        """Fetch data from CCXT exchange."""
        try:
            exchange = self.exchanges.get(source)
            if not exchange:
                return None

            # Convert symbol
            ccxt_symbol = self._convert_symbol(symbol, source)

            # Check if symbol is available
            await exchange.load_markets()
            if ccxt_symbol not in exchange.symbols:
                logger.warning(f"{ccxt_symbol} not available on {source}")
                return None

            # Convert since to timestamp
            since_ts = None
            if since:
                since_ts = int(since.timestamp() * 1000)

            # Fetch OHLCV
            ohlcv = await exchange.fetch_ohlcv(
                ccxt_symbol, timeframe=timeframe, since=since_ts, limit=limit
            )

            if not ohlcv:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

            # Convert timestamp to datetime index
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            return df

        except Exception as e:
            logger.error(f"CCXT {source} error: {e}")
            return None

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[datetime] = None,
        limit: int = 100,
        sources: Optional[List[DataSource]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Synchronous wrapper for fetch_ohlcv_async.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.fetch_ohlcv_async(symbol, timeframe, since, limit, sources)
            )
        finally:
            loop.close()

    def get_available_symbols(self, source: DataSource) -> List[str]:
        """
        Get list of available symbols from a source.

        Args:
            source: Data source to query

        Returns:
            List of available symbols
        """
        try:
            if source == DataSource.YFINANCE:
                # yfinance doesn't provide a symbol list easily
                # Return common symbols
                return ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "BTC-USD", "ETH-USD", "BNB-USD"]
            else:
                exchange = self.exchanges.get(source)
                if exchange:
                    exchange.load_markets()
                    return list(exchange.symbols)

        except Exception as e:
            logger.error(f"Error getting symbols from {source}: {e}")

        return []

    def test_connection(self, source: DataSource) -> bool:
        """
        Test connection to a data source.

        Args:
            source: Data source to test

        Returns:
            True if connection successful
        """
        try:
            if source == DataSource.YFINANCE:
                # Test with a known symbol
                ticker = yf.Ticker("AAPL")
                info = ticker.info
                return "symbol" in info
            else:
                exchange = self.exchanges.get(source)
                if exchange:
                    exchange.fetch_ticker("BTC/USDT")
                    return True

        except Exception as e:
            logger.error(f"Connection test failed for {source}: {e}")

        return False

    def get_source_status(self) -> Dict[str, bool]:
        """
        Get connection status for all sources.

        Returns:
            Dictionary of source -> connection status
        """
        status = {}

        for source in DataSource:
            status[source.value] = self.test_connection(source)

        return status
