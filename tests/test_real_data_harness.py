#!/usr/bin/env python3
"""
Test harness for real data ingestion
Tests WebSocket, REST fallback, and P&L calculation
"""

import asyncio
import pytest
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.price_service_real import price_service
from src.adapters.binance_ws import ws_adapter
from src.models.portfolio import portfolio_manager
from src.providers.coingecko_free import coingecko_provider


@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connects and receives data"""
    # Start WebSocket
    await price_service.start_websocket()
    await asyncio.sleep(5)  # Wait for connection
    
    # Check connection
    metrics = ws_adapter.get_metrics()
    assert metrics['connected'], "WebSocket should be connected"
    
    # Check for fresh data
    fresh_symbols = []
    for symbol, data in metrics['symbols'].items():
        if data.get('freshness', 999) < 15:
            fresh_symbols.append(symbol)
    
    assert len(fresh_symbols) > 0, "Should have at least one symbol with fresh data"


@pytest.mark.asyncio
async def test_rest_fallback():
    """Test REST API fallback when WebSocket unavailable"""
    # Get price via REST
    result = await price_service.get_price_rest('BTC-USD', 'BTCUSDT')
    
    assert result is not None, "Should get result from REST"
    assert result['price'] > 0, "Price should be positive"
    assert result['source'] in ['rest', 'rest_cache'], "Source should be REST"


@pytest.mark.asyncio
async def test_coingecko_provider():
    """Test CoinGecko free API provider"""
    result = await coingecko_provider.get_price('BTC-USD')
    
    assert result is not None, "Should get result from CoinGecko"
    assert result['price'] > 0, "Price should be positive"
    assert result['source'] == 'coingecko', "Source should be coingecko"


@pytest.mark.asyncio
async def test_price_service_priority():
    """Test WebSocket-first, REST-fallback priority"""
    # Start WebSocket
    await price_service.start_websocket()
    await asyncio.sleep(5)
    
    # Get price (should use WebSocket if available)
    result = await price_service.get_price('BTC-USD')
    
    assert result is not None, "Should get price"
    assert result['price'] > 0, "Price should be positive"
    
    # Source should be WebSocket if connected and fresh
    if ws_adapter.connected:
        freshness = ws_adapter.get_freshness('BTCUSDT')
        if freshness and freshness < 15:
            assert result['source'] == 'websocket', "Should use WebSocket when available"


def test_portfolio_initialization():
    """Test portfolio initializes correctly"""
    portfolio = portfolio_manager.get_portfolio()
    
    assert portfolio is not None, "Portfolio should exist"
    assert portfolio['base_currency'] == 'USD', "Base currency should be USD"
    assert portfolio['cash_balance'] >= 0, "Cash balance should be non-negative"
    assert 'positions' in portfolio, "Should have positions list"


def test_paper_trade_execution():
    """Test paper trade execution"""
    # Get initial portfolio
    initial = portfolio_manager.get_portfolio()
    initial_cash = initial['cash_balance']
    
    # Execute a buy order
    result = portfolio_manager.execute_order(
        symbol='BTC-USD',
        side='buy',
        usd_amount=1000,
        price=50000
    )
    
    assert result['success'], "Order should succeed"
    assert result['quantity'] > 0, "Should have bought some quantity"
    
    # Check portfolio updated
    portfolio = portfolio_manager.get_portfolio()
    assert portfolio['cash_balance'] < initial_cash, "Cash should decrease after buy"
    assert len(portfolio['positions']) > 0, "Should have at least one position"


def test_pnl_calculation():
    """Test P&L calculation"""
    # Create a position
    portfolio_manager.execute_order(
        symbol='ETH-USD',
        side='buy',
        usd_amount=1000,
        price=3000
    )
    
    # Get position
    portfolio = portfolio_manager.get_portfolio()
    position = next((p for p in portfolio['positions'] if p['symbol'] == 'ETH-USD'), None)
    
    assert position is not None, "Should have ETH position"
    
    # Update price (simulate profit)
    new_price = 3100
    portfolio_manager.update_position_prices({'ETH-USD': new_price})
    
    # Check P&L
    portfolio = portfolio_manager.get_portfolio()
    position = next((p for p in portfolio['positions'] if p['symbol'] == 'ETH-USD'), None)
    
    assert position['current_price'] == new_price, "Price should be updated"
    assert position['pnl'] > 0, "Should have positive P&L"
    assert position['pnl_pct'] > 0, "Should have positive P&L percentage"


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics collection"""
    metrics = price_service.get_metrics()
    
    assert 'websocket_enabled' in metrics, "Should have WebSocket enabled flag"
    assert 'cache_ttl' in metrics, "Should have cache TTL"
    assert 'rest_timeout' in metrics, "Should have REST timeout"
    
    # If WebSocket enabled, check WebSocket metrics
    if metrics['websocket_enabled']:
        assert 'websocket_metrics' in metrics, "Should have WebSocket metrics"


