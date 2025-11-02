"""
Strategy Optimization Engine for Polymarket Whale Copy Trading
Uses genetic algorithms and bayesian optimization for parameter tuning
"""

import asyncio
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging
from decimal import Decimal
import random
from scipy import stats
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel

logger = logging.getLogger(__name__)


@dataclass
class StrategyParameters:
    """Parameters for copy trading strategy"""
    # Whale selection
    min_whale_score: float = 0.7
    max_whales_followed: int = 10
    whale_score_weights: Dict[str, float] = field(default_factory=lambda: {
        'sharpe': 0.30,
        'information_ratio': 0.25,
        'calmar': 0.20,
        'consistency': 0.15,
        'volume': 0.10
    })

    # Position sizing
    kelly_fraction: float = 0.25
    max_position_pct: float = 0.05
    min_position_size: float = 10.0

    # Risk management
    max_daily_loss: float = 0.10
    max_drawdown: float = 0.20
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15

    # Signal filtering
    min_confidence: float = 0.60
    signal_decay_hours: int = 24
    correlation_threshold: float = 0.70

    # Market conditions
    volatility_adjustment: bool = True
    regime_detection: bool = True
    liquidity_threshold: float = 10000

    def to_vector(self) -> np.ndarray:
        """Convert parameters to numpy vector for optimization"""
        return np.array([
            self.min_whale_score,
            self.kelly_fraction,
            self.max_position_pct,
            self.max_daily_loss,
            self.max_drawdown,
            self.stop_loss_pct,
            self.take_profit_pct,
            self.min_confidence,
            self.correlation_threshold,
            self.liquidity_threshold
        ])

    @classmethod
    def from_vector(cls, vector: np.ndarray) -> 'StrategyParameters':
        """Create parameters from numpy vector"""
        return cls(
            min_whale_score=vector[0],
            kelly_fraction=vector[1],
            max_position_pct=vector[2],
            max_daily_loss=vector[3],
            max_drawdown=vector[4],
            stop_loss_pct=vector[5],
            take_profit_pct=vector[6],
            min_confidence=vector[7],
            correlation_threshold=vector[8],
            liquidity_threshold=vector[9]
        )


@dataclass
class OptimizationResult:
    """Results from strategy optimization"""
    best_params: StrategyParameters
    best_score: float
    optimization_history: List[Dict]
    convergence_plot: List[float]
    parameter_importance: Dict[str, float]
    robustness_score: float
    overfitting_score: float
    timestamp: datetime


