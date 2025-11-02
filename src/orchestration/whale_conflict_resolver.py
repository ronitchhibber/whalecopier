"""
Whale Conflict Resolution System
Week 6: Multi-Whale Orchestration - Enhanced Conflict Resolution
Resolves conflicts when whales trade opposite sides with performance-weighted voting
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class ConflictDecision(Enum):
    """Final decision on conflicted trade"""
    SKIP_TRADE = "SKIP_TRADE"              # 2 whales oppose → skip
    TAKE_YES = "TAKE_YES"                  # Majority/weighted vote for YES
    TAKE_NO = "TAKE_NO"                    # Majority/weighted vote for NO
    SIZE_UP_YES = "SIZE_UP_YES"            # Strong consensus on YES (3+)
    SIZE_UP_NO = "SIZE_UP_NO"              # Strong consensus on NO (3+)


@dataclass
class WhaleVote:
    """Single whale's vote on a market"""
    whale_address: str
    outcome: str  # YES or NO
    quality_score: Decimal
    performance_weight: Decimal  # Recent performance multiplier
    vote_weight: Decimal  # Final weighted vote


@dataclass
class ConflictAnalysis:
    """Analysis of conflicting whale positions"""
    market_id: str
    votes_yes: List[WhaleVote]
    votes_no: List[WhaleVote]
    total_weight_yes: Decimal
    total_weight_no: Decimal
    decision: ConflictDecision
    confidence: Decimal  # 0-1 scale
    reason: str
    size_multiplier: Decimal  # 0, 1.0, or 1.5
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConflictConfig:
    """Configuration for conflict resolution"""
    # Voting thresholds
    min_whales_for_consensus: int = 3        # Need 3+ for sizing up
    low_overlap_threshold: Decimal = Decimal("0.20")  # <20% for size up

    # Performance weighting
    use_performance_weighting: bool = True
    recent_performance_window: int = 20      # Last 20 trades

    # Size multipliers
    consensus_multiplier: Decimal = Decimal("1.5")  # 3+ agree → 1.5x
    normal_multiplier: Decimal = Decimal("1.0")

    # Confidence thresholds
    min_confidence_to_trade: Decimal = Decimal("0.60")  # 60% confidence minimum


# ==================== Whale Conflict Resolver ====================