@pytest.mark.asyncio
async def test_symbol_mapping():
    """Test symbol mapping between UI and exchange formats"""
    from src.services.symbols import get_ws_sym, get_rest_sym
    
    # Test UI to WebSocket mapping
    ws_symbol = get_ws_sym('BTC-USD')
    assert ws_symbol == 'BTCUSDT', "Should map BTC-USD to BTCUSDT"
    
    # Test UI to REST mapping
    rest_symbol = get_rest_sym('ETH-USD')
    assert rest_symbol == 'ETHUSDT', "Should map ETH-USD to ETHUSDT"


@pytest.mark.asyncio
async def test_websocket_reconnection():
    """Test WebSocket reconnection logic"""
    # Start WebSocket
    await price_service.start_websocket()
    await asyncio.sleep(5)
    
    initial_metrics = ws_adapter.get_metrics()
    initial_connected = initial_metrics['connected']
    
    # Force disconnect
    if ws_adapter.connected:
        await ws_adapter.disconnect()
        await asyncio.sleep(2)
    
    # Should reconnect automatically
    await asyncio.sleep(10)
    
    final_metrics = ws_adapter.get_metrics()
    
    if initial_connected:
        assert final_metrics['reconnect_count'] > 0, "Should have reconnected"


@pytest.mark.asyncio
async def test_sma_ema_indicators():
    """Test SMA/EMA calculation in WebSocket adapter"""
    # Start WebSocket
    await price_service.start_websocket()
    await asyncio.sleep(10)  # Wait for some data
    
    metrics = ws_adapter.get_metrics()
    
    # Check if indicators are being calculated
    for symbol, data in metrics['symbols'].items():
        if data.get('tick_count', 0) > 5:  # Need some ticks for indicators
            # SMA/EMA might be None initially, that's ok
            assert 'sma' in data, "Should have SMA field"
            assert 'ema' in data, "Should have EMA field"


# Integration test
@pytest.mark.asyncio
async def test_end_to_end_paper_trading():
    """Test complete paper trading flow"""
    # 1. Get real price
    price_data = await price_service.get_price('BTC-USD')
    assert price_data is not None, "Should get price"
    
    price = price_data['price']
    assert price > 0, "Price should be positive"
    
    # 2. Execute paper trade
    result = portfolio_manager.execute_order(
        symbol='BTC-USD',
        side='buy',
        usd_amount=5000,
        price=price
    )
    assert result['success'], "Trade should succeed"
    
    # 3. Wait for price update
    await asyncio.sleep(5)
    
    # 4. Get new price
    new_price_data = await price_service.get_price('BTC-USD')
    if new_price_data:
        new_price = new_price_data['price']
        
        # 5. Update position price
        portfolio_manager.update_position_prices({'BTC-USD': new_price})
        
        # 6. Check P&L
        portfolio = portfolio_manager.get_portfolio()
        position = next((p for p in portfolio['positions'] if p['symbol'] == 'BTC-USD'), None)
        
        assert position is not None, "Should have position"
        assert 'pnl' in position, "Should have P&L calculated"
        assert 'pnl_pct' in position, "Should have P&L percentage"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])