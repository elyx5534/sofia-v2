"""
Live proof endpoint - Real-time Binance data verification
"""

import time

import ccxt
from fastapi import APIRouter, Query

router = APIRouter(prefix="/live-proof", tags=["proof"])


@router.get("")
async def get_live_proof(symbol: str = Query("BTC/USDT", description="Trading symbol")):
    """
    Get real-time ticker data from Binance to prove live connection

    Returns:
        JSON with bid, ask, last price, exchange time, and local time
    """
    try:
        # Initialize Binance exchange
        exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})

        # Fetch ticker data
        ticker = exchange.fetch_ticker(symbol)

        # Try to fetch exchange time
        try:
            exchange_time = exchange.fetch_time()
        except:
            exchange_time = None

        # Prepare response
        response = {
            "symbol": symbol,
            "bid": ticker["bid"] if ticker["bid"] else 0,
            "ask": ticker["ask"] if ticker["ask"] else 0,
            "last": ticker["last"] if ticker["last"] else 0,
            "exchange": "binance",
            "exchange_server_time_ms": exchange_time if exchange_time else 0,
            "local_time_ms": int(time.time() * 1000),
        }

        return response

    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
            "exchange": "binance",
            "local_time_ms": int(time.time() * 1000),
        }
