"""
Backtest API Routes
Historical strategy testing endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging

from src.services.backtester import backtester

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtest", tags=["backtest"])

class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start: str
    end: str
    strategy: str = "sma_cross"
    params: Dict = {}

class BacktestResponse(BaseModel):
    run_id: str
    equity_curve: List[List]
    drawdown: List[List]
    trades: List[Dict]
    stats: Dict

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> Dict:
    """Run a backtest with specified parameters"""
    try:
        logger.info(f"Starting backtest: {request.strategy} on {request.symbol}")
        
        result = backtester.run_backtest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            strategy=request.strategy,
            params=request.params
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        logger.info(f"Backtest completed: {result['run_id']}")
        return result
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{run_id}")
async def get_results(run_id: str) -> Dict:
    """Get saved backtest results"""
    try:
        results = backtester.get_results(run_id)
        if not results:
            raise HTTPException(status_code=404, detail=f"Results not found for {run_id}")
        return results
    except Exception as e:
        logger.error(f"Get results error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_csv(run_id: str):
    """Export backtest results as CSV"""
    try:
        csv_path = backtester.export_csv(run_id)
        if not csv_path:
            raise HTTPException(status_code=404, detail=f"CSV not found for {run_id}")
            
        return FileResponse(
            path=str(csv_path),
            media_type="text/csv",
            filename=f"backtest_{run_id}.csv"
        )
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
async def get_strategies() -> List[Dict]:
    """Get available strategies and their parameters"""
    return [
        {
            "name": "sma_cross",
            "display_name": "SMA Crossover",
            "params": {
                "fast": {"type": "int", "default": 20, "min": 5, "max": 50},
                "slow": {"type": "int", "default": 50, "min": 20, "max": 200}
            }
        },
        {
            "name": "rsi_revert",
            "display_name": "RSI Mean Reversion",
            "params": {
                "period": {"type": "int", "default": 14, "min": 5, "max": 30},
                "oversold": {"type": "int", "default": 30, "min": 10, "max": 40},
                "overbought": {"type": "int", "default": 70, "min": 60, "max": 90}
            }
        },
        {
            "name": "grid",
            "display_name": "Grid Trading",
            "params": {
                "levels": {"type": "int", "default": 10, "min": 5, "max": 20},
                "spacing_pct": {"type": "float", "default": 1.0, "min": 0.5, "max": 3.0}
            }
        },
        {
            "name": "mean_revert",
            "display_name": "Mean Reversion",
            "params": {
                "lookback": {"type": "int", "default": 20, "min": 10, "max": 50},
                "z_threshold": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0}
            }
        }
    ]

@router.get("/timeframes")
async def get_timeframes() -> List[str]:
    """Get available timeframes"""
    return ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]