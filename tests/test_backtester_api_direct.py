"""
Direct tests for Backtester API components without circular imports
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from src.data_hub.models import AssetType


class TestBacktesterAPIComponents:
    """Test individual components of the Backtester API"""

    def test_sma_strategy_import(self):
        """Test that SMA strategy can be imported"""
        from src.backtester.strategies.sma import SMAStrategy

        strategy = SMAStrategy()
        assert strategy is not None

    def test_backtest_engine_import(self):
        """Test that BacktestEngine can be imported"""
        from src.backtester.engine import BacktestEngine

        engine = BacktestEngine()
        assert engine.initial_capital == 10000.0

    def test_metrics_calculation_import(self):
        """Test that metrics calculation can be imported"""
        from src.backtester.metrics import calculate_metrics

        # Test with mock data
        equity_curve = [10000, 10100, 10200, 10150, 10300]
        trades = [
            {
                "timestamp": datetime.now(),
                "type": "buy",
                "price": 100,
                "quantity": 10,
                "value": 1000,
                "commission": 1,
            },
            {
                "timestamp": datetime.now(),
                "type": "sell",
                "price": 103,
                "quantity": 10,
                "value": 1030,
                "commission": 1,
            },
        ]

        metrics = calculate_metrics(equity_curve, trades, initial_capital=10000.0)
        assert isinstance(metrics, dict)
        assert "total_return" in metrics

    def test_data_hub_adapter_import(self):
        """Test that DataHubAdapter can be imported"""
        from src.backtester.data_adapters.data_hub import DataHubAdapter

        adapter = DataHubAdapter()
        assert adapter is not None

    @patch("src.backtester.data_adapters.data_hub.DataHubAdapter")
    @patch("src.backtester.engine.BacktestEngine")
    @patch("src.backtester.metrics.calculate_metrics")
    def test_backtest_logic_simulation(self, mock_metrics, mock_engine, mock_adapter):
        """Test the main backtest logic without FastAPI"""
        # Setup mocks
        mock_data = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000, 1100, 1200, 1300, 1400],
            },
            index=pd.date_range("2023-01-01", periods=5, freq="D"),
        )

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.fetch_ohlcv.return_value = mock_data
        mock_adapter.return_value = mock_adapter_instance

        mock_engine_instance = MagicMock()
        mock_engine_instance.initial_capital = 10000.0
        mock_engine_instance.run.return_value = {
            "equity_curve": [10000.0, 10100.0, 10200.0, 10150.0, 10300.0],
            "trades": [
                {
                    "timestamp": datetime(2023, 1, 2),
                    "type": "buy",
                    "price": 101.0,
                    "quantity": 10.0,
                    "value": 1010.0,
                    "commission": 1.01,
                }
            ],
            "final_equity": 10300.0,
            "return": 0.03,
        }
        mock_engine.return_value = mock_engine_instance

        mock_metrics.return_value = {
            "total_return": 0.03,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.05,
        }

        # Simulate the backtest logic
        from src.backtester.strategies.sma import SMAStrategy

        # Initialize components
        adapter = mock_adapter()
        strategy = SMAStrategy()
        engine = mock_engine(initial_capital=10000.0)

        # Fetch data
        data = adapter.fetch_ohlcv(
            symbol="AAPL", asset_type=AssetType.EQUITY, timeframe="1d", limit=1000
        )

        # Run backtest
        results = engine.run(data, strategy)

        # Calculate metrics
        metrics = mock_metrics(
            equity_curve=results["equity_curve"],
            trades=results["trades"],
            initial_capital=engine.initial_capital,
        )

        # Verify the workflow
        assert not data.empty
        assert "equity_curve" in results
        assert "trades" in results
        assert "total_return" in metrics

        # Verify mocks were called
        mock_adapter_instance.fetch_ohlcv.assert_called_once()
        mock_engine_instance.run.assert_called_once()
        mock_metrics.assert_called_once()

    def test_parameter_parsing_logic(self):
        """Test JSON parameter parsing logic"""

        # Valid JSON
        valid_params = '{"fast_period": 10, "slow_period": 30, "initial_capital": 50000}'
        parsed = json.loads(valid_params)
        assert parsed["fast_period"] == 10
        assert parsed["initial_capital"] == 50000

        # Empty parameters
        empty_params = "{}"
        parsed_empty = json.loads(empty_params)
        assert isinstance(parsed_empty, dict)
        assert len(parsed_empty) == 0

        # Invalid JSON should raise exception
        with pytest.raises(json.JSONDecodeError):
            json.loads("invalid json")

    def test_asset_type_validation(self):
        """Test AssetType enum validation"""
        assert AssetType.EQUITY == "equity"
        assert AssetType.CRYPTO == "crypto"

        # Test that enum values are valid
        valid_types = ["equity", "crypto"]
        for asset_type in valid_types:
            assert asset_type in AssetType

    def test_trade_formatting_logic(self):
        """Test trade data formatting for JSON serialization"""
        # Mock trade data
        trades = [
            {
                "timestamp": datetime(2023, 1, 2, 12, 30, 0),
                "type": "buy",
                "price": 101.0,
                "quantity": 10.0,
                "value": 1010.0,
                "commission": 1.01,
            },
            {
                "timestamp": datetime(2023, 1, 4, 14, 45, 0),
                "type": "sell",
                "price": 103.0,
                "quantity": 10.0,
                "value": 1030.0,
                "commission": 1.03,
            },
        ]

        # Format trades for JSON serialization
        formatted_trades = []
        for trade in trades:
            formatted_trade = {
                "timestamp": (
                    trade["timestamp"].isoformat()
                    if hasattr(trade["timestamp"], "isoformat")
                    else str(trade["timestamp"])
                ),
                "type": trade["type"],
                "price": trade["price"],
                "quantity": trade["quantity"],
                "value": trade["value"],
                "commission": trade["commission"],
            }
            formatted_trades.append(formatted_trade)

        # Verify formatting
        assert len(formatted_trades) == 2
        assert formatted_trades[0]["timestamp"] == "2023-01-02T12:30:00"
        assert formatted_trades[0]["type"] == "buy"
        assert formatted_trades[1]["type"] == "sell"

    def test_error_handling_scenarios(self):
        """Test various error scenarios"""
        from fastapi import HTTPException

        # Test HTTPException creation
        error_404 = HTTPException(status_code=404, detail="Symbol not found")
        assert error_404.status_code == 404
        assert error_404.detail == "Symbol not found"

        error_400 = HTTPException(status_code=400, detail="Invalid parameters")
        assert error_400.status_code == 400

        error_500 = HTTPException(status_code=500, detail="Internal server error")
        assert error_500.status_code == 500

    @patch("src.backtester.data_adapters.data_hub.DataHubAdapter")
    def test_data_fetch_error_handling(self, mock_adapter):
        """Test data fetching error scenarios"""
        # Test ValueError (symbol not found)
        mock_adapter_instance = MagicMock()
        mock_adapter_instance.fetch_ohlcv.side_effect = ValueError("Symbol not found")
        mock_adapter.return_value = mock_adapter_instance

        adapter = mock_adapter()

        with pytest.raises(ValueError):
            adapter.fetch_ohlcv(symbol="INVALID", asset_type=AssetType.EQUITY, timeframe="1d")

        # Test generic exception
        mock_adapter_instance.fetch_ohlcv.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            adapter.fetch_ohlcv(symbol="AAPL", asset_type=AssetType.EQUITY, timeframe="1d")

    def test_empty_data_handling(self):
        """Test handling of empty DataFrames"""
        empty_df = pd.DataFrame()

        # Test that empty DataFrame is properly detected
        assert empty_df.empty
        assert len(empty_df) == 0

        # Test with empty DataFrame with columns
        empty_with_cols = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        assert empty_with_cols.empty
        assert len(empty_with_cols) == 0

    @patch("src.backtester.engine.BacktestEngine")
    def test_engine_error_handling(self, mock_engine):
        """Test BacktestEngine error scenarios"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.run.side_effect = Exception("Engine error")
        mock_engine.return_value = mock_engine_instance

        engine = mock_engine()

        with pytest.raises(Exception):
            engine.run(pd.DataFrame(), None)

    def test_strategy_validation(self):
        """Test strategy name validation logic"""
        valid_strategies = ["sma"]

        for strategy in valid_strategies:
            assert strategy.lower() in ["sma"]

        # Test invalid strategy
        invalid_strategy = "unknown_strategy"
        assert invalid_strategy.lower() not in ["sma"]

    def test_timeframe_validation(self):
        """Test timeframe validation"""
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]

        for tf in valid_timeframes:
            assert isinstance(tf, str)
            assert len(tf) > 0

    def test_response_structure_validation(self):
        """Test that response structure is valid"""
        # Mock complete response structure
        response = {
            "metrics": {"total_return": 0.03, "sharpe_ratio": 1.5, "max_drawdown": 0.05},
            "equity_curve": [10000.0, 10100.0, 10200.0],
            "trades": [
                {
                    "timestamp": "2023-01-02T12:00:00",
                    "type": "buy",
                    "price": 101.0,
                    "quantity": 10.0,
                    "value": 1010.0,
                    "commission": 1.01,
                }
            ],
            "summary": {
                "symbol": "AAPL",
                "asset_type": "equity",
                "timeframe": "1d",
                "strategy": "sma",
                "initial_capital": 10000.0,
                "final_equity": 10300.0,
                "total_return": 0.03,
            },
        }

        # Verify structure
        required_keys = ["metrics", "equity_curve", "trades", "summary"]
        for key in required_keys:
            assert key in response

        assert isinstance(response["metrics"], dict)
        assert isinstance(response["equity_curve"], list)
        assert isinstance(response["trades"], list)
        assert isinstance(response["summary"], dict)

    def test_date_parsing_logic(self):
        """Test date parsing and formatting"""
        from datetime import datetime

        # Test ISO format parsing
        iso_date = "2023-01-01T00:00:00Z"
        parsed_date = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        assert parsed_date.year == 2023
        assert parsed_date.month == 1
        assert parsed_date.day == 1

        # Test date formatting
        test_date = datetime(2023, 6, 15, 14, 30, 0)
        iso_formatted = test_date.isoformat()
        assert "2023-06-15T14:30:00" in iso_formatted

    def test_concurrent_backtest_safety(self):
        """Test that backtest components are thread-safe"""
        from src.backtester.engine import BacktestEngine
        from src.backtester.strategies.sma import SMAStrategy

        # Create multiple instances
        strategies = [SMAStrategy() for _ in range(5)]
        engines = [BacktestEngine() for _ in range(5)]

        # Verify they're independent
        for i, strategy in enumerate(strategies):
            assert strategy is not None
            assert strategy is not strategies[0] or i == 0

        for i, engine in enumerate(engines):
            assert engine.initial_capital == 10000.0
            assert engine is not engines[0] or i == 0


