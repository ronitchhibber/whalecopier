"""
Week 10: Edge Detection & Decay - Edge Detection System

This module calculates and tracks trading edge per whale/market:
- Edge formula: E = (win_rate × avg_win) - (loss_rate × avg_loss)
- Track edge over rolling 30-day windows
- Alert when edge < 0.05 (minimum profitable threshold)
- Dashboard showing edge by whale and market
- Automatic disabling of whales with negative edge

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


class EdgeStatus(Enum):
    """Edge status levels"""
    EXCELLENT = "excellent"  # Edge > 0.15
    GOOD = "good"           # Edge > 0.10
    MODERATE = "moderate"   # Edge > 0.05
    MINIMAL = "minimal"     # Edge > 0.00
    NEGATIVE = "negative"   # Edge <= 0.00


@dataclass
class EdgeConfig:
    """Configuration for edge detection"""

    # Edge thresholds
    excellent_edge_threshold: Decimal = Decimal("0.15")
    good_edge_threshold: Decimal = Decimal("0.10")
    min_edge_threshold: Decimal = Decimal("0.05")  # Minimum for profitability

    # Analysis parameters
    rolling_window_days: int = 30
    min_trades_for_significance: int = 10

    # Update frequency
    update_interval_seconds: int = 300  # 5 minutes

    # Action thresholds
    auto_disable_negative_edge: bool = True
    alert_edge_below_threshold: bool = True


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
class EdgeMetrics:
    """Edge metrics for a whale or market"""

    # Identification
    entity_id: str  # Whale address or market ID
    entity_type: str  # "whale" or "market"
    calculation_time: datetime

    # Edge calculation
    edge: Decimal  # E = (win_rate × avg_win) - (loss_rate × avg_loss)
    edge_status: EdgeStatus

    # Components
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    loss_rate: Decimal
    avg_win_usd: Decimal
    avg_loss_usd: Decimal

    # Performance
    total_pnl_usd: Decimal
    expected_value_per_trade: Decimal  # Edge in USD terms

    # Tracking
    edge_30d: Decimal  # 30-day rolling edge
    edge_7d: Decimal   # 7-day rolling edge
    edge_trend: str    # "improving", "stable", "declining"

    # Significance
    is_significant: bool
    confidence_score: Decimal

    # Actions
    should_alert: bool
    should_disable: bool
    alert_reason: Optional[str] = None


class EdgeDetectionSystem:
    """
    Edge detection system.

    Calculates trading edge using the formula:
    E = (win_rate × avg_win) - (loss_rate × avg_loss)

    Where:
    - win_rate = winning_trades / total_trades
    - loss_rate = losing_trades / total_trades
    - avg_win = average profit from winning trades
    - avg_loss = average loss from losing trades

    Edge interpretation:
    - E > 0.15: Excellent edge
    - E > 0.10: Good edge
    - E > 0.05: Minimum profitable edge
    - E <= 0: No edge (unprofitable)
    """

    def __init__(self, config: EdgeConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.whale_edges: Dict[str, EdgeMetrics] = {}
        self.market_edges: Dict[str, EdgeMetrics] = {}

        # Disabled entities
        self.disabled_whales: Dict[str, datetime] = {}
        self.disabled_markets: Dict[str, datetime] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("EdgeDetectionSystem initialized")

    async def start(self):
        """Start edge detection"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("EdgeDetectionSystem started")

    async def stop(self):
        """Stop edge detection"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("EdgeDetectionSystem stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                # Calculate edge for all whales
                await self.calculate_all_edges()

                # Check for alerts
                await self._process_alerts()

                # Auto-disable if configured
                if self.config.auto_disable_negative_edge:
                    await self._auto_disable_negative_edge()

                logger.info(f"Edge update complete - {len(self.whale_edges)} whales, {len(self.market_edges)} markets")

                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"Edge detection error: {e}", exc_info=True)
                await asyncio.sleep(30)

    def add_trade(self, trade: Trade):
        """Add trade"""
        self.trades.append(trade)

    async def calculate_all_edges(self):
        """Calculate edge for all whales and markets"""

        # Calculate whale edges
        whales = set(t.whale_address for t in self.trades)
        for whale in whales:
            self.whale_edges[whale] = await self.calculate_edge(whale, "whale")

        # Calculate market edges
        markets = set(t.market_id for t in self.trades)
        for market in markets:
            self.market_edges[market] = await self.calculate_edge(market, "market")

    async def calculate_edge(self, entity_id: str, entity_type: str) -> EdgeMetrics:
        """
        Calculate edge for a whale or market.

        Args:
            entity_id: Whale address or market ID
            entity_type: "whale" or "market"

        Returns:
            EdgeMetrics with calculated edge
        """

        # Filter trades
        if entity_type == "whale":
            trades = [t for t in self.trades if t.whale_address == entity_id and not t.is_open]
        else:
            trades = [t for t in self.trades if t.market_id == entity_id and not t.is_open]

        if not trades:
            return self._create_empty_edge(entity_id, entity_type)

        # Calculate basic metrics
        total_trades = len(trades)
        winning = [t for t in trades if t.pnl_usd > 0]
        losing = [t for t in trades if t.pnl_usd < 0]

        winning_count = len(winning)
        losing_count = len(losing)

        # Win/loss rates
        win_rate = Decimal(str(winning_count)) / Decimal(str(total_trades))
        loss_rate = Decimal(str(losing_count)) / Decimal(str(total_trades))

        # Average win/loss
        avg_win = sum(t.pnl_usd for t in winning) / Decimal(str(winning_count)) if winning_count > 0 else Decimal("0")
        avg_loss = abs(sum(t.pnl_usd for t in losing) / Decimal(str(losing_count))) if losing_count > 0 else Decimal("0")

        # Calculate edge: E = (win_rate × avg_win) - (loss_rate × avg_loss)
        edge = (win_rate * avg_win) - (loss_rate * avg_loss)

        # Determine status
        if edge >= self.config.excellent_edge_threshold:
            status = EdgeStatus.EXCELLENT
        elif edge >= self.config.good_edge_threshold:
            status = EdgeStatus.GOOD
        elif edge >= self.config.min_edge_threshold:
            status = EdgeStatus.MODERATE
        elif edge > Decimal("0"):
            status = EdgeStatus.MINIMAL
        else:
            status = EdgeStatus.NEGATIVE

        # Calculate rolling edges
        edge_30d = self._calculate_rolling_edge(entity_id, entity_type, 30)
        edge_7d = self._calculate_rolling_edge(entity_id, entity_type, 7)

        # Determine trend
        if edge_7d > edge_30d * Decimal("1.10"):
            trend = "improving"
        elif edge_7d < edge_30d * Decimal("0.90"):
            trend = "declining"
        else:
            trend = "stable"

        # Total P&L
        total_pnl = sum(t.pnl_usd for t in trades)

        # Expected value per trade (edge in USD)
        ev_per_trade = total_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")

        # Significance
        is_significant = total_trades >= self.config.min_trades_for_significance
        confidence = min(Decimal("100"), Decimal(str(total_trades)) / Decimal(str(self.config.min_trades_for_significance)) * Decimal("100"))

        # Alerts
        should_alert = (
            self.config.alert_edge_below_threshold and
            edge < self.config.min_edge_threshold and
            is_significant
        )

        should_disable = (
            self.config.auto_disable_negative_edge and
            edge <= Decimal("0") and
            is_significant
        )

        alert_reason = None
        if should_alert:
            alert_reason = f"Edge {edge:.3f} below minimum threshold {self.config.min_edge_threshold}"
        elif should_disable:
            alert_reason = f"Negative edge {edge:.3f} - auto-disabling"

        return EdgeMetrics(
            entity_id=entity_id,
            entity_type=entity_type,
            calculation_time=datetime.now(),
            edge=edge,
            edge_status=status,
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate=win_rate * Decimal("100"),
            loss_rate=loss_rate * Decimal("100"),
            avg_win_usd=avg_win,
            avg_loss_usd=avg_loss,
            total_pnl_usd=total_pnl,
            expected_value_per_trade=ev_per_trade,
            edge_30d=edge_30d,
            edge_7d=edge_7d,
            edge_trend=trend,
            is_significant=is_significant,
            confidence_score=confidence,
            should_alert=should_alert,
            should_disable=should_disable,
            alert_reason=alert_reason
        )

    def _calculate_rolling_edge(self, entity_id: str, entity_type: str, days: int) -> Decimal:
        """Calculate rolling edge for N days"""
        cutoff = datetime.now() - timedelta(days=days)

        if entity_type == "whale":
            trades = [t for t in self.trades if t.whale_address == entity_id and not t.is_open and t.exit_time and t.exit_time >= cutoff]
        else:
            trades = [t for t in self.trades if t.market_id == entity_id and not t.is_open and t.exit_time and t.exit_time >= cutoff]

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

    async def _process_alerts(self):
        """Process edge alerts"""

        for whale_id, metrics in self.whale_edges.items():
            if metrics.should_alert and metrics.alert_reason:
                logger.warning(f"EDGE ALERT - Whale {whale_id[:10]}...: {metrics.alert_reason}")

    async def _auto_disable_negative_edge(self):
        """Auto-disable whales/markets with negative edge"""

        for whale_id, metrics in self.whale_edges.items():
            if metrics.should_disable and whale_id not in self.disabled_whales:
                self.disabled_whales[whale_id] = datetime.now()
                logger.warning(f"AUTO-DISABLED whale {whale_id[:10]}... due to negative edge {metrics.edge:.3f}")

    def is_whale_disabled(self, whale_address: str) -> bool:
        """Check if whale is disabled"""
        return whale_address in self.disabled_whales

    def get_whale_edge(self, whale_address: str) -> Optional[EdgeMetrics]:
        """Get edge metrics for a whale"""
        return self.whale_edges.get(whale_address)

    def get_top_edge_whales(self, n: int = 10) -> List[EdgeMetrics]:
        """Get top N whales by edge"""
        whales = list(self.whale_edges.values())
        whales.sort(key=lambda m: m.edge, reverse=True)
        return whales[:n]

    def get_negative_edge_whales(self) -> List[EdgeMetrics]:
        """Get all whales with negative edge"""
        return [m for m in self.whale_edges.values() if m.edge <= Decimal("0") and m.is_significant]

    def _create_empty_edge(self, entity_id: str, entity_type: str) -> EdgeMetrics:
        """Create empty edge metrics"""
        return EdgeMetrics(
            entity_id=entity_id,
            entity_type=entity_type,
            calculation_time=datetime.now(),
            edge=Decimal("0"),
            edge_status=EdgeStatus.MINIMAL,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            loss_rate=Decimal("0"),
            avg_win_usd=Decimal("0"),
            avg_loss_usd=Decimal("0"),
            total_pnl_usd=Decimal("0"),
            expected_value_per_trade=Decimal("0"),
            edge_30d=Decimal("0"),
            edge_7d=Decimal("0"),
            edge_trend="stable",
            is_significant=False,
            confidence_score=Decimal("0"),
            should_alert=False,
            should_disable=False
        )

    def print_edge_summary(self):
        """Print edge summary"""
        print(f"\n{'='*100}")
        print("EDGE DETECTION SUMMARY")
        print(f"{'='*100}\n")

        print("TOP 10 WHALES BY EDGE:")
        print(f"{'Rank':<6}{'Whale':<25}{'Edge':<10}{'Status':<12}{'Win Rate':<10}{'Avg Win':<12}{'Avg Loss':<12}{'Trend':<12}")
        print("-" * 100)

        for i, metrics in enumerate(self.get_top_edge_whales(10), 1):
            print(
                f"{i:<6}"
                f"{metrics.entity_id[:23]:<25}"
                f"{metrics.edge:>8.3f}  "
                f"{metrics.edge_status.value:<12}"
                f"{metrics.win_rate:>7.1f}%  "
                f"${metrics.avg_win_usd:>9,.2f}  "
                f"${metrics.avg_loss_usd:>9,.2f}  "
                f"{metrics.edge_trend:<12}"
            )

        # Negative edge warnings
        negative = self.get_negative_edge_whales()
        if negative:
            print(f"\n\nWARNING - {len(negative)} WHALES WITH NEGATIVE EDGE:")
            for metrics in negative:
                print(f"  {metrics.entity_id[:30]:<30} Edge: {metrics.edge:.3f} (Disabled: {self.is_whale_disabled(metrics.entity_id)})")

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = EdgeConfig()
        system = EdgeDetectionSystem(config)

        # Add sample trades
        print("Adding sample trades...")

        for i in range(100):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=f"0xwhale{i % 5}",
                market_id=f"market_{i % 10}",
                entry_time=datetime.now() - timedelta(days=30-i//10),
                exit_time=datetime.now() - timedelta(days=30-i//10-1),
                pnl_usd=Decimal("50") if i % 3 != 0 else Decimal("-30"),  # 67% win rate
                is_open=False
            )
            system.add_trade(trade)

        # Calculate edges
        print("\nCalculating edges...")
        await system.calculate_all_edges()

        # Print summary
        system.print_edge_summary()

        # Test disabled whales
        negative_whales = system.get_negative_edge_whales()
        print(f"\nNegative edge whales: {len(negative_whales)}")

        print("\nEdge detection demo complete!")

    asyncio.run(main())
