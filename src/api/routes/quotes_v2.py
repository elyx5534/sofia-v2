"""
Enhanced Quotes API Routes with Multi-Market Support
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from src.services.datahub_v2 import datahub_v2
from src.services.symbols import symbol_registry, AssetType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quotes", tags=["quotes"])

@router.get("/ohlcv")
async def get_ohlcv(
    asset: str = Query(..., description="Asset like BTC/USDT@BINANCE or AAPL@NASDAQ"),
    tf: str = Query("1d", description="Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    adjust: bool = Query(True, description="Adjust for corporate actions (stocks)")
) -> Dict:
    """Get OHLCV data for an asset"""
    try:
        # Default date range
        if not end:
            end = datetime.now().isoformat()[:10]
        if not start:
            # Default based on timeframe
            days_map = {
                "1m": 1, "5m": 3, "15m": 7, "30m": 14,
                "1h": 30, "4h": 60, "1d": 365, "1w": 730
            }
            days = days_map.get(tf, 30)
            start = (datetime.now() - timedelta(days=days)).isoformat()[:10]
        
        # Parse asset
        asset_obj = symbol_registry.parse(asset)
        if not asset_obj:
            raise HTTPException(status_code=400, detail=f"Invalid asset: {asset}")
        
        # Get data
        data = datahub_v2.get_ohlcv(asset, tf, start, end, adjust_corporate=adjust)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {asset} from {start} to {end}"
            )
        
        return {
            "asset": str(asset_obj),
            "timeframe": tf,
            "start": start,
            "end": end,
            "count": len(data),
            "data": data,
            "adjusted": adjust if asset_obj.type == AssetType.STOCK else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OHLCV error for {asset}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ticker")
async def get_ticker(
    asset: str = Query(..., description="Asset like BTC/USDT@BINANCE or AAPL")
) -> Dict:
    """Get latest ticker for an asset"""
    try:
        result = datahub_v2.get_ticker(asset)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ticker error for {asset}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols")
async def get_symbols(
    type: Optional[str] = Query(None, description="Filter by type: crypto, stock, forex"),
    venue: Optional[str] = Query(None, description="Filter by venue: BINANCE, NASDAQ, BIST")
) -> List[Dict]:
    """Get available symbols"""
    try:
        assets = []
        
        if type:
            asset_type = AssetType(type.lower())
            assets = symbol_registry.get_by_type(asset_type)
        elif venue:
            assets = symbol_registry.get_by_venue(venue.upper())
        else:
            # Return all registered assets
            assets = list(symbol_registry.assets.values())
        
        # Remove duplicates and format
        seen = set()
        result = []
        for asset in assets:
            key = str(asset)
            if key not in seen:
                seen.add(key)
                result.append({
                    "symbol": key,
                    "type": asset.type.value,
                    "base": asset.base,
                    "quote": asset.quote,
                    "venue": asset.venue
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Symbols error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_symbols(
    q: str = Query(..., description="Search query")
) -> List[Dict]:
    """Search for symbols"""
    try:
        assets = symbol_registry.search(q)
        
        return [
            {
                "symbol": str(asset),
                "type": asset.type.value,
                "base": asset.base,
                "quote": asset.quote,
                "venue": asset.venue
            }
            for asset in assets
        ]
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check() -> Dict:
    """Get data service health metrics"""
    try:
        health = datahub_v2.get_health()
        
        # Add timestamp
        health["timestamp"] = datetime.now().isoformat()
        health["status"] = "healthy" if health["cache_hit_rate"] else "warming"
        
        # Test connectivity
        test_result = datahub_v2.get_ticker("BTC/USDT@BINANCE")
        health["btc_price"] = test_result.get("price", 0)
        
        return health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/venues")
async def get_venues() -> List[Dict]:
    """Get supported venues"""
    return [
        {"name": "BINANCE", "type": "crypto", "region": "Global"},
        {"name": "BYBIT", "type": "crypto", "region": "Global"},
        {"name": "COINBASE", "type": "crypto", "region": "US"},
        {"name": "BTCTURK", "type": "crypto", "region": "Turkey"},
        {"name": "PARIBU", "type": "crypto", "region": "Turkey"},
        {"name": "NASDAQ", "type": "stock", "region": "US"},
        {"name": "NYSE", "type": "stock", "region": "US"},
        {"name": "BIST", "type": "stock", "region": "Turkey"},
        {"name": "FOREX", "type": "forex", "region": "Global"}
    ]

@router.get("/timeframes")
async def get_timeframes() -> List[str]:
    """Get supported timeframes"""
    return ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]