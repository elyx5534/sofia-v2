"""Async queue system for Genetic Algorithm optimization jobs."""

import asyncio
import json
import logging
import pickle
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .genetic_algorithm import GeneticAlgorithm

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Optimization job status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(int, Enum):
    """Job priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class OptimizationJob:
    """Represents an optimization job."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    symbol: str = ""
    param_space: Dict[str, tuple] = field(default_factory=dict)
    optimization_target: str = "sharpe"
    ga_params: Dict[str, Any] = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    current_generation: int = 0
    best_fitness: float = 0.0
    best_params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "param_space": self.param_space,
            "optimization_target": self.optimization_target,
            "ga_params": self.ga_params,
            "priority": self.priority.value,
            "status": self.status.value,
            "progress": self.progress,
            "current_generation": self.current_generation,
            "best_fitness": self.best_fitness,
            "best_params": self.best_params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class OptimizationQueue:
    """
    Async queue system for managing GA optimization jobs.
    Supports priority queue, concurrent execution, and progress tracking.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 2, storage_path: Optional[Path] = None):
        """
        Initialize optimization queue.

        Args:
            max_workers: Maximum concurrent optimization jobs
            storage_path: Path to store job results (optional)
        """
        if self._initialized:
            return
        self.max_workers = max_workers
        self.storage_path = storage_path or Path("optimization_results")
        self.storage_path.mkdir(exist_ok=True)
        self.jobs: Dict[str, OptimizationJob] = {}
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.workers: List[asyncio.Task] = []
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        self.progress_callbacks: Dict[str, Callable] = {}
        self._initialized = True
        self._running = False

    async def start(self):
        """Start the queue workers."""
        if self._running:
            return
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        logger.info(f"Started {self.max_workers} optimization workers")

    async def stop(self):
        """Stop all workers gracefully."""
        self._running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.executor.shutdown(wait=True)
        logger.info("Optimization queue stopped")

    async def _worker(self, name: str):
        """Worker coroutine that processes jobs from the queue."""
        logger.info(f"{name} started")
        while self._running:
            try:
                priority_inverse, job_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            job = self.jobs.get(job_id)
            if not job:
                continue
            logger.info(f"{name} processing job {job_id}")
            try:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                await self._run_optimization(job)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                self._save_job_results(job)
                logger.info(f"{name} completed job {job_id}")
            except Exception as e:
                logger.error(f"{name} failed job {job_id}: {e}")
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.utcnow()

    async def _run_optimization(self, job: OptimizationJob):
        """Run GA optimization for a job."""
        import yfinance as yf

        from src.backtester.strategies.registry import StrategyRegistry

        try:
            registry = StrategyRegistry()
            strategy_class = registry.get_strategy(job.strategy_name)
            if not strategy_class:
                raise ValueError(f"Strategy {job.strategy_name} not found")
            ticker = yf.Ticker(job.symbol)
            data = ticker.history(period="1y")
            if data.empty:
                raise ValueError(f"No data found for {job.symbol}")
            ga_params = {
                "population_size": 50,
                "generations": 100,
                "crossover_rate": 0.8,
                "mutation_rate": 0.1,
                "elite_size": 5,
                **job.ga_params,
            }

            def fitness_function(params: Dict) -> float:
                from src.backtester.engine import BacktestEngine

                try:
                    strategy = strategy_class(**params)
                    engine = BacktestEngine()
                    results = engine.run(data, strategy)
                    if job.optimization_target == "sharpe":
                        return results.get("sharpe", 0)
                    elif job.optimization_target == "return":
                        return results.get("total_return", 0)
                    elif job.optimization_target == "calmar":
                        ret = results.get("total_return", 0)
                        dd = abs(results.get("max_drawdown", -1))
                        return ret / dd if dd > 0 else 0
                    else:
                        return results.get(job.optimization_target, 0)
                except Exception as e:
                    logger.error(f"Fitness calculation error: {e}")
                    return -float("inf")

            ga = GeneticAlgorithm(
                param_space=job.param_space, fitness_function=fitness_function, **ga_params
            )
            original_run = ga.run

            def run_with_progress():
                ga.initialize_population()
                ga.evaluate_population()
                for generation in range(ga.generations):
                    job.current_generation = generation
                    job.progress = generation / ga.generations * 100
                    current_best = max(ga.population, key=lambda x: x.fitness)
                    if (
                        ga.best_individual is None
                        or current_best.fitness > ga.best_individual.fitness
                    ):
                        ga.best_individual = current_best
                        job.best_fitness = current_best.fitness
                        job.best_params = current_best.genes
                    if job.id in self.progress_callbacks:
                        asyncio.create_task(self.progress_callbacks[job.id](job))
                    if generation < ga.generations - 1:
                        ga.evolve_generation()
                        ga.evaluate_population()
                return {
                    "best_params": ga.best_individual.genes,
                    "best_fitness": ga.best_individual.fitness,
                    "history": ga.history,
                    "final_population": [
                        {"genes": ind.genes, "fitness": ind.fitness}
                        for ind in sorted(ga.population, key=lambda x: x.fitness, reverse=True)[:10]
                    ],
                }

            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, run_with_progress
            )
            job.result = result
            job.progress = 100.0
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            raise

    def _save_job_results(self, job: OptimizationJob):
        """Save job results to disk."""
        try:
            json_path = self.storage_path / f"{job.id}.json"
            with open(json_path, "w") as f:
                json.dump(job.to_dict(), f, indent=2)
            if job.result:
                pickle_path = self.storage_path / f"{job.id}.pkl"
                with open(pickle_path, "wb") as f:
                    pickle.dump(job.result, f)
        except Exception as e:
            logger.error(f"Failed to save job results: {e}")

    async def submit_job(
        self,
        strategy_name: str,
        symbol: str,
        param_space: Dict[str, tuple],
        optimization_target: str = "sharpe",
        ga_params: Optional[Dict[str, Any]] = None,
        priority: JobPriority = JobPriority.NORMAL,
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        Submit a new optimization job to the queue.

        Args:
            strategy_name: Name of strategy to optimize
            symbol: Trading symbol
            param_space: Parameter search space
            optimization_target: Metric to optimize
            ga_params: GA algorithm parameters
            priority: Job priority
            progress_callback: Async callback for progress updates

        Returns:
            Job ID
        """
        job = OptimizationJob(
            strategy_name=strategy_name,
            symbol=symbol,
            param_space=param_space,
            optimization_target=optimization_target,
            ga_params=ga_params or {},
            priority=priority,
        )
        self.jobs[job.id] = job
        if progress_callback:
            self.progress_callbacks[job.id] = progress_callback
        await self.queue.put((-priority.value, job.id))
        logger.info(f"Submitted optimization job {job.id}")
        return job.id

    def get_job(self, job_id: str) -> Optional[OptimizationJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(
        self, status: Optional[JobStatus] = None, limit: int = 50
    ) -> List[OptimizationJob]:
        """List jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            return True
        return False

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        jobs_by_status = {}
        for status in JobStatus:
            jobs_by_status[status.value] = len(
                [j for j in self.jobs.values() if j.status == status]
            )
        return {
            "total_jobs": len(self.jobs),
            "queue_size": self.queue.qsize(),
            "max_workers": self.max_workers,
            "active_workers": len([w for w in self.workers if not w.done()]),
            "jobs_by_status": jobs_by_status,
        }


optimizer_queue = OptimizationQueue()
