"""
Strategy Registry
Simple registry for backtesting strategies
"""

from typing import Any, Dict, List


class StrategyRegistry:
    """Registry for trading strategies"""

    def __init__(self):
        self.strategies = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register default strategies"""
        self.strategies = {
            "sma_crossover": {
                "name": "SMA Crossover",
                "description": "Simple Moving Average crossover strategy",
                "params": {"fast_period": 10, "slow_period": 20},
            },
            "rsi_oversold": {
                "name": "RSI Oversold",
                "description": "Buy when RSI is oversold",
                "params": {"period": 14, "oversold": 30, "overbought": 70},
            },
            "bollinger_bands": {
                "name": "Bollinger Bands",
                "description": "Trade on Bollinger Band breakouts",
                "params": {"period": 20, "std_dev": 2},
            },
            "macd": {
                "name": "MACD",
                "description": "MACD signal crossover strategy",
                "params": {"fast": 12, "slow": 26, "signal": 9},
            },
            "grid_monster": {
                "name": "Grid Monster",
                "description": "Advanced grid trading strategy",
                "params": {"grid_levels": 30, "grid_spacing_pct": 0.25},
            },
        }

    def get_all_strategies(self) -> Dict[str, Any]:
        """Get all registered strategies"""
        return self.strategies

    def get_strategy(self, name: str) -> Dict[str, Any]:
        """Get a specific strategy"""
        return self.strategies.get(name, {})

    def register_strategy(self, name: str, config: Dict[str, Any]):
        """Register a new strategy"""
        self.strategies[name] = config

    def list_strategy_names(self) -> List[str]:
        """List all strategy names"""
        return list(self.strategies.keys())


# Global registry instance
strategy_registry = StrategyRegistry()
