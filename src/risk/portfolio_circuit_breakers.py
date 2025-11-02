"""
Portfolio-Level Circuit Breakers for Risk Management
Week 5: Risk Management Framework - Circuit Breakers
Implements multi-tier protection: HALT, REDUCE, PAUSE
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Circuit Breaker States ====================

class CircuitBreakerState(Enum):
    """Circuit breaker operational states"""
    NORMAL = "NORMAL"           # Normal operations
    REDUCE = "REDUCE"           # Reduce position sizes by 50%
    PAUSE = "PAUSE"             # Pause trading temporarily
    HALT = "HALT"               # Halt all trading
    EMERGENCY = "EMERGENCY"     # Emergency shutdown


class CircuitBreakerTrigger(Enum):
    """Reasons for circuit breaker activation"""
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    WHALE_LOSS_LIMIT = "WHALE_LOSS_LIMIT"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class CircuitBreakerLimits:
    """Configuration limits for circuit breakers"""
    # Daily loss limit (HALT)
    daily_loss_limit: Decimal = Decimal("500")

    # Max drawdown (REDUCE)
    max_drawdown_pct: Decimal = Decimal("0.10")  # 10%

    # Consecutive losses (PAUSE)
    max_consecutive_losses: int = 5
    pause_duration_minutes: int = 60

    # Per-whale loss limit
    whale_daily_loss_limit: Decimal = Decimal("200")

    # Position size reduction factor when in REDUCE state
    reduce_factor: Decimal = Decimal("0.50")  # 50% reduction


@dataclass
class CircuitBreakerEvent:
    """Record of a circuit breaker activation"""
    trigger: CircuitBreakerTrigger
    state: CircuitBreakerState
    timestamp: datetime
    reason: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class TradingMetrics:
    """Current trading performance metrics"""
    daily_pnl: Decimal
    portfolio_value: Decimal
    peak_value: Decimal
    consecutive_losses: int
    whale_daily_losses: Dict[str, Decimal]
    last_loss_timestamp: Optional[datetime] = None


# ==================== Circuit Breaker Manager ====================

class PortfolioCircuitBreaker:
    """
    Portfolio-Level Circuit Breaker System

    Implements three-tier protection:
    - HALT: Stop all trading (daily loss limit exceeded)
    - REDUCE: Cut position sizes by 50% (max drawdown hit)
    - PAUSE: Temporary trading pause (consecutive losses)

    Research-backed thresholds prevent catastrophic losses
    while allowing controlled recovery.
    """

    def __init__(self, limits: Optional[CircuitBreakerLimits] = None):
        """
        Initialize circuit breaker system

        Args:
            limits: Circuit breaker limits configuration
        """
        self.limits = limits or CircuitBreakerLimits()

        # Current state
        self.state = CircuitBreakerState.NORMAL
        self.pause_until: Optional[datetime] = None

        # Event history
        self.events: List[CircuitBreakerEvent] = []

        # Metrics tracking
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        logger.info(
            f"CircuitBreaker initialized: "
            f"daily_loss=${float(self.limits.daily_loss_limit)}, "
            f"max_drawdown={float(self.limits.max_drawdown_pct)*100}%, "
            f"max_consec_losses={self.limits.max_consecutive_losses}"
        )

    def check_limits(self, metrics: TradingMetrics) -> Tuple[CircuitBreakerState, Optional[str]]:
        """
        Check all circuit breaker limits and return appropriate state

        Args:
            metrics: Current trading metrics

        Returns:
            (new_state, reason) tuple
        """
        # Check if paused and still within pause duration
        if self.state == CircuitBreakerState.PAUSE and self.pause_until:
            if datetime.now() < self.pause_until:
                return CircuitBreakerState.PAUSE, "Trading paused until circuit breaker expires"
            else:
                # Pause expired, reset to NORMAL
                self._transition_state(CircuitBreakerState.NORMAL, "Pause period expired")

        # Check HALT conditions (highest priority)
        halt_reason = self._check_halt_conditions(metrics)
        if halt_reason:
            self._transition_state(CircuitBreakerState.HALT, halt_reason, CircuitBreakerTrigger.DAILY_LOSS_LIMIT)
            return CircuitBreakerState.HALT, halt_reason

        # Check PAUSE conditions
        pause_reason = self._check_pause_conditions(metrics)
        if pause_reason:
            self._transition_state(CircuitBreakerState.PAUSE, pause_reason, CircuitBreakerTrigger.CONSECUTIVE_LOSSES)
            self.pause_until = datetime.now() + timedelta(minutes=self.limits.pause_duration_minutes)
            return CircuitBreakerState.PAUSE, pause_reason

        # Check REDUCE conditions
        reduce_reason = self._check_reduce_conditions(metrics)
        if reduce_reason:
            self._transition_state(CircuitBreakerState.REDUCE, reduce_reason, CircuitBreakerTrigger.MAX_DRAWDOWN)
            return CircuitBreakerState.REDUCE, reduce_reason

        # All checks passed - NORMAL state
        if self.state != CircuitBreakerState.NORMAL:
            self._transition_state(CircuitBreakerState.NORMAL, "All limits within acceptable range")

        return CircuitBreakerState.NORMAL, None

    def _check_halt_conditions(self, metrics: TradingMetrics) -> Optional[str]:
        """Check conditions that require immediate HALT"""
        # Daily loss limit exceeded
        if metrics.daily_pnl <= -self.limits.daily_loss_limit:
            return (
                f"Daily loss limit exceeded: ${float(metrics.daily_pnl):.2f} "
                f"<= -${float(self.limits.daily_loss_limit):.2f}"
            )

        # Check per-whale loss limits
        for whale_address, whale_loss in metrics.whale_daily_losses.items():
            if whale_loss <= -self.limits.whale_daily_loss_limit:
                return (
                    f"Whale loss limit exceeded: {whale_address[:10]}... "
                    f"loss=${float(whale_loss):.2f}"
                )

        return None

    def _check_pause_conditions(self, metrics: TradingMetrics) -> Optional[str]:
        """Check conditions that require PAUSE"""
        # Consecutive losses
        if metrics.consecutive_losses >= self.limits.max_consecutive_losses:
            return (
                f"Consecutive losses limit: {metrics.consecutive_losses} "
                f">= {self.limits.max_consecutive_losses} (pausing for "
                f"{self.limits.pause_duration_minutes} minutes)"
            )

        return None

    def _check_reduce_conditions(self, metrics: TradingMetrics) -> Optional[str]:
        """Check conditions that require REDUCE"""
        # Max drawdown from peak
        if metrics.portfolio_value > 0 and metrics.peak_value > 0:
            current_drawdown = (metrics.peak_value - metrics.portfolio_value) / metrics.peak_value

            if current_drawdown >= self.limits.max_drawdown_pct:
                return (
                    f"Max drawdown exceeded: {float(current_drawdown)*100:.2f}% "
                    f">= {float(self.limits.max_drawdown_pct)*100:.2f}% "
                    f"(reducing position sizes by {float(self.limits.reduce_factor)*100:.0f}%)"
                )

        return None

    def _transition_state(
        self,
        new_state: CircuitBreakerState,
        reason: str,
        trigger: Optional[CircuitBreakerTrigger] = None
    ):
        """Transition to a new circuit breaker state"""
        if new_state != self.state:
            old_state = self.state
            self.state = new_state

            # Record event
            event = CircuitBreakerEvent(
                trigger=trigger or CircuitBreakerTrigger.MANUAL,
                state=new_state,
                timestamp=datetime.now(),
                reason=reason
            )
            self.events.append(event)

            logger.warning(
                f"CIRCUIT BREAKER: {old_state.value} → {new_state.value} | "
                f"Reason: {reason}"
            )

    def can_trade(self) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed in current state

        Returns:
            (can_trade, reason) tuple
        """
        if self.state == CircuitBreakerState.HALT:
            return False, "Trading halted due to circuit breaker"

        if self.state == CircuitBreakerState.PAUSE:
            if self.pause_until and datetime.now() < self.pause_until:
                time_remaining = (self.pause_until - datetime.now()).total_seconds() / 60
                return False, f"Trading paused for {time_remaining:.1f} more minutes"

        if self.state == CircuitBreakerState.EMERGENCY:
            return False, "Emergency shutdown - manual intervention required"

        return True, None

    def get_position_size_multiplier(self) -> Decimal:
        """
        Get position size multiplier based on current state

        Returns:
            Multiplier for position sizing (1.0 = normal, 0.5 = reduced, 0.0 = halted)
        """
        if self.state in [CircuitBreakerState.HALT, CircuitBreakerState.PAUSE, CircuitBreakerState.EMERGENCY]:
            return Decimal("0")

        if self.state == CircuitBreakerState.REDUCE:
            return self.limits.reduce_factor

        return Decimal("1.0")

    def emergency_shutdown(self, reason: str):
        """Trigger emergency shutdown"""
        self._transition_state(CircuitBreakerState.EMERGENCY, reason, CircuitBreakerTrigger.EMERGENCY)
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")

    def manual_override(self, new_state: CircuitBreakerState, reason: str):
        """Manual override of circuit breaker state"""
        self._transition_state(new_state, f"Manual override: {reason}", CircuitBreakerTrigger.MANUAL)

    def reset_daily_metrics(self):
        """Reset daily tracking metrics (call at midnight)"""
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        logger.info("Daily circuit breaker metrics reset")

    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        return {
            "state": self.state.value,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
            "can_trade": self.can_trade()[0],
            "position_multiplier": float(self.get_position_size_multiplier()),
            "recent_events": [
                {
                    "trigger": e.trigger.value,
                    "state": e.state.value,
                    "timestamp": e.timestamp.isoformat(),
                    "reason": e.reason
                }
                for e in self.events[-10:]  # Last 10 events
            ],
            "limits": {
                "daily_loss_limit": float(self.limits.daily_loss_limit),
                "max_drawdown_pct": float(self.limits.max_drawdown_pct),
                "max_consecutive_losses": self.limits.max_consecutive_losses,
                "whale_daily_loss_limit": float(self.limits.whale_daily_loss_limit)
            }
        }

    def get_metrics_required(self) -> List[str]:
        """Get list of metrics required for circuit breaker checks"""
        return [
            "daily_pnl",
            "portfolio_value",
            "peak_value",
            "consecutive_losses",
            "whale_daily_losses"
        ]


