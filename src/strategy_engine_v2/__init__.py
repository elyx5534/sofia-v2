"""
Strategy Engine v2 - Multi-asset Portfolio Trading System

This module provides advanced portfolio management capabilities:
- Multi-asset portfolio allocation and rebalancing
- Cross-asset correlation analysis  
- Dynamic position sizing based on volatility
- Portfolio-level risk management
- Asset diversification strategies
"""

from .portfolio_manager import PortfolioManager
from .asset_allocator import AssetAllocator
from .correlation_engine import CorrelationEngine
from .portfolio_optimizer import PortfolioOptimizer
from .rebalancing_engine import RebalancingEngine

__version__ = "2.0.0"
__all__ = [
    "PortfolioManager",
    "AssetAllocator", 
    "CorrelationEngine",
    "PortfolioOptimizer",
    "RebalancingEngine"
]