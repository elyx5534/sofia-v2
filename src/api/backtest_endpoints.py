"""
Backtest API endpoints for job submission and result retrieval
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
import os
import json
from pathlib import Path

from src.models.backtest import BacktestJob, BacktestResult, Base

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./backtest.db')
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestRequest(BaseModel):
    """Request model for running backtest"""
    strategy: str = Field(..., description="Strategy name: sma_cross, ema_breakout, rsi_reversion")
    params: Dict[str, Any] = Field(..., description="Strategy parameters")
    symbol: str = Field(default="BTC/USDT", description="Trading symbol")
    timeframe: str = Field(default="1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d")
    limit: int = Field(default=1000, description="Number of candles to use", ge=100, le=10000)


class BacktestResponse(BaseModel):
    """Response model for backtest submission"""
    job_id: int
    status: str
    message: str
    created_at: str


class BacktestStatus(BaseModel):
    """Status response model"""
    job_id: int
    status: str
    strategy: str
    symbol: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None


class BacktestResultResponse(BaseModel):
    """Result response model"""
    job_id: int
    status: str
    metrics: Optional[Dict[str, Any]] = None
    links: Optional[Dict[str, str]] = None
    created_at: str


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks
) -> BacktestResponse:
    """
    Submit a new backtest job to the queue
    """
    session = Session()
    
    try:
        # Validate strategy
        valid_strategies = ['sma_cross', 'ema_breakout', 'rsi_reversion']
        if request.strategy not in valid_strategies:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy. Must be one of: {valid_strategies}"
            )
        
        # Create job
        job = BacktestJob(
            strategy=request.strategy,
            params_json=request.params,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
            status='pending'
        )
        
        session.add(job)
        session.commit()
        session.refresh(job)
        
        return BacktestResponse(
            job_id=job.id,
            status=job.status,
            message=f"Backtest job {job.id} submitted successfully",
            created_at=job.created_at.isoformat()
        )
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{job_id}/status", response_model=BacktestStatus)
async def get_backtest_status(job_id: int) -> BacktestStatus:
    """
    Get the status of a backtest job
    """
    session = Session()
    
    try:
        job = session.query(BacktestJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Calculate ETA if running
        eta_seconds = None
        if job.status == 'running' and job.started_at:
            # Estimate based on average job time (30 seconds)
            elapsed = (datetime.utcnow() - job.started_at).total_seconds()
            eta_seconds = max(0, 30 - int(elapsed))
        elif job.status == 'pending':
            # Count pending jobs ahead
            pending_count = session.query(BacktestJob).filter(
                BacktestJob.status == 'pending',
                BacktestJob.created_at < job.created_at
            ).count()
            eta_seconds = (pending_count + 1) * 30  # 30 seconds per job estimate
        
        return BacktestStatus(
            job_id=job.id,
            status=job.status,
            strategy=job.strategy,
            symbol=job.symbol,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            eta_seconds=eta_seconds,
            error_message=job.error_message
        )
        
    finally:
        session.close()


@router.get("/{job_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result(job_id: int) -> BacktestResultResponse:
    """
    Get the result of a completed backtest job
    """
    session = Session()
    
    try:
        job = session.query(BacktestJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job.status == 'pending':
            raise HTTPException(status_code=425, detail="Job is still pending")
        
        if job.status == 'running':
            raise HTTPException(status_code=425, detail="Job is still running")
        
        if job.status == 'error':
            raise HTTPException(
                status_code=500,
                detail=f"Job failed with error: {job.error_message}"
            )
        
        # Get result
        result = session.query(BacktestResult).filter_by(job_id=job_id).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Result not found for completed job")
        
        # Build response
        return BacktestResultResponse(
            job_id=job_id,
            status=job.status,
            metrics=result.metrics_json,
            links={
                'equity_csv': f"/outputs/equity/{job_id}_equity.csv",
                'trades_csv': f"/outputs/trades/{job_id}_trades.csv" if result.trades_csv_path else None,
                'logs': f"/outputs/logs/{job_id}_logs.txt",
                'report_html': f"/outputs/reports/{job_id}_report.html"
            },
            created_at=result.created_at.isoformat()
        )
        
    finally:
        session.close()


class BacktestListItem(BaseModel):
    """List item model"""
    job_id: int
    strategy: str
    symbol: str
    status: str
    created_at: str
    metrics: Optional[Dict[str, float]] = None


@router.get("/list", response_model=List[BacktestListItem])
async def list_backtests(
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    strategy: Optional[str] = Query(default=None, description="Filter by strategy")
) -> List[BacktestListItem]:
    """
    List backtest jobs with optional filters
    """
    session = Session()
    
    try:
        query = session.query(BacktestJob)
        
        # Apply filters
        if status:
            query = query.filter_by(status=status)
        if strategy:
            query = query.filter_by(strategy=strategy)
        
        # Order by creation time and limit
        jobs = query.order_by(desc(BacktestJob.created_at)).limit(limit).all()
        
        # Build response
        items = []
        for job in jobs:
            item = BacktestListItem(
                job_id=job.id,
                strategy=job.strategy,
                symbol=job.symbol,
                status=job.status,
                created_at=job.created_at.isoformat()
            )
            
            # Add metrics if completed
            if job.status == 'done' and job.result:
                item.metrics = {
                    'total_return': job.result.total_return,
                    'sharpe_ratio': job.result.sharpe_ratio,
                    'max_drawdown': job.result.max_drawdown,
                    'win_rate': job.result.win_rate
                }
            
            items.append(item)
        
        return items
        
    finally:
        session.close()


@router.delete("/{job_id}")
async def delete_backtest(job_id: int) -> Dict[str, str]:
    """
    Delete a backtest job and its results
    """
    session = Session()
    
    try:
        job = session.query(BacktestJob).filter_by(id=job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Delete result if exists
        result = session.query(BacktestResult).filter_by(job_id=job_id).first()
        if result:
            # Delete output files
            for path_attr in ['equity_csv_path', 'trades_csv_path', 'logs_txt_path', 'report_html_path']:
                file_path = getattr(result, path_attr)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
            session.delete(result)
        
        # Delete job
        session.delete(job)
        session.commit()
        
        return {"message": f"Job {job_id} deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/strategies")
async def list_strategies() -> List[Dict[str, Any]]:
    """
    List available strategies and their parameters
    """
    strategies = [
        {
            "name": "sma_cross",
            "description": "Simple Moving Average Crossover Strategy",
            "params": {
                "fast": {"default": 10, "min": 5, "max": 50, "step": 5},
                "slow": {"default": 30, "min": 20, "max": 200, "step": 10},
                "signal_mode": {"default": "cross", "options": ["cross", "position"]}
            }
        },
        {
            "name": "ema_breakout",
            "description": "Exponential Moving Average Breakout with ATR filter",
            "params": {
                "ema_period": {"default": 20, "min": 10, "max": 100, "step": 5},
                "atr_period": {"default": 14, "min": 7, "max": 28, "step": 7},
                "atr_multiplier": {"default": 2.0, "min": 1.0, "max": 4.0, "step": 0.5},
                "use_volume": {"default": False, "options": [True, False]}
            }
        },
        {
            "name": "rsi_reversion",
            "description": "RSI-based mean reversion strategy",
            "params": {
                "rsi_period": {"default": 14, "min": 7, "max": 28, "step": 7},
                "oversold": {"default": 30, "min": 20, "max": 40, "step": 5},
                "overbought": {"default": 70, "min": 60, "max": 80, "step": 5},
                "exit_at_mean": {"default": True, "options": [True, False]}
            }
        }
    ]
    
    return strategies