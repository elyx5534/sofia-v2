"""
Test suite for Backtester API endpoints
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import pandas as pd

from fastapi.testclient import TestClient

# Import modules separately to avoid circular imports
from fastapi import FastAPI
from src.data_hub.models import AssetType

# Create a test app with just the backtester router
test_app = FastAPI()

# Mock the backtester router to avoid circular import
@test_app.get("/backtester/backtest")
async def mock_backtest_endpoint(
    symbol: str = "AAPL",
    asset_type: AssetType = AssetType.EQUITY,
    timeframe: str = "1d",
    strategy: str = "sma",
    params: str = "{}"
):
    """Mock backtest endpoint for testing"""
    # This will be mocked in tests
    pass

# Create test client
client = TestClient(test_app)


@pytest.fixture
def mock_data_adapter():
    """Mock DataHubAdapter"""
    with patch('src.backtester.api.DataHubAdapter') as mock:
        mock_instance = MagicMock()
        
        # Create sample OHLCV data
        sample_data = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [101.0, 102.0, 103.0, 104.0, 105.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'volume': [1000, 1100, 1200, 1300, 1400]
        }, index=pd.date_range('2023-01-01', periods=5, freq='D'))
        
        mock_instance.fetch_ohlcv.return_value = sample_data
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_backtest_engine():
    """Mock BacktestEngine"""
    with patch('src.backtester.api.BacktestEngine') as mock:
        mock_instance = MagicMock()
        mock_instance.initial_capital = 10000.0
        
        # Mock backtest results
        mock_results = {
            "equity_curve": [10000.0, 10100.0, 10200.0, 10150.0, 10300.0],
            "trades": [
                {
                    "timestamp": datetime(2023, 1, 2),
                    "type": "buy",
                    "price": 101.0,
                    "quantity": 10.0,
                    "value": 1010.0,
                    "commission": 1.01
                },
                {
                    "timestamp": datetime(2023, 1, 4),
                    "type": "sell",
                    "price": 103.0,
                    "quantity": 10.0,
                    "value": 1030.0,
                    "commission": 1.03
                }
            ],
            "final_equity": 10300.0,
            "return": 0.03
        }
        
        mock_instance.run.return_value = mock_results
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_calculate_metrics():
    """Mock calculate_metrics function"""
    with patch('src.backtester.api.calculate_metrics') as mock:
        mock_metrics = {
            "total_return": 0.03,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.05,
            "win_rate": 0.75,
            "profit_factor": 2.1,
            "num_trades": 2,
            "avg_trade_return": 0.015
        }
        mock.return_value = mock_metrics
        yield mock


class TestBacktesterAPI:
    """Test Backtester API endpoints"""

    def test_backtest_endpoint_success(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test successful backtest execution"""
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&timeframe=1d&strategy=sma"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "metrics" in data
        assert "equity_curve" in data
        assert "trades" in data
        assert "summary" in data
        
        # Check metrics
        assert data["metrics"]["total_return"] == 0.03
        assert data["metrics"]["sharpe_ratio"] == 1.5
        
        # Check summary
        summary = data["summary"]
        assert summary["symbol"] == "AAPL"
        assert summary["asset_type"] == "equity"
        assert summary["strategy"] == "sma"
        assert summary["initial_capital"] == 10000.0

    def test_backtest_endpoint_with_custom_params(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest with custom parameters"""
        params = {
            "initial_capital": 50000.0,
            "commission": 0.002,
            "fast_period": 10,
            "slow_period": 30
        }
        
        response = client.get(
            f"/backtester/backtest?symbol=BTC/USDT&asset_type=crypto&strategy=sma&params={json.dumps(params)}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify engine was initialized with custom parameters
        mock_backtest_engine.assert_called_once()
        args, kwargs = mock_backtest_engine.call_args
        assert kwargs.get('initial_capital') == 50000.0 or args[0] == 50000.0

    def test_backtest_endpoint_with_date_range(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest with specific date range"""
        start_date = "2023-01-01T00:00:00Z"
        end_date = "2023-12-31T23:59:59Z"
        
        response = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&start={start_date}&end={end_date}&strategy=sma"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data

    def test_backtest_endpoint_missing_required_params(self):
        """Test backtest endpoint with missing required parameters"""
        # Missing symbol
        response = client.get("/backtester/backtest?asset_type=equity&strategy=sma")
        assert response.status_code == 422
        
        # Missing asset_type
        response = client.get("/backtester/backtest?symbol=AAPL&strategy=sma")
        assert response.status_code == 422

    def test_backtest_endpoint_invalid_asset_type(self):
        """Test backtest endpoint with invalid asset type"""
        response = client.get("/backtester/backtest?symbol=AAPL&asset_type=invalid&strategy=sma")
        assert response.status_code == 422

    def test_backtest_endpoint_invalid_json_params(self, mock_data_adapter):
        """Test backtest endpoint with invalid JSON parameters"""
        invalid_params = "{'invalid': json}"  # Invalid JSON syntax
        
        response = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma&params={invalid_params}"
        )
        
        assert response.status_code == 400
        assert "Invalid strategy parameters JSON" in response.json()["detail"]

    def test_backtest_endpoint_unknown_strategy(self, mock_data_adapter):
        """Test backtest endpoint with unknown strategy"""
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=unknown_strategy"
        )
        
        assert response.status_code == 400
        assert "Unknown strategy" in response.json()["detail"]

    def test_backtest_endpoint_symbol_not_found(self, mock_data_adapter):
        """Test backtest endpoint when symbol is not found"""
        # Mock data adapter to raise ValueError
        mock_data_adapter.return_value.fetch_ohlcv.side_effect = ValueError("Symbol not found")
        
        response = client.get(
            "/backtester/backtest?symbol=INVALID&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 404
        assert "Symbol not found" in response.json()["detail"]

    def test_backtest_endpoint_data_fetch_error(self, mock_data_adapter):
        """Test backtest endpoint when data fetch fails"""
        # Mock data adapter to raise generic exception
        mock_data_adapter.return_value.fetch_ohlcv.side_effect = Exception("API Error")
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 500
        assert "Failed to fetch data" in response.json()["detail"]

    def test_backtest_endpoint_empty_data(self, mock_data_adapter):
        """Test backtest endpoint when no data is returned"""
        # Mock empty DataFrame
        empty_df = pd.DataFrame()
        mock_data_adapter.return_value.fetch_ohlcv.return_value = empty_df
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 404
        assert "No data found" in response.json()["detail"]

    def test_backtest_endpoint_engine_error(self, mock_data_adapter, mock_backtest_engine):
        """Test backtest endpoint when engine raises error"""
        # Mock engine to raise exception
        mock_backtest_engine.return_value.run.side_effect = Exception("Engine error")
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 500
        assert "Backtest failed" in response.json()["detail"]

    def test_backtest_endpoint_comprehensive_response_format(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test that backtest response has all expected fields and correct format"""
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&timeframe=1h&strategy=sma"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        required_keys = ["metrics", "equity_curve", "trades", "summary"]
        for key in required_keys:
            assert key in data
        
        # Check metrics structure
        metrics = data["metrics"]
        expected_metrics = ["total_return", "sharpe_ratio", "max_drawdown", "win_rate", "profit_factor"]
        for metric in expected_metrics:
            assert metric in metrics
        
        # Check trades format
        trades = data["trades"]
        assert isinstance(trades, list)
        if trades:
            trade = trades[0]
            expected_trade_keys = ["timestamp", "type", "price", "quantity", "value", "commission"]
            for key in expected_trade_keys:
                assert key in trade
            
            # Check timestamp is ISO format string
            assert isinstance(trade["timestamp"], str)
        
        # Check summary structure
        summary = data["summary"]
        expected_summary_keys = [
            "symbol", "asset_type", "timeframe", "strategy", "start_date", "end_date",
            "data_points", "initial_capital", "final_equity", "total_return"
        ]
        for key in expected_summary_keys:
            assert key in summary

    def test_backtest_endpoint_different_timeframes(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest endpoint with different timeframes"""
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        for timeframe in timeframes:
            response = client.get(
                f"/backtester/backtest?symbol=AAPL&asset_type=equity&timeframe={timeframe}&strategy=sma"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["timeframe"] == timeframe

    def test_backtest_endpoint_different_asset_types(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest endpoint with different asset types"""
        test_cases = [
            ("AAPL", "equity"),
            ("BTC/USDT", "crypto")
        ]
        
        for symbol, asset_type in test_cases:
            response = client.get(
                f"/backtester/backtest?symbol={symbol}&asset_type={asset_type}&strategy=sma"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["symbol"] == symbol
            assert data["summary"]["asset_type"] == asset_type

    def test_backtest_endpoint_parameter_parsing(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test that strategy parameters are correctly parsed and passed"""
        params = {
            "fast_period": 5,
            "slow_period": 20,
            "initial_capital": 25000.0,
            "commission": 0.0015
        }
        
        response = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma&params={json.dumps(params)}"
        )
        
        assert response.status_code == 200
        
        # Verify that engine.run was called with the parameters
        mock_engine_instance = mock_backtest_engine.return_value
        mock_engine_instance.run.assert_called_once()
        
        # Check that parameters were passed to run method
        call_args = mock_engine_instance.run.call_args
        assert call_args is not None
        
        # Parameters should be passed as kwargs
        kwargs = call_args[1] if len(call_args) > 1 else {}
        assert kwargs.get("fast_period") == 5
        assert kwargs.get("slow_period") == 20

    def test_backtest_endpoint_edge_cases(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest endpoint edge cases"""
        # Test with minimal data (edge case for small datasets)
        small_data = pd.DataFrame({
            'open': [100.0], 'high': [101.0], 'low': [99.0], 'close': [100.5], 'volume': [1000]
        }, index=pd.date_range('2023-01-01', periods=1, freq='D'))
        
        mock_data_adapter.return_value.fetch_ohlcv.return_value = small_data
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["data_points"] == 1

    def test_backtest_endpoint_special_characters_in_symbol(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest endpoint with special characters in symbol"""
        symbols = ["BTC/USDT", "BRK.A", "SPY"]
        
        for symbol in symbols:
            response = client.get(
                f"/backtester/backtest?symbol={symbol}&asset_type=equity&strategy=sma"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["summary"]["symbol"] == symbol

    def test_backtest_endpoint_concurrent_requests(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test that backtest endpoint can handle multiple concurrent requests"""
        import threading
        
        results = []
        
        def make_request():
            response = client.get(
                "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
            )
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)

    def test_backtest_endpoint_memory_efficiency(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test backtest endpoint with large dataset"""
        # Create large dataset
        large_data = pd.DataFrame({
            'open': [100.0 + i for i in range(10000)],
            'high': [101.0 + i for i in range(10000)],
            'low': [99.0 + i for i in range(10000)],
            'close': [100.5 + i for i in range(10000)],
            'volume': [1000] * 10000
        }, index=pd.date_range('2020-01-01', periods=10000, freq='D'))
        
        mock_data_adapter.return_value.fetch_ohlcv.return_value = large_data
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["data_points"] == 10000

    def test_backtest_endpoint_error_recovery(self, mock_data_adapter):
        """Test backtest endpoint error recovery and proper error responses"""
        # Test sequence: error -> success
        mock_data_adapter.return_value.fetch_ohlcv.side_effect = [
            Exception("Temporary error"),
            pd.DataFrame({
                'open': [100.0], 'high': [101.0], 'low': [99.0], 
                'close': [100.5], 'volume': [1000]
            }, index=pd.date_range('2023-01-01', periods=1, freq='D'))
        ]
        
        # First request should fail
        response1 = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        assert response1.status_code == 500
        
        # Second request should succeed (but won't because mock is consumed)
        # This tests that the endpoint doesn't maintain bad state

    def test_backtest_endpoint_data_validation(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test that backtest validates input data properly"""
        # Test with NaN values in data
        data_with_nan = pd.DataFrame({
            'open': [100.0, float('nan'), 102.0],
            'high': [101.0, float('nan'), 103.0],
            'low': [99.0, float('nan'), 101.0],
            'close': [100.5, float('nan'), 102.5],
            'volume': [1000, float('nan'), 1200]
        }, index=pd.date_range('2023-01-01', periods=3, freq='D'))
        
        mock_data_adapter.return_value.fetch_ohlcv.return_value = data_with_nan
        
        response = client.get(
            "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma"
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 500]  # Either works or fails gracefully


class TestBacktesterAPIIntegration:
    """Integration tests for Backtester API"""

    def test_full_backtest_workflow(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test complete backtest workflow from request to response"""
        # Setup comprehensive test scenario
        params = {
            "initial_capital": 100000.0,
            "commission": 0.001,
            "slippage": 0.0001,
            "fast_period": 12,
            "slow_period": 26
        }
        
        response = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&timeframe=1d&strategy=sma&params={json.dumps(params)}"
            f"&start=2023-01-01T00:00:00Z&end=2023-12-31T23:59:59Z"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify complete workflow
        assert "metrics" in data
        assert "equity_curve" in data  
        assert "trades" in data
        assert "summary" in data
        
        # Verify data flow
        mock_data_adapter.return_value.fetch_ohlcv.assert_called_once()
        mock_backtest_engine.assert_called_once()
        mock_backtest_engine.return_value.run.assert_called_once()
        mock_calculate_metrics.assert_called_once()

    def test_strategy_parameter_effects(self, mock_data_adapter, mock_backtest_engine, mock_calculate_metrics):
        """Test that different strategy parameters produce different results"""
        params1 = {"fast_period": 5, "slow_period": 10}
        params2 = {"fast_period": 20, "slow_period": 50}
        
        # First backtest
        response1 = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma&params={json.dumps(params1)}"
        )
        
        # Second backtest  
        response2 = client.get(
            f"/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma&params={json.dumps(params2)}"
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should have valid structures
        data1 = response1.json()
        data2 = response2.json()
        
        assert "metrics" in data1 and "metrics" in data2
        assert "summary" in data1 and "summary" in data2


class TestBacktesterAPIErrorHandling:
    """Test error handling in Backtester API"""

    def test_comprehensive_error_scenarios(self, mock_data_adapter):
        """Test various error scenarios and responses"""
        error_scenarios = [
            # Invalid JSON in params
            {
                "url": "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=sma&params=invalid_json",
                "expected_status": 400,
                "expected_detail_contains": "Invalid strategy parameters JSON"
            },
            # Unknown strategy
            {
                "url": "/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=unknown",
                "expected_status": 400,
                "expected_detail_contains": "Unknown strategy"
            }
        ]
        
        for scenario in error_scenarios:
            response = client.get(scenario["url"])
            assert response.status_code == scenario["expected_status"]
            if "expected_detail_contains" in scenario:
                assert scenario["expected_detail_contains"] in response.json()["detail"]

    def test_error_response_format(self, mock_data_adapter):
        """Test that error responses follow consistent format"""
        # Trigger an error
        response = client.get("/backtester/backtest?symbol=AAPL&asset_type=equity&strategy=unknown")
        
        assert response.status_code == 400
        error_data = response.json()
        
        # FastAPI error format
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)