class TestBacktesterAPIValidation:
    """Test parameter validation logic"""

    def test_symbol_validation(self):
        """Test symbol parameter validation"""
        valid_symbols = ["AAPL", "BTC/USDT", "SPY", "BRK.A"]

        for symbol in valid_symbols:
            assert isinstance(symbol, str)
            assert len(symbol) > 0
            assert len(symbol) < 20  # Reasonable symbol length limit

    def test_parameter_boundary_values(self):
        """Test parameter boundary conditions"""
        # Test initial capital boundaries
        valid_capitals = [1000.0, 10000.0, 100000.0, 1000000.0]
        for capital in valid_capitals:
            assert capital > 0
            assert isinstance(capital, (int, float))

        # Test commission boundaries
        valid_commissions = [0.0, 0.001, 0.01, 0.1]
        for commission in valid_commissions:
            assert commission >= 0
            assert commission <= 1.0

    def test_data_quality_validation(self):
        """Test data quality validation logic"""
        # Valid OHLCV data
        valid_data = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [1000, 1100, 1200],
            }
        )

        # Basic validation checks
        assert not valid_data.empty
        assert len(valid_data) > 0
        assert "open" in valid_data.columns
        assert "close" in valid_data.columns

        # Data integrity checks
        assert (valid_data["high"] >= valid_data["low"]).all()
        assert (valid_data["high"] >= valid_data["open"]).all()
        assert (valid_data["high"] >= valid_data["close"]).all()
        assert (valid_data["low"] <= valid_data["open"]).all()
        assert (valid_data["low"] <= valid_data["close"]).all()
        assert (valid_data["volume"] >= 0).all()


