"""
Chaos Tests for Paper Trading - WebSocket/Data Feed Failures
"""

import pytest
import asyncio
import random
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime
import pandas as pd

from src.paper.runner import PaperTradingRunner
from src.paper.signal_hub import SignalHub


class TestWebSocketFailures:
    """Test WebSocket connection failures and recovery"""
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_recovery(self):
        """Test recovery from WebSocket disconnection"""
        runner = PaperTradingRunner()
        
        # Mock WebSocket that fails after 3 messages
        message_count = 0
        
        async def mock_receive():
            nonlocal message_count
            message_count += 1
            
            if message_count == 3:
                raise ConnectionError("WebSocket disconnected")
            
            return {
                'type': 'price',
                'symbol': 'BTC/USDT',
                'price': 50000 + random.randint(-100, 100)
            }
        
        runner._websocket_receive = mock_receive
        
        # Start runner
        task = asyncio.create_task(runner._websocket_loop())
        
        # Let it run for a bit
        await asyncio.sleep(0.5)
        
        # Should handle disconnection gracefully
        assert runner.reconnect_attempts > 0
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_websocket_malformed_data(self):
        """Test handling of malformed WebSocket data"""
        runner = PaperTradingRunner()
        
        malformed_messages = [
            {},  # Empty message
            {'type': 'price'},  # Missing fields
            {'symbol': 'BTC/USDT'},  # Missing type
            {'type': 'price', 'symbol': 'BTC/USDT', 'price': 'invalid'},  # Invalid price
            None,  # Null message
        ]
        
        for msg in malformed_messages:
            # Should not crash
            try:
                await runner._handle_websocket_message(msg)
            except Exception as e:
                pytest.fail(f"Failed to handle malformed message {msg}: {e}")
    
    @pytest.mark.asyncio
    async def test_websocket_exponential_backoff(self):
        """Test exponential backoff on repeated failures"""
        runner = PaperTradingRunner()
        
        # Track reconnect delays
        delays = []
        
        async def mock_connect():
            raise ConnectionError("Cannot connect")
        
        runner._websocket_connect = mock_connect
        
        # Override sleep to capture delays
        original_sleep = asyncio.sleep
        
        async def mock_sleep(delay):
            delays.append(delay)
            if len(delays) > 3:
                raise asyncio.CancelledError()
            return await original_sleep(0.01)  # Speed up test
        
        with patch('asyncio.sleep', mock_sleep):
            try:
                await runner._reconnect_websocket()
            except asyncio.CancelledError:
                pass
        
        # Verify exponential backoff
        assert len(delays) > 2
        assert delays[1] > delays[0]  # Should increase
        assert delays[2] > delays[1]  # Should keep increasing


class TestDataFeedFailures:
    """Test data feed failures and fallback mechanisms"""
    
    @pytest.mark.asyncio
    async def test_primary_feed_failure_fallback(self):
        """Test fallback to secondary data feed"""
        runner = PaperTradingRunner()
        
        # Mock primary feed failure
        async def mock_fetch_primary():
            raise Exception("Primary feed unavailable")
        
        # Mock working secondary feed
        async def mock_fetch_secondary():
            return {
                'symbol': 'BTC/USDT',
                'price': 50000,
                'timestamp': datetime.now()
            }
        
        runner._fetch_primary_data = mock_fetch_primary
        runner._fetch_secondary_data = mock_fetch_secondary
        
        # Should fallback to secondary
        data = await runner._fetch_market_data('BTC/USDT')
        
        assert data is not None
        assert data['price'] == 50000
    
    @pytest.mark.asyncio
    async def test_all_feeds_failure(self):
        """Test behavior when all data feeds fail"""
        runner = PaperTradingRunner()
        
        # Mock all feeds failing
        async def mock_fetch_fail():
            raise Exception("Feed unavailable")
        
        runner._fetch_primary_data = mock_fetch_fail
        runner._fetch_secondary_data = mock_fetch_fail
        runner._fetch_tertiary_data = mock_fetch_fail
        
        # Should handle gracefully
        data = await runner._fetch_market_data('BTC/USDT')
        
        assert data is None
        
        # Should not process signals without data
        signal = {'symbol': 'BTC/USDT', 'strength': 0.8}
        await runner._process_signal(signal)
        
        # No orders should be created
        assert len(runner.orders) == 0
    
    @pytest.mark.asyncio
    async def test_partial_data_loss(self):
        """Test handling of partial data loss"""
        hub = SignalHub()
        
        # Provide incomplete OHLCV data
        incomplete_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='5min'),
            'open': [50000] * 10,
            'high': [50100] * 10,
            'low': [49900] * 10,
            'close': [None, 50050, None, 50100, None, None, 50000, None, 49950, None],  # Missing values
            'volume': [100] * 10
        })
        
        hub.update_ohlcv('BTC/USDT', incomplete_data.values.tolist())
        
        # Should handle missing data gracefully
        signal = hub.get_signal('BTC/USDT', Decimal('50000'))
        
        # Should return neutral signal with missing data
        assert signal['strength'] == 0 or signal['confidence'] < 0.5


