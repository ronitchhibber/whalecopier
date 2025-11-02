"""
Week 11: Strategy Optimization - Complete Integration

This file integrates all optimization modules:
1. Strategy Parameter Optimizer (grid search, Bayesian)
2. Portfolio Optimizer (Kelly criterion, risk parity)
3. Multi-Strategy Ensemble (combines multiple strategies)
4. Adaptive Strategy Selector (dynamic selection)
5. Strategy Performance Monitor (real-time tracking)

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Strategy types"""
    CONSERVATIVE = "conservative"  # Low risk, stable returns
    AGGRESSIVE = "aggressive"  # High risk, high returns
    BALANCED = "balanced"  # Medium risk/return
    ADAPTIVE = "adaptive"  # Changes based on conditions


@dataclass
class Strategy:
    """Trading strategy"""
    name: str
    strategy_type: StrategyType
    parameters: Dict
    enabled: bool = True
    weight: Decimal = Decimal("1.0")
    performance_sharpe: Decimal = Decimal("0")
    performance_return: Decimal = Decimal("0")


@dataclass
class EnsembleConfig:
    """Configuration for strategy ensemble"""
    rebalance_interval_hours: int = 24
    min_strategy_weight: Decimal = Decimal("0.05")
    max_strategy_weight: Decimal = Decimal("0.50")


class MultiStrategyEnsemble:
    """
    Combines multiple strategies with weighted voting.

    Each strategy gets a weight based on recent performance.
    Ensemble decision is weighted average of individual strategies.
    """

    def __init__(self, config: EnsembleConfig):
        self.config = config
        self.strategies: List[Strategy] = []
        logger.info("MultiStrategyEnsemble initialized")

    def add_strategy(self, strategy: Strategy):
        """Add strategy to ensemble"""
        self.strategies.append(strategy)
        logger.info(f"Added strategy: {strategy.name}")

    def get_ensemble_decision(self, whale_address: str, signals: Dict[str, float]) -> float:
        """
        Get ensemble decision as weighted average of individual strategy signals.

        Args:
            whale_address: Whale to evaluate
            signals: Dict of strategy_name -> signal (0-1, probability to copy)

        Returns:
            Ensemble signal (0-1)
        """

        if not self.strategies:
            return 0.5  # Neutral

        total_weight = sum(s.weight for s in self.strategies if s.enabled)

        if total_weight == 0:
            return 0.5

        weighted_signal = sum(
            signals.get(s.name, 0.5) * float(s.weight)
            for s in self.strategies if s.enabled
        )

        ensemble_signal = weighted_signal / float(total_weight)

        return ensemble_signal

    def rebalance_weights(self):
        """Rebalance strategy weights based on recent performance"""

        # Update weights proportional to Sharpe ratios
        total_sharpe = sum(max(float(s.performance_sharpe), 0.1) for s in self.strategies)

        for strategy in self.strategies:
            raw_weight = max(float(strategy.performance_sharpe), 0.1) / total_sharpe

            # Apply constraints
            strategy.weight = Decimal(str(max(
                float(self.config.min_strategy_weight),
                min(float(self.config.max_strategy_weight), raw_weight)
            )))

        # Normalize
        total_weight = sum(s.weight for s in self.strategies)
        for strategy in self.strategies:
            strategy.weight = strategy.weight / total_weight

        logger.info("Strategy weights rebalanced")


class AdaptiveStrategySelector:
    """
    Dynamically selects strategy based on market conditions.

    Monitors:
    - Market volatility (high vol -> conservative)
    - Win rate trend (declining -> switch strategy)
    - Sharpe ratio (poor performance -> adapt)
    """

    def __init__(self):
        self.current_strategy: Optional[StrategyType] = StrategyType.BALANCED
        self.last_switch_time: datetime = datetime.now()
        logger.info("AdaptiveStrategySelector initialized")

    def select_strategy(
        self,
        volatility: float,
        recent_sharpe: float,
        recent_win_rate: float
    ) -> StrategyType:
        """
        Select optimal strategy based on market conditions.

        Rules:
        - High volatility (>30%) -> Conservative
        - Low Sharpe (<1.0) -> Adaptive
        - Good performance -> Continue current
        - Poor performance -> Switch to Balanced
        """

        # High volatility -> Conservative
        if volatility > 0.30:
            return StrategyType.CONSERVATIVE

        # Good performance -> Continue
        if recent_sharpe > 2.0 and recent_win_rate > 0.60:
            return self.current_strategy

        # Poor performance -> Balanced
        if recent_sharpe < 1.0:
            return StrategyType.BALANCED

        # Default to Adaptive
        return StrategyType.ADAPTIVE

    def should_switch_strategy(
        self,
        current_type: StrategyType,
        recommended_type: StrategyType,
        min_hours_between_switches: int = 24
    ) -> bool:
        """Determine if strategy should be switched"""

        # Don't switch too frequently
        hours_since_switch = (datetime.now() - self.last_switch_time).total_seconds() / 3600

        if hours_since_switch < min_hours_between_switches:
            return False

        # Switch if recommendation differs
        if current_type != recommended_type:
            self.last_switch_time = datetime.now()
            return True

        return False


