"""
Week 10: Edge Detection & Decay - Whale Lifecycle Tracker

This module tracks whale performance lifecycle:
- Discovery phase (new whale identified)
- Hot streak phase (consistent outperformance)
- Decline phase (performance degradation)
- Retirement phase (sustained underperformance)

Goals:
- Identify typical lifecycle patterns
- Predict edge decay before it happens
- Proactively rotate to new whales
- Maximize allocation to whales in hot streak phase

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class LifecyclePhase(Enum):
    """Whale lifecycle phases"""
    DISCOVERY = "discovery"      # Just identified, limited data
    EVALUATION = "evaluation"    # Accumulating performance data
    HOT_STREAK = "hot_streak"    # Consistently outperforming
    MATURE = "mature"            # Stable performance
    DECLINING = "declining"      # Performance deteriorating
    RETIRED = "retired"          # Sustained underperformance


@dataclass
class LifecycleConfig:
    """Configuration for lifecycle tracking"""

    # Phase thresholds
    discovery_trades_threshold: int = 10
    hot_streak_edge_threshold: Decimal = Decimal("0.15")
    hot_streak_min_trades: int = 20
    declining_edge_threshold: Decimal = Decimal("0.05")
    retirement_edge_threshold: Decimal = Decimal("0.00")

    # Lookback windows
    hot_streak_lookback_days: int = 30
    declining_lookback_days: int = 14

    # Update frequency
    update_interval_seconds: int = 300


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    whale_address: str
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl_usd: Decimal
    is_open: bool


@dataclass
class WhaleLifecycleState:
    """Lifecycle state for a whale"""

    whale_address: str
    calculation_time: datetime

    # Phase
    current_phase: LifecyclePhase
    phase_duration_days: int
    days_since_discovery: int

    # Performance
    lifetime_edge: Decimal
    recent_edge: Decimal  # Last 30 days
    edge_trend: str  # "improving", "stable", "declining"

    # Trade count
    lifetime_trades: int
    recent_trades: int  # Last 30 days

    # P&L
    lifetime_pnl: Decimal
    recent_pnl: Decimal

    # Lifecycle events
    discovery_date: datetime
    hot_streak_start: Optional[datetime]
    decline_start: Optional[datetime]
    retirement_date: Optional[datetime]

    # Predictions
    predicted_lifecycle_days: int  # Expected total lifecycle
    predicted_decline_date: Optional[datetime]  # When decline expected
    days_until_rotation: int  # Days before should rotate

    # Actions
    allocation_recommendation: Decimal  # 0.0 to 1.5 (can exceed 1.0 in hot streak)
    should_increase_allocation: bool
    should_decrease_allocation: bool
    should_retire: bool


class WhaleLifecycleTracker:
    """
    Tracks whale performance lifecycle from discovery to retirement.

    Typical lifecycle pattern:
    1. Discovery (0-10 trades): New whale identified
    2. Evaluation (10-30 trades): Assess performance
    3. Hot Streak (edge > 0.15): Peak performance
    4. Mature (stable edge): Consistent performance
    5. Declining (edge < 0.05): Performance degrading
    6. Retired (edge ≤ 0): Sustained underperformance

    Applications:
    - Maximize allocation during hot streaks
    - Reduce allocation during decline
    - Proactively rotate before retirement
    - Identify typical lifecycle patterns
    """

    def __init__(self, config: LifecycleConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.whale_states: Dict[str, WhaleLifecycleState] = {}
        self.whale_discovery_dates: Dict[str, datetime] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("WhaleLifecycleTracker initialized")

    async def start(self):
        """Start tracker"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("WhaleLifecycleTracker started")

    async def stop(self):
        """Stop tracker"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("WhaleLifecycleTracker stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                await self.update_all_lifecycles()
                logger.info(f"Lifecycle update complete - {len(self.whale_states)} whales tracked")
                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"Lifecycle update error: {e}", exc_info=True)
                await asyncio.sleep(30)

    def add_trade(self, trade: Trade):
        """Add trade and auto-discover whale"""
        self.trades.append(trade)

        # Auto-discover whale
        if trade.whale_address not in self.whale_discovery_dates:
            self.whale_discovery_dates[trade.whale_address] = trade.entry_time
            logger.info(f"New whale discovered: {trade.whale_address[:10]}...")

    async def update_all_lifecycles(self):
        """Update lifecycle for all whales"""
        whales = set(t.whale_address for t in self.trades)

        for whale in whales:
            state = await self.update_lifecycle(whale)
            self.whale_states[whale] = state

            # Log phase transitions
            prev_state = self.whale_states.get(whale)
            if prev_state and prev_state.current_phase != state.current_phase:
                logger.info(
                    f"PHASE TRANSITION - Whale {whale[:10]}...: "
                    f"{prev_state.current_phase.value} → {state.current_phase.value}"
                )

    async def update_lifecycle(self, whale_address: str) -> WhaleLifecycleState:
        """Update lifecycle state for a whale"""

        # Get whale trades
        whale_trades = [t for t in self.trades if t.whale_address == whale_address and not t.is_open]

        if not whale_trades:
            return self._create_empty_state(whale_address)

        # Discovery date
        discovery_date = self.whale_discovery_dates.get(whale_address, whale_trades[0].entry_time)
        days_since_discovery = (datetime.now() - discovery_date).days

        # Calculate metrics
        lifetime_trades = len(whale_trades)
        lifetime_edge = self._calculate_edge(whale_trades)
        lifetime_pnl = sum(t.pnl_usd for t in whale_trades)

        # Recent metrics (30 days)
        cutoff_30d = datetime.now() - timedelta(days=30)
        recent_trades_list = [t for t in whale_trades if t.exit_time and t.exit_time >= cutoff_30d]
        recent_trades_count = len(recent_trades_list)
        recent_edge = self._calculate_edge(recent_trades_list) if recent_trades_list else Decimal("0")
        recent_pnl = sum(t.pnl_usd for t in recent_trades_list)

        # Edge trend
        cutoff_7d = datetime.now() - timedelta(days=7)
        week_trades = [t for t in whale_trades if t.exit_time and t.exit_time >= cutoff_7d]
        week_edge = self._calculate_edge(week_trades) if week_trades else Decimal("0")

        if week_edge > recent_edge * Decimal("1.10"):
            edge_trend = "improving"
        elif week_edge < recent_edge * Decimal("0.90"):
            edge_trend = "declining"
        else:
            edge_trend = "stable"

        # Determine phase
        current_phase, phase_events = self._determine_phase(
            lifetime_trades, recent_trades_count, lifetime_edge, recent_edge, edge_trend
        )

        # Calculate phase duration
        prev_state = self.whale_states.get(whale_address)
        if prev_state and prev_state.current_phase == current_phase:
            phase_duration_days = prev_state.phase_duration_days + 1
        else:
            phase_duration_days = 0

        # Allocation recommendation
        allocation = self._calculate_allocation_recommendation(current_phase, recent_edge, edge_trend)
        should_increase = current_phase == LifecyclePhase.HOT_STREAK and allocation > Decimal("1.0")
        should_decrease = current_phase in [LifecyclePhase.DECLINING, LifecyclePhase.RETIRED]
        should_retire = current_phase == LifecyclePhase.RETIRED

        # Predictions
        predicted_lifecycle = self._predict_lifecycle_duration(days_since_discovery, current_phase)
        predicted_decline = self._predict_decline_date(discovery_date, current_phase, edge_trend)
        days_until_rotation = self._calculate_rotation_timing(current_phase, phase_duration_days, edge_trend)

        return WhaleLifecycleState(
            whale_address=whale_address,
            calculation_time=datetime.now(),
            current_phase=current_phase,
            phase_duration_days=phase_duration_days,
            days_since_discovery=days_since_discovery,
            lifetime_edge=lifetime_edge,
            recent_edge=recent_edge,
            edge_trend=edge_trend,
            lifetime_trades=lifetime_trades,
            recent_trades=recent_trades_count,
            lifetime_pnl=lifetime_pnl,
            recent_pnl=recent_pnl,
            discovery_date=discovery_date,
            hot_streak_start=phase_events.get("hot_streak_start"),
            decline_start=phase_events.get("decline_start"),
            retirement_date=phase_events.get("retirement_date"),
            predicted_lifecycle_days=predicted_lifecycle,
            predicted_decline_date=predicted_decline,
            days_until_rotation=days_until_rotation,
            allocation_recommendation=allocation,
            should_increase_allocation=should_increase,
            should_decrease_allocation=should_decrease,
            should_retire=should_retire
        )

    def _calculate_edge(self, trades: List[Trade]) -> Decimal:
        """Calculate edge from trades"""
        if not trades:
            return Decimal("0")

        winning = [t for t in trades if t.pnl_usd > 0]
        losing = [t for t in trades if t.pnl_usd < 0]

        total = len(trades)
        win_rate = Decimal(str(len(winning))) / Decimal(str(total))
        loss_rate = Decimal(str(len(losing))) / Decimal(str(total))

        avg_win = sum(t.pnl_usd for t in winning) / Decimal(str(len(winning))) if winning else Decimal("0")
        avg_loss = abs(sum(t.pnl_usd for t in losing) / Decimal(str(len(losing)))) if losing else Decimal("0")

        edge = (win_rate * avg_win) - (loss_rate * avg_loss)
        return edge

    def _determine_phase(self, lifetime_trades: int, recent_trades: int,
                        lifetime_edge: Decimal, recent_edge: Decimal, trend: str) -> Tuple[LifecyclePhase, Dict]:
        """Determine current lifecycle phase"""

        events = {}

        # Discovery
        if lifetime_trades < self.config.discovery_trades_threshold:
            return LifecyclePhase.DISCOVERY, events

        # Evaluation
        if lifetime_trades < self.config.hot_streak_min_trades:
            return LifecyclePhase.EVALUATION, events

        # Retired
        if recent_edge <= self.config.retirement_edge_threshold:
            events["retirement_date"] = datetime.now()
            return LifecyclePhase.RETIRED, events

        # Declining
        if recent_edge < self.config.declining_edge_threshold:
            events["decline_start"] = datetime.now()
            return LifecyclePhase.DECLINING, events

        # Hot streak
        if recent_edge >= self.config.hot_streak_edge_threshold:
            events["hot_streak_start"] = datetime.now()
            return LifecyclePhase.HOT_STREAK, events

        # Mature
        return LifecyclePhase.MATURE, events

    def _calculate_allocation_recommendation(self, phase: LifecyclePhase,
                                            recent_edge: Decimal, trend: str) -> Decimal:
        """Calculate recommended allocation multiplier"""

        if phase == LifecyclePhase.DISCOVERY:
            return Decimal("0.25")  # 25% allocation (testing)
        elif phase == LifecyclePhase.EVALUATION:
            return Decimal("0.50")  # 50% allocation
        elif phase == LifecyclePhase.HOT_STREAK:
            return Decimal("1.50")  # 150% allocation (overweight)
        elif phase == LifecyclePhase.MATURE:
            return Decimal("1.00")  # 100% allocation (normal)
        elif phase == LifecyclePhase.DECLINING:
            return Decimal("0.25")  # 25% allocation (reducing)
        elif phase == LifecyclePhase.RETIRED:
            return Decimal("0.00")  # 0% allocation (stopped)
        else:
            return Decimal("1.00")

    def _predict_lifecycle_duration(self, days_since_discovery: int, phase: LifecyclePhase) -> int:
        """Predict total lifecycle duration"""

        # Based on typical patterns (simplified)
        # In reality, would use historical data
        if phase in [LifecyclePhase.DISCOVERY, LifecyclePhase.EVALUATION]:
            return 180  # 6 months typical
        elif phase == LifecyclePhase.HOT_STREAK:
            return 120  # 4 months hot streak
        else:
            return 90  # 3 months decline/retirement

    def _predict_decline_date(self, discovery_date: datetime, phase: LifecyclePhase, trend: str) -> Optional[datetime]:
        """Predict when decline will begin"""

        if phase in [LifecyclePhase.DECLINING, LifecyclePhase.RETIRED]:
            return None  # Already declining

        # Estimate based on phase and trend
        if phase == LifecyclePhase.HOT_STREAK:
            days_until_decline = 60 if trend == "stable" else 30
        elif phase == LifecyclePhase.MATURE:
            days_until_decline = 45 if trend == "stable" else 20
        else:
            days_until_decline = 90

        return datetime.now() + timedelta(days=days_until_decline)

    def _calculate_rotation_timing(self, phase: LifecyclePhase, phase_duration: int, trend: str) -> int:
        """Calculate days until should rotate to new whale"""

        if phase == LifecyclePhase.RETIRED:
            return 0  # Rotate now
        elif phase == LifecyclePhase.DECLINING:
            return max(0, 14 - phase_duration)  # Rotate within 14 days
        elif trend == "declining":
            return 30  # Start planning rotation
        else:
            return 90  # No urgent need

    def get_hot_streak_whales(self) -> List[WhaleLifecycleState]:
        """Get whales in hot streak phase"""
        return [s for s in self.whale_states.values() if s.current_phase == LifecyclePhase.HOT_STREAK]

    def get_declining_whales(self) -> List[WhaleLifecycleState]:
        """Get whales in declining phase"""
        return [s for s in self.whale_states.values() if s.current_phase == LifecyclePhase.DECLINING]

    def get_rotation_candidates(self) -> List[WhaleLifecycleState]:
        """Get whales that should be rotated soon"""
        return [s for s in self.whale_states.values() if s.days_until_rotation <= 7]

    def _create_empty_state(self, whale_address: str) -> WhaleLifecycleState:
        """Create empty state"""
        return WhaleLifecycleState(
            whale_address=whale_address,
            calculation_time=datetime.now(),
            current_phase=LifecyclePhase.DISCOVERY,
            phase_duration_days=0,
            days_since_discovery=0,
            lifetime_edge=Decimal("0"),
            recent_edge=Decimal("0"),
            edge_trend="stable",
            lifetime_trades=0,
            recent_trades=0,
            lifetime_pnl=Decimal("0"),
            recent_pnl=Decimal("0"),
            discovery_date=datetime.now(),
            hot_streak_start=None,
            decline_start=None,
            retirement_date=None,
            predicted_lifecycle_days=0,
            predicted_decline_date=None,
            days_until_rotation=999,
            allocation_recommendation=Decimal("0"),
            should_increase_allocation=False,
            should_decrease_allocation=False,
            should_retire=False
        )

    def print_lifecycle_summary(self):
        """Print lifecycle summary"""
        print(f"\n{'='*100}")
        print("WHALE LIFECYCLE SUMMARY")
        print(f"{'='*100}\n")

        # Group by phase
        by_phase: Dict[LifecyclePhase, List[WhaleLifecycleState]] = {}
        for state in self.whale_states.values():
            if state.current_phase not in by_phase:
                by_phase[state.current_phase] = []
            by_phase[state.current_phase].append(state)

        for phase in LifecyclePhase:
            states = by_phase.get(phase, [])
            if not states:
                continue

            print(f"\n{phase.value.upper()} ({len(states)} whales):")
            print(f"{'Whale':<25}{'Days':<8}{'Edge':<10}{'Alloc':<10}{'P&L':<15}{'Action':<20}")
            print("-" * 100)

            for state in sorted(states, key=lambda s: s.recent_edge, reverse=True)[:10]:
                action = "INCREASE" if state.should_increase_allocation else ("RETIRE" if state.should_retire else ("DECREASE" if state.should_decrease_allocation else "-"))

                print(
                    f"{state.whale_address[:23]:<25}"
                    f"{state.days_since_discovery:<8}"
                    f"{state.recent_edge:>8.3f}  "
                    f"{state.allocation_recommendation:>8.0%}  "
                    f"${state.lifetime_pnl:>12,.2f}  "
                    f"{action:<20}"
                )

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = LifecycleConfig()
        tracker = WhaleLifecycleTracker(config)

        # Simulate whale lifecycle
        print("Simulating whale lifecycle...")

        # Hot streak whale
        for i in range(50):
            trade = Trade(
                trade_id=f"trade_hot_{i}",
                whale_address="0xwhale_hotstreak",
                entry_time=datetime.now() - timedelta(days=60-i),
                exit_time=datetime.now() - timedelta(days=60-i-1),
                pnl_usd=Decimal("80"),
                is_open=False
            )
            tracker.add_trade(trade)

        # Declining whale
        for i in range(50):
            pnl = Decimal("50") if i < 30 else Decimal("-20")
            trade = Trade(
                trade_id=f"trade_decline_{i}",
                whale_address="0xwhale_declining",
                entry_time=datetime.now() - timedelta(days=60-i),
                exit_time=datetime.now() - timedelta(days=60-i-1),
                pnl_usd=pnl,
                is_open=False
            )
            tracker.add_trade(trade)

        # Update lifecycles
        await tracker.update_all_lifecycles()

        # Print summary
        tracker.print_lifecycle_summary()

        print("\nWhale lifecycle tracker demo complete!")

    asyncio.run(main())
