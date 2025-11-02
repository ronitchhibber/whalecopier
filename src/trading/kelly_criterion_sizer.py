"""
Fractional Kelly Criterion Position Sizing
Conservative position sizing to prevent over-leverage
Week 4: Position Management - Research-Backed Implementation
"""

import logging
from decimal import Decimal
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KellyParameters:
    """Parameters for Kelly Criterion calculation"""
    win_rate: Decimal  # Probability of winning (0-1)
    avg_win: Decimal   # Average profit on winning trade
    avg_loss: Decimal  # Average loss on losing trade (positive number)
    kelly_fraction: Decimal = Decimal("0.5")  # Default: 50% (conservative)


@dataclass
class PositionSizeRecommendation:
    """Position sizing recommendation"""
    recommended_size: Decimal
    kelly_fraction: Decimal
    full_kelly_size: Decimal
    edge: Decimal
    win_rate: Decimal
    risk_adjusted: bool
    reason: str


class FractionalKellyCriterion:
    """
    Fractional Kelly Criterion Position Sizer

    Research-backed implementation using 25-50% of optimal Kelly to prevent
    boom-bust cycles and reduce risk of ruin.

    Formula:
        Full Kelly: f* = (edge * p - (1-p)) / edge
        Where: edge = avg_win / avg_loss
               p = win_rate

        Fractional Kelly: f = kelly_fraction * f*
        Where: kelly_fraction ∈ [0.25, 0.50] (conservative)

    Reference: Deep Research Report - Fractional Kelly prevents over-leverage
    """

    def __init__(
        self,
        kelly_fraction: float = 0.5,
        min_position_size: Decimal = Decimal("10"),
        max_position_size: Decimal = Decimal("1000"),
        min_edge: Decimal = Decimal("0.05")  # Minimum 5% edge required
    ):
        """
        Initialize Kelly sizer

        Args:
            kelly_fraction: Fraction of full Kelly to use (0.25-0.50 recommended)
            min_position_size: Minimum position size ($)
            max_position_size: Maximum position size ($)
            min_edge: Minimum edge required to trade (default: 5%)
        """
        if not (0.0 < kelly_fraction <= 1.0):
            raise ValueError(f"Kelly fraction must be in (0, 1], got {kelly_fraction}")

        self.kelly_fraction = Decimal(str(kelly_fraction))
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
        self.min_edge = min_edge

        logger.info(
            f"FractionalKellyCriterion initialized: "
            f"fraction={kelly_fraction}, min=${float(min_position_size)}, "
            f"max=${float(max_position_size)}, min_edge={float(min_edge)*100}%"
        )

    def calculate_position_size(
        self,
        balance: Decimal,
        kelly_params: KellyParameters,
        risk_multiplier: float = 1.0
    ) -> PositionSizeRecommendation:
        """
        Calculate optimal position size using Fractional Kelly Criterion

        Args:
            balance: Current account balance
            kelly_params: Win rate and payoff parameters
            risk_multiplier: Additional risk scaling factor (0.5 = half kelly, 1.0 = full)

        Returns:
            PositionSizeRecommendation with size and rationale
        """
        # Validate inputs
        if balance <= 0:
            return self._zero_size_recommendation(
                kelly_params,
                reason="Zero or negative balance"
            )

        if kelly_params.win_rate <= 0 or kelly_params.win_rate >= 1:
            return self._zero_size_recommendation(
                kelly_params,
                reason=f"Invalid win rate: {float(kelly_params.win_rate)}"
            )

        if kelly_params.avg_loss <= 0:
            return self._zero_size_recommendation(
                kelly_params,
                reason="Average loss must be positive"
            )

        # Calculate edge
        if kelly_params.avg_loss == 0:
            edge = Decimal("0")
        else:
            edge = kelly_params.avg_win / kelly_params.avg_loss

        # Check minimum edge requirement
        if edge < self.min_edge:
            return self._zero_size_recommendation(
                kelly_params,
                reason=f"Insufficient edge: {float(edge)*100:.2f}% < {float(self.min_edge)*100:.2f}%"
            )

        # Calculate Full Kelly
        p = kelly_params.win_rate
        full_kelly = (edge * p - (Decimal("1") - p)) / edge

        # If Full Kelly is negative or zero, don't trade
        if full_kelly <= 0:
            return self._zero_size_recommendation(
                kelly_params,
                reason=f"Negative Kelly: {float(full_kelly):.4f} (no edge)"
            )

        # Apply Kelly fraction (conservative sizing)
        fractional_kelly = full_kelly * self.kelly_fraction * Decimal(str(risk_multiplier))

        # Calculate position size as fraction of balance
        recommended_size = balance * fractional_kelly

        # Apply min/max bounds
        bounded_size = max(self.min_position_size, min(recommended_size, self.max_position_size))

        # Check if size was adjusted by risk constraints
        risk_adjusted = bounded_size != recommended_size

        # Build recommendation
        if risk_adjusted:
            if bounded_size == self.min_position_size:
                reason = f"Kelly size ${float(recommended_size):.2f} below min ${float(self.min_position_size)}"
            else:
                reason = f"Kelly size ${float(recommended_size):.2f} above max ${float(self.max_position_size)}"
        else:
            reason = f"Optimal Fractional Kelly ({float(self.kelly_fraction)*100:.0f}%)"

        logger.info(
            f"Position sizing: balance=${float(balance):.2f}, "
            f"full_kelly={float(full_kelly):.4f}, "
            f"fractional_kelly={float(fractional_kelly):.4f}, "
            f"size=${float(bounded_size):.2f}, edge={float(edge):.2f}"
        )

        return PositionSizeRecommendation(
            recommended_size=bounded_size,
            kelly_fraction=self.kelly_fraction,
            full_kelly_size=balance * full_kelly,
            edge=edge,
            win_rate=p,
            risk_adjusted=risk_adjusted,
            reason=reason
        )

    def calculate_from_historical_performance(
        self,
        balance: Decimal,
        historical_trades: list,
        lookback_days: int = 30,
        risk_multiplier: float = 1.0
    ) -> PositionSizeRecommendation:
        """
        Calculate position size from historical trading performance

        Args:
            balance: Current account balance
            historical_trades: List of past trades with P&L
            lookback_days: Days of history to use
            risk_multiplier: Risk scaling factor

        Returns:
            PositionSizeRecommendation
        """
        if not historical_trades:
            # No history - use conservative default
            return PositionSizeRecommendation(
                recommended_size=self.min_position_size,
                kelly_fraction=self.kelly_fraction,
                full_kelly_size=self.min_position_size,
                edge=Decimal("0"),
                win_rate=Decimal("0.5"),
                risk_adjusted=True,
                reason="No historical data - using minimum size"
            )

        # Calculate win rate
        winning_trades = [t for t in historical_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in historical_trades if t.get('pnl', 0) < 0]

        total_trades = len(historical_trades)
        win_rate = Decimal(str(len(winning_trades) / total_trades)) if total_trades > 0 else Decimal("0.5")

        # Calculate average win/loss
        if winning_trades:
            avg_win = Decimal(str(sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades)))
        else:
            avg_win = Decimal("0")

        if losing_trades:
            avg_loss = Decimal(str(abs(sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades))))
        else:
            avg_loss = Decimal("1")  # Default to avoid division by zero

        # Create parameters
        kelly_params = KellyParameters(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            kelly_fraction=self.kelly_fraction
        )

        return self.calculate_position_size(balance, kelly_params, risk_multiplier)

    def adjust_for_market_conditions(
        self,
        base_recommendation: PositionSizeRecommendation,
        volatility_multiplier: float = 1.0,
        whale_confidence: float = 1.0
    ) -> PositionSizeRecommendation:
        """
        Adjust position size for market conditions

        Args:
            base_recommendation: Base Kelly recommendation
            volatility_multiplier: Reduce size in high volatility (0.5 = halve size)
            whale_confidence: Increase size for high-confidence whales (1.5 = 50% increase)

        Returns:
            Adjusted PositionSizeRecommendation
        """
        # Apply adjustments
        adjustment_factor = Decimal(str(volatility_multiplier * whale_confidence))
        adjusted_size = base_recommendation.recommended_size * adjustment_factor

        # Re-apply bounds
        bounded_size = max(
            self.min_position_size,
            min(adjusted_size, self.max_position_size)
        )

        # Update reason
        adjustments = []
        if volatility_multiplier < 1.0:
            adjustments.append(f"volatility×{volatility_multiplier:.2f}")
        if whale_confidence > 1.0:
            adjustments.append(f"confidence×{whale_confidence:.2f}")

        adjusted_reason = base_recommendation.reason
        if adjustments:
            adjusted_reason += f" (adjusted: {', '.join(adjustments)})"

        return PositionSizeRecommendation(
            recommended_size=bounded_size,
            kelly_fraction=base_recommendation.kelly_fraction,
            full_kelly_size=base_recommendation.full_kelly_size,
            edge=base_recommendation.edge,
            win_rate=base_recommendation.win_rate,
            risk_adjusted=True,
            reason=adjusted_reason
        )

    def _zero_size_recommendation(
        self,
        kelly_params: KellyParameters,
        reason: str
    ) -> PositionSizeRecommendation:
        """Return a zero-size recommendation with reason"""
        return PositionSizeRecommendation(
            recommended_size=Decimal("0"),
            kelly_fraction=self.kelly_fraction,
            full_kelly_size=Decimal("0"),
            edge=Decimal("0"),
            win_rate=kelly_params.win_rate,
            risk_adjusted=True,
            reason=reason
        )


