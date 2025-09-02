"""
Symbol Management Service
Canonical asset representation and mapping
"""

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

class AssetType(Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    FOREX = "forex"
    COMMODITY = "commodity"
    INDEX = "index"

@dataclass
class Asset:
    """Canonical asset representation"""
    type: AssetType
    base: str  # BTC, AAPL, EUR
    quote: str  # USDT, USD, TRY
    venue: str  # BINANCE, NASDAQ, BIST
    
    def __str__(self):
        """Standard format: BASE/QUOTE@VENUE"""
        return f"{self.base}/{self.quote}@{self.venue}"
    
    def to_ccxt(self) -> str:
        """Convert to CCXT format"""
        return f"{self.base}/{self.quote}"
    
    def to_yfinance(self) -> str:
        """Convert to yfinance format"""
        if self.type == AssetType.CRYPTO:
            # Crypto: BTC-USD
            return f"{self.base}-{self.quote}"
        elif self.type == AssetType.STOCK:
            # Stock: AAPL or ASELS.IS for BIST
            if self.venue == "BIST":
                return f"{self.base}.IS"
            return self.base
        return f"{self.base}{self.quote}=X"  # Forex format
    
    def to_binance(self) -> str:
        """Convert to Binance format"""
        return f"{self.base}{self.quote}"
    
    def to_stooq(self) -> str:
        """Convert to Stooq format"""
        if self.venue == "BIST":
            return f"{self.base.lower()}.is"
        return self.base.lower()

class SymbolRegistry:
    """Symbol mapping and management"""
    
    def __init__(self):
        self.assets: Dict[str, Asset] = {}
        self._init_common_symbols()
        
    def _init_common_symbols(self):
        """Initialize common symbol mappings"""
        # Crypto symbols
        cryptos = [
            ("BTC/USDT@BINANCE", "crypto", "BTC", "USDT", "BINANCE"),
            ("ETH/USDT@BINANCE", "crypto", "ETH", "USDT", "BINANCE"),
            ("SOL/USDT@BINANCE", "crypto", "SOL", "USDT", "BINANCE"),
            ("BTC/USDT@BYBIT", "crypto", "BTC", "USDT", "BYBIT"),
            ("ETH/USDT@BYBIT", "crypto", "ETH", "USDT", "BYBIT"),
            ("BTC/TRY@BTCTURK", "crypto", "BTC", "TRY", "BTCTURK"),
            ("ETH/TRY@BTCTURK", "crypto", "ETH", "TRY", "BTCTURK"),
            ("BTC/TRY@PARIBU", "crypto", "BTC", "TRY", "PARIBU"),
        ]
        
        # Stock symbols
        stocks = [
            ("AAPL@NASDAQ", "stock", "AAPL", "USD", "NASDAQ"),
            ("MSFT@NASDAQ", "stock", "MSFT", "USD", "NASDAQ"),
            ("GOOGL@NASDAQ", "stock", "GOOGL", "USD", "NASDAQ"),
            ("TSLA@NASDAQ", "stock", "TSLA", "USD", "NASDAQ"),
            ("ASELS@BIST", "stock", "ASELS", "TRY", "BIST"),
            ("THYAO@BIST", "stock", "THYAO", "TRY", "BIST"),
            ("SISE@BIST", "stock", "SISE", "TRY", "BIST"),
            ("GARAN@BIST", "stock", "GARAN", "TRY", "BIST"),
        ]
        
        # Forex pairs
        forex = [
            ("USD/TRY@FOREX", "forex", "USD", "TRY", "FOREX"),
            ("EUR/USD@FOREX", "forex", "EUR", "USD", "FOREX"),
            ("GBP/USD@FOREX", "forex", "GBP", "USD", "FOREX"),
        ]
        
        # Register all
        for symbol, asset_type, base, quote, venue in cryptos + stocks + forex:
            self.register(symbol, AssetType(asset_type), base, quote, venue)
    
    def register(self, symbol: str, asset_type: AssetType, base: str, quote: str, venue: str) -> Asset:
        """Register a new asset"""
        asset = Asset(type=asset_type, base=base, quote=quote, venue=venue)
        self.assets[symbol] = asset
        
        # Also register without venue for convenience
        simple_symbol = f"{base}/{quote}"
        if simple_symbol not in self.assets:
            self.assets[simple_symbol] = asset
            
        return asset
    
    def parse(self, symbol: str) -> Optional[Asset]:
        """Parse symbol string to Asset"""
        # Check if already registered
        if symbol in self.assets:
            return self.assets[symbol]
        
        # Try to parse: BASE/QUOTE@VENUE or BASE/QUOTE
        if "@" in symbol:
            parts = symbol.split("@")
            if len(parts) == 2:
                pair, venue = parts
                if "/" in pair:
                    base, quote = pair.split("/")
                    # Guess asset type
                    asset_type = self._guess_asset_type(base, quote, venue)
                    return self.register(symbol, asset_type, base, quote, venue)
        elif "/" in symbol:
            base, quote = symbol.split("/")
            # Default venue based on quote
            if quote in ["USDT", "BUSD", "USDC"]:
                venue = "BINANCE"
                asset_type = AssetType.CRYPTO
            elif quote == "TRY":
                venue = "BTCTURK" if base in ["BTC", "ETH"] else "BIST"
                asset_type = AssetType.CRYPTO if base in ["BTC", "ETH"] else AssetType.STOCK
            else:
                venue = "FOREX"
                asset_type = AssetType.FOREX
            return self.register(symbol, asset_type, base, quote, venue)
        
        # Try stock symbol
        if symbol.upper() == symbol and 2 <= len(symbol) <= 5:
            # Likely a stock ticker
            if symbol.endswith(".IS"):
                # BIST stock
                base = symbol[:-3]
                return self.register(f"{base}@BIST", AssetType.STOCK, base, "TRY", "BIST")
            else:
                # US stock
                return self.register(f"{symbol}@NASDAQ", AssetType.STOCK, symbol, "USD", "NASDAQ")
        
        return None
    
    def _guess_asset_type(self, base: str, quote: str, venue: str) -> AssetType:
        """Guess asset type from components"""
        crypto_venues = ["BINANCE", "BYBIT", "COINBASE", "BTCTURK", "PARIBU"]
        stock_venues = ["NASDAQ", "NYSE", "BIST"]
        
        if venue in crypto_venues:
            return AssetType.CRYPTO
        elif venue in stock_venues:
            return AssetType.STOCK
        elif quote in ["USDT", "BUSD", "BTC", "ETH"]:
            return AssetType.CRYPTO
        elif len(base) == 3 and len(quote) == 3:
            return AssetType.FOREX
        else:
            return AssetType.STOCK
    
    def search(self, query: str) -> List[Asset]:
        """Search for assets matching query"""
        query = query.upper()
        results = []
        
        for symbol, asset in self.assets.items():
            if query in asset.base or query in str(asset):
                results.append(asset)
        
        return results
    
    def get_by_venue(self, venue: str) -> List[Asset]:
        """Get all assets from a specific venue"""
        return [a for a in self.assets.values() if a.venue == venue]
    
    def get_by_type(self, asset_type: AssetType) -> List[Asset]:
        """Get all assets of a specific type"""
        return [a for a in self.assets.values() if a.type == asset_type]

# Global registry instance
symbol_registry = SymbolRegistry()