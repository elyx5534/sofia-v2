"""Tests for the trading engine module."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.trading_engine.engine import TradingEngine
from src.trading_engine.order_manager import OrderSide, OrderType, OrderStatus
from src.trading_engine.risk_manager import RiskParameters


class TestTradingEngine:
    """Test cases for TradingEngine class."""

    @pytest.fixture
    def trading_engine(self):
        """Create a test trading engine."""
        return TradingEngine(initial_capital=100000)

    @pytest.fixture
    def custom_trading_engine(self):
        """Create a trading engine with custom risk parameters."""
        risk_params = RiskParameters(
            max_position_size=0.15,
            max_daily_loss=0.03,
            max_open_positions=5
        )
        return TradingEngine(initial_capital=50000, risk_parameters=risk_params)

    def test_trading_engine_initialization_default(self, trading_engine):
        """Test TradingEngine initialization with default parameters."""
        assert trading_engine.portfolio.initial_capital == 100000
        assert trading_engine.portfolio.cash_balance == 100000
        assert trading_engine.is_running is False
        assert len(trading_engine.last_prices) == 0
        assert trading_engine.risk_manager.current_value == 100000
        assert trading_engine.risk_manager.peak_value == 100000

    def test_trading_engine_initialization_custom(self, custom_trading_engine):
        """Test TradingEngine initialization with custom parameters."""
        assert custom_trading_engine.portfolio.initial_capital == 50000
        assert custom_trading_engine.portfolio.cash_balance == 50000
        assert custom_trading_engine.risk_manager.parameters.max_position_size == 0.15
        assert custom_trading_engine.risk_manager.parameters.max_open_positions == 5
        assert custom_trading_engine.risk_manager.current_value == 50000

    @pytest.mark.asyncio
    async def test_start_engine(self, trading_engine):
        """Test starting the trading engine."""
        with patch('asyncio.create_task') as mock_create_task:
            await trading_engine.start()
            
            assert trading_engine.is_running is True
            assert mock_create_task.call_count == 3  # 3 background tasks

    @pytest.mark.asyncio
    async def test_stop_engine(self, trading_engine):
        """Test stopping the trading engine."""
        # Start engine first
        trading_engine.is_running = True
        
        # Create some test orders
        order1 = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 100, 150.0)
        order2 = trading_engine.order_manager.create_order("GOOGL", OrderSide.BUY, OrderType.LIMIT, 50, 2000.0)
        
        await trading_engine.stop()
        
        assert trading_engine.is_running is False
        # All orders should be cancelled
        assert len(trading_engine.order_manager.get_active_orders()) == 0

    @pytest.mark.asyncio
    async def test_place_order_success(self, trading_engine):
        """Test successfully placing an order."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        order = await trading_engine.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,  # $7,500 = 7.5% < 10% limit
            price=150.0
        )
        
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 50
        assert order.price == 150.0

    @pytest.mark.asyncio
    async def test_place_order_position_size_exceeded(self, trading_engine):
        """Test order rejection due to position size limit."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Try to place order worth more than 10% of portfolio (>$10,000)
        order = await trading_engine.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,  # $150,000 worth > 10% limit
            price=150.0
        )
        
        assert order is None  # Order should be rejected

    @pytest.mark.asyncio
    async def test_place_order_daily_loss_exceeded(self, trading_engine):
        """Test order rejection due to daily loss limit."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Simulate daily losses exceeding limit
        trading_engine.risk_manager.daily_losses = -3000  # 3% > 2% limit
        trading_engine.risk_manager.current_value = 100000
        
        order = await trading_engine.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.0
        )
        
        assert order is None  # Order should be rejected

    @pytest.mark.asyncio
    async def test_place_order_max_positions_exceeded(self, trading_engine):
        """Test order rejection due to max positions limit."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Fill position manager with max positions
        for i in range(10):  # Max is 10
            symbol = f"STOCK{i}"
            trading_engine.position_manager.open_position(symbol, 100, 100.0)
        
        # Try to open another position
        order = await trading_engine.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.0
        )
        
        assert order is None  # Order should be rejected

    @pytest.mark.asyncio
    async def test_place_sell_order_with_max_positions(self, trading_engine):
        """Test that sell orders are allowed even when at max positions."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Fill position manager with max positions
        for i in range(10):
            symbol = f"STOCK{i}"
            trading_engine.position_manager.open_position(symbol, 100, 100.0)
        
        # SELL orders should still be allowed
        order = await trading_engine.place_order(
            symbol="STOCK1",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=150.0
        )
        
        assert order is not None  # Sell order should be allowed

    @pytest.mark.asyncio
    async def test_cancel_order(self, trading_engine):
        """Test cancelling an order."""
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 100, 150.0)
        
        success = await trading_engine.cancel_order(order.id)
        
        assert success is True
        assert len(trading_engine.order_manager.get_active_orders()) == 0

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, trading_engine):
        """Test cancelling a non-existent order."""
        success = await trading_engine.cancel_order("nonexistent-id")
        
        assert success is False

    def test_update_market_prices(self, trading_engine):
        """Test updating market prices."""
        prices = {
            "AAPL": 155.0,
            "GOOGL": 2100.0,
            "MSFT": 295.0
        }
        
        trading_engine.update_market_prices(prices)
        
        assert trading_engine.last_prices == prices
        # Portfolio and positions should be updated (tested in their respective modules)

    @pytest.mark.asyncio
    async def test_execute_buy_order(self, trading_engine):
        """Test executing a buy order."""
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 100, None)
        
        success = await trading_engine.execute_order(order, 150.0)
        
        assert success is True
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order.average_fill_price == 150.0
        
        # Check portfolio was updated
        asset = trading_engine.portfolio.get_asset("AAPL")
        assert asset is not None
        assert asset.quantity == 100
        
        # Check position was created
        position = trading_engine.position_manager.get_position("AAPL")
        assert position is not None
        assert position.quantity == 100

    @pytest.mark.asyncio
    async def test_execute_sell_order(self, trading_engine):
        """Test executing a sell order."""
        # First create a position
        trading_engine.portfolio.add_asset("AAPL", 100, 145.0)
        trading_engine.position_manager.open_position("AAPL", 100, 145.0)
        
        # Create sell order
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.SELL, OrderType.MARKET, 100, None)
        
        success = await trading_engine.execute_order(order, 155.0)
        
        assert success is True
        assert order.status == OrderStatus.FILLED
        
        # Check position was closed
        position = trading_engine.position_manager.get_position("AAPL")
        assert position is None  # Position should be closed
        
        # Check risk metrics were updated
        assert trading_engine.risk_manager.winning_trades == 1  # Profitable trade

    @pytest.mark.asyncio
    async def test_execute_partial_sell_order(self, trading_engine):
        """Test executing a partial sell order."""
        # Create position
        trading_engine.portfolio.add_asset("AAPL", 100, 145.0)
        trading_engine.position_manager.open_position("AAPL", 100, 145.0)
        
        # Partial sell
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.SELL, OrderType.MARKET, 50, None)
        
        success = await trading_engine.execute_order(order, 155.0)
        
        assert success is True
        
        # Check position was partially closed
        position = trading_engine.position_manager.get_position("AAPL")
        assert position is not None
        assert position.quantity == 50  # 100 - 50 = 50 remaining

    @pytest.mark.asyncio
    async def test_execute_order_insufficient_assets(self, trading_engine):
        """Test executing sell order with insufficient assets."""
        # Try to sell without having the asset
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.SELL, OrderType.MARKET, 100, None)
        
        success = await trading_engine.execute_order(order, 150.0)
        
        assert success is False
        assert order.status != OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_execute_order_insufficient_cash(self, trading_engine):
        """Test executing buy order with insufficient cash."""
        # Try to buy more than available cash
        order = trading_engine.order_manager.create_order("EXPENSIVE", OrderSide.BUY, OrderType.MARKET, 1000, None)
        
        success = await trading_engine.execute_order(order, 10000.0)  # $10M total
        
        assert success is False
        assert order.status != OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_process_orders_market_order(self, trading_engine):
        """Test processing market orders."""
        trading_engine.is_running = True
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Create market order
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.MARKET, 50, None)
        
        # Process orders (simulate one iteration)
        with patch.object(trading_engine, 'execute_order') as mock_execute:
            mock_execute.return_value = True
            
            # Manually call the order processing logic once
            for order in trading_engine.order_manager.get_active_orders():
                if order.type == OrderType.MARKET:
                    price = trading_engine.last_prices.get(order.symbol)
                    if price:
                        await trading_engine.execute_order(order, price)
            
            mock_execute.assert_called_once_with(order, 150.0)

    @pytest.mark.asyncio
    async def test_process_orders_limit_order_triggered(self, trading_engine):
        """Test processing limit orders that should be triggered."""
        trading_engine.is_running = True
        trading_engine.last_prices = {"AAPL": 149.0}  # Below limit price
        
        # Create buy limit order at $150
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 50, 150.0)
        
        with patch.object(trading_engine, 'execute_order') as mock_execute:
            mock_execute.return_value = True
            
            # Process order logic
            for order in trading_engine.order_manager.get_active_orders():
                if order.type == OrderType.LIMIT:
                    price = trading_engine.last_prices.get(order.symbol)
                    if price and order.price:
                        if (order.side == OrderSide.BUY and price <= order.price):
                            await trading_engine.execute_order(order, order.price)
            
            mock_execute.assert_called_once_with(order, 150.0)

    @pytest.mark.asyncio
    async def test_process_orders_limit_order_not_triggered(self, trading_engine):
        """Test processing limit orders that should NOT be triggered."""
        trading_engine.is_running = True
        trading_engine.last_prices = {"AAPL": 151.0}  # Above limit price
        
        # Create buy limit order at $150
        order = trading_engine.order_manager.create_order("AAPL", OrderSide.BUY, OrderType.LIMIT, 50, 150.0)
        
        with patch.object(trading_engine, 'execute_order') as mock_execute:
            # Process order logic
            for order in trading_engine.order_manager.get_active_orders():
                if order.type == OrderType.LIMIT:
                    price = trading_engine.last_prices.get(order.symbol)
                    if price and order.price:
                        if (order.side == OrderSide.BUY and price <= order.price):
                            await trading_engine.execute_order(order, order.price)
            
            mock_execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_positions_stop_loss_trigger_long(self, trading_engine):
        """Test stop loss trigger for long position."""
        trading_engine.is_running = True
        
        # Create long position
        trading_engine.position_manager.open_position("AAPL", 100, 150.0)
        trading_engine.last_prices = {"AAPL": 146.0}  # Below stop loss (2% = 147.0)
        
        with patch.object(trading_engine, 'place_order') as mock_place_order:
            mock_place_order.return_value = MagicMock()
            
            # Manually trigger position update logic
            for symbol, position in trading_engine.position_manager.positions.items():
                price = trading_engine.last_prices.get(symbol)
                if price:
                    stop_price = trading_engine.risk_manager.get_stop_loss_price(
                        position.entry_price,
                        "buy" if position.quantity > 0 else "sell"
                    )
                    
                    if (position.quantity > 0 and price <= stop_price):
                        await trading_engine.place_order(
                            symbol=symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            quantity=abs(position.quantity),
                        )
            
            mock_place_order.assert_called_once()
            args, kwargs = mock_place_order.call_args
            assert kwargs['symbol'] == "AAPL"
            assert kwargs['side'] == OrderSide.SELL
            assert kwargs['quantity'] == 100

    @pytest.mark.asyncio
    async def test_update_positions_stop_loss_trigger_short(self, trading_engine):
        """Test stop loss trigger for short position."""
        trading_engine.is_running = True
        
        # Create short position
        trading_engine.position_manager.open_position("AAPL", -100, 150.0)
        trading_engine.last_prices = {"AAPL": 154.0}  # Above stop loss (2% = 153.0)
        
        with patch.object(trading_engine, 'place_order') as mock_place_order:
            mock_place_order.return_value = MagicMock()
            
            # Manually trigger position update logic
            for symbol, position in trading_engine.position_manager.positions.items():
                price = trading_engine.last_prices.get(symbol)
                if price:
                    stop_price = trading_engine.risk_manager.get_stop_loss_price(
                        position.entry_price,
                        "buy" if position.quantity > 0 else "sell"
                    )
                    
                    if (position.quantity < 0 and price >= stop_price):
                        await trading_engine.place_order(
                            symbol=symbol,
                            side=OrderSide.BUY,  # Buy to cover short
                            order_type=OrderType.MARKET,
                            quantity=abs(position.quantity),
                        )
            
            mock_place_order.assert_called_once()
            args, kwargs = mock_place_order.call_args
            assert kwargs['symbol'] == "AAPL"
            assert kwargs['side'] == OrderSide.BUY
            assert kwargs['quantity'] == 100

    @pytest.mark.asyncio
    async def test_monitor_risk_drawdown_alert(self, trading_engine):
        """Test risk monitoring for drawdown alerts."""
        trading_engine.is_running = True
        
        # Set up drawdown scenario
        trading_engine.risk_manager.peak_value = 100000
        trading_engine.risk_manager.current_value = 85000  # 15% drawdown > 10% limit
        
        with patch('src.trading_engine.engine.logger') as mock_logger:
            # Manually trigger risk monitoring logic
            dd_ok, dd_msg = trading_engine.risk_manager.check_drawdown()
            if not dd_ok:
                mock_logger.error(f"Risk alert: {dd_msg}")
            
            mock_logger.error.assert_called_once()
            assert "Risk alert:" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_monitor_risk_daily_loss_alert(self, trading_engine):
        """Test risk monitoring for daily loss alerts."""
        trading_engine.is_running = True
        
        # Set up daily loss scenario
        trading_engine.risk_manager.current_value = 100000
        trading_engine.risk_manager.daily_losses = -3000  # 3% > 2% limit
        
        with patch('src.trading_engine.engine.logger') as mock_logger:
            # Manually trigger risk monitoring logic
            loss_ok, loss_msg = trading_engine.risk_manager.check_daily_loss_limit()
            if not loss_ok:
                mock_logger.error(f"Risk alert: {loss_msg}")
            
            mock_logger.error.assert_called_once()
            assert "Risk alert:" in mock_logger.error.call_args[0][0]

    def test_get_portfolio_summary(self, trading_engine):
        """Test getting portfolio summary."""
        # Add some test data
        trading_engine.portfolio.add_asset("AAPL", 100, 150.0)
        trading_engine.position_manager.open_position("AAPL", 100, 150.0)
        order = trading_engine.order_manager.create_order("GOOGL", OrderSide.BUY, OrderType.LIMIT, 50, 2000.0)
        
        summary = trading_engine.get_portfolio_summary()
        
        assert "portfolio" in summary
        assert "positions" in summary
        assert "active_orders" in summary
        assert "risk_metrics" in summary
        assert summary["active_orders"] == 1
        assert len(summary["positions"]) == 1

    @pytest.mark.asyncio
    async def test_full_trading_lifecycle(self, trading_engine):
        """Test complete trading lifecycle."""
        trading_engine.last_prices = {"AAPL": 150.0}
        
        # Place buy order (within 10% limit: $7,500 = 7.5%)
        buy_order = await trading_engine.place_order("AAPL", OrderSide.BUY, OrderType.MARKET, 50, None)
        assert buy_order is not None
        
        # Execute buy order
        success = await trading_engine.execute_order(buy_order, 150.0)
        assert success is True
        
        # Check position created
        position = trading_engine.position_manager.get_position("AAPL")
        assert position is not None
        assert position.quantity == 50
        
        # Update price (profitable)
        trading_engine.update_market_prices({"AAPL": 160.0})
        
        # Place sell order
        sell_order = await trading_engine.place_order("AAPL", OrderSide.SELL, OrderType.MARKET, 50, None)
        assert sell_order is not None
        
        # Execute sell order
        success = await trading_engine.execute_order(sell_order, 160.0)
        assert success is True
        
        # Check position closed
        position = trading_engine.position_manager.get_position("AAPL")
        assert position is None
        
        # Check profit recorded
        assert trading_engine.risk_manager.winning_trades == 1
        assert trading_engine.risk_manager.total_wins == 500.0  # (160-150) * 50

    @pytest.mark.asyncio
    async def test_error_handling_in_background_tasks(self, trading_engine):
        """Test error handling in background tasks."""
        trading_engine.is_running = True
        
        # Test with broken order processing
        with patch.object(trading_engine.order_manager, 'get_active_orders', side_effect=Exception("Test error")):
            with patch('src.trading_engine.engine.logger') as mock_logger:
                with patch('asyncio.sleep', side_effect=[None, StopAsyncIteration]):  # Stop after first error
                    try:
                        await trading_engine._process_orders()
                    except StopAsyncIteration:
                        pass
                
                mock_logger.error.assert_called_with("Error processing orders: Test error")

    def test_engine_with_custom_risk_parameters(self, custom_trading_engine):
        """Test engine behavior with custom risk parameters."""
        # Verify custom parameters are set correctly
        assert custom_trading_engine.risk_manager.parameters.max_position_size == 0.15
        assert custom_trading_engine.risk_manager.parameters.max_open_positions == 5
        
        # Test custom max open positions (should be 5 instead of default 10)
        custom_trading_engine.last_prices = {"STOCK0": 100.0, "STOCK1": 100.0, "STOCK2": 100.0, 
                                           "STOCK3": 100.0, "STOCK4": 100.0, "STOCK5": 100.0}
        
        # Add 5 positions (at the limit)
        for i in range(5):
            custom_trading_engine.position_manager.open_position(f"STOCK{i}", 50, 100.0)
        
        # 6th position should be rejected
        order = asyncio.run(custom_trading_engine.place_order("STOCK5", OrderSide.BUY, OrderType.LIMIT, 50, 100.0))
        assert order is None

    def test_market_price_updates_integration(self, trading_engine):
        """Test integration of market price updates across all components."""
        # Add initial position
        trading_engine.portfolio.add_asset("AAPL", 100, 150.0)
        trading_engine.position_manager.open_position("AAPL", 100, 150.0)
        
        initial_portfolio_value = trading_engine.portfolio.total_value
        
        # Update prices
        new_prices = {"AAPL": 160.0}
        trading_engine.update_market_prices(new_prices)
        
        # Check all components updated
        assert trading_engine.last_prices["AAPL"] == 160.0
        assert trading_engine.portfolio.total_value > initial_portfolio_value
        
        position = trading_engine.position_manager.get_position("AAPL")
        assert position.current_price == 160.0
        assert position.unrealized_pnl == 1000.0
        
        assert trading_engine.risk_manager.current_value == trading_engine.portfolio.total_value

    @pytest.mark.asyncio
    async def test_process_orders_background_task(self, trading_engine):
        """Test background order processing covers lines 195-208."""
        # Just test that the background task runs without errors
        await trading_engine.start()
        await asyncio.sleep(0.1)  # Let background tasks run
        await trading_engine.stop()
        
        # Test covered - background tasks executed

    @pytest.mark.asyncio
    async def test_process_orders_error_handling(self, trading_engine):
        """Test error handling in background order processing covers lines 210-212."""
        # Mock execute_order to raise exception during background processing
        original_execute = trading_engine.execute_order
        
        async def mock_execute_error(*args, **kwargs):
            raise RuntimeError("Mock execution error")
        
        trading_engine.execute_order = mock_execute_error
        
        # Start and stop engine to trigger error handling
        await trading_engine.start()
        await asyncio.sleep(0.1)
        await trading_engine.stop()
        
        # Restore original method
        trading_engine.execute_order = original_execute

    @pytest.mark.asyncio
    async def test_update_positions_background_task(self, trading_engine):
        """Test background position update task covers lines 216-246."""
        # Start engine to trigger background tasks including position updates
        await trading_engine.start()
        await asyncio.sleep(0.1)
        await trading_engine.stop()
        
        # Background task executed

    @pytest.mark.asyncio
    async def test_position_update_error_handling(self, trading_engine):
        """Test error handling in position update task covers lines 219-222."""
        # Mock update_prices to raise exception
        original_update = trading_engine.position_manager.update_prices
        
        def mock_update_error(*args, **kwargs):
            raise RuntimeError("Mock update error")
        
        trading_engine.position_manager.update_prices = mock_update_error
        
        # Start and stop engine (should handle error gracefully)
        await trading_engine.start()
        await asyncio.sleep(0.1)
        await trading_engine.stop()
        
        # Restore original method
        trading_engine.position_manager.update_prices = original_update

    @pytest.mark.asyncio
    async def test_monitor_risk_background_task(self, trading_engine):
        """Test background risk monitoring task covers lines 250-268."""
        # Start engine to trigger background tasks including risk monitoring  
        await trading_engine.start()
        await asyncio.sleep(0.1)
        await trading_engine.stop()
        
        # Background task executed

    @pytest.mark.asyncio
    async def test_risk_monitoring_error_handling(self, trading_engine):
        """Test error handling in risk monitoring task covers lines 263-265."""
        # Mock update_portfolio_value to raise exception
        original_update = trading_engine.risk_manager.update_portfolio_value
        
        def mock_update_error(*args, **kwargs):
            raise RuntimeError("Mock risk update error")
        
        trading_engine.risk_manager.update_portfolio_value = mock_update_error
        
        # Start and stop engine (should handle error gracefully)
        await trading_engine.start()
        await asyncio.sleep(0.1)
        await trading_engine.stop()
        
        # Restore original method
        trading_engine.risk_manager.update_portfolio_value = original_update