class TestRateLimitingAndThrottling:
    """Test rate limiting and throttling scenarios"""
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_handling(self):
        """Test handling of API rate limits"""
        runner = PaperTradingRunner()
        
        call_count = 0
        
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            
            if call_count > 5:
                # Simulate rate limit
                raise Exception("Rate limit exceeded: 429")
            
            return {'status': 'ok'}
        
        runner._api_call = mock_api_call
        
        # Make multiple calls
        for _ in range(10):
            try:
                await runner._api_call()
            except Exception as e:
                if "429" in str(e):
                    # Should back off
                    await asyncio.sleep(0.1)
        
        # Should have stopped after rate limit
        assert call_count <= 7  # Some retry attempts
    
    @pytest.mark.asyncio
    async def test_order_submission_throttling(self):
        """Test order submission throttling"""
        runner = PaperTradingRunner()
        
        # Try to submit many orders rapidly
        orders_submitted = []
        
        async def mock_submit(order):
            orders_submitted.append(order)
            return True
        
        runner._submit_order = mock_submit
        
        # Generate many signals
        for i in range(20):
            signal = {
                'symbol': f'BTC/USDT',
                'strength': 0.8,
                'confidence': 0.7
            }
            
            # Should throttle rapid submissions
            await runner._process_signal(signal)
            
        # Should not submit all 20 immediately
        assert len(orders_submitted) < 20


