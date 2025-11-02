"""
Dynamic Risk Scaling Based on Performance
Week 5: Risk Management Framework - Performance-Based Position Sizing
Automatically adjusts position sizes based on recent trading performance
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class PerformanceState(Enum):
    """Current performance state"""
    SCALING_UP = "SCALING_UP"          # Recent wins, increase size
    NEUTRAL = "NEUTRAL"                # Normal sizing
    SCALING_DOWN = "SCALING_DOWN"      # Recent losses, decrease size
    MINIMAL = "MINIMAL"                # Severe losses, minimal sizing


@dataclass
class TradeResult:
    """Record of a completed trade"""
    trade_id: str
    timestamp: datetime
    pnl: Decimal
    is_win: bool
    position_size: Decimal


@dataclass
class PerformanceWindow:
    """Rolling window of recent performance"""
    window_size: int
    trades: deque = field(default_factory=deque)

    def add_trade(self, trade: TradeResult):
        """Add trade to window"""
        self.trades.append(trade)
        if len(self.trades) > self.window_size:
            self.trades.popleft()

    def get_win_count(self) -> int:
        """Count wins in window"""
        return sum(1 for t in self.trades if t.is_win)

    def get_loss_count(self) -> int:
        """Count losses in window"""
        return sum(1 for t in self.trades if not t.is_win)

    def get_win_rate(self) -> Decimal:
        """Calculate win rate"""
        if not self.trades:
            return Decimal("0.5")
        return Decimal(str(self.get_win_count() / len(self.trades)))

    def get_consecutive_wins(self) -> int:
        """Count consecutive wins from most recent"""
        count = 0
        for trade in reversed(self.trades):
            if trade.is_win:
                count += 1
            else:
                break
        return count

    def get_consecutive_losses(self) -> int:
        """Count consecutive losses from most recent"""
        count = 0
        for trade in reversed(self.trades):
            if not trade.is_win:
                count += 1
            else:
                break
        return count


@dataclass
class ScalingConfig:
    """Configuration for dynamic risk scaling"""
    # Performance thresholds
    wins_for_scale_up: int = 3          # Consecutive wins to increase size
    losses_for_scale_down: int = 2      # Consecutive losses to decrease size
    severe_loss_threshold: int = 5      # Consecutive losses for minimal sizing

    # Scaling factors
    max_scale: Decimal = Decimal("2.0")     # Maximum multiplier (2x)
    min_scale: Decimal = Decimal("0.25")    # Minimum multiplier (0.25x)
    neutral_scale: Decimal = Decimal("1.0")  # Normal sizing

    # Scale adjustment increments
    scale_up_increment: Decimal = Decimal("0.25")    # Increase by 25%
    scale_down_increment: Decimal = Decimal("0.25")  # Decrease by 25%

    # Reset parameters
    reset_after_days: int = 7           # Reset scaling after 7 days
    window_size: int = 20               # Number of trades to consider

    # Minimum trades before scaling
    min_trades_for_scaling: int = 5


@dataclass
class ScalingMetrics:
    """Current scaling metrics and state"""
    current_multiplier: Decimal
    state: PerformanceState
    consecutive_wins: int
    consecutive_losses: int
    win_rate: Decimal
    total_trades: int
    last_reset: datetime
    days_since_reset: int
    next_reset: datetime


# ==================== Dynamic Risk Scaler ====================

class DynamicRiskScaler:
    """
    Dynamic Risk Scaling System

    Automatically adjusts position sizes based on recent trading performance:
    - Scale UP after 3 consecutive wins (max 2x)
    - Scale DOWN after 2 consecutive losses (min 0.25x)
    - Reset scaling after 7 days
    - Uses rolling window for performance tracking

    Research-backed approach: Size up during hot streaks,
    size down during cold streaks to preserve capital.
    """

    def __init__(self, config: Optional[ScalingConfig] = None):
        """
        Initialize dynamic risk scaler

        Args:
            config: Scaling configuration
        """
        self.config = config or ScalingConfig()

        # Current state
        self.current_multiplier = self.config.neutral_scale
        self.state = PerformanceState.NEUTRAL

        # Performance tracking
        self.performance_window = PerformanceWindow(
            window_size=self.config.window_size
        )

        # Reset tracking
        self.last_reset = datetime.now()

        logger.info(
            f"DynamicRiskScaler initialized: "
            f"scale_range={float(self.config.min_scale)}-{float(self.config.max_scale)}x, "
            f"reset_days={self.config.reset_after_days}"
        )

    def record_trade(self, trade: TradeResult) -> Tuple[Decimal, str]:
        """
        Record a completed trade and update scaling multiplier

        Args:
            trade: Completed trade result

        Returns:
            (new_multiplier, reason) tuple
        """
        # Check if reset needed (7 days elapsed)
        self._check_and_reset()

        # Add trade to performance window
        self.performance_window.add_trade(trade)

        old_multiplier = self.current_multiplier
        old_state = self.state

        # Update scaling based on performance
        self._update_scaling()

        # Log change if multiplier changed
        if self.current_multiplier != old_multiplier:
            logger.info(
                f"Scaling changed: {float(old_multiplier):.2f}x → {float(self.current_multiplier):.2f}x | "
                f"State: {old_state.value} → {self.state.value} | "
                f"Win: {trade.is_win} | "
                f"Consecutive: {self.performance_window.get_consecutive_wins()}W / "
                f"{self.performance_window.get_consecutive_losses()}L"
            )

            reason = self._get_scaling_reason()
            return self.current_multiplier, reason

        return self.current_multiplier, "No change"

    def get_position_multiplier(self) -> Decimal:
        """
        Get current position size multiplier

        Returns:
            Multiplier to apply to base position size (0.25x - 2.0x)
        """
        # Check if reset needed before returning multiplier
        self._check_and_reset()
        return self.current_multiplier

    def get_metrics(self) -> ScalingMetrics:
        """
        Get current scaling metrics

        Returns:
            ScalingMetrics with current state
        """
        days_since_reset = (datetime.now() - self.last_reset).days
        next_reset = self.last_reset + timedelta(days=self.config.reset_after_days)

        return ScalingMetrics(
            current_multiplier=self.current_multiplier,
            state=self.state,
            consecutive_wins=self.performance_window.get_consecutive_wins(),
            consecutive_losses=self.performance_window.get_consecutive_losses(),
            win_rate=self.performance_window.get_win_rate(),
            total_trades=len(self.performance_window.trades),
            last_reset=self.last_reset,
            days_since_reset=days_since_reset,
            next_reset=next_reset
        )

    def manual_reset(self, reason: str = "Manual reset"):
        """Manually reset scaling to neutral"""
        old_multiplier = self.current_multiplier
        self.current_multiplier = self.config.neutral_scale
        self.state = PerformanceState.NEUTRAL
        self.performance_window.trades.clear()
        self.last_reset = datetime.now()

        logger.warning(
            f"Manual reset: {float(old_multiplier):.2f}x → 1.0x | Reason: {reason}"
        )

    def get_status(self) -> Dict:
        """Get comprehensive status"""
        metrics = self.get_metrics()

        return {
            "multiplier": float(self.current_multiplier),
            "state": self.state.value,
            "performance": {
                "consecutive_wins": metrics.consecutive_wins,
                "consecutive_losses": metrics.consecutive_losses,
                "win_rate": float(metrics.win_rate),
                "total_trades": metrics.total_trades
            },
            "reset": {
                "last_reset": metrics.last_reset.isoformat(),
                "days_since_reset": metrics.days_since_reset,
                "next_reset": metrics.next_reset.isoformat()
            },
            "config": {
                "max_scale": float(self.config.max_scale),
                "min_scale": float(self.config.min_scale),
                "wins_for_scale_up": self.config.wins_for_scale_up,
                "losses_for_scale_down": self.config.losses_for_scale_down,
                "reset_after_days": self.config.reset_after_days
            }
        }

    # ==================== Private Methods ====================

    def _check_and_reset(self):
        """Check if reset needed (7 days elapsed)"""
        days_elapsed = (datetime.now() - self.last_reset).days

        if days_elapsed >= self.config.reset_after_days:
            old_multiplier = self.current_multiplier
            self.current_multiplier = self.config.neutral_scale
            self.state = PerformanceState.NEUTRAL
            self.performance_window.trades.clear()
            self.last_reset = datetime.now()

            logger.info(
                f"Automatic reset after {days_elapsed} days: "
                f"{float(old_multiplier):.2f}x → 1.0x"
            )

    def _update_scaling(self):
        """Update scaling multiplier based on performance"""
        # Need minimum trades before scaling
        if len(self.performance_window.trades) < self.config.min_trades_for_scaling:
            self.state = PerformanceState.NEUTRAL
            self.current_multiplier = self.config.neutral_scale
            return

        consecutive_wins = self.performance_window.get_consecutive_wins()
        consecutive_losses = self.performance_window.get_consecutive_losses()

        # Severe losses: minimal sizing
        if consecutive_losses >= self.config.severe_loss_threshold:
            self.state = PerformanceState.MINIMAL
            self.current_multiplier = self.config.min_scale
            return

        # Scale down after losses
        if consecutive_losses >= self.config.losses_for_scale_down:
            self.state = PerformanceState.SCALING_DOWN
            # Decrease by increment for each loss beyond threshold
            extra_losses = consecutive_losses - self.config.losses_for_scale_down + 1
            reduction = self.config.scale_down_increment * Decimal(str(extra_losses))
            self.current_multiplier = max(
                self.config.min_scale,
                self.config.neutral_scale - reduction
            )
            return

        # Scale up after wins
        if consecutive_wins >= self.config.wins_for_scale_up:
            self.state = PerformanceState.SCALING_UP
            # Increase by increment for each win beyond threshold
            extra_wins = consecutive_wins - self.config.wins_for_scale_up + 1
            increase = self.config.scale_up_increment * Decimal(str(extra_wins))
            self.current_multiplier = min(
                self.config.max_scale,
                self.config.neutral_scale + increase
            )
            return

        # Neutral state (some wins/losses but not enough to scale)
        self.state = PerformanceState.NEUTRAL
        self.current_multiplier = self.config.neutral_scale

    def _get_scaling_reason(self) -> str:
        """Get human-readable reason for current scaling"""
        consecutive_wins = self.performance_window.get_consecutive_wins()
        consecutive_losses = self.performance_window.get_consecutive_losses()

        if self.state == PerformanceState.MINIMAL:
            return f"Severe losses ({consecutive_losses} consecutive) - minimal sizing"
        elif self.state == PerformanceState.SCALING_DOWN:
            return f"Recent losses ({consecutive_losses} consecutive) - reducing size"
        elif self.state == PerformanceState.SCALING_UP:
            return f"Hot streak ({consecutive_wins} consecutive wins) - increasing size"
        else:
            return "Normal performance - neutral sizing"


# ==================== Example Usage ====================

def main():
    """Example usage of DynamicRiskScaler"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize scaler
    scaler = DynamicRiskScaler()

    print("\n=== Dynamic Risk Scaler Test Scenarios ===\n")

    # Scenario 1: Winning streak
    print("=== Scenario 1: Winning Streak ===")
    base_size = Decimal("1000")

    for i in range(5):
        trade = TradeResult(
            trade_id=f"trade_w{i}",
            timestamp=datetime.now(),
            pnl=Decimal("50"),
            is_win=True,
            position_size=base_size
        )

        multiplier, reason = scaler.record_trade(trade)
        actual_size = base_size * multiplier

        print(f"Trade {i+1} (WIN): Multiplier={float(multiplier):.2f}x, Size=${float(actual_size):.2f}")
        print(f"  {reason}")

    # Scenario 2: Losing streak
    print("\n=== Scenario 2: Losing Streak ===")
    scaler.manual_reset("Testing losing streak")

    for i in range(6):
        trade = TradeResult(
            trade_id=f"trade_l{i}",
            timestamp=datetime.now(),
            pnl=Decimal("-30"),
            is_win=False,
            position_size=base_size
        )

        multiplier, reason = scaler.record_trade(trade)
        actual_size = base_size * multiplier

        print(f"Trade {i+1} (LOSS): Multiplier={float(multiplier):.2f}x, Size=${float(actual_size):.2f}")
        print(f"  {reason}")

    # Scenario 3: Mixed performance
    print("\n=== Scenario 3: Mixed Performance ===")
    scaler.manual_reset("Testing mixed performance")

    sequence = [True, True, False, True, False, False, True, True, True]
    for i, is_win in enumerate(sequence):
        trade = TradeResult(
            trade_id=f"trade_m{i}",
            timestamp=datetime.now(),
            pnl=Decimal("25") if is_win else Decimal("-20"),
            is_win=is_win,
            position_size=base_size
        )

        multiplier, reason = scaler.record_trade(trade)
        actual_size = base_size * multiplier

        result = "WIN" if is_win else "LOSS"
        print(f"Trade {i+1} ({result}): Multiplier={float(multiplier):.2f}x, Size=${float(actual_size):.2f}")

    # Get comprehensive status
    print("\n=== Current Status ===")
    import json
    status = scaler.get_status()
    print(json.dumps(status, indent=2))

    # Test reset after 7 days (simulate)
    print("\n=== Testing Auto-Reset ===")
    scaler.last_reset = datetime.now() - timedelta(days=8)  # Simulate 8 days ago
    multiplier = scaler.get_position_multiplier()
    print(f"Multiplier after 8 days: {float(multiplier):.2f}x (should be reset to 1.0x)")


if __name__ == "__main__":
    main()
