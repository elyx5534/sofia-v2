"""
Market Data API endpoints with fallback
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List
import logging

from src.services.market_data import market_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quote", response_model=Dict[str, Any])
async def get_market_quote(
    symbol: str = Query(..., description="Symbol (e.g., BTC/USDT)")
) -> Dict[str, Any]:
    """
    Get market quote with fallback chain
    """
    try:
        quote = await market_data_service.get_quote(symbol)
        return quote
    except Exception as e:
        logger.error(f"Error fetching quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlcv", response_model=Dict[str, Any])
async def get_market_ohlcv(
    symbol: str = Query(..., description="Symbol (e.g., BTC/USDT)"),
    timeframe: str = Query(default="1h", description="Timeframe (1m, 5m, 15m, 1h, 4h, 1d)"),
    limit: int = Query(default=100, ge=10, le=1000, description="Number of bars")
) -> Dict[str, Any]:
    """
    Get OHLCV data with fallback chain
    """
    try:
        ohlcv = await market_data_service.get_ohlcv(symbol, timeframe, limit)
        return ohlcv
    except Exception as e:
        logger.error(f"Error fetching OHLCV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=Dict[str, Any])
async def get_data_status() -> Dict[str, Any]:
    """
    Get market data service status
    """
    return market_data_service.get_status()