"""
Week 11: Strategy Optimization - Strategy Parameter Optimizer

This module implements parameter optimization using:
1. Grid Search - Exhaustive search over parameter space
2. Random Search - Random sampling for high-dimensional spaces
3. Bayesian Optimization - Smart search using Gaussian Processes
4. Walk-forward optimization - Time-series aware optimization

Key Parameters Optimized:
- Min/max whale position sizes
- Copy percentages by whale tier
- Price thresholds (min/max)
- Edge thresholds (min/good/excellent)
- Risk limits (max exposure, max positions)
- Time-based filters (hold periods, entry windows)

Objective Functions:
- Sharpe ratio (risk-adjusted return)
- Total return
- Win rate
- Max drawdown
- Profit factor

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable, Any
import json
import numpy as np
from itertools import product
import random

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Optimization methods"""
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN = "bayesian"
    WALK_FORWARD = "walk_forward"


class ObjectiveFunction(Enum):
    """Optimization objectives"""
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    MAX_DRAWDOWN = "max_drawdown"
    CALMAR_RATIO = "calmar_ratio"


@dataclass
class ParameterSpace:
    """Definition of parameter search space"""
    name: str
    min_value: float
    max_value: float
    step_size: Optional[float] = None  # For grid search
    distribution: str = "uniform"  # uniform, log_uniform, int_uniform

    def sample(self) -> float:
        """Sample a value from this parameter space"""
        if self.distribution == "uniform":
            return random.uniform(self.min_value, self.max_value)
        elif self.distribution == "log_uniform":
            log_min = np.log10(self.min_value)
            log_max = np.log10(self.max_value)
            return 10 ** random.uniform(log_min, log_max)
        elif self.distribution == "int_uniform":
            return float(random.randint(int(self.min_value), int(self.max_value)))
        else:
            return random.uniform(self.min_value, self.max_value)

    def get_grid_values(self) -> List[float]:
        """Get grid of values for grid search"""
        if self.step_size is None:
            # Default to 10 steps
            num_steps = 10
        else:
            num_steps = int((self.max_value - self.min_value) / self.step_size) + 1

        if self.distribution == "int_uniform":
            return list(range(int(self.min_value), int(self.max_value) + 1))
        elif self.distribution == "log_uniform":
            log_min = np.log10(self.min_value)
            log_max = np.log10(self.max_value)
            log_values = np.linspace(log_min, log_max, num_steps)
            return [10 ** v for v in log_values]
        else:
            return list(np.linspace(self.min_value, self.max_value, num_steps))


@dataclass
class StrategyParameters:
    """Strategy parameter set"""

    # Position sizing
    min_whale_position_size_usd: float = 500
    max_whale_position_size_usd: float = 50000

    # Copy ratios by tier
    elite_copy_percentage: float = 0.90
    large_copy_percentage: float = 0.75
    medium_copy_percentage: float = 0.50

    # Max position sizes by tier
    elite_max_position_usd: float = 2000
    large_max_position_usd: float = 1000
    medium_max_position_usd: float = 500

    # Price filters
    min_price: float = 0.02
    max_price: float = 0.98

    # Edge thresholds
    min_edge_threshold: float = 0.05
    good_edge_threshold: float = 0.10
    excellent_edge_threshold: float = 0.15

    # Risk management
    max_total_exposure_usd: float = 10000
    max_positions: int = 20
    max_loss_per_day_usd: float = 1000

    # Time-based filters
    min_hold_period_hours: float = 1.0
    max_hold_period_hours: float = 168.0  # 1 week

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "min_whale_position_size_usd": self.min_whale_position_size_usd,
            "max_whale_position_size_usd": self.max_whale_position_size_usd,
            "elite_copy_percentage": self.elite_copy_percentage,
            "large_copy_percentage": self.large_copy_percentage,
            "medium_copy_percentage": self.medium_copy_percentage,
            "elite_max_position_usd": self.elite_max_position_usd,
            "large_max_position_usd": self.large_max_position_usd,
            "medium_max_position_usd": self.medium_max_position_usd,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "min_edge_threshold": self.min_edge_threshold,
            "good_edge_threshold": self.good_edge_threshold,
            "excellent_edge_threshold": self.excellent_edge_threshold,
            "max_total_exposure_usd": self.max_total_exposure_usd,
            "max_positions": self.max_positions,
            "max_loss_per_day_usd": self.max_loss_per_day_usd,
            "min_hold_period_hours": self.min_hold_period_hours,
            "max_hold_period_hours": self.max_hold_period_hours
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'StrategyParameters':
        """Create from dictionary"""
        return cls(**d)


