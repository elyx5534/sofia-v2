"""
Backtest API Routes v2
Enhanced with Grid Search, GA, WFO, and Portfolio support
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.services.backtester import BacktestConfig, backtester

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start: str
    end: str
    strategy: str = "sma_cross"
    params: Dict = {}
    config: Optional[Dict] = None


class GridSearchRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start: str
    end: str
    strategy: str = "sma_cross"
    param_grid: Dict[str, List]


class GeneticAlgorithmRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start: str
    end: str
    strategy: str = "sma_cross"
    param_ranges: Dict[str, List]  # [min, max] for each param
    population_size: int = 30
    generations: int = 15
    elite_size: int = 2


class WalkForwardRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start: str
    end: str
    strategy: str = "sma_cross"
    param_grid: Dict[str, List]
    n_splits: int = 3
    train_ratio: float = 0.7


class BacktestResponse(BaseModel):
    run_id: str
    equity_curve: List[List]
    drawdown: List[List]
    trades: List[Dict]
    stats: Dict


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> Dict:
    """Run a single backtest with specified parameters"""
    try:
        logger.info(f"Starting backtest: {request.strategy} on {request.symbol}")

        # Convert config dict to BacktestConfig if provided
        config = None
        if request.config:
            config = BacktestConfig(**request.config)

        result = backtester.run_backtest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            strategy=request.strategy,
            params=request.params,
            config=config,
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        logger.info(f"Backtest completed: {result['run_id']}")
        return result

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/grid")
async def run_grid_search(request: GridSearchRequest) -> Dict:
    """Run grid search optimization"""
    try:
        logger.info(f"Starting grid search: {request.strategy} on {request.symbol}")

        result = backtester.run_grid_search(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            strategy=request.strategy,
            param_grid=request.param_grid,
        )

        logger.info(f"Grid search completed: best Sharpe = {result.get('best_sharpe', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"Grid search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ga")
async def run_genetic_algorithm(request: GeneticAlgorithmRequest) -> Dict:
    """Run genetic algorithm optimization"""
    try:
        logger.info(f"Starting GA: {request.strategy} on {request.symbol}")

        # Convert param_ranges from list format to tuple format
        param_ranges = {k: tuple(v) for k, v in request.param_ranges.items()}

        result = backtester.run_genetic_algorithm(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            strategy=request.strategy,
            param_ranges=param_ranges,
            population_size=request.population_size,
            generations=request.generations,
            elite_size=request.elite_size,
        )

        logger.info(f"GA completed: best fitness = {result.get('best_fitness', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"GA error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wfo")
async def run_walk_forward(request: WalkForwardRequest) -> Dict:
    """Run walk-forward optimization"""
    try:
        logger.info(f"Starting WFO: {request.strategy} on {request.symbol}")

        result = backtester.run_walk_forward_optimization(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            strategy=request.strategy,
            param_grid=request.param_grid,
            n_splits=request.n_splits,
            train_ratio=request.train_ratio,
        )

        logger.info(f"WFO completed: avg OOS Sharpe = {result.get('avg_oos_sharpe', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"WFO error: {e}")
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
            path=str(csv_path), media_type="text/csv", filename=f"backtest_{run_id}.csv"
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
                "slow": {"type": "int", "default": 50, "min": 20, "max": 200},
            },
        },
        {
            "name": "rsi_revert",
            "display_name": "RSI Mean Reversion",
            "params": {
                "period": {"type": "int", "default": 14, "min": 5, "max": 30},
                "oversold": {"type": "int", "default": 30, "min": 10, "max": 40},
                "overbought": {"type": "int", "default": 70, "min": 60, "max": 90},
            },
        },
        {
            "name": "breakout",
            "display_name": "Channel Breakout",
            "params": {"period": {"type": "int", "default": 20, "min": 10, "max": 50}},
        },
        {
            "name": "mean_rev_spread",
            "display_name": "Pairs Mean Reversion",
            "params": {
                "symbol2": {"type": "str", "default": "ETH/USDT"},
                "lookback": {"type": "int", "default": 20, "min": 10, "max": 50},
                "z_entry": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0},
                "z_exit": {"type": "float", "default": 0.5, "min": 0.1, "max": 1.0},
            },
        },
    ]


@router.get("/timeframes")
async def get_timeframes() -> List[str]:
    """Get available timeframes"""
    return ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]


@router.get("/config/defaults")
async def get_config_defaults() -> Dict:
    """Get default backtest configuration"""
    return {
        "initial_capital": 10000,
        "commission_bps": 10,
        "slippage_bps": 5,
        "funding_rate": 0.0001,
        "max_positions": 10,
        "position_size_pct": 10,
    }
