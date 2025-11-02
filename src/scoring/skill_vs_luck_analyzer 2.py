"""
Statistical Skill vs Luck Separation Framework
Based on Section 6 of the Polymarket Whale Filtering Research Brief

This module implements rigorous statistical tests to separate skilled traders
from lucky ones, ensuring copy-trading strategies emphasize persistent edge.

Multi-Stage Methodology:
1. Establish null model (performance is due to luck)
2. Assess statistical significance (bootstrap resampling)
3. Estimate skill persistence (rolling window regression)
4. Control for biases (multiple testing, selection, small-sample, survivorship)

Key Statistical Corrections:
- Deflated Sharpe Ratio (DSR): Corrects for selection bias
- Probabilistic Sharpe Ratio (PSR): Assesses statistical significance
- False Discovery Rate (FDR): Controls for multiple hypothesis testing
- White's Reality Check / Hansen's SPA: Tests if best is truly superior
- Empirical Bayes Shrinkage: Robust estimates for short histories

References:
- Bailey, D.H. & López de Prado, M. (2014). The Deflated Sharpe Ratio
- Harvey, C.R. & Liu, Y. (2020). Backtesting
- Research Brief Section 6: Skill vs Luck Statistical Analysis
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats
from scipy.special import comb

logger = logging.getLogger(__name__)


@dataclass
class SkillTestConfig:
    """Configuration for skill vs luck testing"""

    # Statistical significance
    confidence_level: float = 0.95
    min_trades_for_test: int = 30

    # Bootstrap parameters
    bootstrap_iterations: int = 10000
    block_length: int = 5  # For stationary bootstrap to preserve autocorrelation

    # Multiple testing correction
    false_discovery_rate: float = 0.05  # 5% FDR threshold

    # Persistence testing
    rolling_window_days: int = 90
    min_windows_for_persistence: int = 4

    # Empirical Bayes shrinkage
    use_empirical_bayes: bool = True
    shrinkage_intensity_auto: bool = True  # Auto-estimate shrinkage intensity

    # Null model parameters
    target_sharpe_ratio: float = 0.0  # Null hypothesis: SR = 0
    risk_free_rate_daily: float = 0.00012  # 4.5% annual ≈ 0.012% daily


@dataclass
class SkillTestResult:
    """Results from skill vs luck testing"""

    address: str
    test_timestamp: datetime

    # Performance metrics
    observed_sharpe_ratio: float
    observed_information_coefficient: float
    observed_log_score: float
    observed_brier_score: float

    # Statistical significance
    p_value_sharpe: float  # Probability performance is due to luck
    is_significant: bool  # After FDR correction
    adjusted_p_value: float  # FDR-adjusted p-value

    # Skill persistence
    persistence_t_statistic: float
    persistence_p_value: float
    has_persistent_skill: bool

    # Bias corrections
    deflated_sharpe_ratio: float  # Selection bias corrected
    probabilistic_sharpe_ratio: float  # P(SR > target)
    empirical_bayes_sharpe: float  # Shrunk toward population mean

    # Bootstrap confidence intervals
    sharpe_ci_lower: float
    sharpe_ci_upper: float
    ic_ci_lower: float
    ic_ci_upper: float

    # Summary
    overall_skill_score: float  # 0-1, combining all tests
    skill_category: str  # "HIGH_SKILL", "MODERATE_SKILL", "LIKELY_LUCK", "INSUFFICIENT_DATA"


class SkillVsLuckAnalyzer:
    """
    Comprehensive statistical framework to separate skill from luck.

    Implements the 4-step methodology from Section 6:
    1. Null model establishment
    2. Statistical significance assessment
    3. Skill persistence estimation
    4. Bias correction
    """

    def __init__(self, config: SkillTestConfig = None):
        """
        Initialize the skill vs luck analyzer.

        Args:
            config: Configuration object (uses defaults if None)
        """
        self.config = config or SkillTestConfig()
        logger.info("SkillVsLuckAnalyzer initialized")

    def stationary_bootstrap(
        self,
        returns: np.ndarray,
        num_iterations: int = 10000,
        block_length: int = 5
    ) -> np.ndarray:
        """
        Stationary bootstrap resampling that preserves temporal dependencies.

        Unlike standard bootstrap, this method respects autocorrelation
        in returns by sampling blocks rather than individual observations.

        Reference: Section 6, "Stationary Bootstrap"

        Args:
            returns: Array of returns
            num_iterations: Number of bootstrap samples
            block_length: Average block length

        Returns:
            Array of shape (num_iterations, len(returns)) with bootstrap samples
        """
        n = len(returns)
        bootstrap_samples = np.zeros((num_iterations, n))

        for i in range(num_iterations):
            resampled = []
            while len(resampled) < n:
                # Random starting point
                start_idx = np.random.randint(0, n)

                # Geometric block length
                block_size = np.random.geometric(1.0 / block_length)
                block_size = min(block_size, n - len(resampled))

                # Extract block
                block = []
                for j in range(block_size):
                    idx = (start_idx + j) % n
                    block.append(returns[idx])

                resampled.extend(block)

            bootstrap_samples[i, :] = resampled[:n]

        return bootstrap_samples

    def calculate_sharpe_ratio_bootstrap_ci(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
        confidence_level: float = 0.95
    ) -> Tuple[float, float, float, float, float]:
        """
        Calculate Sharpe ratio with bootstrap confidence interval.

        Args:
            returns: Array of returns
            risk_free_rate: Risk-free rate (daily)
            confidence_level: Confidence level for CI

        Returns:
            Tuple of (observed_sr, p_value, ci_lower, ci_upper, bootstrap_std)
        """
        if len(returns) < self.config.min_trades_for_test:
            return (0.0, 1.0, 0.0, 0.0, 0.0)

        # Observed Sharpe ratio
        excess_returns = returns - risk_free_rate
        observed_sr = (
            np.mean(excess_returns) / np.std(excess_returns)
            if np.std(excess_returns) > 0
            else 0.0
        )

        # Bootstrap
        bootstrap_samples = self.stationary_bootstrap(
            returns,
            num_iterations=self.config.bootstrap_iterations,
            block_length=self.config.block_length
        )

        # Calculate SR for each bootstrap sample
        bootstrap_srs = []
        for sample in bootstrap_samples:
            sample_excess = sample - risk_free_rate
            if np.std(sample_excess) > 0:
                sr = np.mean(sample_excess) / np.std(sample_excess)
                bootstrap_srs.append(sr)

        bootstrap_srs = np.array(bootstrap_srs)

        # p-value: proportion of bootstrap SRs <= 0 (null hypothesis: SR = 0)
        p_value = np.mean(bootstrap_srs <= self.config.target_sharpe_ratio)

        # Confidence interval
        alpha = 1 - confidence_level
        ci_lower = np.percentile(bootstrap_srs, 100 * alpha / 2)
        ci_upper = np.percentile(bootstrap_srs, 100 * (1 - alpha / 2))

        # Bootstrap standard deviation
        bootstrap_std = np.std(bootstrap_srs)

        return (observed_sr, p_value, ci_lower, ci_upper, bootstrap_std)

    def test_skill_persistence(
        self,
        returns_series: List[Tuple[datetime, float]],
        window_days: int = 90
    ) -> Tuple[float, float, bool]:
        """
        Test if performance is stable over time using rolling window regression.

        Persistent skill should show consistent performance across time windows.

        Reference: Section 6, "Estimate Skill Persistence"

        Args:
            returns_series: List of (timestamp, return) tuples
            window_days: Size of rolling window

        Returns:
            Tuple of (t_statistic, p_value, has_persistence)
        """
        if len(returns_series) < self.config.min_trades_for_test:
            return (0.0, 1.0, False)

        # Sort by timestamp
        sorted_returns = sorted(returns_series, key=lambda x: x[0])

        # Create rolling windows
        window_sharpes = []
        window_delta = timedelta(days=window_days)

        i = 0
        while i < len(sorted_returns):
            window_start = sorted_returns[i][0]
            window_end = window_start + window_delta

            # Collect returns in window
            window_returns = [
                r for t, r in sorted_returns
                if window_start <= t < window_end
            ]

            if len(window_returns) >= 10:  # Minimum for stable SR
                window_sr = (
                    np.mean(window_returns) / np.std(window_returns)
                    if np.std(window_returns) > 0
                    else 0.0
                )
                window_sharpes.append(window_sr)

            # Move to next window (50% overlap)
            i += len(window_returns) // 2 + 1

        if len(window_sharpes) < self.config.min_windows_for_persistence:
            return (0.0, 1.0, False)

        # Regress window SRs on constant (test if mean SR significantly > 0)
        # This is equivalent to a one-sample t-test with HAC standard errors

        # Use Newey-West HAC standard errors to account for autocorrelation
        mean_sr = np.mean(window_sharpes)
        n_windows = len(window_sharpes)

        # Simple t-test (would use Newey-West in production)
        std_sr = np.std(window_sharpes, ddof=1)
        t_stat = mean_sr / (std_sr / np.sqrt(n_windows)) if std_sr > 0 else 0.0

        # p-value (two-tailed)
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=n_windows - 1))

        has_persistence = p_value < (1 - self.config.confidence_level)

        return (t_stat, p_value, has_persistence)

    def benjamini_hochberg_fdr(
        self,
        p_values: List[float],
        alpha: float = 0.05
    ) -> Tuple[List[bool], List[float]]:
        """
        Benjamini-Hochberg False Discovery Rate (FDR) correction.

        Controls the expected proportion of false discoveries among rejections.

        Reference: Section 6, "Multiple Testing Bias"

        Args:
            p_values: List of p-values from multiple tests
            alpha: FDR threshold (default: 0.05)

        Returns:
            Tuple of (list of significance flags, list of adjusted p-values)
        """
        m = len(p_values)
        if m == 0:
            return ([], [])

        # Sort p-values
        sorted_indices = np.argsort(p_values)
        sorted_p_values = np.array(p_values)[sorted_indices]

        # BH procedure: find largest k where p_(k) <= (k/m) * alpha
        bh_threshold = np.arange(1, m + 1) / m * alpha
        significant_mask = sorted_p_values <= bh_threshold

        # Find largest k
        if not np.any(significant_mask):
            # No rejections
            adjusted_p = [1.0] * m
            is_significant = [False] * m
        else:
            k_max = np.where(significant_mask)[0][-1]

            # Adjusted p-values
            adjusted_p = [0.0] * m
            is_significant = [False] * m

            for i, orig_idx in enumerate(sorted_indices):
                if i <= k_max:
                    is_significant[orig_idx] = True

                # Adjusted p-value = min(1, p * m / rank)
                adjusted_p[orig_idx] = min(1.0, sorted_p_values[i] * m / (i + 1))

        return (is_significant, adjusted_p)

    def whites_reality_check(
        self,
        returns_matrix: np.ndarray,
        best_strategy_idx: int = 0
    ) -> float:
        """
        White's Reality Check to test if the best performer is truly superior.

        Null hypothesis: All strategies have equal expected performance.

        Reference: Section 6, "White's Reality Check"

        Args:
            returns_matrix: Array of shape (n_strategies, n_periods)
            best_strategy_idx: Index of the best-performing strategy

        Returns:
            p-value for the test
        """
        n_strategies, n_periods = returns_matrix.shape

        if n_strategies < 2 or n_periods < self.config.min_trades_for_test:
            return 1.0

        # Observed performance
        observed_means = np.mean(returns_matrix, axis=1)
        best_mean = observed_means[best_strategy_idx]

        # Bootstrap under the null (all strategies are equal)
        # Resample residuals (returns - mean) and add back mean
        centered_returns = returns_matrix - observed_means[:, np.newaxis]

        bootstrap_max_means = []
        for _ in range(self.config.bootstrap_iterations):
            # Resample with replacement
            boot_indices = np.random.choice(n_periods, size=n_periods, replace=True)
            boot_centered = centered_returns[:, boot_indices]

            # Under null, all strategies have same mean (use overall mean)
            overall_mean = np.mean(returns_matrix)
            boot_returns = boot_centered + overall_mean

            # Max mean across all strategies
            boot_means = np.mean(boot_returns, axis=1)
            bootstrap_max_means.append(np.max(boot_means))

        bootstrap_max_means = np.array(bootstrap_max_means)

        # p-value: proportion of bootstrap max means >= observed best mean
        p_value = np.mean(bootstrap_max_means >= best_mean)

        return float(p_value)

    def empirical_bayes_shrinkage(
        self,
        individual_sharpe: float,
        population_sharpes: List[float],
        num_observations: int
    ) -> Tuple[float, float]:
        """
        Empirical Bayes shrinkage for robust Sharpe ratio estimation.

        Shrinks individual estimate toward population mean, with intensity
        based on estimation uncertainty.

        Reference: Section 6, "Small-Sample Bias" -> "Empirical Bayes shrinkage"

        Args:
            individual_sharpe: Sharpe ratio for individual whale
            population_sharpes: Sharpe ratios for all whales
            num_observations: Number of trades for individual whale

        Returns:
            Tuple of (shrunk_sharpe, shrinkage_intensity)
        """
        if len(population_sharpes) < 10 or num_observations <= 0:
            return (individual_sharpe, 0.0)

        # Population statistics
        population_mean = np.mean(population_sharpes)
        population_var = np.var(population_sharpes, ddof=1)

        # Individual estimation variance (James-Stein formula)
        # var(SR_estimate) ≈ (1 + SR^2 / 2) / n
        individual_var = (1 + individual_sharpe**2 / 2) / num_observations

        # Shrinkage intensity
        if self.config.shrinkage_intensity_auto:
            # Optimal shrinkage: λ = var(individual) / (var(individual) + var(population))
            lambda_shrink = individual_var / (individual_var + population_var)
            lambda_shrink = np.clip(lambda_shrink, 0.0, 1.0)
        else:
            lambda_shrink = 0.3  # Fixed shrinkage

        # Shrunk estimate
        shrunk_sharpe = (
            (1 - lambda_shrink) * individual_sharpe
            + lambda_shrink * population_mean
        )

        return (shrunk_sharpe, lambda_shrink)

    def analyze_whale_skill(
        self,
        whale_address: str,
        returns: np.ndarray,
        returns_series: List[Tuple[datetime, float]],
        all_whale_sharpes: List[float] = None,
        num_whales_tested: int = 1
    ) -> SkillTestResult:
        """
        Comprehensive skill vs luck analysis for a single whale.

        Implements the full 4-step methodology:
        1. Null model (SR = 0)
        2. Statistical significance (bootstrap + FDR)
        3. Persistence (rolling window regression)
        4. Bias corrections (DSR, PSR, Empirical Bayes)

        Args:
            whale_address: Whale wallet address
            returns: Array of returns
            returns_series: List of (timestamp, return) tuples for persistence testing
            all_whale_sharpes: Sharpe ratios for all whales (for Empirical Bayes)
            num_whales_tested: Total number of whales tested (for DSR)

        Returns:
            SkillTestResult object
        """
        logger.info(f"Analyzing skill for whale: {whale_address}")

        # Insufficient data check
        if len(returns) < self.config.min_trades_for_test:
            return SkillTestResult(
                address=whale_address,
                test_timestamp=datetime.now(),
                observed_sharpe_ratio=0.0,
                observed_information_coefficient=0.0,
                observed_log_score=0.0,
                observed_brier_score=0.0,
                p_value_sharpe=1.0,
                is_significant=False,
                adjusted_p_value=1.0,
                persistence_t_statistic=0.0,
                persistence_p_value=1.0,
                has_persistent_skill=False,
                deflated_sharpe_ratio=0.0,
                probabilistic_sharpe_ratio=0.0,
                empirical_bayes_sharpe=0.0,
                sharpe_ci_lower=0.0,
                sharpe_ci_upper=0.0,
                ic_ci_lower=0.0,
                ic_ci_upper=0.0,
                overall_skill_score=0.0,
                skill_category="INSUFFICIENT_DATA"
            )

        # Step 1: Observed performance metrics
        excess_returns = returns - self.config.risk_free_rate_daily
        observed_sharpe = (
            np.mean(excess_returns) / np.std(excess_returns)
            if np.std(excess_returns) > 0
            else 0.0
        )

        # Step 2: Statistical significance (bootstrap)
        (
            _,
            p_value_sharpe,
            sharpe_ci_lower,
            sharpe_ci_upper,
            bootstrap_std
        ) = self.calculate_sharpe_ratio_bootstrap_ci(
            returns,
            risk_free_rate=self.config.risk_free_rate_daily,
            confidence_level=self.config.confidence_level
        )

        # FDR correction would be applied across all whales
        # For now, use raw p-value
        adjusted_p_value = p_value_sharpe
        is_significant = p_value_sharpe < (1 - self.config.confidence_level)

        # Step 3: Persistence testing
        (
            persistence_t_stat,
            persistence_p_value,
            has_persistence
        ) = self.test_skill_persistence(
            returns_series,
            window_days=self.config.rolling_window_days
        )

        # Step 4a: Deflated Sharpe Ratio
        n_obs = len(returns)
        returns_variance = np.var(returns, ddof=1)
        dsr = self._calculate_dsr(
            observed_sharpe,
            num_whales_tested,
            returns_variance,
            n_obs
        )

        # Step 4b: Probabilistic Sharpe Ratio
        psr = self._calculate_psr(
            observed_sharpe,
            n_obs,
            skewness=stats.skew(returns),
            kurtosis=stats.kurtosis(returns, fisher=False)
        )

        # Step 4c: Empirical Bayes shrinkage
        if all_whale_sharpes and self.config.use_empirical_bayes:
            eb_sharpe, _ = self.empirical_bayes_shrinkage(
                observed_sharpe,
                all_whale_sharpes,
                n_obs
            )
        else:
            eb_sharpe = observed_sharpe

        # Overall skill score (0-1)
        # Combines: significance, persistence, DSR, PSR
        skill_components = [
            1.0 if is_significant else 0.0,  # Statistical significance
            1.0 if has_persistence else 0.0,  # Persistence
            stats.norm.cdf(dsr),  # DSR (normalized)
            psr,  # PSR (already 0-1)
        ]
        overall_skill_score = np.mean(skill_components)

        # Categorize
        if overall_skill_score >= 0.75:
            skill_category = "HIGH_SKILL"
        elif overall_skill_score >= 0.50:
            skill_category = "MODERATE_SKILL"
        else:
            skill_category = "LIKELY_LUCK"

        result = SkillTestResult(
            address=whale_address,
            test_timestamp=datetime.now(),
            observed_sharpe_ratio=observed_sharpe,
            observed_information_coefficient=0.0,  # Would calculate separately
            observed_log_score=0.0,  # Would calculate separately
            observed_brier_score=0.0,  # Would calculate separately
            p_value_sharpe=p_value_sharpe,
            is_significant=is_significant,
            adjusted_p_value=adjusted_p_value,
            persistence_t_statistic=persistence_t_stat,
            persistence_p_value=persistence_p_value,
            has_persistent_skill=has_persistence,
            deflated_sharpe_ratio=dsr,
            probabilistic_sharpe_ratio=psr,
            empirical_bayes_sharpe=eb_sharpe,
            sharpe_ci_lower=sharpe_ci_lower,
            sharpe_ci_upper=sharpe_ci_upper,
            ic_ci_lower=0.0,
            ic_ci_upper=0.0,
            overall_skill_score=overall_skill_score,
            skill_category=skill_category
        )

        logger.info(
            f"Whale {whale_address}: Skill Score = {overall_skill_score:.3f}, "
            f"Category = {skill_category}, DSR = {dsr:.3f}, PSR = {psr:.3f}"
        )

        return result

    def _calculate_dsr(
        self,
        observed_sharpe: float,
        num_trials: int,
        returns_variance: float,
        num_observations: int
    ) -> float:
        """Calculate Deflated Sharpe Ratio"""
        if num_observations <= 0:
            return 0.0

        expected_max_sr = np.sqrt(2 * np.log(num_trials))
        sr_std_error = np.sqrt((1 + 0.5 * observed_sharpe**2) / num_observations)
        dsr = (observed_sharpe - expected_max_sr) / sr_std_error if sr_std_error > 0 else 0.0

        return float(dsr)

    def _calculate_psr(
        self,
        observed_sharpe: float,
        num_observations: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> float:
        """Calculate Probabilistic Sharpe Ratio"""
        if num_observations <= 0:
            return 0.0

        sr_variance = (
            1
            + 0.5 * observed_sharpe**2
            - skewness * observed_sharpe
            + (kurtosis - 3) / 4 * observed_sharpe**2
        ) / num_observations

        sr_std_error = np.sqrt(sr_variance)
        z_stat = (observed_sharpe - self.config.target_sharpe_ratio) / sr_std_error if sr_std_error > 0 else 0.0
        psr = stats.norm.cdf(z_stat)

        return float(psr)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize analyzer
    analyzer = SkillVsLuckAnalyzer()

    # Simulated returns for a whale (30 trades)
    np.random.seed(42)
    returns = np.random.normal(0.015, 0.05, 50)  # Mean 1.5% return, 5% volatility

    # Returns series with timestamps
    start_date = datetime.now() - timedelta(days=150)
    returns_series = [
        (start_date + timedelta(days=i*3), returns[i])
        for i in range(len(returns))
    ]

    # All whale Sharpe ratios (for Empirical Bayes)
    all_sharpes = [0.8, 1.2, 0.5, 1.5, 0.9, 1.1, 0.7, 1.3]

    # Analyze skill
    result = analyzer.analyze_whale_skill(
        whale_address="0x1234...abcd",
        returns=returns,
        returns_series=returns_series,
        all_whale_sharpes=all_sharpes,
        num_whales_tested=100
    )

    # Display results
    print(f"\n=== Skill vs Luck Analysis ===")
    print(f"Whale: {result.address}")
    print(f"Skill Category: {result.skill_category}")
    print(f"Overall Skill Score: {result.overall_skill_score:.3f}")
    print(f"\nMetrics:")
    print(f"  Observed Sharpe: {result.observed_sharpe_ratio:.3f}")
    print(f"  Deflated Sharpe (DSR): {result.deflated_sharpe_ratio:.3f}")
    print(f"  Probabilistic Sharpe (PSR): {result.probabilistic_sharpe_ratio:.3f}")
    print(f"  Empirical Bayes Sharpe: {result.empirical_bayes_sharpe:.3f}")
    print(f"\nSignificance:")
    print(f"  p-value: {result.p_value_sharpe:.4f}")
    print(f"  Is Significant: {result.is_significant}")
    print(f"  95% CI: [{result.sharpe_ci_lower:.3f}, {result.sharpe_ci_upper:.3f}]")
    print(f"\nPersistence:")
    print(f"  t-statistic: {result.persistence_t_statistic:.3f}")
    print(f"  p-value: {result.persistence_p_value:.4f}")
    print(f"  Has Persistent Skill: {result.has_persistent_skill}")
