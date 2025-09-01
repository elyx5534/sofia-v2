"""Backtester module for trading strategy evaluation."""

from .engine import BacktestEngine
from .metrics import calculate_metrics

__all__ = ["BacktestEngine", "calculate_metrics"]