class GeneticOptimizer:
    """
    Genetic algorithm for strategy optimization
    Evolves population of parameter sets
    """

    def __init__(self,
                 population_size: int = 50,
                 generations: int = 100,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.7,
                 elite_size: int = 5):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = elite_size
        self.bounds = self._define_bounds()

    def _define_bounds(self) -> List[Tuple[float, float]]:
        """Define parameter bounds"""
        return [
            (0.5, 0.95),   # min_whale_score
            (0.1, 0.5),    # kelly_fraction
            (0.01, 0.10),  # max_position_pct
            (0.05, 0.20),  # max_daily_loss
            (0.10, 0.30),  # max_drawdown
            (0.02, 0.10),  # stop_loss_pct
            (0.05, 0.30),  # take_profit_pct
            (0.50, 0.90),  # min_confidence
            (0.50, 0.90),  # correlation_threshold
            (5000, 50000)  # liquidity_threshold
        ]

    def _initialize_population(self) -> List[np.ndarray]:
        """Create initial random population"""
        population = []
        for _ in range(self.population_size):
            individual = []
            for low, high in self.bounds:
                individual.append(random.uniform(low, high))
            population.append(np.array(individual))
        return population

    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """Apply mutation to individual"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if random.random() < self.mutation_rate:
                low, high = self.bounds[i]
                # Gaussian mutation
                mutated[i] += np.random.normal(0, (high - low) * 0.1)
                mutated[i] = np.clip(mutated[i], low, high)
        return mutated

    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Perform crossover between two parents"""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        # Uniform crossover
        child1, child2 = parent1.copy(), parent2.copy()
        for i in range(len(parent1)):
            if random.random() < 0.5:
                child1[i], child2[i] = child2[i], child1[i]

        return child1, child2

    def _tournament_selection(self, population: List[np.ndarray],
                            fitness_scores: List[float],
                            tournament_size: int = 3) -> np.ndarray:
        """Select individual using tournament selection"""
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_idx = tournament_indices[np.argmax(tournament_fitness)]
        return population[winner_idx].copy()

    async def optimize(self, fitness_function: Callable) -> OptimizationResult:
        """Run genetic algorithm optimization"""
        population = self._initialize_population()
        history = []
        convergence = []
        best_individual = None
        best_fitness = -float('inf')

        for generation in range(self.generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                params = StrategyParameters.from_vector(individual)
                fitness = await fitness_function(params)
                fitness_scores.append(fitness)

                # Track best
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual.copy()

            convergence.append(best_fitness)
            history.append({
                'generation': generation,
                'best_fitness': best_fitness,
                'avg_fitness': np.mean(fitness_scores),
                'std_fitness': np.std(fitness_scores)
            })

            # Log progress
            if generation % 10 == 0:
                logger.info(f"Generation {generation}: Best fitness = {best_fitness:.4f}")

            # Create next generation
            new_population = []

            # Elite preservation
            elite_indices = np.argsort(fitness_scores)[-self.elite_size:]
            for idx in elite_indices:
                new_population.append(population[idx].copy())

            # Generate rest of population
            while len(new_population) < self.population_size:
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)

                child1, child2 = self._crossover(parent1, parent2)
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)

                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)

            population = new_population

        # Final evaluation
        best_params = StrategyParameters.from_vector(best_individual)

        # Calculate parameter importance
        importance = await self._calculate_parameter_importance(
            best_individual, fitness_function
        )

        # Calculate robustness
        robustness = await self._calculate_robustness(
            best_individual, fitness_function
        )

        return OptimizationResult(
            best_params=best_params,
            best_score=best_fitness,
            optimization_history=history,
            convergence_plot=convergence,
            parameter_importance=importance,
            robustness_score=robustness,
            overfitting_score=0.0,  # Would calculate with validation set
            timestamp=datetime.now()
        )

    async def _calculate_parameter_importance(self,
                                             best_individual: np.ndarray,
                                             fitness_function: Callable) -> Dict[str, float]:
        """Calculate importance of each parameter"""
        base_fitness = await fitness_function(StrategyParameters.from_vector(best_individual))
        importance = {}
        param_names = [
            'min_whale_score', 'kelly_fraction', 'max_position_pct',
            'max_daily_loss', 'max_drawdown', 'stop_loss_pct',
            'take_profit_pct', 'min_confidence', 'correlation_threshold',
            'liquidity_threshold'
        ]

        for i, name in enumerate(param_names):
            # Perturb parameter
            perturbed = best_individual.copy()
            low, high = self.bounds[i]
            perturbed[i] = np.clip(perturbed[i] * 1.1, low, high)

            # Calculate fitness change
            new_fitness = await fitness_function(StrategyParameters.from_vector(perturbed))
            importance[name] = abs(new_fitness - base_fitness) / abs(base_fitness)

        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v/total for k, v in importance.items()}

        return importance

    async def _calculate_robustness(self,
                                   best_individual: np.ndarray,
                                   fitness_function: Callable,
                                   n_samples: int = 20) -> float:
        """Calculate robustness of parameters to noise"""
        fitness_scores = []

        for _ in range(n_samples):
            # Add small noise to parameters
            noisy = best_individual.copy()
            for i in range(len(noisy)):
                low, high = self.bounds[i]
                noise = np.random.normal(0, (high - low) * 0.02)
                noisy[i] = np.clip(noisy[i] + noise, low, high)

            fitness = await fitness_function(StrategyParameters.from_vector(noisy))
            fitness_scores.append(fitness)

        # Robustness is inverse of coefficient of variation
        mean_fitness = np.mean(fitness_scores)
        std_fitness = np.std(fitness_scores)

        if mean_fitness == 0:
            return 0.0

        cv = std_fitness / abs(mean_fitness)
        robustness = 1.0 / (1.0 + cv)

        return robustness


