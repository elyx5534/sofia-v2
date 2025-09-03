"""
CCXT-based exchange interface for multi-exchange OHLCV data collection
"""

from datetime import datetime
from typing import Dict, List, Optional

import ccxt
import pandas as pd
from loguru import logger


class ExchangeClient:
    """Unified interface for cryptocurrency exchanges using CCXT"""

    def __init__(self, exchange_name: str, sandbox: bool = True):
        self.exchange_name = exchange_name
        self.sandbox = sandbox
        self.client = self._create_client()

    def _create_client(self) -> ccxt.Exchange:
        """Create CCXT exchange client"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            client = exchange_class(
                {
                    "sandbox": self.sandbox,
                    "rateLimit": True,
                    "enableRateLimit": True,
                    "verbose": False,
                }
            )
            return client
        except Exception as e:
            logger.error(f"Failed to create {self.exchange_name} client: {e}")
            raise

    def list_usdt_markets(self) -> List[str]:
        """Get all USDT trading pairs from exchange"""
        try:
            markets = self.client.load_markets()
            usdt_pairs = []
            for symbol, market in markets.items():
                if market["quote"] == "USDT" and market["active"] and (market["type"] == "spot"):
                    usdt_pairs.append(symbol)
            logger.info(f"{self.exchange_name}: Found {len(usdt_pairs)} USDT pairs")
            return sorted(usdt_pairs)
        except Exception as e:
            logger.error(f"Failed to get markets from {self.exchange_name}: {e}")
            return []

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol"""
        try:
            since_ms = None
            if since:
                since_ms = int(since.timestamp() * 1000)
            ohlcv = self.client.fetch_ohlcv(
                symbol=symbol, timeframe=timeframe, since=since_ms, limit=limit
            )
            if not ohlcv:
                return pd.DataFrame()
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            logger.debug(f"Fetched {len(df)} candles for {symbol} from {self.exchange_name}")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch {symbol} from {self.exchange_name}: {e}")
            return pd.DataFrame()


class MultiExchangeManager:
    """Manage multiple exchanges and aggregate data"""

    def __init__(self, exchange_names: List[str] = None):
        if exchange_names is None:
            exchange_names = ["binance", "bybit", "kraken"]
        self.exchanges = {}
        for name in exchange_names:
            try:
                self.exchanges[name] = ExchangeClient(name, sandbox=False)
                logger.info(f"Initialized {name} exchange client")
            except Exception as e:
                logger.warning(f"Failed to initialize {name}: {e}")

    def get_unified_symbol_list(self) -> List[str]:
        """Get unified list of USDT symbols across all exchanges"""
        all_symbols = set()
        for exchange_name, client in self.exchanges.items():
            symbols = client.list_usdt_markets()
            all_symbols.update(symbols)
        unified_symbols = []
        for symbol in all_symbols:
            if "/" in symbol and symbol.endswith("/USDT"):
                base = symbol.split("/")[0]
                if base not in ["USDT", "BUSD", "USDC", "DAI", "TEST"]:
                    unified_symbols.append(symbol)
        logger.info(f"Unified symbol list: {len(unified_symbols)} pairs")
        return sorted(unified_symbols)

    def fetch_ohlcv_multi(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV from all available exchanges"""
        results = {}
        for exchange_name, client in self.exchanges.items():
            try:
                df = client.fetch_ohlcv(symbol, timeframe, since, limit)
                if not df.empty:
                    results[exchange_name] = df
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol} from {exchange_name}: {e}")
        return results

    def get_best_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Get best available data for a symbol (highest volume exchange)"""
        multi_data = self.fetch_ohlcv_multi(symbol, timeframe, since, limit)
        if not multi_data:
            return pd.DataFrame()
        best_exchange = None
        highest_volume = 0
        for exchange_name, df in multi_data.items():
            if not df.empty:
                avg_volume = df["volume"].mean()
                if avg_volume > highest_volume:
                    highest_volume = avg_volume
                    best_exchange = exchange_name
        if best_exchange:
            logger.info(f"Selected {best_exchange} for {symbol} (avg volume: {highest_volume:.2f})")
            return multi_data[best_exchange]
        return pd.DataFrame()


exchange_manager = MultiExchangeManager()
