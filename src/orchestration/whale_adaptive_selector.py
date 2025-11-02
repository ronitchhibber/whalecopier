"""
Whale Adaptive Selection System
Week 6: Multi-Whale Orchestration - Adaptive Enable/Disable
Automatically enables/disables whales based on performance and correlation
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class WhaleState(Enum):
    """Whale activation state"""
    ENABLED = "ENABLED"                # Active - copying trades
    DISABLED_PERFORMANCE = "DISABLED_PERFORMANCE"  # Disabled due to poor performance
    DISABLED_CORRELATION = "DISABLED_CORRELATION"  # Disabled due to high correlation
    DISABLED_MANUAL = "DISABLED_MANUAL"            # Manually disabled by user
    PROBATION = "PROBATION"                        # Trial period (limited allocation)
    PENDING_ENABLE = "PENDING_ENABLE"              # Recovering, needs more wins


class StateTransition(Enum):
    """State change triggers"""
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"      # 5+ losses
    CONSECUTIVE_WINS = "CONSECUTIVE_WINS"          # 2+ wins
    HIGH_CORRELATION = "HIGH_CORRELATION"          # >70% correlation
    QUALITY_SCORE_DROP = "QUALITY_SCORE_DROP"      # Quality score below threshold
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"            # User action
    PROBATION_SUCCESS = "PROBATION_SUCCESS"        # Trial period successful
    PROBATION_FAILURE = "PROBATION_FAILURE"        # Trial period failed


@dataclass
class WhaleStateInfo:
    """Current state information for a whale"""
    whale_address: str
    current_state: WhaleState
    previous_state: Optional[WhaleState]

    # Performance tracking
    consecutive_wins: int
    consecutive_losses: int
    recent_quality_score: Decimal

    # Correlation tracking
    correlation_with_active: Dict[str, Decimal]  # whale_address -> correlation
    max_correlation: Decimal

    # State metadata
    state_since: datetime
    transitions: List[Tuple[datetime, WhaleState, StateTransition, str]]  # history

    # Manual controls
    manual_override: bool
    manual_override_reason: Optional[str]


@dataclass
class StateChangeEvent:
    """Event for state change"""
    whale_address: str
    old_state: WhaleState
    new_state: WhaleState
    trigger: StateTransition
    reason: str
    timestamp: datetime
    metrics: Dict[str, str]  # Key metrics at time of change


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive selection"""
    # Performance thresholds
    consecutive_losses_threshold: int = 5          # Disable after 5 losses
    consecutive_wins_threshold: int = 2            # Re-enable after 2 wins
    quality_score_threshold: Decimal = Decimal("40")  # Min quality score

    # Correlation thresholds
    high_correlation_threshold: Decimal = Decimal("0.70")  # 70% correlation
    max_correlated_whales: int = 2                 # Max 2 highly correlated whales

    # Probation settings
    probation_duration_days: int = 7               # 7-day trial period
    probation_min_trades: int = 5                  # Min trades during probation
    probation_min_win_rate: Decimal = Decimal("0.50")  # 50% win rate required

    # Re-enable settings
    recovery_period_days: int = 3                  # Wait 3 days before re-enable
    min_quality_for_reenable: Decimal = Decimal("50")  # Need 50+ quality score

    # Safety limits
    min_enabled_whales: int = 3                    # Always keep at least 3 whales
    max_enabled_whales: int = 30                   # Max 30 whales active


# ==================== Whale Adaptive Selector ====================

