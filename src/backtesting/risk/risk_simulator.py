"""
Risk Management Simulator for Backtesting
Implements Cornish-Fisher mVaR and comprehensive risk controls
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from scipy import stats
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Current risk metrics for portfolio."""
    total_exposure: float
    net_exposure: float
    gross_exposure: float
    var_95: float
    cvar_95: float
    cornish_fisher_var: float
    max_loss_today: float
    correlation_risk: float
    concentration_risk: float
    liquidity_risk: float
    regime_risk: float
    timestamp: datetime


@dataclass
class RiskLimits:
    """Risk limits for portfolio."""
    max_position_size: float
    max_total_exposure: float
    max_var_95: float
    max_daily_loss: float
    max_correlation: float
    max_concentration: float
    min_liquidity_ratio: float
    stop_loss_pct: float
    circuit_breaker_threshold: float


class RiskSimulator:
    """
    Comprehensive risk management simulator implementing:
    - Cornish-Fisher modified VaR
    - Multi-factor risk model
    - Dynamic risk limits
    - Circuit breakers
    - Stress testing
    """

    def __init__(self, config: Dict = None):
        """Initialize risk simulator."""
        self.config = config or self._default_config()

        # Risk tracking
        self.current_positions = {}
        self.position_history = []
        self.risk_metrics_history = []

        # Returns tracking for VaR
        self.returns_window = deque(maxlen=self.config['lookback_days'])
        self.high_frequency_returns = deque(maxlen=1000)  # For intraday VaR

        # Risk limits
        self.risk_limits = self._initialize_risk_limits()
        self.breached_limits = set()

        # Market regime
        self.current_regime = 'normal'
        self.regime_volatility = 0.01

        # Correlation matrix
        self.correlation_matrix = {}
        self.correlation_lookback = deque(maxlen=self.config['correlation_window'])

        # Circuit breaker state
        self.circuit_breaker_triggered = False
        self.circuit_breaker_until = None
        self.daily_loss = 0
        self.daily_loss_reset = None

    def _default_config(self) -> Dict:
        """Default risk configuration."""
        return {
            'lookback_days': 252,
            'correlation_window': 60,
            'confidence_levels': [0.95, 0.99],
            'ewma_lambda': 0.94,
            'min_observations': 30,
            'stress_scenarios': [
                {'name': 'market_crash', 'probability': 0.05, 'impact': -0.20},
                {'name': 'flash_crash', 'probability': 0.01, 'impact': -0.10},
                {'name': 'whale_dump', 'probability': 0.10, 'impact': -0.05}
            ],
            'circuit_breaker': {
                'daily_loss_threshold': 0.05,  # 5% daily loss triggers breaker
                'cooldown_minutes': 60,
                'position_reduction': 0.5  # Reduce positions by 50%
            },
            'risk_limits': {
                'max_position_size_pct': 0.25,
                'max_total_exposure_pct': 0.95,
                'max_var_95_pct': 0.02,
                'max_daily_loss_pct': 0.05,
                'max_correlation': 0.6,
                'max_concentration_pct': 0.3,
                'min_liquidity_ratio': 2.0,
                'stop_loss_pct': 0.05
            }
        }

    def _initialize_risk_limits(self) -> RiskLimits:
        """Initialize risk limits from config."""
        limits_config = self.config['risk_limits']

        return RiskLimits(
            max_position_size=limits_config['max_position_size_pct'],
            max_total_exposure=limits_config['max_total_exposure_pct'],
            max_var_95=limits_config['max_var_95_pct'],
            max_daily_loss=limits_config['max_daily_loss_pct'],
            max_correlation=limits_config['max_correlation'],
            max_concentration=limits_config['max_concentration_pct'],
            min_liquidity_ratio=limits_config['min_liquidity_ratio'],
            stop_loss_pct=limits_config['stop_loss_pct'],
            circuit_breaker_threshold=self.config['circuit_breaker']['daily_loss_threshold']
        )

    def update_positions(
        self,
        positions: Dict[str, float],
        prices: Dict[str, float],
        timestamp: datetime
    ):
        """
        Update current positions and calculate risk metrics.

        Args:
            positions: Current positions by market
            prices: Current prices by market
            timestamp: Current time
        """
        # Calculate position values
        position_values = {}
        for market_id, position in positions.items():
            if market_id in prices:
                position_values[market_id] = position * prices[market_id]

        # Update tracking
        self.current_positions = position_values
        self.position_history.append({
            'timestamp': timestamp,
            'positions': position_values.copy(),
            'prices': prices.copy()
        })

        # Calculate returns if we have history
        if len(self.position_history) > 1:
            prev_value = sum(self.position_history[-2]['positions'].values())
            curr_value = sum(position_values.values())

            if prev_value != 0:
                ret = (curr_value - prev_value) / abs(prev_value)
                self.returns_window.append(ret)
                self.high_frequency_returns.append(ret)

                # Update daily loss tracking
                self._update_daily_loss(ret, timestamp)

        # Calculate current risk metrics
        metrics = self._calculate_risk_metrics(timestamp)
        self.risk_metrics_history.append(metrics)

        # Check risk limits
        self._check_risk_limits(metrics)

    def _calculate_risk_metrics(self, timestamp: datetime) -> RiskMetrics:
        """Calculate comprehensive risk metrics."""
        # Exposure metrics
        long_exposure = sum(v for v in self.current_positions.values() if v > 0)
        short_exposure = abs(sum(v for v in self.current_positions.values() if v < 0))
        total_exposure = sum(abs(v) for v in self.current_positions.values())
        net_exposure = long_exposure - short_exposure

        # VaR calculations
        var_95 = self._calculate_var(0.95)
        cvar_95 = self._calculate_cvar(0.95)
        cf_var = self._calculate_cornish_fisher_var(0.95)

        # Concentration risk
        concentration = self._calculate_concentration_risk()

        # Correlation risk
        correlation = self._calculate_correlation_risk()

        # Liquidity risk
        liquidity = self._calculate_liquidity_risk()

        # Regime risk adjustment
        regime_risk = self._calculate_regime_risk()

        return RiskMetrics(
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            gross_exposure=long_exposure + short_exposure,
            var_95=var_95,
            cvar_95=cvar_95,
            cornish_fisher_var=cf_var,
            max_loss_today=self.daily_loss,
            correlation_risk=correlation,
            concentration_risk=concentration,
            liquidity_risk=liquidity,
            regime_risk=regime_risk,
            timestamp=timestamp
        )

    def _calculate_var(self, confidence: float) -> float:
        """Calculate Value at Risk."""
        if len(self.returns_window) < self.config['min_observations']:
            return 0.0

        returns = np.array(self.returns_window)
        var = np.percentile(returns, (1 - confidence) * 100)

        # Scale by current exposure
        total_exposure = sum(abs(v) for v in self.current_positions.values())
        return abs(var) * total_exposure

    def _calculate_cvar(self, confidence: float) -> float:
        """Calculate Conditional VaR (Expected Shortfall)."""
        if len(self.returns_window) < self.config['min_observations']:
            return 0.0

        returns = np.array(self.returns_window)
        var_threshold = np.percentile(returns, (1 - confidence) * 100)

        # Get returns worse than VaR
        tail_returns = returns[returns <= var_threshold]

        if len(tail_returns) == 0:
            return abs(var_threshold)

        cvar = np.mean(tail_returns)

        # Scale by exposure
        total_exposure = sum(abs(v) for v in self.current_positions.values())
        return abs(cvar) * total_exposure

    def _calculate_cornish_fisher_var(self, confidence: float) -> float:
        """
        Calculate Cornish-Fisher modified VaR.

        Adjusts for skewness and kurtosis in return distribution.
        Formula from research: z_CF = z_α + adjustments for higher moments
        """
        if len(self.returns_window) < self.config['min_observations']:
            return 0.0

        returns = np.array(self.returns_window)

        # Calculate moments
        mean = np.mean(returns)
        std = np.std(returns)
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns, fisher=True)  # Excess kurtosis

        # Standard normal quantile
        z_alpha = stats.norm.ppf(1 - confidence)

        # Cornish-Fisher expansion
        z_cf = (z_alpha +
                (z_alpha**2 - 1) * skewness / 6 +
                (z_alpha**3 - 3*z_alpha) * kurtosis / 24 -
                (2*z_alpha**3 - 5*z_alpha) * skewness**2 / 36)

        # Calculate CF-VaR
        cf_var = mean + z_cf * std

        # Scale by exposure
        total_exposure = sum(abs(v) for v in self.current_positions.values())
        return abs(cf_var) * total_exposure

    def _calculate_concentration_risk(self) -> float:
        """Calculate concentration risk (Herfindahl index)."""
        if not self.current_positions:
            return 0.0

        total_exposure = sum(abs(v) for v in self.current_positions.values())
        if total_exposure == 0:
            return 0.0

        # Herfindahl-Hirschman Index
        hhi = sum((abs(v) / total_exposure) ** 2 for v in self.current_positions.values())

        # Normalize to [0, 1]
        # HHI ranges from 1/n (perfect diversification) to 1 (single position)
        n = len(self.current_positions)
        if n > 1:
            min_hhi = 1 / n
            normalized_hhi = (hhi - min_hhi) / (1 - min_hhi)
        else:
            normalized_hhi = 1.0

        return normalized_hhi

    def _calculate_correlation_risk(self) -> float:
        """Calculate portfolio correlation risk."""
        if len(self.position_history) < 10:
            return 0.0

        # Build returns matrix for positions
        markets = list(self.current_positions.keys())
        if len(markets) < 2:
            return 0.0

        # Get returns for each market
        returns_matrix = []
        for market in markets:
            market_returns = []
            for i in range(1, min(60, len(self.position_history))):
                prev_price = self.position_history[i-1]['prices'].get(market, 0)
                curr_price = self.position_history[i]['prices'].get(market, 0)
                if prev_price != 0:
                    ret = (curr_price - prev_price) / prev_price
                else:
                    ret = 0
                market_returns.append(ret)
            returns_matrix.append(market_returns)

        # Calculate correlation matrix
        if len(returns_matrix) > 1 and len(returns_matrix[0]) > 1:
            corr_matrix = np.corrcoef(returns_matrix)

            # Get maximum pairwise correlation (excluding diagonal)
            np.fill_diagonal(corr_matrix, 0)
            max_correlation = np.max(np.abs(corr_matrix))

            return max_correlation

        return 0.0

    def _calculate_liquidity_risk(self) -> float:
        """Calculate liquidity risk based on position sizes."""
        # Simplified liquidity risk based on position concentration
        if not self.current_positions:
            return 0.0

        # Assume liquidity decreases with position size
        total_exposure = sum(abs(v) for v in self.current_positions.values())

        # Liquidity penalty increases non-linearly with size
        liquidity_penalty = min(1.0, (total_exposure / 100000) ** 2)

        return liquidity_penalty

    def _calculate_regime_risk(self) -> float:
        """Calculate risk adjustment based on market regime."""
        # Use EWMA volatility to detect regime
        if len(self.high_frequency_returns) < 20:
            return 1.0

        returns = list(self.high_frequency_returns)[-100:]

        # EWMA volatility
        ewma_var = 0
        lambda_param = self.config['ewma_lambda']

        for ret in returns:
            ewma_var = lambda_param * ewma_var + (1 - lambda_param) * ret**2

        ewma_vol = np.sqrt(ewma_var)

        # Determine regime
        if ewma_vol < 0.01:
            self.current_regime = 'low_volatility'
            return 0.8
        elif ewma_vol < 0.03:
            self.current_regime = 'normal'
            return 1.0
        elif ewma_vol < 0.05:
            self.current_regime = 'high_volatility'
            return 1.5
        else:
            self.current_regime = 'extreme'
            return 2.0

    def _update_daily_loss(self, ret: float, timestamp: datetime):
        """Update daily loss tracking for circuit breaker."""
        # Reset daily loss if new day
        if self.daily_loss_reset is None or timestamp.date() > self.daily_loss_reset:
            self.daily_loss = 0
            self.daily_loss_reset = timestamp.date()

        # Accumulate loss (negative returns)
        if ret < 0:
            self.daily_loss += abs(ret)

    def _check_risk_limits(self, metrics: RiskMetrics):
        """Check if any risk limits are breached."""
        self.breached_limits.clear()

        # Get total capital (simplified - would come from portfolio)
        total_capital = 100000  # This should be passed in

        # Check exposure limits
        if metrics.total_exposure > total_capital * self.risk_limits.max_total_exposure:
            self.breached_limits.add('max_exposure')
            logger.warning(f"Max exposure limit breached: {metrics.total_exposure}")

        # Check VaR limit
        if metrics.cornish_fisher_var > total_capital * self.risk_limits.max_var_95:
            self.breached_limits.add('max_var')
            logger.warning(f"VaR limit breached: {metrics.cornish_fisher_var}")

        # Check daily loss circuit breaker
        if self.daily_loss > self.risk_limits.circuit_breaker_threshold:
            self._trigger_circuit_breaker(metrics.timestamp)

        # Check concentration
        if metrics.concentration_risk > self.risk_limits.max_concentration:
            self.breached_limits.add('concentration')
            logger.warning(f"Concentration limit breached: {metrics.concentration_risk}")

        # Check correlation
        if metrics.correlation_risk > self.risk_limits.max_correlation:
            self.breached_limits.add('correlation')
            logger.warning(f"Correlation limit breached: {metrics.correlation_risk}")

    def _trigger_circuit_breaker(self, timestamp: datetime):
        """Trigger circuit breaker to halt trading."""
        if not self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_until = timestamp + timedelta(
                minutes=self.config['circuit_breaker']['cooldown_minutes']
            )
            logger.critical(f"CIRCUIT BREAKER TRIGGERED! Trading halted until {self.circuit_breaker_until}")

    def should_accept_trade(
        self,
        market_id: str,
        side: str,
        size: float,
        price: float
    ) -> Tuple[bool, str]:
        """
        Check if a trade should be accepted based on risk limits.

        Returns:
            (accepted, reason)
        """
        # Check circuit breaker
        if self.circuit_breaker_triggered:
            if datetime.utcnow() < self.circuit_breaker_until:
                return False, "Circuit breaker active"
            else:
                self.circuit_breaker_triggered = False

        # Check position size limit
        trade_value = size * price
        total_capital = 100000  # Should be passed in

        if trade_value > total_capital * self.risk_limits.max_position_size:
            return False, f"Position too large: {trade_value}"

        # Simulate new position
        new_positions = self.current_positions.copy()
        if side == 'buy':
            new_positions[market_id] = new_positions.get(market_id, 0) + trade_value
        else:
            new_positions[market_id] = new_positions.get(market_id, 0) - trade_value

        # Check new total exposure
        new_exposure = sum(abs(v) for v in new_positions.values())
        if new_exposure > total_capital * self.risk_limits.max_total_exposure:
            return False, f"Would exceed max exposure: {new_exposure}"

        # Check concentration with new position
        new_concentration = abs(new_positions[market_id]) / new_exposure if new_exposure > 0 else 0
        if new_concentration > self.risk_limits.max_concentration:
            return False, f"Would exceed concentration limit: {new_concentration}"

        return True, "Trade accepted"

    def calculate_position_size_adjustment(
        self,
        base_size: float,
        confidence: float
    ) -> float:
        """
        Adjust position size based on current risk metrics.

        Args:
            base_size: Base position size
            confidence: Signal confidence (0-100)

        Returns:
            Adjusted position size
        """
        # Start with base size
        adjusted_size = base_size

        # Adjust for regime
        regime_multiplier = {
            'low_volatility': 1.2,
            'normal': 1.0,
            'high_volatility': 0.6,
            'extreme': 0.3
        }.get(self.current_regime, 1.0)

        adjusted_size *= regime_multiplier

        # Adjust for current VaR utilization
        if len(self.risk_metrics_history) > 0:
            latest_metrics = self.risk_metrics_history[-1]
            total_capital = 100000  # Should be passed in

            var_utilization = latest_metrics.cornish_fisher_var / (total_capital * self.risk_limits.max_var_95)

            if var_utilization > 0.8:
                # Reduce size if approaching VaR limit
                adjusted_size *= (1 - var_utilization) / 0.2

            # Adjust for concentration
            if latest_metrics.concentration_risk > 0.5:
                adjusted_size *= (1 - latest_metrics.concentration_risk)

        # Adjust for confidence
        confidence_multiplier = 0.5 + (confidence / 100) * 0.5  # 50% to 100% of size
        adjusted_size *= confidence_multiplier

        # Apply circuit breaker reduction if recently triggered
        if self.daily_loss > self.risk_limits.circuit_breaker_threshold * 0.5:
            adjusted_size *= self.config['circuit_breaker']['position_reduction']

        return max(0, adjusted_size)

    def run_stress_test(
        self,
        scenarios: List[Dict] = None
    ) -> Dict:
        """
        Run stress test scenarios on current portfolio.

        Returns:
            Stress test results
        """
        if scenarios is None:
            scenarios = self.config['stress_scenarios']

        results = {}
        current_value = sum(self.current_positions.values())

        for scenario in scenarios:
            scenario_name = scenario['name']
            impact = scenario['impact']
            probability = scenario.get('probability', 0.01)

            # Apply scenario shock
            stressed_value = current_value * (1 + impact)
            loss = current_value - stressed_value

            # Calculate stressed VaR
            stressed_var = abs(loss) * probability

            results[scenario_name] = {
                'impact': impact,
                'probability': probability,
                'potential_loss': loss,
                'stressed_var': stressed_var,
                'survival': loss < current_value * 0.5  # Survive if loss < 50%
            }

        return results

    def get_risk_dashboard(self) -> Dict:
        """Get current risk dashboard."""
        if not self.risk_metrics_history:
            return {}

        latest = self.risk_metrics_history[-1]
        total_capital = 100000  # Should be passed in

        return {
            'exposures': {
                'total': latest.total_exposure,
                'net': latest.net_exposure,
                'gross': latest.gross_exposure,
                'utilization': latest.total_exposure / total_capital
            },
            'risk_metrics': {
                'var_95': latest.var_95,
                'cvar_95': latest.cvar_95,
                'cornish_fisher_var': latest.cornish_fisher_var,
                'daily_loss': self.daily_loss
            },
            'risk_factors': {
                'concentration': latest.concentration_risk,
                'correlation': latest.correlation_risk,
                'liquidity': latest.liquidity_risk,
                'regime': self.current_regime,
                'regime_risk': latest.regime_risk
            },
            'limits': {
                'breached': list(self.breached_limits),
                'circuit_breaker': self.circuit_breaker_triggered,
                'var_utilization': latest.cornish_fisher_var / (total_capital * self.risk_limits.max_var_95)
            },
            'stress_test': self.run_stress_test() if len(self.current_positions) > 0 else {}
        }