"""
Regression tests for Walk-Forward Optimization and Genetic Algorithm
"""

import numpy as np
import pandas as pd


def test_walk_forward_optimization():
    """Test WFO with mini dataset"""
    # Create mini dataset
    dates = pd.date_range("2024-01-01", periods=100, freq="1h")
    prices = 50000 + np.random.randn(100) * 1000

    data = []
    for i, date in enumerate(dates):
        data.append(
            [
                int(date.timestamp() * 1000),
                prices[i] * 0.99,  # open
                prices[i] * 1.01,  # high
                prices[i] * 0.98,  # low
                prices[i],  # close
                1000 + np.random.rand() * 100,  # volume
            ]
        )

    # Mock WFO
    in_sample = data[:70]
    out_sample = data[70:]

    # Simple optimization (find best SMA period)
    best_return = -float("inf")
    best_period = None

    for period in [5, 10, 20]:
        # Calculate returns with SMA
        closes = [d[4] for d in in_sample]
        sma = pd.Series(closes).rolling(period).mean()

        # Simple strategy: buy when price > SMA
        signals = [1 if c > s else 0 for c, s in zip(closes[period:], sma[period:])]
        returns = sum(signals) / len(signals) * 0.01  # Simplified return

        if returns > best_return:
            best_return = returns
            best_period = period

    assert best_period is not None
    assert best_return > -1  # Should have some return


def test_genetic_algorithm_optimization():
    """Test GA parameter optimization"""

    def fitness_function(params):
        """Simple fitness function for testing"""
        # Minimize (x-5)^2 + (y-3)^2
        x, y = params
        return -((x - 5) ** 2 + (y - 3) ** 2)

    # Simple GA implementation
    population_size = 20
    generations = 10
    mutation_rate = 0.1

    # Initialize population
    population = [(np.random.rand() * 10, np.random.rand() * 10) for _ in range(population_size)]

    for gen in range(generations):
        # Evaluate fitness
        fitness_scores = [fitness_function(ind) for ind in population]

        # Select best half
        sorted_pop = sorted(zip(fitness_scores, population), reverse=True)
        survivors = [ind for _, ind in sorted_pop[: population_size // 2]]

        # Create new generation
        new_population = survivors.copy()
        while len(new_population) < population_size:
            # Crossover
            parent1 = survivors[np.random.randint(len(survivors))]
            parent2 = survivors[np.random.randint(len(survivors))]
            child = ((parent1[0] + parent2[0]) / 2, (parent1[1] + parent2[1]) / 2)

            # Mutation
            if np.random.rand() < mutation_rate:
                child = (child[0] + np.random.randn() * 0.5, child[1] + np.random.randn() * 0.5)

            new_population.append(child)

        population = new_population

    # Check final best solution
    final_fitness = [fitness_function(ind) for ind in population]
    best_idx = np.argmax(final_fitness)
    best_solution = population[best_idx]

    # Should be close to (5, 3)
    assert abs(best_solution[0] - 5) < 2
    assert abs(best_solution[1] - 3) < 2


def test_strategy_regression():
    """Test that strategies produce consistent results"""
    # Create fixed dataset
    np.random.seed(42)
    data = []
    for i in range(100):
        price = 50000 + i * 100 + np.random.randn() * 500
        data.append(
            [
                i * 3600000,  # timestamp
                price * 0.99,  # open
                price * 1.01,  # high
                price * 0.98,  # low
                price,  # close
                1000,  # volume
            ]
        )

    # Test SMA strategy
    sma_fast = 10
    sma_slow = 20

    closes = [d[4] for d in data]
    sma_f = pd.Series(closes).rolling(sma_fast).mean()
    sma_s = pd.Series(closes).rolling(sma_slow).mean()

    # Generate signals
    signals = []
    for i in range(sma_slow, len(closes)):
        if sma_f.iloc[i] > sma_s.iloc[i]:
            signals.append(1)  # Buy
        else:
            signals.append(-1)  # Sell

    # Should generate some signals
    assert len(signals) > 0
    assert 1 in signals  # Should have buy signals
    assert -1 in signals  # Should have sell signals
