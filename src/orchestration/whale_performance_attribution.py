"""
Whale Performance Attribution System
Week 6: Multi-Whale Orchestration - Performance Attribution & Portfolio Optimization
Tracks P&L per whale with correlation-adjusted attribution and provides recommendations
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class AttributionPeriod(Enum):
    """Time period for attribution analysis"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    ALL_TIME = "ALL_TIME"


class RecommendationType(Enum):
    """Whale portfolio recommendations"""
    KEEP = "KEEP"                      # Strong performer
    MONITOR = "MONITOR"                # Marginal performance
    REDUCE_ALLOCATION = "REDUCE_ALLOCATION"  # Underperforming
    DISABLE = "DISABLE"                # Poor performer - disable
    ADD_TO_PORTFOLIO = "ADD_TO_PORTFOLIO"    # Strong candidate to add


@dataclass
class TradeAttribution:
    """Attribution for a single trade"""
    trade_id: str
    whale_address: str
    market_id: str
    outcome: str
    size_usd: Decimal
    pnl: Decimal
    pnl_percentage: Decimal
    correlation_factor: Decimal  # 1.0 = unique, 0.5 = 50% correlated, etc.
    adjusted_pnl: Decimal        # PnL adjusted for correlation
    timestamp: datetime


@dataclass
class WhaleAttribution:
    """Complete attribution for a whale"""
    whale_address: str

    # P&L metrics
    total_pnl: Decimal
    adjusted_pnl: Decimal           # Correlation-adjusted
    attribution_pct: Decimal         # % of total portfolio profit

    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal

    # Size metrics
    total_volume: Decimal
    avg_position_size: Decimal

    # Performance metrics
    avg_pnl_per_trade: Decimal
    best_trade_pnl: Decimal
    worst_trade_pnl: Decimal

    # Correlation metrics
    correlation_overlap_pct: Decimal  # % of trades overlapping with others
    unique_contribution_pct: Decimal  # % of PnL that's unique

    # Optional performance metrics
    sharpe_ratio: Optional[Decimal] = None

    # Rankings
    pnl_rank: int = 0
    win_rate_rank: int = 0
    volume_rank: int = 0
    overall_rank: int = 0

    # Trade history
    trades: List[TradeAttribution] = field(default_factory=list)


@dataclass
class WhaleRecommendation:
    """Recommendation for whale portfolio optimization"""
    whale_address: str
    recommendation: RecommendationType
    confidence: Decimal  # 0-1 scale
    reasoning: List[str]
    current_allocation_pct: Decimal
    suggested_allocation_pct: Decimal
    key_metrics: Dict[str, str]


@dataclass
class PortfolioAttribution:
    """Complete portfolio attribution analysis"""
    period: AttributionPeriod
    start_date: datetime
    end_date: datetime

    # Portfolio metrics
    total_pnl: Decimal
    total_trades: int
    portfolio_win_rate: Decimal

    # Whale attributions
    whale_attributions: List[WhaleAttribution]

    # Top performers
    top_5_by_pnl: List[WhaleAttribution]
    top_5_by_win_rate: List[WhaleAttribution]
    bottom_5_by_pnl: List[WhaleAttribution]

    # Recommendations
    recommendations: List[WhaleRecommendation]

    # Overlap analysis
    high_overlap_pairs: List[Tuple[str, str, Decimal]]  # (whale1, whale2, overlap_pct)

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AttributionConfig:
    """Configuration for attribution system"""
    # Correlation adjustment
    correlation_attribution_method: str = "PROPORTIONAL"  # or "FIRST_MOVER"
    min_correlation_for_adjustment: Decimal = Decimal("0.30")

    # Performance thresholds
    strong_performer_pnl_pct: Decimal = Decimal("0.10")    # Top 10% by PnL
    weak_performer_pnl_pct: Decimal = Decimal("0.10")      # Bottom 10% by PnL
    min_win_rate_threshold: Decimal = Decimal("0.50")      # 50% minimum

    # Overlap thresholds
    high_overlap_threshold: Decimal = Decimal("0.50")      # 50%+ overlap
    extreme_overlap_threshold: Decimal = Decimal("0.70")   # 70%+ overlap

    # Recommendation thresholds
    min_trades_for_recommendation: int = 10                # Need 10+ trades
    disable_threshold_loss_pct: Decimal = Decimal("-0.15") # -15% total loss
    reduce_threshold_loss_pct: Decimal = Decimal("-0.05")  # -5% total loss