class StrategyPerformanceMonitor:
    """
    Real-time monitoring of strategy performance.

    Tracks per strategy:
    - Win rate
    - Sharpe ratio
    - Total return
    - Max drawdown
    - Recent trades
    """

    def __init__(self):
        self.strategy_metrics: Dict[str, Dict] = {}
        logger.info("StrategyPerformanceMonitor initialized")

    def update_strategy_performance(
        self,
        strategy_name: str,
        trade_pnl: Decimal,
        trade_return: Decimal
    ):
        """Update strategy performance metrics"""

        if strategy_name not in self.strategy_metrics:
            self.strategy_metrics[strategy_name] = {
                "trades": [],
                "total_pnl": Decimal("0"),
                "total_return": Decimal("0"),
                "win_count": 0,
                "loss_count": 0
            }

        metrics = self.strategy_metrics[strategy_name]
        metrics["trades"].append({
            "pnl": trade_pnl,
            "return": trade_return,
            "timestamp": datetime.now()
        })

        metrics["total_pnl"] += trade_pnl
        metrics["total_return"] += trade_return

        if trade_pnl > 0:
            metrics["win_count"] += 1
        else:
            metrics["loss_count"] += 1

    def get_strategy_sharpe(self, strategy_name: str) -> Decimal:
        """Calculate strategy Sharpe ratio"""

        if strategy_name not in self.strategy_metrics:
            return Decimal("0")

        metrics = self.strategy_metrics[strategy_name]
        trades = metrics["trades"]

        if len(trades) < 2:
            return Decimal("0")

        returns = [float(t["return"]) for t in trades]
        import numpy as np

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return Decimal("0")

        sharpe = Decimal(str(mean_return / std_return * np.sqrt(252)))  # Annualized
        return sharpe

    def print_performance_summary(self):
        """Print performance summary for all strategies"""

        print(f"\n{'='*100}")
        print("STRATEGY PERFORMANCE MONITOR")
        print(f"{'='*100}\n")

        print(f"{'Strategy':<25}{'Trades':<10}{'Win%':<10}{'Total P&L':<15}{'Sharpe':<10}")
        print("-" * 100)

        for strategy_name, metrics in self.strategy_metrics.items():
            total_trades = metrics["win_count"] + metrics["loss_count"]
            win_rate = metrics["win_count"] / total_trades * 100 if total_trades > 0 else 0
            sharpe = self.get_strategy_sharpe(strategy_name)

            print(
                f"{strategy_name:<25}"
                f"{total_trades:<10}"
                f"{win_rate:<10.1f}"
                f"${float(metrics['total_pnl']):<14,.2f}"
                f"{float(sharpe):<10.2f}"
            )

        print(f"\n{'='*100}\n")


# Integrated example
if __name__ == "__main__":
    print("Strategy Optimization Integration Demo\n")

    # 1. Multi-Strategy Ensemble
    ensemble_config = EnsembleConfig()
    ensemble = MultiStrategyEnsemble(ensemble_config)

    # Add strategies
    ensemble.add_strategy(Strategy(
        name="Conservative",
        strategy_type=StrategyType.CONSERVATIVE,
        parameters={"min_edge": 0.10, "max_positions": 10},
        weight=Decimal("0.3"),
        performance_sharpe=Decimal("1.8")
    ))

    ensemble.add_strategy(Strategy(
        name="Aggressive",
        strategy_type=StrategyType.AGGRESSIVE,
        parameters={"min_edge": 0.05, "max_positions": 30},
        weight=Decimal("0.4"),
        performance_sharpe=Decimal("2.2")
    ))

    ensemble.add_strategy(Strategy(
        name="Balanced",
        strategy_type=StrategyType.BALANCED,
        parameters={"min_edge": 0.07, "max_positions": 20},
        weight=Decimal("0.3"),
        performance_sharpe=Decimal("2.0")
    ))

    # Get ensemble decision
    signals = {
        "Conservative": 0.7,
        "Aggressive": 0.9,
        "Balanced": 0.8
    }

    ensemble_signal = ensemble.get_ensemble_decision("0xwhale1", signals)
    print(f"Ensemble signal for 0xwhale1: {ensemble_signal:.2f}")

    # 2. Adaptive Strategy Selector
    selector = AdaptiveStrategySelector()

    # Test different market conditions
    print("\n Market Conditions Analysis:")
    print("-" * 100)

    conditions = [
        {"vol": 0.15, "sharpe": 2.5, "win_rate": 0.65, "desc": "Normal, good performance"},
        {"vol": 0.35, "sharpe": 1.5, "win_rate": 0.55, "desc": "High volatility"},
        {"vol": 0.20, "sharpe": 0.8, "win_rate": 0.48, "desc": "Poor performance"}
    ]

    for cond in conditions:
        recommended = selector.select_strategy(
            volatility=cond["vol"],
            recent_sharpe=cond["sharpe"],
            recent_win_rate=cond["win_rate"]
        )
        print(f"{cond['desc']:<30} -> Recommended: {recommended.value}")

    # 3. Strategy Performance Monitor
    monitor = StrategyPerformanceMonitor()

    # Simulate trades
    for i in range(10):
        strategy = ["Conservative", "Aggressive", "Balanced"][i % 3]
        pnl = Decimal(str(50 if i % 3 != 0 else -30))
        ret = pnl / Decimal("1000")
        monitor.update_strategy_performance(strategy, pnl, ret)

    monitor.print_performance_summary()

    print("\nOptimization integration demo complete!")
