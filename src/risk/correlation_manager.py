"""
Portfolio Exposure & Correlation Management
Week 5: Risk Management Framework - Correlation Management
Prevents over-concentration in correlated markets and topics
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class RebalanceAction(Enum):
    """Recommended rebalancing actions"""
    NONE = "NONE"
    REDUCE_CORRELATED = "REDUCE_CORRELATED"
    INCREASE_DIVERSIFICATION = "INCREASE_DIVERSIFICATION"
    CLOSE_OVERLAPPING = "CLOSE_OVERLAPPING"


@dataclass
class PositionExposure:
    """Exposure data for a single position"""
    position_id: str
    market_id: str
    topic: str
    whale_address: str
    size_usd: Decimal
    outcome: str  # YES or NO
    timestamp: datetime


@dataclass
class TopicExposure:
    """Aggregate exposure by topic"""
    topic: str
    total_exposure_usd: Decimal
    position_count: int
    positions: List[str] = field(default_factory=list)
    concentration: Decimal = Decimal("0")  # 0-1 scale


@dataclass
class CorrelationWarning:
    """Warning about correlated positions"""
    severity: str  # INFO, WARNING, CRITICAL
    message: str
    positions: List[str]
    correlation: Optional[float] = None
    recommended_action: RebalanceAction = RebalanceAction.NONE
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DiversificationMetrics:
    """Portfolio diversification metrics"""
    herfindahl_index: Decimal  # 0-1, lower = more diversified
    topic_diversity: Decimal  # 0-1, higher = more diverse
    market_diversity: Decimal  # 0-1, higher = more diverse
    whale_diversity: Decimal  # 0-1, higher = more diverse
    overall_score: Decimal  # 0-1, higher = better
    needs_rebalancing: bool
    warnings: List[CorrelationWarning] = field(default_factory=list)


@dataclass
class CorrelationLimits:
    """Configuration limits for correlation management"""
    # Maximum positions in same topic
    max_positions_per_topic: int = 3

    # Minimum diversification score (0-1)
    min_diversification_score: Decimal = Decimal("0.6")

    # Maximum concentration in single topic (0-1)
    max_topic_concentration: Decimal = Decimal("0.40")  # 40%

    # Maximum correlation between positions (0-1)
    max_correlation_threshold: Decimal = Decimal("0.70")  # 70%

    # Minimum number of different topics
    min_topics: int = 3

    # Maximum exposure to single whale
    max_whale_exposure_pct: Decimal = Decimal("0.30")  # 30%


# ==================== Correlation Manager ====================

class CorrelationManager:
    """
    Portfolio Exposure & Correlation Management

    Monitors and manages portfolio diversification to prevent
    over-concentration in correlated markets. Implements research-backed
    limits on topic exposure and provides rebalancing recommendations.

    Key Features:
    - Real-time correlation tracking
    - Topic-based exposure limits
    - Diversification scoring (Herfindahl Index)
    - Automatic rebalancing alerts
    """

    def __init__(self, limits: Optional[CorrelationLimits] = None):
        """
        Initialize correlation manager

        Args:
            limits: Correlation limits configuration
        """
        self.limits = limits or CorrelationLimits()

        # Tracking state
        self.positions: Dict[str, PositionExposure] = {}
        self.topic_exposures: Dict[str, TopicExposure] = {}
        self.warnings: List[CorrelationWarning] = []

        logger.info(
            f"CorrelationManager initialized: "
            f"max_positions_per_topic={self.limits.max_positions_per_topic}, "
            f"min_diversification={float(self.limits.min_diversification_score)}"
        )

    def add_position(self, position: PositionExposure) -> Tuple[bool, Optional[str]]:
        """
        Add a position and check if it violates correlation limits

        Args:
            position: Position to add

        Returns:
            (can_add, reason) tuple
        """
        # Check topic exposure limit
        topic_count = sum(
            1 for p in self.positions.values()
            if p.topic == position.topic
        )

        if topic_count >= self.limits.max_positions_per_topic:
            reason = (
                f"Topic '{position.topic}' already has {topic_count} positions "
                f"(max: {self.limits.max_positions_per_topic})"
            )
            logger.warning(f"Position rejected: {reason}")
            return False, reason

        # Check topic concentration
        total_portfolio_value = self._calculate_total_exposure()
        if total_portfolio_value > 0:
            topic_exposure = self._calculate_topic_exposure(position.topic)
            new_topic_exposure = topic_exposure + position.size_usd
            concentration = new_topic_exposure / (total_portfolio_value + position.size_usd)

            if concentration > self.limits.max_topic_concentration:
                reason = (
                    f"Adding position would exceed topic concentration limit: "
                    f"{float(concentration)*100:.1f}% > "
                    f"{float(self.limits.max_topic_concentration)*100:.1f}%"
                )
                logger.warning(f"Position rejected: {reason}")
                return False, reason

        # Add position
        self.positions[position.position_id] = position
        self._update_topic_exposures()

        logger.info(
            f"Position added: {position.position_id} | "
            f"Topic: {position.topic} | Size: ${float(position.size_usd):.2f}"
        )

        return True, None

    def remove_position(self, position_id: str):
        """Remove a position from tracking"""
        if position_id in self.positions:
            position = self.positions.pop(position_id)
            self._update_topic_exposures()
            logger.info(f"Position removed: {position_id}")

    def calculate_diversification(self) -> DiversificationMetrics:
        """
        Calculate comprehensive diversification metrics

        Returns:
            DiversificationMetrics with scores and warnings
        """
        if not self.positions:
            return DiversificationMetrics(
                herfindahl_index=Decimal("0"),
                topic_diversity=Decimal("1"),
                market_diversity=Decimal("1"),
                whale_diversity=Decimal("1"),
                overall_score=Decimal("1"),
                needs_rebalancing=False
            )

        # Calculate Herfindahl-Hirschman Index (HHI)
        # Lower = more diversified (0 = perfect, 1 = concentrated)
        total_exposure = self._calculate_total_exposure()
        herfindahl = Decimal("0")

        if total_exposure > 0:
            for position in self.positions.values():
                share = position.size_usd / total_exposure
                herfindahl += share * share

        # Calculate diversity scores (0-1, higher = more diverse)
        topic_diversity = self._calculate_topic_diversity()
        market_diversity = self._calculate_market_diversity()
        whale_diversity = self._calculate_whale_diversity()

        # Overall score (weighted average, inverted HHI)
        overall_score = (
            (Decimal("1") - herfindahl) * Decimal("0.30") +  # 30% weight on HHI
            topic_diversity * Decimal("0.30") +               # 30% weight on topic
            market_diversity * Decimal("0.25") +              # 25% weight on market
            whale_diversity * Decimal("0.15")                 # 15% weight on whale
        )

        # Generate warnings
        warnings = self._generate_warnings(
            herfindahl=herfindahl,
            topic_diversity=topic_diversity,
            overall_score=overall_score
        )

        # Check if rebalancing needed
        needs_rebalancing = overall_score < self.limits.min_diversification_score

        metrics = DiversificationMetrics(
            herfindahl_index=herfindahl,
            topic_diversity=topic_diversity,
            market_diversity=market_diversity,
            whale_diversity=whale_diversity,
            overall_score=overall_score,
            needs_rebalancing=needs_rebalancing,
            warnings=warnings
        )

        if needs_rebalancing:
            logger.warning(
                f"Portfolio needs rebalancing: score={float(overall_score):.3f} < "
                f"{float(self.limits.min_diversification_score):.3f}"
            )

        return metrics

    def calculate_correlation_matrix(self) -> np.ndarray:
        """
        Calculate correlation matrix between positions

        Note: This is a simplified correlation based on topic overlap.
        In production, use historical price correlation.

        Returns:
            NxN correlation matrix
        """
        positions_list = list(self.positions.values())
        n = len(positions_list)

        if n == 0:
            return np.array([])

        # Build correlation matrix based on topic similarity
        correlation_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i == j:
                    correlation_matrix[i][j] = 1.0
                else:
                    # Same topic = high correlation
                    # Same whale = medium correlation
                    # Different = low correlation
                    p1, p2 = positions_list[i], positions_list[j]

                    if p1.topic == p2.topic and p1.outcome == p2.outcome:
                        correlation_matrix[i][j] = 0.85  # High correlation
                    elif p1.topic == p2.topic:
                        correlation_matrix[i][j] = 0.60  # Medium correlation
                    elif p1.whale_address == p2.whale_address:
                        correlation_matrix[i][j] = 0.40  # Low-medium correlation
                    else:
                        correlation_matrix[i][j] = 0.15  # Low correlation

        return correlation_matrix

    def get_rebalancing_recommendations(self) -> List[CorrelationWarning]:
        """
        Get specific recommendations for rebalancing portfolio

        Returns:
            List of actionable warnings
        """
        recommendations = []

        # Check topic concentrations
        for topic, exposure in self.topic_exposures.items():
            if exposure.position_count > self.limits.max_positions_per_topic:
                recommendations.append(CorrelationWarning(
                    severity="WARNING",
                    message=f"Too many positions in '{topic}': {exposure.position_count} > {self.limits.max_positions_per_topic}",
                    positions=exposure.positions,
                    recommended_action=RebalanceAction.REDUCE_CORRELATED
                ))

            if exposure.concentration > self.limits.max_topic_concentration:
                recommendations.append(CorrelationWarning(
                    severity="CRITICAL",
                    message=f"Topic '{topic}' over-concentrated: {float(exposure.concentration)*100:.1f}%",
                    positions=exposure.positions,
                    recommended_action=RebalanceAction.CLOSE_OVERLAPPING
                ))

        # Check overall diversification
        metrics = self.calculate_diversification()
        if metrics.needs_rebalancing:
            recommendations.append(CorrelationWarning(
                severity="WARNING",
                message=f"Portfolio under-diversified: score={float(metrics.overall_score):.3f}",
                positions=list(self.positions.keys()),
                recommended_action=RebalanceAction.INCREASE_DIVERSIFICATION
            ))

        # Check topic count
        if len(self.topic_exposures) < self.limits.min_topics:
            recommendations.append(CorrelationWarning(
                severity="INFO",
                message=f"Too few topics: {len(self.topic_exposures)} < {self.limits.min_topics}",
                positions=[],
                recommended_action=RebalanceAction.INCREASE_DIVERSIFICATION
            ))

        return recommendations

    def get_topic_exposures(self) -> Dict[str, TopicExposure]:
        """Get current topic exposures"""
        return self.topic_exposures.copy()

    def get_exposure_summary(self) -> Dict:
        """Get comprehensive exposure summary"""
        total = self._calculate_total_exposure()

        # Whale exposures
        whale_exposures = defaultdict(Decimal)
        for position in self.positions.values():
            whale_exposures[position.whale_address] += position.size_usd

        # Market exposures
        market_exposures = defaultdict(Decimal)
        for position in self.positions.values():
            market_exposures[position.market_id] += position.size_usd

        return {
            "total_exposure_usd": float(total),
            "position_count": len(self.positions),
            "topic_count": len(self.topic_exposures),
            "whale_count": len(whale_exposures),
            "market_count": len(market_exposures),
            "topics": {
                topic: {
                    "exposure_usd": float(exp.total_exposure_usd),
                    "position_count": exp.position_count,
                    "concentration": float(exp.concentration)
                }
                for topic, exp in self.topic_exposures.items()
            },
            "top_whales": sorted(
                [
                    {"address": addr[:10] + "...", "exposure_usd": float(exp)}
                    for addr, exp in whale_exposures.items()
                ],
                key=lambda x: x["exposure_usd"],
                reverse=True
            )[:5]
        }

    # ==================== Private Methods ====================

    def _calculate_total_exposure(self) -> Decimal:
        """Calculate total portfolio exposure"""
        return sum(p.size_usd for p in self.positions.values())

    def _calculate_topic_exposure(self, topic: str) -> Decimal:
        """Calculate exposure for a specific topic"""
        return sum(
            p.size_usd for p in self.positions.values()
            if p.topic == topic
        )

    def _update_topic_exposures(self):
        """Update topic exposure tracking"""
        self.topic_exposures.clear()
        total = self._calculate_total_exposure()

        # Group by topic
        topic_positions = defaultdict(list)
        for position in self.positions.values():
            topic_positions[position.topic].append(position)

        # Calculate exposures
        for topic, positions in topic_positions.items():
            topic_total = sum(p.size_usd for p in positions)
            concentration = topic_total / total if total > 0 else Decimal("0")

            self.topic_exposures[topic] = TopicExposure(
                topic=topic,
                total_exposure_usd=topic_total,
                position_count=len(positions),
                positions=[p.position_id for p in positions],
                concentration=concentration
            )

    def _calculate_topic_diversity(self) -> Decimal:
        """Calculate topic diversity score (0-1)"""
        if not self.positions:
            return Decimal("1")

        unique_topics = len(set(p.topic for p in self.positions.values()))
        total_positions = len(self.positions)

        # Normalize by expected number of topics
        # Perfect diversity = each position in different topic
        return Decimal(str(min(unique_topics / total_positions, 1.0)))

    def _calculate_market_diversity(self) -> Decimal:
        """Calculate market diversity score (0-1)"""
        if not self.positions:
            return Decimal("1")

        unique_markets = len(set(p.market_id for p in self.positions.values()))
        total_positions = len(self.positions)

        return Decimal(str(min(unique_markets / total_positions, 1.0)))

    def _calculate_whale_diversity(self) -> Decimal:
        """Calculate whale diversity score (0-1)"""
        if not self.positions:
            return Decimal("1")

        # Calculate whale concentration
        whale_exposures = defaultdict(Decimal)
        total = self._calculate_total_exposure()

        for position in self.positions.values():
            whale_exposures[position.whale_address] += position.size_usd

        if total == 0:
            return Decimal("1")

        # Check max whale exposure
        max_whale_pct = max(exp / total for exp in whale_exposures.values())

        # Score: 1.0 if well-distributed, 0.0 if one whale dominates
        if max_whale_pct > self.limits.max_whale_exposure_pct:
            penalty = (max_whale_pct - self.limits.max_whale_exposure_pct) / (Decimal("1") - self.limits.max_whale_exposure_pct)
            return Decimal("1") - penalty

        return Decimal("1")

    def _generate_warnings(
        self,
        herfindahl: Decimal,
        topic_diversity: Decimal,
        overall_score: Decimal
    ) -> List[CorrelationWarning]:
        """Generate correlation warnings"""
        warnings = []

        # High HHI warning (concentrated portfolio)
        if herfindahl > Decimal("0.50"):
            warnings.append(CorrelationWarning(
                severity="WARNING",
                message=f"Portfolio highly concentrated (HHI={float(herfindahl):.3f})",
                positions=list(self.positions.keys()),
                recommended_action=RebalanceAction.INCREASE_DIVERSIFICATION
            ))

        # Low topic diversity
        if topic_diversity < Decimal("0.50"):
            warnings.append(CorrelationWarning(
                severity="INFO",
                message=f"Low topic diversity ({float(topic_diversity):.3f})",
                positions=[],
                recommended_action=RebalanceAction.INCREASE_DIVERSIFICATION
            ))

        # Check for over-concentrated topics
        for topic, exposure in self.topic_exposures.items():
            if exposure.concentration > self.limits.max_topic_concentration:
                warnings.append(CorrelationWarning(
                    severity="CRITICAL",
                    message=f"Topic '{topic}' over-concentrated: {float(exposure.concentration)*100:.1f}%",
                    positions=exposure.positions,
                    recommended_action=RebalanceAction.REDUCE_CORRELATED
                ))

        return warnings


# ==================== Example Usage ====================

def main():
    """Example usage of CorrelationManager"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize manager
    manager = CorrelationManager()

    print("\n=== Correlation Manager Test Scenarios ===\n")

    # Scenario 1: Add diverse positions
    positions = [
        PositionExposure(
            position_id="pos_1",
            market_id="market_election",
            topic="Politics",
            whale_address="0x1234567890abcdef",
            size_usd=Decimal("1000"),
            outcome="YES",
            timestamp=datetime.now()
        ),
        PositionExposure(
            position_id="pos_2",
            market_id="market_sports",
            topic="Sports",
            whale_address="0xabcdef1234567890",
            size_usd=Decimal("800"),
            outcome="YES",
            timestamp=datetime.now()
        ),
        PositionExposure(
            position_id="pos_3",
            market_id="market_tech",
            topic="Technology",
            whale_address="0x9876543210fedcba",
            size_usd=Decimal("1200"),
            outcome="NO",
            timestamp=datetime.now()
        ),
    ]

    for position in positions:
        can_add, reason = manager.add_position(position)
        print(f"Adding {position.position_id} ({position.topic}): {'✓' if can_add else '✗'} {reason or ''}")

    # Calculate diversification
    print("\n=== Diversification Metrics ===")
    metrics = manager.calculate_diversification()
    print(f"Overall Score: {float(metrics.overall_score):.3f}")
    print(f"Herfindahl Index: {float(metrics.herfindahl_index):.3f}")
    print(f"Topic Diversity: {float(metrics.topic_diversity):.3f}")
    print(f"Market Diversity: {float(metrics.market_diversity):.3f}")
    print(f"Needs Rebalancing: {metrics.needs_rebalancing}")

    # Add concentrated positions
    print("\n=== Testing Concentration Limits ===")
    for i in range(3):
        concentrated_pos = PositionExposure(
            position_id=f"pos_politics_{i}",
            market_id=f"market_pol_{i}",
            topic="Politics",
            whale_address=f"0x{'0'*i}123",
            size_usd=Decimal("500"),
            outcome="YES",
            timestamp=datetime.now()
        )
        can_add, reason = manager.add_position(concentrated_pos)
        print(f"Adding Politics position {i+1}: {'✓' if can_add else '✗'} {reason or ''}")

    # Get recommendations
    print("\n=== Rebalancing Recommendations ===")
    recommendations = manager.get_rebalancing_recommendations()
    for rec in recommendations:
        print(f"[{rec.severity}] {rec.message}")
        print(f"  Action: {rec.recommended_action.value}")

    # Exposure summary
    print("\n=== Exposure Summary ===")
    import json
    summary = manager.get_exposure_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
