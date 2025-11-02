"""
Adaptive Kelly Position Sizing Engine
Production-grade implementation with volatility and correlation adjustments.

Research Target: Reduce max drawdown from 24.6% to 11.2% (54% improvement)

Formula:
    f_adjusted = 0.5 * f_kelly * k_conf * k_vol * k_corr * k_dd

Components:
- Base Kelly fraction: (p*b - q) / b
- Confidence adjustment (0.4-1.0): Based on whale quality score
- Volatility adjustment (0.5-1.2): EWMA market volatility (λ=0.94)
- Correlation adjustment (0.3-1.0): Portfolio correlation penalty
- Drawdown adjustment (0.2-1.0): Current drawdown protection

Position cap: 8% NAV (hard limit)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    fraction: float  # Position size as fraction of NAV
    dollar_size: float  # Position size in dollars

    # Components breakdown
    base_kelly: float
    adjusted_kelly: float

    # Adjustment factors
    k_conf: float  # Confidence (whale quality)
    k_vol: float   # Volatility
    k_corr: float  # Correlation
    k_dd: float    # Drawdown

    # Metadata
    capped: bool  # Was position capped at max?
    reason: str   # Explanation


class EWMAVolatilityEstimator:
    """
    Exponentially Weighted Moving Average volatility estimator.

    Research parameter: λ = 0.94
    Higher λ = more weight on recent observations
    """

    def __init__(self, lambda_param: float = 0.94):
        """
        Args:
            lambda_param: EWMA decay parameter (0.94 from research)
        """
        self.lambda_param = lambda_param
        self.variance_ewma = None
        self.last_update = None

    def update(self, returns: List[float]) -> None:
        """
        Update EWMA variance estimate with new returns.

        Args:
            returns: List of returns (newest last)
        """
        if not returns:
            return

        # Initialize with sample variance if first time
        if self.variance_ewma is None:
            self.variance_ewma = np.var(returns) if len(returns) > 1 else 0.01

        # Update EWMA variance
        for ret in returns:
            self.variance_ewma = (
                self.lambda_param * self.variance_ewma +
                (1 - self.lambda_param) * ret**2
            )

        self.last_update = datetime.now()

    def get_volatility(self) -> float:
        """Get current volatility estimate (standard deviation)."""
        if self.variance_ewma is None:
            return 0.1  # Default if not initialized

        return np.sqrt(self.variance_ewma)

    def get_variance(self) -> float:
        """Get current variance estimate."""
        return self.variance_ewma if self.variance_ewma is not None else 0.01


class AdaptiveKellyPositionSizer:
    """
    Adaptive Kelly position sizing with multiple adjustment factors.

    Research targets:
    - Max drawdown: 11.2% (vs 24.6% fixed sizing)
    - CAGR reduction: Only 5% vs fixed Kelly
    - Position cap: 8% NAV
    """

    def __init__(
        self,
        max_position_fraction: float = 0.08,  # 8% NAV cap
        min_position_fraction: float = 0.01,  # 1% NAV floor
        use_half_kelly: bool = True,  # Conservative half-Kelly
        ewma_lambda: float = 0.94  # Volatility decay parameter
    ):
        """
        Args:
            max_position_fraction: Maximum position size (8% from research)
            min_position_fraction: Minimum viable position size
            use_half_kelly: Use half-Kelly (more conservative)
            ewma_lambda: EWMA parameter for volatility (0.94 from research)
        """
        self.max_position_fraction = max_position_fraction
        self.min_position_fraction = min_position_fraction
        self.use_half_kelly = use_half_kelly

        # Volatility estimators per market
        self.volatility_estimators: Dict[str, EWMAVolatilityEstimator] = {}
        self.ewma_lambda = ewma_lambda

    def _calculate_base_kelly(
        self,
        win_probability: float,
        win_payoff: float,
        loss_payoff: float = 1.0
    ) -> float:
        """
        Calculate base Kelly fraction.

        Formula: f = (p*b - q) / b
        where:
            p = win probability
            b = win payoff ratio (how much you win per $1 bet)
            q = 1 - p (loss probability)

        Args:
            win_probability: Probability of winning (0-1)
            win_payoff: Win payoff ratio (e.g., 2.0 = double your bet)
            loss_payoff: Loss payoff ratio (typically 1.0 = lose your bet)

        Returns:
            Kelly fraction (can be negative if -EV)
        """
        if win_probability <= 0 or win_probability >= 1:
            return 0.0

        if win_payoff <= 0:
            return 0.0

        p = win_probability
        q = 1 - p
        b = win_payoff

        # Kelly formula: (p*b - q) / b
        kelly_fraction = (p * b - q) / b

        return kelly_fraction

    def _calculate_confidence_adjustment(
        self,
        whale_quality_score: float
    ) -> float:
        """
        Confidence adjustment based on whale quality.

        Formula: k_conf = 0.4 + 0.6 * (WQS / 100)
        Range: 0.4 (low quality) to 1.0 (perfect quality)

        Args:
            whale_quality_score: WQS (0-100)

        Returns:
            Confidence multiplier (0.4-1.0)
        """
        wqs_normalized = max(0, min(100, whale_quality_score)) / 100.0
        k_conf = 0.4 + 0.6 * wqs_normalized

        return k_conf

    def _calculate_volatility_adjustment(
        self,
        market_id: str,
        recent_returns: Optional[List[float]] = None
    ) -> float:
        """
        Volatility adjustment based on EWMA market volatility.

        Formula: k_vol = max(0.5, min(1.2, 1.0 / (1.0 + 5.0 * σ)))
        Range: 0.5 (high vol) to 1.2 (low vol)

        Args:
            market_id: Market identifier
            recent_returns: Recent returns for EWMA update

        Returns:
            Volatility multiplier (0.5-1.2)
        """
        # Get or create volatility estimator for this market
        if market_id not in self.volatility_estimators:
            self.volatility_estimators[market_id] = EWMAVolatilityEstimator(
                lambda_param=self.ewma_lambda
            )

        estimator = self.volatility_estimators[market_id]

        # Update with recent returns if provided
        if recent_returns:
            estimator.update(recent_returns)

        # Get current volatility estimate
        market_vol = estimator.get_volatility()

        # Calculate adjustment factor
        k_vol = 1.0 / (1.0 + 5.0 * market_vol)

        # Clamp to [0.5, 1.2]
        k_vol = max(0.5, min(1.2, k_vol))

        return k_vol

    def _calculate_correlation_adjustment(
        self,
        portfolio_correlation: float
    ) -> float:
        """
        Correlation adjustment to penalize correlated positions.

        Formula: k_corr = max(0.3, 1.0 - ρ²)
        Range: 0.3 (high correlation) to 1.0 (zero correlation)

        Args:
            portfolio_correlation: Correlation with existing portfolio (-1 to 1)

        Returns:
            Correlation multiplier (0.3-1.0)
        """
        # Use squared correlation (0-1)
        corr_squared = portfolio_correlation ** 2

        k_corr = 1.0 - corr_squared

        # Floor at 0.3 (max penalty)
        k_corr = max(0.3, k_corr)

        return k_corr

    def _calculate_drawdown_adjustment(
        self,
        current_drawdown: float
    ) -> float:
        """
        Drawdown adjustment to reduce sizing during drawdowns.

        Formula: k_dd = max(0.2, 1.0 - DD * 3.0)
        Range: 0.2 (severe DD) to 1.0 (no DD)

        Args:
            current_drawdown: Current portfolio drawdown (0-1)

        Returns:
            Drawdown multiplier (0.2-1.0)
        """
        k_dd = 1.0 - current_drawdown * 3.0

        # Floor at 0.2 (max penalty)
        k_dd = max(0.2, k_dd)

        return k_dd

    def calculate_position_size(
        self,
        win_probability: float,
        win_payoff: float,
        whale_quality_score: float,
        market_id: str,
        nav: float,
        recent_returns: Optional[List[float]] = None,
        portfolio_correlation: float = 0.0,
        current_drawdown: float = 0.0
    ) -> PositionSizeResult:
        """
        Calculate adaptive Kelly position size with all adjustments.

        Args:
            win_probability: Estimated win probability (0-1)
            win_payoff: Win payoff ratio
            whale_quality_score: WQS (0-100)
            market_id: Market identifier for volatility tracking
            nav: Net asset value (portfolio size)
            recent_returns: Recent returns for volatility estimation
            portfolio_correlation: Correlation with existing positions
            current_drawdown: Current portfolio drawdown (0-1)

        Returns:
            PositionSizeResult with fraction, dollar size, and breakdown
        """
        # 1. Calculate base Kelly fraction
        base_kelly = self._calculate_base_kelly(win_probability, win_payoff)

        # If negative edge, no position
        if base_kelly <= 0:
            return PositionSizeResult(
                fraction=0.0,
                dollar_size=0.0,
                base_kelly=base_kelly,
                adjusted_kelly=0.0,
                k_conf=1.0,
                k_vol=1.0,
                k_corr=1.0,
                k_dd=1.0,
                capped=False,
                reason="Negative or zero edge (Kelly <= 0)"
            )

        # 2. Calculate adjustment factors
        k_conf = self._calculate_confidence_adjustment(whale_quality_score)
        k_vol = self._calculate_volatility_adjustment(market_id, recent_returns)
        k_corr = self._calculate_correlation_adjustment(portfolio_correlation)
        k_dd = self._calculate_drawdown_adjustment(current_drawdown)

        # 3. Apply half-Kelly if configured
        kelly_multiplier = 0.5 if self.use_half_kelly else 1.0

        # 4. Calculate adjusted fraction
        adjusted_kelly = kelly_multiplier * base_kelly * k_conf * k_vol * k_corr * k_dd

        # 5. Apply position cap
        capped = False
        if adjusted_kelly > self.max_position_fraction:
            adjusted_kelly = self.max_position_fraction
            capped = True

        # 6. Apply position floor (or zero if below)
        if adjusted_kelly < self.min_position_fraction:
            if adjusted_kelly > 0:
                reason = f"Position too small ({adjusted_kelly:.1%} < {self.min_position_fraction:.1%})"
            else:
                reason = "All adjustments resulted in zero position"

            return PositionSizeResult(
                fraction=0.0,
                dollar_size=0.0,
                base_kelly=base_kelly,
                adjusted_kelly=adjusted_kelly,
                k_conf=k_conf,
                k_vol=k_vol,
                k_corr=k_corr,
                k_dd=k_dd,
                capped=False,
                reason=reason
            )

        # 7. Calculate dollar size
        dollar_size = adjusted_kelly * nav

        # Build reason string
        if capped:
            reason = f"Capped at {self.max_position_fraction:.1%} NAV"
        else:
            reason = f"Sized at {adjusted_kelly:.1%} NAV"

        reason += f" (base Kelly: {base_kelly:.1%})"

        return PositionSizeResult(
            fraction=adjusted_kelly,
            dollar_size=dollar_size,
            base_kelly=base_kelly,
            adjusted_kelly=adjusted_kelly,
            k_conf=k_conf,
            k_vol=k_vol,
            k_corr=k_corr,
            k_dd=k_dd,
            capped=capped,
            reason=reason
        )

    def calculate_batch_positions(
        self,
        signals: List[Dict],
        nav: float,
        current_drawdown: float = 0.0
    ) -> List[Tuple[Dict, PositionSizeResult]]:
        """
        Calculate position sizes for multiple signals simultaneously.

        Useful for portfolio construction and rebalancing.

        Args:
            signals: List of signal dicts with keys:
                - win_probability: float
                - win_payoff: float
                - whale_quality_score: float
                - market_id: str
                - recent_returns: List[float] (optional)
                - portfolio_correlation: float (optional)
            nav: Net asset value
            current_drawdown: Current portfolio drawdown

        Returns:
            List of (signal, PositionSizeResult) tuples
        """
        results = []

        for signal in signals:
            result = self.calculate_position_size(
                win_probability=signal['win_probability'],
                win_payoff=signal['win_payoff'],
                whale_quality_score=signal['whale_quality_score'],
                market_id=signal['market_id'],
                nav=nav,
                recent_returns=signal.get('recent_returns'),
                portfolio_correlation=signal.get('portfolio_correlation', 0.0),
                current_drawdown=current_drawdown
            )

            results.append((signal, result))

        return results


def estimate_win_probability_from_odds(
    market_price: float,
    whale_win_rate: float,
    calibration_alpha: float = 0.7
) -> float:
    """
    Estimate true win probability from market price and whale win rate.

    Combines market-implied probability with whale's historical win rate.

    Args:
        market_price: Market price (0-1)
        whale_win_rate: Whale's historical win rate (0-1)
        calibration_alpha: Weight on whale rate (0.7 = 70% whale, 30% market)

    Returns:
        Estimated win probability (0-1)
    """
    # Blend market and whale estimates
    p_est = calibration_alpha * whale_win_rate + (1 - calibration_alpha) * market_price

    # Clamp to valid range
    p_est = max(0.01, min(0.99, p_est))

    return p_est


def calculate_win_payoff(
    market_price: float,
    side: str = 'BUY'
) -> float:
    """
    Calculate win payoff ratio for a prediction market bet.

    Args:
        market_price: Market price (0-1)
        side: 'BUY' or 'SELL'

    Returns:
        Win payoff ratio (how much you win per $1 bet)
    """
    if side == 'BUY':
        # If buying YES at 0.6, you pay $0.60 to win $1.00
        # Payoff = (1.0 - 0.6) / 0.6 = 0.67x your bet
        payoff = (1.0 - market_price) / market_price if market_price > 0 else 0
    else:
        # If selling YES (buying NO) at 0.6, you pay $0.40 to win $1.00
        # Payoff = market_price / (1.0 - market_price) = 1.5x your bet
        payoff = market_price / (1.0 - market_price) if market_price < 1.0 else 0

    return payoff


# Example usage and testing
if __name__ == "__main__":
    print("="*80)
    print("ADAPTIVE KELLY POSITION SIZING DEMO")
    print("="*80)

    # Initialize position sizer
    sizer = AdaptiveKellyPositionSizer(
        max_position_fraction=0.08,  # 8% NAV cap
        use_half_kelly=True,
        ewma_lambda=0.94
    )

    nav = 100000  # $100K portfolio

    print("\n📊 Test Case 1: Elite Whale, Low Volatility, No Correlation")
    print("-"*80)

    result = sizer.calculate_position_size(
        win_probability=0.65,  # 65% win rate
        win_payoff=0.67,  # Buying at 0.6 (payoff = 0.4/0.6 = 0.67)
        whale_quality_score=90,  # Elite whale
        market_id="market_1",
        nav=nav,
        recent_returns=[0.02, 0.01, 0.015, 0.012, 0.018],  # Low vol
        portfolio_correlation=0.0,
        current_drawdown=0.0
    )

    print(f"Position size:         ${result.dollar_size:,.0f} ({result.fraction:.1%} NAV)")
    print(f"Base Kelly:            {result.base_kelly:.1%}")
    print(f"Adjusted Kelly:        {result.adjusted_kelly:.1%}")
    print(f"\nAdjustment Factors:")
    print(f"  Confidence (k_conf): {result.k_conf:.3f}")
    print(f"  Volatility (k_vol):  {result.k_vol:.3f}")
    print(f"  Correlation (k_corr): {result.k_corr:.3f}")
    print(f"  Drawdown (k_dd):     {result.k_dd:.3f}")
    print(f"  Total multiplier:    {result.k_conf * result.k_vol * result.k_corr * result.k_dd:.3f}")
    print(f"\nCapped at max?         {result.capped}")
    print(f"Reason:                {result.reason}")

    print("\n📊 Test Case 2: Mediocre Whale, High Volatility, High Correlation")
    print("-"*80)

    result2 = sizer.calculate_position_size(
        win_probability=0.55,  # Mediocre win rate
        win_payoff=1.0,
        whale_quality_score=60,  # Mid-tier whale
        market_id="market_2",
        nav=nav,
        recent_returns=[0.10, -0.08, 0.12, -0.09, 0.11],  # High vol
        portfolio_correlation=0.7,  # Highly correlated
        current_drawdown=0.0
    )

    print(f"Position size:         ${result2.dollar_size:,.0f} ({result2.fraction:.1%} NAV)")
    print(f"Base Kelly:            {result2.base_kelly:.1%}")
    print(f"Adjusted Kelly:        {result2.adjusted_kelly:.1%}")
    print(f"\nAdjustment Factors:")
    print(f"  Confidence (k_conf): {result2.k_conf:.3f}")
    print(f"  Volatility (k_vol):  {result2.k_vol:.3f}")
    print(f"  Correlation (k_corr): {result2.k_corr:.3f}")
    print(f"  Drawdown (k_dd):     {result2.k_dd:.3f}")
    print(f"  Total multiplier:    {result2.k_conf * result2.k_vol * result2.k_corr * result2.k_dd:.3f}")

    print("\n📊 Test Case 3: During Drawdown")
    print("-"*80)

    result3 = sizer.calculate_position_size(
        win_probability=0.65,
        win_payoff=0.67,
        whale_quality_score=85,
        market_id="market_3",
        nav=nav,
        recent_returns=[0.02, 0.015, 0.018],
        portfolio_correlation=0.1,
        current_drawdown=0.15  # 15% drawdown!
    )

    print(f"Position size:         ${result3.dollar_size:,.0f} ({result3.fraction:.1%} NAV)")
    print(f"Drawdown (k_dd):       {result3.k_dd:.3f} (REDUCED by {(1-result3.k_dd)*100:.0f}%)")
    print(f"Note: Position reduced due to drawdown protection")

    print("\n📊 Test Case 4: Batch Position Sizing")
    print("-"*80)

    signals = [
        {
            'win_probability': 0.65,
            'win_payoff': 0.67,
            'whale_quality_score': 90,
            'market_id': 'market_A',
            'recent_returns': [0.02, 0.01, 0.015],
            'portfolio_correlation': 0.0
        },
        {
            'win_probability': 0.60,
            'win_payoff': 1.0,
            'whale_quality_score': 75,
            'market_id': 'market_B',
            'recent_returns': [0.03, 0.025, 0.02],
            'portfolio_correlation': 0.3
        },
        {
            'win_probability': 0.70,
            'win_payoff': 0.5,
            'whale_quality_score': 95,
            'market_id': 'market_C',
            'recent_returns': [0.015, 0.012, 0.018],
            'portfolio_correlation': 0.1
        }
    ]

    batch_results = sizer.calculate_batch_positions(signals, nav, current_drawdown=0.0)

    total_allocated = 0
    for i, (signal, result) in enumerate(batch_results, 1):
        print(f"\nSignal {i} ({signal['market_id']}):")
        print(f"  Position: ${result.dollar_size:,.0f} ({result.fraction:.1%})")
        print(f"  Multiplier: {result.k_conf * result.k_vol * result.k_corr * result.k_dd:.3f}")
        total_allocated += result.dollar_size

    print(f"\nTotal allocated: ${total_allocated:,.0f} ({total_allocated/nav:.1%} NAV)")

    print("\n" + "="*80)
    print("✅ Adaptive Kelly sizing adjusts for quality, volatility, correlation, drawdown")
    print("✅ Position cap at 8% NAV prevents over-concentration")
    print("✅ Half-Kelly provides conservative growth with reduced variance")
    print("="*80)