class WhaleAdaptiveSelector:
    """
    Whale Adaptive Selection System

    Automatically manages whale portfolio by enabling/disabling whales based on:
    1. **Performance:** Disable after 5 consecutive losses, re-enable after 2 wins
    2. **Correlation:** Disable if >70% correlated with existing active whales
    3. **Quality Score:** Disable if quality drops below threshold
    4. **Manual Override:** User can force enable/disable with override flag

    State Machine:
    ```
    ENABLED ─[5 losses]→ DISABLED_PERFORMANCE
    ENABLED ─[>70% corr]→ DISABLED_CORRELATION
    DISABLED_* ─[2 wins]→ PENDING_ENABLE ─[verification]→ ENABLED
    NEW_WHALE → PROBATION ─[success]→ ENABLED
    ```

    Safety Features:
    - Minimum 3 whales always enabled (prevents complete shutdown)
    - Manual override capability (user can force state)
    - Probation period for new whales (trial with limited allocation)
    - Recovery period before re-enabling (prevents flip-flopping)
    """

    def __init__(self, config: Optional[AdaptiveConfig] = None):
        """
        Initialize adaptive selector

        Args:
            config: Adaptive selection configuration
        """
        self.config = config or AdaptiveConfig()

        # Whale states
        self.whale_states: Dict[str, WhaleStateInfo] = {}
        self.active_whales: Set[str] = set()
        self.disabled_whales: Set[str] = set()

        # State change history
        self.state_changes: List[StateChangeEvent] = []

        # Statistics
        self.total_disables = 0
        self.total_enables = 0
        self.performance_disables = 0
        self.correlation_disables = 0
        self.manual_overrides = 0

        logger.info(
            f"WhaleAdaptiveSelector initialized: "
            f"loss_threshold={self.config.consecutive_losses_threshold}, "
            f"win_threshold={self.config.consecutive_wins_threshold}, "
            f"correlation_threshold={float(self.config.high_correlation_threshold)}"
        )

    def register_whale(
        self,
        whale_address: str,
        initial_state: WhaleState = WhaleState.PROBATION,
        quality_score: Optional[Decimal] = None
    ):
        """
        Register a new whale in the system

        Args:
            whale_address: Whale address
            initial_state: Initial state (default: PROBATION for new whales)
            quality_score: Initial quality score
        """
        if whale_address in self.whale_states:
            logger.warning(f"Whale {whale_address[:10]}... already registered")
            return

        state_info = WhaleStateInfo(
            whale_address=whale_address,
            current_state=initial_state,
            previous_state=None,
            consecutive_wins=0,
            consecutive_losses=0,
            recent_quality_score=quality_score or Decimal("50"),
            correlation_with_active={},
            max_correlation=Decimal("0"),
            state_since=datetime.now(),
            transitions=[],
            manual_override=False,
            manual_override_reason=None
        )

        self.whale_states[whale_address] = state_info

        if initial_state == WhaleState.ENABLED:
            self.active_whales.add(whale_address)
        else:
            self.disabled_whales.add(whale_address)

        logger.info(
            f"Registered whale: {whale_address[:10]}... | "
            f"Initial state: {initial_state.value} | "
            f"Quality: {float(quality_score or 50):.0f}"
        )

    def update_performance(
        self,
        whale_address: str,
        trade_won: bool,
        quality_score: Optional[Decimal] = None
    ):
        """
        Update whale performance and evaluate state changes

        Args:
            whale_address: Whale address
            trade_won: True if trade was winning, False if losing
            quality_score: Updated quality score
        """
        if whale_address not in self.whale_states:
            logger.warning(f"Whale {whale_address[:10]}... not registered")
            return

        state_info = self.whale_states[whale_address]

        # Update consecutive streaks
        if trade_won:
            state_info.consecutive_wins += 1
            state_info.consecutive_losses = 0
        else:
            state_info.consecutive_losses += 1
            state_info.consecutive_wins = 0

        # Update quality score
        if quality_score is not None:
            state_info.recent_quality_score = quality_score

        # Evaluate state transitions
        self._evaluate_state_transitions(whale_address)

    def update_correlations(
        self,
        correlations: Dict[Tuple[str, str], Decimal]
    ):
        """
        Update correlation data and evaluate state changes

        Args:
            correlations: Pairwise correlation dict
        """
        # Update correlation info for each whale
        for whale_addr in self.whale_states:
            state_info = self.whale_states[whale_addr]
            state_info.correlation_with_active = {}

            # Check correlations with active whales
            for (w1, w2), corr in correlations.items():
                if w1 == whale_addr and w2 in self.active_whales:
                    state_info.correlation_with_active[w2] = corr
                elif w2 == whale_addr and w1 in self.active_whales:
                    state_info.correlation_with_active[w1] = corr

            # Calculate max correlation
            if state_info.correlation_with_active:
                state_info.max_correlation = max(state_info.correlation_with_active.values())
            else:
                state_info.max_correlation = Decimal("0")

        # Evaluate correlation-based state changes
        for whale_addr in list(self.whale_states.keys()):
            self._evaluate_correlation_state(whale_addr)

    def manual_override_state(
        self,
        whale_address: str,
        new_state: WhaleState,
        reason: str
    ):
        """
        Manually override whale state (admin/dashboard action)

        Args:
            whale_address: Whale address
            new_state: New state to set
            reason: Reason for manual override
        """
        if whale_address not in self.whale_states:
            logger.warning(f"Whale {whale_address[:10]}... not registered")
            return

        state_info = self.whale_states[whale_address]
        old_state = state_info.current_state

        # Apply manual override
        state_info.manual_override = True
        state_info.manual_override_reason = reason

        self._transition_state(
            whale_address,
            new_state,
            StateTransition.MANUAL_OVERRIDE,
            f"Manual override: {reason}"
        )

        self.manual_overrides += 1

        logger.warning(
            f"Manual override: {whale_address[:10]}... | "
            f"{old_state.value} → {new_state.value} | "
            f"Reason: {reason}"
        )

    def get_enabled_whales(self) -> List[str]:
        """Get list of currently enabled whales"""
        return list(self.active_whales)

    def get_disabled_whales(self) -> List[str]:
        """Get list of currently disabled whales"""
        return list(self.disabled_whales)

    def get_whale_state(self, whale_address: str) -> Optional[WhaleStateInfo]:
        """Get state info for a whale"""
        return self.whale_states.get(whale_address)

    def get_state_changes(
        self,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[StateChangeEvent]:
        """Get recent state change events"""
        if since:
            filtered = [e for e in self.state_changes if e.timestamp >= since]
        else:
            filtered = self.state_changes

        return sorted(filtered, key=lambda x: x.timestamp, reverse=True)[:limit]

    # ==================== Private Methods ====================

    def _evaluate_state_transitions(self, whale_address: str):
        """Evaluate and apply state transitions based on performance"""
        state_info = self.whale_states[whale_address]

        # Skip if manual override
        if state_info.manual_override:
            return

        current_state = state_info.current_state

        # ENABLED → DISABLED_PERFORMANCE (too many losses)
        if current_state == WhaleState.ENABLED:
            if state_info.consecutive_losses >= self.config.consecutive_losses_threshold:
                self._transition_state(
                    whale_address,
                    WhaleState.DISABLED_PERFORMANCE,
                    StateTransition.CONSECUTIVE_LOSSES,
                    f"Disabled after {state_info.consecutive_losses} consecutive losses"
                )
                self.performance_disables += 1

            # Check quality score
            elif state_info.recent_quality_score < self.config.quality_score_threshold:
                self._transition_state(
                    whale_address,
                    WhaleState.DISABLED_PERFORMANCE,
                    StateTransition.QUALITY_SCORE_DROP,
                    f"Quality score dropped to {float(state_info.recent_quality_score):.0f}"
                )
                self.performance_disables += 1

        # DISABLED_PERFORMANCE → PENDING_ENABLE (recovering with wins)
        elif current_state == WhaleState.DISABLED_PERFORMANCE:
            if state_info.consecutive_wins >= self.config.consecutive_wins_threshold:
                # Check if enough time has passed
                time_disabled = datetime.now() - state_info.state_since
                if time_disabled.days >= self.config.recovery_period_days:
                    self._transition_state(
                        whale_address,
                        WhaleState.PENDING_ENABLE,
                        StateTransition.CONSECUTIVE_WINS,
                        f"Recovered with {state_info.consecutive_wins} wins after {time_disabled.days} days"
                    )

        # PENDING_ENABLE → ENABLED (verification passed)
        elif current_state == WhaleState.PENDING_ENABLE:
            if (state_info.consecutive_wins >= self.config.consecutive_wins_threshold and
                state_info.recent_quality_score >= self.config.min_quality_for_reenable):
                self._transition_state(
                    whale_address,
                    WhaleState.ENABLED,
                    StateTransition.CONSECUTIVE_WINS,
                    f"Re-enabled: {state_info.consecutive_wins} wins, quality {float(state_info.recent_quality_score):.0f}"
                )
                self.total_enables += 1

        # PROBATION → ENABLED/DISABLED (trial period evaluation)
        elif current_state == WhaleState.PROBATION:
            time_in_probation = datetime.now() - state_info.state_since
            if time_in_probation.days >= self.config.probation_duration_days:
                # Calculate win rate during probation
                total_trades = state_info.consecutive_wins + state_info.consecutive_losses
                if total_trades >= self.config.probation_min_trades:
                    win_rate = Decimal(str(state_info.consecutive_wins / total_trades))

                    if win_rate >= self.config.probation_min_win_rate:
                        self._transition_state(
                            whale_address,
                            WhaleState.ENABLED,
                            StateTransition.PROBATION_SUCCESS,
                            f"Probation successful: {float(win_rate)*100:.0f}% win rate over {total_trades} trades"
                        )
                        self.total_enables += 1
                    else:
                        self._transition_state(
                            whale_address,
                            WhaleState.DISABLED_PERFORMANCE,
                            StateTransition.PROBATION_FAILURE,
                            f"Probation failed: {float(win_rate)*100:.0f}% win rate (need {float(self.config.probation_min_win_rate)*100:.0f}%)"
                        )

    def _evaluate_correlation_state(self, whale_address: str):
        """Evaluate state changes based on correlation"""
        state_info = self.whale_states[whale_address]

        # Skip if manual override
        if state_info.manual_override:
            return

        current_state = state_info.current_state

        # ENABLED → DISABLED_CORRELATION (too correlated with active whales)
        if current_state == WhaleState.ENABLED:
            if state_info.max_correlation >= self.config.high_correlation_threshold:
                # Count highly correlated active whales
                high_corr_count = sum(
                    1 for corr in state_info.correlation_with_active.values()
                    if corr >= self.config.high_correlation_threshold
                )

                if high_corr_count >= self.config.max_correlated_whales:
                    self._transition_state(
                        whale_address,
                        WhaleState.DISABLED_CORRELATION,
                        StateTransition.HIGH_CORRELATION,
                        f"High correlation ({float(state_info.max_correlation)*100:.0f}%) with {high_corr_count} active whales"
                    )
                    self.correlation_disables += 1

        # DISABLED_CORRELATION → PENDING_ENABLE (correlation decreased)
        elif current_state == WhaleState.DISABLED_CORRELATION:
            if state_info.max_correlation < self.config.high_correlation_threshold:
                self._transition_state(
                    whale_address,
                    WhaleState.PENDING_ENABLE,
                    StateTransition.HIGH_CORRELATION,
                    f"Correlation decreased to {float(state_info.max_correlation)*100:.0f}%"
                )

    def _transition_state(
        self,
        whale_address: str,
        new_state: WhaleState,
        trigger: StateTransition,
        reason: str
    ):
        """Apply state transition"""
        state_info = self.whale_states[whale_address]
        old_state = state_info.current_state

        # Check safety limits
        if new_state in [WhaleState.DISABLED_PERFORMANCE, WhaleState.DISABLED_CORRELATION, WhaleState.DISABLED_MANUAL]:
            if len(self.active_whales) <= self.config.min_enabled_whales:
                logger.warning(
                    f"Cannot disable {whale_address[:10]}... - would violate min_enabled_whales limit "
                    f"({self.config.min_enabled_whales})"
                )
                return

        if new_state == WhaleState.ENABLED:
            if len(self.active_whales) >= self.config.max_enabled_whales:
                logger.warning(
                    f"Cannot enable {whale_address[:10]}... - would exceed max_enabled_whales limit "
                    f"({self.config.max_enabled_whales})"
                )
                return

        # Update state
        state_info.previous_state = old_state
        state_info.current_state = new_state
        state_info.state_since = datetime.now()

        # Update sets
        if new_state == WhaleState.ENABLED:
            self.active_whales.add(whale_address)
            self.disabled_whales.discard(whale_address)
        else:
            self.active_whales.discard(whale_address)
            self.disabled_whales.add(whale_address)

        # Record transition
        state_info.transitions.append((
            datetime.now(),
            new_state,
            trigger,
            reason
        ))

        # Create state change event
        event = StateChangeEvent(
            whale_address=whale_address,
            old_state=old_state,
            new_state=new_state,
            trigger=trigger,
            reason=reason,
            timestamp=datetime.now(),
            metrics={
                "consecutive_wins": str(state_info.consecutive_wins),
                "consecutive_losses": str(state_info.consecutive_losses),
                "quality_score": f"{float(state_info.recent_quality_score):.0f}",
                "max_correlation": f"{float(state_info.max_correlation)*100:.0f}%"
            }
        )
        self.state_changes.append(event)

        if new_state in [WhaleState.DISABLED_PERFORMANCE, WhaleState.DISABLED_CORRELATION, WhaleState.DISABLED_MANUAL]:
            self.total_disables += 1

        logger.info(
            f"State transition: {whale_address[:10]}... | "
            f"{old_state.value} → {new_state.value} | "
            f"Trigger: {trigger.value} | "
            f"Reason: {reason}"
        )

    def get_statistics(self) -> Dict:
        """Get adaptive selector statistics"""
        return {
            "total_whales": len(self.whale_states),
            "active_whales": len(self.active_whales),
            "disabled_whales": len(self.disabled_whales),
            "state_distribution": {
                state.value: sum(1 for s in self.whale_states.values() if s.current_state == state)
                for state in WhaleState
            },
            "transitions": {
                "total_disables": self.total_disables,
                "total_enables": self.total_enables,
                "performance_disables": self.performance_disables,
                "correlation_disables": self.correlation_disables,
                "manual_overrides": self.manual_overrides
            },
            "recent_state_changes": len(self.state_changes)
        }


# ==================== Example Usage ====================

def main():
    """Example usage of WhaleAdaptiveSelector"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize selector
    selector = WhaleAdaptiveSelector()

    print("\n=== Whale Adaptive Selector Test ===\n")

    # Register some whales
    print("=== Registering Whales ===")
    whales = [f"0x{i:040x}" for i in range(5)]

    # Whale 0: Start enabled (top performer)
    selector.register_whale(whales[0], WhaleState.ENABLED, quality_score=Decimal("85"))

    # Whale 1: Start in probation (new whale)
    selector.register_whale(whales[1], WhaleState.PROBATION, quality_score=Decimal("60"))

    # Whale 2: Start enabled
    selector.register_whale(whales[2], WhaleState.ENABLED, quality_score=Decimal("75"))

    print(f"Active whales: {len(selector.get_enabled_whales())}\n")

    # Scenario 1: Whale 0 has losing streak → should disable
    print("=== Scenario 1: Losing Streak (Whale 0) ===")
    for i in range(6):
        selector.update_performance(whales[0], trade_won=False, quality_score=Decimal("70"))
        print(f"Loss {i+1}: State = {selector.get_whale_state(whales[0]).current_state.value}")

    print(f"\nActive whales: {len(selector.get_enabled_whales())}")
    print(f"Disabled whales: {len(selector.get_disabled_whales())}\n")

    # Scenario 2: Whale 0 recovers with wins → should re-enable
    print("=== Scenario 2: Recovery (Whale 0) ===")
    import time
    time.sleep(1)  # Simulate time passing
    for i in range(3):
        selector.update_performance(whales[0], trade_won=True, quality_score=Decimal("80"))
        print(f"Win {i+1}: State = {selector.get_whale_state(whales[0]).current_state.value}")

    print(f"\nActive whales: {len(selector.get_enabled_whales())}\n")

    # Scenario 3: High correlation disables whale
    print("=== Scenario 3: Correlation Disable (Whale 2) ===")
    correlations = {
        (whales[0], whales[2]): Decimal("0.85"),  # High correlation
    }
    selector.update_correlations(correlations)
    whale2_state = selector.get_whale_state(whales[2])
    print(f"Whale 2 max correlation: {float(whale2_state.max_correlation)*100:.0f}%")
    print(f"Whale 2 state: {whale2_state.current_state.value}\n")

    # Scenario 4: Manual override
    print("=== Scenario 4: Manual Override ===")
    selector.manual_override_state(
        whales[2],
        WhaleState.ENABLED,
        "Admin override - strategic whale needed"
    )
    print(f"Whale 2 state after override: {selector.get_whale_state(whales[2]).current_state.value}\n")

    # Get recent state changes
    print("=== Recent State Changes ===")
    recent_changes = selector.get_state_changes(limit=10)
    for change in recent_changes:
        print(f"{change.timestamp.strftime('%H:%M:%S')} | {change.whale_address[:10]}... | "
              f"{change.old_state.value} → {change.new_state.value} | {change.reason}")

    # Get statistics
    print("\n=== Statistics ===")
    import json
    stats = selector.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