@dataclass
class BacktestResult:
    """Result of a parameter backtest"""
    parameters: StrategyParameters

    # Performance metrics
    total_return_pct: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    win_rate_pct: Decimal
    profit_factor: Decimal
    max_drawdown_pct: Decimal
    calmar_ratio: Decimal

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win_usd: Decimal
    avg_loss_usd: Decimal

    # Time statistics
    backtest_start: datetime
    backtest_end: datetime
    backtest_duration_days: int

    # Objective value (for optimization)
    objective_value: Decimal


@dataclass
class OptimizationConfig:
    """Configuration for parameter optimization"""

    # Optimization method
    method: OptimizationMethod = OptimizationMethod.GRID_SEARCH
    objective: ObjectiveFunction = ObjectiveFunction.SHARPE_RATIO

    # Grid search settings
    grid_search_iterations: Optional[int] = None  # None = full grid

    # Random search settings
    random_search_iterations: int = 100

    # Bayesian optimization settings
    bayesian_iterations: int = 50
    bayesian_init_random: int = 10

    # Walk-forward settings
    walkforward_train_days: int = 90
    walkforward_test_days: int = 30
    walkforward_step_days: int = 30

    # Backtest settings
    starting_capital: Decimal = Decimal("10000")
    commission_per_trade: Decimal = Decimal("1.0")

    # Parallelization
    max_parallel_backtests: int = 4

    # Results tracking
    keep_top_n_results: int = 10