class BayesianOptimizer:
    """
    Bayesian optimization for strategy parameters
    Uses Gaussian Process to model objective function
    """

    def __init__(self,
                 n_initial_points: int = 20,
                 n_iterations: int = 50,
                 acquisition: str = 'ei'):  # Expected Improvement
        self.n_initial_points = n_initial_points
        self.n_iterations = n_iterations
        self.acquisition = acquisition
        self.bounds = self._define_bounds()
        self.gp = self._create_gp()

    def _define_bounds(self) -> List[Tuple[float, float]]:
        """Define parameter bounds"""
        return [
            (0.5, 0.95),   # min_whale_score
            (0.1, 0.5),    # kelly_fraction
            (0.01, 0.10),  # max_position_pct
            (0.05, 0.20),  # max_daily_loss
            (0.10, 0.30),  # max_drawdown
            (0.02, 0.10),  # stop_loss_pct
            (0.05, 0.30),  # take_profit_pct
            (0.50, 0.90),  # min_confidence
            (0.50, 0.90),  # correlation_threshold
            (5000, 50000)  # liquidity_threshold
        ]

    def _create_gp(self) -> GaussianProcessRegressor:
        """Create Gaussian Process model"""
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
        return GaussianProcessRegressor(
            kernel=kernel,
            alpha=1e-6,
            normalize_y=True,
            n_restarts_optimizer=10
        )

    def _expected_improvement(self, X: np.ndarray,
                            X_sample: np.ndarray,
                            Y_sample: np.ndarray,
                            xi: float = 0.01) -> np.ndarray:
        """Calculate expected improvement acquisition function"""
        mu, sigma = self.gp.predict(X, return_std=True)
        mu = mu.reshape(-1, 1)
        sigma = sigma.reshape(-1, 1)

        # Current best
        Y_best = np.max(Y_sample)

        with np.errstate(divide='warn'):
            Z = (mu - Y_best - xi) / sigma
            ei = (mu - Y_best - xi) * stats.norm.cdf(Z) + sigma * stats.norm.pdf(Z)
            ei[sigma == 0.0] = 0.0

        return ei.flatten()

    def _upper_confidence_bound(self, X: np.ndarray, beta: float = 2.0) -> np.ndarray:
        """Calculate UCB acquisition function"""
        mu, sigma = self.gp.predict(X, return_std=True)
        return mu + beta * sigma

    def _propose_location(self, X_sample: np.ndarray, Y_sample: np.ndarray) -> np.ndarray:
        """Propose next sampling location"""
        # Create grid of candidates
        n_candidates = 10000
        X_candidates = []

        for _ in range(n_candidates):
            candidate = []
            for low, high in self.bounds:
                candidate.append(random.uniform(low, high))
            X_candidates.append(candidate)

        X_candidates = np.array(X_candidates)

        # Calculate acquisition function
        if self.acquisition == 'ei':
            acquisition = self._expected_improvement(X_candidates, X_sample, Y_sample)
        elif self.acquisition == 'ucb':
            acquisition = self._upper_confidence_bound(X_candidates)
        else:
            raise ValueError(f"Unknown acquisition function: {self.acquisition}")

        # Return best candidate
        best_idx = np.argmax(acquisition)
        return X_candidates[best_idx]

    async def optimize(self, fitness_function: Callable) -> OptimizationResult:
        """Run Bayesian optimization"""
        # Initial random sampling
        X_sample = []
        Y_sample = []

        logger.info(f"Bayesian optimization: Initial sampling ({self.n_initial_points} points)")

        for i in range(self.n_initial_points):
            x = []
            for low, high in self.bounds:
                x.append(random.uniform(low, high))
            x = np.array(x)

            params = StrategyParameters.from_vector(x)
            y = await fitness_function(params)

            X_sample.append(x)
            Y_sample.append(y)

            if i % 5 == 0:
                logger.info(f"Initial sample {i}: fitness = {y:.4f}")

        X_sample = np.array(X_sample)
        Y_sample = np.array(Y_sample).reshape(-1, 1)

        history = []
        convergence = [np.max(Y_sample)]

        # Bayesian optimization loop
        for iteration in range(self.n_iterations):
            # Update GP with all observations
            self.gp.fit(X_sample, Y_sample)

            # Find next point to sample
            X_next = self._propose_location(X_sample, Y_sample)

            # Evaluate objective function
            params = StrategyParameters.from_vector(X_next)
            Y_next = await fitness_function(params)

            # Add to samples
            X_sample = np.vstack((X_sample, X_next.reshape(1, -1)))
            Y_sample = np.vstack((Y_sample, [[Y_next]]))

            # Track progress
            best_so_far = np.max(Y_sample)
            convergence.append(best_so_far)

            history.append({
                'iteration': iteration,
                'best_fitness': best_so_far,
                'current_fitness': Y_next,
                'gp_variance': np.mean(self.gp.predict(X_sample, return_std=True)[1])
            })

            if iteration % 10 == 0:
                logger.info(f"Iteration {iteration}: Best fitness = {best_so_far:.4f}")

        # Get best parameters
        best_idx = np.argmax(Y_sample)
        best_individual = X_sample[best_idx]
        best_params = StrategyParameters.from_vector(best_individual)

        # Calculate parameter importance
        importance = await self._calculate_parameter_importance(
            best_individual, fitness_function
        )

        # Calculate robustness
        robustness = await self._calculate_robustness(
            best_individual, fitness_function
        )

        return OptimizationResult(
            best_params=best_params,
            best_score=float(np.max(Y_sample)),
            optimization_history=history,
            convergence_plot=convergence,
            parameter_importance=importance,
            robustness_score=robustness,
            overfitting_score=self._calculate_overfitting(history),
            timestamp=datetime.now()
        )

    async def _calculate_parameter_importance(self,
                                             best_individual: np.ndarray,
                                             fitness_function: Callable) -> Dict[str, float]:
        """Calculate importance of each parameter using sensitivity analysis"""
        base_fitness = await fitness_function(StrategyParameters.from_vector(best_individual))
        importance = {}
        param_names = [
            'min_whale_score', 'kelly_fraction', 'max_position_pct',
            'max_daily_loss', 'max_drawdown', 'stop_loss_pct',
            'take_profit_pct', 'min_confidence', 'correlation_threshold',
            'liquidity_threshold'
        ]

        for i, name in enumerate(param_names):
            sensitivities = []

            # Test multiple perturbations
            for delta in [-0.1, -0.05, 0.05, 0.1]:
                perturbed = best_individual.copy()
                low, high = self.bounds[i]
                perturbed[i] = np.clip(perturbed[i] * (1 + delta), low, high)

                new_fitness = await fitness_function(StrategyParameters.from_vector(perturbed))
                sensitivity = abs(new_fitness - base_fitness) / abs(base_fitness)
                sensitivities.append(sensitivity)

            importance[name] = np.mean(sensitivities)

        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v/total for k, v in importance.items()}

        return importance

    async def _calculate_robustness(self,
                                   best_individual: np.ndarray,
                                   fitness_function: Callable,
                                   n_samples: int = 30) -> float:
        """Calculate robustness to parameter perturbation"""
        fitness_scores = []

        for _ in range(n_samples):
            # Add noise proportional to parameter scale
            noisy = best_individual.copy()
            for i in range(len(noisy)):
                low, high = self.bounds[i]
                noise_scale = (high - low) * 0.01  # 1% noise
                noisy[i] += np.random.normal(0, noise_scale)
                noisy[i] = np.clip(noisy[i], low, high)

            fitness = await fitness_function(StrategyParameters.from_vector(noisy))
            fitness_scores.append(fitness)

        # Calculate stability metrics
        mean_fitness = np.mean(fitness_scores)
        std_fitness = np.std(fitness_scores)

        # Robustness score (higher is better)
        if mean_fitness == 0:
            return 0.0

        cv = std_fitness / abs(mean_fitness)
        robustness = np.exp(-cv)  # Exponential decay with CV

        return float(robustness)

    def _calculate_overfitting(self, history: List[Dict]) -> float:
        """Estimate overfitting from optimization history"""
        if len(history) < 10:
            return 0.0

        # Look at improvement rate over time
        early_improvement = history[10]['best_fitness'] - history[0]['best_fitness']
        late_improvement = history[-1]['best_fitness'] - history[-10]['best_fitness']

        if early_improvement == 0:
            return 0.0

        # If late improvement is much smaller, might be overfitting
        improvement_ratio = late_improvement / early_improvement

        # Also check GP variance trend
        early_variance = np.mean([h['gp_variance'] for h in history[:10]])
        late_variance = np.mean([h['gp_variance'] for h in history[-10:]])

        variance_ratio = late_variance / (early_variance + 1e-6)

        # Combine metrics (0 = no overfit, 1 = high overfit)
        overfitting_score = 1.0 - min(1.0, improvement_ratio * variance_ratio)

        return float(overfitting_score)


