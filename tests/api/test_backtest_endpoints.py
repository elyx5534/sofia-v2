"""Comprehensive tests for backtest API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json


class TestBacktestEndpoints:
    """Test all backtest API endpoints."""
    
    @pytest.fixture
    def client(self):
        from src.api.main import app
        return TestClient(app)
    
    @patch('src.services.backtester.backtester')
    def test_backtest_run_endpoint(self, mock_backtester, client):
        """Test /api/backtest/run endpoint."""
        mock_backtester.run_backtest.return_value = {
            "run_id": "test-run-123",
            "equity_curve": [[0, 10000], [1, 10100], [2, 10050]],
            "drawdown": [[0, 0], [1, -0.01], [2, -0.005]],
            "trades": [
                {"timestamp": 1, "side": "buy", "price": 50000, "quantity": 0.1},
                {"timestamp": 2, "side": "sell", "price": 50500, "quantity": 0.1}
            ],
            "stats": {
                "total_return": 0.005,
                "sharpe_ratio": 1.2,
                "max_drawdown": -0.01,
                "win_rate": 0.6
            }
        }
        
        response = client.post("/api/backtest/run", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "strategy": "sma_cross",
            "params": {"fast_period": 10, "slow_period": 20}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "test-run-123"
        assert len(data["equity_curve"]) == 3
        assert data["stats"]["sharpe_ratio"] == 1.2
    
    @patch('src.services.backtester.backtester')
    def test_backtest_grid_endpoint(self, mock_backtester, client):
        """Test /api/backtest/grid endpoint."""
        mock_backtester.run_grid_search.return_value = {
            "best_params": {"fast_period": 10, "slow_period": 25},
            "best_sharpe": 1.5,
            "all_results": [
                {"params": {"fast_period": 10, "slow_period": 20}, "sharpe": 1.2},
                {"params": {"fast_period": 10, "slow_period": 25}, "sharpe": 1.5},
                {"params": {"fast_period": 15, "slow_period": 20}, "sharpe": 0.9},
                {"params": {"fast_period": 15, "slow_period": 25}, "sharpe": 1.1}
            ],
            "optimization_stats": {
                "total_combinations": 4,
                "time_elapsed": 5.2
            }
        }
        
        response = client.post("/api/backtest/grid", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "strategy": "sma_cross",
            "param_grid": {
                "fast_period": [10, 15],
                "slow_period": [20, 25]
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["best_sharpe"] == 1.5
        assert data["best_params"]["fast_period"] == 10
        assert len(data["all_results"]) == 4
    
    @patch('src.services.backtester.backtester')
    def test_backtest_ga_endpoint(self, mock_backtester, client):
        """Test /api/backtest/ga endpoint."""
        mock_backtester.run_genetic_algorithm.return_value = {
            "best_params": {"fast_period": 12, "slow_period": 23},
            "best_fitness": 1.8,
            "generation_history": [
                {"generation": 0, "best_fitness": 1.2, "avg_fitness": 0.8},
                {"generation": 1, "best_fitness": 1.5, "avg_fitness": 1.0},
                {"generation": 2, "best_fitness": 1.8, "avg_fitness": 1.3}
            ],
            "convergence_plot": [[0, 1.2], [1, 1.5], [2, 1.8]]
        }
        
        response = client.post("/api/backtest/ga", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "strategy": "sma_cross",
            "param_ranges": {
                "fast_period": [5, 15],
                "slow_period": [15, 30]
            },
            "population_size": 10,
            "generations": 3,
            "elite_size": 2
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["best_fitness"] == 1.8
        assert len(data["generation_history"]) == 3
        assert data["best_params"]["fast_period"] == 12
    
    @patch('src.services.backtester.backtester')
    def test_backtest_wfo_endpoint(self, mock_backtester, client):
        """Test /api/backtest/wfo endpoint."""
        mock_backtester.run_walk_forward.return_value = {
            "splits": [
                {"train_sharpe": 1.2, "test_sharpe": 1.1, "best_params": {"fast_period": 10, "slow_period": 20}},
                {"train_sharpe": 1.3, "test_sharpe": 1.0, "best_params": {"fast_period": 12, "slow_period": 22}},
                {"train_sharpe": 1.4, "test_sharpe": 1.2, "best_params": {"fast_period": 11, "slow_period": 21}}
            ],
            "oos_sharpe": 1.1,
            "best_params_per_split": [
                {"fast_period": 10, "slow_period": 20},
                {"fast_period": 12, "slow_period": 22},
                {"fast_period": 11, "slow_period": 21}
            ],
            "stability_score": 0.85
        }
        
        response = client.post("/api/backtest/wfo", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-10",
            "strategy": "sma_cross",
            "param_grid": {
                "fast_period": [10, 12],
                "slow_period": [20, 22]
            },
            "n_splits": 3,
            "train_ratio": 0.7
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["oos_sharpe"] == 1.1
        assert len(data["splits"]) == 3
        assert data["stability_score"] == 0.85
    
    def test_backtest_invalid_strategy(self, client):
        """Test backtest with invalid strategy."""
        response = client.post("/api/backtest/run", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-01-02",
            "strategy": "non_existent_strategy",
            "params": {}
        })
        
        assert response.status_code in [400, 500]
        
    def test_backtest_missing_params(self, client):
        """Test backtest with missing required params."""
        response = client.post("/api/backtest/run", json={
            "symbol": "BTC/USDT",
            "timeframe": "1h"
            # Missing start, end, strategy
        })
        
        assert response.status_code == 422  # Validation error