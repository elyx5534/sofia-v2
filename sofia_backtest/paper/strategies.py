"""Paper trading strategy implementations"""

from sofia_strategies.grid import GridStrategy
from sofia_strategies.trend import TrendStrategy

# Alias for backward compatibility
GridLiteStrategy = GridStrategy

__all__ = ["GridStrategy", "TrendStrategy", "GridLiteStrategy"]