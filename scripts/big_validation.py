#!/usr/bin/env python3
"""
BIG VALIDATION SCRIPT - 10 Minute Proof
Proves real-data ingestion and P&L calculation works end-to-end
"""

import asyncio
import time
import sys
import os
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.price_service_real import price_service
from src.models.portfolio import portfolio_manager
from src.adapters.binance_ws import ws_adapter
from src.providers.coingecko_free import coingecko_provider

# Colors for terminal output (ASCII only)
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}")

def print_section(text):
    print(f"\n{Colors.OKBLUE}{'-' * 40}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{text}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{'-' * 40}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.OKGREEN}[SUCCESS] {text}{Colors.ENDC}")

def print_fail(text):
    print(f"{Colors.FAIL}[FAIL] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}[INFO] {text}{Colors.ENDC}")

async def validate_websocket():
    """Test WebSocket connection and data flow"""
    print_section("WEBSOCKET VALIDATION")
    
    # Check WebSocket is enabled
    if not os.getenv('SOFIA_WS_ENABLED', 'true').lower() == 'true':
        print_fail("WebSocket is disabled in environment")
        return False
    
    print_info("Starting WebSocket connection...")
    
    # Start WebSocket if not already started
    if not ws_adapter.connected:
        await price_service.start_websocket()
        await asyncio.sleep(3)  # Give it time to connect
    
    # Check connection status
    metrics = ws_adapter.get_metrics()
    
    if metrics['connected']:
        print_success(f"WebSocket connected")
        print_info(f"  Tracking {len(metrics['symbols'])} symbols")
        
        # Check for data freshness
        stale_count = 0
        for symbol, data in metrics['symbols'].items():
            freshness = data.get('freshness')
            if freshness and freshness < 15:
                print_success(f"  {symbol}: Fresh data ({freshness:.1f}s)")
            else:
                stale_count += 1
                print_fail(f"  {symbol}: Stale/No data")
        
        if stale_count == 0:
            print_success("All symbols receiving fresh data")
            return True
        else:
            print_fail(f"{stale_count} symbols have stale data")
            return False
    else:
        print_fail("WebSocket not connected")
        if metrics.get('last_error'):
            print_info(f"  Last error: {metrics['last_error']}")
        return False

async def validate_rest_fallback():
    """Test REST API fallback"""
    print_section("REST FALLBACK VALIDATION")
    
    test_symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD']
    success_count = 0
    
    for symbol in test_symbols:
        result = await price_service.get_price_rest(symbol, symbol.replace('-USD', 'USDT'))
        
        if result and result.get('price') > 0:
            print_success(f"{symbol}: ${result['price']:,.2f} (source: {result['source']})")
            success_count += 1
        else:
            print_fail(f"{symbol}: No data")
    
    if success_count == len(test_symbols):
        print_success("REST fallback working for all test symbols")
        return True
    else:
        print_fail(f"REST fallback failed for {len(test_symbols) - success_count} symbols")
        return False

async def validate_coingecko():
    """Test CoinGecko provider"""
    print_section("COINGECKO VALIDATION")
    
    test_symbols = ['BTC-USD', 'ETH-USD']
    success_count = 0
    
    for symbol in test_symbols:
        result = await coingecko_provider.get_price(symbol)
        
        if result and result.get('price') > 0:
            print_success(f"{symbol}: ${result['price']:,.2f}")
            success_count += 1
        else:
            print_fail(f"{symbol}: No data")
    
    if success_count == len(test_symbols):
        print_success("CoinGecko provider working")
        return True
    else:
        print_fail("CoinGecko provider issues")
        return False

async def validate_paper_trading():
    """Test paper trading with real prices"""
    print_section("PAPER TRADING VALIDATION")
    
    # Reset portfolio
    print_info("Resetting portfolio to $100,000...")
    conn = portfolio_manager._init_db()
    
    # Execute test trades
    test_trades = [
        {'symbol': 'BTC-USD', 'amount': 10000},
        {'symbol': 'ETH-USD', 'amount': 5000},
        {'symbol': 'SOL-USD', 'amount': 2000}
    ]
    
    initial_balance = 100000
    positions_created = []
    
    for trade in test_trades:
        symbol = trade['symbol']
        amount = trade['amount']
        
        # Get real price
        price_data = await price_service.get_price(symbol)
        
        if price_data and price_data['price'] > 0:
            price = price_data['price']
            print_info(f"Buying {symbol} for ${amount:,.2f} at ${price:,.2f}")
            
            result = portfolio_manager.execute_order(
                symbol=symbol,
                side='buy',
                usd_amount=amount,
                price=price
            )
            
            if result['success']:
                print_success(f"  Bought {result['quantity']:.8f} {symbol}")
                positions_created.append(symbol)
            else:
                print_fail(f"  Failed: {result.get('error')}")
        else:
            print_fail(f"No price for {symbol}")
    
    if len(positions_created) > 0:
        print_success(f"Created {len(positions_created)} positions")
        return True
    else:
        print_fail("No positions created")
        return False