class StrategyOptimizer:
    """
    Main strategy optimization orchestrator
    Combines multiple optimization techniques
    """

    def __init__(self, backtester):
        self.backtester = backtester
        self.genetic_optimizer = GeneticOptimizer()
        self.bayesian_optimizer = BayesianOptimizer()

    async def create_fitness_function(self,
                                     historical_data: List[Dict],
                                     validation_split: float = 0.2) -> Callable:
        """Create fitness function for optimization"""
        # Split data into train/validation
        split_idx = int(len(historical_data) * (1 - validation_split))
        train_data = historical_data[:split_idx]
        val_data = historical_data[split_idx:]

        async def fitness(params: StrategyParameters) -> float:
            """Evaluate strategy parameters"""
            # Run backtest with parameters
            results = await self.backtester.run(train_data, params)

            # Calculate fitness score (Sharpe ratio + other metrics)
            sharpe = results.get('sharpe_ratio', 0)
            returns = results.get('total_return', 0)
            max_dd = results.get('max_drawdown', 0)
            win_rate = results.get('win_rate', 0)

            # Penalize excessive drawdown
            if max_dd > params.max_drawdown:
                drawdown_penalty = (max_dd - params.max_drawdown) * 10
            else:
                drawdown_penalty = 0

            # Composite fitness score
            fitness_score = (
                sharpe * 0.4 +
                returns * 0.3 +
                win_rate * 0.2 +
                (1 - max_dd) * 0.1 -
                drawdown_penalty
            )

            return fitness_score

        return fitness

    async def optimize(self,
                       historical_data: List[Dict],
                       method: str = 'both') -> Dict[str, OptimizationResult]:
        """Run strategy optimization"""
        logger.info(f"Starting strategy optimization with method: {method}")

        # Create fitness function
        fitness_function = await self.create_fitness_function(historical_data)

        results = {}

        # Genetic algorithm optimization
        if method in ['genetic', 'both']:
            logger.info("Running genetic algorithm optimization...")
            genetic_result = await self.genetic_optimizer.optimize(fitness_function)
            results['genetic'] = genetic_result
            logger.info(f"Genetic optimization complete. Best score: {genetic_result.best_score:.4f}")

        # Bayesian optimization
        if method in ['bayesian', 'both']:
            logger.info("Running Bayesian optimization...")
            bayesian_result = await self.bayesian_optimizer.optimize(fitness_function)
            results['bayesian'] = bayesian_result
            logger.info(f"Bayesian optimization complete. Best score: {bayesian_result.best_score:.4f}")

        # Compare and select best
        if method == 'both':
            if results['genetic'].best_score > results['bayesian'].best_score:
                results['best'] = results['genetic']
                results['best_method'] = 'genetic'
            else:
                results['best'] = results['bayesian']
                results['best_method'] = 'bayesian'

        return results

    def save_results(self, results: Dict[str, OptimizationResult], filepath: str):
        """Save optimization results to file"""
        output = {}

        for method, result in results.items():
            if isinstance(result, OptimizationResult):
                output[method] = {
                    'best_score': result.best_score,
                    'parameters': result.best_params.__dict__,
                    'parameter_importance': result.parameter_importance,
                    'robustness_score': result.robustness_score,
                    'overfitting_score': result.overfitting_score,
                    'convergence': result.convergence_plot[-10:],  # Last 10 points
                    'timestamp': result.timestamp.isoformat()
                }

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        logger.info(f"Optimization results saved to {filepath}")


