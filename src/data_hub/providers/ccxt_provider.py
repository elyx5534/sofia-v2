"""CCXT provider for cryptocurrency data."""

from datetime import datetime

import ccxt.async_support as ccxt

from ..models import AssetType, OHLCVData, SymbolInfo
from ..settings import settings


class CCXTProvider:
    """Provider for fetching cryptocurrency data from exchanges."""

    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M",
    }

    def __init__(self, exchange_name: str = None):
        """Initialize CCXT provider with specified exchange."""
        self.exchange_name = exchange_name or settings.default_exchange
        self.exchange: ccxt.Exchange | None = None

    async def _get_exchange(self) -> ccxt.Exchange:
        """Get or create exchange instance."""
        if not self.exchange:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class(
                {
                    "enableRateLimit": True,
                    "timeout": settings.provider_timeout * 1000,
                }
            )
        return self.exchange

    async def close(self) -> None:
        """Close exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self.exchange = None

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 500,
    ) -> list[OHLCVData]:
        """
        Fetch OHLCV data for a cryptocurrency pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe for candles
            start_date: Start date for historical data
            end_date: End date for historical data
            limit: Maximum number of candles to return

        Returns:
            List of OHLCV data points

        Raises:
            ValueError: If symbol not found or invalid parameters
            Exception: For provider errors
        """
        try:
            exchange = await self._get_exchange()

            # Load markets if not loaded
            if not exchange.markets:
                await exchange.load_markets()

            # Check if symbol exists
            if symbol not in exchange.markets:
                raise ValueError(f"Symbol {symbol} not found on {self.exchange_name}")

            # Convert timeframe
            ccxt_timeframe = self.TIMEFRAME_MAP.get(timeframe, "1h")

            # Calculate since timestamp if start_date provided
            since = None
            if start_date:
                since = int(start_date.timestamp() * 1000)

            # Fetch OHLCV data
            ohlcv = await exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=ccxt_timeframe,
                since=since,
                limit=limit,
            )

            # Convert to OHLCVData objects
            result = []
            for candle in ohlcv:
                timestamp = datetime.fromtimestamp(candle[0] / 1000)

                # Filter by end_date if provided
                if end_date and timestamp > end_date:
                    continue

                result.append(
                    OHLCVData(
                        timestamp=timestamp,
                        open=float(candle[1]),
                        high=float(candle[2]),
                        low=float(candle[3]),
                        close=float(candle[4]),
                        volume=float(candle[5]),
                    )
                )

            return result

        except ccxt.BaseError as e:
            if isinstance(e, ccxt.BadSymbol):
                raise ValueError(f"Invalid symbol: {symbol}") from e
            raise Exception(f"CCXT error: {e!s}") from e
        except Exception as e:
            raise Exception(f"Unexpected error: {e!s}") from e

    async def search_symbols(self, query: str = "", limit: int = 50) -> list[SymbolInfo]:
        """
        Search for cryptocurrency symbols.

        Args:
            query: Search query string (filters symbols)
            limit: Maximum number of results

        Returns:
            List of symbol information
        """
        try:
            exchange = await self._get_exchange()

            # Load markets if not loaded
            if not exchange.markets:
                await exchange.load_markets()

            symbols = []
            query_upper = query.upper()

            for symbol, market in exchange.markets.items():
                # Filter by query if provided
                if query and query_upper not in symbol.upper():
                    continue

                symbols.append(
                    SymbolInfo(
                        symbol=symbol,
                        name=f"{market['base']}/{market['quote']}",
                        asset_type=AssetType.CRYPTO,
                        exchange=self.exchange_name,
                        currency=market.get("quote", "USDT"),
                        active=market.get("active", True),
                    )
                )

                if len(symbols) >= limit:
                    break

            return symbols

        except ccxt.BaseError as e:
            raise Exception(f"CCXT error: {e!s}") from e
        except Exception as e:
            raise Exception(f"Unexpected error: {e!s}") from e

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """
        Get detailed information for a specific symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Symbol information or None if not found
        """
        try:
            exchange = await self._get_exchange()

            # Load markets if not loaded
            if not exchange.markets:
                await exchange.load_markets()

            if symbol not in exchange.markets:
                return None

            market = exchange.markets[symbol]

            return SymbolInfo(
                symbol=symbol,
                name=f"{market['base']}/{market['quote']}",
                asset_type=AssetType.CRYPTO,
                exchange=self.exchange_name,
                currency=market.get("quote", "USDT"),
                active=market.get("active", True),
            )

        except Exception:
            return None

    async def list_exchanges(self) -> list[str]:
        """
        List all available exchanges.

        Returns:
            List of exchange names
        """
        return ccxt.exchanges

    async def get_markets(self) -> dict:
        """
        Get all markets for the current exchange.

        Returns:
            Dictionary of market information
        """
        try:
            exchange = await self._get_exchange()
            if not exchange.markets:
                await exchange.load_markets()
            return exchange.markets
        except Exception as e:
            raise Exception(f"Failed to fetch markets: {e!s}") from e
