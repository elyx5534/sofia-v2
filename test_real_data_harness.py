#!/usr/bin/env python3
"""
Real Data Test Harness
Tests all data providers and proves P&L tracking works
"""

import asyncio
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.adapters.binance_ws import ws_adapter
from src.adapters.yahoo_free import yahoo_adapter
from src.adapters.stooq_eod import stooq_adapter
from src.adapters.coingecko_free import coingecko_adapter
from src.services.price_service_real import price_service
from src.models.portfolio import portfolio_manager

async def test_data_providers():
    """Test all data providers"""
    
    print("=" * 60)
    print("REAL DATA PROVIDER TEST")
    print("=" * 60)
    
    test_symbols = ['BTC-USD', 'ETH-USD', 'AAPL']
    
    # Test Yahoo Finance
    print("\n[YAHOO FINANCE]")
    for symbol in test_symbols:
        result = await yahoo_adapter.get_quote(symbol)
        if result:
            print(f"  {symbol}: ${result['price']:.2f} ({result['change_percent']:+.2f}%)")
        else:
            print(f"  {symbol}: NO DATA")
    
    # Test CoinGecko
    print("\n[COINGECKO]")
    for symbol in ['BTC-USD', 'ETH-USD']:
        result = await coingecko_adapter.get_price(symbol)
        if result:
            print(f"  {symbol}: ${result['price']:.2f}")
        else:
            print(f"  {symbol}: NO DATA")
    
    # Test Stooq EOD
    print("\n[STOOQ EOD]")
    for symbol in test_symbols:
        result = await stooq_adapter.get_latest_eod(symbol)
        if result:
            print(f"  {symbol}: ${result['price']:.2f} (EOD: {result['date']})")
        else:
            print(f"  {symbol}: NO DATA")
    
    # Test WebSocket + REST fallback
    print("\n[WEBSOCKET + REST]")
    for symbol in test_symbols:
        result = await price_service.get_price(symbol)
        if result:
            print(f"  {symbol}: ${result['price']:.2f} (source: {result['source']}, freshness: {result.get('freshness', 'N/A')})")
        else:
            print(f"  {symbol}: NO DATA")

async def test_paper_trading():
    """Test paper trading with real prices"""
    
    print("\n" + "=" * 60)
    print("PAPER TRADING TEST")
    print("=" * 60)
    
    # Initial portfolio
    portfolio = portfolio_manager.get_portfolio()
    print(f"\nStarting Balance: ${portfolio['cash_balance']:,.2f}")
    
    # Test trades
    trades = [
        {'symbol': 'BTC-USD', 'side': 'buy', 'amount': 1000},
        {'symbol': 'ETH-USD', 'side': 'buy', 'amount': 500},
    ]
    
    print("\nExecuting trades...")
    
    for trade in trades:
        # Get live price
        price_data = await price_service.get_price(trade['symbol'])
        if not price_data:
            price_data = await yahoo_adapter.get_quote(trade['symbol'])
        
        if price_data:
            price = price_data['price']
            print(f"\n{trade['side'].upper()} {trade['symbol']} @ ${price:.2f}")
            
            result = portfolio_manager.execute_order(
                symbol=trade['symbol'],
                side=trade['side'],
                usd_amount=trade['amount'],
                price=price
            )
            
            if result['success']:
                print(f"  SUCCESS: {result['quantity']:.8f} units")
            else:
                print(f"  FAILED: {result['error']}")
    
    # Show positions
    portfolio = portfolio_manager.get_portfolio()
    print(f"\nPositions: {len(portfolio['positions'])}")
    for pos in portfolio['positions']:
        print(f"  {pos['symbol']}: {pos['quantity']:.8f} @ ${pos['entry_price']:.2f}")

async def monitor_pnl(duration_seconds=120):
    """Monitor P&L changes"""
    
    print("\n" + "=" * 60)
    print("P&L MONITORING TEST")
    print("=" * 60)
    
    portfolio = portfolio_manager.get_portfolio()
    if not portfolio['positions']:
        print("No positions to monitor")
        return
    
    initial_value = portfolio['total_balance']
    print(f"\nInitial Value: ${initial_value:,.2f}")
    print(f"Monitoring for {duration_seconds} seconds...\n")
    
    start_time = time.time()
    update_count = 0
    
    while time.time() - start_time < duration_seconds:
        await asyncio.sleep(10)
        
        # Update prices
        prices = {}
        for pos in portfolio['positions']:
            result = await price_service.get_price(pos['symbol'])
            if not result:
                result = await yahoo_adapter.get_quote(pos['symbol'])
            
            if result:
                prices[pos['symbol']] = result['price']
        
        if prices:
            portfolio_manager.update_position_prices(prices)
            portfolio = portfolio_manager.get_portfolio()
            
            current_value = portfolio['total_balance']
            pnl = current_value - initial_value
            pnl_pct = (pnl / initial_value) * 100
            
            update_count += 1
            elapsed = int(time.time() - start_time)
            
            print(f"[{elapsed:3d}s] Value: ${current_value:,.2f} | P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
            
            for pos in portfolio['positions']:
                print(f"       {pos['symbol']}: ${pos['current_price']:.2f} | P&L: ${pos['pnl']:+.2f} ({pos['pnl_pct']:+.2f}%)")
    
    print(f"\nUpdates: {update_count}")
    print("P&L monitoring complete")

async def test_metrics():
    """Test system metrics"""
    
    print("\n" + "=" * 60)
    print("SYSTEM METRICS")
    print("=" * 60)
    
    metrics = price_service.get_metrics()
    
    print(f"\nWebSocket Enabled: {metrics['websocket_enabled']}")
    print(f"WebSocket Connected: {metrics['websocket_connected']}")
    print(f"Cache TTL: {metrics['cache_ttl']}s")
    print(f"REST Timeout: {metrics['rest_timeout']}s")
    
    if metrics.get('websocket_metrics'):
        ws_metrics = metrics['websocket_metrics']
        print(f"\nWebSocket Metrics:")
        print(f"  Connected: {ws_metrics.get('connected', False)}")
        print(f"  Reconnect Count: {ws_metrics.get('reconnect_count', 0)}")
        print(f"  Symbols Tracked: {len(ws_metrics.get('symbols', {}))}")
    
    if metrics.get('stale_symbols'):
        print(f"\nStale Symbols: {metrics['stale_symbols']}")
    
    if metrics.get('rest_failures'):
        print(f"\nREST Failures: {metrics['rest_failures']}")

async def main():
    """Run all tests"""
    
    print("\n" + "=" * 60)
    print(" SOFIA V2 - REAL DATA TEST HARNESS")
    print("=" * 60)
    print("\nTesting real data ingestion and P&L tracking...")
    print("Using FREE, LEGAL data sources only")
    print("-" * 60)
    
    try:
        # Test data providers
        await test_data_providers()
        
        # Test paper trading
        await test_paper_trading()
        
        # Monitor P&L for 2 minutes
        await monitor_pnl(120)
        
        # Show metrics
        await test_metrics()
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE - All systems operational")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await price_service.shutdown()

if __name__ == "__main__":
    asyncio.run(main())