"""
Market Regime Detection System
Identifies market conditions using volatility, momentum, and structural breaks
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""
    BULL = "bull"  # Low volatility, positive trend
    BEAR = "bear"  # High volatility, negative trend
    NEUTRAL = "neutral"  # Normal volatility, no clear trend
    HIGH_VOLATILITY = "high_volatility"  # Extreme volatility
    RANGING = "ranging"  # Low volatility, no trend


class RegimeDetector:
    """
    Detects market regimes using multiple indicators:
    - EWMA volatility with λ=0.94
    - Rolling Sharpe ratios
    - Structural break detection
    - Volume analysis
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.ewma_lambda = self.config['ewma_lambda']
        self.regime_history = []
        self.current_regime = MarketRegime.NEUTRAL

    def _default_config(self) -> Dict:
        """Default configuration for regime detection."""
        return {
            'ewma_lambda': 0.94,  # Decay factor for EWMA
            'lookback_days': 60,  # Days for regime detection
            'vol_percentiles': {
                'low': 25,
                'high': 75,
                'extreme': 90
            },
            'trend_threshold': 0.02,  # 2% trend threshold
            'min_observations': 20,
            'structural_break_confidence': 0.95
        }

    def detect_regime(
        self,
        price_data: np.ndarray,
        volume_data: np.ndarray = None,
        timestamp: datetime = None
    ) -> Dict:
        """
        Detect current market regime from price and volume data.

        Args:
            price_data: Array of historical prices
            volume_data: Optional array of volumes
            timestamp: Current timestamp

        Returns:
            Dictionary with regime classification and indicators
        """
        if len(price_data) < self.config['min_observations']:
            return {
                'regime': MarketRegime.NEUTRAL,
                'confidence': 0.0,
                'message': 'Insufficient data'
            }

        # Calculate returns
        returns = np.diff(np.log(price_data))

        # 1. Calculate EWMA volatility
        ewma_vol = self._calculate_ewma_volatility(returns)
        historical_vol = np.std(returns) * np.sqrt(252)  # Annualized

        # 2. Calculate trend strength
        trend_strength = self._calculate_trend_strength(price_data)

        # 3. Detect structural breaks
        has_break, break_confidence = self._detect_structural_break(returns)

        # 4. Analyze volume (if available)
        volume_regime = self._analyze_volume_regime(volume_data) if volume_data is not None else None

        # 5. Calculate volatility percentile
        vol_percentile = self._calculate_volatility_percentile(ewma_vol, returns)

        # 6. Determine regime
        regime = self._classify_regime(
            ewma_vol,
            historical_vol,
            trend_strength,
            vol_percentile,
            has_break
        )

        # 7. Calculate regime confidence
        confidence = self._calculate_regime_confidence(
            ewma_vol,
            trend_strength,
            break_confidence,
            volume_regime
        )

        # Update regime history
        self.current_regime = regime
        self.regime_history.append({
            'timestamp': timestamp or datetime.utcnow(),
            'regime': regime,
            'confidence': confidence
        })

        return {
            'regime': regime,
            'confidence': confidence,
            'indicators': {
                'ewma_volatility': ewma_vol,
                'historical_volatility': historical_vol,
                'trend_strength': trend_strength,
                'volatility_percentile': vol_percentile,
                'has_structural_break': has_break,
                'break_confidence': break_confidence,
                'volume_regime': volume_regime
            },
            'timestamp': timestamp or datetime.utcnow()
        }

    def _calculate_ewma_volatility(self, returns: np.ndarray) -> float:
        """
        Calculate EWMA volatility with specified lambda.
        Standard RiskMetrics approach with λ=0.94.
        """
        if len(returns) < 2:
            return 0.02  # Default 2% volatility

        lambda_param = self.ewma_lambda
        squared_returns = returns ** 2

        # Calculate weights (exponentially decaying)
        weights = np.array([(1 - lambda_param) * lambda_param ** i
                           for i in range(len(squared_returns) - 1, -1, -1)])

        # Normalize weights
        weights = weights / np.sum(weights)

        # Calculate EWMA variance
        ewma_variance = np.sum(weights * squared_returns)

        # Convert to annualized volatility
        ewma_vol = np.sqrt(ewma_variance * 252)

        return ewma_vol

    def _calculate_trend_strength(self, price_data: np.ndarray) -> float:
        """
        Calculate trend strength using linear regression slope.
        Returns normalized trend strength [-1, 1].
        """
        if len(price_data) < 2:
            return 0.0

        # Fit linear regression
        x = np.arange(len(price_data))
        slope, intercept = np.polyfit(x, np.log(price_data), 1)

        # Annualize the slope
        annualized_slope = slope * 252

        # Normalize to [-1, 1] range
        # Assuming ±50% annual return as max
        normalized_trend = np.clip(annualized_slope / 0.5, -1, 1)

        return normalized_trend

    def _detect_structural_break(self, returns: np.ndarray) -> Tuple[bool, float]:
        """
        Detect structural breaks using Chow test.
        Tests if the return distribution has changed significantly.
        """
        if len(returns) < 40:  # Need sufficient data for split
            return False, 0.0

        # Split data in half
        mid_point = len(returns) // 2
        first_half = returns[:mid_point]
        second_half = returns[mid_point:]

        # Test for mean shift
        t_stat, p_value_mean = stats.ttest_ind(first_half, second_half)

        # Test for variance shift (F-test)
        var_ratio = np.var(second_half, ddof=1) / np.var(first_half, ddof=1)
        f_stat = var_ratio if var_ratio > 1 else 1 / var_ratio
        p_value_var = 1 - stats.f.cdf(f_stat, len(second_half)-1, len(first_half)-1)

        # Combine tests
        has_break = (p_value_mean < 0.05) or (p_value_var < 0.05)
        confidence = 1 - min(p_value_mean, p_value_var)

        return has_break, confidence

    def _analyze_volume_regime(self, volume_data: np.ndarray) -> str:
        """
        Analyze volume patterns to detect regime.
        High volume often indicates regime changes.
        """
        if volume_data is None or len(volume_data) < 10:
            return "normal"

        # Calculate volume metrics
        recent_volume = np.mean(volume_data[-5:])
        historical_volume = np.mean(volume_data[:-5])

        volume_ratio = recent_volume / historical_volume if historical_volume > 0 else 1

        if volume_ratio > 2.0:
            return "extreme_high"
        elif volume_ratio > 1.5:
            return "high"
        elif volume_ratio < 0.5:
            return "low"
        else:
            return "normal"

    def _calculate_volatility_percentile(
        self,
        current_vol: float,
        historical_returns: np.ndarray
    ) -> float:
        """
        Calculate where current volatility sits in historical distribution.
        """
        if len(historical_returns) < 20:
            return 50.0

        # Calculate rolling volatilities
        window = 20
        rolling_vols = []

        for i in range(window, len(historical_returns) + 1):
            window_returns = historical_returns[i-window:i]
            vol = np.std(window_returns) * np.sqrt(252)
            rolling_vols.append(vol)

        if not rolling_vols:
            return 50.0

        # Calculate percentile
        percentile = stats.percentileofscore(rolling_vols, current_vol)

        return percentile

    def _classify_regime(
        self,
        ewma_vol: float,
        historical_vol: float,
        trend_strength: float,
        vol_percentile: float,
        has_structural_break: bool
    ) -> MarketRegime:
        """
        Classify market regime based on indicators.

        Decision tree:
        1. Check for extreme volatility
        2. Check for structural break
        3. Check trend and normal volatility
        """
        # Extreme volatility regime
        if vol_percentile > self.config['vol_percentiles']['extreme']:
            return MarketRegime.HIGH_VOLATILITY

        # Structural break detected - likely regime change
        if has_structural_break and vol_percentile > self.config['vol_percentiles']['high']:
            return MarketRegime.HIGH_VOLATILITY

        # Normal volatility - check trend
        if vol_percentile < self.config['vol_percentiles']['low']:
            # Low volatility
            if abs(trend_strength) < self.config['trend_threshold']:
                return MarketRegime.RANGING
            elif trend_strength > self.config['trend_threshold']:
                return MarketRegime.BULL
            else:
                return MarketRegime.BEAR

        # Medium to high volatility
        if trend_strength > self.config['trend_threshold']:
            return MarketRegime.BULL
        elif trend_strength < -self.config['trend_threshold']:
            return MarketRegime.BEAR
        else:
            return MarketRegime.NEUTRAL

    def _calculate_regime_confidence(
        self,
        ewma_vol: float,
        trend_strength: float,
        break_confidence: float,
        volume_regime: Optional[str]
    ) -> float:
        """
        Calculate confidence in regime classification.
        Higher when multiple indicators agree.
        """
        confidence_factors = []

        # Volatility clarity (extreme values = higher confidence)
        vol_confidence = min(abs(ewma_vol - 0.15) / 0.15, 1.0)
        confidence_factors.append(vol_confidence)

        # Trend clarity
        trend_confidence = min(abs(trend_strength) * 2, 1.0)
        confidence_factors.append(trend_confidence)

        # Structural break confidence
        if break_confidence > 0:
            confidence_factors.append(break_confidence)

        # Volume confirmation
        if volume_regime in ['extreme_high', 'low']:
            confidence_factors.append(0.8)
        elif volume_regime == 'high':
            confidence_factors.append(0.6)

        # Average confidence
        confidence = np.mean(confidence_factors) if confidence_factors else 0.5

        return confidence

    def get_regime_transition_matrix(self) -> np.ndarray:
        """
        Calculate regime transition probabilities from history.
        Returns transition matrix.
        """
        if len(self.regime_history) < 2:
            # Return equal probability matrix
            n_regimes = len(MarketRegime)
            return np.ones((n_regimes, n_regimes)) / n_regimes

        # Count transitions
        regimes = list(MarketRegime)
        n_regimes = len(regimes)
        transition_counts = np.zeros((n_regimes, n_regimes))

        for i in range(1, len(self.regime_history)):
            from_regime = self.regime_history[i-1]['regime']
            to_regime = self.regime_history[i]['regime']

            from_idx = regimes.index(from_regime)
            to_idx = regimes.index(to_regime)

            transition_counts[from_idx, to_idx] += 1

        # Normalize rows to get probabilities
        row_sums = transition_counts.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # Avoid division by zero

        transition_matrix = transition_counts / row_sums

        return transition_matrix

    def predict_next_regime(
        self,
        horizon_days: int = 5
    ) -> Dict:
        """
        Predict most likely regime over next horizon days.
        Uses transition matrix and current indicators.
        """
        transition_matrix = self.get_regime_transition_matrix()
        current_regime_idx = list(MarketRegime).index(self.current_regime)

        # Calculate regime probabilities after n steps
        regime_probs = transition_matrix[current_regime_idx]

        for _ in range(horizon_days - 1):
            regime_probs = regime_probs @ transition_matrix

        # Find most likely regime
        most_likely_idx = np.argmax(regime_probs)
        most_likely_regime = list(MarketRegime)[most_likely_idx]

        return {
            'predicted_regime': most_likely_regime,
            'probability': regime_probs[most_likely_idx],
            'regime_probabilities': {
                regime.value: prob
                for regime, prob in zip(MarketRegime, regime_probs)
            },
            'horizon_days': horizon_days
        }

    def get_regime_trading_parameters(self, regime: MarketRegime) -> Dict:
        """
        Return recommended trading parameters for each regime.
        """
        parameters = {
            MarketRegime.BULL: {
                'position_size_multiplier': 1.2,
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.15,
                'max_positions': 10,
                'preferred_strategy': 'momentum',
                'risk_level': 'moderate'
            },
            MarketRegime.BEAR: {
                'position_size_multiplier': 0.5,
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.08,
                'max_positions': 5,
                'preferred_strategy': 'contrarian',
                'risk_level': 'conservative'
            },
            MarketRegime.NEUTRAL: {
                'position_size_multiplier': 1.0,
                'stop_loss_pct': 0.04,
                'take_profit_pct': 0.10,
                'max_positions': 8,
                'preferred_strategy': 'balanced',
                'risk_level': 'moderate'
            },
            MarketRegime.HIGH_VOLATILITY: {
                'position_size_multiplier': 0.3,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.05,
                'max_positions': 3,
                'preferred_strategy': 'defensive',
                'risk_level': 'very_conservative'
            },
            MarketRegime.RANGING: {
                'position_size_multiplier': 0.8,
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.06,
                'max_positions': 6,
                'preferred_strategy': 'mean_reversion',
                'risk_level': 'conservative'
            }
        }

        return parameters.get(regime, parameters[MarketRegime.NEUTRAL])

    def calculate_regime_adjusted_signals(
        self,
        base_signal_strength: float,
        regime: MarketRegime
    ) -> float:
        """
        Adjust signal strength based on market regime.
        """
        regime_multipliers = {
            MarketRegime.BULL: 1.2,
            MarketRegime.BEAR: 0.6,
            MarketRegime.NEUTRAL: 1.0,
            MarketRegime.HIGH_VOLATILITY: 0.4,
            MarketRegime.RANGING: 0.8
        }

        multiplier = regime_multipliers.get(regime, 1.0)
        adjusted_signal = base_signal_strength * multiplier

        # Clip to [0, 1] range
        return np.clip(adjusted_signal, 0, 1)

    def get_regime_summary(self) -> Dict:
        """
        Get summary of regime detection system status.
        """
        recent_regimes = self.regime_history[-10:] if self.regime_history else []

        regime_counts = {}
        for entry in recent_regimes:
            regime = entry['regime'].value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        return {
            'current_regime': self.current_regime.value,
            'recent_regime_counts': regime_counts,
            'regime_stability': self._calculate_regime_stability(),
            'total_regime_changes': len(self.regime_history) - 1 if self.regime_history else 0,
            'current_parameters': self.get_regime_trading_parameters(self.current_regime)
        }

    def _calculate_regime_stability(self) -> float:
        """
        Calculate regime stability (0-1, higher is more stable).
        Based on frequency of regime changes.
        """
        if len(self.regime_history) < 2:
            return 1.0

        # Count regime changes
        changes = 0
        for i in range(1, len(self.regime_history)):
            if self.regime_history[i]['regime'] != self.regime_history[i-1]['regime']:
                changes += 1

        # Calculate stability (inverse of change rate)
        change_rate = changes / len(self.regime_history)
        stability = 1 - change_rate

        return stability