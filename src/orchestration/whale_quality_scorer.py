"""
Whale Quality Scoring System
Week 6: Multi-Whale Orchestration - Quality Scoring
Continuously evaluates whale performance and assigns quality scores
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class WhaleStatus(Enum):
    """Whale operational status"""
    ACTIVE = "ACTIVE"              # Normal operation
    PROBATION = "PROBATION"        # Recent losses, monitoring
    DISABLED = "DISABLED"          # Auto-disabled due to poor performance
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"  # Manual enable/disable


@dataclass
class WhalePerformance:
    """Historical performance data for a whale"""
    whale_address: str

    # Performance metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Decimal = Decimal("0")

    # Returns
    total_pnl: Decimal = Decimal("0")
    avg_return: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")

    # Volume
    total_volume: Decimal = Decimal("0")
    avg_position_size: Decimal = Decimal("0")

    # Streak tracking
    current_streak: int = 0  # Positive = wins, negative = losses
    consecutive_losses: int = 0
    last_trade_timestamp: Optional[datetime] = None

    # Recency
    days_since_last_trade: int = 0
    trades_last_7d: int = 0
    trades_last_30d: int = 0


@dataclass
class WhaleQualityScore:
    """Comprehensive quality score for a whale"""
    whale_address: str

    # Overall score (0-100)
    quality_score: Decimal

    # Component scores (0-100 each)
    performance_score: Decimal  # Win rate & Sharpe
    volume_score: Decimal       # Total volume
    consistency_score: Decimal  # Trade frequency
    recency_score: Decimal      # Recent activity

    # Status
    status: WhaleStatus
    enabled: bool

    # Metadata
    last_updated: datetime
    reason: str = ""  # Reason for status change


@dataclass
class ScoringConfig:
    """Configuration for quality scoring"""
    # Score weights (must sum to 1.0)
    performance_weight: Decimal = Decimal("0.40")  # 40%
    volume_weight: Decimal = Decimal("0.25")       # 25%
    consistency_weight: Decimal = Decimal("0.20")  # 20%
    recency_weight: Decimal = Decimal("0.15")      # 15%

    # Thresholds
    quality_threshold: Decimal = Decimal("50")  # Min score to trade
    disable_threshold: Decimal = Decimal("30")  # Auto-disable below this

    # Auto-disable conditions
    max_consecutive_losses: int = 5             # Disable after 5 losses
    min_trades_for_scoring: int = 10            # Need 10 trades minimum
    max_days_inactive: int = 30                 # Disable if inactive 30+ days

    # Update frequency
    update_interval_hours: int = 6


# ==================== Whale Quality Scorer ====================

class WhaleQualityScorer:
    """
    Whale Quality Scoring System

    Continuously evaluates whale performance and assigns quality scores:
    - Performance score (40%): Win rate + Sharpe ratio
    - Volume score (25%): Total trading volume
    - Consistency score (20%): Trade frequency and regularity
    - Recency score (15%): Recent activity level

    Auto-disables whales with:
    - 5+ consecutive losses
    - Quality score < 30
    - 30+ days inactive
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        """
        Initialize whale quality scorer

        Args:
            config: Scoring configuration
        """
        self.config = config or ScoringConfig()

        # Whale data
        self.whale_scores: Dict[str, WhaleQualityScore] = {}
        self.whale_performance: Dict[str, WhalePerformance] = {}

        # Update tracking
        self.last_update = datetime.now()

        logger.info(
            f"WhaleQualityScorer initialized: "
            f"quality_threshold={float(self.config.quality_threshold)}, "
            f"update_interval={self.config.update_interval_hours}h"
        )

    def update_whale_performance(
        self,
        whale_address: str,
        trade_pnl: Decimal,
        position_size: Decimal,
        is_win: bool,
        timestamp: datetime
    ):
        """
        Update whale performance with new trade result

        Args:
            whale_address: Whale address
            trade_pnl: Profit/loss from trade
            position_size: Position size
            is_win: Whether trade was profitable
            timestamp: Trade timestamp
        """
        if whale_address not in self.whale_performance:
            self.whale_performance[whale_address] = WhalePerformance(
                whale_address=whale_address
            )

        perf = self.whale_performance[whale_address]

        # Update trade counts
        perf.total_trades += 1
        if is_win:
            perf.winning_trades += 1
        else:
            perf.losing_trades += 1

        # Update win rate
        perf.win_rate = Decimal(str(perf.winning_trades / perf.total_trades))

        # Update P&L
        perf.total_pnl += trade_pnl

        # Update volume
        perf.total_volume += position_size
        perf.avg_position_size = perf.total_volume / Decimal(str(perf.total_trades))

        # Update streak
        if is_win:
            if perf.current_streak > 0:
                perf.current_streak += 1
            else:
                perf.current_streak = 1
            perf.consecutive_losses = 0
        else:
            if perf.current_streak < 0:
                perf.current_streak -= 1
            else:
                perf.current_streak = -1
            perf.consecutive_losses += 1

        # Update timestamp
        perf.last_trade_timestamp = timestamp

        # Recalculate quality score for this whale
        self._calculate_quality_score(whale_address)

        logger.debug(
            f"Updated whale {whale_address[:10]}... | "
            f"Win: {is_win} | Streak: {perf.current_streak} | "
            f"Quality: {float(self.whale_scores[whale_address].quality_score):.1f}"
        )

    def calculate_all_scores(self):
        """Recalculate quality scores for all whales"""
        logger.info(f"Recalculating quality scores for {len(self.whale_performance)} whales...")

        for whale_address in self.whale_performance.keys():
            self._calculate_quality_score(whale_address)

        self.last_update = datetime.now()

        # Log summary
        active = sum(1 for s in self.whale_scores.values() if s.enabled)
        disabled = sum(1 for s in self.whale_scores.values() if not s.enabled)

        logger.info(
            f"Quality scores updated: {active} active, {disabled} disabled whales"
        )

    def get_quality_score(self, whale_address: str) -> Optional[WhaleQualityScore]:
        """Get quality score for a whale"""
        return self.whale_scores.get(whale_address)

    def is_whale_enabled(self, whale_address: str) -> bool:
        """Check if whale is enabled for trading"""
        score = self.whale_scores.get(whale_address)
        if not score:
            return False

        return score.enabled and score.quality_score >= self.config.quality_threshold

    def get_enabled_whales(self) -> List[WhaleQualityScore]:
        """Get all enabled whales sorted by quality score"""
        enabled = [
            score for score in self.whale_scores.values()
            if score.enabled and score.quality_score >= self.config.quality_threshold
        ]

        return sorted(enabled, key=lambda x: x.quality_score, reverse=True)

    def manually_enable_whale(self, whale_address: str, reason: str = "Manual enable"):
        """Manually enable a whale"""
        if whale_address in self.whale_scores:
            score = self.whale_scores[whale_address]
            score.status = WhaleStatus.MANUAL_OVERRIDE
            score.enabled = True
            score.reason = reason
            score.last_updated = datetime.now()

            logger.warning(
                f"Whale {whale_address[:10]}... manually enabled | Reason: {reason}"
            )

    def manually_disable_whale(self, whale_address: str, reason: str = "Manual disable"):
        """Manually disable a whale"""
        if whale_address in self.whale_scores:
            score = self.whale_scores[whale_address]
            score.status = WhaleStatus.MANUAL_OVERRIDE
            score.enabled = False
            score.reason = reason
            score.last_updated = datetime.now()

            logger.warning(
                f"Whale {whale_address[:10]}... manually disabled | Reason: {reason}"
            )

    def get_scoring_summary(self) -> Dict:
        """Get comprehensive scoring summary"""
        total_whales = len(self.whale_scores)
        enabled = sum(1 for s in self.whale_scores.values() if s.enabled)
        active = sum(1 for s in self.whale_scores.values() if s.status == WhaleStatus.ACTIVE)
        probation = sum(1 for s in self.whale_scores.values() if s.status == WhaleStatus.PROBATION)
        disabled = sum(1 for s in self.whale_scores.values() if s.status == WhaleStatus.DISABLED)

        # Get top performers
        top_whales = sorted(
            self.whale_scores.values(),
            key=lambda x: x.quality_score,
            reverse=True
        )[:10]

        return {
            "total_whales": total_whales,
            "enabled": enabled,
            "status_breakdown": {
                "active": active,
                "probation": probation,
                "disabled": disabled
            },
            "last_update": self.last_update.isoformat(),
            "top_whales": [
                {
                    "address": w.whale_address[:10] + "...",
                    "quality_score": float(w.quality_score),
                    "status": w.status.value,
                    "enabled": w.enabled
                }
                for w in top_whales
            ]
        }

    # ==================== Private Methods ====================

    def _calculate_quality_score(self, whale_address: str):
        """Calculate comprehensive quality score for a whale"""
        perf = self.whale_performance.get(whale_address)
        if not perf:
            return

        # Need minimum trades to score
        if perf.total_trades < self.config.min_trades_for_scoring:
            self.whale_scores[whale_address] = WhaleQualityScore(
                whale_address=whale_address,
                quality_score=Decimal("0"),
                performance_score=Decimal("0"),
                volume_score=Decimal("0"),
                consistency_score=Decimal("0"),
                recency_score=Decimal("0"),
                status=WhaleStatus.DISABLED,
                enabled=False,
                last_updated=datetime.now(),
                reason=f"Insufficient trades ({perf.total_trades} < {self.config.min_trades_for_scoring})"
            )
            return

        # Calculate component scores
        performance_score = self._calculate_performance_score(perf)
        volume_score = self._calculate_volume_score(perf)
        consistency_score = self._calculate_consistency_score(perf)
        recency_score = self._calculate_recency_score(perf)

        # Weighted overall score
        quality_score = (
            performance_score * self.config.performance_weight +
            volume_score * self.config.volume_weight +
            consistency_score * self.config.consistency_weight +
            recency_score * self.config.recency_weight
        )

        # Determine status and enabled state
        status, enabled, reason = self._determine_status(perf, quality_score)

        # Create/update score
        self.whale_scores[whale_address] = WhaleQualityScore(
            whale_address=whale_address,
            quality_score=quality_score,
            performance_score=performance_score,
            volume_score=volume_score,
            consistency_score=consistency_score,
            recency_score=recency_score,
            status=status,
            enabled=enabled,
            last_updated=datetime.now(),
            reason=reason
        )

    def _calculate_performance_score(self, perf: WhalePerformance) -> Decimal:
        """Calculate performance score (0-100) based on win rate and Sharpe"""
        # Win rate component (0-50 points)
        win_rate_score = perf.win_rate * Decimal("100")  # 0-100%

        # Sharpe ratio component (0-50 points)
        # Normalize Sharpe: 0 = 0 points, 1.0 = 25 points, 2.0+ = 50 points
        sharpe_score = min(perf.sharpe_ratio * Decimal("25"), Decimal("50"))

        # Combined (50% each)
        performance = (win_rate_score * Decimal("0.5") + sharpe_score)

        return min(performance, Decimal("100"))

    def _calculate_volume_score(self, perf: WhalePerformance) -> Decimal:
        """Calculate volume score (0-100) based on total volume"""
        # Normalize volume: $10k = 50 points, $50k+ = 100 points
        volume_usd = float(perf.total_volume)

        if volume_usd >= 50000:
            return Decimal("100")
        elif volume_usd >= 10000:
            # Linear scale from $10k (50 pts) to $50k (100 pts)
            pct = (volume_usd - 10000) / 40000
            return Decimal(str(50 + pct * 50))
        else:
            # Linear scale from $0 (0 pts) to $10k (50 pts)
            pct = volume_usd / 10000
            return Decimal(str(pct * 50))

    def _calculate_consistency_score(self, perf: WhalePerformance) -> Decimal:
        """Calculate consistency score (0-100) based on trade frequency"""
        # Trade count component (more trades = more consistent)
        # 10 trades = 25 pts, 50 trades = 75 pts, 100+ = 100 pts
        if perf.total_trades >= 100:
            trade_score = Decimal("100")
        elif perf.total_trades >= 50:
            pct = (perf.total_trades - 50) / 50
            trade_score = Decimal(str(75 + pct * 25))
        elif perf.total_trades >= 10:
            pct = (perf.total_trades - 10) / 40
            trade_score = Decimal(str(25 + pct * 50))
        else:
            trade_score = Decimal(str(perf.total_trades * 2.5))

        return min(trade_score, Decimal("100"))

    def _calculate_recency_score(self, perf: WhalePerformance) -> Decimal:
        """Calculate recency score (0-100) based on recent activity"""
        if not perf.last_trade_timestamp:
            return Decimal("0")

        # Days since last trade
        days_since = (datetime.now() - perf.last_trade_timestamp).days

        # Scoring:
        # 0-7 days = 100 pts
        # 7-14 days = 75 pts
        # 14-30 days = 50 pts
        # 30+ days = 0 pts
        if days_since <= 7:
            return Decimal("100")
        elif days_since <= 14:
            pct = (14 - days_since) / 7
            return Decimal(str(75 + pct * 25))
        elif days_since <= 30:
            pct = (30 - days_since) / 16
            return Decimal(str(50 * pct))
        else:
            return Decimal("0")

    def _determine_status(
        self,
        perf: WhalePerformance,
        quality_score: Decimal
    ) -> Tuple[WhaleStatus, bool, str]:
        """Determine whale status and enabled state"""
        # Check for manual override
        if perf.whale_address in self.whale_scores:
            old_score = self.whale_scores[perf.whale_address]
            if old_score.status == WhaleStatus.MANUAL_OVERRIDE:
                return old_score.status, old_score.enabled, old_score.reason

        # Auto-disable conditions

        # 1. Consecutive losses
        if perf.consecutive_losses >= self.config.max_consecutive_losses:
            return (
                WhaleStatus.DISABLED,
                False,
                f"Auto-disabled: {perf.consecutive_losses} consecutive losses"
            )

        # 2. Quality score too low
        if quality_score < self.config.disable_threshold:
            return (
                WhaleStatus.DISABLED,
                False,
                f"Auto-disabled: quality score {float(quality_score):.1f} < {float(self.config.disable_threshold)}"
            )

        # 3. Inactive too long
        if perf.last_trade_timestamp:
            days_inactive = (datetime.now() - perf.last_trade_timestamp).days
            if days_inactive >= self.config.max_days_inactive:
                return (
                    WhaleStatus.DISABLED,
                    False,
                    f"Auto-disabled: inactive for {days_inactive} days"
                )

        # Probation conditions
        if perf.consecutive_losses >= 3 or quality_score < self.config.quality_threshold:
            return (
                WhaleStatus.PROBATION,
                quality_score >= self.config.quality_threshold,
                "On probation: recent poor performance"
            )

        # Active and enabled
        return (
            WhaleStatus.ACTIVE,
            True,
            "Active with good performance"
        )


