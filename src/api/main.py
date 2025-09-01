"""Main API application with all endpoints."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import logging

# Import routers and services
from src.backtester.strategies.registry import StrategyRegistry
from src.optimizer.optimizer_queue import optimizer_queue, JobPriority
from src.ml.price_predictor import PricePredictor
from src.data_hub.providers.multi_source import MultiSourceDataProvider
from src.api.live_proof import router as live_router
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sofia Trading Platform API",
    description="Complete backend API for trading strategies, optimization, and ML predictions",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
strategy_registry = StrategyRegistry()
data_provider = MultiSourceDataProvider()
ml_predictor = PricePredictor()

# Include routers
app.include_router(live_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Start optimizer queue
    await optimizer_queue.start()
    logger.info("Optimizer queue started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    # Stop optimizer queue
    await optimizer_queue.stop()
    logger.info("Optimizer queue stopped")


# ==================== Strategy Endpoints ====================

@app.get("/api/strategies")
async def list_strategies(category: Optional[str] = None):
    """List all available trading strategies."""
    strategies = strategy_registry.list_strategies(category)
    return {
        "strategies": [s.to_dict() for s in strategies],
        "categories": strategy_registry.get_categories(),
        "total": len(strategies)
    }


@app.get("/api/strategies/{strategy_name}")
async def get_strategy(strategy_name: str):
    """Get detailed information about a specific strategy."""
    metadata = strategy_registry.get_metadata(strategy_name)
    
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")
    
    return metadata.to_dict()


@app.post("/api/strategies/{strategy_name}/validate")
async def validate_strategy_params(strategy_name: str, parameters: Dict[str, Any]):
    """Validate parameters for a strategy."""
    try:
        validated = strategy_registry.validate_parameters(strategy_name, parameters)
        return {
            "valid": True,
            "validated_parameters": validated
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": str(e)
        }


# ==================== Optimization Endpoints ====================

@app.post("/api/optimize/submit")
async def submit_optimization(
    strategy_name: str,
    symbol: str,
    param_space: Dict[str, List[float]],
    optimization_target: str = "sharpe",
    ga_params: Optional[Dict[str, Any]] = None,
    priority: str = "normal"
):
    """Submit a new optimization job to the queue."""
    # Convert param_space lists to tuples
    param_space_tuples = {k: tuple(v) for k, v in param_space.items()}
    
    # Convert priority string to enum
    priority_map = {
        "low": JobPriority.LOW,
        "normal": JobPriority.NORMAL,
        "high": JobPriority.HIGH,
        "urgent": JobPriority.URGENT
    }
    job_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)
    
    # Submit job
    job_id = await optimizer_queue.submit_job(
        strategy_name=strategy_name,
        symbol=symbol,
        param_space=param_space_tuples,
        optimization_target=optimization_target,
        ga_params=ga_params,
        priority=job_priority
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Optimization job submitted successfully"
    }


@app.get("/api/optimize/job/{job_id}")
async def get_optimization_job(job_id: str):
    """Get status and results of an optimization job."""
    job = optimizer_queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.to_dict()


@app.get("/api/optimize/jobs")
async def list_optimization_jobs(
    status: Optional[str] = None,
    limit: int = 50
):
    """List optimization jobs."""
    from src.optimizer.optimizer_queue import JobStatus
    
    status_enum = None
    if status:
        try:
            status_enum = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    jobs = optimizer_queue.list_jobs(status_enum, limit)
    
    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs)
    }


@app.delete("/api/optimize/job/{job_id}")
async def cancel_optimization_job(job_id: str):
    """Cancel an optimization job."""
    success = optimizer_queue.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    return {"message": "Job cancelled successfully"}


@app.get("/api/optimize/stats")
async def get_optimizer_stats():
    """Get optimizer queue statistics."""
    return optimizer_queue.get_queue_stats()


# ==================== ML Prediction Endpoints ====================

@app.post("/api/ml/train")
async def train_ml_model(
    symbol: str,
    model_type: str = "classification",
    algorithm: str = "xgboost",
    prediction_horizon: int = 1,
    training_period: str = "1y"
):
    """Train ML model for price prediction."""
    try:
        # Fetch data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=training_period)
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Create and train model
        predictor = PricePredictor(model_type=model_type, algorithm=algorithm)
        metrics = predictor.train(data, prediction_horizon=prediction_horizon)
        
        # Save model (optional - implement model storage)
        # model_path = Path(f"models/{symbol}_{model_type}_{algorithm}.pkl")
        # predictor.save_model(model_path)
        
        return {
            "symbol": symbol,
            "model_type": model_type,
            "algorithm": algorithm,
            "metrics": metrics,
            "training_samples": len(data),
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/predict")
async def predict_price(
    symbol: str,
    model_type: str = "classification",
    algorithm: str = "xgboost",
    periods_ahead: int = 1
):
    """Make price predictions for a symbol."""
    try:
        # Fetch recent data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="3mo")
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Train model (in production, load pre-trained model)
        predictor = PricePredictor(model_type=model_type, algorithm=algorithm)
        
        # Use last 2 months for training
        train_data = data.iloc[:-20]
        predictor.train(train_data, prediction_horizon=periods_ahead)
        
        # Predict on recent data
        recent_data = data.iloc[-20:]
        predictions = predictor.predict(recent_data, return_confidence=True)
        
        # Get top features
        top_features = predictor.get_top_features(10)
        
        return {
            "symbol": symbol,
            "predictions": predictions.tail(5).to_dict('records'),
            "latest_prediction": predictions.iloc[-1].to_dict(),
            "top_features": top_features.to_dict() if not top_features.empty else {},
            "model_type": model_type,
            "algorithm": algorithm
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/backtest")
async def backtest_ml_model(
    symbol: str,
    model_type: str = "classification",
    algorithm: str = "xgboost",
    prediction_horizon: int = 1,
    training_window: int = 252,
    retrain_frequency: int = 20
):
    """Backtest ML model with walk-forward analysis."""
    try:
        # Fetch data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="2y")
        
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Create model and run backtest
        predictor = PricePredictor(model_type=model_type, algorithm=algorithm)
        backtest_results = predictor.backtest_predictions(
            data,
            prediction_horizon=prediction_horizon,
            training_window=training_window,
            retrain_frequency=retrain_frequency
        )
        
        # Calculate summary metrics
        if model_type == "classification":
            accuracy = backtest_results['correct'].mean()
            summary = {
                "accuracy": accuracy,
                "total_predictions": len(backtest_results),
                "avg_confidence": backtest_results['confidence'].mean()
            }
        else:
            from sklearn.metrics import mean_squared_error, mean_absolute_error
            
            mse = mean_squared_error(
                backtest_results['actual_return'],
                backtest_results['predicted']
            )
            mae = mean_absolute_error(
                backtest_results['actual_return'],
                backtest_results['predicted']
            )
            summary = {
                "mse": mse,
                "mae": mae,
                "total_predictions": len(backtest_results)
            }
        
        return {
            "symbol": symbol,
            "model_type": model_type,
            "algorithm": algorithm,
            "summary": summary,
            "recent_results": backtest_results.tail(20).to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Data Source Endpoints ====================

@app.get("/api/data/sources/status")
async def get_data_sources_status():
    """Get connection status for all data sources."""
    return data_provider.get_source_status()


@app.get("/api/data/sources/{source}/symbols")
async def get_source_symbols(source: str):
    """Get available symbols from a data source."""
    from src.data_hub.providers.multi_source import DataSource
    
    try:
        source_enum = DataSource(source)
        symbols = data_provider.get_available_symbols(source_enum)
        
        return {
            "source": source,
            "symbols": symbols,
            "count": len(symbols)
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")


@app.post("/api/data/fetch")
async def fetch_multi_source_data(
    symbol: str,
    timeframe: str = "1d",
    limit: int = 100,
    sources: Optional[List[str]] = None
):
    """Fetch data with automatic fallback between sources."""
    from src.data_hub.providers.multi_source import DataSource
    
    # Convert source strings to enums
    source_enums = None
    if sources:
        try:
            source_enums = [DataSource(s) for s in sources]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Fetch data
    data = await data_provider.fetch_ohlcv_async(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        sources=source_enums
    )
    
    if data is None or data.empty:
        raise HTTPException(status_code=404, detail="No data available from any source")
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data_points": len(data),
        "start_date": data.index[0].isoformat(),
        "end_date": data.index[-1].isoformat(),
        "data": data.tail(10).to_dict('records')
    }


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """API health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "strategies": len(strategy_registry.list_strategies()),
            "optimizer_queue": optimizer_queue.get_queue_stats(),
            "data_sources": len(data_provider.get_source_status())
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)