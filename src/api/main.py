"""Main API application with all endpoints."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Setup logger first
logger = logging.getLogger(__name__)

# Import routers and services with error handling
try:
    from src.backtester.strategies.registry import StrategyRegistry
except ImportError:
    logger.warning("StrategyRegistry not available")
    StrategyRegistry = None

try:
    from src.optimizer.optimizer_queue import JobPriority, optimizer_queue
except ImportError:
    logger.warning("Optimizer queue not available")
    optimizer_queue = None
    JobPriority = None

try:
    from src.ml.price_predictor import PricePredictor
except ImportError:
    logger.warning("PricePredictor not available")
    PricePredictor = None

try:
    from src.data_hub.providers.multi_source import MultiSourceDataProvider
except ImportError:
    logger.warning("MultiSourceDataProvider not available")
    MultiSourceDataProvider = None

try:
    from src.api.live_proof import router as live_router
except ImportError:
    logger.warning("Live proof router not available")
    live_router = None

try:
    from src.api.pnl import router as pnl_router
except ImportError:
    logger.warning("PnL router not available")
    pnl_router = None

try:
    from src.api.dashboard import router as old_dashboard_router
except ImportError:
    logger.warning("Old dashboard router not available")
    old_dashboard_router = None
import os

import psutil
import yfinance as yf
from fastapi import status

# Create FastAPI app
app = FastAPI(
    title="Sofia Trading Platform API",
    description="Complete backend API for trading strategies, optimization, and ML predictions",
    version="2.0.0",
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
# Initialize services only if available
data_provider = MultiSourceDataProvider() if MultiSourceDataProvider else None
ml_predictor = PricePredictor() if PricePredictor else None

# Include routers if available
if live_router:
    app.include_router(live_router)
if pnl_router:
    app.include_router(pnl_router)
# Don't include old dashboard router - using new UI templates instead
# if old_dashboard_router:
#     app.include_router(old_dashboard_router)

# Try to include backtester router
try:
    from src.backtester.api import router as backtester_router

    app.include_router(backtester_router, prefix="/api/backtest")
except ImportError:
    logger.warning("Backtester router not available")
    from fastapi import APIRouter

    backtester_router = APIRouter()
    app.include_router(backtester_router, prefix="/api/backtest")

# Include new routers for UI wireup
try:
    from src.api.routes.quotes import router as quotes_router

    app.include_router(quotes_router)
except ImportError as e:
    logger.warning(f"Quotes router not available: {e}")

# Include enhanced quotes v2 router
try:
    from src.api.routes.quotes_v2 import router as quotes_v2_router

    app.include_router(quotes_v2_router, prefix="/v2")
except ImportError as e:
    logger.warning(f"Quotes v2 router not available: {e}")

try:
    from src.api.routes.backtest import router as new_backtest_router

    app.include_router(new_backtest_router)
except ImportError as e:
    logger.warning(f"New backtest router not available: {e}")

try:
    from src.api.routes.paper import router as paper_router

    app.include_router(paper_router)
except ImportError as e:
    logger.warning(f"Paper router not available: {e}")

try:
    from src.api.routes.live import router as live_trading_router

    app.include_router(live_trading_router)
except ImportError as e:
    logger.warning(f"Live trading router not available: {e}")

try:
    from src.api.routes.arbitrage import router as arb_router

    app.include_router(arb_router)
except ImportError as e:
    logger.warning(f"Arbitrage router not available: {e}")

# Mount UI routes
try:
    from src.api.ui_server import mount_ui_routes

    mount_ui_routes(app)
    logger.info("UI routes mounted successfully")
except ImportError as e:
    logger.warning(f"UI server not available: {e}")

# ==================== Health Check Endpoints ====================


@app.get("/api/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check endpoint for deployment."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "deployment": os.getenv("DEPLOYMENT", "local"),
        "version": "2.0.0",
    }


@app.get("/api/dev/status")
async def dev_status():
    """Detailed status for developers (fast endpoint)."""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        return {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "deployment": os.getenv("DEPLOYMENT", "local"),
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
            },
            "services": {
                "optimizer_queue": "running" if optimizer_queue else "stopped",
                "strategy_registry": "loaded" if strategy_registry else "not_loaded",
                "ml_predictor": "ready" if ml_predictor else "not_ready",
            },
            "uptime_seconds": (
                (datetime.now() - app.state.startup_time).total_seconds()
                if hasattr(app.state, "startup_time")
                else 0
            ),
        }
    except Exception as e:
        logger.error(f"Error getting dev status: {e}")
        return {"status": "degraded", "error": str(e), "timestamp": datetime.now().isoformat()}


@app.get("/api/readiness")
async def readiness_check():
    """Readiness probe for Kubernetes/Docker."""
    # Check if critical services are ready
    checks = {
        "optimizer": optimizer_queue is not None,
        "strategies": len(strategy_registry.list_strategies()) > 0,
        "data_provider": data_provider is not None,
    }

    all_ready = all(checks.values())

    return {"ready": all_ready, "checks": checks, "timestamp": datetime.now().isoformat()}


@app.get("/api/liveness")
async def liveness_check():
    """Liveness probe - always returns OK if app is running."""
    return {"alive": True, "timestamp": datetime.now().isoformat()}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Record startup time
    app.state.startup_time = datetime.now()

    # Start optimizer queue
    await optimizer_queue.start()
    logger.info("Optimizer queue started")

    logger.info(f"API started in {os.getenv('DEPLOYMENT', 'local')} mode")


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
        "total": len(strategies),
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
        return {"valid": True, "validated_parameters": validated}
    except ValueError as e:
        return {"valid": False, "error": str(e)}


# ==================== Optimization Endpoints ====================


@app.post("/api/optimize/submit")
async def submit_optimization(
    strategy_name: str,
    symbol: str,
    param_space: Dict[str, List[float]],
    optimization_target: str = "sharpe",
    ga_params: Optional[Dict[str, Any]] = None,
    priority: str = "normal",
):
    """Submit a new optimization job to the queue."""
    # Convert param_space lists to tuples
    param_space_tuples = {k: tuple(v) for k, v in param_space.items()}

    # Convert priority string to enum
    priority_map = {
        "low": JobPriority.LOW,
        "normal": JobPriority.NORMAL,
        "high": JobPriority.HIGH,
        "urgent": JobPriority.URGENT,
    }
    job_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)

    # Submit job
    job_id = await optimizer_queue.submit_job(
        strategy_name=strategy_name,
        symbol=symbol,
        param_space=param_space_tuples,
        optimization_target=optimization_target,
        ga_params=ga_params,
        priority=job_priority,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Optimization job submitted successfully",
    }


@app.get("/api/optimize/job/{job_id}")
async def get_optimization_job(job_id: str):
    """Get status and results of an optimization job."""
    job = optimizer_queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@app.get("/api/optimize/jobs")
async def list_optimization_jobs(status: Optional[str] = None, limit: int = 50):
    """List optimization jobs."""
    from src.optimizer.optimizer_queue import JobStatus

    status_enum = None
    if status:
        try:
            status_enum = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    jobs = optimizer_queue.list_jobs(status_enum, limit)

    return {"jobs": [j.to_dict() for j in jobs], "total": len(jobs)}


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
    training_period: str = "1y",
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
            "status": "success",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/predict")
async def predict_price(
    symbol: str,
    model_type: str = "classification",
    algorithm: str = "xgboost",
    periods_ahead: int = 1,
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
            "predictions": predictions.tail(5).to_dict("records"),
            "latest_prediction": predictions.iloc[-1].to_dict(),
            "top_features": top_features.to_dict() if not top_features.empty else {},
            "model_type": model_type,
            "algorithm": algorithm,
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
    retrain_frequency: int = 20,
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
            retrain_frequency=retrain_frequency,
        )

        # Calculate summary metrics
        if model_type == "classification":
            accuracy = backtest_results["correct"].mean()
            summary = {
                "accuracy": accuracy,
                "total_predictions": len(backtest_results),
                "avg_confidence": backtest_results["confidence"].mean(),
            }
        else:
            from sklearn.metrics import mean_absolute_error, mean_squared_error

            mse = mean_squared_error(
                backtest_results["actual_return"], backtest_results["predicted"]
            )
            mae = mean_absolute_error(
                backtest_results["actual_return"], backtest_results["predicted"]
            )
            summary = {"mse": mse, "mae": mae, "total_predictions": len(backtest_results)}

        return {
            "symbol": symbol,
            "model_type": model_type,
            "algorithm": algorithm,
            "summary": summary,
            "recent_results": backtest_results.tail(20).to_dict("records"),
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

        return {"source": source, "symbols": symbols, "count": len(symbols)}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")


@app.post("/api/data/fetch")
async def fetch_multi_source_data(
    symbol: str, timeframe: str = "1d", limit: int = 100, sources: Optional[List[str]] = None
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
        symbol=symbol, timeframe=timeframe, limit=limit, sources=source_enums
    )

    if data is None or data.empty:
        raise HTTPException(status_code=404, detail="No data available from any source")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data_points": len(data),
        "start_date": data.index[0].isoformat(),
        "end_date": data.index[-1].isoformat(),
        "data": data.tail(10).to_dict("records"),
    }


# ==================== Health Check ====================


@app.get("/api/health")
async def api_health_check():
    """API health check endpoint."""
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    """Detailed health check with service status."""
    import time

    import psutil

    services = {}

    try:
        if StrategyRegistry:
            strategy_registry = StrategyRegistry()
            services["strategies"] = len(strategy_registry.list_strategies())
    except:
        services["strategies"] = 0

    try:
        if optimizer_queue:
            services["optimizer_queue"] = optimizer_queue.get_queue_stats()
    except:
        services["optimizer_queue"] = {}

    try:
        if data_provider:
            services["data_sources"] = len(data_provider.get_source_status())
    except:
        services["data_sources"] = 0

    # Add system metrics
    process = psutil.Process()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": time.time() - process.create_time(),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "cpu_percent": process.cpu_percent(),
        "services": services,
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    import time

    # Collect metrics
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    cpu_percent = process.cpu_percent()
    uptime = time.time() - process.create_time()

    # Get request metrics (would need middleware to track properly)
    request_count = getattr(app.state, "request_count", 0)
    request_latency = getattr(app.state, "avg_latency_ms", 0)

    # Format as Prometheus text format
    metrics = []
    metrics.append("# HELP sofia_uptime_seconds API uptime in seconds")
    metrics.append("# TYPE sofia_uptime_seconds gauge")
    metrics.append(f"sofia_uptime_seconds {uptime:.2f}")

    metrics.append("# HELP sofia_memory_mb Memory usage in MB")
    metrics.append("# TYPE sofia_memory_mb gauge")
    metrics.append(f"sofia_memory_mb {memory_mb:.2f}")

    metrics.append("# HELP sofia_cpu_percent CPU usage percentage")
    metrics.append("# TYPE sofia_cpu_percent gauge")
    metrics.append(f"sofia_cpu_percent {cpu_percent:.2f}")

    metrics.append("# HELP sofia_request_total Total number of requests")
    metrics.append("# TYPE sofia_request_total counter")
    metrics.append(f"sofia_request_total {request_count}")

    metrics.append("# HELP sofia_request_latency_ms Average request latency")
    metrics.append("# TYPE sofia_request_latency_ms gauge")
    metrics.append(f"sofia_request_latency_ms {request_latency:.2f}")

    # Add trading metrics if available
    try:
        from src.services.paper_engine import paper_engine

        status = paper_engine.get_status()
        if status["running"]:
            metrics.append("# HELP sofia_paper_pnl Paper trading P&L")
            metrics.append("# TYPE sofia_paper_pnl gauge")
            metrics.append(f"sofia_paper_pnl {status['pnl']:.2f}")

            metrics.append("# HELP sofia_paper_trades_total Total paper trades")
            metrics.append("# TYPE sofia_paper_trades_total counter")
            metrics.append(f"sofia_paper_trades_total {status['num_trades']}")
    except:
        pass

    return "\n".join(metrics)


# Add middleware for request tracking
@app.middleware("http")
async def track_requests(request, call_next):
    """Track request metrics for Prometheus."""
    import time

    # Initialize state if needed
    if not hasattr(app.state, "request_count"):
        app.state.request_count = 0
        app.state.total_latency_ms = 0
        app.state.avg_latency_ms = 0

    # Track request
    start_time = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start_time) * 1000

    # Update metrics
    app.state.request_count += 1
    app.state.total_latency_ms += latency_ms
    app.state.avg_latency_ms = app.state.total_latency_ms / app.state.request_count

    return response


# ==================== Missing Dashboard Endpoints ====================


@app.get("/api/pnl/summary")
async def get_pnl_summary():
    """Get P&L summary for dashboard."""
    import json
    from pathlib import Path

    logs_path = Path("logs/pnl_summary.json")
    if logs_path.exists():
        try:
            with open(logs_path) as f:
                return json.load(f)
        except:
            pass

    # Return default if file doesn't exist
    return {
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "session_complete": False,
        "is_running": False,
        "realized": 0.0,
        "unrealized": 0.0,
        "today_pnl": 0.0,
    }


@app.get("/api/pnl/timeseries")
async def get_pnl_timeseries():
    """Get P&L time series for equity chart."""
    import json
    from pathlib import Path

    logs_path = Path("logs/pnl_timeseries.json")
    if logs_path.exists():
        try:
            with open(logs_path) as f:
                return json.load(f)
        except:
            pass

    # Return empty array if file doesn't exist
    return []


@app.get("/api/trades/last")
async def get_last_trades(n: int = 25):
    """Get last N trades."""
    import json
    from pathlib import Path

    logs_path = Path("logs/trades.jsonl")
    if logs_path.exists():
        try:
            trades = []
            with open(logs_path) as f:
                for line in f:
                    if line.strip():
                        trades.append(json.loads(line))
            # Return last N trades
            return trades[-n:] if len(trades) > n else trades
        except:
            pass

    # Return empty array if file doesn't exist
    return []


@app.get("/api/live-guard")
async def get_live_guard():
    """Get live trading guard status."""
    return {
        "enabled": False,
        "approvals": {"operator_A": False, "operator_B": False},
        "requirements": {"readiness": False, "hours_ok": False, "warmup_complete": False},
    }


@app.post("/api/dev/actions")
async def dev_actions(action_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Execute dev actions from dashboard."""
    action = action_data.get("action")

    job_id = f"{action}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if action == "demo":
        # Start 5-minute demo
        minutes = action_data.get("minutes", 5)
        background_tasks.add_task(run_demo_task, job_id, minutes)
        return {"job_id": job_id, "status": "started", "action": "demo", "minutes": minutes}

    elif action == "qa":
        # Run QA proof
        background_tasks.add_task(run_qa_task, job_id)
        return {"job_id": job_id, "status": "started", "action": "qa"}

    elif action == "readiness":
        # Check readiness
        background_tasks.add_task(run_readiness_task, job_id)
        return {"job_id": job_id, "status": "started", "action": "readiness"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


async def run_demo_task(job_id: str, minutes: int):
    """Background task to run demo."""
    import subprocess

    logger.info(f"Starting demo task {job_id} for {minutes} minutes")

    try:
        # Run the actual demo script
        result = subprocess.run(
            ["python", "tools/run_simple_demo.py", str(minutes)],
            capture_output=True,
            text=True,
            timeout=minutes * 60 + 30,
            check=False,  # Give extra 30 seconds
        )

        if result.returncode == 0:
            logger.info(f"Demo task {job_id} completed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"Demo task {job_id} failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error(f"Demo task {job_id} timed out")
    except Exception as e:
        logger.error(f"Demo task {job_id} error: {e}")


async def run_qa_task(job_id: str):
    """Background task to run QA."""
    logger.info(f"Starting QA task {job_id}")
    await asyncio.sleep(5)  # Placeholder
    logger.info(f"QA task {job_id} completed")


async def run_readiness_task(job_id: str):
    """Background task to check readiness."""
    logger.info(f"Starting readiness task {job_id}")
    await asyncio.sleep(5)  # Placeholder
    logger.info(f"Readiness task {job_id} completed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