class WhaleConflictResolver:
    """
    Enhanced Whale Conflict Resolution System

    Handles multi-whale trading conflicts with sophisticated logic:

    1. **Opposition Rule:** 2 whales on opposite sides → SKIP
    2. **Consensus Rule:** 3+ whales agree → SIZE UP 1.5x
    3. **Performance-Weighted Voting:** Weight votes by recent performance
    4. **Correlation Check:** Use correlation tracker to validate

    Decision Matrix:
    - Opposite sides (2 whales) → SKIP
    - 3+ agree, <20% overlap → SIZE UP 1.5x
    - 3+ agree, >30% overlap → SKIP (correlation tracker blocks)
    - Majority vote (weighted) → TAKE position
    - Tie or low confidence → SKIP
    """

    def __init__(self, config: Optional[ConflictConfig] = None):
        """
        Initialize conflict resolver

        Args:
            config: Conflict resolution configuration
        """
        self.config = config or ConflictConfig()

        # Statistics
        self.conflicts_resolved = 0
        self.conflicts_skipped = 0
        self.consensus_trades = 0
        self.weighted_votes_used = 0

        logger.info(
            f"WhaleConflictResolver initialized: "
            f"min_consensus={self.config.min_whales_for_consensus}, "
            f"performance_weighting={'ON' if self.config.use_performance_weighting else 'OFF'}"
        )

    def resolve_conflict(
        self,
        market_id: str,
        whale_signals: List[Tuple[str, str, Decimal]],  # (whale_address, outcome, quality_score)
        whale_performance: Optional[Dict[str, Decimal]] = None,  # Recent win rates
        overlap_percentage: Optional[Decimal] = None
    ) -> ConflictAnalysis:
        """
        Resolve trading conflict when multiple whales signal on same market

        Args:
            market_id: Market identifier
            whale_signals: List of (whale_address, outcome, quality_score)
            whale_performance: Optional recent performance data (win rates)
            overlap_percentage: Optional whale overlap % from correlation tracker

        Returns:
            ConflictAnalysis with decision and reasoning
        """
        self.conflicts_resolved += 1

        # Build weighted votes
        votes_yes: List[WhaleVote] = []
        votes_no: List[WhaleVote] = []

        for whale_address, outcome, quality_score in whale_signals:
            # Calculate performance weight
            if self.config.use_performance_weighting and whale_performance:
                perf_weight = whale_performance.get(whale_address, Decimal("0.5"))
                # Normalize: 0.5 (50% win rate) = 1.0x weight
                # 0.7 (70% win rate) = 1.4x weight
                # 0.3 (30% win rate) = 0.6x weight
                perf_weight = Decimal("1.0") + (perf_weight - Decimal("0.5")) * Decimal("2.0")
                perf_weight = max(Decimal("0.1"), min(perf_weight, Decimal("2.0")))
            else:
                perf_weight = Decimal("1.0")

            # Final vote weight = quality_score * performance_weight
            vote_weight = quality_score * perf_weight

            vote = WhaleVote(
                whale_address=whale_address,
                outcome=outcome,
                quality_score=quality_score,
                performance_weight=perf_weight,
                vote_weight=vote_weight
            )

            if outcome == "YES":
                votes_yes.append(vote)
            else:
                votes_no.append(vote)

        # Calculate total weights
        total_weight_yes = sum(v.vote_weight for v in votes_yes)
        total_weight_no = sum(v.vote_weight for v in votes_no)
        total_weight = total_weight_yes + total_weight_no

        # Check for opposition (whales on both sides)
        if len(votes_yes) > 0 and len(votes_no) > 0:
            # Opposition detected
            self.conflicts_skipped += 1
            return ConflictAnalysis(
                market_id=market_id,
                votes_yes=votes_yes,
                votes_no=votes_no,
                total_weight_yes=total_weight_yes,
                total_weight_no=total_weight_no,
                decision=ConflictDecision.SKIP_TRADE,
                confidence=Decimal("1.0"),  # 100% confident to skip
                reason=(
                    f"Whale conflict: {len(votes_yes)} on YES vs {len(votes_no)} on NO - "
                    f"skipping trade to avoid contradictory signals"
                ),
                size_multiplier=Decimal("0")
            )

        # No opposition - determine winning side
        if len(votes_yes) > len(votes_no):
            winning_votes = votes_yes
            winning_weight = total_weight_yes
            winning_outcome = "YES"
            decision_base = ConflictDecision.TAKE_YES
            size_up_decision = ConflictDecision.SIZE_UP_YES
        else:
            winning_votes = votes_no
            winning_weight = total_weight_no
            winning_outcome = "NO"
            decision_base = ConflictDecision.TAKE_NO
            size_up_decision = ConflictDecision.SIZE_UP_NO

        # Calculate confidence
        if total_weight > 0:
            confidence = winning_weight / total_weight
        else:
            confidence = Decimal("0")

        # Check for consensus (3+ whales agree)
        if len(winning_votes) >= self.config.min_whales_for_consensus:
            # Check overlap
            if overlap_percentage is not None and overlap_percentage <= self.config.low_overlap_threshold:
                # Strong consensus with low overlap → SIZE UP
                self.consensus_trades += 1
                return ConflictAnalysis(
                    market_id=market_id,
                    votes_yes=votes_yes,
                    votes_no=votes_no,
                    total_weight_yes=total_weight_yes,
                    total_weight_no=total_weight_no,
                    decision=size_up_decision,
                    confidence=confidence,
                    reason=(
                        f"✅ Strong consensus: {len(winning_votes)} whales agree on {winning_outcome} "
                        f"with {float(overlap_percentage)*100:.1f}% overlap - sizing up 1.5x"
                    ),
                    size_multiplier=self.config.consensus_multiplier
                )

        # Check confidence threshold
        if confidence < self.config.min_confidence_to_trade:
            self.conflicts_skipped += 1
            return ConflictAnalysis(
                market_id=market_id,
                votes_yes=votes_yes,
                votes_no=votes_no,
                total_weight_yes=total_weight_yes,
                total_weight_no=total_weight_no,
                decision=ConflictDecision.SKIP_TRADE,
                confidence=confidence,
                reason=(
                    f"Low confidence ({float(confidence)*100:.1f}%) below "
                    f"{float(self.config.min_confidence_to_trade)*100:.0f}% threshold - skipping"
                ),
                size_multiplier=Decimal("0")
            )

        # Normal trade with weighted vote
        if self.config.use_performance_weighting:
            self.weighted_votes_used += 1

        return ConflictAnalysis(
            market_id=market_id,
            votes_yes=votes_yes,
            votes_no=votes_no,
            total_weight_yes=total_weight_yes,
            total_weight_no=total_weight_no,
            decision=decision_base,
            confidence=confidence,
            reason=(
                f"Weighted vote: {len(winning_votes)} whale(s) on {winning_outcome} "
                f"with {float(confidence)*100:.1f}% confidence (weight: {float(winning_weight):.2f})"
            ),
            size_multiplier=self.config.normal_multiplier
        )

    def get_statistics(self) -> Dict:
        """Get conflict resolution statistics"""
        skip_rate = (
            self.conflicts_skipped / self.conflicts_resolved
            if self.conflicts_resolved > 0
            else 0
        )

        consensus_rate = (
            self.consensus_trades / self.conflicts_resolved
            if self.conflicts_resolved > 0
            else 0
        )

        return {
            "total_conflicts": self.conflicts_resolved,
            "conflicts_skipped": {
                "count": self.conflicts_skipped,
                "skip_rate": f"{skip_rate*100:.1f}%"
            },
            "consensus_trades": {
                "count": self.consensus_trades,
                "consensus_rate": f"{consensus_rate*100:.1f}%"
            },
            "weighted_votes_used": self.weighted_votes_used,
            "performance_weighting_enabled": self.config.use_performance_weighting
        }