# ==================== Example Usage ====================

def main():
    """Example usage of FractionalKellyCriterion"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize Kelly sizer with 50% fraction (conservative)
    kelly_sizer = FractionalKellyCriterion(
        kelly_fraction=0.5,  # Use 50% of optimal Kelly
        min_position_size=Decimal("10"),
        max_position_size=Decimal("1000")
    )

    # Example 1: Calculate from known parameters
    balance = Decimal("5000")
    params = KellyParameters(
        win_rate=Decimal("0.60"),  # 60% win rate
        avg_win=Decimal("50"),      # $50 avg profit
        avg_loss=Decimal("30"),     # $30 avg loss
        kelly_fraction=Decimal("0.5")
    )

    recommendation = kelly_sizer.calculate_position_size(balance, params)

    print(f"\n=== Example 1: Direct Calculation ===")
    print(f"Balance: ${float(balance):.2f}")
    print(f"Win Rate: {float(params.win_rate)*100:.1f}%")
    print(f"Edge: {float(recommendation.edge):.2f} ({float(params.avg_win):.2f} / {float(params.avg_loss):.2f})")
    print(f"Full Kelly Size: ${float(recommendation.full_kelly_size):.2f}")
    print(f"Fractional Kelly Size ({float(recommendation.kelly_fraction)*100:.0f}%): ${float(recommendation.recommended_size):.2f}")
    print(f"Reason: {recommendation.reason}")

    # Example 2: Adjust for market conditions
    print(f"\n=== Example 2: Market Adjustments ===")

    # High volatility - reduce size
    adjusted = kelly_sizer.adjust_for_market_conditions(
        recommendation,
        volatility_multiplier=0.5,  # Halve size due to volatility
        whale_confidence=1.2         # 20% increase for high-confidence whale
    )

    print(f"Original Size: ${float(recommendation.recommended_size):.2f}")
    print(f"Adjusted Size (volatility=0.5, confidence=1.2): ${float(adjusted.recommended_size):.2f}")
    print(f"Reason: {adjusted.reason}")

    # Example 3: Insufficient edge
    print(f"\n=== Example 3: No Edge ===")

    no_edge_params = KellyParameters(
        win_rate=Decimal("0.45"),  # 45% win rate
        avg_win=Decimal("10"),
        avg_loss=Decimal("10"),     # No edge (1:1 payoff)
        kelly_fraction=Decimal("0.5")
    )

    no_edge_rec = kelly_sizer.calculate_position_size(balance, no_edge_params)
    print(f"Win Rate: {float(no_edge_params.win_rate)*100:.1f}%")
    print(f"Edge: {float(no_edge_rec.edge):.2f}")
    print(f"Recommended Size: ${float(no_edge_rec.recommended_size):.2f}")
    print(f"Reason: {no_edge_rec.reason}")


if __name__ == "__main__":
    main()
