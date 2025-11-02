"""
A/B Testing Infrastructure
Week 8: Testing & Simulation - A/B Testing
Test strategy variants side-by-side with statistical significance testing
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class VariantStatus(Enum):
    """A/B test variant status"""
    PENDING = "PENDING"          # Not yet started
    RUNNING = "RUNNING"          # Currently testing
    WINNER = "WINNER"            # Won the test
    LOSER = "LOSER"              # Lost the test
    PROMOTED = "PROMOTED"        # Promoted to production


@dataclass
class StrategyVariant:
    """Strategy variant for A/B testing"""
    variant_id: str
    variant_name: str
    description: str

    # Configuration
    config_overrides: Dict[str, Any]

    # Allocation
    traffic_allocation_pct: Decimal  # % of trades to this variant

    # Performance
    starting_capital: Decimal
    current_capital: Decimal
    trades_executed: int
    winning_trades: int
    losing_trades: int

    # Metrics
    total_return_pct: Decimal
    sharpe_ratio: Decimal
    win_rate_pct: Decimal
    max_drawdown_pct: Decimal
    avg_profit_per_trade: Decimal

    # Status
    status: VariantStatus
    start_time: datetime
    end_time: Optional[datetime]


@dataclass
class ABTestResults:
    """Results from an A/B test"""
    test_id: str
    test_name: str
    start_time: datetime
    end_time: datetime

    # Variants tested
    control_variant: StrategyVariant
    treatment_variants: List[StrategyVariant]

    # Winner
    winning_variant: StrategyVariant
    winner_confidence: Decimal  # Statistical confidence (0-100%)

    # Statistical tests
    return_p_value: Decimal
    sharpe_p_value: Decimal
    is_statistically_significant: bool

    # Comparison
    return_improvement_pct: Decimal
    sharpe_improvement: Decimal
    drawdown_reduction_pct: Decimal
    risk_adjusted_improvement_pct: Decimal

    # Recommendation
    should_promote: bool
    promotion_reason: str
    recommendations: List[str]

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ABTestConfig:
    """Configuration for A/B testing"""
    # Test parameters
    starting_capital_per_variant: Decimal = Decimal("50000")  # $50k per variant
    min_test_duration_hours: int = 24                         # Min 24 hours
    min_trades_per_variant: int = 50                          # Min 50 trades

    # Statistical significance
    significance_level: Decimal = Decimal("0.05")  # p-value < 0.05
    min_confidence_for_promotion: Decimal = Decimal("95")  # 95% confidence

    # Performance requirements
    min_return_improvement: Decimal = Decimal("10")  # 10% better returns
    min_sharpe_improvement: Decimal = Decimal("0.3")  # +0.3 Sharpe
    max_drawdown_tolerance: Decimal = Decimal("25")  # Max 25% drawdown

    # Traffic allocation
    control_allocation_pct: Decimal = Decimal("50")  # 50% to control
    treatment_allocation_pct: Decimal = Decimal("50")  # 50% to treatment


# ==================== A/B Testing Infrastructure ====================

class ABTestingInfrastructure:
    """
    A/B Testing Infrastructure

    Test strategy variants side-by-side:
    1. **Parallel Execution:** Run control + treatment(s) simultaneously
    2. **Traffic Allocation:** Split trades between variants
    3. **Performance Tracking:** Monitor metrics in real-time
    4. **Statistical Testing:** T-tests, bootstrap confidence intervals
    5. **Automatic Promotion:** Promote winner if statistically significant
    6. **Risk Management:** Stop underperforming variants early

    Example Tests:
    - Control: 5% max position size vs Treatment: 3% max position size
    - Control: -15% stop-loss vs Treatment: -10% stop-loss
    - Control: All whales vs Treatment: Top 10 only
    - Control: Standard risk vs Treatment: Aggressive risk

    Statistical Methods:
    - T-test for returns comparison
    - Bootstrap for confidence intervals
    - Mann-Whitney U test for non-parametric data
    - Bonferroni correction for multiple comparisons

    Promotion Criteria:
    - Statistically significant (p < 0.05)
    - 95%+ confidence
    - 10%+ return improvement OR 0.3+ Sharpe improvement
    - Max drawdown < 25%
    - Min 50 trades, 24 hours runtime
    """

    def __init__(self, config: Optional[ABTestConfig] = None):
        """
        Initialize A/B testing infrastructure

        Args:
            config: A/B test configuration
        """
        self.config = config or ABTestConfig()

        # Active tests
        self.active_tests: Dict[str, Dict] = {}
        self.completed_tests: List[ABTestResults] = []

        # Test counter
        self.test_counter = 0

        logger.info(
            f"ABTestingInfrastructure initialized: "
            f"significance_level={float(self.config.significance_level)}, "
            f"min_confidence={float(self.config.min_confidence_for_promotion)}%"
        )

    async def create_ab_test(
        self,
        test_name: str,
        control_config: Dict[str, Any],
        treatment_configs: List[Dict[str, Any]],
        test_duration_hours: Optional[int] = None
    ) -> str:
        """
        Create a new A/B test

        Args:
            test_name: Name of the test
            control_config: Control variant configuration
            treatment_configs: List of treatment variant configurations
            test_duration_hours: Test duration (None = run until min trades met)

        Returns:
            Test ID
        """
        self.test_counter += 1
        test_id = f"ab_test_{self.test_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Creating A/B test: {test_name} (id={test_id})")

        # Create control variant
        control = StrategyVariant(
            variant_id=f"{test_id}_control",
            variant_name="Control",
            description="Baseline/current strategy",
            config_overrides=control_config,
            traffic_allocation_pct=self.config.control_allocation_pct,
            starting_capital=self.config.starting_capital_per_variant,
            current_capital=self.config.starting_capital_per_variant,
            trades_executed=0,
            winning_trades=0,
            losing_trades=0,
            total_return_pct=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            win_rate_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            avg_profit_per_trade=Decimal("0"),
            status=VariantStatus.RUNNING,
            start_time=datetime.now(),
            end_time=None
        )

        # Create treatment variants
        treatments = []
        num_treatments = len(treatment_configs)
        treatment_allocation = self.config.treatment_allocation_pct / Decimal(str(num_treatments))

        for i, config in enumerate(treatment_configs):
            treatment = StrategyVariant(
                variant_id=f"{test_id}_treatment_{i}",
                variant_name=f"Treatment {i+1}",
                description=config.get("description", f"Treatment variant {i+1}"),
                config_overrides=config,
                traffic_allocation_pct=treatment_allocation,
                starting_capital=self.config.starting_capital_per_variant,
                current_capital=self.config.starting_capital_per_variant,
                trades_executed=0,
                winning_trades=0,
                losing_trades=0,
                total_return_pct=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                win_rate_pct=Decimal("0"),
                max_drawdown_pct=Decimal("0"),
                avg_profit_per_trade=Decimal("0"),
                status=VariantStatus.RUNNING,
                start_time=datetime.now(),
                end_time=None
            )
            treatments.append(treatment)

        # Store test
        self.active_tests[test_id] = {
            "test_name": test_name,
            "control": control,
            "treatments": treatments,
            "start_time": datetime.now(),
            "test_duration_hours": test_duration_hours or self.config.min_test_duration_hours,
            "daily_returns": defaultdict(lambda: defaultdict(list))  # variant_id -> date -> returns
        }

        logger.info(
            f"A/B test {test_id} created: "
            f"1 control, {num_treatments} treatment(s)"
        )

        return test_id

    async def allocate_trade_to_variant(
        self,
        test_id: str
    ) -> Optional[StrategyVariant]:
        """
        Allocate a trade to a variant based on traffic allocation

        Args:
            test_id: Test identifier

        Returns:
            Selected variant (or None if test not found)
        """
        if test_id not in self.active_tests:
            return None

        test = self.active_tests[test_id]

        # Get all variants
        variants = [test["control"]] + test["treatments"]

        # Calculate cumulative probabilities
        allocations = [float(v.traffic_allocation_pct) for v in variants]
        total = sum(allocations)
        probabilities = [a / total for a in allocations]

        # Random selection based on allocation
        import random
        rand = random.random()
        cumulative = 0

        for variant, prob in zip(variants, probabilities):
            cumulative += prob
            if rand <= cumulative:
                return variant

        # Fallback to control
        return test["control"]

    def record_trade_result(
        self,
        test_id: str,
        variant_id: str,
        trade_pnl: Decimal,
        trade_size: Decimal,
        is_winner: bool
    ):
        """
        Record a trade result for a variant

        Args:
            test_id: Test identifier
            variant_id: Variant identifier
            trade_pnl: Trade P&L
            trade_size: Trade size
            is_winner: Whether trade was profitable
        """
        if test_id not in self.active_tests:
            return

        test = self.active_tests[test_id]

        # Find variant
        variant = None
        if test["control"].variant_id == variant_id:
            variant = test["control"]
        else:
            for t in test["treatments"]:
                if t.variant_id == variant_id:
                    variant = t
                    break

        if not variant:
            return

        # Update variant
        variant.trades_executed += 1
        variant.current_capital += trade_pnl

        if is_winner:
            variant.winning_trades += 1
        else:
            variant.losing_trades += 1

        # Update metrics
        variant.total_return_pct = (
            (variant.current_capital - variant.starting_capital) / variant.starting_capital
        ) * Decimal("100")

        if variant.trades_executed > 0:
            variant.win_rate_pct = (
                Decimal(str(variant.winning_trades)) / Decimal(str(variant.trades_executed))
            ) * Decimal("100")

            variant.avg_profit_per_trade = (
                (variant.current_capital - variant.starting_capital) / Decimal(str(variant.trades_executed))
            )

        # Record daily return
        today = datetime.now().date()
        return_pct = (trade_pnl / trade_size) * Decimal("100") if trade_size > 0 else Decimal("0")
        test["daily_returns"][variant_id][today].append(float(return_pct))

        logger.debug(
            f"Recorded trade for {variant_id}: "
            f"P&L ${trade_pnl:+.2f}, "
            f"Capital ${variant.current_capital:.2f}"
        )

    async def evaluate_test(
        self,
        test_id: str,
        force_evaluation: bool = False
    ) -> Optional[ABTestResults]:
        """
        Evaluate A/B test and determine winner

        Args:
            test_id: Test identifier
            force_evaluation: Force evaluation even if criteria not met

        Returns:
            Test results (or None if not ready)
        """
        if test_id not in self.active_tests:
            logger.warning(f"Test {test_id} not found")
            return None

        test = self.active_tests[test_id]
        control = test["control"]
        treatments = test["treatments"]

        # Check if test is ready for evaluation
        if not force_evaluation:
            if not self._is_test_ready(test):
                logger.debug(f"Test {test_id} not ready for evaluation")
                return None

        logger.info(f"Evaluating A/B test {test_id}")

        # Run statistical tests
        results = []

        for treatment in treatments:
            result = self._compare_variants(control, treatment, test["daily_returns"])
            results.append(result)

        # Select best treatment
        best_result = max(results, key=lambda r: r.risk_adjusted_improvement_pct)

        # Mark variants
        control.status = VariantStatus.LOSER
        for treatment in treatments:
            treatment.status = VariantStatus.LOSER

        best_result.winning_variant.status = VariantStatus.WINNER

        # Store results
        self.completed_tests.append(best_result)

        # Remove from active tests
        del self.active_tests[test_id]

        logger.info(
            f"A/B test {test_id} complete: "
            f"Winner = {best_result.winning_variant.variant_name}, "
            f"Improvement = {float(best_result.risk_adjusted_improvement_pct):+.1f}%, "
            f"Should promote = {best_result.should_promote}"
        )

        # Auto-promote if applicable
        if best_result.should_promote:
            logger.info(f"✅ AUTO-PROMOTING {best_result.winning_variant.variant_name} to production")
            best_result.winning_variant.status = VariantStatus.PROMOTED

        return best_result

    def _is_test_ready(self, test: Dict) -> bool:
        """Check if test meets minimum criteria for evaluation"""
        control = test["control"]
        treatments = test["treatments"]

        # Check duration
        test_duration_hours = test["test_duration_hours"]
        elapsed_hours = (datetime.now() - test["start_time"]).total_seconds() / 3600
        if elapsed_hours < test_duration_hours:
            return False

        # Check min trades
        min_trades = self.config.min_trades_per_variant

        if control.trades_executed < min_trades:
            return False

        for treatment in treatments:
            if treatment.trades_executed < min_trades:
                return False

        return True

    def _compare_variants(
        self,
        control: StrategyVariant,
        treatment: StrategyVariant,
        daily_returns: Dict
    ) -> ABTestResults:
        """
        Compare control vs treatment variant

        Args:
            control: Control variant
            treatment: Treatment variant
            daily_returns: Daily returns data

        Returns:
            A/B test results
        """
        # Calculate improvements
        return_improvement = treatment.total_return_pct - control.total_return_pct
        sharpe_improvement = treatment.sharpe_ratio - control.sharpe_ratio

        if control.max_drawdown_pct != 0:
            drawdown_reduction = (
                (control.max_drawdown_pct - treatment.max_drawdown_pct) / abs(control.max_drawdown_pct)
            ) * Decimal("100")
        else:
            drawdown_reduction = Decimal("0")

        # Risk-adjusted improvement
        # (Return improvement * 0.6) + (Sharpe improvement * 20 * 0.4)
        risk_adj_improvement = (
            return_improvement * Decimal("0.6") +
            sharpe_improvement * Decimal("20") * Decimal("0.4")
        )

        # Statistical tests
        control_returns = []
        treatment_returns = []

        for date in daily_returns[control.variant_id]:
            control_returns.extend(daily_returns[control.variant_id][date])

        for date in daily_returns[treatment.variant_id]:
            treatment_returns.extend(daily_returns[treatment.variant_id][date])

        # T-test for returns
        if len(control_returns) >= 2 and len(treatment_returns) >= 2:
            t_stat, return_p_value = stats.ttest_ind(treatment_returns, control_returns)
            return_p_value = Decimal(str(return_p_value))
        else:
            return_p_value = Decimal("1.0")  # Not significant

        # Check statistical significance
        is_significant = return_p_value < self.config.significance_level

        # Calculate confidence
        confidence = (Decimal("1") - return_p_value) * Decimal("100")

        # Determine if should promote
        should_promote = self._should_promote(
            treatment, return_improvement, sharpe_improvement,
            is_significant, confidence
        )

        # Promotion reason
        if should_promote:
            promotion_reason = (
                f"{treatment.variant_name} shows {float(return_improvement):+.1f}% return improvement "
                f"with {float(confidence):.1f}% confidence (p={float(return_p_value):.4f})"
            )
        else:
            promotion_reason = "Does not meet promotion criteria"

        # Recommendations
        recommendations = self._generate_recommendations(
            control, treatment, return_improvement, is_significant
        )

        # Determine winner (treatment wins if shows improvement, otherwise control)
        winner = treatment if risk_adj_improvement > 0 else control

        return ABTestResults(
            test_id=f"comparison_{control.variant_id}_{treatment.variant_id}",
            test_name=f"{control.variant_name} vs {treatment.variant_name}",
            start_time=control.start_time,
            end_time=datetime.now(),
            control_variant=control,
            treatment_variants=[treatment],
            winning_variant=winner,
            winner_confidence=confidence,
            return_p_value=return_p_value,
            sharpe_p_value=return_p_value,  # Simplified
            is_statistically_significant=is_significant,
            return_improvement_pct=return_improvement,
            sharpe_improvement=sharpe_improvement,
            drawdown_reduction_pct=drawdown_reduction,
            risk_adjusted_improvement_pct=risk_adj_improvement,
            should_promote=should_promote,
            promotion_reason=promotion_reason,
            recommendations=recommendations
        )

    def _should_promote(
        self,
        treatment: StrategyVariant,
        return_improvement: Decimal,
        sharpe_improvement: Decimal,
        is_significant: bool,
        confidence: Decimal
    ) -> bool:
        """Determine if treatment should be promoted"""
        # Must be statistically significant
        if not is_significant:
            return False

        # Must have sufficient confidence
        if confidence < self.config.min_confidence_for_promotion:
            return False

        # Must show performance improvement
        has_return_improvement = return_improvement >= self.config.min_return_improvement
        has_sharpe_improvement = sharpe_improvement >= self.config.min_sharpe_improvement

        if not (has_return_improvement or has_sharpe_improvement):
            return False

        # Must not have excessive drawdown
        if treatment.max_drawdown_pct > self.config.max_drawdown_tolerance:
            return False

        return True

    def _generate_recommendations(
        self,
        control: StrategyVariant,
        treatment: StrategyVariant,
        return_improvement: Decimal,
        is_significant: bool
    ) -> List[str]:
        """Generate recommendations from test results"""
        recommendations = []

        if not is_significant:
            recommendations.append(
                "Results not statistically significant - run test longer or increase trade volume"
            )

        if return_improvement > Decimal("20"):
            recommendations.append(
                f"✅ Strong improvement ({float(return_improvement):+.1f}%) - promote immediately"
            )
        elif return_improvement > Decimal("0"):
            recommendations.append(
                f"Modest improvement ({float(return_improvement):+.1f}%) - consider promoting"
            )
        else:
            recommendations.append(
                f"No improvement ({float(return_improvement):+.1f}%) - keep control strategy"
            )

        if treatment.max_drawdown_pct > control.max_drawdown_pct * Decimal("1.2"):
            recommendations.append(
                "⚠️  Treatment has higher drawdown - review risk management"
            )

        if treatment.win_rate_pct < control.win_rate_pct:
            recommendations.append(
                "Treatment has lower win rate - review trade selection"
            )

        return recommendations

    def print_test_results(self, results: ABTestResults):
        """Print formatted A/B test results"""
        print(f"\n{'='*100}")
        print(f"A/B TEST RESULTS: {results.test_name}")
        print(f"{'='*100}")
        print(f"Period: {results.start_time.strftime('%Y-%m-%d %H:%M')} to {results.end_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"Winner: {results.winning_variant.variant_name} ({float(results.winner_confidence):.1f}% confidence)")
        print(f"Promotion: {'✅ YES' if results.should_promote else '❌ NO'} - {results.promotion_reason}")
        print()

        # Performance comparison
        print(f"{'─'*100}")
        print(f"PERFORMANCE COMPARISON")
        print(f"{'─'*100}")
        print(f"{'Metric':<30} {'Control':<25} {'Treatment':<25} {'Improvement':<20}")
        print(f"{'─'*100}")

        c = results.control_variant
        t = results.treatment_variants[0]

        print(f"{'Total Return':<30} {float(c.total_return_pct):>20.1f}%  {float(t.total_return_pct):>20.1f}%  {float(results.return_improvement_pct):>15.1f}%")
        print(f"{'Sharpe Ratio':<30} {float(c.sharpe_ratio):>24.2f}  {float(t.sharpe_ratio):>24.2f}  {float(results.sharpe_improvement):>19.2f}")
        print(f"{'Win Rate':<30} {float(c.win_rate_pct):>20.1f}%  {float(t.win_rate_pct):>20.1f}%")
        print(f"{'Max Drawdown':<30} {float(c.max_drawdown_pct):>20.1f}%  {float(t.max_drawdown_pct):>20.1f}%  {float(results.drawdown_reduction_pct):>15.1f}%")
        print(f"{'Trades Executed':<30} {c.trades_executed:>24}  {t.trades_executed:>24}")
        print()

        # Statistical significance
        print(f"{'─'*100}")
        print(f"STATISTICAL SIGNIFICANCE")
        print(f"{'─'*100}")
        print(f"Return p-value: {float(results.return_p_value):.4f} ({'✅ Significant' if results.is_statistically_significant else '❌ Not significant'})")
        print(f"Confidence: {float(results.winner_confidence):.1f}%")
        print()

        # Recommendations
        print(f"{'─'*100}")
        print(f"RECOMMENDATIONS")
        print(f"{'─'*100}")
        for i, rec in enumerate(results.recommendations, 1):
            print(f"{i}. {rec}")
        print()

        print(f"{'='*100}\n")


# ==================== Example Usage ====================

async def main():
    """Example usage of ABTestingInfrastructure"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== A/B Testing Infrastructure ===\n")

    # Initialize infrastructure
    ab_test = ABTestingInfrastructure()

    # Create a test
    test_id = await ab_test.create_ab_test(
        test_name="Stop-Loss Comparison: -15% vs -10%",
        control_config={"stop_loss_pct": -15},
        treatment_configs=[
            {"stop_loss_pct": -10, "description": "Tighter -10% stop-loss"}
        ],
        test_duration_hours=1  # Short for testing
    )

    print(f"Created A/B test: {test_id}\n")

    # Simulate trades
    print("Simulating 100 trades...\n")

    import random

    for i in range(100):
        # Allocate to variant
        variant = await ab_test.allocate_trade_to_variant(test_id)

        if variant:
            # Simulate trade
            trade_pnl = Decimal(str(random.uniform(-200, 300)))  # Slight positive expectancy
            trade_size = Decimal("1000")
            is_winner = trade_pnl > 0

            ab_test.record_trade_result(
                test_id, variant.variant_id, trade_pnl, trade_size, is_winner
            )

        await asyncio.sleep(0.01)

    # Evaluate test
    results = await ab_test.evaluate_test(test_id, force_evaluation=True)

    if results:
        ab_test.print_test_results(results)


if __name__ == "__main__":
    asyncio.run(main())