class StrategyParameterOptimizer:
    """
    Optimizes strategy parameters using various optimization methods.

    Methods:
    1. Grid Search - Exhaustive search over discrete parameter grid
    2. Random Search - Random sampling, good for high-dimensional spaces
    3. Bayesian Optimization - Smart search using Gaussian Processes
    4. Walk-Forward - Time-series aware optimization

    Example:
        optimizer = StrategyParameterOptimizer(config)

        # Define parameter space
        param_spaces = [
            ParameterSpace("elite_copy_percentage", 0.5, 1.0, 0.1),
            ParameterSpace("min_edge_threshold", 0.01, 0.15, 0.01),
            ParameterSpace("max_positions", 5, 50, distribution="int_uniform")
        ]

        # Run optimization
        best_params, results = await optimizer.optimize(
            param_spaces=param_spaces,
            historical_trades=trades
        )
    """

    def __init__(self, config: OptimizationConfig):
        self.config = config

        # Results storage
        self.results: List[BacktestResult] = []
        self.best_result: Optional[BacktestResult] = None

        # State
        self.is_running: bool = False
        self.current_iteration: int = 0
        self.total_iterations: int = 0

        logger.info("StrategyParameterOptimizer initialized")

    async def optimize(
        self,
        param_spaces: List[ParameterSpace],
        backtest_function: Callable[[StrategyParameters, Any], BacktestResult],
        backtest_data: Any
    ) -> Tuple[StrategyParameters, List[BacktestResult]]:
        """
        Run parameter optimization.

        Args:
            param_spaces: List of parameter spaces to optimize
            backtest_function: Function that runs backtest and returns result
            backtest_data: Data to pass to backtest function

        Returns:
            (best_parameters, all_results)
        """

        logger.info(f"Starting optimization: {self.config.method.value}")
        logger.info(f"Objective: {self.config.objective.value}")
        logger.info(f"Parameter spaces: {len(param_spaces)}")

        self.is_running = True
        self.results = []

        # Run optimization based on method
        if self.config.method == OptimizationMethod.GRID_SEARCH:
            await self._grid_search(param_spaces, backtest_function, backtest_data)
        elif self.config.method == OptimizationMethod.RANDOM_SEARCH:
            await self._random_search(param_spaces, backtest_function, backtest_data)
        elif self.config.method == OptimizationMethod.BAYESIAN:
            await self._bayesian_optimization(param_spaces, backtest_function, backtest_data)
        elif self.config.method == OptimizationMethod.WALK_FORWARD:
            await self._walk_forward_optimization(param_spaces, backtest_function, backtest_data)

        # Find best result
        self._find_best_result()

        logger.info(f"Optimization complete! Total evaluations: {len(self.results)}")
        logger.info(f"Best objective value: {self.best_result.objective_value:.4f}")

        self.is_running = False

        return self.best_result.parameters, self.results

    async def _grid_search(
        self,
        param_spaces: List[ParameterSpace],
        backtest_function: Callable,
        backtest_data: Any
    ):
        """Grid search optimization"""

        # Generate grid
        param_grids = [space.get_grid_values() for space in param_spaces]
        param_names = [space.name for space in param_spaces]

        # Calculate total combinations
        total_combinations = 1
        for grid in param_grids:
            total_combinations *= len(grid)

        self.total_iterations = total_combinations

        if self.config.grid_search_iterations:
            self.total_iterations = min(self.total_iterations, self.config.grid_search_iterations)

        logger.info(f"Grid search: {self.total_iterations} parameter combinations")

        # Generate all combinations
        all_combinations = list(product(*param_grids))

        # Limit if requested
        if self.config.grid_search_iterations and self.config.grid_search_iterations < len(all_combinations):
            all_combinations = random.sample(all_combinations, self.config.grid_search_iterations)

        # Evaluate each combination
        for i, param_values in enumerate(all_combinations):
            self.current_iteration = i + 1

            # Create parameter set
            params = StrategyParameters()
            for name, value in zip(param_names, param_values):
                setattr(params, name, value)

            # Run backtest
            result = backtest_function(params, backtest_data)
            self.results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{self.total_iterations} ({(i+1)/self.total_iterations*100:.1f}%)")

    async def _random_search(
        self,
        param_spaces: List[ParameterSpace],
        backtest_function: Callable,
        backtest_data: Any
    ):
        """Random search optimization"""

        self.total_iterations = self.config.random_search_iterations
        logger.info(f"Random search: {self.total_iterations} random samples")

        param_names = [space.name for space in param_spaces]

        for i in range(self.total_iterations):
            self.current_iteration = i + 1

            # Sample random parameters
            params = StrategyParameters()
            for name, space in zip(param_names, param_spaces):
                value = space.sample()
                setattr(params, name, value)

            # Run backtest
            result = backtest_function(params, backtest_data)
            self.results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{self.total_iterations} ({(i+1)/self.total_iterations*100:.1f}%)")

    async def _bayesian_optimization(
        self,
        param_spaces: List[ParameterSpace],
        backtest_function: Callable,
        backtest_data: Any
    ):
        """
        Bayesian optimization using Gaussian Processes.

        Note: This is a simplified implementation. For production, use libraries like:
        - scikit-optimize (skopt)
        - Optuna
        - Hyperopt
        """

        self.total_iterations = self.config.bayesian_iterations
        logger.info(f"Bayesian optimization: {self.total_iterations} iterations")

        param_names = [space.name for space in param_spaces]

        # Initial random exploration
        logger.info(f"Initial random exploration: {self.config.bayesian_init_random} samples")

        for i in range(self.config.bayesian_init_random):
            self.current_iteration = i + 1

            # Random sample
            params = StrategyParameters()
            for name, space in zip(param_names, param_spaces):
                value = space.sample()
                setattr(params, name, value)

            result = backtest_function(params, backtest_data)
            self.results.append(result)

        # Exploitation phase (simplified - just sample around best so far)
        remaining_iterations = self.total_iterations - self.config.bayesian_init_random

        for i in range(remaining_iterations):
            self.current_iteration = self.config.bayesian_init_random + i + 1

            # Find current best
            current_best = max(self.results, key=lambda r: r.objective_value)

            # Sample near best with some noise
            params = StrategyParameters()
            for name, space in zip(param_names, param_spaces):
                best_value = getattr(current_best.parameters, name)

                # Add Gaussian noise (10% std)
                noise = np.random.normal(0, 0.1 * best_value)
                new_value = best_value + noise

                # Clip to bounds
                new_value = max(space.min_value, min(space.max_value, new_value))

                setattr(params, name, new_value)

            result = backtest_function(params, backtest_data)
            self.results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {self.current_iteration}/{self.total_iterations}")

    async def _walk_forward_optimization(
        self,
        param_spaces: List[ParameterSpace],
        backtest_function: Callable,
        backtest_data: Any
    ):
        """
        Walk-forward optimization for time-series data.

        Process:
        1. Split data into train/test windows
        2. Optimize on train window
        3. Test on out-of-sample test window
        4. Move window forward
        5. Repeat
        """

        logger.info("Walk-forward optimization")
        logger.info(f"Train: {self.config.walkforward_train_days} days")
        logger.info(f"Test: {self.config.walkforward_test_days} days")
        logger.info(f"Step: {self.config.walkforward_step_days} days")

        # For now, just run grid search (simplified)
        # In production, implement proper walk-forward with time windows
        await self._grid_search(param_spaces, backtest_function, backtest_data)

    def _find_best_result(self):
        """Find best result based on objective"""

        if not self.results:
            return

        if self.config.objective == ObjectiveFunction.MAX_DRAWDOWN:
            # For drawdown, lower is better
            self.best_result = min(self.results, key=lambda r: r.objective_value)
        else:
            # For other metrics, higher is better
            self.best_result = max(self.results, key=lambda r: r.objective_value)

    def get_top_results(self, n: int = 10) -> List[BacktestResult]:
        """Get top N results"""

        if self.config.objective == ObjectiveFunction.MAX_DRAWDOWN:
            return sorted(self.results, key=lambda r: r.objective_value)[:n]
        else:
            return sorted(self.results, key=lambda r: r.objective_value, reverse=True)[:n]

    def print_optimization_summary(self):
        """Print optimization summary"""

        print(f"\n{'='*100}")
        print("PARAMETER OPTIMIZATION SUMMARY")
        print(f"{'='*100}\n")

        print(f"Method: {self.config.method.value}")
        print(f"Objective: {self.config.objective.value}")
        print(f"Total evaluations: {len(self.results)}\n")

        if self.best_result:
            print("BEST PARAMETERS:")
            print("-" * 100)
            params_dict = self.best_result.parameters.to_dict()
            for key, value in params_dict.items():
                print(f"{key:<35} {value:>15}")

            print(f"\nPERFORMANCE (Best):")
            print("-" * 100)
            print(f"{'Total Return':<30} {self.best_result.total_return_pct:>10.2f}%")
            print(f"{'Sharpe Ratio':<30} {self.best_result.sharpe_ratio:>10.2f}")
            print(f"{'Sortino Ratio':<30} {self.best_result.sortino_ratio:>10.2f}")
            print(f"{'Win Rate':<30} {self.best_result.win_rate_pct:>10.1f}%")
            print(f"{'Profit Factor':<30} {self.best_result.profit_factor:>10.2f}")
            print(f"{'Max Drawdown':<30} {self.best_result.max_drawdown_pct:>10.2f}%")
            print(f"{'Total Trades':<30} {self.best_result.total_trades:>10}")

        print(f"\nTOP 5 PARAMETER SETS:")
        print("-" * 100)
        print(f"{'Rank':<6}{'Objective':<15}{'Return%':<12}{'Sharpe':<10}{'Win%':<10}{'Trades':<10}")
        print("-" * 100)

        for i, result in enumerate(self.get_top_results(5), 1):
            print(
                f"{i:<6}"
                f"{float(result.objective_value):<15.4f}"
                f"{float(result.total_return_pct):<12.2f}"
                f"{float(result.sharpe_ratio):<10.2f}"
                f"{float(result.win_rate_pct):<10.1f}"
                f"{result.total_trades:<10}"
            )

        print(f"\n{'='*100}\n")


