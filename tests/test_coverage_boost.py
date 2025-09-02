"""Coverage boost tests for existing modules."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import pandas as pd
import numpy as np


class TestCoreModules:
    """Test core modules for coverage."""
    
    def test_portfolio_basic(self):
        """Test portfolio module."""
        from src.core.portfolio import Portfolio
        
        portfolio = Portfolio(initial_capital=10000, cash_balance=10000)
        assert portfolio.total_value == 10000
        assert portfolio.cash_balance == 10000
        
        # Add position
        portfolio.add_position("BTC/USDT", 0.1, 50000)
        assert "BTC/USDT" in portfolio.positions
    
    def test_order_manager_basic(self):
        """Test order manager."""
        from src.core.order_manager import OrderManager, OrderSide, OrderType
        
        manager = OrderManager()
        
        # Create order
        order = manager.create_order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1
        )
        
        assert order.symbol == "BTC/USDT"
        assert order.side == OrderSide.BUY
        assert order.quantity == 0.1
    
    def test_position_manager_basic(self):
        """Test position manager."""
        from src.core.position_manager import PositionManager
        
        manager = PositionManager()
        
        # Open position
        position = manager.open_position(
            symbol="BTC/USDT",
            side="long",
            quantity=0.1,
            entry_price=50000
        )
        
        assert position.symbol == "BTC/USDT"
        assert position.quantity == 0.1
    
    def test_risk_manager_basic(self):
        """Test risk manager."""
        from src.core.risk_manager import RiskManager, RiskParameters
        
        params = RiskParameters(
            max_position_size=0.1,
            max_daily_loss=0.02
        )
        
        manager = RiskManager(params)
        manager.update_portfolio_value(10000)
        
        # Check position size
        allowed, msg = manager.check_position_size(500, 10000)
        assert allowed  # 5% < 10% limit
    
    def test_indicators_calculation(self):
        """Test indicator calculations."""
        from src.metrics.indicators import calculate_sma, calculate_rsi, calculate_bollinger_bands
        
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109])
        
        # SMA
        sma = calculate_sma(prices, period=3)
        assert len(sma) == len(prices)
        assert not pd.isna(sma.iloc[-1])
        
        # RSI
        rsi = calculate_rsi(prices, period=5)
        assert len(rsi) == len(prices)
        assert 0 <= rsi.iloc[-1] <= 100
        
        # Bollinger Bands
        upper, middle, lower = calculate_bollinger_bands(prices, period=5)
        assert upper.iloc[-1] > middle.iloc[-1] > lower.iloc[-1]


class TestBacktestModules:
    """Test backtest modules."""
    
    def test_sma_strategy(self):
        """Test SMA strategy."""
        from src.backtest.strategies.sma import SMAStrategy
        
        # Create test data
        data = pd.DataFrame({
            'close': [100 + i for i in range(50)]
        })
        
        strategy = SMAStrategy()
        signals = strategy.generate_signals(data, fast_period=5, slow_period=10)
        
        assert len(signals) == len(data)
        assert all(s in [-1, 0, 1] for s in signals)
    
    def test_backtest_metrics(self):
        """Test backtest metrics calculation."""
        from src.backtest.metrics import calculate_sharpe_ratio, calculate_max_drawdown
        
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.015, 0.025])
        
        # Sharpe ratio
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0)
        assert isinstance(sharpe, (int, float))
        
        # Max drawdown
        equity = pd.Series([10000, 10100, 9900, 10200, 10100, 10300, 10150, 10400])
        dd = calculate_max_drawdown(equity)
        assert dd < 0  # Drawdown is negative
        assert -1 <= dd <= 0  # Between -100% and 0%
    
    def test_strategy_registry(self):
        """Test strategy registry."""
        from src.backtest.strategies.registry import StrategyRegistry
        
        registry = StrategyRegistry()
        
        # List strategies
        strategies = registry.list_strategy_names()
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        # Get strategy
        if 'sma' in strategies:
            strategy = registry.get_strategy('sma')
            assert strategy is not None
            assert hasattr(strategy, 'generate_signals')


class TestAPIEndpoints:
    """Test API endpoints with mocks."""
    
    @pytest.fixture
    def client(self):
        from src.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus format text
        assert "# HELP" in response.text or "# TYPE" in response.text or len(response.text) > 0
    
    @patch('src.services.datahub.datahub.get_ohlcv')
    def test_quotes_endpoint(self, mock_get, client):
        """Test quotes endpoint."""
        mock_get.return_value = [
            [1704067200000, 50000, 50500, 49500, 50200, 1000]
        ]
        
        response = client.get("/api/quotes/ohlcv", params={
            "symbol": "BTC/USDT",
            "tf": "1h"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestDataHub:
    """Test DataHub service."""
    
    @patch('src.services.datahub.yf.Ticker')
    def test_datahub_yfinance(self, mock_ticker):
        """Test DataHub with yfinance."""
        from src.services.datahub import DataHub
        
        # Mock yfinance response
        mock_history = pd.DataFrame({
            'Open': [50000],
            'High': [50500],
            'Low': [49500],
            'Close': [50200],
            'Volume': [1000]
        }, index=pd.DatetimeIndex(['2024-01-01']))
        
        mock_ticker.return_value.history.return_value = mock_history
        
        hub = DataHub()
        data = hub._fetch_yfinance("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        
        assert len(data) == 1
        assert data[0][4] == 50200  # close price
    
    @patch('src.services.datahub.requests.get')
    def test_datahub_binance(self, mock_get):
        """Test DataHub Binance fallback."""
        from src.services.datahub import DataHub
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [1704067200000, "50000", "50500", "49500", "50200", "1000"]
        ]
        mock_get.return_value = mock_response
        
        hub = DataHub()
        data = hub._fetch_binance("BTC/USDT", "1h", "2024-01-01", "2024-01-02")
        
        assert len(data) == 1
        assert data[0][4] == 50200.0