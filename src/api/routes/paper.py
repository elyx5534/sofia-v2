"""
Paper Trading API Routes
Simulated trading session endpoints
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.paper_engine import paper_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/paper", tags=["paper"])


class StartSessionRequest(BaseModel):
    session: str  # "grid", "mean_revert", "simple"
    symbol: str
    params: Optional[Dict] = {}


@router.post("/start")
async def start_session(request: StartSessionRequest) -> Dict:
    """Start a paper trading session"""
    try:
        result = paper_engine.start_session(
            session_type=request.session, symbol=request.symbol, params=request.params
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        logger.info(f"Started paper session: {request.session} for {request.symbol}")
        return result

    except Exception as e:
        logger.error(f"Start session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_session() -> Dict:
    """Stop the current paper trading session"""
    try:
        result = paper_engine.stop_session()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        logger.info("Stopped paper session")
        return result

    except Exception as e:
        logger.error(f"Stop session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status() -> Dict:
    """Get current paper trading status"""
    try:
        return paper_engine.get_status()
    except Exception as e:
        logger.error(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_strategies() -> List[Dict]:
    """Get available paper trading strategies"""
    return [
        {
            "name": "grid",
            "display_name": "Grid Trading",
            "description": "Places buy and sell orders at regular price intervals",
            "params": {
                "grid_spacing": {"type": "float", "default": 0.01, "min": 0.005, "max": 0.05},
                "grid_levels": {"type": "int", "default": 5, "min": 3, "max": 10},
            },
        },
        {
            "name": "mean_revert",
            "display_name": "Mean Reversion",
            "description": "Trades based on price deviation from mean",
            "params": {
                "lookback": {"type": "int", "default": 20, "min": 10, "max": 50},
                "z_threshold": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0},
            },
        },
        {
            "name": "simple",
            "display_name": "Simple Momentum",
            "description": "Basic momentum-based trading",
            "params": {},
        },
    ]
