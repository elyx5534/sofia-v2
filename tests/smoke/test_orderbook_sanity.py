"""
Smoke test for orderbook sanity
"""
import pytest
import ccxt

def test_binance_orderbook_sanity():
    """Test that Binance orderbook is sane (ask > bid)"""
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot'
        }
    })
    
    # Fetch BTC/USDT orderbook
    orderbook = exchange.fetch_order_book("BTC/USDT", limit=5)
    
    # Check structure
    assert "bids" in orderbook
    assert "asks" in orderbook
    assert len(orderbook["bids"]) > 0
    assert len(orderbook["asks"]) > 0
    
    # Check sanity: best ask > best bid
    best_bid = orderbook["bids"][0][0]  # Price of best bid
    best_ask = orderbook["asks"][0][0]  # Price of best ask
    
    assert best_ask > best_bid, f"Ask ({best_ask}) should be > Bid ({best_bid})"
    
    # Check spread is reasonable (< 1%)
    spread_pct = (best_ask - best_bid) / best_bid * 100
    assert spread_pct < 1.0, f"Spread too wide: {spread_pct:.3f}%"
    
def test_multiple_symbols_orderbook():
    """Test orderbooks for multiple symbols"""
    exchange = ccxt.binance({'enableRateLimit': True})
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    for symbol in symbols:
        orderbook = exchange.fetch_order_book(symbol, limit=1)
        
        best_bid = orderbook["bids"][0][0]
        best_ask = orderbook["asks"][0][0]
        
        assert best_ask > best_bid, f"{symbol}: Ask should be > Bid"
        assert best_bid > 0, f"{symbol}: Bid should be positive"
        assert best_ask > 0, f"{symbol}: Ask should be positive"