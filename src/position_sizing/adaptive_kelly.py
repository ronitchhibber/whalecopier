"""
Adaptive Kelly Criterion Position Sizing
Implements dynamic position sizing with multiple adjustment factors
"""

import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AdaptiveKellyCalculator:
    """
    Implements Adaptive Kelly Criterion with multiple adjustment factors:
    - Base Kelly: f* = (p*b - q)/b where p=win_prob, q=1-p, b=win/loss ratio
    - Adjustments: Volatility, Confidence, Diversification, Regime
    - Final allocation capped at 25% per Kelly safety principles
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.kelly_fraction = self.config.get('kelly_fraction', 0.25)  # Use 25% Kelly for safety
        self.max_position_pct = self.config.get('max_position_pct', 0.25)
        self.min_position_pct = self.config.get('min_position_pct', 0.01)

    def _default_config(self) -> Dict:
        """Default configuration for Adaptive Kelly."""
        return {
            'kelly_fraction': 0.25,  # Use fractional Kelly (25% of full Kelly)
            'max_position_pct': 0.25,  # Never exceed 25% of capital
            'min_position_pct': 0.01,  # Minimum 1% position
            'confidence_threshold': 50,  # Min trades for full confidence
            'volatility_lookback_days': 30,
            'regime_lookback_days': 60,
            'diversification_benefit': 0.15  # 15% boost for diversification
        }

    def calculate_position_size(
        self,
        whale_metrics: Dict,
        market_metrics: Dict,
        portfolio_state: Dict,
        capital: float
    ) -> Dict:
        """
        Calculate optimal position size using Adaptive Kelly Criterion.

        Args:
            whale_metrics: Whale performance metrics including win rate, Sharpe, etc.
            market_metrics: Market data including volatility, liquidity
            portfolio_state: Current portfolio positions and risk metrics
            capital: Available capital for trading

        Returns:
            Dictionary with position size and calculation details
        """
        # Step 1: Calculate base Kelly fraction
        base_kelly = self._calculate_base_kelly(whale_metrics, market_metrics)

        # Step 2: Apply adjustments
        vol_adj = self._volatility_adjustment(market_metrics)
        conf_adj = self._confidence_adjustment(whale_metrics)
        div_adj = self._diversification_adjustment(portfolio_state)
        regime_adj = self._regime_adjustment(market_metrics)

        # Step 3: Calculate final Kelly fraction
        adjusted_kelly = base_kelly * vol_adj * conf_adj * div_adj * regime_adj

        # Step 4: Apply fractional Kelly for safety
        safe_kelly = adjusted_kelly * self.kelly_fraction

        # Step 5: Apply position limits
        final_position_pct = np.clip(safe_kelly, self.min_position_pct, self.max_position_pct)

        # Step 6: Calculate dollar amount
        position_size = capital * final_position_pct

        return {
            'position_size_usd': position_size,
            'position_pct': final_position_pct,
            'base_kelly': base_kelly,
            'adjustments': {
                'volatility': vol_adj,
                'confidence': conf_adj,
                'diversification': div_adj,
                'regime': regime_adj
            },
            'adjusted_kelly': adjusted_kelly,
            'safe_kelly': safe_kelly,
            'calculation_timestamp': datetime.utcnow()
        }

    def _calculate_base_kelly(self, whale_metrics: Dict, market_metrics: Dict) -> float:
        """
        Calculate base Kelly fraction using whale's edge.

        Kelly formula: f* = (p*b - q) / b
        where:
        - p = win probability
        - q = 1 - p (loss probability)
        - b = win/loss ratio (average win / average loss)
        """
        # Get adjusted win rate (Bayesian if available, raw otherwise)
        win_rate = whale_metrics.get('adjusted_win_rate') or whale_metrics.get('win_rate', 0.5)

        if win_rate <= 0 or win_rate >= 1:
            return 0.0

        # Calculate average win/loss ratio
        avg_win = whale_metrics.get('avg_win_size', 1.0)
        avg_loss = abs(whale_metrics.get('avg_loss_size', 1.0))

        if avg_loss == 0:
            return 0.0

        win_loss_ratio = avg_win / avg_loss

        # Apply Kelly formula
        p = win_rate
        q = 1 - p
        b = win_loss_ratio

        if b <= 0:
            return 0.0

        kelly = (p * b - q) / b

        # Kelly can be negative if edge is negative - return 0
        return max(0, kelly)

    def _volatility_adjustment(self, market_metrics: Dict) -> float:
        """
        Adjust for market volatility.
        Higher volatility -> smaller position size

        Uses formula: adj = 1 / (1 + volatility_ratio)
        where volatility_ratio = current_vol / historical_vol
        """
        current_vol = market_metrics.get('volatility', 0.02)
        historical_vol = market_metrics.get('historical_volatility', 0.02)

        if historical_vol == 0:
            return 1.0

        vol_ratio = current_vol / historical_vol

        # If volatility is 2x normal, position size is halved
        adjustment = 1 / (1 + max(0, vol_ratio - 1))

        return np.clip(adjustment, 0.3, 1.0)  # Cap between 30% and 100%

    def _confidence_adjustment(self, whale_metrics: Dict) -> float:
        """
        Adjust based on confidence in whale's track record.
        Fewer trades -> lower confidence -> smaller position

        Uses sigmoid function centered at confidence_threshold
        """
        trade_count = whale_metrics.get('trade_count', 0)
        threshold = self.config['confidence_threshold']

        if trade_count == 0:
            return 0.5  # 50% penalty for no track record

        # Sigmoid function: approaches 1 as trade_count increases
        confidence = 1 / (1 + np.exp(-0.1 * (trade_count - threshold)))

        # Scale between 0.5 and 1.0
        return 0.5 + 0.5 * confidence

    def _diversification_adjustment(self, portfolio_state: Dict) -> float:
        """
        Boost allocation for diversifying positions.
        Lower correlation -> higher allocation

        Uses formula: adj = 1 + benefit * (1 - correlation)
        """
        avg_correlation = portfolio_state.get('avg_correlation', 0)
        benefit = self.config['diversification_benefit']

        # If adding uncorrelated asset, get full benefit
        # If adding perfectly correlated asset, get no benefit
        adjustment = 1 + benefit * (1 - abs(avg_correlation))

        return np.clip(adjustment, 1.0, 1.0 + benefit)

    def _regime_adjustment(self, market_metrics: Dict) -> float:
        """
        Adjust based on market regime.
        Bear/high volatility regimes -> smaller positions

        Regimes:
        - Bull (trending up, low vol): 1.0x
        - Neutral: 0.9x
        - Bear (trending down): 0.7x
        - High volatility: 0.5x
        """
        regime = market_metrics.get('regime', 'neutral')

        regime_multipliers = {
            'bull': 1.0,
            'neutral': 0.9,
            'bear': 0.7,
            'high_volatility': 0.5
        }

        return regime_multipliers.get(regime, 0.9)

    def calculate_portfolio_kelly(
        self,
        positions: List[Dict],
        correlations: np.ndarray
    ) -> Dict:
        """
        Calculate Kelly allocation for entire portfolio considering correlations.

        Uses matrix formulation:
        f* = C^(-1) * μ / λ

        where:
        - f* = vector of Kelly fractions
        - C = correlation matrix
        - μ = vector of expected returns
        - λ = risk aversion parameter (usually 1 for full Kelly)
        """
        if not positions or len(positions) == 0:
            return {'allocations': [], 'total_allocation': 0}

        n = len(positions)

        # Build expected return vector
        returns = np.array([p.get('expected_return', 0) for p in positions])

        # Ensure correlation matrix is positive definite
        if correlations.shape != (n, n):
            # If correlations not provided, assume independence
            correlations = np.eye(n)

        # Add small diagonal to ensure positive definite
        correlations = correlations + np.eye(n) * 0.001

        try:
            # Calculate Kelly allocations
            inv_corr = np.linalg.inv(correlations)
            kelly_fractions = inv_corr @ returns

            # Apply fractional Kelly
            kelly_fractions = kelly_fractions * self.kelly_fraction

            # Apply limits
            kelly_fractions = np.clip(kelly_fractions, 0, self.max_position_pct)

            # Normalize if total exceeds 100%
            total = np.sum(kelly_fractions)
            if total > 1.0:
                kelly_fractions = kelly_fractions / total

            return {
                'allocations': kelly_fractions.tolist(),
                'total_allocation': np.sum(kelly_fractions),
                'positions': [
                    {
                        'market_id': positions[i].get('market_id'),
                        'allocation_pct': kelly_fractions[i],
                        'expected_return': returns[i]
                    }
                    for i in range(n)
                ]
            }

        except np.linalg.LinAlgError:
            logger.error("Failed to invert correlation matrix")
            # Fall back to equal weight
            equal_weight = min(1.0 / n, self.max_position_pct)
            return {
                'allocations': [equal_weight] * n,
                'total_allocation': equal_weight * n
            }

    def calculate_dynamic_kelly_fraction(
        self,
        recent_performance: List[float],
        lookback_window: int = 30
    ) -> float:
        """
        Dynamically adjust Kelly fraction based on recent performance.
        If recent drawdown is high, reduce Kelly fraction.

        Uses formula: dynamic_fraction = base_fraction * (1 - drawdown_penalty)
        """
        if not recent_performance or len(recent_performance) < 2:
            return self.kelly_fraction

        # Calculate recent returns
        returns = np.array(recent_performance[-lookback_window:])

        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)

        # Calculate max drawdown
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdown))

        # Apply penalty based on drawdown
        # If drawdown > 10%, start reducing Kelly
        # If drawdown > 25%, use minimum Kelly
        if max_drawdown < 0.10:
            penalty = 0
        elif max_drawdown < 0.25:
            penalty = (max_drawdown - 0.10) / 0.15  # Linear scale
        else:
            penalty = 1.0  # Maximum penalty

        # Reduce Kelly fraction
        dynamic_fraction = self.kelly_fraction * (1 - penalty * 0.75)

        # Never go below 5% of full Kelly
        return max(0.05, dynamic_fraction)

    def get_position_sizing_rules(self) -> Dict:
        """
        Return current position sizing rules and limits.
        Used for monitoring and compliance.
        """
        return {
            'kelly_fraction': self.kelly_fraction,
            'max_position_pct': self.max_position_pct,
            'min_position_pct': self.min_position_pct,
            'adjustments_enabled': {
                'volatility': True,
                'confidence': True,
                'diversification': True,
                'regime': True
            },
            'safety_features': {
                'fractional_kelly': True,
                'position_limits': True,
                'drawdown_reduction': True,
                'correlation_consideration': True
            }
        }