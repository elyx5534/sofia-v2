"""
Test suite for Auto Trading Module
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.auto_trader import AutoTrader, RiskLevel, TradeAction


class TestAutoTrader:
    """Test Auto Trader functionality"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            "initial_balance": 100000,
            "max_position_size": 0.1,
            "risk_per_trade": 0.02,
            "stop_loss": 0.05,
            "take_profit": 0.15,
            "alert_api": "http://localhost:8010",
            "trading_api": "http://localhost:8003",
        }

    @pytest.fixture
    def auto_trader(self, config):
        """Create auto trader instance"""
        return AutoTrader(config)

    @pytest.fixture
    def sample_alert(self):
        """Sample alert signal"""
        return {
            "id": "test_123",
            "action": "momentum_long",
            "severity": "high",
            "message": "Positive news: BTC ETF approved",
            "source": "finnhub",
            "timestamp": datetime.now().isoformat(),
        }

    def test_initialization(self, auto_trader, config):
        """Test auto trader initialization"""
        assert auto_trader.portfolio_balance == config["initial_balance"]
        assert auto_trader.max_position_size == config["max_position_size"]
        assert auto_trader.risk_per_trade == config["risk_per_trade"]
        assert len(auto_trader.active_trades) == 0
        assert len(auto_trader.trade_history) == 0

    def test_calculate_position_size(self, auto_trader):
        """Test position size calculation"""
        # Test different risk levels
        size_low = auto_trader.calculate_position_size(RiskLevel.LOW)
        size_medium = auto_trader.calculate_position_size(RiskLevel.MEDIUM)
        size_high = auto_trader.calculate_position_size(RiskLevel.HIGH)

        assert size_low < size_medium < size_high
        assert size_low > 0
        assert size_high <= auto_trader.portfolio_balance * auto_trader.max_position_size

    def test_extract_symbol_from_alert(self, auto_trader):
        """Test symbol extraction from alert"""
        # Test with BTC in message
        alert1 = {"message": "BTC price surging"}
        assert auto_trader.extract_symbol_from_alert(alert1) == "BTC/USDT"

        # Test with ETH in message
        alert2 = {"message": "ETH breaking resistance"}
        assert auto_trader.extract_symbol_from_alert(alert2) == "ETH/USDT"

        # Test with no symbol
        alert3 = {"message": "Market looking bullish"}
        assert auto_trader.extract_symbol_from_alert(alert3) is None

        # Test with data field
        alert4 = {"message": "Price alert", "data": {"coins": [{"symbol": "SOL"}]}}
        assert auto_trader.extract_symbol_from_alert(alert4) == "SOL/USDT"

    def test_should_execute_trade(self, auto_trader):
        """Test trade execution conditions"""
        trade = {"symbol": "BTC/USDT", "action": "buy", "position_size": 5000}

        # Should execute when no active trades
        assert auto_trader.should_execute_trade(trade) is True

        # Add to active trades
        auto_trader.active_trades["BTC/USDT"] = trade

        # Should not execute opposite direction
        opposite_trade = trade.copy()
        opposite_trade["action"] = "sell"
        assert auto_trader.should_execute_trade(opposite_trade) is False

        # Test max exposure limit
        large_trade = {
            "symbol": "ETH/USDT",
            "action": "buy",
            "position_size": 60000,  # Over 50% of portfolio
        }
        assert auto_trader.should_execute_trade(large_trade) is False

    @pytest.mark.asyncio
    async def test_process_alert_signal(self, auto_trader, sample_alert):
        """Test processing alert signals"""
        with patch.object(auto_trader, "execute_trade", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "trade": {}}

            result = await auto_trader.process_alert_signal(sample_alert)

            assert result is not None
            mock_execute.assert_called_once()

            # Check the trade that was created
            call_args = mock_execute.call_args[0][0]
            assert call_args["action"] == TradeAction.BUY.value
            assert call_args["symbol"] == "BTC/USDT"
            assert call_args["risk_level"] == RiskLevel.HIGH.value

    @pytest.mark.asyncio
    async def test_execute_trade(self, auto_trader):
        """Test trade execution"""
        trade = {
            "symbol": "BTC/USDT",
            "action": "buy",
            "position_size": 5000,
            "stop_loss": 0.05,
            "take_profit": 0.15,
        }

        # Mock HTTP client
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "executed"}

            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await auto_trader.execute_trade(trade)

            assert result["success"] is True
            assert "BTC/USDT" in auto_trader.active_trades
            assert len(auto_trader.trade_history) == 1

    @pytest.mark.asyncio
    async def test_get_current_price(self, auto_trader):
        """Test getting current price"""
        # Test with API response
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"price": 96000}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            price = await auto_trader.get_current_price("BTC/USDT")
            assert price == 96000

        # Test default price fallback
        with patch("httpx.AsyncClient", side_effect=Exception("Connection error")):
            price = await auto_trader.get_current_price("BTC/USDT")
            assert price == 95000  # Default BTC price

    @pytest.mark.asyncio
    async def test_close_position(self, auto_trader):
        """Test closing position"""
        # Add active trade
        auto_trader.active_trades["BTC/USDT"] = {
            "symbol": "BTC/USDT",
            "position_size": 0.1,
            "entry_price": 95000,
        }

        with patch.object(auto_trader, "get_current_price", new_callable=AsyncMock) as mock_price:
            mock_price.return_value = 100000  # Price went up

            await auto_trader.close_position("BTC/USDT", "take_profit")

            assert "BTC/USDT" not in auto_trader.active_trades
            assert auto_trader.portfolio_balance > 100000  # Made profit

    def test_get_stats(self, auto_trader):
        """Test statistics calculation"""
        # Add some trades
        auto_trader.trade_history = [{"pnl": 1000}, {"pnl": -500}, {"pnl": 2000}]

        auto_trader.active_trades = {
            "BTC/USDT": {"position_size": 10000},
            "ETH/USDT": {"position_size": 5000},
        }

        stats = auto_trader.get_stats()

        assert stats["total_trades"] == 3
        assert stats["active_positions"] == 2
        assert stats["total_pnl"] == 2500
        assert stats["win_rate"] == 2 / 3
        assert stats["total_exposure"] == 15000


