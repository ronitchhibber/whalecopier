"""
Week 10: Edge Detection & Decay - CUSUM Edge Decay Detector

This module implements CUSUM (Cumulative Sum) algorithm for detecting edge decay:
- Detects regime changes in whale/market performance
- Alerts on significant edge decay
- Reduces allocation to decaying whales
- Auto-disables whales with sustained negative edge

CUSUM algorithm:
- S+ = max(0, S+ + (x - μ - k)) for detecting upward shifts
- S- = max(0, S- + (μ - k - x)) for detecting downward shifts
- Alert when S+ or S- exceeds threshold H

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class RegimeState(Enum):
    """Performance regime states"""
    EXCELLENT = "excellent"
    GOOD = "good"
    NORMAL = "normal"
    DECLINING = "declining"
    POOR = "poor"


@dataclass
class CUSUMConfig:
    """Configuration for CUSUM detector"""

    # CUSUM parameters
    reference_edge: Decimal = Decimal("0.10")  # Target edge (μ)
    slack_parameter: Decimal = Decimal("0.02")  # k (allowable deviation)
    threshold_parameter: Decimal = Decimal("0.15")  # H (detection threshold)

    # Action thresholds
    reduce_allocation_threshold: Decimal = Decimal("0.10")  # Reduce allocation when S- > 0.10
    disable_threshold: Decimal = Decimal("0.20")  # Disable when S- > 0.20

    # Update frequency
    update_interval_seconds: int = 300


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    whale_address: str
    market_id: str
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl_usd: Decimal
    is_open: bool


@dataclass
class CUSUMState:
    """CUSUM state for a whale"""
    entity_id: str
    entity_type: str  # "whale" or "market"

    # CUSUM statistics
    S_plus: Decimal  # Upward CUSUM
    S_minus: Decimal  # Downward CUSUM

    # Current metrics
    current_edge: Decimal
    mean_edge: Decimal
    recent_trades: int

    # Regime
    regime_state: RegimeState
    regime_change_detected: bool
    last_regime_change: Optional[datetime]

    # Actions
    should_reduce_allocation: bool
    should_disable: bool
    allocation_multiplier: Decimal  # 0.0 to 1.0

    # History
    edge_history: List[Decimal]
    cusum_history: List[Decimal]

    calculation_time: datetime


class CUSUMEdgeDecayDetector:
    """
    CUSUM (Cumulative Sum) algorithm for edge decay detection.

    CUSUM is a change detection algorithm that accumulates deviations from a reference value.
    When cumulative deviation exceeds a threshold, it signals a regime change.

    Formula:
    - S+ = max(0, S+ + (x - μ - k))  # Detects performance improvement
    - S- = max(0, S- + (μ - k - x))  # Detects performance degradation

    Where:
    - x = current edge
    - μ = reference edge (target)
    - k = slack parameter (allowable deviation)
    - H = threshold (detection sensitivity)

    When S- > H, edge decay is detected.
    """

    def __init__(self, config: CUSUMConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.cusum_states: Dict[str, CUSUMState] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("CUSUMEdgeDecayDetector initialized")

    async def start(self):
        """Start detector"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("CUSUMEdgeDecayDetector started")

    async def stop(self):
        """Stop detector"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("CUSUMEdgeDecayDetector stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                await self.update_all_cusum()
                logger.info(f"CUSUM update complete - {len(self.cusum_states)} entities monitored")
                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"CUSUM update error: {e}", exc_info=True)
                await asyncio.sleep(30)

    def add_trade(self, trade: Trade):
        """Add trade"""
        self.trades.append(trade)

    async def update_all_cusum(self):
        """Update CUSUM for all whales"""
        whales = set(t.whale_address for t in self.trades if not t.is_open)

        for whale in whales:
            state = await self.update_cusum(whale, "whale")
            self.cusum_states[whale] = state

            # Log regime changes
            if state.regime_change_detected:
                logger.warning(
                    f"REGIME CHANGE - Whale {whale[:10]}...: {state.regime_state.value} "
                    f"(Edge: {state.current_edge:.3f}, S-: {state.S_minus:.3f})"
                )

            # Log allocation changes
            if state.should_reduce_allocation:
                logger.warning(
                    f"REDUCING ALLOCATION - Whale {whale[:10]}...: {state.allocation_multiplier:.0%} "
                    f"(Edge decay detected: S- = {state.S_minus:.3f})"
                )

    async def update_cusum(self, entity_id: str, entity_type: str) -> CUSUMState:
        """Update CUSUM state"""

        # Get previous state
        prev_state = self.cusum_states.get(entity_id)

        # Get entity trades
        if entity_type == "whale":
            trades = [t for t in self.trades if t.whale_address == entity_id and not t.is_open]
        else:
            trades = [t for t in self.trades if t.market_id == entity_id and not t.is_open]

        if not trades:
            return self._create_empty_state(entity_id, entity_type)

        # Calculate current edge
        current_edge = self._calculate_edge(trades)

        # Initialize CUSUM values
        if prev_state:
            S_plus = prev_state.S_plus
            S_minus = prev_state.S_minus
            edge_history = prev_state.edge_history + [current_edge]
            cusum_history = prev_state.cusum_history
        else:
            S_plus = Decimal("0")
            S_minus = Decimal("0")
            edge_history = [current_edge]
            cusum_history = []

        # CUSUM update
        mu = self.config.reference_edge
        k = self.config.slack_parameter

        # Upward CUSUM: S+ = max(0, S+ + (x - μ - k))
        S_plus = max(Decimal("0"), S_plus + (current_edge - mu - k))

        # Downward CUSUM: S- = max(0, S- + (μ - k - x))
        S_minus = max(Decimal("0"), S_minus + (mu - k - current_edge))

        cusum_history.append(S_minus)

        # Determine regime
        H = self.config.threshold_parameter

        if S_minus > self.config.disable_threshold:
            regime = RegimeState.POOR
        elif S_minus > self.config.reduce_allocation_threshold:
            regime = RegimeState.DECLINING
        elif S_plus > H:
            regime = RegimeState.EXCELLENT
        elif current_edge >= self.config.reference_edge:
            regime = RegimeState.GOOD
        else:
            regime = RegimeState.NORMAL

        # Detect regime change
        regime_change_detected = False
        last_regime_change = prev_state.last_regime_change if prev_state else None

        if prev_state and prev_state.regime_state != regime:
            regime_change_detected = True
            last_regime_change = datetime.now()

        # Determine actions
        should_reduce = S_minus > self.config.reduce_allocation_threshold
        should_disable = S_minus > self.config.disable_threshold

        # Calculate allocation multiplier
        if should_disable:
            allocation_multiplier = Decimal("0")
        elif should_reduce:
            # Linear reduction based on S-
            reduction_factor = (S_minus - self.config.reduce_allocation_threshold) / (self.config.disable_threshold - self.config.reduce_allocation_threshold)
            allocation_multiplier = Decimal("1") - reduction_factor
            allocation_multiplier = max(Decimal("0.25"), allocation_multiplier)  # Min 25%
        else:
            allocation_multiplier = Decimal("1.0")

        # Calculate mean edge
        mean_edge = sum(edge_history) / Decimal(str(len(edge_history)))

        return CUSUMState(
            entity_id=entity_id,
            entity_type=entity_type,
            S_plus=S_plus,
            S_minus=S_minus,
            current_edge=current_edge,
            mean_edge=mean_edge,
            recent_trades=len(trades),
            regime_state=regime,
            regime_change_detected=regime_change_detected,
            last_regime_change=last_regime_change,
            should_reduce_allocation=should_reduce,
            should_disable=should_disable,
            allocation_multiplier=allocation_multiplier,
            edge_history=edge_history[-30:],  # Keep last 30
            cusum_history=cusum_history[-30:],
            calculation_time=datetime.now()
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

    def get_decaying_whales(self) -> List[CUSUMState]:
        """Get whales with detected edge decay"""
        return [
            state for state in self.cusum_states.values()
            if state.regime_state in [RegimeState.DECLINING, RegimeState.POOR]
        ]

    def get_allocation_multiplier(self, whale_address: str) -> Decimal:
        """Get allocation multiplier for a whale"""
        state = self.cusum_states.get(whale_address)
        return state.allocation_multiplier if state else Decimal("1.0")

    def _create_empty_state(self, entity_id: str, entity_type: str) -> CUSUMState:
        """Create empty CUSUM state"""
        return CUSUMState(
            entity_id=entity_id,
            entity_type=entity_type,
            S_plus=Decimal("0"),
            S_minus=Decimal("0"),
            current_edge=Decimal("0"),
            mean_edge=Decimal("0"),
            recent_trades=0,
            regime_state=RegimeState.NORMAL,
            regime_change_detected=False,
            last_regime_change=None,
            should_reduce_allocation=False,
            should_disable=False,
            allocation_multiplier=Decimal("1.0"),
            edge_history=[],
            cusum_history=[],
            calculation_time=datetime.now()
        )

    def print_cusum_summary(self):
        """Print CUSUM summary"""
        print(f"\n{'='*100}")
        print("CUSUM EDGE DECAY DETECTION SUMMARY")
        print(f"{'='*100}\n")

        # Group by regime
        by_regime: Dict[RegimeState, List[CUSUMState]] = {}
        for state in self.cusum_states.values():
            if state.regime_state not in by_regime:
                by_regime[state.regime_state] = []
            by_regime[state.regime_state].append(state)

        for regime in RegimeState:
            states = by_regime.get(regime, [])
            if not states:
                continue

            print(f"\n{regime.value.upper()} ({len(states)} whales):")
            print(f"{'Whale':<25}{'Edge':<10}{'S+':<10}{'S-':<10}{'Allocation':<12}{'Trades':<8}")
            print("-" * 100)

            for state in sorted(states, key=lambda s: s.S_minus, reverse=True)[:10]:
                print(
                    f"{state.entity_id[:23]:<25}"
                    f"{state.current_edge:>8.3f}  "
                    f"{state.S_plus:>8.3f}  "
                    f"{state.S_minus:>8.3f}  "
                    f"{state.allocation_multiplier:>10.0%}  "
                    f"{state.recent_trades:<8}"
                )

        # Decaying whales
        decaying = self.get_decaying_whales()
        if decaying:
            print(f"\n\nWARNING - {len(decaying)} WHALES WITH EDGE DECAY:")
            for state in decaying:
                action = "DISABLED" if state.should_disable else f"REDUCED to {state.allocation_multiplier:.0%}"
                print(f"  {state.entity_id[:30]:<30} S-: {state.S_minus:.3f} - {action}")

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = CUSUMConfig()
        detector = CUSUMEdgeDecayDetector(config)

        # Simulate edge decay
        print("Simulating edge decay scenario...")

        # Initial good performance
        for i in range(30):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address="0xwhale_declining",
                market_id="market_1",
                entry_time=datetime.now() - timedelta(days=60-i),
                exit_time=datetime.now() - timedelta(days=60-i-1),
                pnl_usd=Decimal("50"),  # Good edge initially
                is_open=False
            )
            detector.add_trade(trade)

        # Performance degrades
        for i in range(30, 60):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address="0xwhale_declining",
                market_id="market_1",
                entry_time=datetime.now() - timedelta(days=60-i),
                exit_time=datetime.now() - timedelta(days=60-i-1),
                pnl_usd=Decimal("-30") if i % 2 == 0 else Decimal("10"),  # Edge decays
                is_open=False
            )
            detector.add_trade(trade)

        # Update CUSUM
        await detector.update_all_cusum()

        # Print results
        detector.print_cusum_summary()

        print("\nCUSUM edge decay detector demo complete!")

    asyncio.run(main())