# ==================== Example Usage ====================

def main():
    """Example usage of WhaleConflictResolver"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize resolver
    resolver = WhaleConflictResolver()

    print("\n=== Whale Conflict Resolver Test ===\n")

    # Scenario 1: Opposition (2 whales, opposite sides)
    print("=== Scenario 1: Whale Opposition ===")
    signals_1 = [
        ("0x1111", "YES", Decimal("80")),
        ("0x2222", "NO", Decimal("75")),
    ]

    analysis_1 = resolver.resolve_conflict(
        market_id="market_election",
        whale_signals=signals_1
    )
    print(f"Decision: {analysis_1.decision.value}")
    print(f"Confidence: {float(analysis_1.confidence)*100:.1f}%")
    print(f"Reason: {analysis_1.reason}\n")

    # Scenario 2: Consensus (3+ whales agree, low overlap)
    print("=== Scenario 2: Strong Consensus (Size Up) ===")
    signals_2 = [
        ("0x1111", "YES", Decimal("85")),
        ("0x2222", "YES", Decimal("80")),
        ("0x3333", "YES", Decimal("75")),
    ]

    # Simulate recent performance
    performance = {
        "0x1111": Decimal("0.70"),  # 70% win rate
        "0x2222": Decimal("0.65"),
        "0x3333": Decimal("0.60"),
    }

    analysis_2 = resolver.resolve_conflict(
        market_id="market_sports",
        whale_signals=signals_2,
        whale_performance=performance,
        overlap_percentage=Decimal("0.15")  # 15% overlap
    )
    print(f"Decision: {analysis_2.decision.value}")
    print(f"Size Multiplier: {float(analysis_2.size_multiplier)}x")
    print(f"Confidence: {float(analysis_2.confidence)*100:.1f}%")
    print(f"Reason: {analysis_2.reason}\n")

    # Scenario 3: Weighted vote (2 whales, different quality)
    print("=== Scenario 3: Performance-Weighted Vote ===")
    signals_3 = [
        ("0x1111", "NO", Decimal("90")),   # High quality
        ("0x2222", "NO", Decimal("60")),   # Lower quality
    ]

    performance_3 = {
        "0x1111": Decimal("0.75"),  # 75% win rate (excellent)
        "0x2222": Decimal("0.45"),  # 45% win rate (poor)
    }

    analysis_3 = resolver.resolve_conflict(
        market_id="market_tech",
        whale_signals=signals_3,
        whale_performance=performance_3
    )
    print(f"Decision: {analysis_3.decision.value}")
    print(f"Confidence: {float(analysis_3.confidence)*100:.1f}%")
    print(f"Total Weight YES: {float(analysis_3.total_weight_yes):.2f}")
    print(f"Total Weight NO: {float(analysis_3.total_weight_no):.2f}")
    print(f"Reason: {analysis_3.reason}\n")

    # Get statistics
    print("=== Resolver Statistics ===")
    import json
    stats = resolver.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
