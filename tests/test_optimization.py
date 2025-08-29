"""
Tests for optimization algorithms
"""

import pytest
import numpy as np
from typing import Dict, Any

from src.optimization.ga_optimizer import GeneticAlgorithm, Individual
from src.optimization.grid_optimizer import GridSearchOptimizer, AdaptiveGrid


class TestGeneticAlgorithm:
    """Test Genetic Algorithm optimizer"""
    
    @pytest.fixture
    def simple_objective(self):
        """Simple quadratic objective function"""
        def objective(params: Dict[str, Any]) -> float:
            x = params.get('x', 0)
            y = params.get('y', 0)
            # Maximum at x=5, y=5
            return -(x - 5)**2 - (y - 5)**2
        return objective
    
    @pytest.fixture
    def param_space(self):
        """Simple parameter space"""
        return {
            'x': {'min': 0, 'max': 10, 'step': 0.5},
            'y': {'min': 0, 'max': 10, 'step': 0.5},
            'mode': {'values': ['a', 'b', 'c']}
        }
    
    def test_initialization(self, param_space, simple_objective):
        """Test GA initialization"""
        ga = GeneticAlgorithm(
            param_space=param_space,
            fitness_func=simple_objective,
            population_size=20,
            generations=10
        )
        
        assert ga.population_size == 20
        assert ga.generations == 10
        assert ga.crossover_rate == 0.8
        assert ga.mutation_rate == 0.1
    
    def test_random_params_generation(self, param_space, simple_objective):
        """Test random parameter generation"""
        ga = GeneticAlgorithm(param_space, simple_objective)
        
        for _ in range(10):
            params = ga._random_params()
            
            assert 0 <= params['x'] <= 10
            assert 0 <= params['y'] <= 10
            assert params['mode'] in ['a', 'b', 'c']
    
    def test_optimization(self, param_space, simple_objective):
        """Test GA optimization"""
        ga = GeneticAlgorithm(
            param_space=param_space,
            fitness_func=simple_objective,
            population_size=20,
            generations=20,
            elite_size=3
        )
        
        result = ga.optimize()
        
        assert 'best_params' in result
        assert 'best_fitness' in result
        assert 'generations_run' in result
        assert 'history' in result
        
        # Should find values close to optimum (x=5, y=5)
        best_x = result['best_params']['x']
        best_y = result['best_params']['y']
        
        assert abs(best_x - 5) < 2  # Within 2 of optimum
        assert abs(best_y - 5) < 2
        assert result['best_fitness'] > -10  # Reasonable fitness
    
    def test_crossover(self, param_space, simple_objective):
        """Test crossover operation"""
        ga = GeneticAlgorithm(param_space, simple_objective)
        
        parent1 = Individual(params={'x': 2, 'y': 3, 'mode': 'a'})
        parent2 = Individual(params={'x': 8, 'y': 7, 'mode': 'b'})
        
        child1, child2 = ga._crossover(parent1, parent2)
        
        # Children should have mix of parent genes
        assert child1.params['x'] in [2, 8]
        assert child1.params['y'] in [3, 7]
        assert child1.params['mode'] in ['a', 'b']
    
    def test_mutation(self, param_space, simple_objective):
        """Test mutation operation"""
        ga = GeneticAlgorithm(param_space, simple_objective)
        ga.mutation_rate = 1.0  # Force mutation
        
        individual = Individual(params={'x': 5, 'y': 5, 'mode': 'a'})
        mutated = ga._mutate(individual)
        
        # At least one parameter should change
        assert (mutated.params['x'] != 5 or 
                mutated.params['y'] != 5 or 
                mutated.params['mode'] != 'a')
    
    def test_convergence(self, param_space, simple_objective):
        """Test early convergence detection"""
        ga = GeneticAlgorithm(
            param_space=param_space,
            fitness_func=simple_objective,
            population_size=10,
            generations=100  # Set high, but should converge early
        )
        
        result = ga.optimize()
        
        # Should converge before max generations
        assert result['generations_run'] < 100


