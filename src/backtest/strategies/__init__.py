"""Trading strategies for backtesting."""

from .base import BaseStrategy
from .sma import SMAStrategy

__all__ = ["BaseStrategy", "SMAStrategy"]