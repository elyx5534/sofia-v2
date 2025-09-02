"""YFinance provider for equity data."""

import asyncio
from datetime import datetime

import yfinance as yf

from ..models import AssetType, OHLCVData, SymbolInfo


class YFinanceProvider:
    """Provider for fetching equity data from Yahoo Finance."""

    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "60m",
        "1d": "1d",
        "1w": "1wk",
        "1M": "1mo",
    }

    PERIOD_MAP = {
        "1m": "7d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "1h": "730d",
        "1d": "max",
        "1w": "max",
        "1M": "max",
    }

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 500,
    ) -> list[OHLCVData]:
        """
        Fetch OHLCV data for an equity symbol.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            timeframe: Timeframe for candles (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)
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
            # Convert timeframe
            yf_interval = self.TIMEFRAME_MAP.get(timeframe, "1d")

            # Run yfinance in thread pool (it's not async)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self._fetch_sync,
                symbol,
                yf_interval,
                start_date,
                end_date,
                limit,
            )

            return data

        except Exception as e:
            if "No data found" in str(e):
                raise ValueError(f"Symbol {symbol} not found") from e
            raise Exception(f"YFinance error: {e!s}") from e

    def _fetch_sync(
        self,
        symbol: str,
        interval: str,
        start_date: datetime | None,
        end_date: datetime | None,
        limit: int,
    ) -> list[OHLCVData]:
        """Synchronous fetch function for yfinance."""
        ticker = yf.Ticker(symbol)

        # Determine period or use dates
        if start_date and end_date:
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
            )
        else:
            # Use default period based on interval
            period = self.PERIOD_MAP.get(interval, "1mo")
            df = ticker.history(period=period, interval=interval)

        if df.empty:
            raise ValueError(f"No data found for symbol {symbol}")

        # Convert to OHLCVData
        ohlcv_data = []
        for timestamp, row in df.iterrows():
            ohlcv_data.append(
                OHLCVData(
                    timestamp=timestamp.to_pydatetime(),  # type: ignore
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )

        # Apply limit
        if len(ohlcv_data) > limit:
            ohlcv_data = ohlcv_data[-limit:]

        return ohlcv_data

    async def search_symbols(self, query: str, limit: int = 10) -> list[SymbolInfo]:
        """
        Search for equity symbols.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of symbol information
        """
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self._search_sync, query, limit)
            return results
        except Exception as e:
            raise Exception(f"YFinance search error: {e!s}") from e

    def _search_sync(self, query: str, limit: int) -> list[SymbolInfo]:
        """Synchronous search function."""
        # YFinance doesn't have a direct search API, so we'll use ticker info
        # For demo purposes, we'll check if the ticker exists
        symbols = []

        # Common suffixes for the query
        potential_tickers = [
            query.upper(),
            f"{query.upper()}.L",  # London
            f"{query.upper()}.TO",  # Toronto
            f"{query.upper()}.AX",  # Australia
        ]

        for ticker_symbol in potential_tickers[:limit]:
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info

                if info and "symbol" in info:
                    symbols.append(
                        SymbolInfo(
                            symbol=info.get("symbol", ticker_symbol),
                            name=info.get("longName") or info.get("shortName"),
                            asset_type=AssetType.EQUITY,
                            currency=info.get("currency", "USD"),
                            active=info.get("tradeable", True),
                        )
                    )
            except Exception:
                # Skip invalid tickers
                continue

        return symbols

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """
        Get detailed information for a specific symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Symbol information or None if not found
        """
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._get_info_sync, symbol)
            return info
        except Exception:
            return None

    def _get_info_sync(self, symbol: str) -> SymbolInfo | None:
        """Synchronous function to get symbol info."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or "symbol" not in info:
                return None

            return SymbolInfo(
                symbol=info.get("symbol", symbol),
                name=info.get("longName") or info.get("shortName"),
                asset_type=AssetType.EQUITY,
                currency=info.get("currency", "USD"),
                active=info.get("tradeable", True),
            )
        except Exception:
            return None