class TestSystemResourceFailures:
    """Test system resource failures"""
    
    @pytest.mark.asyncio
    async def test_memory_pressure(self):
        """Test behavior under memory pressure"""
        runner = PaperTradingRunner()
        
        # Simulate large data accumulation
        for i in range(1000):
            runner.orders.append(Mock(
                timestamp=datetime.now(),
                symbol='BTC/USDT',
                quantity=Decimal('0.01'),
                price=Decimal('50000')
            ))
        
        # Should implement cleanup
        runner._cleanup_old_data()
        
        # Should keep reasonable amount of data
        assert len(runner.orders) <= 500  # Assuming max 500 orders kept
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test database connection failure handling"""
        runner = PaperTradingRunner()
        
        # Mock database failure
        async def mock_save_fail():
            raise Exception("Database connection lost")
        
        runner._save_to_database = mock_save_fail
        
        # Should continue operating without database
        await runner._create_paper_order(
            symbol='BTC/USDT',
            side='buy',
            quantity=Decimal('0.01'),
            price=Decimal('50000')
        )
        
        # Order should still be created in memory
        assert len(runner.orders) == 1
        
        # Should queue for later persistence
        assert len(runner.pending_persistence) > 0


class TestConcurrencyIssues:
    """Test concurrent operation issues"""
    
    @pytest.mark.asyncio
    async def test_concurrent_signal_processing(self):
        """Test handling of concurrent signals"""
        runner = PaperTradingRunner()
        runner.balance = Decimal('10000')
        
        # Generate multiple concurrent signals
        signals = [
            {'symbol': 'BTC/USDT', 'strength': 0.8, 'confidence': 0.7},
            {'symbol': 'ETH/USDT', 'strength': 0.6, 'confidence': 0.8},
            {'symbol': 'BTC/USDT', 'strength': -0.7, 'confidence': 0.6},  # Conflicting
        ]
        
        # Process concurrently
        tasks = [runner._process_signal(s) for s in signals]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should handle concurrent updates safely
        assert runner.balance >= Decimal('0')  # No negative balance
        assert len(runner.positions) <= 2  # Max 2 unique symbols
    
    @pytest.mark.asyncio
    async def test_race_condition_position_update(self):
        """Test race condition in position updates"""
        runner = PaperTradingRunner()
        
        # Create initial position
        runner.positions['BTC/USDT'] = {
            'quantity': Decimal('0.1'),
            'entry_price': Decimal('50000'),
            'position_value': Decimal('5000'),
            'unrealized_pnl': Decimal('0')
        }
        
        # Concurrent updates to same position
        async def update1():
            await runner._update_position('BTC/USDT', Decimal('51000'))
        
        async def update2():
            await runner._update_position('BTC/USDT', Decimal('49000'))
        
        # Run concurrently
        await asyncio.gather(update1(), update2(), return_exceptions=True)
        
        # Position should have consistent state
        pos = runner.positions.get('BTC/USDT')
        assert pos is not None
        assert pos['quantity'] == Decimal('0.1')  # Quantity unchanged


class TestKillSwitchAndEmergency:
    """Test kill switch and emergency scenarios"""
    
    @pytest.mark.asyncio
    async def test_kill_switch_activation(self):
        """Test kill switch stops all operations"""
        runner = PaperTradingRunner()
        runner.running = True
        
        # Start some background tasks
        tasks = [
            asyncio.create_task(runner._heartbeat_loop()),
            asyncio.create_task(runner._monitor_loop())
        ]
        
        # Activate kill switch
        runner.kill_switch = True
        await runner.stop()
        
        # All tasks should stop
        for task in tasks:
            assert task.done() or task.cancelled()
        
        # No new operations should be allowed
        signal = {'symbol': 'BTC/USDT', 'strength': 0.8}
        await runner._process_signal(signal)
        
        assert len(runner.orders) == 0  # No new orders
    
    @pytest.mark.asyncio
    async def test_max_daily_loss_trigger(self):
        """Test max daily loss triggers kill switch"""
        runner = PaperTradingRunner()
        runner.config['MAX_DAILY_LOSS'] = '200'
        
        # Simulate large loss
        runner.daily_pnl = Decimal('-250')
        
        # Should trigger kill switch
        await runner._check_risk_limits()
        
        assert runner.kill_switch == True
        assert runner.running == False


class TestDataCorruption:
    """Test data corruption scenarios"""
    
    def test_corrupted_position_data(self):
        """Test handling of corrupted position data"""
        runner = PaperTradingRunner()
        
        # Corrupt position data
        runner.positions['BTC/USDT'] = {
            'quantity': 'invalid',  # Should be Decimal
            'entry_price': None,  # Missing price
            'position_value': -1000,  # Negative value
        }
        
        # Should detect and handle corruption
        runner._validate_positions()
        
        # Corrupted position should be removed or fixed
        pos = runner.positions.get('BTC/USDT')
        assert pos is None or isinstance(pos['quantity'], Decimal)
    
    def test_order_history_corruption(self):
        """Test corrupted order history recovery"""
        runner = PaperTradingRunner()
        
        # Add corrupted orders
        runner.orders = [
            Mock(timestamp=None, symbol='BTC/USDT'),  # Missing timestamp
            Mock(timestamp=datetime.now(), symbol=None),  # Missing symbol
            Mock(timestamp='invalid', symbol='ETH/USDT'),  # Invalid timestamp
        ]
        
        # Should clean up corrupted data
        runner._cleanup_corrupted_orders()
        
        # Only valid orders should remain
        for order in runner.orders:
            assert order.timestamp is not None
            assert order.symbol is not None
            assert isinstance(order.timestamp, datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])