"""
Live proof endpoint - Real-time Binance data verification
"""

import time

import ccxt

from src.adapters.web.fastapi_adapter import APIRouter, Query

router = APIRouter(prefix="/live-proof", tags=["proof"])


@router.get("")
async def get_live_proof(symbol: str = Query("BTC/USDT", description="Trading symbol")):
    """
    Get real-time ticker data from Binance to prove live connection

    Returns:
        JSON with bid, ask, last price, exchange time, and local time
    """
    try:
        exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        ticker = exchange.fetch_ticker(symbol)
        try:
            exchange_time = exchange.fetch_time()
        except:
            exchange_time = None
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
