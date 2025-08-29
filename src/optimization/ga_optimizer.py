"""
Genetic Algorithm optimizer for strategy parameter optimization
"""

import numpy as np
import random
from typing import Dict, Any, List, Tuple, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Individual:
    """Individual in GA population"""
    params: Dict[str, Any]
    fitness: float = -float('inf')
    
    def __lt__(self, other):
        return self.fitness < other.fitness


class GeneticAlgorithm:
    """Genetic Algorithm for parameter optimization"""
    
    def __init__(
        self,
        param_space: Dict[str, Dict[str, Any]],
        fitness_func: Callable[[Dict[str, Any]], float],
        population_size: int = 50,
        generations: int = 30,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        elite_size: int = 5,
        tournament_size: int = 3
    ):
        self.param_space = param_space
        self.fitness_func = fitness_func
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.tournament_size = tournament_size
        
        self.population: List[Individual] = []
        self.best_individual: Optional[Individual] = None
        self.generation_history: List[Dict[str, Any]] = []
    
    def _random_params(self) -> Dict[str, Any]:
        """Generate random parameters from space"""
        params = {}
        for param, config in self.param_space.items():
            if 'values' in config:
                # Categorical parameter
                params[param] = random.choice(config['values'])
            elif 'min' in config and 'max' in config:
                # Numeric parameter
                if isinstance(config['min'], float) or isinstance(config['max'], float):
                    # Float parameter
                    step = config.get('step', 0.1)
                    min_val, max_val = config['min'], config['max']
                    num_steps = int((max_val - min_val) / step) + 1
                    value = min_val + random.randint(0, num_steps - 1) * step
                    params[param] = round(value, 2)
                else:
                    # Integer parameter
                    step = config.get('step', 1)
                    min_val, max_val = config['min'], config['max']
                    num_steps = (max_val - min_val) // step + 1
                    value = min_val + random.randint(0, num_steps - 1) * step
                    params[param] = value
        return params
    
    def _initialize_population(self):
        """Initialize random population"""
        self.population = []
        for _ in range(self.population_size):
            params = self._random_params()
            individual = Individual(params=params)
            self.population.append(individual)
        logger.info(f"Initialized population with {self.population_size} individuals")
    
    def _evaluate_population(self):
        """Evaluate fitness for all individuals"""
        for individual in self.population:
            if individual.fitness == -float('inf'):
                try:
                    individual.fitness = self.fitness_func(individual.params)
                except Exception as e:
                    logger.error(f"Error evaluating fitness: {e}")
                    individual.fitness = -float('inf')
    
    def _tournament_selection(self) -> Individual:
        """Select individual using tournament selection"""
        tournament = random.sample(self.population, self.tournament_size)
        return max(tournament, key=lambda x: x.fitness)
    
    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Perform crossover between two parents"""
        if random.random() > self.crossover_rate:
            return Individual(params=parent1.params.copy()), Individual(params=parent2.params.copy())
        
        # Uniform crossover
        child1_params = {}
        child2_params = {}
        
        for param in self.param_space.keys():
            if random.random() < 0.5:
                child1_params[param] = parent1.params[param]
                child2_params[param] = parent2.params[param]
            else:
                child1_params[param] = parent2.params[param]
                child2_params[param] = parent1.params[param]
        
        return Individual(params=child1_params), Individual(params=child2_params)
    
    def _mutate(self, individual: Individual) -> Individual:
        """Mutate an individual"""
        mutated_params = individual.params.copy()
        
        for param, config in self.param_space.items():
            if random.random() < self.mutation_rate:
                if 'values' in config:
                    # Categorical mutation
                    mutated_params[param] = random.choice(config['values'])
                elif 'min' in config and 'max' in config:
                    # Numeric mutation
                    if isinstance(config['min'], float) or isinstance(config['max'], float):
                        # Float parameter
                        step = config.get('step', 0.1)
                        current = mutated_params[param]
                        # Small mutation: +/- 1-3 steps
                        mutation_steps = random.choice([-3, -2, -1, 1, 2, 3])
                        new_value = current + mutation_steps * step
                        new_value = max(config['min'], min(config['max'], new_value))
                        mutated_params[param] = round(new_value, 2)
                    else:
                        # Integer parameter
                        step = config.get('step', 1)
                        current = mutated_params[param]
                        mutation_steps = random.choice([-2, -1, 1, 2])
                        new_value = current + mutation_steps * step
                        new_value = max(config['min'], min(config['max'], new_value))
                        mutated_params[param] = new_value
        
        return Individual(params=mutated_params)
    
    def optimize(self, callback: Optional[Callable[[int, Individual], None]] = None) -> Dict[str, Any]:
        """
        Run genetic algorithm optimization
        
        Args:
            callback: Optional callback function(generation, best_individual)
        
        Returns:
            Best parameters found
        """
        logger.info("Starting GA optimization")
        
        # Initialize population
        self._initialize_population()
        
        for generation in range(self.generations):
            # Evaluate population
            self._evaluate_population()
            
            # Sort by fitness
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            
            # Update best individual
            if self.population[0].fitness > (self.best_individual.fitness if self.best_individual else -float('inf')):
                self.best_individual = self.population[0]
            
            # Record generation stats
            fitnesses = [ind.fitness for ind in self.population if ind.fitness > -float('inf')]
            if fitnesses:
                stats = {
                    'generation': generation,
                    'best_fitness': self.population[0].fitness,
                    'avg_fitness': np.mean(fitnesses),
                    'std_fitness': np.std(fitnesses),
                    'best_params': self.population[0].params
                }
                self.generation_history.append(stats)
                
                logger.info(
                    f"Generation {generation}: "
                    f"Best={stats['best_fitness']:.4f}, "
                    f"Avg={stats['avg_fitness']:.4f}"
                )
            
            # Callback
            if callback:
                callback(generation, self.best_individual)
            
            # Check for convergence
            if generation > 10:
                recent_best = [h['best_fitness'] for h in self.generation_history[-5:]]
                if len(set(recent_best)) == 1:
                    logger.info(f"Converged at generation {generation}")
                    break
            
            # Create next generation
            new_population = []
            
            # Elitism: keep best individuals
            for i in range(self.elite_size):
                new_population.append(Individual(params=self.population[i].params.copy()))
            
            # Generate rest of population
            while len(new_population) < self.population_size:
                # Selection
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()
                
                # Crossover
                child1, child2 = self._crossover(parent1, parent2)
                
                # Mutation
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)
                
                new_population.extend([child1, child2])
            
            # Trim to population size
            self.population = new_population[:self.population_size]
        
        # Final evaluation
        self._evaluate_population()
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        if self.population[0].fitness > (self.best_individual.fitness if self.best_individual else -float('inf')):
            self.best_individual = self.population[0]
        
        logger.info(f"GA optimization completed. Best fitness: {self.best_individual.fitness:.4f}")
        
        return {
            'best_params': self.best_individual.params,
            'best_fitness': self.best_individual.fitness,
            'generations_run': len(self.generation_history),
            'history': self.generation_history
        }