"""
Strategy Engine v3 - Cross-Market Trading System

Advanced multi-market trading platform supporting:
- Cryptocurrency exchanges (Binance, Coinbase, Kraken)
- Traditional equity markets (NYSE, NASDAQ)
- Forex markets
- Commodity futures
- Cross-market arbitrage
- Market correlation analysis
- Advanced order routing
"""

from .market_adapter import MarketAdapter, MarketType
from .cross_market_engine import CrossMarketEngine
from .arbitrage_scanner import ArbitrageScanner
from .correlation_analyzer import CorrelationAnalyzer
from .order_router import SmartOrderRouter

__version__ = "3.0.0"
__all__ = [
    "MarketAdapter",
    "MarketType",
    "CrossMarketEngine",
    "ArbitrageScanner",
    "CorrelationAnalyzer",
    "SmartOrderRouter"
]