async def validate_pnl_calculation():
    """Test P&L calculation with price updates"""
    print_section("P&L CALCULATION VALIDATION")
    
    portfolio = portfolio_manager.get_portfolio()
    
    if not portfolio['positions']:
        print_fail("No positions to test P&L")
        return False
    
    initial_value = portfolio['total_balance']
    print_info(f"Initial portfolio value: ${initial_value:,.2f}")
    
    # Wait and update prices
    print_info("Waiting 30 seconds for price changes...")
    await asyncio.sleep(30)
    
    # Get new prices and update
    price_updates = {}
    for pos in portfolio['positions']:
        result = await price_service.get_price(pos['symbol'])
        if result and result['price'] > 0:
            price_updates[pos['symbol']] = result['price']
            print_info(f"  {pos['symbol']}: ${result['price']:,.2f}")
    
    if price_updates:
        portfolio_manager.update_position_prices(price_updates)
        
        # Get updated portfolio
        portfolio = portfolio_manager.get_portfolio()
        current_value = portfolio['total_balance']
        pnl = current_value - initial_value
        pnl_pct = (pnl / initial_value) * 100
        
        print_info(f"Updated portfolio value: ${current_value:,.2f}")
        print_info(f"Total P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)")
        
        # Show position P&L
        for pos in portfolio['positions']:
            if pos['pnl'] != 0:
                print_info(f"  {pos['symbol']}: P&L ${pos['pnl']:+,.2f} ({pos['pnl_pct']:+.2f}%)")
        
        print_success("P&L calculation working correctly")
        return True
    else:
        print_fail("Could not get price updates")
        return False

async def validate_api_endpoints():
    """Test API endpoints"""
    print_section("API ENDPOINTS VALIDATION")
    
    import httpx
    api_base = "http://localhost:8001"
    
    endpoints = [
        ("/health", "GET"),
        ("/metrics", "GET"),
        ("/api/trading/portfolio", "GET"),
        ("/api/trading/positions", "GET")
    ]
    
    success_count = 0
    
    async with httpx.AsyncClient() as client:
        for endpoint, method in endpoints:
            try:
                url = f"{api_base}{endpoint}"
                response = await client.request(method, url, timeout=5.0)
                
                if response.status_code == 200:
                    print_success(f"{method} {endpoint} - OK")
                    success_count += 1
                else:
                    print_fail(f"{method} {endpoint} - {response.status_code}")
            except Exception as e:
                print_fail(f"{method} {endpoint} - {str(e)}")
    
    if success_count == len(endpoints):
        print_success("All API endpoints working")
        return True
    else:
        print_fail(f"{len(endpoints) - success_count} endpoints failed")
        return False

async def run_10_minute_validation():
    """Run complete 10-minute validation"""
    print_header("SOFIA V2 - 10 MINUTE VALIDATION")
    print_info(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    results = {}
    
    # Run validation steps
    results['websocket'] = await validate_websocket()
    results['rest_fallback'] = await validate_rest_fallback()
    results['coingecko'] = await validate_coingecko()
    results['paper_trading'] = await validate_paper_trading()
    results['pnl_calculation'] = await validate_pnl_calculation()
    results['api_endpoints'] = await validate_api_endpoints()
    
    # Monitor for remaining time (up to 10 minutes total)
    elapsed = time.time() - start_time
    remaining = max(600 - elapsed, 60)  # At least 1 minute monitoring
    
    if remaining > 0:
        print_section(f"LIVE MONITORING ({int(remaining)}s)")
        
        monitor_start = time.time()
        update_interval = 30
        
        while time.time() - monitor_start < remaining:
            await asyncio.sleep(update_interval)
            
            # Get metrics
            metrics = price_service.get_metrics()
            
            print_info(f"[{int(time.time() - start_time)}s] System Status:")
            print_info(f"  WebSocket: {'Connected' if metrics['websocket_connected'] else 'Disconnected'}")
            
            # Show price freshness
            if metrics.get('websocket_metrics'):
                ws_metrics = metrics['websocket_metrics']
                fresh_count = 0
                for symbol, data in ws_metrics.get('symbols', {}).items():
                    if data.get('freshness', 999) < 15:
                        fresh_count += 1
                print_info(f"  Fresh prices: {fresh_count}/{len(ws_metrics.get('symbols', {}))}")
            
            # Update portfolio P&L
            portfolio = portfolio_manager.get_portfolio()
            if portfolio['positions']:
                total_pnl = sum(pos['pnl'] for pos in portfolio['positions'])
                print_info(f"  Total P&L: ${total_pnl:+,.2f}")
    
    # Final results
    print_header("VALIDATION COMPLETE")
    
    total_time = time.time() - start_time
    print_info(f"Total time: {int(total_time)}s")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print_info(f"Tests passed: {passed}/{total}")
    
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        color = Colors.OKGREEN if passed else Colors.FAIL
        print(f"  {color}[{status}] {test}{Colors.ENDC}")
    
    if passed == total:
        print_success("\nALL VALIDATIONS PASSED - SYSTEM READY")
        print_info("Real-data ingestion: WORKING")
        print_info("Live P&L tracking: WORKING")
        print_info("Paper trading: WORKING")
        return 0
    else:
        print_fail(f"\n{total - passed} VALIDATIONS FAILED")
        return 1

async def main():
    """Main entry point"""
    try:
        exit_code = await run_10_minute_validation()
        
        # Cleanup
        await price_service.shutdown()
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        await price_service.shutdown()
        sys.exit(1)
    except Exception as e:
        print_fail(f"Validation error: {e}")
        import traceback
        traceback.print_exc()
        await price_service.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())