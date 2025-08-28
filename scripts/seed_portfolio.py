#!/usr/bin/env python3
"""
Seed portfolio with initial test trades
Demonstrates live P&L tracking with real data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from src.models.portfolio import portfolio_manager
from src.services.price_service_real import price_service
from src.adapters.yahoo_free import yahoo_adapter
from src.adapters.coingecko_free import coingecko_adapter

async def seed_portfolio():
    """Seed portfolio with test positions"""
    
    print("=" * 60)
    print("PORTFOLIO SEEDING SCRIPT")
    print("=" * 60)
    
    # Get initial portfolio state
    portfolio = portfolio_manager.get_portfolio()
    print(f"\nInitial Portfolio:")
    print(f"  Cash: ${portfolio['cash_balance']:,.2f}")
    print(f"  Total Value: ${portfolio['total_balance']:,.2f}")
    
    # Test trades to execute
    test_trades = [
        {'symbol': 'BTC-USD', 'side': 'buy', 'usd_amount': 5000},
        {'symbol': 'ETH-USD', 'side': 'buy', 'usd_amount': 3000},
        {'symbol': 'BNB-USD', 'side': 'buy', 'usd_amount': 2000},
    ]
    
    print("\n" + "-" * 40)
    print("EXECUTING TEST TRADES")
    print("-" * 40)
    
    for trade in test_trades:
        symbol = trade['symbol']
        side = trade['side']
        amount = trade['usd_amount']
        
        print(f"\n{side.upper()} {symbol} for ${amount:,.2f}")
        
        # Get current price from multiple sources
        price = None
        source = None
        
        # Try primary price service
        result = await price_service.get_price(symbol)
        if result:
            price = result['price']
            source = result['source']
        
        # Fallback to Yahoo
        if not price:
            result = await yahoo_adapter.get_quote(symbol)
            if result:
                price = result['price']
                source = 'yahoo'
        
        # Fallback to CoinGecko
        if not price:
            result = await coingecko_adapter.get_price(symbol)
            if result:
                price = result['price']
                source = 'coingecko'
        
        if price and price > 0:
            print(f"  Price: ${price:,.2f} (source: {source})")
            
            # Execute trade
            trade_result = portfolio_manager.execute_order(
                symbol=symbol,
                side=side,
                usd_amount=amount,
                price=price
            )
            
            if trade_result['success']:
                print(f"  SUCCESS - Bought {trade_result['quantity']:.8f} units")
            else:
                print(f"  FAILED - {trade_result.get('error', 'Unknown error')}")
        else:
            print(f"  SKIPPED - No price available")
        
        # Small delay between trades
        await asyncio.sleep(1)
    
    print("\n" + "-" * 40)
    print("PORTFOLIO AFTER TRADES")
    print("-" * 40)
    
    # Get final portfolio
    portfolio = portfolio_manager.get_portfolio()
    print(f"\nFinal Portfolio:")
    print(f"  Cash: ${portfolio['cash_balance']:,.2f}")
    print(f"  Positions Value: ${portfolio['positions_value']:,.2f}")
    print(f"  Total Value: ${portfolio['total_balance']:,.2f}")
    
    if portfolio['positions']:
        print(f"\nOpen Positions ({len(portfolio['positions'])}):")
        for pos in portfolio['positions']:
            print(f"  {pos['symbol']}:")
            print(f"    Quantity: {pos['quantity']:.8f}")
            print(f"    Entry: ${pos['entry_price']:,.2f}")
            print(f"    Current: ${pos['current_price']:,.2f}")
            print(f"    P&L: ${pos['pnl']:,.2f} ({pos['pnl_pct']:.2f}%)")
    
    print("\n" + "=" * 60)
    print("P&L MONITORING")
    print("=" * 60)
    
    # Monitor P&L for 10 minutes
    start_time = time.time()
    monitor_duration = 600  # 10 minutes
    update_interval = 30  # Update every 30 seconds
    
    print(f"\nMonitoring P&L for 10 minutes...")
    print("Press Ctrl+C to stop early\n")
    
    initial_value = portfolio['total_balance']
    
    try:
        while time.time() - start_time < monitor_duration:
            # Wait for interval
            await asyncio.sleep(update_interval)
            
            # Get current prices and update positions
            prices_to_update = {}
            
            for pos in portfolio['positions']:
                symbol = pos['symbol']
                
                # Get latest price
                result = await price_service.get_price(symbol)
                if not result:
                    result = await yahoo_adapter.get_quote(symbol)
                if not result:
                    result = await coingecko_adapter.get_price(symbol)
                
                if result and result['price'] > 0:
                    prices_to_update[symbol] = result['price']
            
            # Update position prices
            if prices_to_update:
                portfolio_manager.update_position_prices(prices_to_update)
            
            # Get updated portfolio
            portfolio = portfolio_manager.get_portfolio()
            
            # Calculate P&L
            current_value = portfolio['total_balance']
            total_pnl = current_value - initial_value
            total_pnl_pct = (total_pnl / initial_value) * 100
            
            # Display update
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] Total Value: ${current_value:,.2f} | P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
            
            # Show position updates
            for pos in portfolio['positions']:
                if pos['pnl'] != 0:
                    print(f"  {pos['symbol']}: ${pos['current_price']:,.2f} | P&L: ${pos['pnl']:,.2f} ({pos['pnl_pct']:+.2f}%)")
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    # Final portfolio state
    portfolio = portfolio_manager.get_portfolio()
    final_value = portfolio['total_balance']
    total_pnl = final_value - 100000  # Assuming started with $100k
    total_pnl_pct = (total_pnl / 100000) * 100
    
    print(f"\nFinal Portfolio Value: ${final_value:,.2f}")
    print(f"Total P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
    
    if portfolio['positions']:
        print(f"\nFinal Positions:")
        for pos in portfolio['positions']:
            print(f"  {pos['symbol']}: P&L ${pos['pnl']:,.2f} ({pos['pnl_pct']:+.2f}%)")
    
    print("\n" + "=" * 60)
    print("SEED COMPLETE - Portfolio ready for paper trading")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(seed_portfolio())