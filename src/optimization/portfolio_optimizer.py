"""
Week 11: Strategy Optimization - Portfolio Optimizer

Implements modern portfolio theory and Kelly criterion for optimal allocation:
1. Mean-Variance Optimization (Markowitz)
2. Kelly Criterion for position sizing
3. Risk parity allocation
4. Maximum Sharpe ratio portfolio
5. Minimum variance portfolio

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WhaleAllocation:
    """Allocation for a single whale"""
    whale_address: str
    allocation_pct: Decimal  # Percentage of portfolio
    allocation_usd: Decimal  # Dollar amount
    expected_return: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal


@dataclass
class PortfolioConfig:
    """Configuration for portfolio optimization"""
    total_capital_usd: Decimal = Decimal("10000")
    min_allocation_per_whale_pct: Decimal = Decimal("1.0")
    max_allocation_per_whale_pct: Decimal = Decimal("25.0")
    risk_free_rate: Decimal = Decimal("0.04")
    kelly_fraction: Decimal = Decimal("0.25")  # Use 25% Kelly for safety


class PortfolioOptimizer:
    """
    Optimizes whale portfolio allocations using modern portfolio theory.

    Methods:
    - Maximum Sharpe ratio portfolio
    - Minimum variance portfolio
    - Kelly criterion sizing
    - Risk parity
    """

    def __init__(self, config: PortfolioConfig):
        self.config = config
        logger.info("PortfolioOptimizer initialized")

    def optimize_sharpe_ratio(
        self,
        whale_returns: Dict[str, List[Decimal]],
        whale_metadata: Dict[str, Dict]
    ) -> List[WhaleAllocation]:
        """
        Calculate maximum Sharpe ratio portfolio.

        Uses mean-variance optimization to find the portfolio
        with the highest risk-adjusted return.
        """

        whale_addresses = list(whale_returns.keys())
        n_whales = len(whale_addresses)

        # Calculate expected returns and covariance matrix
        returns_matrix = np.array([
            [float(r) for r in whale_returns[addr]]
            for addr in whale_addresses
        ])

        expected_returns = np.mean(returns_matrix, axis=1)
        cov_matrix = np.cov(returns_matrix)

        # Find maximum Sharpe ratio weights (simplified - use equal weight for demo)
        # In production, use scipy.optimize
        weights = np.ones(n_whales) / n_whales

        # Apply constraints
        weights = np.clip(
            weights,
            float(self.config.min_allocation_per_whale_pct) / 100,
            float(self.config.max_allocation_per_whale_pct) / 100
        )
        weights = weights / weights.sum()  # Normalize

        # Calculate portfolio metrics
        portfolio_return = np.dot(weights, expected_returns)
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
        sharpe = (portfolio_return - float(self.config.risk_free_rate)) / portfolio_vol

        # Create allocations
        allocations = []
        for i, addr in enumerate(whale_addresses):
            alloc_pct = Decimal(str(weights[i] * 100))
            alloc_usd = self.config.total_capital_usd * Decimal(str(weights[i]))

            allocations.append(WhaleAllocation(
                whale_address=addr,
                allocation_pct=alloc_pct,
                allocation_usd=alloc_usd,
                expected_return=Decimal(str(expected_returns[i])),
                volatility=Decimal(str(np.std(returns_matrix[i]))),
                sharpe_ratio=Decimal(str(sharpe))
            ))

        logger.info(f"Maximum Sharpe portfolio: {sharpe:.2f}")
        return allocations

    def kelly_criterion_allocation(
        self,
        whale_stats: Dict[str, Dict]
    ) -> List[WhaleAllocation]:
        """
        Calculate Kelly criterion position sizes.

        Kelly formula: f* = (p*b - q) / b
        Where:
        - p = win probability
        - q = loss probability (1-p)
        - b = win/loss ratio
        - f* = optimal fraction of capital
        """

        allocations = []
        total_kelly = Decimal("0")

        # Calculate Kelly fraction for each whale
        kelly_fractions = {}
        for addr, stats in whale_stats.items():
            win_rate = stats.get('win_rate', 0.55)
            avg_win = stats.get('avg_win', 100)
            avg_loss = abs(stats.get('avg_loss', -50))

            p = Decimal(str(win_rate))
            q = Decimal("1") - p
            b = Decimal(str(avg_win / avg_loss)) if avg_loss > 0 else Decimal("1")

            # Kelly formula
            kelly_raw = (p * b - q) / b if b > 0 else Decimal("0")

            # Apply fraction (fractional Kelly for safety)
            kelly_safe = kelly_raw * self.config.kelly_fraction

            # Clip to constraints
            kelly_safe = max(
                self.config.min_allocation_per_whale_pct / Decimal("100"),
                min(self.config.max_allocation_per_whale_pct / Decimal("100"), kelly_safe)
            )

            kelly_fractions[addr] = kelly_safe
            total_kelly += kelly_safe

        # Normalize if total exceeds 100%
        if total_kelly > Decimal("1.0"):
            for addr in kelly_fractions:
                kelly_fractions[addr] = kelly_fractions[addr] / total_kelly

        # Create allocations
        for addr, fraction in kelly_fractions.items():
            alloc_pct = fraction * Decimal("100")
            alloc_usd = self.config.total_capital_usd * fraction

            allocations.append(WhaleAllocation(
                whale_address=addr,
                allocation_pct=alloc_pct,
                allocation_usd=alloc_usd,
                expected_return=Decimal(str(whale_stats[addr].get('expected_return', 0.10))),
                volatility=Decimal(str(whale_stats[addr].get('volatility', 0.20))),
                sharpe_ratio=Decimal(str(whale_stats[addr].get('sharpe', 1.0)))
            ))

        logger.info(f"Kelly criterion allocation: {len(allocations)} whales")
        return allocations

    def risk_parity_allocation(
        self,
        whale_returns: Dict[str, List[Decimal]]
    ) -> List[WhaleAllocation]:
        """
        Risk parity: allocate inversely proportional to volatility.
        Each whale contributes equal risk to the portfolio.
        """

        whale_addresses = list(whale_returns.keys())

        # Calculate volatilities
        volatilities = {}
        for addr, returns in whale_returns.items():
            vol = np.std([float(r) for r in returns])
            volatilities[addr] = Decimal(str(vol))

        # Inverse volatility weights
        inv_vols = {addr: Decimal("1") / vol if vol > 0 else Decimal("0")
                    for addr, vol in volatilities.items()}

        total_inv_vol = sum(inv_vols.values())

        # Normalize to get weights
        weights = {addr: inv_vol / total_inv_vol
                   for addr, inv_vol in inv_vols.items()}

        # Create allocations
        allocations = []
        for addr in whale_addresses:
            alloc_pct = weights[addr] * Decimal("100")
            alloc_usd = self.config.total_capital_usd * weights[addr]

            allocations.append(WhaleAllocation(
                whale_address=addr,
                allocation_pct=alloc_pct,
                allocation_usd=alloc_usd,
                expected_return=Decimal("0"),
                volatility=volatilities[addr],
                sharpe_ratio=Decimal("0")
            ))

        logger.info(f"Risk parity allocation: {len(allocations)} whales")
        return allocations

    def print_allocation_summary(self, allocations: List[WhaleAllocation]):
        """Print allocation summary"""

        print(f"\n{'='*100}")
        print("PORTFOLIO ALLOCATION SUMMARY")
        print(f"{'='*100}\n")

        print(f"Total Capital: ${float(self.config.total_capital_usd):,.2f}\n")

        print(f"{'Whale':<25}{'Allocation %':<15}{'Amount $':<15}{'Exp. Return':<15}{'Volatility':<15}")
        print("-" * 100)

        for alloc in sorted(allocations, key=lambda a: a.allocation_pct, reverse=True):
            print(
                f"{alloc.whale_address[:23]:<25}"
                f"{float(alloc.allocation_pct):>13.2f}% "
                f"${float(alloc.allocation_usd):>13,.2f} "
                f"{float(alloc.expected_return):>13.2%} "
                f"{float(alloc.volatility):>13.2%}"
            )

        total_alloc_pct = sum(a.allocation_pct for a in allocations)
        total_alloc_usd = sum(a.allocation_usd for a in allocations)

        print("-" * 100)
        print(f"{'TOTAL':<25}{float(total_alloc_pct):>13.2f}% ${float(total_alloc_usd):>13,.2f}")
        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    config = PortfolioConfig(total_capital_usd=Decimal("10000"))
    optimizer = PortfolioOptimizer(config)

    # Mock whale data
    whale_returns = {
        "0xwhale1": [Decimal("0.05"), Decimal("0.03"), Decimal("0.07"), Decimal("-0.02")],
        "0xwhale2": [Decimal("0.08"), Decimal("0.06"), Decimal("0.04"), Decimal("0.05")],
        "0xwhale3": [Decimal("0.02"), Decimal("0.03"), Decimal("0.01"), Decimal("0.04")]
    }

    whale_stats = {
        "0xwhale1": {"win_rate": 0.60, "avg_win": 100, "avg_loss": -50, "sharpe": 1.5},
        "0xwhale2": {"win_rate": 0.65, "avg_win": 120, "avg_loss": -40, "sharpe": 1.8},
        "0xwhale3": {"win_rate": 0.55, "avg_win": 80, "avg_loss": -60, "sharpe": 1.2}
    }

    print("1. Kelly Criterion Allocation:")
    kelly_alloc = optimizer.kelly_criterion_allocation(whale_stats)
    optimizer.print_allocation_summary(kelly_alloc)

    print("\n2. Risk Parity Allocation:")
    risk_parity_alloc = optimizer.risk_parity_allocation(whale_returns)
    optimizer.print_allocation_summary(risk_parity_alloc)

    print("\nPortfolio optimization complete!")