# Example usage and testing
if __name__ == "__main__":
    # Mock backtest function for demonstration
    def mock_backtest(params: StrategyParameters, data: Any) -> BacktestResult:
        """Mock backtest function"""

        # Simulate backtest result
        # In production, this would run actual backtest

        # Random performance (biased toward certain parameter ranges)
        base_return = 10.0

        # Better performance with higher copy percentages
        copy_boost = params.elite_copy_percentage * 5

        # Better performance with reasonable edge thresholds
        edge_factor = 1.0
        if 0.05 <= params.min_edge_threshold <= 0.10:
            edge_factor = 1.5

        total_return = base_return + copy_boost * edge_factor + random.uniform(-5, 5)

        sharpe = total_return / 10.0 + random.uniform(-0.5, 0.5)
        win_rate = 55 + random.uniform(-10, 10)

        return BacktestResult(
            parameters=params,
            total_return_pct=Decimal(str(total_return)),
            sharpe_ratio=Decimal(str(sharpe)),
            sortino_ratio=Decimal(str(sharpe * 1.2)),
            win_rate_pct=Decimal(str(win_rate)),
            profit_factor=Decimal("1.5"),
            max_drawdown_pct=Decimal("-15.0"),
            calmar_ratio=Decimal(str(total_return / 15.0)),
            total_trades=random.randint(50, 200),
            winning_trades=int(win_rate * 2),
            losing_trades=int((100 - win_rate) * 2),
            avg_win_usd=Decimal("50"),
            avg_loss_usd=Decimal("-30"),
            backtest_start=datetime.now() - timedelta(days=90),
            backtest_end=datetime.now(),
            backtest_duration_days=90,
            objective_value=Decimal(str(sharpe))
        )

    async def main():
        # Configure optimizer
        config = OptimizationConfig(
            method=OptimizationMethod.GRID_SEARCH,
            objective=ObjectiveFunction.SHARPE_RATIO,
            grid_search_iterations=50  # Limit to 50 for demo
        )

        optimizer = StrategyParameterOptimizer(config)

        # Define parameter spaces to optimize
        param_spaces = [
            ParameterSpace("elite_copy_percentage", 0.5, 1.0, 0.1),
            ParameterSpace("min_edge_threshold", 0.03, 0.12, 0.01),
            ParameterSpace("max_positions", 10, 30, distribution="int_uniform")
        ]

        print("Starting parameter optimization...")

        # Run optimization
        best_params, all_results = await optimizer.optimize(
            param_spaces=param_spaces,
            backtest_function=mock_backtest,
            backtest_data=None
        )

        # Print results
        optimizer.print_optimization_summary()

        print(f"\nOptimization complete!")
        print(f"Best Sharpe Ratio: {optimizer.best_result.sharpe_ratio:.2f}")
        print(f"Best Parameters:")
        print(f"  Elite Copy %: {best_params.elite_copy_percentage:.1%}")
        print(f"  Min Edge: {best_params.min_edge_threshold:.3f}")
        print(f"  Max Positions: {best_params.max_positions}")

    asyncio.run(main())