# ==================== Whale Performance Attribution ====================

class WhalePerformanceAttributor:
    """
    Whale Performance Attribution System

    Tracks and attributes P&L to individual whales with sophisticated
    correlation adjustments and provides actionable portfolio recommendations.

    Key Features:
    1. **Correlation-Adjusted Attribution:** When multiple whales profit from
       the same market, properly attributes gains based on correlation
    2. **Unique Contribution Tracking:** Identifies which whales provide
       genuinely unique value vs. duplicative signals
    3. **Performance Rankings:** Multi-dimensional rankings (PnL, win rate, volume)
    4. **Overlap Analysis:** Flags whales with >50% market overlap
    5. **Portfolio Recommendations:** Data-driven suggestions for whale additions/removals

    Attribution Methods:
    - PROPORTIONAL: Split correlated profits equally among whales
    - FIRST_MOVER: Credit first whale to enter position (time priority)
    """

    def __init__(self, config: Optional[AttributionConfig] = None):
        """
        Initialize attribution system

        Args:
            config: Attribution configuration
        """
        self.config = config or AttributionConfig()

        # Attribution storage
        self.trade_attributions: Dict[str, TradeAttribution] = {}  # trade_id -> attribution
        self.whale_trades: Dict[str, List[str]] = defaultdict(list)  # whale -> [trade_ids]
        self.market_whales: Dict[str, Set[str]] = defaultdict(set)  # market -> {whales}

        # Statistics
        self.attributions_calculated = 0
        self.correlation_adjustments_applied = 0

        logger.info(
            f"WhalePerformanceAttributor initialized: "
            f"method={self.config.correlation_attribution_method}, "
            f"min_correlation={float(self.config.min_correlation_for_adjustment)}"
        )

    def record_trade(
        self,
        trade_id: str,
        whale_address: str,
        market_id: str,
        outcome: str,
        size_usd: Decimal,
        pnl: Decimal,
        timestamp: datetime,
        correlated_whales: Optional[List[str]] = None
    ):
        """
        Record a trade and calculate attribution

        Args:
            trade_id: Unique trade identifier
            whale_address: Whale who made the trade
            market_id: Market identifier
            outcome: YES or NO
            size_usd: Position size in USD
            pnl: Profit/loss on the trade
            timestamp: Trade timestamp
            correlated_whales: List of other whales in same market (for correlation adjustment)
        """
        # Calculate P&L percentage
        pnl_percentage = (pnl / size_usd * Decimal("100")) if size_usd > 0 else Decimal("0")

        # Calculate correlation factor
        correlation_factor = self._calculate_correlation_factor(
            whale_address,
            market_id,
            correlated_whales or []
        )

        # Adjusted P&L (split among correlated whales)
        adjusted_pnl = pnl * correlation_factor

        # Create attribution
        attribution = TradeAttribution(
            trade_id=trade_id,
            whale_address=whale_address,
            market_id=market_id,
            outcome=outcome,
            size_usd=size_usd,
            pnl=pnl,
            pnl_percentage=pnl_percentage,
            correlation_factor=correlation_factor,
            adjusted_pnl=adjusted_pnl,
            timestamp=timestamp
        )

        # Store attribution
        self.trade_attributions[trade_id] = attribution
        self.whale_trades[whale_address].append(trade_id)
        self.market_whales[market_id].add(whale_address)

        self.attributions_calculated += 1

        if correlation_factor < Decimal("1.0"):
            self.correlation_adjustments_applied += 1
            logger.debug(
                f"Correlation adjustment applied: {whale_address[:10]}... | "
                f"Market {market_id[:10]}... | "
                f"Factor: {float(correlation_factor):.2f} | "
                f"Raw P&L: ${float(pnl):,.2f} → Adjusted: ${float(adjusted_pnl):,.2f}"
            )

    def calculate_portfolio_attribution(
        self,
        period: AttributionPeriod = AttributionPeriod.ALL_TIME,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        whale_allocations: Optional[Dict[str, Decimal]] = None  # whale -> allocation %
    ) -> PortfolioAttribution:
        """
        Calculate comprehensive portfolio attribution

        Args:
            period: Time period for analysis
            start_date: Optional start date filter
            end_date: Optional end date filter
            whale_allocations: Current capital allocation percentages

        Returns:
            PortfolioAttribution with complete analysis
        """
        # Filter trades by date range
        filtered_trades = self._filter_trades_by_date(start_date, end_date)

        # Calculate attribution for each whale
        whale_attributions = self._calculate_whale_attributions(filtered_trades)

        # Calculate portfolio totals
        total_pnl = sum(attr.adjusted_pnl for attr in whale_attributions)
        total_trades = sum(attr.total_trades for attr in whale_attributions)
        total_wins = sum(attr.winning_trades for attr in whale_attributions)
        portfolio_win_rate = Decimal(str(total_wins / total_trades)) if total_trades > 0 else Decimal("0")

        # Rank whales
        self._rank_whales(whale_attributions)

        # Identify top/bottom performers
        sorted_by_pnl = sorted(whale_attributions, key=lambda x: x.adjusted_pnl, reverse=True)
        sorted_by_win_rate = sorted(whale_attributions, key=lambda x: x.win_rate, reverse=True)

        top_5_pnl = sorted_by_pnl[:5]
        top_5_win_rate = sorted_by_win_rate[:5]
        bottom_5_pnl = sorted_by_pnl[-5:]

        # Detect high overlap pairs
        high_overlap_pairs = self._detect_high_overlap_pairs(whale_attributions)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            whale_attributions,
            whale_allocations or {}
        )

        attribution = PortfolioAttribution(
            period=period,
            start_date=start_date or datetime.now() - timedelta(days=365),
            end_date=end_date or datetime.now(),
            total_pnl=total_pnl,
            total_trades=total_trades,
            portfolio_win_rate=portfolio_win_rate,
            whale_attributions=whale_attributions,
            top_5_by_pnl=top_5_pnl,
            top_5_by_win_rate=top_5_win_rate,
            bottom_5_by_pnl=bottom_5_pnl,
            recommendations=recommendations,
            high_overlap_pairs=high_overlap_pairs
        )

        logger.info(
            f"Portfolio attribution calculated: {len(whale_attributions)} whales | "
            f"{total_trades} trades | "
            f"Total P&L: ${float(total_pnl):,.2f} | "
            f"{len(recommendations)} recommendations"
        )

        return attribution

    def get_whale_attribution(
        self,
        whale_address: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[WhaleAttribution]:
        """Get attribution for a specific whale"""
        filtered_trades = self._filter_trades_by_date(start_date, end_date)
        whale_trade_ids = [
            trade_id for trade_id in self.whale_trades.get(whale_address, [])
            if trade_id in filtered_trades
        ]

        if not whale_trade_ids:
            return None

        trades = [filtered_trades[tid] for tid in whale_trade_ids]
        return self._calculate_single_whale_attribution(whale_address, trades)

    # ==================== Private Methods ====================

    def _calculate_correlation_factor(
        self,
        whale_address: str,
        market_id: str,
        correlated_whales: List[str]
    ) -> Decimal:
        """
        Calculate correlation factor for attribution adjustment

        If multiple whales are in same market, split the attribution
        """
        if not correlated_whales:
            return Decimal("1.0")  # No correlation, full attribution

        # Count whales in this market (including current whale)
        whales_in_market = len(correlated_whales) + 1

        if whales_in_market == 1:
            return Decimal("1.0")

        # Method: PROPORTIONAL - split equally
        if self.config.correlation_attribution_method == "PROPORTIONAL":
            return Decimal("1.0") / Decimal(str(whales_in_market))

        # Method: FIRST_MOVER - first whale gets full credit
        # (Would need timestamp comparison - simplified here)
        return Decimal("1.0")

    def _filter_trades_by_date(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> Dict[str, TradeAttribution]:
        """Filter trades by date range"""
        filtered = {}
        for trade_id, attribution in self.trade_attributions.items():
            if start_date and attribution.timestamp < start_date:
                continue
            if end_date and attribution.timestamp > end_date:
                continue
            filtered[trade_id] = attribution
        return filtered

    def _calculate_whale_attributions(
        self,
        trades: Dict[str, TradeAttribution]
    ) -> List[WhaleAttribution]:
        """Calculate attribution for all whales"""
        whale_trade_map = defaultdict(list)
        for trade_id, attribution in trades.items():
            whale_trade_map[attribution.whale_address].append(attribution)

        attributions = []
        for whale_address, whale_trades_list in whale_trade_map.items():
            attribution = self._calculate_single_whale_attribution(whale_address, whale_trades_list)
            attributions.append(attribution)

        return attributions

    def _calculate_single_whale_attribution(
        self,
        whale_address: str,
        trades: List[TradeAttribution]
    ) -> WhaleAttribution:
        """Calculate attribution for a single whale"""
        if not trades:
            return WhaleAttribution(
                whale_address=whale_address,
                total_pnl=Decimal("0"),
                adjusted_pnl=Decimal("0"),
                attribution_pct=Decimal("0"),
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_volume=Decimal("0"),
                avg_position_size=Decimal("0"),
                avg_pnl_per_trade=Decimal("0"),
                best_trade_pnl=Decimal("0"),
                worst_trade_pnl=Decimal("0"),
                correlation_overlap_pct=Decimal("0"),
                unique_contribution_pct=Decimal("0"),
                trades=[]
            )

        # P&L metrics
        total_pnl = sum(t.pnl for t in trades)
        adjusted_pnl = sum(t.adjusted_pnl for t in trades)

        # Trade metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal("0")

        # Size metrics
        total_volume = sum(t.size_usd for t in trades)
        avg_position_size = total_volume / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

        # Performance metrics
        avg_pnl_per_trade = adjusted_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")
        best_trade_pnl = max(t.pnl for t in trades)
        worst_trade_pnl = min(t.pnl for t in trades)

        # Correlation metrics
        correlation_adjusted_trades = len([t for t in trades if t.correlation_factor < Decimal("1.0")])
        correlation_overlap_pct = (
            Decimal(str(correlation_adjusted_trades / total_trades))
            if total_trades > 0 else Decimal("0")
        )

        unique_contribution_pct = (
            adjusted_pnl / total_pnl if total_pnl != 0 else Decimal("1.0")
        )

        return WhaleAttribution(
            whale_address=whale_address,
            total_pnl=total_pnl,
            adjusted_pnl=adjusted_pnl,
            attribution_pct=Decimal("0"),  # Calculated later with portfolio context
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_volume=total_volume,
            avg_position_size=avg_position_size,
            avg_pnl_per_trade=avg_pnl_per_trade,
            best_trade_pnl=best_trade_pnl,
            worst_trade_pnl=worst_trade_pnl,
            correlation_overlap_pct=correlation_overlap_pct,
            unique_contribution_pct=unique_contribution_pct,
            trades=trades
        )

    def _rank_whales(self, attributions: List[WhaleAttribution]):
        """Rank whales across multiple dimensions"""
        # Rank by adjusted PnL
        sorted_by_pnl = sorted(attributions, key=lambda x: x.adjusted_pnl, reverse=True)
        for rank, attr in enumerate(sorted_by_pnl, 1):
            attr.pnl_rank = rank

        # Rank by win rate
        sorted_by_win_rate = sorted(attributions, key=lambda x: x.win_rate, reverse=True)
        for rank, attr in enumerate(sorted_by_win_rate, 1):
            attr.win_rate_rank = rank

        # Rank by volume
        sorted_by_volume = sorted(attributions, key=lambda x: x.total_volume, reverse=True)
        for rank, attr in enumerate(sorted_by_volume, 1):
            attr.volume_rank = rank

        # Overall rank (average of ranks)
        for attr in attributions:
            avg_rank = (attr.pnl_rank + attr.win_rate_rank + attr.volume_rank) / 3
            attr.overall_rank = int(avg_rank)

        # Calculate attribution percentages
        total_pnl = sum(attr.adjusted_pnl for attr in attributions)
        if total_pnl > 0:
            for attr in attributions:
                attr.attribution_pct = attr.adjusted_pnl / total_pnl
        else:
            for attr in attributions:
                attr.attribution_pct = Decimal("0")

    def _detect_high_overlap_pairs(
        self,
        attributions: List[WhaleAttribution]
    ) -> List[Tuple[str, str, Decimal]]:
        """Detect whale pairs with high market overlap"""
        high_overlap_pairs = []

        whale_markets = {}
        for whale_addr in self.whale_trades.keys():
            markets = set()
            for trade_id in self.whale_trades[whale_addr]:
                if trade_id in self.trade_attributions:
                    markets.add(self.trade_attributions[trade_id].market_id)
            whale_markets[whale_addr] = markets

        # Check all pairs
        whale_addrs = list(whale_markets.keys())
        for i, whale1 in enumerate(whale_addrs):
            for whale2 in whale_addrs[i+1:]:
                markets1 = whale_markets[whale1]
                markets2 = whale_markets[whale2]

                if not markets1 or not markets2:
                    continue

                # Calculate overlap
                overlap = len(markets1 & markets2)
                total = len(markets1 | markets2)
                overlap_pct = Decimal(str(overlap / total)) if total > 0 else Decimal("0")

                if overlap_pct >= self.config.high_overlap_threshold:
                    high_overlap_pairs.append((whale1, whale2, overlap_pct))

        return sorted(high_overlap_pairs, key=lambda x: x[2], reverse=True)

    def _generate_recommendations(
        self,
        attributions: List[WhaleAttribution],
        whale_allocations: Dict[str, Decimal]
    ) -> List[WhaleRecommendation]:
        """Generate portfolio optimization recommendations"""
        recommendations = []

        for attr in attributions:
            # Skip whales with insufficient data
            if attr.total_trades < self.config.min_trades_for_recommendation:
                continue

            current_allocation = whale_allocations.get(attr.whale_address, Decimal("0"))
            reasoning = []

            # Determine recommendation
            recommendation_type = RecommendationType.KEEP
            suggested_allocation = current_allocation
            confidence = Decimal("0.5")

            # DISABLE: Severe losses or very low win rate
            if (attr.adjusted_pnl / attr.total_volume < self.config.disable_threshold_loss_pct or
                attr.win_rate < Decimal("0.35")):
                recommendation_type = RecommendationType.DISABLE
                suggested_allocation = Decimal("0")
                confidence = Decimal("0.90")
                reasoning.append(f"Severe losses: ${float(attr.adjusted_pnl):,.2f}")
                reasoning.append(f"Low win rate: {float(attr.win_rate)*100:.1f}%")

            # REDUCE_ALLOCATION: Moderate losses
            elif attr.adjusted_pnl / attr.total_volume < self.config.reduce_threshold_loss_pct:
                recommendation_type = RecommendationType.REDUCE_ALLOCATION
                suggested_allocation = current_allocation * Decimal("0.50")  # Reduce by 50%
                confidence = Decimal("0.75")
                reasoning.append(f"Underperforming: ${float(attr.adjusted_pnl):,.2f}")
                reasoning.append(f"Win rate: {float(attr.win_rate)*100:.1f}%")

            # MONITOR: Below average but not critical
            elif attr.overall_rank > len(attributions) * 0.7:  # Bottom 30%
                recommendation_type = RecommendationType.MONITOR
                confidence = Decimal("0.60")
                reasoning.append(f"Below average performance (rank {attr.overall_rank})")

            # KEEP: Strong performer
            else:
                recommendation_type = RecommendationType.KEEP
                confidence = Decimal("0.80")
                reasoning.append(f"Strong performer: ${float(attr.adjusted_pnl):,.2f}")
                reasoning.append(f"Win rate: {float(attr.win_rate)*100:.1f}%")
                reasoning.append(f"Rank: {attr.overall_rank} of {len(attributions)}")

            # Check for high overlap
            if attr.correlation_overlap_pct > self.config.high_overlap_threshold:
                reasoning.append(
                    f"⚠️ High overlap: {float(attr.correlation_overlap_pct)*100:.0f}% of trades correlated"
                )

            recommendation = WhaleRecommendation(
                whale_address=attr.whale_address,
                recommendation=recommendation_type,
                confidence=confidence,
                reasoning=reasoning,
                current_allocation_pct=current_allocation * Decimal("100"),
                suggested_allocation_pct=suggested_allocation * Decimal("100"),
                key_metrics={
                    "adjusted_pnl": f"${float(attr.adjusted_pnl):,.2f}",
                    "win_rate": f"{float(attr.win_rate)*100:.1f}%",
                    "total_trades": str(attr.total_trades),
                    "attribution_pct": f"{float(attr.attribution_pct)*100:.1f}%",
                    "overall_rank": f"{attr.overall_rank} of {len(attributions)}"
                }
            )

            recommendations.append(recommendation)

        return sorted(recommendations, key=lambda x: x.confidence, reverse=True)

    def get_statistics(self) -> Dict:
        """Get attribution system statistics"""
        correlation_adjustment_rate = (
            self.correlation_adjustments_applied / self.attributions_calculated
            if self.attributions_calculated > 0 else 0
        )

        return {
            "total_attributions": self.attributions_calculated,
            "correlation_adjustments": {
                "count": self.correlation_adjustments_applied,
                "rate": f"{correlation_adjustment_rate*100:.1f}%"
            },
            "unique_whales": len(self.whale_trades),
            "unique_markets": len(self.market_whales),
            "attribution_method": self.config.correlation_attribution_method
        }


# ==================== Example Usage ====================

def main():
    """Example usage of WhalePerformanceAttributor"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize attributor
    attributor = WhalePerformanceAttributor()

    print("\n=== Whale Performance Attribution Test ===\n")

    # Simulate some trades
    base_time = datetime.now() - timedelta(days=30)

    whales = [f"0x{i:040x}" for i in range(5)]

    print("=== Recording Trades ===")

    # Whale 0: Strong performer, unique markets
    for i in range(15):
        attributor.record_trade(
            trade_id=f"trade_w0_{i}",
            whale_address=whales[0],
            market_id=f"market_{i}",
            outcome="YES",
            size_usd=Decimal("1000"),
            pnl=Decimal("150") if i % 3 != 0 else Decimal("-50"),
            timestamp=base_time + timedelta(days=i),
            correlated_whales=[]
        )

    # Whale 1: Good performer, some overlap with Whale 0
    for i in range(12):
        correlated = [whales[0]] if i % 3 == 0 else []
        attributor.record_trade(
            trade_id=f"trade_w1_{i}",
            whale_address=whales[1],
            market_id=f"market_{i}" if i % 3 == 0 else f"market_w1_{i}",
            outcome="NO",
            size_usd=Decimal("800"),
            pnl=Decimal("120") if i % 4 != 0 else Decimal("-80"),
            timestamp=base_time + timedelta(days=i),
            correlated_whales=correlated
        )

    # Whale 2: Poor performer
    for i in range(10):
        attributor.record_trade(
            trade_id=f"trade_w2_{i}",
            whale_address=whales[2],
            market_id=f"market_w2_{i}",
            outcome="YES",
            size_usd=Decimal("500"),
            pnl=Decimal("-100"),
            timestamp=base_time + timedelta(days=i),
            correlated_whales=[]
        )

    print(f"✓ Recorded {attributor.attributions_calculated} trades\n")

    # Calculate portfolio attribution
    print("=== Portfolio Attribution ===")
    whale_allocations = {
        whales[0]: Decimal("0.30"),
        whales[1]: Decimal("0.25"),
        whales[2]: Decimal("0.20"),
    }

    attribution = attributor.calculate_portfolio_attribution(
        period=AttributionPeriod.MONTHLY,
        whale_allocations=whale_allocations
    )

    print(f"Total Portfolio P&L: ${float(attribution.total_pnl):,.2f}")
    print(f"Total Trades: {attribution.total_trades}")
    print(f"Portfolio Win Rate: {float(attribution.portfolio_win_rate)*100:.1f}%\n")

    print("=== Top 3 Performers (by P&L) ===")
    for i, attr in enumerate(attribution.top_5_by_pnl[:3], 1):
        print(f"{i}. {attr.whale_address[:10]}...")
        print(f"   Adjusted P&L: ${float(attr.adjusted_pnl):,.2f}")
        print(f"   Attribution: {float(attr.attribution_pct)*100:.1f}%")
        print(f"   Win Rate: {float(attr.win_rate)*100:.1f}%")
        print(f"   Trades: {attr.total_trades}")
        print(f"   Overlap: {float(attr.correlation_overlap_pct)*100:.0f}%\n")

    print("=== Recommendations ===")
    for rec in attribution.recommendations[:5]:
        print(f"\n{rec.whale_address[:10]}... | {rec.recommendation.value}")
        print(f"Confidence: {float(rec.confidence)*100:.0f}%")
        print(f"Current Allocation: {float(rec.current_allocation_pct):.1f}%")
        print(f"Suggested Allocation: {float(rec.suggested_allocation_pct):.1f}%")
        print("Reasoning:")
        for reason in rec.reasoning:
            print(f"  - {reason}")

    print("\n=== High Overlap Pairs ===")
    if attribution.high_overlap_pairs:
        for w1, w2, overlap in attribution.high_overlap_pairs:
            print(f"{w1[:10]}... ↔ {w2[:10]}... | {float(overlap)*100:.0f}% overlap")
    else:
        print("No high overlap detected")

    # Get statistics
    print("\n=== Attribution Statistics ===")
    import json
    stats = attributor.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
