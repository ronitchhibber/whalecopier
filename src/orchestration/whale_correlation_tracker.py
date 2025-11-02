"""
Real-Time Whale Correlation Tracker
Week 6: Multi-Whale Orchestration - CRITICAL CORRELATION RISK PREVENTION
🚨 MANDATORY IMPLEMENTATION - Prevents over-leverage disaster from whale overlap
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class TradeDecision(Enum):
    """Trade execution decision"""
    PROCEED_NORMAL = "PROCEED_NORMAL"          # Normal 1x sizing
    PROCEED_AMPLIFIED = "PROCEED_AMPLIFIED"    # Size up 1.5x (3+ whales, low overlap)
    SKIP_OVERLAPPED = "SKIP_OVERLAPPED"        # Skip (>30% overlap)
    SKIP_CONFLICTED = "SKIP_CONFLICTED"        # Skip (whales on opposite sides)


@dataclass
class WhalePosition:
    """Active whale position in a market"""
    whale_address: str
    market_id: str
    outcome: str  # YES or NO
    size_usd: Decimal
    entry_time: datetime
    is_active: bool = True


@dataclass
class MarketOverlap:
    """Whale overlap statistics for a market"""
    market_id: str
    total_whales: int
    whales_on_yes: Set[str]
    whales_on_no: Set[str]
    overlap_percentage: Decimal  # % of active whales in this market
    total_exposure: Decimal
    timestamp: datetime


@dataclass
class CorrelationWarning:
    """Warning about dangerous whale overlap"""
    severity: str  # WARNING, CRITICAL
    market_id: str
    whale_count: int
    overlap_percentage: Decimal
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TradeEvaluation:
    """Result of evaluating a potential trade"""
    decision: TradeDecision
    size_multiplier: Decimal  # 0 (skip), 1.0 (normal), or 1.5 (amplified)
    reason: str
    market_overlap: Optional[MarketOverlap] = None
    warnings: List[CorrelationWarning] = field(default_factory=list)


@dataclass
class CorrelationConfig:
    """Configuration for correlation tracking"""
    # Overlap thresholds
    max_overlap_pct: Decimal = Decimal("0.30")  # 30% - SKIP trade
    amplify_overlap_threshold: Decimal = Decimal("0.20")  # 20% - OK to size up
    min_whales_for_amplify: int = 3  # Need 3+ agreeing whales

    # Size multipliers
    normal_multiplier: Decimal = Decimal("1.0")
    amplify_multiplier: Decimal = Decimal("1.5")  # Size up 50%

    # Tracking
    max_position_age_hours: int = 72  # Clean up old positions


# ==================== Whale Correlation Tracker ====================

class WhaleCorrelationTracker:
    """
    Real-Time Whale Correlation Tracker

    🚨 CRITICAL SYSTEM - Prevents over-leverage disaster

    Research Finding: Top 10 whales trade same markets 42% of time
    → Naive copying = 2x effective exposure on correlated bets

    Core Logic:
    1. Track all active whale positions by market
    2. Calculate overlap when new whale trade detected
    3. If overlap >30% → SKIP TRADE (danger zone)
    4. If 3+ whales agree with <20% overlap → SIZE UP 1.5x (confidence signal)
    5. If whales on opposite sides → SKIP (conflicted signal)

    Success Metric: ZERO overleveraged positions
    """

    def __init__(self, config: Optional[CorrelationConfig] = None):
        """
        Initialize correlation tracker

        Args:
            config: Correlation configuration
        """
        self.config = config or CorrelationConfig()

        # Active positions tracking
        self.whale_positions: Dict[str, List[WhalePosition]] = defaultdict(list)  # whale_address -> positions
        self.market_positions: Dict[str, List[WhalePosition]] = defaultdict(list)  # market_id -> positions

        # Statistics
        self.trades_evaluated = 0
        self.trades_skipped_overlap = 0
        self.trades_skipped_conflict = 0
        self.trades_amplified = 0
        self.warnings: List[CorrelationWarning] = []

        logger.warning(
            "🚨 CORRELATION TRACKER ACTIVE - Over-leverage protection enabled | "
            f"Max overlap: {float(self.config.max_overlap_pct)*100}%"
        )

    def register_whale_position(
        self,
        whale_address: str,
        market_id: str,
        outcome: str,
        size_usd: Decimal
    ):
        """
        Register a new whale position

        Args:
            whale_address: Whale address
            market_id: Market identifier
            outcome: YES or NO
            size_usd: Position size
        """
        position = WhalePosition(
            whale_address=whale_address,
            market_id=market_id,
            outcome=outcome,
            size_usd=size_usd,
            entry_time=datetime.now()
        )

        self.whale_positions[whale_address].append(position)
        self.market_positions[market_id].append(position)

        # Check for warnings
        self._check_market_overlap(market_id)

        logger.debug(
            f"Registered position: {whale_address[:10]}... in {market_id[:15]}... | "
            f"Outcome: {outcome} | Size: ${float(size_usd):.2f}"
        )

    def close_whale_position(self, whale_address: str, market_id: str):
        """
        Close a whale position

        Args:
            whale_address: Whale address
            market_id: Market identifier
        """
        # Mark position as inactive
        for position in self.whale_positions.get(whale_address, []):
            if position.market_id == market_id and position.is_active:
                position.is_active = False

        for position in self.market_positions.get(market_id, []):
            if position.whale_address == whale_address and position.is_active:
                position.is_active = False

        logger.debug(f"Closed position: {whale_address[:10]}... in {market_id[:15]}...")

    def evaluate_trade(
        self,
        market_id: str,
        outcome: str,
        proposing_whale: str,
        enabled_whales: List[str]
    ) -> TradeEvaluation:
        """
        Evaluate whether to execute a trade based on whale overlap

        Args:
            market_id: Market to trade
            outcome: YES or NO
            proposing_whale: Whale suggesting this trade
            enabled_whales: List of currently enabled whale addresses

        Returns:
            TradeEvaluation with decision and reasoning
        """
        self.trades_evaluated += 1

        # Get active positions in this market
        active_positions = [
            p for p in self.market_positions.get(market_id, [])
            if p.is_active
        ]

        if not active_positions:
            # No overlap - proceed normally
            return TradeEvaluation(
                decision=TradeDecision.PROCEED_NORMAL,
                size_multiplier=self.config.normal_multiplier,
                reason="No whale overlap detected - normal sizing"
            )

        # Calculate overlap
        overlap = self._calculate_market_overlap(market_id, enabled_whales)

        # Check for conflicting positions (whales on opposite sides)
        if len(overlap.whales_on_yes) > 0 and len(overlap.whales_on_no) > 0:
            self.trades_skipped_conflict += 1
            return TradeEvaluation(
                decision=TradeDecision.SKIP_CONFLICTED,
                size_multiplier=Decimal("0"),
                reason=(
                    f"Whale conflict detected: {len(overlap.whales_on_yes)} on YES, "
                    f"{len(overlap.whales_on_no)} on NO - skipping trade"
                ),
                market_overlap=overlap,
                warnings=[CorrelationWarning(
                    severity="WARNING",
                    market_id=market_id,
                    whale_count=overlap.total_whales,
                    overlap_percentage=overlap.overlap_percentage,
                    message="Whales trading opposite sides"
                )]
            )

        # Check for dangerous overlap (>30%)
        if overlap.overlap_percentage > self.config.max_overlap_pct:
            self.trades_skipped_overlap += 1
            return TradeEvaluation(
                decision=TradeDecision.SKIP_OVERLAPPED,
                size_multiplier=Decimal("0"),
                reason=(
                    f"🚨 DANGER: Whale overlap {float(overlap.overlap_percentage)*100:.1f}% "
                    f"> {float(self.config.max_overlap_pct)*100:.1f}% threshold - "
                    f"skipping to prevent over-leverage"
                ),
                market_overlap=overlap,
                warnings=[CorrelationWarning(
                    severity="CRITICAL",
                    market_id=market_id,
                    whale_count=overlap.total_whales,
                    overlap_percentage=overlap.overlap_percentage,
                    message=f"Dangerous overlap: {overlap.total_whales} whales in market"
                )]
            )

        # Check for amplification signal (3+ whales, low overlap)
        whales_on_same_side = (
            overlap.whales_on_yes if outcome == "YES" else overlap.whales_on_no
        )

        if (len(whales_on_same_side) >= self.config.min_whales_for_amplify and
            overlap.overlap_percentage <= self.config.amplify_overlap_threshold):
            self.trades_amplified += 1
            return TradeEvaluation(
                decision=TradeDecision.PROCEED_AMPLIFIED,
                size_multiplier=self.config.amplify_multiplier,
                reason=(
                    f"✅ Strong signal: {len(whales_on_same_side)} whales agree on {outcome} "
                    f"with only {float(overlap.overlap_percentage)*100:.1f}% overlap - sizing up 1.5x"
                ),
                market_overlap=overlap
            )

        # Normal execution
        return TradeEvaluation(
            decision=TradeDecision.PROCEED_NORMAL,
            size_multiplier=self.config.normal_multiplier,
            reason=f"Acceptable overlap ({float(overlap.overlap_percentage)*100:.1f}%) - normal sizing",
            market_overlap=overlap
        )

    def get_market_overlap(self, market_id: str, enabled_whales: List[str]) -> MarketOverlap:
        """Get current overlap statistics for a market"""
        return self._calculate_market_overlap(market_id, enabled_whales)

    def get_high_overlap_markets(self, enabled_whales: List[str], threshold: Decimal = None) -> List[MarketOverlap]:
        """
        Get markets with high whale overlap

        Args:
            enabled_whales: List of enabled whale addresses
            threshold: Overlap threshold (defaults to config max)

        Returns:
            List of markets with overlap above threshold
        """
        if threshold is None:
            threshold = self.config.max_overlap_pct

        high_overlap = []

        for market_id in self.market_positions.keys():
            overlap = self._calculate_market_overlap(market_id, enabled_whales)
            if overlap.overlap_percentage >= threshold:
                high_overlap.append(overlap)

        return sorted(high_overlap, key=lambda x: x.overlap_percentage, reverse=True)

    def cleanup_old_positions(self):
        """Remove stale positions older than configured threshold"""
        cutoff = datetime.now() - timedelta(hours=self.config.max_position_age_hours)
        removed = 0

        for whale_address in list(self.whale_positions.keys()):
            self.whale_positions[whale_address] = [
                p for p in self.whale_positions[whale_address]
                if p.entry_time > cutoff
            ]
            if not self.whale_positions[whale_address]:
                del self.whale_positions[whale_address]

        for market_id in list(self.market_positions.keys()):
            old_count = len(self.market_positions[market_id])
            self.market_positions[market_id] = [
                p for p in self.market_positions[market_id]
                if p.entry_time > cutoff
            ]
            removed += old_count - len(self.market_positions[market_id])
            if not self.market_positions[market_id]:
                del self.market_positions[market_id]

        if removed > 0:
            logger.info(f"Cleaned up {removed} stale positions older than {self.config.max_position_age_hours}h")

    def get_statistics(self) -> Dict:
        """Get comprehensive tracking statistics"""
        active_positions = sum(
            sum(1 for p in positions if p.is_active)
            for positions in self.whale_positions.values()
        )

        skip_rate = (
            (self.trades_skipped_overlap + self.trades_skipped_conflict) / self.trades_evaluated
            if self.trades_evaluated > 0
            else 0
        )

        amplify_rate = (
            self.trades_amplified / self.trades_evaluated
            if self.trades_evaluated > 0
            else 0
        )

        return {
            "trades_evaluated": self.trades_evaluated,
            "trades_skipped": {
                "overlap": self.trades_skipped_overlap,
                "conflict": self.trades_skipped_conflict,
                "total": self.trades_skipped_overlap + self.trades_skipped_conflict,
                "skip_rate": f"{skip_rate*100:.1f}%"
            },
            "trades_amplified": {
                "count": self.trades_amplified,
                "amplify_rate": f"{amplify_rate*100:.1f}%"
            },
            "active_tracking": {
                "positions": active_positions,
                "whales": len(self.whale_positions),
                "markets": len(self.market_positions)
            },
            "recent_warnings": [
                {
                    "severity": w.severity,
                    "market": w.market_id[:15] + "...",
                    "whale_count": w.whale_count,
                    "overlap": f"{float(w.overlap_percentage)*100:.1f}%",
                    "message": w.message
                }
                for w in self.warnings[-10:]  # Last 10 warnings
            ]
        }

    # ==================== Private Methods ====================

    def _calculate_market_overlap(
        self,
        market_id: str,
        enabled_whales: List[str]
    ) -> MarketOverlap:
        """Calculate whale overlap for a specific market"""
        active_positions = [
            p for p in self.market_positions.get(market_id, [])
            if p.is_active
        ]

        whales_on_yes = set()
        whales_on_no = set()
        total_exposure = Decimal("0")

        for position in active_positions:
            if position.outcome == "YES":
                whales_on_yes.add(position.whale_address)
            else:
                whales_on_no.add(position.whale_address)
            total_exposure += position.size_usd

        total_whales_in_market = len(whales_on_yes | whales_on_no)
        total_enabled = len(enabled_whales)

        # Calculate overlap percentage (% of enabled whales in this market)
        overlap_pct = (
            Decimal(str(total_whales_in_market / total_enabled))
            if total_enabled > 0
            else Decimal("0")
        )

        return MarketOverlap(
            market_id=market_id,
            total_whales=total_whales_in_market,
            whales_on_yes=whales_on_yes,
            whales_on_no=whales_on_no,
            overlap_percentage=overlap_pct,
            total_exposure=total_exposure,
            timestamp=datetime.now()
        )

    def _check_market_overlap(self, market_id: str):
        """Check and warn about dangerous market overlap"""
        active_positions = [
            p for p in self.market_positions.get(market_id, [])
            if p.is_active
        ]

        if len(active_positions) < 3:
            return  # Not enough positions to worry about

        unique_whales = len(set(p.whale_address for p in active_positions))

        if unique_whales >= 5:  # 5+ whales in one market
            warning = CorrelationWarning(
                severity="CRITICAL" if unique_whales >= 7 else "WARNING",
                market_id=market_id,
                whale_count=unique_whales,
                overlap_percentage=Decimal("0"),  # Will be calculated properly later
                message=f"{unique_whales} whales concentrated in single market"
            )
            self.warnings.append(warning)

            logger.warning(
                f"🚨 [{warning.severity}] Market concentration detected: "
                f"{market_id[:15]}... has {unique_whales} whales"
            )


# ==================== Example Usage ====================

def main():
    """Example usage of WhaleCorrelationTracker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize tracker
    tracker = WhaleCorrelationTracker()

    print("\n=== Whale Correlation Tracker Test ===\n")

    # Simulate enabled whales
    enabled_whales = [f"0x{i:040x}" for i in range(10)]  # 10 enabled whales

    # Scenario 1: Normal trade (no overlap)
    print("=== Scenario 1: No Overlap ===")
    eval1 = tracker.evaluate_trade(
        market_id="market_election_2024",
        outcome="YES",
        proposing_whale=enabled_whales[0],
        enabled_whales=enabled_whales
    )
    print(f"Decision: {eval1.decision.value}")
    print(f"Size Multiplier: {float(eval1.size_multiplier)}x")
    print(f"Reason: {eval1.reason}\n")

    # Scenario 2: Dangerous overlap (>30%)
    print("=== Scenario 2: Dangerous Overlap ===")

    # Register 4 whales in same market (40% overlap)
    for i in range(4):
        tracker.register_whale_position(
            whale_address=enabled_whales[i],
            market_id="market_hot_topic",
            outcome="YES",
            size_usd=Decimal("1000")
        )

    eval2 = tracker.evaluate_trade(
        market_id="market_hot_topic",
        outcome="YES",
        proposing_whale=enabled_whales[4],
        enabled_whales=enabled_whales
    )
    print(f"Decision: {eval2.decision.value}")
    print(f"Size Multiplier: {float(eval2.size_multiplier)}x")
    print(f"Reason: {eval2.reason}\n")

    # Scenario 3: Strong signal (3+ whales, low overlap)
    print("=== Scenario 3: Strong Signal (Amplify) ===")

    # Register 3 whales in different market (30% overlap, but all agree)
    for i in range(3):
        tracker.register_whale_position(
            whale_address=enabled_whales[i],
            market_id="market_strong_signal",
            outcome="NO",
            size_usd=Decimal("800")
        )

    eval3 = tracker.evaluate_trade(
        market_id="market_strong_signal",
        outcome="NO",
        proposing_whale=enabled_whales[3],
        enabled_whales=enabled_whales
    )
    print(f"Decision: {eval3.decision.value}")
    print(f"Size Multiplier: {float(eval3.size_multiplier)}x")
    print(f"Reason: {eval3.reason}\n")

    # Scenario 4: Conflicting whales
    print("=== Scenario 4: Whale Conflict ===")

    tracker.register_whale_position(
        whale_address=enabled_whales[0],
        market_id="market_conflict",
        outcome="YES",
        size_usd=Decimal("1000")
    )
    tracker.register_whale_position(
        whale_address=enabled_whales[1],
        market_id="market_conflict",
        outcome="NO",
        size_usd=Decimal("1000")
    )

    eval4 = tracker.evaluate_trade(
        market_id="market_conflict",
        outcome="YES",
        proposing_whale=enabled_whales[2],
        enabled_whales=enabled_whales
    )
    print(f"Decision: {eval4.decision.value}")
    print(f"Size Multiplier: {float(eval4.size_multiplier)}x")
    print(f"Reason: {eval4.reason}\n")

    # Get statistics
    print("=== Tracker Statistics ===")
    import json
    stats = tracker.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
