"""Tests for the strategy registry."""

import pytest
from src.backtester.strategies.registry import (
    StrategyRegistry,
    ParameterSchema, 
    ParameterType,
    StrategyMetadata
)
from src.backtester.strategies.base import BaseStrategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, period: int = 14, threshold: float = 0.7):
        super().__init__()
        self.period = period
        self.threshold = threshold
    
    def generate_signals(self, df) -> list:
        """Generate mock signals."""
        return [{"type": "buy", "timestamp": "2023-01-01", "price": 100.0}]


def test_parameter_schema_creation():
    """Test ParameterSchema creation."""
    schema = ParameterSchema(
        name="period",
        display_name="Period",
        type=ParameterType.INTEGER,
        default=14,
        description="Lookback period",
        min_value=5,
        max_value=50
    )
    
    assert schema.name == "period"
    assert schema.type == ParameterType.INTEGER
    assert schema.default == 14
    assert schema.min_value == 5
    assert schema.max_value == 50


def test_strategy_metadata_creation():
    """Test StrategyMetadata creation."""
    parameters = [
        ParameterSchema("period", "Period", ParameterType.INTEGER, 14, "Period desc"),
        ParameterSchema("threshold", "Threshold", ParameterType.FLOAT, 0.7, "Threshold desc")
    ]
    
    metadata = StrategyMetadata(
        name="mock_strategy",
        display_name="Mock Strategy", 
        description="Test strategy",
        category="test",
        author="Test Author",
        version="1.0.0",
        parameters=parameters
    )
    
    assert metadata.name == "mock_strategy"
    assert metadata.display_name == "Mock Strategy"
    assert len(metadata.parameters) == 2


def test_registry_register_strategy():
    """Test registering a strategy."""
    registry = StrategyRegistry()
    
    parameters = [
        ParameterSchema("period", "Period", ParameterType.INTEGER, 14, "Period desc")
    ]
    
    metadata = StrategyMetadata(
        name="mock_strategy",
        display_name="Mock Strategy",
        description="Test strategy",
        category="test", 
        author="Test",
        version="1.0",
        parameters=parameters
    )
    
    registry.register(MockStrategy, metadata)
    
    # Check if registered (simplified check)
    strategies = registry.list_strategies()
    assert any(s.name == "mock_strategy" for s in strategies)


def test_registry_list_strategies():
    """Test listing strategies."""
    registry = StrategyRegistry()
    
    strategies = registry.list_strategies()
    # Should have some built-in strategies
    assert len(strategies) > 0
    assert isinstance(strategies, list)
    
    # Check first strategy structure
    if strategies:
        strategy = strategies[0]
        assert hasattr(strategy, "name")
        assert hasattr(strategy, "display_name")
        assert hasattr(strategy, "category")


def test_registry_singleton():
    """Test that registry is singleton."""
    registry1 = StrategyRegistry()
    registry2 = StrategyRegistry()
    
    assert registry1 is registry2


def test_parameter_types():
    """Test all parameter types."""
    # INTEGER
    int_param = ParameterSchema("int_param", "Integer", ParameterType.INTEGER, 10, "Int desc")
    assert int_param.type == ParameterType.INTEGER
    
    # FLOAT
    float_param = ParameterSchema("float_param", "Float", ParameterType.FLOAT, 1.5, "Float desc")
    assert float_param.type == ParameterType.FLOAT
    
    # BOOLEAN
    bool_param = ParameterSchema("bool_param", "Boolean", ParameterType.BOOLEAN, True, "Bool desc")
    assert bool_param.type == ParameterType.BOOLEAN
    
    # STRING
    str_param = ParameterSchema("str_param", "String", ParameterType.STRING, "test", "String desc")
    assert str_param.type == ParameterType.STRING
    
    # SELECT
    select_param = ParameterSchema(
        "select_param", "Select", ParameterType.SELECT, "option1", "Select desc",
        options=["option1", "option2", "option3"]
    )
    assert select_param.type == ParameterType.SELECT
    assert select_param.options == ["option1", "option2", "option3"]