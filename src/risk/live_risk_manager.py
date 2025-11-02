"""
Live Risk Management System for Polymarket Whale Copy Trading
Implements comprehensive risk controls from research documents
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for position sizing and controls"""
    SAFE = "safe"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetrics:
    """Current risk metrics for the portfolio"""
    total_exposure: Decimal
    max_position_size: Decimal
    current_drawdown: Decimal
    var_95: Decimal  # 95% Value at Risk
    cvar_95: Decimal  # Conditional VaR
    sharpe_ratio: float
    kelly_fraction: float
    risk_level: RiskLevel
    timestamp: datetime


@dataclass
class PositionLimits:
    """Position limits based on risk assessment"""
    max_single_position: Decimal
    max_market_exposure: Decimal
    max_total_exposure: Decimal
    max_correlated_exposure: Decimal
    min_liquidity_required: Decimal


class LiveRiskManager:
    """
    Comprehensive risk management system
    Implements Cornish-Fisher VaR, dynamic Kelly sizing, and circuit breakers
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.positions = {}
        self.trade_history = []
        self.risk_metrics = None
        self.circuit_breaker_triggered = False
        self.last_risk_check = datetime.now()

    def _default_config(self) -> Dict:
        """Default risk management configuration"""
        return {
            # Position limits
            "max_position_pct": 0.05,  # 5% max per position
            "max_total_exposure": 0.75,  # 75% max total exposure
            "max_correlated_exposure": 0.30,  # 30% max in correlated markets

            # Kelly criterion
            "kelly_fraction": 0.25,  # 25% fractional Kelly
            "min_kelly": 0.01,  # 1% minimum position
            "max_kelly": 0.10,  # 10% maximum position

            # Risk metrics thresholds
            "max_daily_loss": 0.10,  # 10% daily loss limit
            "max_drawdown": 0.20,  # 20% max drawdown
            "min_sharpe": 0.5,  # Minimum Sharpe ratio
            "max_var_95": 0.15,  # 15% VaR limit

            # Circuit breakers
            "circuit_breaker_loss": 0.05,  # 5% loss triggers circuit breaker
            "circuit_breaker_duration": 3600,  # 1 hour cooldown
            "max_trades_per_hour": 20,

            # Liquidity requirements
            "min_market_liquidity": 10000,  # $10k minimum
            "max_impact": 0.02,  # 2% max price impact
        }

    def calculate_risk_metrics(self, portfolio_value: Decimal) -> RiskMetrics:
        """Calculate current risk metrics"""
        # Calculate exposure
        total_exposure = sum(abs(p["size"]) for p in self.positions.values())

        # Calculate returns for risk metrics
        returns = self._calculate_returns()

        # Calculate VaR using Cornish-Fisher expansion
        var_95, cvar_95 = self._cornish_fisher_var(returns)

        # Calculate current drawdown
        current_drawdown = self._calculate_drawdown()

        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe(returns)

        # Calculate Kelly fraction
        kelly_fraction = self._calculate_kelly(returns)

        # Determine risk level
        risk_level = self._assess_risk_level(
            var_95, current_drawdown, sharpe_ratio, total_exposure / portfolio_value
        )

        # Create metrics
        metrics = RiskMetrics(
            total_exposure=total_exposure,
            max_position_size=max([abs(p["size"]) for p in self.positions.values()], default=Decimal(0)),
            current_drawdown=current_drawdown,
            var_95=var_95,
            cvar_95=cvar_95,
            sharpe_ratio=sharpe_ratio,
            kelly_fraction=kelly_fraction,
            risk_level=risk_level,
            timestamp=datetime.now()
        )

        self.risk_metrics = metrics
        return metrics

    def _cornish_fisher_var(self, returns: np.ndarray, confidence: float = 0.95) -> Tuple[Decimal, Decimal]:
        """
        Calculate VaR using Cornish-Fisher expansion
        Accounts for skewness and kurtosis in return distribution
        """
        if len(returns) < 30:
            # Not enough data, use simple percentile
            var = np.percentile(returns, (1 - confidence) * 100)
            cvar = np.mean(returns[returns <= var])
            return Decimal(str(abs(var))), Decimal(str(abs(cvar)))

        # Calculate moments
        mean = np.mean(returns)
        std = np.std(returns)
        skew = self._skewness(returns)
        kurt = self._kurtosis(returns)

        # Standard normal quantile
        from scipy.stats import norm
        z = norm.ppf(1 - confidence)

        # Cornish-Fisher expansion
        cf_z = z + (z**2 - 1) * skew / 6 + \
               (z**3 - 3*z) * (kurt - 3) / 24 - \
               (2*z**3 - 5*z) * skew**2 / 36

        # Calculate VaR
        var = mean + cf_z * std

        # Calculate CVaR (expected shortfall)
        threshold = mean + cf_z * std
        tail_returns = returns[returns <= threshold]
        cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var

        return Decimal(str(abs(var))), Decimal(str(abs(cvar)))

    def _skewness(self, returns: np.ndarray) -> float:
        """Calculate skewness of returns"""
        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0
        return np.mean(((returns - mean) / std) ** 3)

    def _kurtosis(self, returns: np.ndarray) -> float:
        """Calculate excess kurtosis of returns"""
        mean = np.mean(returns)
        std = np.std(returns)
        if std == 0:
            return 0
        return np.mean(((returns - mean) / std) ** 4)

    def _calculate_returns(self) -> np.ndarray:
        """Calculate portfolio returns from trade history"""
        if len(self.trade_history) < 2:
            return np.array([])

        returns = []
        for i in range(1, len(self.trade_history)):
            prev_value = self.trade_history[i-1]["portfolio_value"]
            curr_value = self.trade_history[i]["portfolio_value"]
            if prev_value > 0:
                ret = float((curr_value - prev_value) / prev_value)
                returns.append(ret)

        return np.array(returns)

    def _calculate_drawdown(self) -> Decimal:
        """Calculate current drawdown from peak"""
        if not self.trade_history:
            return Decimal(0)

        values = [t["portfolio_value"] for t in self.trade_history]
        peak = max(values)
        current = values[-1]

        if peak > 0:
            return (peak - current) / peak
        return Decimal(0)

    def _calculate_sharpe(self, returns: np.ndarray, risk_free: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free / 252  # Daily risk-free rate
        if np.std(excess_returns) > 0:
            return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return 0.0

    def _calculate_kelly(self, returns: np.ndarray) -> float:
        """
        Calculate Kelly fraction for position sizing
        Implements fractional Kelly with adjustments
        """
        if len(returns) < 10:
            return self.config["kelly_fraction"]

        # Calculate win rate and win/loss ratio
        wins = returns[returns > 0]
        losses = returns[returns <= 0]

        if len(wins) == 0 or len(losses) == 0:
            return self.config["kelly_fraction"]

        win_rate = len(wins) / len(returns)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        if avg_loss == 0:
            return self.config["max_kelly"]

        # Kelly formula: f = p - q/b
        # where p = win probability, q = loss probability, b = win/loss ratio
        b = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / b

        # Apply fractional Kelly
        kelly *= self.config["kelly_fraction"]

        # Apply bounds
        kelly = max(self.config["min_kelly"], min(kelly, self.config["max_kelly"]))

        return kelly

    def _assess_risk_level(
        self,
        var_95: Decimal,
        drawdown: Decimal,
        sharpe: float,
        exposure_ratio: Decimal
    ) -> RiskLevel:
        """Assess current risk level based on multiple factors"""
        score = 0

        # VaR check
        if var_95 > self.config["max_var_95"]:
            score += 3
        elif var_95 > self.config["max_var_95"] * 0.8:
            score += 2
        elif var_95 > self.config["max_var_95"] * 0.6:
            score += 1

        # Drawdown check
        if drawdown > self.config["max_drawdown"] * 0.8:
            score += 3
        elif drawdown > self.config["max_drawdown"] * 0.6:
            score += 2
        elif drawdown > self.config["max_drawdown"] * 0.4:
            score += 1

        # Sharpe check
        if sharpe < self.config["min_sharpe"]:
            score += 2
        elif sharpe < self.config["min_sharpe"] * 1.5:
            score += 1

        # Exposure check
        if exposure_ratio > self.config["max_total_exposure"]:
            score += 3
        elif exposure_ratio > self.config["max_total_exposure"] * 0.8:
            score += 2
        elif exposure_ratio > self.config["max_total_exposure"] * 0.6:
            score += 1

        # Map score to risk level
        if score >= 9:
            return RiskLevel.CRITICAL
        elif score >= 6:
            return RiskLevel.HIGH
        elif score >= 4:
            return RiskLevel.ELEVATED
        elif score >= 2:
            return RiskLevel.NORMAL
        else:
            return RiskLevel.SAFE

    def get_position_limits(self, portfolio_value: Decimal) -> PositionLimits:
        """Get current position limits based on risk assessment"""
        if not self.risk_metrics:
            self.calculate_risk_metrics(portfolio_value)

        # Adjust limits based on risk level
        risk_multiplier = {
            RiskLevel.SAFE: 1.0,
            RiskLevel.NORMAL: 0.8,
            RiskLevel.ELEVATED: 0.6,
            RiskLevel.HIGH: 0.3,
            RiskLevel.CRITICAL: 0.1
        }[self.risk_metrics.risk_level]

        # Calculate limits
        base_position = portfolio_value * Decimal(str(self.config["max_position_pct"]))
        kelly_position = portfolio_value * Decimal(str(self.risk_metrics.kelly_fraction))

        # Use minimum of base and Kelly
        max_position = min(base_position, kelly_position) * Decimal(str(risk_multiplier))

        limits = PositionLimits(
            max_single_position=max_position,
            max_market_exposure=max_position * Decimal(2),  # Allow 2x in same market
            max_total_exposure=portfolio_value * Decimal(str(self.config["max_total_exposure"] * risk_multiplier)),
            max_correlated_exposure=portfolio_value * Decimal(str(self.config["max_correlated_exposure"] * risk_multiplier)),
            min_liquidity_required=Decimal(str(self.config["min_market_liquidity"]))
        )

        return limits

    def check_trade_allowed(
        self,
        market_id: str,
        side: str,
        size: Decimal,
        portfolio_value: Decimal
    ) -> Tuple[bool, str]:
        """Check if a trade is allowed based on risk limits"""
        # Check circuit breaker
        if self.circuit_breaker_triggered:
            return False, "Circuit breaker active"

        # Get position limits
        limits = self.get_position_limits(portfolio_value)

        # Check single position limit
        if size > limits.max_single_position:
            return False, f"Position size {size} exceeds limit {limits.max_single_position}"

        # Check market exposure
        market_exposure = sum(
            abs(p["size"]) for mid, p in self.positions.items()
            if mid == market_id
        )
        if market_exposure + size > limits.max_market_exposure:
            return False, f"Market exposure would exceed limit {limits.max_market_exposure}"

        # Check total exposure
        total_exposure = sum(abs(p["size"]) for p in self.positions.values())
        if total_exposure + size > limits.max_total_exposure:
            return False, f"Total exposure would exceed limit {limits.max_total_exposure}"

        # Check trade frequency
        recent_trades = [
            t for t in self.trade_history
            if t["timestamp"] > datetime.now() - timedelta(hours=1)
        ]
        if len(recent_trades) >= self.config["max_trades_per_hour"]:
            return False, "Trade frequency limit reached"

        return True, "Trade allowed"

    def trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker to halt trading"""
        logger.warning(f"🚨 Circuit breaker triggered: {reason}")
        self.circuit_breaker_triggered = True

        # Schedule reset
        import threading
        def reset_breaker():
            import time
            time.sleep(self.config["circuit_breaker_duration"])
            self.circuit_breaker_triggered = False
            logger.info("Circuit breaker reset")

        threading.Thread(target=reset_breaker, daemon=True).start()

    def update_position(self, market_id: str, side: str, size: Decimal, price: Decimal):
        """Update position tracking"""
        if market_id not in self.positions:
            self.positions[market_id] = {
                "size": Decimal(0),
                "avg_price": Decimal(0),
                "side": side
            }

        position = self.positions[market_id]

        # Update position
        if side == position["side"]:
            # Adding to position
            total_cost = position["size"] * position["avg_price"] + size * price
            position["size"] += size
            position["avg_price"] = total_cost / position["size"] if position["size"] > 0 else Decimal(0)
        else:
            # Reducing position
            position["size"] -= size
            if position["size"] < 0:
                # Flipped position
                position["side"] = side
                position["size"] = abs(position["size"])
                position["avg_price"] = price

        # Remove if closed
        if position["size"] == 0:
            del self.positions[market_id]

    def record_trade(self, trade: Dict):
        """Record trade for risk calculations"""
        self.trade_history.append({
            **trade,
            "timestamp": datetime.now()
        })

        # Keep only recent history (e.g., last 1000 trades)
        if len(self.trade_history) > 1000:
            self.trade_history = self.trade_history[-1000:]

    def get_risk_report(self, portfolio_value: Decimal) -> Dict:
        """Generate comprehensive risk report"""
        metrics = self.calculate_risk_metrics(portfolio_value)
        limits = self.get_position_limits(portfolio_value)

        return {
            "timestamp": datetime.now().isoformat(),
            "risk_metrics": {
                "total_exposure": float(metrics.total_exposure),
                "max_position_size": float(metrics.max_position_size),
                "current_drawdown": float(metrics.current_drawdown),
                "var_95": float(metrics.var_95),
                "cvar_95": float(metrics.cvar_95),
                "sharpe_ratio": metrics.sharpe_ratio,
                "kelly_fraction": metrics.kelly_fraction,
                "risk_level": metrics.risk_level.value
            },
            "position_limits": {
                "max_single_position": float(limits.max_single_position),
                "max_market_exposure": float(limits.max_market_exposure),
                "max_total_exposure": float(limits.max_total_exposure),
                "max_correlated_exposure": float(limits.max_correlated_exposure),
                "min_liquidity_required": float(limits.min_liquidity_required)
            },
            "circuit_breaker_active": self.circuit_breaker_triggered,
            "positions_count": len(self.positions),
            "recent_trades": len([
                t for t in self.trade_history
                if t["timestamp"] > datetime.now() - timedelta(hours=1)
            ])
        }