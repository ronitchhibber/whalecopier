"""
Week 9: Performance Analytics - Trade Attribution Analyzer

This module provides detailed P&L attribution analysis:
- P&L breakdown by whale address
- P&L breakdown by market
- P&L breakdown by topic/category
- Win/loss analysis per segment
- Time-of-day performance patterns
- Market condition impact analysis

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class AttributionDimension(Enum):
    """Dimensions for attribution analysis"""
    WHALE = "whale"
    MARKET = "market"
    TOPIC = "topic"
    HOUR_OF_DAY = "hour"
    DAY_OF_WEEK = "day"
    MARKET_CONDITION = "condition"


class MarketCondition(Enum):
    """Market condition types"""
    HIGH_VOLATILITY = "high_vol"
    LOW_VOLATILITY = "low_vol"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"


@dataclass
class AttributionConfig:
    """Configuration for attribution analysis"""

    # Update frequency
    update_interval_seconds: int = 300  # Update every 5 minutes

    # Minimum thresholds for significance
    min_trades_for_significance: int = 10
    min_pnl_for_significance: Decimal = Decimal("100")

    # Time windows
    analysis_lookback_days: int = 90

    # Top N for rankings
    top_n_performers: int = 10
    top_n_markets: int = 20

    # Database paths
    trades_db_path: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/data/trades.db"


@dataclass
class Trade:
    """Individual trade record"""
    trade_id: str
    whale_address: str
    market_id: str
    market_topic: str
    side: str
    entry_price: Decimal
    exit_price: Optional[Decimal]
    position_size_usd: Decimal
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl_usd: Decimal
    pnl_pct: Decimal
    is_open: bool


@dataclass
class AttributionResult:
    """Attribution analysis result for a specific dimension and segment"""

    # Identification
    dimension: AttributionDimension
    segment: str  # e.g., whale address, market ID, topic name
    calculation_time: datetime

    # P&L metrics
    total_pnl_usd: Decimal
    total_pnl_pct: Decimal
    contribution_to_total_pct: Decimal  # % of total portfolio P&L

    # Trade counts
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal

    # Average metrics
    avg_pnl_per_trade_usd: Decimal
    avg_win_usd: Decimal
    avg_loss_usd: Decimal

    # Risk metrics
    profit_factor: Decimal
    payoff_ratio: Decimal
    sharpe_ratio: Decimal

    # Volume
    total_volume_usd: Decimal

    # Rankings
    rank: int  # Rank by P&L
    rank_by_win_rate: int
    rank_by_profit_factor: int

    # Quality indicators
    is_significant: bool  # Meets minimum thresholds
    confidence_score: Decimal  # 0-100 based on sample size


@dataclass
class WinLossAnalysis:
    """Detailed win/loss analysis"""

    # Winning trades
    winning_trades_count: int
    winning_trades_total_pnl: Decimal
    winning_trades_avg_pnl: Decimal
    winning_trades_largest: Decimal

    # Losing trades
    losing_trades_count: int
    losing_trades_total_pnl: Decimal
    losing_trades_avg_pnl: Decimal
    losing_trades_largest: Decimal

    # Breakeven
    breakeven_trades_count: int

    # Win streaks
    longest_win_streak: int
    longest_loss_streak: int
    current_streak: int
    current_streak_type: str  # "WIN" or "LOSS"


@dataclass
class TimeOfDayAnalysis:
    """Performance analysis by time of day"""
    hour: int
    total_trades: int
    win_rate_pct: Decimal
    total_pnl_usd: Decimal
    avg_pnl_usd: Decimal
    best_performing: bool


@dataclass
class DayOfWeekAnalysis:
    """Performance analysis by day of week"""
    day_name: str  # "Monday", "Tuesday", etc.
    day_number: int  # 0=Monday, 6=Sunday
    total_trades: int
    win_rate_pct: Decimal
    total_pnl_usd: Decimal
    avg_pnl_usd: Decimal
    best_performing: bool


class TradeAttributionAnalyzer:
    """
    Comprehensive trade attribution analyzer.

    Breaks down P&L by:
    - Whale address (which whales contribute most?)
    - Market (which markets are most profitable?)
    - Topic/category (crypto, politics, sports, etc.)
    - Time of day (are there profitable hours?)
    - Day of week (are certain days better?)
    - Market conditions (how do we perform in different environments?)
    """

    def __init__(self, config: AttributionConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.total_pnl: Decimal = Decimal("0")

        # Cached attribution results
        self.attribution_by_whale: List[AttributionResult] = []
        self.attribution_by_market: List[AttributionResult] = []
        self.attribution_by_topic: List[AttributionResult] = []

        # Time-based analysis
        self.time_of_day_analysis: List[TimeOfDayAnalysis] = []
        self.day_of_week_analysis: List[DayOfWeekAnalysis] = []

        # Win/loss by segment
        self.win_loss_by_whale: Dict[str, WinLossAnalysis] = {}
        self.win_loss_by_market: Dict[str, WinLossAnalysis] = {}
        self.win_loss_by_topic: Dict[str, WinLossAnalysis] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("TradeAttributionAnalyzer initialized")

    async def start(self):
        """Start the attribution analyzer"""
        if self.is_running:
            logger.warning("TradeAttributionAnalyzer already running")
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())

        logger.info("TradeAttributionAnalyzer started")

    async def stop(self):
        """Stop the attribution analyzer"""
        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        logger.info("TradeAttributionAnalyzer stopped")

    async def _update_loop(self):
        """Background loop to update attribution analysis"""
        while self.is_running:
            try:
                # Perform full attribution analysis
                await self.analyze_all()

                # Log summary
                logger.info(
                    f"Attribution Analysis Update - "
                    f"Whales: {len(self.attribution_by_whale)}, "
                    f"Markets: {len(self.attribution_by_market)}, "
                    f"Topics: {len(self.attribution_by_topic)}"
                )

                await asyncio.sleep(self.config.update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in attribution update loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    def add_trade(self, trade: Trade):
        """Add a trade to the attribution history"""
        self.trades.append(trade)

        if not trade.is_open:
            self.total_pnl += trade.pnl_usd

        logger.debug(f"Added trade {trade.trade_id} to attribution history")

    async def analyze_all(self):
        """Perform comprehensive attribution analysis across all dimensions"""

        # Analyze by whale
        self.attribution_by_whale = await self.analyze_by_dimension(AttributionDimension.WHALE)

        # Analyze by market
        self.attribution_by_market = await self.analyze_by_dimension(AttributionDimension.MARKET)

        # Analyze by topic
        self.attribution_by_topic = await self.analyze_by_dimension(AttributionDimension.TOPIC)

        # Analyze time patterns
        self.time_of_day_analysis = await self.analyze_time_of_day()
        self.day_of_week_analysis = await self.analyze_day_of_week()

        # Analyze win/loss patterns
        self.win_loss_by_whale = await self.analyze_win_loss_by_segment(AttributionDimension.WHALE)
        self.win_loss_by_market = await self.analyze_win_loss_by_segment(AttributionDimension.MARKET)
        self.win_loss_by_topic = await self.analyze_win_loss_by_segment(AttributionDimension.TOPIC)

        logger.info("Completed full attribution analysis")

    async def analyze_by_dimension(self, dimension: AttributionDimension) -> List[AttributionResult]:
        """
        Analyze attribution for a specific dimension.

        Args:
            dimension: Dimension to analyze (whale, market, topic, etc.)

        Returns:
            List of attribution results, sorted by P&L (descending)
        """

        # Filter trades
        trades = self._filter_recent_trades()

        if not trades:
            return []

        # Group trades by dimension
        trades_by_segment = self._group_trades_by_dimension(trades, dimension)

        # Calculate attribution for each segment
        results: List[AttributionResult] = []

        for segment, segment_trades in trades_by_segment.items():
            result = self._calculate_attribution(dimension, segment, segment_trades)
            results.append(result)

        # Sort by P&L (descending)
        results.sort(key=lambda r: r.total_pnl_usd, reverse=True)

        # Assign ranks
        for rank, result in enumerate(results, 1):
            result.rank = rank

        # Assign win rate ranks
        sorted_by_win_rate = sorted(results, key=lambda r: r.win_rate_pct, reverse=True)
        for rank, result in enumerate(sorted_by_win_rate, 1):
            result.rank_by_win_rate = rank

        # Assign profit factor ranks
        sorted_by_pf = sorted(results, key=lambda r: r.profit_factor, reverse=True)
        for rank, result in enumerate(sorted_by_pf, 1):
            result.rank_by_profit_factor = rank

        return results

    def _group_trades_by_dimension(self, trades: List[Trade], dimension: AttributionDimension) -> Dict[str, List[Trade]]:
        """Group trades by dimension"""
        grouped: Dict[str, List[Trade]] = defaultdict(list)

        for trade in trades:
            if dimension == AttributionDimension.WHALE:
                key = trade.whale_address
            elif dimension == AttributionDimension.MARKET:
                key = trade.market_id
            elif dimension == AttributionDimension.TOPIC:
                key = trade.market_topic
            elif dimension == AttributionDimension.HOUR_OF_DAY:
                key = str(trade.entry_time.hour) if trade.entry_time else "unknown"
            elif dimension == AttributionDimension.DAY_OF_WEEK:
                key = trade.entry_time.strftime("%A") if trade.entry_time else "unknown"
            else:
                key = "unknown"

            grouped[key].append(trade)

        return dict(grouped)

    def _calculate_attribution(self, dimension: AttributionDimension, segment: str,
                               trades: List[Trade]) -> AttributionResult:
        """Calculate attribution for a specific segment"""

        # P&L metrics
        total_pnl = sum(t.pnl_usd for t in trades if not t.is_open)
        contribution_pct = (total_pnl / self.total_pnl * Decimal("100")) if self.total_pnl != 0 else Decimal("0")

        # Trade counts
        closed_trades = [t for t in trades if not t.is_open]
        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if t.pnl_usd > 0])
        losing_trades = len([t for t in closed_trades if t.pnl_usd < 0])

        # Win rate
        win_rate_pct = (Decimal(str(winning_trades)) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

        # Average P&L
        avg_pnl = total_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

        # Average win/loss
        winning_pnl = [t.pnl_usd for t in closed_trades if t.pnl_usd > 0]
        losing_pnl = [t.pnl_usd for t in closed_trades if t.pnl_usd < 0]

        avg_win = sum(winning_pnl) / Decimal(str(len(winning_pnl))) if winning_pnl else Decimal("0")
        avg_loss = sum(losing_pnl) / Decimal(str(len(losing_pnl))) if losing_pnl else Decimal("0")

        # Profit factor
        gross_profit = sum(winning_pnl)
        gross_loss = abs(sum(losing_pnl))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("999")

        # Payoff ratio
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else Decimal("999")

        # Sharpe ratio (simplified)
        if total_trades > 2:
            returns = [t.pnl_pct for t in closed_trades]
            mean_return = sum(returns) / Decimal(str(len(returns)))
            variance = sum((r - mean_return) ** 2 for r in returns) / Decimal(str(len(returns)))
            std_dev = variance ** Decimal("0.5")
            sharpe_ratio = mean_return / std_dev if std_dev > 0 else Decimal("0")
        else:
            sharpe_ratio = Decimal("0")

        # Volume
        total_volume = sum(t.position_size_usd for t in trades)

        # Significance
        is_significant = (
            total_trades >= self.config.min_trades_for_significance and
            abs(total_pnl) >= self.config.min_pnl_for_significance
        )

        # Confidence score (based on sample size)
        if total_trades >= 100:
            confidence = Decimal("100")
        elif total_trades >= 50:
            confidence = Decimal("90")
        elif total_trades >= 30:
            confidence = Decimal("80")
        elif total_trades >= 20:
            confidence = Decimal("70")
        elif total_trades >= 10:
            confidence = Decimal("60")
        else:
            confidence = Decimal("50")

        # Calculate total P&L %
        total_pnl_pct = sum(t.pnl_pct for t in closed_trades) if closed_trades else Decimal("0")

        return AttributionResult(
            dimension=dimension,
            segment=segment,
            calculation_time=datetime.now(),
            total_pnl_usd=total_pnl,
            total_pnl_pct=total_pnl_pct,
            contribution_to_total_pct=contribution_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=win_rate_pct,
            avg_pnl_per_trade_usd=avg_pnl,
            avg_win_usd=avg_win,
            avg_loss_usd=avg_loss,
            profit_factor=profit_factor,
            payoff_ratio=payoff_ratio,
            sharpe_ratio=sharpe_ratio,
            total_volume_usd=total_volume,
            rank=0,  # Will be assigned later
            rank_by_win_rate=0,
            rank_by_profit_factor=0,
            is_significant=is_significant,
            confidence_score=confidence
        )

    async def analyze_win_loss_by_segment(self, dimension: AttributionDimension) -> Dict[str, WinLossAnalysis]:
        """Analyze detailed win/loss patterns by segment"""

        trades = self._filter_recent_trades()
        trades_by_segment = self._group_trades_by_dimension(trades, dimension)

        win_loss_analysis: Dict[str, WinLossAnalysis] = {}

        for segment, segment_trades in trades_by_segment.items():
            analysis = self._calculate_win_loss_analysis(segment_trades)
            win_loss_analysis[segment] = analysis

        return win_loss_analysis

    def _calculate_win_loss_analysis(self, trades: List[Trade]) -> WinLossAnalysis:
        """Calculate detailed win/loss analysis"""

        closed_trades = [t for t in trades if not t.is_open]

        winning = [t for t in closed_trades if t.pnl_usd > 0]
        losing = [t for t in closed_trades if t.pnl_usd < 0]
        breakeven = [t for t in closed_trades if t.pnl_usd == 0]

        # Winning trades
        winning_count = len(winning)
        winning_total = sum(t.pnl_usd for t in winning)
        winning_avg = winning_total / Decimal(str(winning_count)) if winning_count > 0 else Decimal("0")
        winning_largest = max((t.pnl_usd for t in winning), default=Decimal("0"))

        # Losing trades
        losing_count = len(losing)
        losing_total = sum(t.pnl_usd for t in losing)
        losing_avg = losing_total / Decimal(str(losing_count)) if losing_count > 0 else Decimal("0")
        losing_largest = min((t.pnl_usd for t in losing), default=Decimal("0"))

        # Breakeven
        breakeven_count = len(breakeven)

        # Streaks
        longest_win, longest_loss, current_streak, current_type = self._calculate_streaks(closed_trades)

        return WinLossAnalysis(
            winning_trades_count=winning_count,
            winning_trades_total_pnl=winning_total,
            winning_trades_avg_pnl=winning_avg,
            winning_trades_largest=winning_largest,
            losing_trades_count=losing_count,
            losing_trades_total_pnl=losing_total,
            losing_trades_avg_pnl=losing_avg,
            losing_trades_largest=losing_largest,
            breakeven_trades_count=breakeven_count,
            longest_win_streak=longest_win,
            longest_loss_streak=longest_loss,
            current_streak=current_streak,
            current_streak_type=current_type
        )

    def _calculate_streaks(self, trades: List[Trade]) -> Tuple[int, int, int, str]:
        """Calculate win/loss streaks"""

        if not trades:
            return 0, 0, 0, ""

        sorted_trades = sorted(trades, key=lambda t: t.exit_time or datetime.max)

        longest_win = 0
        longest_loss = 0
        current_win = 0
        current_loss = 0

        for trade in sorted_trades:
            if trade.pnl_usd > 0:
                current_win += 1
                current_loss = 0
                longest_win = max(longest_win, current_win)
            elif trade.pnl_usd < 0:
                current_loss += 1
                current_win = 0
                longest_loss = max(longest_loss, current_loss)

        # Current streak
        if current_win > 0:
            current_streak = current_win
            current_type = "WIN"
        elif current_loss > 0:
            current_streak = current_loss
            current_type = "LOSS"
        else:
            current_streak = 0
            current_type = ""

        return longest_win, longest_loss, current_streak, current_type

    async def analyze_time_of_day(self) -> List[TimeOfDayAnalysis]:
        """Analyze performance by hour of day"""

        trades = self._filter_recent_trades()

        # Group by hour
        trades_by_hour: Dict[int, List[Trade]] = defaultdict(list)

        for trade in trades:
            if not trade.is_open and trade.entry_time:
                hour = trade.entry_time.hour
                trades_by_hour[hour].append(trade)

        # Calculate metrics for each hour
        hourly_analysis: List[TimeOfDayAnalysis] = []

        for hour in range(24):
            hour_trades = trades_by_hour.get(hour, [])

            if not hour_trades:
                continue

            total_trades = len(hour_trades)
            winning = len([t for t in hour_trades if t.pnl_usd > 0])
            win_rate = (Decimal(str(winning)) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

            total_pnl = sum(t.pnl_usd for t in hour_trades)
            avg_pnl = total_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

            hourly_analysis.append(TimeOfDayAnalysis(
                hour=hour,
                total_trades=total_trades,
                win_rate_pct=win_rate,
                total_pnl_usd=total_pnl,
                avg_pnl_usd=avg_pnl,
                best_performing=False  # Will be set later
            ))

        # Mark best performing hour
        if hourly_analysis:
            best_hour = max(hourly_analysis, key=lambda h: h.total_pnl_usd)
            best_hour.best_performing = True

        return hourly_analysis

    async def analyze_day_of_week(self) -> List[DayOfWeekAnalysis]:
        """Analyze performance by day of week"""

        trades = self._filter_recent_trades()

        # Group by day
        trades_by_day: Dict[int, List[Trade]] = defaultdict(list)

        for trade in trades:
            if not trade.is_open and trade.entry_time:
                day_num = trade.entry_time.weekday()  # 0=Monday, 6=Sunday
                trades_by_day[day_num].append(trade)

        # Calculate metrics for each day
        daily_analysis: List[DayOfWeekAnalysis] = []

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day_num in range(7):
            day_trades = trades_by_day.get(day_num, [])

            if not day_trades:
                continue

            total_trades = len(day_trades)
            winning = len([t for t in day_trades if t.pnl_usd > 0])
            win_rate = (Decimal(str(winning)) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

            total_pnl = sum(t.pnl_usd for t in day_trades)
            avg_pnl = total_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

            daily_analysis.append(DayOfWeekAnalysis(
                day_name=day_names[day_num],
                day_number=day_num,
                total_trades=total_trades,
                win_rate_pct=win_rate,
                total_pnl_usd=total_pnl,
                avg_pnl_usd=avg_pnl,
                best_performing=False
            ))

        # Mark best performing day
        if daily_analysis:
            best_day = max(daily_analysis, key=lambda d: d.total_pnl_usd)
            best_day.best_performing = True

        return daily_analysis

    def _filter_recent_trades(self) -> List[Trade]:
        """Filter trades within the analysis lookback window"""
        cutoff = datetime.now() - timedelta(days=self.config.analysis_lookback_days)
        return [t for t in self.trades if not t.is_open and t.exit_time and t.exit_time >= cutoff]

    def get_top_performers(self, dimension: AttributionDimension, n: Optional[int] = None) -> List[AttributionResult]:
        """Get top N performers for a dimension"""

        if n is None:
            n = self.config.top_n_performers

        if dimension == AttributionDimension.WHALE:
            results = self.attribution_by_whale
        elif dimension == AttributionDimension.MARKET:
            results = self.attribution_by_market
        elif dimension == AttributionDimension.TOPIC:
            results = self.attribution_by_topic
        else:
            return []

        return results[:n]

    def get_worst_performers(self, dimension: AttributionDimension, n: Optional[int] = None) -> List[AttributionResult]:
        """Get worst N performers for a dimension"""

        if n is None:
            n = self.config.top_n_performers

        if dimension == AttributionDimension.WHALE:
            results = self.attribution_by_whale
        elif dimension == AttributionDimension.MARKET:
            results = self.attribution_by_market
        elif dimension == AttributionDimension.TOPIC:
            results = self.attribution_by_topic
        else:
            return []

        # Return bottom N
        return results[-n:]

    def print_attribution_summary(self, dimension: AttributionDimension, top_n: int = 10):
        """Print attribution summary for a dimension"""

        if dimension == AttributionDimension.WHALE:
            results = self.attribution_by_whale
            title = "WHALE"
        elif dimension == AttributionDimension.MARKET:
            results = self.attribution_by_market
            title = "MARKET"
        elif dimension == AttributionDimension.TOPIC:
            results = self.attribution_by_topic
            title = "TOPIC"
        else:
            return

        print(f"\n{'='*100}")
        print(f"ATTRIBUTION ANALYSIS - BY {title}")
        print(f"{'='*100}\n")

        print(f"Total segments: {len(results)}")
        print(f"Total P&L: ${self.total_pnl:,.2f}\n")

        print(f"{'Rank':<6}{'Segment':<30}{'P&L':<15}{'Contrib%':<10}{'Trades':<8}{'WinRate':<10}{'PF':<8}{'Sharpe':<8}")
        print("-" * 100)

        for result in results[:top_n]:
            segment_display = result.segment[:28] if len(result.segment) > 28 else result.segment

            print(
                f"{result.rank:<6}"
                f"{segment_display:<30}"
                f"${result.total_pnl_usd:>12,.2f}  "
                f"{result.contribution_to_total_pct:>7.1f}%  "
                f"{result.total_trades:<8}"
                f"{result.win_rate_pct:>7.1f}%  "
                f"{result.profit_factor:>6.2f}  "
                f"{result.sharpe_ratio:>6.2f}"
            )

        print("\n")

    def print_time_analysis(self):
        """Print time-based analysis"""

        print(f"\n{'='*80}")
        print("TIME-BASED PERFORMANCE ANALYSIS")
        print(f"{'='*80}\n")

        # Hour of day
        print("PERFORMANCE BY HOUR OF DAY:")
        print(f"{'Hour':<10}{'Trades':<10}{'Win Rate':<12}{'Total P&L':<15}{'Avg P&L':<15}")
        print("-" * 80)

        for hour_analysis in sorted(self.time_of_day_analysis, key=lambda h: h.hour):
            best_mark = " ★" if hour_analysis.best_performing else ""

            print(
                f"{hour_analysis.hour:02d}:00{best_mark:<6}"
                f"{hour_analysis.total_trades:<10}"
                f"{hour_analysis.win_rate_pct:>8.1f}%   "
                f"${hour_analysis.total_pnl_usd:>12,.2f}  "
                f"${hour_analysis.avg_pnl_usd:>12,.2f}"
            )

        # Day of week
        print("\n\nPERFORMANCE BY DAY OF WEEK:")
        print(f"{'Day':<12}{'Trades':<10}{'Win Rate':<12}{'Total P&L':<15}{'Avg P&L':<15}")
        print("-" * 80)

        for day_analysis in sorted(self.day_of_week_analysis, key=lambda d: d.day_number):
            best_mark = " ★" if day_analysis.best_performing else ""

            print(
                f"{day_analysis.day_name}{best_mark:<3}"
                f"{day_analysis.total_trades:<10}"
                f"{day_analysis.win_rate_pct:>8.1f}%   "
                f"${day_analysis.total_pnl_usd:>12,.2f}  "
                f"${day_analysis.avg_pnl_usd:>12,.2f}"
            )

        print("\n")


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize analyzer
        config = AttributionConfig()
        analyzer = TradeAttributionAnalyzer(config)

        # Add sample trades
        print("Adding sample trades...")

        whales = [f"0xwhale{i}" for i in range(5)]
        markets = [f"market_{i}" for i in range(10)]
        topics = ["Politics", "Crypto", "Sports", "Entertainment"]

        for i in range(200):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=whales[i % len(whales)],
                market_id=markets[i % len(markets)],
                market_topic=topics[i % len(topics)],
                side="BUY" if i % 3 == 0 else "SELL",
                entry_price=Decimal("0.55"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.52"),
                position_size_usd=Decimal("1000"),
                entry_time=datetime.now() - timedelta(days=100-i//2, hours=i % 24),
                exit_time=datetime.now() - timedelta(days=100-i//2-1, hours=(i+1) % 24),
                pnl_usd=Decimal("50") if i % 2 == 0 else Decimal("-30"),
                pnl_pct=Decimal("5.0") if i % 2 == 0 else Decimal("-3.0"),
                is_open=False
            )
            analyzer.add_trade(trade)

        print(f"Added {len(analyzer.trades)} trades")

        # Perform attribution analysis
        print("\nPerforming attribution analysis...")
        await analyzer.analyze_all()

        # Print results
        analyzer.print_attribution_summary(AttributionDimension.WHALE)
        analyzer.print_attribution_summary(AttributionDimension.MARKET)
        analyzer.print_attribution_summary(AttributionDimension.TOPIC)
        analyzer.print_time_analysis()

        print("\nAttribution analysis complete!")

    asyncio.run(main())
