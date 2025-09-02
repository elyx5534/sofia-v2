"""
Arbitrage API Routes
Turkish arbitrage radar endpoints
"""

import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.arb_tl_radar import arb_radar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/arb", tags=["arbitrage"])


class StartRadarRequest(BaseModel):
    mode: str = "tl"
    pairs: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    threshold_bps: int = 50


@router.post("/start")
async def start_radar(request: StartRadarRequest) -> Dict:
    """Start arbitrage radar monitoring"""
    try:
        result = arb_radar.start_radar(
            mode=request.mode, pairs=request.pairs, threshold_bps=request.threshold_bps
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        logger.info(f"Started arbitrage radar: {request.mode}")
        return result

    except Exception as e:
        logger.error(f"Start radar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_radar() -> Dict:
    """Stop arbitrage radar"""
    try:
        result = arb_radar.stop_radar()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        logger.info("Stopped arbitrage radar")
        return result

    except Exception as e:
        logger.error(f"Stop radar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snap")
async def get_snapshot() -> Dict:
    """Get current arbitrage radar snapshot"""
    try:
        return arb_radar.get_snapshot()
    except Exception as e:
        logger.error(f"Get snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pairs")
async def get_pairs() -> List[str]:
    """Get recommended arbitrage pairs"""
    return ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT", "AVAX/USDT", "MATIC/USDT"]


@router.get("/exchanges")
async def get_exchanges() -> List[Dict]:
    """Get supported Turkish exchanges"""
    return [
        {"name": "btcturk", "display_name": "BtcTurk", "active": True},
        {"name": "paribu", "display_name": "Paribu", "active": True},
        {"name": "binance_tr", "display_name": "Binance TR", "active": True},
    ]
