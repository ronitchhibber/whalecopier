"""
Cornish-Fisher Modified Value at Risk (mVaR) Implementation
Accounts for skewness and kurtosis in non-normal return distributions
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CornishFisherVaR:
    """
    Implements modified VaR using Cornish-Fisher expansion.
    Adjusts for higher moments (skewness and kurtosis) in return distributions.

    Formula:
    mVaR = μ - σ * z_CF

    where z_CF = z_α + (1/6)(z_α² - 1)S + (1/24)(z_α³ - 3z_α)K - (1/36)(2z_α³ - 5z_α)S²

    S = skewness, K = excess kurtosis
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.confidence_levels = self.config['confidence_levels']
        self.lookback_days = self.config['lookback_days']

    def _default_config(self) -> Dict:
        """Default configuration for mVaR calculation."""
        return {
            'confidence_levels': [0.95, 0.99],  # 95% and 99% confidence
            'lookback_days': 252,  # 1 year of trading days
            'min_observations': 30,  # Minimum data points required
            'ewma_lambda': 0.94,  # Decay factor for EWMA
            'stress_scenarios': True,  # Include stress testing
            'monte_carlo_simulations': 10000
        }

    def calculate_mvar(
        self,
        returns: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Calculate modified VaR using Cornish-Fisher expansion.

        Args:
            returns: Array of historical returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)

        Returns:
            Dictionary with mVaR and related statistics
        """
        if len(returns) < self.config['min_observations']:
            logger.warning(f"Insufficient data: {len(returns)} < {self.config['min_observations']}")
            return {
                'mvar': None,
                'var': None,
                'message': 'Insufficient data'
            }

        # Calculate moments
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        skewness = stats.skew(returns)
        excess_kurtosis = stats.kurtosis(returns, fisher=True)

        # Calculate standard VaR
        alpha = 1 - confidence_level
        z_alpha = stats.norm.ppf(alpha)
        standard_var = mean + std * z_alpha

        # Calculate Cornish-Fisher adjustment
        z_cf = self._cornish_fisher_z(z_alpha, skewness, excess_kurtosis)
        modified_var = mean + std * z_cf

        # Calculate Expected Shortfall (CVaR)
        cvar = self._calculate_cvar(returns, modified_var)

        return {
            'mvar': abs(modified_var),  # Return positive value
            'var': abs(standard_var),
            'cvar': abs(cvar),
            'statistics': {
                'mean': mean,
                'std': std,
                'skewness': skewness,
                'excess_kurtosis': excess_kurtosis,
                'z_standard': z_alpha,
                'z_cf': z_cf
            },
            'confidence_level': confidence_level,
            'observations': len(returns),
            'improvement_over_standard': abs(modified_var) / abs(standard_var) if standard_var != 0 else 1.0
        }

    def _cornish_fisher_z(self, z_alpha: float, skewness: float, excess_kurtosis: float) -> float:
        """
        Calculate Cornish-Fisher adjusted z-score.

        CF expansion:
        z_CF = z_α + (1/6)(z_α² - 1)S + (1/24)(z_α³ - 3z_α)K - (1/36)(2z_α³ - 5z_α)S²
        """
        z2 = z_alpha ** 2
        z3 = z_alpha ** 3
        s2 = skewness ** 2

        # Cornish-Fisher expansion terms
        term1 = z_alpha
        term2 = (1/6) * (z2 - 1) * skewness
        term3 = (1/24) * (z3 - 3*z_alpha) * excess_kurtosis
        term4 = -(1/36) * (2*z3 - 5*z_alpha) * s2

        z_cf = term1 + term2 + term3 + term4

        return z_cf

    def _calculate_cvar(self, returns: np.ndarray, var_threshold: float) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).
        Average loss beyond VaR threshold.
        """
        losses_beyond_var = returns[returns < var_threshold]

        if len(losses_beyond_var) == 0:
            return var_threshold

        return np.mean(losses_beyond_var)

    def calculate_portfolio_mvar(
        self,
        portfolio_returns: Dict[str, np.ndarray],
        weights: Dict[str, float],
        correlations: np.ndarray = None,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Calculate portfolio mVaR considering correlations.

        Args:
            portfolio_returns: Dictionary of asset returns
            weights: Dictionary of asset weights
            correlations: Correlation matrix (if None, calculated from returns)
            confidence_level: Confidence level

        Returns:
            Portfolio mVaR and component VaRs
        """
        assets = list(portfolio_returns.keys())
        n_assets = len(assets)

        if n_assets == 0:
            return {'portfolio_mvar': 0, 'message': 'Empty portfolio'}

        # Convert to arrays
        returns_matrix = np.column_stack([portfolio_returns[asset] for asset in assets])
        weight_vector = np.array([weights.get(asset, 0) for asset in assets])

        # Normalize weights
        weight_sum = np.sum(weight_vector)
        if weight_sum > 0:
            weight_vector = weight_vector / weight_sum

        # Calculate portfolio returns
        portfolio_returns_series = returns_matrix @ weight_vector

        # Calculate portfolio mVaR
        portfolio_mvar = self.calculate_mvar(portfolio_returns_series, confidence_level)

        # Calculate component VaRs
        component_vars = {}
        for i, asset in enumerate(assets):
            asset_mvar = self.calculate_mvar(portfolio_returns[asset], confidence_level)
            component_vars[asset] = {
                'mvar': asset_mvar['mvar'],
                'weight': weight_vector[i],
                'contribution': asset_mvar['mvar'] * weight_vector[i] if asset_mvar['mvar'] else 0
            }

        # Calculate diversification benefit
        standalone_mvar = sum(cv['contribution'] for cv in component_vars.values())
        diversification_benefit = 1 - (portfolio_mvar['mvar'] / standalone_mvar) if standalone_mvar > 0 else 0

        return {
            'portfolio_mvar': portfolio_mvar['mvar'],
            'portfolio_cvar': portfolio_mvar.get('cvar'),
            'component_vars': component_vars,
            'diversification_benefit': diversification_benefit,
            'confidence_level': confidence_level,
            'statistics': portfolio_mvar.get('statistics', {})
        }

    def calculate_dynamic_risk_limits(
        self,
        current_pnl: float,
        historical_returns: np.ndarray,
        base_limit: float
    ) -> Dict:
        """
        Calculate dynamic risk limits based on current P&L and market conditions.

        Adjusts limits based on:
        - Current drawdown
        - Recent volatility
        - Streak (winning/losing)
        """
        # Calculate current drawdown
        cum_returns = np.cumprod(1 + historical_returns)
        running_max = np.maximum.accumulate(cum_returns)
        current_drawdown = (cum_returns[-1] - running_max[-1]) / running_max[-1] if len(cum_returns) > 0 else 0

        # Calculate recent volatility (EWMA)
        ewma_vol = self._calculate_ewma_volatility(historical_returns)
        historical_vol = np.std(historical_returns) if len(historical_returns) > 0 else 0.02

        # Calculate winning/losing streak
        streak = self._calculate_streak(historical_returns)

        # Adjust limits
        drawdown_adj = self._drawdown_adjustment(current_drawdown)
        volatility_adj = self._volatility_limit_adjustment(ewma_vol, historical_vol)
        streak_adj = self._streak_adjustment(streak)

        # Combined adjustment
        total_adjustment = drawdown_adj * volatility_adj * streak_adj
        adjusted_limit = base_limit * total_adjustment

        return {
            'base_limit': base_limit,
            'adjusted_limit': adjusted_limit,
            'adjustments': {
                'drawdown': drawdown_adj,
                'volatility': volatility_adj,
                'streak': streak_adj,
                'total': total_adjustment
            },
            'metrics': {
                'current_drawdown': current_drawdown,
                'ewma_volatility': ewma_vol,
                'historical_volatility': historical_vol,
                'streak': streak
            }
        }

    def _calculate_ewma_volatility(self, returns: np.ndarray) -> float:
        """Calculate EWMA volatility with λ=0.94."""
        if len(returns) < 2:
            return 0.02  # Default 2% volatility

        lambda_param = self.config.get('ewma_lambda', 0.94)
        squared_returns = returns ** 2

        # EWMA calculation
        weights = np.array([(1 - lambda_param) * lambda_param ** i
                           for i in range(len(squared_returns) - 1, -1, -1)])
        weights = weights / np.sum(weights)

        ewma_variance = np.sum(weights * squared_returns)
        ewma_vol = np.sqrt(ewma_variance)

        return ewma_vol

    def _calculate_streak(self, returns: np.ndarray) -> int:
        """Calculate current winning/losing streak."""
        if len(returns) == 0:
            return 0

        streak = 0
        last_sign = np.sign(returns[-1])

        for r in reversed(returns):
            if np.sign(r) == last_sign:
                streak += 1
            else:
                break

        return streak if last_sign > 0 else -streak

    def _drawdown_adjustment(self, drawdown: float) -> float:
        """
        Adjust risk limit based on drawdown.
        Reduce risk as drawdown increases.
        """
        drawdown = abs(drawdown)

        if drawdown < 0.05:
            return 1.0  # No adjustment
        elif drawdown < 0.10:
            return 0.75  # 25% reduction
        elif drawdown < 0.20:
            return 0.50  # 50% reduction
        else:
            return 0.25  # 75% reduction

    def _volatility_limit_adjustment(self, current_vol: float, historical_vol: float) -> float:
        """
        Adjust risk limit based on volatility regime.
        Higher vol -> lower limits.
        """
        if historical_vol == 0:
            return 1.0

        vol_ratio = current_vol / historical_vol

        if vol_ratio < 0.8:
            return 1.2  # Low vol, increase limit
        elif vol_ratio < 1.2:
            return 1.0  # Normal vol
        elif vol_ratio < 1.5:
            return 0.75  # Elevated vol
        else:
            return 0.5  # High vol

    def _streak_adjustment(self, streak: int) -> float:
        """
        Adjust based on winning/losing streak.
        Long losing streak -> reduce risk.
        """
        if abs(streak) < 3:
            return 1.0  # No adjustment for short streaks

        if streak > 0:  # Winning streak
            # Slightly increase risk, but cap it
            return min(1.1, 1 + streak * 0.02)
        else:  # Losing streak
            # Reduce risk more aggressively
            return max(0.5, 1 + streak * 0.1)  # streak is negative

    def stress_test_portfolio(
        self,
        portfolio_returns: Dict[str, np.ndarray],
        weights: Dict[str, float],
        scenarios: List[Dict] = None
    ) -> Dict:
        """
        Stress test portfolio under various scenarios.

        Default scenarios:
        - 2008 Financial Crisis
        - COVID-19 Crash
        - High Inflation
        - Liquidity Crisis
        """
        if scenarios is None:
            scenarios = self._default_stress_scenarios()

        results = {}

        for scenario in scenarios:
            scenario_name = scenario['name']
            shock_factor = scenario['shock_factor']
            correlation_increase = scenario.get('correlation_increase', 0.2)

            # Apply shocks to returns
            shocked_returns = {}
            for asset, returns in portfolio_returns.items():
                # Apply multiplicative shock
                shocked = returns * (1 + shock_factor)
                # Add fat tail events
                tail_prob = scenario.get('tail_probability', 0.01)
                tail_magnitude = scenario.get('tail_magnitude', -0.10)

                # Randomly add tail events
                n_tail_events = int(len(returns) * tail_prob)
                if n_tail_events > 0:
                    tail_indices = np.random.choice(len(shocked), n_tail_events, replace=False)
                    shocked[tail_indices] = tail_magnitude

                shocked_returns[asset] = shocked

            # Calculate stressed mVaR
            stressed_mvar = self.calculate_portfolio_mvar(
                shocked_returns,
                weights,
                confidence_level=0.99  # Use 99% for stress testing
            )

            results[scenario_name] = {
                'mvar': stressed_mvar['portfolio_mvar'],
                'cvar': stressed_mvar.get('portfolio_cvar'),
                'shock_factor': shock_factor,
                'scenario': scenario
            }

        return results

    def _default_stress_scenarios(self) -> List[Dict]:
        """Define default stress test scenarios."""
        return [
            {
                'name': '2008 Financial Crisis',
                'shock_factor': -0.40,
                'correlation_increase': 0.30,
                'tail_probability': 0.05,
                'tail_magnitude': -0.15
            },
            {
                'name': 'COVID-19 Crash',
                'shock_factor': -0.35,
                'correlation_increase': 0.25,
                'tail_probability': 0.03,
                'tail_magnitude': -0.12
            },
            {
                'name': 'High Inflation Shock',
                'shock_factor': -0.20,
                'correlation_increase': 0.15,
                'tail_probability': 0.02,
                'tail_magnitude': -0.08
            },
            {
                'name': 'Liquidity Crisis',
                'shock_factor': -0.25,
                'correlation_increase': 0.40,
                'tail_probability': 0.04,
                'tail_magnitude': -0.10
            }
        ]

    def get_risk_metrics_summary(
        self,
        returns: np.ndarray,
        confidence_levels: List[float] = None
    ) -> Dict:
        """
        Calculate comprehensive risk metrics summary.
        """
        if confidence_levels is None:
            confidence_levels = self.confidence_levels

        metrics = {
            'basic_statistics': {
                'mean': np.mean(returns),
                'std': np.std(returns, ddof=1),
                'skewness': stats.skew(returns),
                'kurtosis': stats.kurtosis(returns, fisher=True),
                'min': np.min(returns),
                'max': np.max(returns)
            },
            'var_metrics': {}
        }

        for confidence in confidence_levels:
            var_result = self.calculate_mvar(returns, confidence)
            metrics['var_metrics'][f'{int(confidence*100)}%'] = {
                'mvar': var_result.get('mvar'),
                'standard_var': var_result.get('var'),
                'cvar': var_result.get('cvar'),
                'improvement': var_result.get('improvement_over_standard')
            }

        # Add risk-adjusted returns
        if metrics['basic_statistics']['std'] > 0:
            metrics['risk_adjusted'] = {
                'sharpe_ratio': metrics['basic_statistics']['mean'] / metrics['basic_statistics']['std'] * np.sqrt(252),
                'sortino_ratio': self._calculate_sortino(returns),
                'calmar_ratio': self._calculate_calmar(returns)
            }

        return metrics

    def _calculate_sortino(self, returns: np.ndarray) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return 0.0

        downside_std = np.std(downside_returns, ddof=1)

        if downside_std == 0:
            return 0.0

        return mean_return / downside_std * np.sqrt(252)

    def _calculate_calmar(self, returns: np.ndarray) -> float:
        """Calculate Calmar ratio (return / max drawdown)."""
        if len(returns) < 2:
            return 0.0

        cum_returns = np.cumprod(1 + returns)
        total_return = cum_returns[-1] - 1

        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdown))

        if max_drawdown == 0:
            return 0.0

        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
        return annualized_return / max_drawdown