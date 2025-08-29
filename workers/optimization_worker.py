"""
Optimization worker - processes parameter optimization jobs
"""

import os
import sys
import time
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.backtest import OptimizationJob, Base
from src.strategies.sma_cross import SmaCross, EmaBreakout, RSIMeanReversion
from src.backtest.runner import BacktestRunner
from src.optimization.ga_optimizer import GeneticAlgorithm
from src.optimization.grid_optimizer import GridSearchOptimizer, AdaptiveGrid
from workers.backtest_worker import BacktestWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./backtest.db')
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Strategy registry
STRATEGIES = {
    'sma_cross': SmaCross(),
    'ema_breakout': EmaBreakout(),
    'rsi_reversion': RSIMeanReversion(),
}


class OptimizationWorker:
    """Worker to process optimization jobs"""
    
    def __init__(self):
        self.session = Session()
        self.runner = BacktestRunner()
        self.backtest_worker = BacktestWorker()
        self.running = True
        
    def fetch_pending_job(self):
        """Fetch next pending optimization job"""
        job = self.session.query(OptimizationJob).filter_by(
            status='pending'
        ).order_by(OptimizationJob.created_at).first()
        
        if job:
            job.status = 'running'
            job.started_at = datetime.utcnow()
            self.session.commit()
            logger.info(f"Fetched optimization job {job.id}: {job.strategy} ({job.mode})")
        
        return job
    
    def create_objective_function(self, strategy, symbol: str, timeframe: str):
        """Create objective function for optimization"""
        
        # Fetch data once for all runs
        ohlcv = self.backtest_worker.fetch_ohlcv_data(symbol, timeframe, 1000)
        
        def objective(params: Dict[str, Any]) -> float:
            """Objective function: returns metric to maximize"""
            try:
                # Generate signals
                signals = strategy(ohlcv, params)
                
                # Run backtest
                metrics, _, _, _ = self.runner.run_backtest(ohlcv, signals)
                
                # Optimization metric: Sharpe ratio * (1 - max_drawdown/100)
                # This balances risk-adjusted returns with drawdown control
                sharpe = metrics['sharpe_ratio']
                max_dd = metrics['max_drawdown']
                win_rate = metrics['win_rate']
                
                # Composite score
                score = sharpe * (1 - max_dd / 100) * (win_rate / 100)
                
                return score
                
            except Exception as e:
                logger.error(f"Error in objective function: {e}")
                return -float('inf')
        
        return objective
    
    def process_ga_job(self, job: OptimizationJob):
        """Process genetic algorithm optimization"""
        
        strategy = STRATEGIES.get(job.strategy)
        if not strategy:
            raise ValueError(f"Unknown strategy: {job.strategy}")
        
        # Create objective function
        objective_func = self.create_objective_function(
            strategy, job.symbol, job.timeframe
        )
        
        # GA parameters from job space
        ga_params = job.space_json.get('ga_params', {})
        
        # Initialize GA
        ga = GeneticAlgorithm(
            param_space=strategy.param_ranges,
            fitness_func=objective_func,
            population_size=ga_params.get('population_size', 50),
            generations=ga_params.get('generations', 30),
            crossover_rate=ga_params.get('crossover_rate', 0.8),
            mutation_rate=ga_params.get('mutation_rate', 0.1),
            elite_size=ga_params.get('elite_size', 5)
        )
        
        # Progress callback
        def progress_callback(generation, best_individual):
            progress = (generation + 1) / ga.generations * 100
            job.progress = progress
            job.completed_runs = (generation + 1) * ga.population_size
            job.total_runs = ga.generations * ga.population_size
            
            if best_individual:
                job.best_params = best_individual.params
                job.best_score = best_individual.fitness
            
            self.session.commit()
        
        # Run optimization
        result = ga.optimize(callback=progress_callback)
        
        # Update job with results
        job.best_params = result['best_params']
        job.best_score = result['best_fitness']
        job.status = 'done'
        job.finished_at = datetime.utcnow()
        job.progress = 100
        
        # Save detailed results
        results_file = Path('outputs/optimization') / f'{job.id}_ga_results.json'
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"GA optimization completed. Best score: {result['best_fitness']:.4f}")
    
    def process_grid_job(self, job: OptimizationJob):
        """Process grid search optimization"""
        
        strategy = STRATEGIES.get(job.strategy)
        if not strategy:
            raise ValueError(f"Unknown strategy: {job.strategy}")
        
        # Create objective function
        objective_func = self.create_objective_function(
            strategy, job.symbol, job.timeframe
        )
        
        # Grid parameters
        grid_params = job.space_json.get('grid_params', {})
        use_adaptive = grid_params.get('adaptive', False)
        
        if use_adaptive:
            # Use adaptive grid search
            optimizer = AdaptiveGrid(
                param_space=strategy.param_ranges,
                objective_func=objective_func,
                refinement_factor=grid_params.get('refinement_factor', 0.5)
            )
            
            result = optimizer.optimize(
                iterations=grid_params.get('iterations', 3),
                initial_grid_size=grid_params.get('initial_grid_size', 10)
            )
        else:
            # Standard grid search
            optimizer = GridSearchOptimizer(
                param_space=strategy.param_ranges,
                objective_func=objective_func
            )
            
            # Progress callback
            def progress_callback(current, total, best_result):
                progress = current / total * 100
                job.progress = progress
                job.completed_runs = current
                job.total_runs = total
                
                if best_result:
                    job.best_params = best_result.params
                    job.best_score = best_result.score
                
                self.session.commit()
            
            result = optimizer.optimize(
                callback=progress_callback,
                max_runs=grid_params.get('max_runs')
            )
        
        # Update job with results
        job.best_params = result['best_params']
        job.best_score = result['best_score']
        job.status = 'done'
        job.finished_at = datetime.utcnow()
        job.progress = 100
        
        # Save detailed results
        results_file = Path('outputs/optimization') / f'{job.id}_grid_results.json'
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Grid search completed. Best score: {result['best_score']:.4f}")
    
    def process_job(self, job: OptimizationJob):
        """Process a single optimization job"""
        try:
            logger.info(f"Processing optimization job {job.id}")
            
            if job.mode == 'ga':
                self.process_ga_job(job)
            elif job.mode == 'grid':
                self.process_grid_job(job)
            else:
                raise ValueError(f"Unknown optimization mode: {job.mode}")
            
            self.session.commit()
            logger.info(f"Optimization job {job.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing optimization job {job.id}: {e}")
            logger.error(traceback.format_exc())
            
            # Update job with error
            job.status = 'error'
            job.finished_at = datetime.utcnow()
            self.session.commit()
    
    def run(self):
        """Main worker loop"""
        logger.info("Optimization worker started")
        
        while self.running:
            try:
                # Fetch pending job
                job = self.fetch_pending_job()
                
                if job:
                    self.process_job(job)
                else:
                    # No jobs, wait
                    time.sleep(10)
                    
            except KeyboardInterrupt:
                logger.info("Worker interrupted by user")
                self.running = False
                
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(traceback.format_exc())
                time.sleep(10)
        
        logger.info("Optimization worker stopped")
        self.session.close()


if __name__ == "__main__":
    worker = OptimizationWorker()
    worker.run()