# ==================== Example Usage ====================

def main():
    """Example usage of WhaleQualityScorer"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize scorer
    scorer = WhaleQualityScorer()

    print("\n=== Whale Quality Scorer Test ===\n")

    # Simulate whale trading activity
    whale1 = "0x1234567890abcdef1234567890abcdef12345678"
    whale2 = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"

    # Whale 1: High performer
    print("=== Simulating Whale 1 (High Performer) ===")
    for i in range(15):
        is_win = i % 4 != 0  # 75% win rate
        pnl = Decimal("100") if is_win else Decimal("-50")
        scorer.update_whale_performance(
            whale1,
            pnl,
            Decimal("1000"),
            is_win,
            datetime.now() - timedelta(hours=i)
        )

    # Whale 2: Poor performer with losing streak
    print("\n=== Simulating Whale 2 (Poor Performer) ===")
    for i in range(12):
        is_win = i < 6  # Win first 6, then lose 6 straight
        pnl = Decimal("50") if is_win else Decimal("-40")
        scorer.update_whale_performance(
            whale2,
            pnl,
            Decimal("800"),
            is_win,
            datetime.now() - timedelta(hours=i)
        )

    # Get scores
    print("\n=== Quality Scores ===")
    score1 = scorer.get_quality_score(whale1)
    score2 = scorer.get_quality_score(whale2)

    print(f"\nWhale 1 ({whale1[:10]}...):")
    print(f"  Quality Score: {float(score1.quality_score):.1f}")
    print(f"  Performance: {float(score1.performance_score):.1f}")
    print(f"  Volume: {float(score1.volume_score):.1f}")
    print(f"  Consistency: {float(score1.consistency_score):.1f}")
    print(f"  Recency: {float(score1.recency_score):.1f}")
    print(f"  Status: {score1.status.value}")
    print(f"  Enabled: {score1.enabled}")

    print(f"\nWhale 2 ({whale2[:10]}...):")
    print(f"  Quality Score: {float(score2.quality_score):.1f}")
    print(f"  Status: {score2.status.value}")
    print(f"  Enabled: {score2.enabled}")
    print(f"  Reason: {score2.reason}")

    # Get enabled whales
    print("\n=== Enabled Whales ===")
    enabled = scorer.get_enabled_whales()
    print(f"Total enabled: {len(enabled)}")
    for whale_score in enabled:
        print(f"  {whale_score.whale_address[:10]}... | Score: {float(whale_score.quality_score):.1f}")

    # Get summary
    print("\n=== Scoring Summary ===")
    import json
    summary = scorer.get_scoring_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