class TestTradeAction:
    """Test TradeAction enum"""

    def test_trade_actions(self):
        """Test trade action values"""
        assert TradeAction.BUY.value == "buy"
        assert TradeAction.SELL.value == "sell"
        assert TradeAction.HOLD.value == "hold"
        assert TradeAction.CLOSE.value == "close"
        assert TradeAction.HEDGE.value == "hedge"


class TestRiskLevel:
    """Test RiskLevel enum"""

    def test_risk_levels(self):
        """Test risk level values"""
        assert RiskLevel.LOW.value == 0.01
        assert RiskLevel.MEDIUM.value == 0.02
        assert RiskLevel.HIGH.value == 0.05
        assert RiskLevel.CRITICAL.value == 0.1


@pytest.mark.asyncio
async def test_monitor_positions():
    """Test position monitoring"""
    config = {
        "initial_balance": 100000,
        "max_position_size": 0.1,
        "risk_per_trade": 0.02,
        "stop_loss": 0.05,
        "take_profit": 0.15,
    }

    auto_trader = AutoTrader(config)

    # Add a position
    auto_trader.active_trades["BTC/USDT"] = {
        "symbol": "BTC/USDT",
        "entry_price": 100000,
        "stop_loss": 0.05,
        "take_profit": 0.15,
        "position_size": 0.1,
    }

    with patch.object(auto_trader, "get_current_price", new_callable=AsyncMock) as mock_price:
        # Simulate price hitting stop loss
        mock_price.return_value = 94000  # 6% loss

        with patch.object(auto_trader, "close_position", new_callable=AsyncMock) as mock_close:
            # Run monitor for one iteration
            monitor_task = asyncio.create_task(auto_trader.monitor_positions())
            await asyncio.sleep(0.1)
            monitor_task.cancel()

            # Should have called close_position
            mock_close.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
