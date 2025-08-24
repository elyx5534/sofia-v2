"""Genetic Algorithm implementation for strategy optimization."""

import random
import numpy as np
from typing import Dict, List, Tuple, Callable, Any, Optional
from dataclasses import dataclass
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json


@dataclass
class Individual:
    """Represents an individual in the population."""
    genes: Dict[str, Any]
    fitness: float = 0.0
    
    def __hash__(self):
        return hash(json.dumps(self.genes, sort_keys=True))


class GeneticAlgorithm:
    """
    Genetic Algorithm optimizer for trading strategies.
    
    This implementation uses evolutionary principles to find optimal
    strategy parameters through selection, crossover, and mutation.
    """
    
    def __init__(
        self,
        param_space: Dict[str, Tuple[Any, Any]],
        fitness_function: Callable[[Dict], float],
        population_size: int = 50,
        generations: int = 100,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        elite_size: int = 5,
        parallel: bool = False
    ):
        """
        Initialize Genetic Algorithm.
        
        Args:
            param_space: Dictionary of parameter names and their (min, max) ranges
            fitness_function: Function that takes parameters and returns fitness score
            population_size: Number of individuals in each generation
            generations: Number of generations to evolve
            crossover_rate: Probability of crossover between parents
            mutation_rate: Probability of mutation for each gene
            elite_size: Number of best individuals to keep unchanged
            parallel: Whether to evaluate fitness in parallel
        """
        self.param_space = param_space
        self.fitness_function = fitness_function
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = min(elite_size, population_size // 2)
        self.parallel = parallel
        
        self.population: List[Individual] = []
        self.best_individual: Optional[Individual] = None
        self.history: List[Dict] = []
    
    def create_individual(self) -> Individual:
        """Create a random individual."""
        genes = {}
        for param, (min_val, max_val) in self.param_space.items():
            if isinstance(min_val, int) and isinstance(max_val, int):
                genes[param] = random.randint(min_val, max_val)
            else:
                genes[param] = random.uniform(min_val, max_val)
        
        return Individual(genes=genes)
    
    def initialize_population(self):
        """Initialize the population with random individuals."""
        self.population = [self.create_individual() for _ in range(self.population_size)]
    
    def evaluate_fitness(self, individual: Individual) -> float:
        """Evaluate fitness of an individual."""
        try:
            fitness = self.fitness_function(individual.genes)
            return fitness
        except Exception as e:
            print(f"Error evaluating fitness: {e}")
            return -float('inf')
    
    def evaluate_population(self):
        """Evaluate fitness for all individuals in the population."""
        if self.parallel:
            with ThreadPoolExecutor(max_workers=4) as executor:
                fitnesses = list(executor.map(self.evaluate_fitness, self.population))
            
            for ind, fitness in zip(self.population, fitnesses):
                ind.fitness = fitness
        else:
            for individual in self.population:
                individual.fitness = self.evaluate_fitness(individual)
    
    def selection(self) -> Tuple[Individual, Individual]:
        """
        Select two parents using tournament selection.
        
        Returns:
            Tuple of two parent individuals
        """
        tournament_size = 3
        
        def tournament():
            candidates = random.sample(self.population, tournament_size)
            return max(candidates, key=lambda x: x.fitness)
        
        return tournament(), tournament()
    
    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """
        Perform crossover between two parents.
        
        Args:
            parent1: First parent
            parent2: Second parent
            
        Returns:
            Tuple of two offspring
        """
        if random.random() > self.crossover_rate:
            return Individual(genes=parent1.genes.copy()), Individual(genes=parent2.genes.copy())
        
        # Uniform crossover
        child1_genes = {}
        child2_genes = {}
        
        for param in self.param_space.keys():
            if random.random() < 0.5:
                child1_genes[param] = parent1.genes[param]
                child2_genes[param] = parent2.genes[param]
            else:
                child1_genes[param] = parent2.genes[param]
                child2_genes[param] = parent1.genes[param]
        
        return Individual(genes=child1_genes), Individual(genes=child2_genes)
    
    def mutate(self, individual: Individual) -> Individual:
        """
        Apply mutation to an individual.
        
        Args:
            individual: Individual to mutate
            
        Returns:
            Mutated individual
        """
        mutated_genes = individual.genes.copy()
        
        for param, (min_val, max_val) in self.param_space.items():
            if random.random() < self.mutation_rate:
                if isinstance(min_val, int) and isinstance(max_val, int):
                    # Integer parameter - small perturbation
                    current = mutated_genes[param]
                    delta = random.randint(-max(1, (max_val - min_val) // 10), 
                                          max(1, (max_val - min_val) // 10))
                    mutated_genes[param] = max(min_val, min(max_val, current + delta))
                else:
                    # Float parameter - gaussian mutation
                    current = mutated_genes[param]
                    sigma = (max_val - min_val) * 0.1
                    mutated_value = current + random.gauss(0, sigma)
                    mutated_genes[param] = max(min_val, min(max_val, mutated_value))
        
        return Individual(genes=mutated_genes)
    
    def evolve_generation(self):
        """Evolve one generation."""
        # Sort population by fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Keep elite individuals
        new_population = self.population[:self.elite_size]
        
        # Generate offspring
        while len(new_population) < self.population_size:
            parent1, parent2 = self.selection()
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)
            
            new_population.extend([child1, child2])
        
        # Trim to population size
        self.population = new_population[:self.population_size]
    
    def run(self) -> Dict[str, Any]:
        """
        Run the genetic algorithm optimization.
        
        Returns:
            Dictionary with best parameters and optimization history
        """
        print(f"Starting Genetic Algorithm optimization...")
        print(f"Population size: {self.population_size}, Generations: {self.generations}")
        
        # Initialize
        self.initialize_population()
        self.evaluate_population()
        
        # Evolution loop
        for generation in range(self.generations):
            # Track best individual
            current_best = max(self.population, key=lambda x: x.fitness)
            if self.best_individual is None or current_best.fitness > self.best_individual.fitness:
                self.best_individual = current_best
            
            # Record history
            fitness_values = [ind.fitness for ind in self.population]
            self.history.append({
                'generation': generation,
                'best_fitness': self.best_individual.fitness,
                'avg_fitness': np.mean(fitness_values),
                'std_fitness': np.std(fitness_values)
            })
            
            # Progress update
            if generation % 10 == 0:
                print(f"Generation {generation}: Best fitness = {self.best_individual.fitness:.4f}")
            
            # Evolve
            if generation < self.generations - 1:  # Don't evolve after last generation
                self.evolve_generation()
                self.evaluate_population()
        
        print(f"\nOptimization complete!")
        print(f"Best parameters: {self.best_individual.genes}")
        print(f"Best fitness: {self.best_individual.fitness:.4f}")
        
        return {
            'best_params': self.best_individual.genes,
            'best_fitness': self.best_individual.fitness,
            'history': self.history,
            'final_population': [
                {'genes': ind.genes, 'fitness': ind.fitness}
                for ind in sorted(self.population, key=lambda x: x.fitness, reverse=True)[:10]
            ]
        }
    
    def adaptive_run(self) -> Dict[str, Any]:
        """
        Run GA with adaptive parameters that change during evolution.
        
        Returns:
            Optimization results with adaptive parameter history
        """
        initial_mutation_rate = self.mutation_rate
        initial_crossover_rate = self.crossover_rate
        
        results = self.run()
        
        # Adaptive schedule: decrease mutation, increase crossover over time
        for gen in range(self.generations):
            progress = gen / self.generations
            self.mutation_rate = initial_mutation_rate * (1 - 0.5 * progress)
            self.crossover_rate = initial_crossover_rate * (1 + 0.2 * progress)
        
        return results


def optimize_strategy_ga(
    strategy_class,
    data: pd.DataFrame,
    param_space: Dict[str, Tuple[Any, Any]],
    metric: str = 'sharpe',
    **ga_kwargs
) -> Dict[str, Any]:
    """
    Optimize a trading strategy using Genetic Algorithm.
    
    Args:
        strategy_class: Strategy class to optimize
        data: Historical price data
        param_space: Parameter search space
        metric: Optimization metric ('sharpe', 'return', 'calmar')
        **ga_kwargs: Additional GA parameters
        
    Returns:
        Optimization results
    """
    from src.backtester.engine import BacktestEngine
    
    engine = BacktestEngine()
    
    def fitness_function(params: Dict) -> float:
        try:
            strategy = strategy_class(**params)
            results = engine.run(data, strategy)
            
            if metric == 'sharpe':
                return results.get('sharpe', 0)
            elif metric == 'return':
                return results.get('return', 0)
            elif metric == 'calmar':
                ret = results.get('return', 0)
                dd = abs(results.get('max_drawdown', -1))
                return ret / dd if dd > 0 else 0
            else:
                return results.get(metric, 0)
        except Exception as e:
            print(f"Backtest error: {e}")
            return -float('inf')
    
    ga = GeneticAlgorithm(
        param_space=param_space,
        fitness_function=fitness_function,
        **ga_kwargs
    )
    
    return ga.run()