class TestGridSearchOptimizer:
    """Test Grid Search optimizer"""
    
    @pytest.fixture
    def simple_objective(self):
        """Simple objective function"""
        def objective(params: Dict[str, Any]) -> float:
            x = params.get('x', 0)
            y = params.get('y', 0)
            # Maximum at x=5, y=5
            return -(x - 5)**2 - (y - 5)**2
        return objective
    
    @pytest.fixture
    def small_param_space(self):
        """Small parameter space for fast testing"""
        return {
            'x': {'min': 3, 'max': 7, 'step': 1},
            'y': {'min': 3, 'max': 7, 'step': 1},
        }
    
    def test_initialization(self, small_param_space, simple_objective):
        """Test grid search initialization"""
        optimizer = GridSearchOptimizer(small_param_space, simple_objective)
        
        assert optimizer.param_space == small_param_space
        assert optimizer.total_combinations == 0
        assert optimizer.completed_runs == 0
    
    def test_grid_generation(self, small_param_space, simple_objective):
        """Test parameter grid generation"""
        optimizer = GridSearchOptimizer(small_param_space, simple_objective)
        grid = optimizer._generate_grid()
        
        # Should have 5x5 = 25 combinations
        assert len(grid) == 25
        
        # Check all combinations are present
        x_values = [3, 4, 5, 6, 7]
        y_values = [3, 4, 5, 6, 7]
        
        for x in x_values:
            for y in y_values:
                assert {'x': x, 'y': y} in grid
    
    def test_optimization(self, small_param_space, simple_objective):
        """Test grid search optimization"""
        optimizer = GridSearchOptimizer(small_param_space, simple_objective)
        result = optimizer.optimize()
        
        assert 'best_params' in result
        assert 'best_score' in result
        assert 'total_runs' in result
        assert 'total_combinations' in result
        assert 'top_10_results' in result
        
        # Should find optimum at x=5, y=5
        assert result['best_params']['x'] == 5
        assert result['best_params']['y'] == 5
        assert result['best_score'] == 0  # Maximum value
        assert result['total_runs'] == 25
    
    def test_max_runs_limit(self, small_param_space, simple_objective):
        """Test max_runs parameter"""
        optimizer = GridSearchOptimizer(small_param_space, simple_objective)
        result = optimizer.optimize(max_runs=10)
        
        assert result['total_runs'] == 10
        assert result['total_combinations'] == 25
    
    def test_callback(self, small_param_space, simple_objective):
        """Test progress callback"""
        optimizer = GridSearchOptimizer(small_param_space, simple_objective)
        
        progress_log = []
        
        def callback(current, total, best_result):
            progress_log.append({
                'current': current,
                'total': total,
                'best_score': best_result.score if best_result else None
            })
        
        result = optimizer.optimize(callback=callback)
        
        assert len(progress_log) == 25
        assert progress_log[-1]['current'] == 25
        assert progress_log[-1]['best_score'] == 0


class TestAdaptiveGrid:
    """Test Adaptive Grid Search"""
    
    @pytest.fixture
    def simple_objective(self):
        """Simple objective function"""
        def objective(params: Dict[str, Any]) -> float:
            x = params.get('x', 0)
            # Maximum at x=5
            return -(x - 5)**2
        return objective
    
    @pytest.fixture
    def param_space(self):
        """Parameter space"""
        return {
            'x': {'min': 0, 'max': 10, 'step': 1}
        }
    
    def test_initialization(self, param_space, simple_objective):
        """Test adaptive grid initialization"""
        optimizer = AdaptiveGrid(
            param_space=param_space,
            objective_func=simple_objective,
            refinement_factor=0.5
        )
        
        assert optimizer.refinement_factor == 0.5
        assert optimizer.iteration_results == []
    
    def test_adaptive_optimization(self, param_space, simple_objective):
        """Test adaptive grid optimization"""
        optimizer = AdaptiveGrid(
            param_space=param_space,
            objective_func=simple_objective,
            refinement_factor=0.5
        )
        
        result = optimizer.optimize(iterations=2, initial_grid_size=5)
        
        assert 'best_params' in result
        assert 'best_score' in result
        assert 'iterations' in result
        
        # Should find value close to optimum (x=5)
        assert abs(result['best_params']['x'] - 5) <= 1
        assert len(result['iterations']) == 2
        
        # Second iteration should have better or equal score
        if len(result['iterations']) >= 2:
            assert result['iterations'][1]['best_score'] >= result['iterations'][0]['best_score']