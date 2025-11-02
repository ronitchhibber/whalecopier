"""
Whale Capital Allocation Algorithm
Week 6: Multi-Whale Orchestration - Correlation-Adjusted Capital Allocation
Distributes capital across whales based on quality scores and correlation
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class WhaleTier(Enum):
    """Whale tier classification"""
    TOP_TIER = "TOP_TIER"          # Top 10 whales (70% capital)
    MID_TIER = "MID_TIER"          # Next 20 whales (25% capital)
    EXPERIMENTAL = "EXPERIMENTAL"   # Remaining whales (5% capital)
    DISABLED = "DISABLED"           # Not allocated capital


@dataclass
class WhaleAllocation:
    """Capital allocation for a single whale"""
    whale_address: str
    tier: WhaleTier
    quality_score: Decimal
    base_allocation_pct: Decimal      # % of total capital
    correlation_adjustment: Decimal    # Multiplier based on correlation
    final_allocation_pct: Decimal      # Adjusted allocation %
    allocated_capital: Decimal         # Actual $ allocated
    max_position_size: Decimal         # Max per-position size


@dataclass
class AllocationConfig:
    """Configuration for capital allocation"""
    # Tier allocations (must sum to 1.0)
    top_tier_pct: Decimal = Decimal("0.70")    # 70% to top 10
    mid_tier_pct: Decimal = Decimal("0.25")    # 25% to next 20
    experimental_pct: Decimal = Decimal("0.05") # 5% to rest

    # Tier size limits
    top_tier_count: int = 10
    mid_tier_count: int = 20

    # Correlation adjustments
    high_correlation_threshold: Decimal = Decimal("0.70")  # >70% correlation
    correlation_penalty: Decimal = Decimal("0.50")         # Reduce to 50% if highly correlated

    # Position sizing
    max_position_pct_of_whale_capital: Decimal = Decimal("0.20")  # 20% max per position


@dataclass
class PortfolioAllocation:
    """Complete portfolio capital allocation"""
    total_capital: Decimal
    whale_allocations: List[WhaleAllocation]
    tier_summary: Dict[str, Decimal]
    correlation_adjustments_applied: int
    timestamp: datetime


# ==================== Whale Capital Allocator ====================

class WhaleCapitalAllocator:
    """
    Whale Capital Allocation Algorithm

    Distributes capital across whale portfolio based on:
    1. Quality scores (from WhaleQualityScorer)
    2. Tier classification (Top 10 / Next 20 / Experimental)
    3. Correlation adjustments (from WhaleCorrelationTracker)

    Capital Distribution:
    - Top 10 whales: 70% of capital (best performers)
    - Next 20 whales: 25% of capital (good performers)
    - Remaining: 5% of capital (experimental/new whales)

    Correlation Handling:
    - If 2+ whales have >70% correlation → Treat as single signal
    - Apply 50% penalty to correlated whale allocations
    - Prevents over-allocation to correlated strategies
    """

    def __init__(self, config: Optional[AllocationConfig] = None):
        """
        Initialize capital allocator

        Args:
            config: Allocation configuration
        """
        self.config = config or AllocationConfig()

        # Validate config
        total_pct = (
            self.config.top_tier_pct +
            self.config.mid_tier_pct +
            self.config.experimental_pct
        )
        if abs(total_pct - Decimal("1.0")) > Decimal("0.01"):
            raise ValueError(f"Tier allocations must sum to 100%, got {float(total_pct)*100:.1f}%")

        logger.info(
            f"WhaleCapitalAllocator initialized: "
            f"Top {self.config.top_tier_count} = {float(self.config.top_tier_pct)*100:.0f}%, "
            f"Mid {self.config.mid_tier_count} = {float(self.config.mid_tier_pct)*100:.0f}%, "
            f"Experimental = {float(self.config.experimental_pct)*100:.0f}%"
        )

    def allocate_capital(
        self,
        total_capital: Decimal,
        whale_scores: List[Tuple[str, Decimal]],  # (whale_address, quality_score)
        whale_correlations: Optional[Dict[Tuple[str, str], Decimal]] = None
    ) -> PortfolioAllocation:
        """
        Allocate capital across whale portfolio

        Args:
            total_capital: Total capital to allocate
            whale_scores: List of (whale_address, quality_score) tuples
            whale_correlations: Optional pairwise correlation dict

        Returns:
            PortfolioAllocation with detailed allocations
        """
        # Sort whales by quality score (descending)
        sorted_whales = sorted(whale_scores, key=lambda x: x[1], reverse=True)

        # Classify whales into tiers
        whale_tiers = self._classify_tiers(sorted_whales)

        # Calculate base allocations (before correlation adjustments)
        base_allocations = self._calculate_base_allocations(
            total_capital,
            sorted_whales,
            whale_tiers
        )

        # Apply correlation adjustments
        adjusted_allocations, adjustments_count = self._apply_correlation_adjustments(
            base_allocations,
            whale_correlations or {}
        )

        # Build final allocations
        whale_allocations = []
        for alloc_data in adjusted_allocations:
            whale_allocations.append(WhaleAllocation(
                whale_address=alloc_data["whale_address"],
                tier=alloc_data["tier"],
                quality_score=alloc_data["quality_score"],
                base_allocation_pct=alloc_data["base_pct"],
                correlation_adjustment=alloc_data["corr_adjustment"],
                final_allocation_pct=alloc_data["final_pct"],
                allocated_capital=alloc_data["allocated_capital"],
                max_position_size=alloc_data["max_position_size"]
            ))

        # Calculate tier summary
        tier_summary = self._calculate_tier_summary(whale_allocations)

        allocation = PortfolioAllocation(
            total_capital=total_capital,
            whale_allocations=whale_allocations,
            tier_summary=tier_summary,
            correlation_adjustments_applied=adjustments_count,
            timestamp=datetime.now()
        )

        logger.info(
            f"Capital allocation complete: {len(whale_allocations)} whales | "
            f"{adjustments_count} correlation adjustments | "
            f"${float(total_capital):,.2f} total"
        )

        return allocation

    def get_whale_allocation(
        self,
        whale_address: str,
        allocation: PortfolioAllocation
    ) -> Optional[WhaleAllocation]:
        """Get allocation for specific whale"""
        for alloc in allocation.whale_allocations:
            if alloc.whale_address == whale_address:
                return alloc
        return None

    def calculate_position_size(
        self,
        whale_address: str,
        allocation: PortfolioAllocation,
        base_size: Decimal
    ) -> Decimal:
        """
        Calculate position size for a whale trade

        Args:
            whale_address: Whale making the trade
            allocation: Current portfolio allocation
            base_size: Base position size

        Returns:
            Adjusted position size based on whale's allocation
        """
        whale_alloc = self.get_whale_allocation(whale_address, allocation)
        if not whale_alloc:
            logger.warning(f"Whale {whale_address[:10]}... not found in allocation")
            return Decimal("0")

        # Position size limited by whale's max position size
        position_size = min(base_size, whale_alloc.max_position_size)

        return position_size

    def get_allocation_summary(self, allocation: PortfolioAllocation) -> Dict:
        """Get comprehensive allocation summary"""
        # Top whales
        top_whales = sorted(
            allocation.whale_allocations,
            key=lambda x: x.allocated_capital,
            reverse=True
        )[:10]

        return {
            "total_capital": float(allocation.total_capital),
            "whale_count": len(allocation.whale_allocations),
            "correlation_adjustments": allocation.correlation_adjustments_applied,
            "tier_summary": {
                tier: {
                    "allocated_capital": float(capital),
                    "percentage": float(capital / allocation.total_capital * 100)
                }
                for tier, capital in allocation.tier_summary.items()
            },
            "top_10_whales": [
                {
                    "address": w.whale_address[:10] + "...",
                    "tier": w.tier.value,
                    "quality_score": float(w.quality_score),
                    "allocated_capital": float(w.allocated_capital),
                    "allocation_pct": float(w.final_allocation_pct * 100),
                    "correlation_adjusted": bool(w.correlation_adjustment != Decimal("1.0"))
                }
                for w in top_whales
            ]
        }

    # ==================== Private Methods ====================

    def _classify_tiers(
        self,
        sorted_whales: List[Tuple[str, Decimal]]
    ) -> Dict[str, WhaleTier]:
        """Classify whales into tiers based on ranking"""
        whale_tiers = {}

        for idx, (whale_address, score) in enumerate(sorted_whales):
            if idx < self.config.top_tier_count:
                tier = WhaleTier.TOP_TIER
            elif idx < self.config.top_tier_count + self.config.mid_tier_count:
                tier = WhaleTier.MID_TIER
            else:
                tier = WhaleTier.EXPERIMENTAL

            whale_tiers[whale_address] = tier

        return whale_tiers

    def _calculate_base_allocations(
        self,
        total_capital: Decimal,
        sorted_whales: List[Tuple[str, Decimal]],
        whale_tiers: Dict[str, WhaleTier]
    ) -> List[Dict]:
        """Calculate base capital allocations before correlation adjustments"""
        allocations = []

        # Group whales by tier
        tier_whales = {
            WhaleTier.TOP_TIER: [],
            WhaleTier.MID_TIER: [],
            WhaleTier.EXPERIMENTAL: []
        }

        for whale_address, quality_score in sorted_whales:
            tier = whale_tiers[whale_address]
            tier_whales[tier].append((whale_address, quality_score))

        # Allocate within each tier
        for tier, whales in tier_whales.items():
            if not whales:
                continue

            # Get tier's capital pool
            if tier == WhaleTier.TOP_TIER:
                tier_capital = total_capital * self.config.top_tier_pct
            elif tier == WhaleTier.MID_TIER:
                tier_capital = total_capital * self.config.mid_tier_pct
            else:  # EXPERIMENTAL
                tier_capital = total_capital * self.config.experimental_pct

            # Calculate total quality score for tier
            total_quality = sum(score for _, score in whales)

            # Allocate proportionally within tier
            for whale_address, quality_score in whales:
                # Proportional allocation based on quality score
                whale_share = quality_score / total_quality if total_quality > 0 else Decimal("1") / Decimal(str(len(whales)))
                whale_tier_pct = whale_share

                # Calculate allocation
                allocated_capital = tier_capital * whale_tier_pct
                allocation_pct = allocated_capital / total_capital

                # Max position size (20% of whale's capital)
                max_position_size = allocated_capital * self.config.max_position_pct_of_whale_capital

                allocations.append({
                    "whale_address": whale_address,
                    "tier": tier,
                    "quality_score": quality_score,
                    "base_pct": allocation_pct,
                    "corr_adjustment": Decimal("1.0"),  # No adjustment yet
                    "final_pct": allocation_pct,
                    "allocated_capital": allocated_capital,
                    "max_position_size": max_position_size
                })

        return allocations

    def _apply_correlation_adjustments(
        self,
        base_allocations: List[Dict],
        whale_correlations: Dict[Tuple[str, str], Decimal]
    ) -> Tuple[List[Dict], int]:
        """Apply correlation penalties to highly correlated whales"""
        if not whale_correlations:
            return base_allocations, 0

        adjusted = []
        adjustments_count = 0

        for alloc in base_allocations:
            whale_addr = alloc["whale_address"]
            correlation_penalty = Decimal("1.0")  # Default: no penalty

            # Check correlations with other whales
            highly_correlated_count = 0
            for (w1, w2), correlation in whale_correlations.items():
                if w1 == whale_addr or w2 == whale_addr:
                    if correlation >= self.config.high_correlation_threshold:
                        highly_correlated_count += 1

            # Apply penalty if highly correlated with others
            if highly_correlated_count > 0:
                # Stronger penalty for more correlations
                # 1 correlation = 50% penalty
                # 2+ correlations = 50% penalty (same, but we track it)
                correlation_penalty = self.config.correlation_penalty
                adjustments_count += 1

                logger.info(
                    f"Correlation penalty applied to {whale_addr[:10]}... | "
                    f"{highly_correlated_count} high correlations | "
                    f"Allocation reduced to {float(correlation_penalty)*100:.0f}%"
                )

            # Adjust allocation
            adjusted_alloc = alloc.copy()
            adjusted_alloc["corr_adjustment"] = correlation_penalty
            adjusted_alloc["final_pct"] = alloc["base_pct"] * correlation_penalty
            adjusted_alloc["allocated_capital"] = alloc["allocated_capital"] * correlation_penalty
            adjusted_alloc["max_position_size"] = alloc["max_position_size"] * correlation_penalty

            adjusted.append(adjusted_alloc)

        return adjusted, adjustments_count

    def _calculate_tier_summary(
        self,
        allocations: List[WhaleAllocation]
    ) -> Dict[str, Decimal]:
        """Calculate capital allocated per tier"""
        tier_totals = {
            WhaleTier.TOP_TIER.value: Decimal("0"),
            WhaleTier.MID_TIER.value: Decimal("0"),
            WhaleTier.EXPERIMENTAL.value: Decimal("0")
        }

        for alloc in allocations:
            tier_totals[alloc.tier.value] += alloc.allocated_capital

        return tier_totals


# ==================== Example Usage ====================

def main():
    """Example usage of WhaleCapitalAllocator"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize allocator
    allocator = WhaleCapitalAllocator()

    print("\n=== Whale Capital Allocator Test ===\n")

    # Simulate whale quality scores
    whale_scores = [
        (f"0x{i:040x}", Decimal(str(90 - i * 2)))  # Scores from 90 down to 50
        for i in range(35)  # 35 whales total
    ]

    # Simulate correlations (some whales are highly correlated)
    correlations = {
        (whale_scores[0][0], whale_scores[1][0]): Decimal("0.85"),  # Top 2 whales highly correlated
        (whale_scores[2][0], whale_scores[3][0]): Decimal("0.75"),  # Another pair
    }

    # Allocate $100,000
    total_capital = Decimal("100000")

    print(f"=== Allocating ${float(total_capital):,.2f} across {len(whale_scores)} whales ===\n")

    allocation = allocator.allocate_capital(
        total_capital=total_capital,
        whale_scores=whale_scores,
        whale_correlations=correlations
    )

    # Get summary
    print("=== Allocation Summary ===")
    import json
    summary = allocator.get_allocation_summary(allocation)
    print(json.dumps(summary, indent=2))

    # Test position sizing
    print("\n=== Example Position Sizing ===")
    top_whale = allocation.whale_allocations[0]
    base_size = Decimal("1000")
    position_size = allocator.calculate_position_size(
        top_whale.whale_address,
        allocation,
        base_size
    )
    print(f"Top whale base trade: ${float(base_size):,.2f}")
    print(f"Max position size: ${float(top_whale.max_position_size):,.2f}")
    print(f"Final position size: ${float(position_size):,.2f}")


if __name__ == "__main__":
    main()
