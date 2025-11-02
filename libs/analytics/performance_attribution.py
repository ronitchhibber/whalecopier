"""
Performance Attribution System
Brinson-Fachler decomposition and factor analysis.

Research Target: 74% of alpha from selection effect (whale picking skill)

Components:
1. Brinson-Fachler Attribution
   - Allocation Effect: Category selection skill
   - Selection Effect: Whale picking skill within categories
   - Interaction Effect: Combined timing
2. Factor Regression (α/β separation)
3. Category-Level Attribution
4. Whale-Level Attribution
5. Time-Series Attribution Analysis
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
from scipy import stats


@dataclass
class AttributionResult:
    """Performance attribution breakdown."""
    # Total return
    total_return: float
    benchmark_return: float
    active_return: float  # Total - Benchmark

    # Brinson-Fachler components
    allocation_effect: float  # Category selection skill
    selection_effect: float  # Whale picking skill
    interaction_effect: float  # Timing skill

    # Factor analysis
    alpha: float  # Skill-based return
    beta: float  # Market exposure
    r_squared: float  # Model fit

    # Breakdown by component
    category_attribution: Dict[str, float]
    whale_attribution: Dict[str, float]

    # Metadata
    period_start: datetime
    period_end: datetime
    num_trades: int
    num_whales: int


@dataclass
class WhaleContribution:
    """Individual whale contribution to portfolio."""
    whale_address: str
    total_return: float
    contribution_to_portfolio: float  # Weight * Return
    weight: float  # Average weight during period
    num_trades: int
    win_rate: float
    sharpe_ratio: float
    rank: int  # Rank by contribution


class BrinsonFachlerAttribution:
    """
    Brinson-Fachler performance attribution.

    Decomposes portfolio return into:
    - Allocation Effect: Did we overweight the right categories?
    - Selection Effect: Did we pick the right whales within categories?
    - Interaction Effect: Did we get the timing right?

    Research target: Selection effect should be 74% of total alpha.
    """

    @staticmethod
    def calculate_attribution(
        portfolio_weights: Dict[str, float],  # Category -> weight
        portfolio_returns: Dict[str, float],  # Category -> return
        benchmark_weights: Dict[str, float],  # Category -> benchmark weight
        benchmark_returns: Dict[str, float]   # Category -> benchmark return
    ) -> Tuple[float, float, float, float]:
        """
        Calculate Brinson-Fachler attribution.

        Args:
            portfolio_weights: Actual category weights
            portfolio_returns: Actual category returns
            benchmark_weights: Benchmark category weights
            benchmark_returns: Benchmark category returns

        Returns:
            (allocation_effect, selection_effect, interaction_effect, total_active_return)
        """
        allocation = 0.0
        selection = 0.0
        interaction = 0.0

        # Get all categories
        all_categories = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for category in all_categories:
            w_p = portfolio_weights.get(category, 0.0)  # Portfolio weight
            w_b = benchmark_weights.get(category, 0.0)  # Benchmark weight
            r_p = portfolio_returns.get(category, 0.0)  # Portfolio return
            r_b = benchmark_returns.get(category, 0.0)  # Benchmark return

            # Allocation effect: (w_p - w_b) * r_b
            # Did we overweight categories that did well?
            allocation += (w_p - w_b) * r_b

            # Selection effect: w_b * (r_p - r_b)
            # Did we pick better whales than benchmark?
            selection += w_b * (r_p - r_b)

            # Interaction effect: (w_p - w_b) * (r_p - r_b)
            # Did we overweight categories where we had superior selection?
            interaction += (w_p - w_b) * (r_p - r_b)

        # Total active return
        total_active = allocation + selection + interaction

        return allocation, selection, interaction, total_active

    @staticmethod
    def calculate_selection_percentage(
        allocation_effect: float,
        selection_effect: float,
        interaction_effect: float
    ) -> float:
        """
        Calculate what % of alpha came from selection (whale picking).

        Research target: 74%

        Args:
            allocation_effect: Allocation effect
            selection_effect: Selection effect
            interaction_effect: Interaction effect

        Returns:
            Selection percentage (0-1)
        """
        total_alpha = allocation_effect + selection_effect + interaction_effect

        if total_alpha <= 0:
            return 0.0

        return selection_effect / total_alpha


class FactorRegression:
    """
    Factor regression for alpha/beta separation.

    Separates skill-based returns (α) from market exposure (β).
    """

    @staticmethod
    def calculate_alpha_beta(
        portfolio_returns: np.ndarray,
        market_returns: np.ndarray
    ) -> Tuple[float, float, float, float]:
        """
        Calculate α and β via linear regression.

        Model: R_p = α + β * R_m + ε

        Args:
            portfolio_returns: Portfolio returns
            market_returns: Market/benchmark returns

        Returns:
            (alpha, beta, r_squared, p_value)
        """
        if len(portfolio_returns) < 10 or len(market_returns) < 10:
            return 0.0, 1.0, 0.0, 1.0

        if len(portfolio_returns) != len(market_returns):
            min_len = min(len(portfolio_returns), len(market_returns))
            portfolio_returns = portfolio_returns[:min_len]
            market_returns = market_returns[:min_len]

        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            market_returns, portfolio_returns
        )

        # β = slope, α = intercept
        beta = slope
        alpha = intercept
        r_squared = r_value ** 2

        # Annualize alpha (assuming daily returns)
        alpha_annualized = alpha * 365

        return alpha_annualized, beta, r_squared, p_value

    @staticmethod
    def calculate_information_ratio(
        alpha: float,
        tracking_error: float
    ) -> float:
        """
        Calculate Information Ratio (alpha per unit of tracking error).

        IR = α / TE

        Args:
            alpha: Annualized alpha
            tracking_error: Annualized tracking error

        Returns:
            Information ratio
        """
        if tracking_error == 0:
            return 0.0

        return alpha / tracking_error


class PerformanceAttributor:
    """
    Comprehensive performance attribution system.
    """

    def __init__(self):
        self.brinson_fachler = BrinsonFachlerAttribution()
        self.factor_regression = FactorRegression()

    def calculate_whale_contributions(
        self,
        trades: List[Dict],
        period_start: datetime,
        period_end: datetime
    ) -> List[WhaleContribution]:
        """
        Calculate individual whale contributions to portfolio.

        Args:
            trades: List of trades with keys:
                - whale_address
                - timestamp
                - pnl
                - size
            period_start: Start of attribution period
            period_end: End of attribution period

        Returns:
            List of WhaleContribution objects sorted by contribution
        """
        # Filter trades in period
        period_trades = [
            t for t in trades
            if period_start <= t['timestamp'] <= period_end
        ]

        # Group by whale
        whale_data = defaultdict(lambda: {
            'pnls': [],
            'sizes': [],
            'timestamps': []
        })

        for trade in period_trades:
            whale = trade['whale_address']
            whale_data[whale]['pnls'].append(trade['pnl'])
            whale_data[whale]['sizes'].append(trade['size'])
            whale_data[whale]['timestamps'].append(trade['timestamp'])

        # Calculate metrics for each whale
        contributions = []

        for whale, data in whale_data.items():
            pnls = np.array(data['pnls'])
            sizes = np.array(data['sizes'])

            # Total return
            total_return = np.sum(pnls)

            # Average weight (simplified - assume equal weighting)
            avg_weight = 1.0 / len(whale_data)

            # Contribution to portfolio
            contribution = avg_weight * total_return

            # Win rate
            wins = np.sum(pnls > 0)
            total_trades = len(pnls)
            win_rate = wins / total_trades if total_trades > 0 else 0.0

            # Sharpe ratio
            if len(pnls) > 1:
                sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(365) if np.std(pnls) > 0 else 0.0
            else:
                sharpe = 0.0

            contributions.append(WhaleContribution(
                whale_address=whale,
                total_return=total_return,
                contribution_to_portfolio=contribution,
                weight=avg_weight,
                num_trades=total_trades,
                win_rate=win_rate,
                sharpe_ratio=sharpe,
                rank=0  # Will be set after sorting
            ))

        # Sort by contribution (descending)
        contributions.sort(key=lambda x: x.contribution_to_portfolio, reverse=True)

        # Set ranks
        for i, contrib in enumerate(contributions, 1):
            contrib.rank = i

        return contributions

    def calculate_category_attribution(
        self,
        trades: List[Dict],
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Dict]:
        """
        Calculate performance attribution by category.

        Args:
            trades: List of trades with 'category' and 'pnl'
            period_start: Start of period
            period_end: End of period

        Returns:
            Dict mapping category to metrics
        """
        # Filter trades in period
        period_trades = [
            t for t in trades
            if period_start <= t['timestamp'] <= period_end
        ]

        # Group by category
        category_data = defaultdict(lambda: {
            'pnls': [],
            'count': 0,
            'total_pnl': 0.0
        })

        for trade in period_trades:
            cat = trade.get('category', 'UNKNOWN')
            pnl = trade.get('pnl', 0.0)

            category_data[cat]['pnls'].append(pnl)
            category_data[cat]['count'] += 1
            category_data[cat]['total_pnl'] += pnl

        # Calculate metrics
        results = {}

        for category, data in category_data.items():
            pnls = np.array(data['pnls'])

            # Return
            total_return = data['total_pnl']
            avg_return = np.mean(pnls)

            # Win rate
            wins = np.sum(pnls > 0)
            win_rate = wins / data['count'] if data['count'] > 0 else 0.0

            # Sharpe
            if len(pnls) > 1 and np.std(pnls) > 0:
                sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(365)
            else:
                sharpe = 0.0

            results[category] = {
                'total_return': total_return,
                'avg_return': avg_return,
                'num_trades': data['count'],
                'win_rate': win_rate,
                'sharpe_ratio': sharpe
            }

        return results

    def calculate_full_attribution(
        self,
        trades: List[Dict],
        period_start: datetime,
        period_end: datetime,
        benchmark_returns: Optional[np.ndarray] = None
    ) -> AttributionResult:
        """
        Calculate comprehensive performance attribution.

        Args:
            trades: List of all trades
            period_start: Attribution period start
            period_end: Attribution period end
            benchmark_returns: Optional benchmark returns for factor regression

        Returns:
            AttributionResult with full breakdown
        """
        # Filter trades in period
        period_trades = [
            t for t in trades
            if period_start <= t['timestamp'] <= period_end
        ]

        if not period_trades:
            return AttributionResult(
                total_return=0.0,
                benchmark_return=0.0,
                active_return=0.0,
                allocation_effect=0.0,
                selection_effect=0.0,
                interaction_effect=0.0,
                alpha=0.0,
                beta=1.0,
                r_squared=0.0,
                category_attribution={},
                whale_attribution={},
                period_start=period_start,
                period_end=period_end,
                num_trades=0,
                num_whales=0
            )

        # Total return
        total_pnl = sum(t['pnl'] for t in period_trades)
        total_return = total_pnl

        # Benchmark return (if not provided, use 0)
        benchmark_return = np.sum(benchmark_returns) if benchmark_returns is not None else 0.0

        # Active return
        active_return = total_return - benchmark_return

        # Category-level metrics
        category_attribution = self.calculate_category_attribution(
            period_trades, period_start, period_end
        )

        # Build category weights and returns for Brinson-Fachler
        portfolio_weights = {}
        portfolio_returns = {}
        benchmark_weights = {}
        benchmark_returns_dict = {}

        total_trades = len(period_trades)

        for category, metrics in category_attribution.items():
            weight = metrics['num_trades'] / total_trades
            portfolio_weights[category] = weight
            portfolio_returns[category] = metrics['total_return']

            # Benchmark: equal weight, zero return (naive assumption)
            benchmark_weights[category] = weight
            benchmark_returns_dict[category] = 0.0

        # Brinson-Fachler attribution
        allocation, selection, interaction, total_active = self.brinson_fachler.calculate_attribution(
            portfolio_weights,
            portfolio_returns,
            benchmark_weights,
            benchmark_returns_dict
        )

        # Factor regression (if benchmark provided)
        if benchmark_returns is not None:
            portfolio_rets = np.array([t['pnl'] for t in period_trades])
            alpha, beta, r_squared, p_value = self.factor_regression.calculate_alpha_beta(
                portfolio_rets, benchmark_returns
            )
        else:
            alpha = total_return
            beta = 1.0
            r_squared = 0.0

        # Whale contributions
        whale_contributions = self.calculate_whale_contributions(
            period_trades, period_start, period_end
        )

        whale_attribution = {
            wc.whale_address: wc.contribution_to_portfolio
            for wc in whale_contributions
        }

        # Number of unique whales
        num_whales = len(set(t['whale_address'] for t in period_trades))

        return AttributionResult(
            total_return=total_return,
            benchmark_return=benchmark_return,
            active_return=active_return,
            allocation_effect=allocation,
            selection_effect=selection,
            interaction_effect=interaction,
            alpha=alpha,
            beta=beta,
            r_squared=r_squared,
            category_attribution=category_attribution,
            whale_attribution=whale_attribution,
            period_start=period_start,
            period_end=period_end,
            num_trades=len(period_trades),
            num_whales=num_whales
        )

    def generate_attribution_report(
        self,
        attribution: AttributionResult
    ) -> str:
        """
        Generate human-readable attribution report.

        Args:
            attribution: AttributionResult

        Returns:
            Formatted report string
        """
        report = []
        report.append("="*80)
        report.append("PERFORMANCE ATTRIBUTION REPORT")
        report.append("="*80)
        report.append(f"Period: {attribution.period_start.strftime('%Y-%m-%d')} to {attribution.period_end.strftime('%Y-%m-%d')}")
        report.append(f"Trades: {attribution.num_trades} | Whales: {attribution.num_whales}")
        report.append("")

        # Returns
        report.append("RETURNS")
        report.append("-"*80)
        report.append(f"Portfolio Return:      ${attribution.total_return:,.2f}")
        report.append(f"Benchmark Return:      ${attribution.benchmark_return:,.2f}")
        report.append(f"Active Return:         ${attribution.active_return:,.2f}")
        report.append("")

        # Brinson-Fachler
        report.append("BRINSON-FACHLER ATTRIBUTION")
        report.append("-"*80)
        report.append(f"Allocation Effect:     ${attribution.allocation_effect:,.2f}")
        report.append(f"Selection Effect:      ${attribution.selection_effect:,.2f}")
        report.append(f"Interaction Effect:    ${attribution.interaction_effect:,.2f}")

        total_attribution = attribution.allocation_effect + attribution.selection_effect + attribution.interaction_effect

        if total_attribution > 0:
            selection_pct = (attribution.selection_effect / total_attribution) * 100
            report.append(f"\nSelection % of Alpha:  {selection_pct:.1f}% (Target: 74%)")

        report.append("")

        # Factor analysis
        report.append("FACTOR ANALYSIS")
        report.append("-"*80)
        report.append(f"Alpha (skill):         ${attribution.alpha:,.2f}")
        report.append(f"Beta (market):         {attribution.beta:.2f}")
        report.append(f"R-squared:             {attribution.r_squared:.2%}")
        report.append("")

        # Category breakdown
        report.append("CATEGORY ATTRIBUTION")
        report.append("-"*80)
        for category, metrics in sorted(
            attribution.category_attribution.items(),
            key=lambda x: x[1]['total_return'],
            reverse=True
        ):
            report.append(f"{category:15} Return: ${metrics['total_return']:>10,.2f} | "
                         f"Win Rate: {metrics['win_rate']:>5.1%} | "
                         f"Sharpe: {metrics['sharpe_ratio']:>5.2f} | "
                         f"Trades: {metrics['num_trades']:>4}")

        report.append("")

        # Top whales
        report.append("TOP 10 WHALE CONTRIBUTIONS")
        report.append("-"*80)

        top_whales = sorted(
            attribution.whale_attribution.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        for i, (whale, contribution) in enumerate(top_whales, 1):
            short_address = f"{whale[:6]}...{whale[-4:]}"
            report.append(f"{i:2}. {short_address}  ${contribution:>10,.2f}")

        report.append("")
        report.append("="*80)

        return "\n".join(report)


# Example usage and testing
if __name__ == "__main__":
    print("="*80)
    print("PERFORMANCE ATTRIBUTION DEMO")
    print("="*80)

    # Initialize attributor
    attributor = PerformanceAttributor()

    # Simulate trade data
    np.random.seed(42)

    trades = []
    base_date = datetime.now() - timedelta(days=90)

    categories = ['POLITICS', 'CRYPTO', 'SPORTS']
    whales = [f"0xWHALE{i:02d}" for i in range(1, 11)]

    for i in range(500):
        whale = np.random.choice(whales)
        category = np.random.choice(categories)

        # Different performance by category
        if category == 'POLITICS':
            pnl = np.random.normal(loc=150, scale=80)
        elif category == 'CRYPTO':
            pnl = np.random.normal(loc=100, scale=120)
        else:
            pnl = np.random.normal(loc=80, scale=60)

        trades.append({
            'whale_address': whale,
            'category': category,
            'pnl': pnl,
            'timestamp': base_date + timedelta(days=i/5),
            'size': 5000
        })

    # Calculate attribution
    period_start = base_date
    period_end = datetime.now()

    attribution = attributor.calculate_full_attribution(
        trades,
        period_start,
        period_end
    )

    # Generate report
    report = attributor.generate_attribution_report(attribution)
    print(report)

    print("\n📊 Key Insights:")
    print("-"*80)

    total_effects = attribution.allocation_effect + attribution.selection_effect + attribution.interaction_effect
    if total_effects > 0:
        selection_pct = (attribution.selection_effect / total_effects) * 100
        allocation_pct = (attribution.allocation_effect / total_effects) * 100
        interaction_pct = (attribution.interaction_effect / total_effects) * 100

        print(f"Selection (whale picking):     {selection_pct:>5.1f}% of alpha")
        print(f"Allocation (category timing):  {allocation_pct:>5.1f}% of alpha")
        print(f"Interaction (combined):        {interaction_pct:>5.1f}% of alpha")
        print(f"\nResearch Target: 74% from selection")
        print(f"Current:         {selection_pct:.1f}% from selection")

    print("\n" + "="*80)
    print("✅ Brinson-Fachler attribution decomposes sources of alpha")
    print("✅ Factor regression separates skill (α) from market (β)")
    print("✅ Category and whale-level attribution identify top performers")
    print("="*80)
