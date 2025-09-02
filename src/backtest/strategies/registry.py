"""Strategy Registry System with parameter schemas."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from .base import BaseStrategy


class ParameterType(str, Enum):
    """Parameter data types."""

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    SELECT = "select"  # Dropdown selection


@dataclass
class ParameterSchema:
    """Schema for a strategy parameter."""

    name: str
    display_name: str
    type: ParameterType
    default: Any
    description: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[Any]] = None  # For SELECT type
    required: bool = True

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "type": self.type.value,
            "default": self.default,
            "description": self.description,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "options": self.options,
            "required": self.required,
        }


@dataclass
class StrategyMetadata:
    """Metadata for a trading strategy."""

    name: str
    display_name: str
    description: str
    category: str  # trend, momentum, mean_reversion, ml, etc.
    author: str
    version: str
    parameters: List[ParameterSchema] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high
    timeframes: List[str] = field(default_factory=lambda: ["1d", "4h", "1h"])

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "author": self.author,
            "version": self.version,
            "parameters": [p.to_dict() for p in self.parameters],
            "tags": self.tags,
            "risk_level": self.risk_level,
            "timeframes": self.timeframes,
        }


class StrategyRegistry:
    """Central registry for all trading strategies."""

    _instance = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry."""
        if self._initialized:
            return

        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._metadata: Dict[str, StrategyMetadata] = {}
        self._initialized = True

        # Register built-in strategies
        self._register_builtin_strategies()

    def _register_builtin_strategies(self):
        """Register all built-in strategies."""
        # Import built-in strategies
        from .bollinger_strategy import BollingerBandsStrategy
        from .macd_strategy import MACDStrategy
        from .multi_indicator import MultiIndicatorStrategy
        from .rsi_strategy import RSIStrategy
        from .sma import SMAStrategy

        # SMA Crossover Strategy
        self.register(
            SMAStrategy,
            StrategyMetadata(
                name="sma_crossover",
                display_name="SMA Crossover",
                description="Classic moving average crossover strategy",
                category="trend",
                author="Sofia Team",
                version="1.0.0",
                parameters=[
                    ParameterSchema(
                        name="short_window",
                        display_name="Short MA Period",
                        type=ParameterType.INTEGER,
                        default=20,
                        description="Period for short moving average",
                        min_value=5,
                        max_value=50,
                        step=1,
                    ),
                    ParameterSchema(
                        name="long_window",
                        display_name="Long MA Period",
                        type=ParameterType.INTEGER,
                        default=50,
                        description="Period for long moving average",
                        min_value=20,
                        max_value=200,
                        step=5,
                    ),
                    ParameterSchema(
                        name="position_size",
                        display_name="Position Size",
                        type=ParameterType.FLOAT,
                        default=0.95,
                        description="Fraction of capital to use per trade",
                        min_value=0.1,
                        max_value=1.0,
                        step=0.05,
                    ),
                ],
                tags=["simple", "trend", "moving_average"],
                risk_level="low",
                timeframes=["1d", "4h"],
            ),
        )

        # RSI Strategy
        self.register(
            RSIStrategy,
            StrategyMetadata(
                name="rsi_oversold",
                display_name="RSI Oversold/Overbought",
                description="Buy oversold, sell overbought based on RSI",
                category="momentum",
                author="Sofia Team",
                version="1.0.0",
                parameters=[
                    ParameterSchema(
                        name="rsi_period",
                        display_name="RSI Period",
                        type=ParameterType.INTEGER,
                        default=14,
                        description="RSI calculation period",
                        min_value=7,
                        max_value=28,
                        step=1,
                    ),
                    ParameterSchema(
                        name="oversold_level",
                        display_name="Oversold Level",
                        type=ParameterType.INTEGER,
                        default=30,
                        description="RSI level to consider oversold",
                        min_value=20,
                        max_value=40,
                        step=5,
                    ),
                    ParameterSchema(
                        name="overbought_level",
                        display_name="Overbought Level",
                        type=ParameterType.INTEGER,
                        default=70,
                        description="RSI level to consider overbought",
                        min_value=60,
                        max_value=80,
                        step=5,
                    ),
                ],
                tags=["momentum", "rsi", "oscillator"],
                risk_level="medium",
            ),
        )

        # MACD Strategy
        self.register(
            MACDStrategy,
            StrategyMetadata(
                name="macd_signal",
                display_name="MACD Signal Cross",
                description="Trade on MACD and signal line crossovers",
                category="momentum",
                author="Sofia Team",
                version="1.0.0",
                parameters=[
                    ParameterSchema(
                        name="fast_period",
                        display_name="Fast EMA",
                        type=ParameterType.INTEGER,
                        default=12,
                        description="Fast EMA period",
                        min_value=8,
                        max_value=20,
                    ),
                    ParameterSchema(
                        name="slow_period",
                        display_name="Slow EMA",
                        type=ParameterType.INTEGER,
                        default=26,
                        description="Slow EMA period",
                        min_value=20,
                        max_value=35,
                    ),
                    ParameterSchema(
                        name="signal_period",
                        display_name="Signal Period",
                        type=ParameterType.INTEGER,
                        default=9,
                        description="Signal line EMA period",
                        min_value=5,
                        max_value=15,
                    ),
                ],
                tags=["momentum", "macd", "trend"],
                risk_level="medium",
            ),
        )

        # Bollinger Bands Strategy
        self.register(
            BollingerBandsStrategy,
            StrategyMetadata(
                name="bollinger_bands",
                display_name="Bollinger Bands Squeeze",
                description="Trade breakouts from Bollinger Bands",
                category="volatility",
                author="Sofia Team",
                version="1.0.0",
                parameters=[
                    ParameterSchema(
                        name="bb_period",
                        display_name="BB Period",
                        type=ParameterType.INTEGER,
                        default=20,
                        description="Bollinger Bands period",
                        min_value=10,
                        max_value=50,
                    ),
                    ParameterSchema(
                        name="bb_std",
                        display_name="Standard Deviations",
                        type=ParameterType.FLOAT,
                        default=2.0,
                        description="Number of standard deviations",
                        min_value=1.0,
                        max_value=3.0,
                        step=0.5,
                    ),
                ],
                tags=["volatility", "bollinger", "breakout"],
                risk_level="medium",
            ),
        )

        # Multi-Indicator Strategy
        self.register(
            MultiIndicatorStrategy,
            StrategyMetadata(
                name="multi_indicator",
                display_name="Multi-Indicator Confluence",
                description="Combines RSI, MACD, and BB for high-probability trades",
                category="composite",
                author="Sofia Team",
                version="2.0.0",
                parameters=[
                    ParameterSchema(
                        name="rsi_weight",
                        display_name="RSI Weight",
                        type=ParameterType.FLOAT,
                        default=0.33,
                        description="Weight for RSI signal",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.1,
                    ),
                    ParameterSchema(
                        name="macd_weight",
                        display_name="MACD Weight",
                        type=ParameterType.FLOAT,
                        default=0.33,
                        description="Weight for MACD signal",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.1,
                    ),
                    ParameterSchema(
                        name="bb_weight",
                        display_name="BB Weight",
                        type=ParameterType.FLOAT,
                        default=0.34,
                        description="Weight for Bollinger Bands signal",
                        min_value=0.0,
                        max_value=1.0,
                        step=0.1,
                    ),
                    ParameterSchema(
                        name="signal_threshold",
                        display_name="Signal Threshold",
                        type=ParameterType.FLOAT,
                        default=0.6,
                        description="Minimum combined signal strength to trade",
                        min_value=0.3,
                        max_value=0.9,
                        step=0.1,
                    ),
                ],
                tags=["advanced", "composite", "multi-indicator"],
                risk_level="low",
                timeframes=["1d", "4h", "1h"],
            ),
        )

    def register(self, strategy_class: Type[BaseStrategy], metadata: StrategyMetadata):
        """Register a new strategy."""
        self._strategies[metadata.name] = strategy_class
        self._metadata[metadata.name] = metadata

    def get_strategy(self, name: str) -> Optional[Type[BaseStrategy]]:
        """Get strategy class by name."""
        return self._strategies.get(name)

    def get_metadata(self, name: str) -> Optional[StrategyMetadata]:
        """Get strategy metadata by name."""
        return self._metadata.get(name)

    def list_strategies(self, category: Optional[str] = None) -> List[StrategyMetadata]:
        """List all registered strategies, optionally filtered by category."""
        strategies = list(self._metadata.values())

        if category:
            strategies = [s for s in strategies if s.category == category]

        return strategies

    def get_categories(self) -> List[str]:
        """Get all unique strategy categories."""
        return list(set(s.category for s in self._metadata.values()))

    def export_schemas(self) -> Dict[str, Any]:
        """Export all strategy schemas as JSON-serializable dict."""
        return {
            "strategies": [m.to_dict() for m in self._metadata.values()],
            "categories": self.get_categories(),
        }

    def validate_parameters(self, strategy_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and coerce parameters for a strategy."""
        metadata = self.get_metadata(strategy_name)
        if not metadata:
            raise ValueError(f"Strategy {strategy_name} not found")

        validated = {}

        for param_schema in metadata.parameters:
            value = parameters.get(param_schema.name, param_schema.default)

            # Type coercion
            if param_schema.type == ParameterType.INTEGER:
                value = int(value)
            elif param_schema.type == ParameterType.FLOAT:
                value = float(value)
            elif param_schema.type == ParameterType.BOOLEAN:
                value = bool(value)

            # Range validation
            if param_schema.min_value is not None and value < param_schema.min_value:
                value = param_schema.min_value
            if param_schema.max_value is not None and value > param_schema.max_value:
                value = param_schema.max_value

            # Options validation
            if param_schema.options and value not in param_schema.options:
                value = param_schema.default

            validated[param_schema.name] = value

        return validated