# ==================== Example Usage ====================

def main():
    """Example usage of PortfolioCircuitBreaker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize circuit breaker with default limits
    circuit_breaker = PortfolioCircuitBreaker()

    print("\n=== Circuit Breaker Test Scenarios ===\n")

    # Scenario 1: Normal trading
    metrics = TradingMetrics(
        daily_pnl=Decimal("-50"),
        portfolio_value=Decimal("10000"),
        peak_value=Decimal("10000"),
        consecutive_losses=2,
        whale_daily_losses={}
    )

    state, reason = circuit_breaker.check_limits(metrics)
    print(f"Scenario 1 (Normal): State={state.value}, Reason={reason}")
    can_trade, trade_reason = circuit_breaker.can_trade()
    print(f"  Can trade: {can_trade}, Multiplier: {float(circuit_breaker.get_position_size_multiplier())}\n")

    # Scenario 2: Max drawdown (REDUCE)
    metrics_drawdown = TradingMetrics(
        daily_pnl=Decimal("-800"),
        portfolio_value=Decimal("8500"),  # 15% drawdown
        peak_value=Decimal("10000"),
        consecutive_losses=3,
        whale_daily_losses={}
    )

    state, reason = circuit_breaker.check_limits(metrics_drawdown)
    print(f"Scenario 2 (Drawdown): State={state.value}")
    print(f"  Reason: {reason}")
    print(f"  Multiplier: {float(circuit_breaker.get_position_size_multiplier())}\n")

    # Scenario 3: Consecutive losses (PAUSE)
    circuit_breaker2 = PortfolioCircuitBreaker()
    metrics_consec = TradingMetrics(
        daily_pnl=Decimal("-300"),
        portfolio_value=Decimal("9700"),
        peak_value=Decimal("10000"),
        consecutive_losses=5,
        whale_daily_losses={}
    )

    state, reason = circuit_breaker2.check_limits(metrics_consec)
    print(f"Scenario 3 (Consecutive Losses): State={state.value}")
    print(f"  Reason: {reason}")
    can_trade, trade_reason = circuit_breaker2.can_trade()
    print(f"  Can trade: {can_trade}, Reason: {trade_reason}\n")

    # Scenario 4: Daily loss limit (HALT)
    circuit_breaker3 = PortfolioCircuitBreaker()
    metrics_halt = TradingMetrics(
        daily_pnl=Decimal("-600"),  # Exceeds $500 limit
        portfolio_value=Decimal("9400"),
        peak_value=Decimal("10000"),
        consecutive_losses=3,
        whale_daily_losses={}
    )

    state, reason = circuit_breaker3.check_limits(metrics_halt)
    print(f"Scenario 4 (Daily Loss Limit): State={state.value}")
    print(f"  Reason: {reason}")
    can_trade, trade_reason = circuit_breaker3.can_trade()
    print(f"  Can trade: {can_trade}, Reason: {trade_reason}\n")

    # Get full status
    print("=== Circuit Breaker Status ===")
    import json
    print(json.dumps(circuit_breaker3.get_status(), indent=2))


if __name__ == "__main__":
    main()