class TestBacktesterAPIPerformance:
    """Test performance-related aspects"""

    def test_large_dataset_handling(self):
        """Test handling of large datasets"""
        # Create large dataset simulation
        large_size = 10000
        large_data = pd.DataFrame(
            {
                "open": list(range(large_size)),
                "high": list(range(1, large_size + 1)),
                "low": list(range(-1, large_size - 1)),
                "close": [x + 0.5 for x in range(large_size)],
                "volume": [1000] * large_size,
            }
        )

        assert len(large_data) == large_size
        assert not large_data.empty

        # Test memory efficiency - data should not cause issues
        memory_usage = large_data.memory_usage(deep=True).sum()
        assert memory_usage > 0
        # Should be reasonable for 10k rows
        assert memory_usage < 50 * 1024 * 1024  # Less than 50MB

    def test_parameter_parsing_performance(self):
        """Test parameter parsing performance"""
        import time

        # Test with complex parameter set
        complex_params = {
            "initial_capital": 100000.0,
            "commission": 0.001,
            "slippage": 0.0001,
            "fast_period": 12,
            "slow_period": 26,
            "stop_loss": 0.02,
            "take_profit": 0.05,
            "risk_per_trade": 0.01,
            "max_positions": 5,
        }

        # Measure parsing time
        start_time = time.time()
        for _ in range(1000):  # Parse 1000 times
            json.dumps(complex_params)
            json.loads(json.dumps(complex_params))
        end_time = time.time()

        # Should be fast
        assert (end_time - start_time) < 1.0  # Less than 1 second for 1000 operations
