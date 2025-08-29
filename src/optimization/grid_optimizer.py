"""
Grid Search optimizer for exhaustive parameter optimization
"""

import itertools
from typing import Dict, Any, List, Callable, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GridResult:
    """Result from grid search"""
    params: Dict[str, Any]
    score: float
    
    def __lt__(self, other):
        return self.score < other.score


class GridSearchOptimizer:
    """Grid search for parameter optimization"""
    
    def __init__(
        self,
        param_space: Dict[str, Dict[str, Any]],
        objective_func: Callable[[Dict[str, Any]], float]
    ):
        self.param_space = param_space
        self.objective_func = objective_func
        self.results: List[GridResult] = []
        self.best_result: Optional[GridResult] = None
        self.total_combinations = 0
        self.completed_runs = 0
    
    def _generate_grid(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations"""
        param_lists = {}
        
        for param, config in self.param_space.items():
            if 'values' in config:
                # Categorical parameter
                param_lists[param] = config['values']
            elif 'min' in config and 'max' in config:
                # Numeric parameter
                if isinstance(config['min'], float) or isinstance(config['max'], float):
                    # Float parameter
                    step = config.get('step', 0.1)
                    min_val, max_val = config['min'], config['max']
                    values = []
                    current = min_val
                    while current <= max_val:
                        values.append(round(current, 2))
                        current += step
                    param_lists[param] = values
                else:
                    # Integer parameter
                    step = config.get('step', 1)
                    min_val, max_val = config['min'], config['max']
                    values = list(range(min_val, max_val + 1, step))
                    param_lists[param] = values
        
        # Generate all combinations
        param_names = list(param_lists.keys())
        param_values = [param_lists[name] for name in param_names]
        
        combinations = []
        for values in itertools.product(*param_values):
            combo = dict(zip(param_names, values))
            combinations.append(combo)
        
        return combinations
    
    def optimize(
        self,
        callback: Optional[Callable[[int, int, GridResult], None]] = None,
        max_runs: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run grid search optimization
        
        Args:
            callback: Optional callback function(current, total, best_result)
            max_runs: Maximum number of runs (for early stopping)
        
        Returns:
            Dictionary with best parameters and results
        """
        logger.info("Starting Grid Search optimization")
        
        # Generate parameter grid
        param_grid = self._generate_grid()
        self.total_combinations = len(param_grid)
        
        logger.info(f"Total parameter combinations: {self.total_combinations}")
        
        if max_runs and max_runs < self.total_combinations:
            logger.info(f"Limiting to {max_runs} runs")
            param_grid = param_grid[:max_runs]
        
        # Evaluate each combination
        for i, params in enumerate(param_grid):
            try:
                # Evaluate objective function
                score = self.objective_func(params)
                
                result = GridResult(params=params, score=score)
                self.results.append(result)
                
                # Update best
                if self.best_result is None or score > self.best_result.score:
                    self.best_result = result
                    logger.info(f"New best score: {score:.4f} with params: {params}")
                
                self.completed_runs += 1
                
                # Progress callback
                if callback:
                    callback(i + 1, len(param_grid), self.best_result)
                
                # Log progress every 10%
                if (i + 1) % max(1, len(param_grid) // 10) == 0:
                    progress = (i + 1) / len(param_grid) * 100
                    logger.info(f"Progress: {progress:.1f}% ({i + 1}/{len(param_grid)})")
                
            except Exception as e:
                logger.error(f"Error evaluating params {params}: {e}")
                continue
        
        # Sort results by score
        self.results.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"Grid search completed. Best score: {self.best_result.score:.4f}")
        
        # Get top 10 results
        top_results = []
        for result in self.results[:10]:
            top_results.append({
                'params': result.params,
                'score': result.score
            })
        
        return {
            'best_params': self.best_result.params,
            'best_score': self.best_result.score,
            'total_runs': self.completed_runs,
            'total_combinations': self.total_combinations,
            'top_10_results': top_results
        }


class AdaptiveGrid:
    """Adaptive grid search that refines search space based on results"""
    
    def __init__(
        self,
        param_space: Dict[str, Dict[str, Any]],
        objective_func: Callable[[Dict[str, Any]], float],
        refinement_factor: float = 0.5
    ):
        self.param_space = param_space
        self.objective_func = objective_func
        self.refinement_factor = refinement_factor
        self.iteration_results = []
    
    def optimize(self, iterations: int = 3, initial_grid_size: int = 10) -> Dict[str, Any]:
        """
        Run adaptive grid search
        
        Args:
            iterations: Number of refinement iterations
            initial_grid_size: Initial grid points per parameter
        
        Returns:
            Best parameters found
        """
        current_space = self.param_space.copy()
        best_overall = None
        
        for iteration in range(iterations):
            logger.info(f"Adaptive iteration {iteration + 1}/{iterations}")
            
            # Adjust grid size
            if iteration == 0:
                # Coarse grid initially
                grid_size = initial_grid_size
            else:
                # Finer grid in later iterations
                grid_size = initial_grid_size * 2
            
            # Create grid search with current space
            grid_search = GridSearchOptimizer(current_space, self.objective_func)
            
            # Run optimization
            result = grid_search.optimize()
            
            self.iteration_results.append(result)
            
            # Update best overall
            if best_overall is None or result['best_score'] > best_overall['best_score']:
                best_overall = result
            
            # Refine search space around best parameters
            if iteration < iterations - 1:
                best_params = result['best_params']
                new_space = {}
                
                for param, config in current_space.items():
                    if 'values' in config:
                        # Keep categorical as is
                        new_space[param] = config
                    else:
                        # Refine numeric parameters
                        best_value = best_params[param]
                        param_range = config['max'] - config['min']
                        new_range = param_range * self.refinement_factor
                        
                        if isinstance(config['min'], float):
                            new_space[param] = {
                                'min': max(config['min'], best_value - new_range / 2),
                                'max': min(config['max'], best_value + new_range / 2),
                                'step': config.get('step', 0.1) / 2  # Finer steps
                            }
                        else:
                            step = config.get('step', 1)
                            new_space[param] = {
                                'min': max(config['min'], int(best_value - new_range / 2)),
                                'max': min(config['max'], int(best_value + new_range / 2)),
                                'step': max(1, step // 2)
                            }
                
                current_space = new_space
                logger.info(f"Refined search space for next iteration")
        
        return {
            'best_params': best_overall['best_params'],
            'best_score': best_overall['best_score'],
            'iterations': self.iteration_results
        }