async def test_optimizer():
    """Test strategy optimizer"""
    print("=" * 60)
    print("STRATEGY OPTIMIZATION TEST")
    print("=" * 60)

    # Create mock backtester
    class MockBacktester:
        async def run(self, data, params):
            # Simulate backtest results
            # Better parameters give higher scores
            score = (
                params.min_whale_score * 0.3 +
                params.kelly_fraction * 0.2 +
                (1 - params.max_drawdown) * 0.3 +
                params.min_confidence * 0.2
            )

            return {
                'sharpe_ratio': score + np.random.normal(0, 0.1),
                'total_return': score * 0.5,
                'max_drawdown': 0.15,
                'win_rate': 0.6 + score * 0.1
            }

    # Create optimizer
    backtester = MockBacktester()
    optimizer = StrategyOptimizer(backtester)

    # Generate mock historical data
    historical_data = [{'price': 100 + i, 'volume': 1000} for i in range(100)]

    # Test genetic optimization
    print("\nTesting Genetic Algorithm Optimization...")
    genetic_opt = GeneticOptimizer(
        population_size=20,
        generations=10,
        mutation_rate=0.1
    )

    fitness_func = await optimizer.create_fitness_function(historical_data)
    genetic_result = await genetic_opt.optimize(fitness_func)

    print(f"Best score: {genetic_result.best_score:.4f}")
    print(f"Robustness: {genetic_result.robustness_score:.4f}")
    print("\nTop 3 important parameters:")
    for param, importance in sorted(genetic_result.parameter_importance.items(),
                                   key=lambda x: x[1], reverse=True)[:3]:
        print(f"  {param}: {importance:.3f}")

    # Test Bayesian optimization
    print("\nTesting Bayesian Optimization...")
    bayesian_opt = BayesianOptimizer(
        n_initial_points=10,
        n_iterations=20
    )

    bayesian_result = await bayesian_opt.optimize(fitness_func)

    print(f"Best score: {bayesian_result.best_score:.4f}")
    print(f"Robustness: {bayesian_result.robustness_score:.4f}")
    print(f"Overfitting risk: {bayesian_result.overfitting_score:.3f}")

    print("\n✓ Strategy optimization test complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_optimizer())