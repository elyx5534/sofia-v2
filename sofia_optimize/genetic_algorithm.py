"""
Genetic Algorithm implementation for strategy optimization
"""

import random
import numpy as np
from typing import Dict, List, Callable, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Individual:
    """Represents an individual in the population"""
    genes: Dict[str, float]
    fitness: float = 0.0


class GeneticAlgorithm:
    """Genetic Algorithm for strategy parameter optimization"""
    
    def __init__(
        self,
        param_space: Dict[str, Tuple[float, float]],
        fitness_function: Callable,
        population_size: int = 50,
        generations: int = 100,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        elite_size: int = 5
    ):
        """
        Initialize GA optimizer
        
        Args:
            param_space: Dictionary of parameter names to (min, max) tuples
            fitness_function: Function that takes parameters and returns fitness score
            population_size: Number of individuals in population
            generations: Number of generations to evolve
            crossover_rate: Probability of crossover
            mutation_rate: Probability of mutation
            elite_size: Number of best individuals to keep
        """
        self.param_space = param_space
        self.fitness_function = fitness_function
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        
        self.population = []
        self.best_individual = None
        self.generation_history = []
    
    def initialize_population(self):
        """Create initial random population"""
        self.population = []
        
        for _ in range(self.population_size):
            genes = {}
            for param, (min_val, max_val) in self.param_space.items():
                genes[param] = random.uniform(min_val, max_val)
            
            individual = Individual(genes=genes)
            self.population.append(individual)
        
        logger.info(f"Initialized population with {self.population_size} individuals")
    
    def evaluate_fitness(self):
        """Evaluate fitness for all individuals"""
        for individual in self.population:
            if individual.fitness == 0.0:  # Only evaluate if not already done
                try:
                    individual.fitness = self.fitness_function(individual.genes)
                except Exception as e:
                    logger.error(f"Fitness evaluation failed: {e}")
                    individual.fitness = -float('inf')
    
    def select_parents(self) -> Tuple[Individual, Individual]:
        """Select two parents using tournament selection"""
        tournament_size = 5
        
        def tournament():
            candidates = random.sample(self.population, min(tournament_size, len(self.population)))
            return max(candidates, key=lambda x: x.fitness)
        
        parent1 = tournament()
        parent2 = tournament()
        
        return parent1, parent2
    
    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Perform crossover between two parents"""
        if random.random() > self.crossover_rate:
            return parent1, parent2
        
        # Uniform crossover
        child1_genes = {}
        child2_genes = {}
        
        for param in self.param_space:
            if random.random() < 0.5:
                child1_genes[param] = parent1.genes[param]
                child2_genes[param] = parent2.genes[param]
            else:
                child1_genes[param] = parent2.genes[param]
                child2_genes[param] = parent1.genes[param]
        
        return Individual(genes=child1_genes), Individual(genes=child2_genes)
    
    def mutate(self, individual: Individual) -> Individual:
        """Apply mutation to an individual"""
        mutated_genes = individual.genes.copy()
        
        for param, (min_val, max_val) in self.param_space.items():
            if random.random() < self.mutation_rate:
                # Gaussian mutation
                current_val = mutated_genes[param]
                mutation_strength = (max_val - min_val) * 0.1
                new_val = current_val + random.gauss(0, mutation_strength)
                mutated_genes[param] = max(min_val, min(max_val, new_val))
        
        return Individual(genes=mutated_genes)
    
    def evolve_generation(self):
        """Evolve one generation"""
        # Evaluate fitness
        self.evaluate_fitness()
        
        # Sort by fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Keep elite
        new_population = self.population[:self.elite_size]
        
        # Generate offspring
        while len(new_population) < self.population_size:
            parent1, parent2 = self.select_parents()
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)
            
            new_population.extend([child1, child2])
        
        # Trim to population size
        self.population = new_population[:self.population_size]
    
    def optimize(self) -> Dict[str, Any]:
        """Run the genetic algorithm optimization"""
        logger.info("Starting GA optimization")
        
        # Initialize
        self.initialize_population()
        
        # Evolution loop
        for generation in range(self.generations):
            self.evolve_generation()
            
            # Track best individual
            best_in_gen = max(self.population, key=lambda x: x.fitness)
            self.generation_history.append({
                'generation': generation,
                'best_fitness': best_in_gen.fitness,
                'avg_fitness': np.mean([ind.fitness for ind in self.population])
            })
            
            if self.best_individual is None or best_in_gen.fitness > self.best_individual.fitness:
                self.best_individual = best_in_gen
                logger.info(f"Gen {generation}: New best fitness = {best_in_gen.fitness:.4f}")
            
            # Early stopping if converged
            if len(self.generation_history) > 10:
                recent_best = [h['best_fitness'] for h in self.generation_history[-10:]]
                if max(recent_best) - min(recent_best) < 0.001:
                    logger.info(f"Converged at generation {generation}")
                    break
        
        return {
            'best_params': self.best_individual.genes,
            'best_fitness': self.best_individual.fitness,
            'generations_run': len(self.generation_history),
            'history': self.generation_history
        }


def genetic_search(
    param_space: Dict[str, Tuple[float, float]],
    fitness_fn: Callable,
    generations: int = 50,
    pop_size: int = 30,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function for genetic search
    
    Args:
        param_space: Parameter search space
        fitness_fn: Fitness evaluation function
        generations: Number of generations
        pop_size: Population size
        **kwargs: Additional GA parameters
    
    Returns:
        Dictionary with best parameters and fitness
    """
    ga = GeneticAlgorithm(
        param_space=param_space,
        fitness_function=fitness_fn,
        population_size=pop_size,
        generations=generations,
        **kwargs
    )
    
    result = ga.optimize()
    return result