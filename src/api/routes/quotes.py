"""
Quotes API Routes
Real-time and historical price data endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.adapters.web.fastapi_adapter import APIRouter, HTTPException, Query
from src.services.datahub import datahub

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("/ticker")
async def get_ticker(symbol: str = Query(..., description="Symbol like BTC/USDT")) -> Dict:
    """Get latest price for a symbol.

    Args:
        symbol: Trading symbol in format BASE/QUOTE (e.g., BTC/USDT)

    Returns:
        Dict containing symbol, price, timestamp, and volume

    Raises:
        HTTPException: If symbol not found or service error

    Example:
        curl -X GET "http://localhost:8000/api/quotes/ticker?symbol=BTC/USDT"
    """
    try:
        result = datahub.get_latest_price(symbol)
        if result["price"] == 0:
            raise HTTPException(status_code=404, detail=f"Price not found for {symbol}")
        return result
    except Exception as e:
        logger.error(f"Ticker error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlcv")
async def get_ohlcv(
    symbol: str = Query(..., description="Symbol like BTC/USDT"),
    tf: str = Query("1d", description="Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
) -> List[List]:
    """Get OHLCV data for a symbol.

    Args:
        symbol: Trading symbol in format BASE/QUOTE (e.g., BTC/USDT)
        tf: Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
        start: Start date in YYYY-MM-DD format (default: 30 days ago)
        end: End date in YYYY-MM-DD format (default: today)

    Returns:
        List of OHLCV candles: [[timestamp, open, high, low, close, volume], ...]

    Raises:
        HTTPException: If no data found or service error

    Example:
        curl -X GET "http://localhost:8000/api/quotes/ohlcv?symbol=BTC/USDT&tf=1h&start=2024-01-01&end=2024-01-07"
    """
    try:
        if not end:
            end = datetime.now().isoformat()[:10]
        if not start:
            start = (datetime.now() - timedelta(days=30)).isoformat()[:10]
        data = datahub.get_ohlcv(symbol, tf, start, end)
        if not data:
            raise HTTPException(
                status_code=404, detail=f"No data found for {symbol} from {start} to {end}"
            )
        return data
    except Exception as e:
        logger.error(f"OHLCV error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
async def get_symbols() -> List[str]:
    """Get list of available symbols"""
    return [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "ADA/USDT",
        "DOT/USDT",
        "AVAX/USDT",
        "MATIC/USDT",
        "LINK/USDT",
        "UNI/USDT",
    ]


@router.get("/health")
async def health_check() -> Dict:
    """Check if quotes service is healthy"""
    try:
        result = datahub.get_latest_price("BTC/USDT")
        return {
            "status": "healthy" if result["price"] > 0 else "degraded",
            "btc_price": result["price"],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}
