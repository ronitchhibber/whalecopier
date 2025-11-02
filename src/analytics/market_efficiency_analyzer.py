"""
Week 10: Edge Detection & Decay - Market Efficiency Analyzer

This module measures market efficiency and edge persistence:
- Time from whale trade to market equilibrium
- Edge disappearance speed (how fast edge degrades)
- Most/least efficient markets identification
- Impact on copy trading profitability

Efficient markets = edge disappears quickly = less profitable for copying
Inefficient markets = edge persists longer = more profitable for copying

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


class EfficiencyLevel(Enum):
    """Market efficiency levels"""
    HIGHLY_EFFICIENT = "highly_efficient"  # Edge gone < 1 hour
    EFFICIENT = "efficient"                # Edge gone 1-4 hours
    MODERATE = "moderate"                  # Edge gone 4-12 hours
    INEFFICIENT = "inefficient"            # Edge gone > 12 hours


@dataclass
class EfficiencyConfig:
    """Configuration for efficiency analysis"""
    update_interval_seconds: int = 300
    time_to_equilibrium_windows: List[int] = None  # Hours: [1, 4, 12, 24]
    min_price_move_threshold: Decimal = Decimal("0.01")  # 1% price move

    def __post_init__(self):
        if self.time_to_equilibrium_windows is None:
            self.time_to_equilibrium_windows = [1, 4, 12, 24]


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    whale_address: str
    market_id: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: Decimal
    exit_price: Optional[Decimal]
    pnl_usd: Decimal
    is_open: bool


@dataclass
class MarketEfficiencyMetrics:
    """Market efficiency metrics"""

    market_id: str
    calculation_time: datetime

    # Time to equilibrium (hours)
    avg_time_to_equilibrium: Decimal
    median_time_to_equilibrium: Decimal
    min_time_to_equilibrium: Decimal
    max_time_to_equilibrium: Decimal

    # Edge persistence
    edge_half_life_hours: Decimal  # Time for edge to decay to 50%
    edge_disappearance_speed: Decimal  # % per hour

    # Efficiency classification
    efficiency_level: EfficiencyLevel
    is_profitable_for_copying: bool

    # Trade statistics
    total_whale_trades: int
    avg_price_impact: Decimal
    avg_edge_at_entry: Decimal
    avg_edge_at_exit: Decimal

    # Profitability
    avg_copy_trader_pnl: Decimal
    success_rate_pct: Decimal


class MarketEfficiencyAnalyzer:
    """
    Analyzes market efficiency and edge persistence.

    Key concept: In efficient markets, whale trades quickly move prices to equilibrium,
    leaving little edge for copy traders. In inefficient markets, edge persists longer.

    Metrics calculated:
    - Time to equilibrium: How long until market price stabilizes after whale trade
    - Edge half-life: Time for profitable edge to decay 50%
    - Edge disappearance speed: Rate of edge decay

    Applications:
    - Identify most profitable markets for copy trading (inefficient markets)
    - Adjust copy speed based on market efficiency
    - Skip highly efficient markets
    """

    def __init__(self, config: EfficiencyConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.market_metrics: Dict[str, MarketEfficiencyMetrics] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("MarketEfficiencyAnalyzer initialized")

    async def start(self):
        """Start analyzer"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("MarketEfficiencyAnalyzer started")

    async def stop(self):
        """Stop analyzer"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("MarketEfficiencyAnalyzer stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                await self.analyze_all_markets()
                logger.info(f"Market efficiency analysis complete - {len(self.market_metrics)} markets analyzed")
                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"Market efficiency analysis error: {e}", exc_info=True)
                await asyncio.sleep(30)

    def add_trade(self, trade: Trade):
        """Add trade"""
        self.trades.append(trade)

    async def analyze_all_markets(self):
        """Analyze efficiency for all markets"""
        markets = set(t.market_id for t in self.trades if not t.is_open)

        for market_id in markets:
            metrics = await self.analyze_market(market_id)
            self.market_metrics[market_id] = metrics

    async def analyze_market(self, market_id: str) -> MarketEfficiencyMetrics:
        """Analyze efficiency for a specific market"""

        # Get market trades
        market_trades = [t for t in self.trades if t.market_id == market_id and not t.is_open]

        if not market_trades:
            return self._create_empty_metrics(market_id)

        # Calculate time to equilibrium
        equilibrium_times = self._calculate_time_to_equilibrium(market_trades)

        if not equilibrium_times:
            return self._create_empty_metrics(market_id)

        avg_time = sum(equilibrium_times) / Decimal(str(len(equilibrium_times)))
        sorted_times = sorted(equilibrium_times)
        median_time = sorted_times[len(sorted_times) // 2]
        min_time = min(equilibrium_times)
        max_time = max(equilibrium_times)

        # Calculate edge metrics
        edge_half_life = self._calculate_edge_half_life(market_trades)
        edge_speed = self._calculate_edge_disappearance_speed(market_trades)

        # Classify efficiency
        if avg_time < Decimal("1.0"):
            efficiency = EfficiencyLevel.HIGHLY_EFFICIENT
        elif avg_time < Decimal("4.0"):
            efficiency = EfficiencyLevel.EFFICIENT
        elif avg_time < Decimal("12.0"):
            efficiency = EfficiencyLevel.MODERATE
        else:
            efficiency = EfficiencyLevel.INEFFICIENT

        # Profitable for copying?
        is_profitable = efficiency in [EfficiencyLevel.MODERATE, EfficiencyLevel.INEFFICIENT]

        # Trade statistics
        total_trades = len(market_trades)
        profitable_trades = [t for t in market_trades if t.pnl_usd > 0]
        success_rate = (Decimal(str(len(profitable_trades))) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

        avg_pnl = sum(t.pnl_usd for t in market_trades) / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

        # Price impact (simplified)
        avg_price_impact = sum(abs(t.exit_price - t.entry_price) / t.entry_price if t.exit_price else Decimal("0") for t in market_trades) / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

        # Edge at entry/exit (simplified estimate)
        avg_edge_entry = Decimal("0.05")  # Placeholder
        avg_edge_exit = Decimal("0.02")   # Placeholder

        return MarketEfficiencyMetrics(
            market_id=market_id,
            calculation_time=datetime.now(),
            avg_time_to_equilibrium=avg_time,
            median_time_to_equilibrium=median_time,
            min_time_to_equilibrium=min_time,
            max_time_to_equilibrium=max_time,
            edge_half_life_hours=edge_half_life,
            edge_disappearance_speed=edge_speed,
            efficiency_level=efficiency,
            is_profitable_for_copying=is_profitable,
            total_whale_trades=total_trades,
            avg_price_impact=avg_price_impact * Decimal("100"),
            avg_edge_at_entry=avg_edge_entry,
            avg_edge_at_exit=avg_edge_exit,
            avg_copy_trader_pnl=avg_pnl,
            success_rate_pct=success_rate
        )

    def _calculate_time_to_equilibrium(self, trades: List[Trade]) -> List[Decimal]:
        """Calculate time to equilibrium for each trade"""

        equilibrium_times = []

        for trade in trades:
            if not trade.exit_time:
                continue

            # Time to equilibrium = time from entry to exit
            # (Simplified: In reality would track price stabilization)
            time_hours = (trade.exit_time - trade.entry_time).total_seconds() / 3600
            equilibrium_times.append(Decimal(str(time_hours)))

        return equilibrium_times

    def _calculate_edge_half_life(self, trades: List[Trade]) -> Decimal:
        """Calculate edge half-life (time for edge to decay to 50%)"""

        if not trades:
            return Decimal("0")

        # Simplified: Use average trade duration as proxy
        total_duration = sum((t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades if t.exit_time)
        avg_duration = total_duration / len(trades) if trades else 0

        # Half-life is roughly half the average duration
        half_life = Decimal(str(avg_duration)) / Decimal("2")

        return half_life

    def _calculate_edge_disappearance_speed(self, trades: List[Trade]) -> Decimal:
        """Calculate edge disappearance speed (% per hour)"""

        if not trades:
            return Decimal("0")

        # Simplified: If edge half-life is 2 hours, speed is ~50% / 2 hours = 25% per hour
        half_life = self._calculate_edge_half_life(trades)

        if half_life > 0:
            speed = Decimal("50") / half_life
        else:
            speed = Decimal("100")  # Instant disappearance

        return speed

    def get_most_efficient_markets(self, n: int = 10) -> List[MarketEfficiencyMetrics]:
        """Get most efficient markets (least profitable for copying)"""
        markets = list(self.market_metrics.values())
        markets.sort(key=lambda m: m.avg_time_to_equilibrium)
        return markets[:n]

    def get_least_efficient_markets(self, n: int = 10) -> List[MarketEfficiencyMetrics]:
        """Get least efficient markets (most profitable for copying)"""
        markets = list(self.market_metrics.values())
        markets.sort(key=lambda m: m.avg_time_to_equilibrium, reverse=True)
        return markets[:n]

    def get_profitable_markets(self) -> List[MarketEfficiencyMetrics]:
        """Get markets profitable for copy trading"""
        return [m for m in self.market_metrics.values() if m.is_profitable_for_copying]

    def _create_empty_metrics(self, market_id: str) -> MarketEfficiencyMetrics:
        """Create empty metrics"""
        return MarketEfficiencyMetrics(
            market_id=market_id,
            calculation_time=datetime.now(),
            avg_time_to_equilibrium=Decimal("0"),
            median_time_to_equilibrium=Decimal("0"),
            min_time_to_equilibrium=Decimal("0"),
            max_time_to_equilibrium=Decimal("0"),
            edge_half_life_hours=Decimal("0"),
            edge_disappearance_speed=Decimal("0"),
            efficiency_level=EfficiencyLevel.MODERATE,
            is_profitable_for_copying=False,
            total_whale_trades=0,
            avg_price_impact=Decimal("0"),
            avg_edge_at_entry=Decimal("0"),
            avg_edge_at_exit=Decimal("0"),
            avg_copy_trader_pnl=Decimal("0"),
            success_rate_pct=Decimal("0")
        )

    def print_efficiency_summary(self):
        """Print efficiency summary"""
        print(f"\n{'='*100}")
        print("MARKET EFFICIENCY ANALYSIS")
        print(f"{'='*100}\n")

        print("MOST INEFFICIENT MARKETS (Best for copy trading):")
        print(f"{'Market':<25}{'Time to Eq':<15}{'Half-Life':<12}{'Speed':<12}{'Success%':<12}{'Avg P&L':<12}")
        print("-" * 100)

        for metrics in self.get_least_efficient_markets(10):
            print(
                f"{metrics.market_id[:23]:<25}"
                f"{metrics.avg_time_to_equilibrium:>11.1f}h   "
                f"{metrics.edge_half_life_hours:>8.1f}h   "
                f"{metrics.edge_disappearance_speed:>8.1f}%/h "
                f"{metrics.success_rate_pct:>9.1f}%  "
                f"${metrics.avg_copy_trader_pnl:>9,.2f}"
            )

        print("\n\nMOST EFFICIENT MARKETS (Avoid for copy trading):")
        print(f"{'Market':<25}{'Time to Eq':<15}{'Half-Life':<12}{'Speed':<12}{'Success%':<12}{'Avg P&L':<12}")
        print("-" * 100)

        for metrics in self.get_most_efficient_markets(10):
            print(
                f"{metrics.market_id[:23]:<25}"
                f"{metrics.avg_time_to_equilibrium:>11.1f}h   "
                f"{metrics.edge_half_life_hours:>8.1f}h   "
                f"{metrics.edge_disappearance_speed:>8.1f}%/h "
                f"{metrics.success_rate_pct:>9.1f}%  "
                f"${metrics.avg_copy_trader_pnl:>9,.2f}"
            )

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = EfficiencyConfig()
        analyzer = MarketEfficiencyAnalyzer(config)

        # Add sample trades
        print("Adding sample trades...")

        # Inefficient market (slow equilibrium)
        for i in range(30):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address="0xwhale1",
                market_id="market_inefficient",
                entry_time=datetime.now() - timedelta(hours=24-i, minutes=i*10),
                exit_time=datetime.now() - timedelta(hours=24-i-8, minutes=i*10),  # 8 hour avg
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.55"),
                pnl_usd=Decimal("100"),
                is_open=False
            )
            analyzer.add_trade(trade)

        # Efficient market (fast equilibrium)
        for i in range(30):
            trade = Trade(
                trade_id=f"trade_eff_{i}",
                whale_address="0xwhale2",
                market_id="market_efficient",
                entry_time=datetime.now() - timedelta(hours=24-i, minutes=i*10),
                exit_time=datetime.now() - timedelta(hours=24-i-0.5, minutes=i*10),  # 30 min avg
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.51"),
                pnl_usd=Decimal("20"),
                is_open=False
            )
            analyzer.add_trade(trade)

        # Analyze
        await analyzer.analyze_all_markets()

        # Print results
        analyzer.print_efficiency_summary()

        print("\nMarket efficiency analyzer demo complete!")

    asyncio.run(main())
