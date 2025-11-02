"""
Week 9: Performance Analytics - Realtime Analytics Dashboard

This module provides live monitoring and visualization:
- Live P&L chart (continuously updating)
- Win rate trends by hour/day/week
- Top performing whales and markets (live rankings)
- Recent trades table (last 50 trades)
- Real-time alerts and notifications

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Deque, Dict, List, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Configuration for realtime dashboard"""
    update_interval_seconds: int = 5
    max_recent_trades: int = 50
    chart_history_hours: int = 24
    top_performers_count: int = 10


@dataclass
class Trade:
    """Trade record"""
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
class LiveDataPoint:
    """Live chart data point"""
    timestamp: datetime
    cumulative_pnl: Decimal
    equity: Decimal
    trade_count: int


@dataclass
class DashboardSnapshot:
    """Complete dashboard state"""
    timestamp: datetime
    current_pnl: Decimal
    current_equity: Decimal
    total_trades: int
    win_rate_pct: Decimal
    hourly_win_rate: Dict[int, Decimal]
    daily_win_rate: Dict[str, Decimal]
    top_whales: List[Dict]
    top_markets: List[Dict]
    recent_trades: List[Trade]
    chart_data: List[LiveDataPoint]
    alerts: List[str]


class RealtimeAnalyticsDashboard:
    """
    Real-time analytics dashboard with live updates.

    Features:
    - Live P&L chart (5-second updates)
    - Win rate trends (hour/day/week)
    - Top performers (whales, markets)
    - Recent trades feed
    - Real-time alerts
    """

    def __init__(self, config: DashboardConfig):
        self.config = config
        self.trades: List[Trade] = []
        self.recent_trades: Deque[Trade] = deque(maxlen=config.max_recent_trades)
        self.chart_data: Deque[LiveDataPoint] = deque(maxlen=config.chart_history_hours * 720)  # 5-sec intervals

        self.starting_capital: Decimal = Decimal("100000")
        self.current_capital: Decimal = Decimal("100000")
        self.cumulative_pnl: Decimal = Decimal("0")

        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("RealtimeAnalyticsDashboard initialized")

    async def start(self):
        """Start dashboard"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("Dashboard started")

    async def stop(self):
        """Stop dashboard"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("Dashboard stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                snapshot = await self.get_snapshot()

                # Add to chart
                data_point = LiveDataPoint(
                    timestamp=datetime.now(),
                    cumulative_pnl=self.cumulative_pnl,
                    equity=self.current_capital,
                    trade_count=len(self.trades)
                )
                self.chart_data.append(data_point)

                logger.debug(f"Dashboard updated - P&L: ${self.cumulative_pnl:,.2f}, Trades: {len(self.trades)}")

                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"Dashboard update error: {e}", exc_info=True)
                await asyncio.sleep(5)

    def add_trade(self, trade: Trade):
        """Add trade"""
        self.trades.append(trade)

        if not trade.is_open:
            self.recent_trades.append(trade)
            self.current_capital += trade.pnl_usd
            self.cumulative_pnl += trade.pnl_usd

    async def get_snapshot(self) -> DashboardSnapshot:
        """Get current dashboard snapshot"""

        # Calculate metrics
        closed_trades = [t for t in self.trades if not t.is_open]
        total_trades = len(closed_trades)
        winning = len([t for t in closed_trades if t.pnl_usd > 0])
        win_rate = (Decimal(str(winning)) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

        # Win rate by hour
        hourly_win_rate = self._calculate_hourly_win_rate(closed_trades)

        # Win rate by day
        daily_win_rate = self._calculate_daily_win_rate(closed_trades)

        # Top performers
        top_whales = self._get_top_performers(closed_trades, "whale")
        top_markets = self._get_top_performers(closed_trades, "market")

        # Alerts
        alerts = self._generate_alerts(closed_trades)

        return DashboardSnapshot(
            timestamp=datetime.now(),
            current_pnl=self.cumulative_pnl,
            current_equity=self.current_capital,
            total_trades=total_trades,
            win_rate_pct=win_rate,
            hourly_win_rate=hourly_win_rate,
            daily_win_rate=daily_win_rate,
            top_whales=top_whales,
            top_markets=top_markets,
            recent_trades=list(self.recent_trades),
            chart_data=list(self.chart_data),
            alerts=alerts
        )

    def _calculate_hourly_win_rate(self, trades: List[Trade]) -> Dict[int, Decimal]:
        """Calculate win rate by hour"""
        hourly_data: Dict[int, Dict] = {}

        for trade in trades:
            if trade.exit_time:
                hour = trade.exit_time.hour
                if hour not in hourly_data:
                    hourly_data[hour] = {"total": 0, "wins": 0}

                hourly_data[hour]["total"] += 1
                if trade.pnl_usd > 0:
                    hourly_data[hour]["wins"] += 1

        hourly_win_rate = {}
        for hour, data in hourly_data.items():
            win_rate = (Decimal(str(data["wins"])) / Decimal(str(data["total"])) * Decimal("100")) if data["total"] > 0 else Decimal("0")
            hourly_win_rate[hour] = win_rate

        return hourly_win_rate

    def _calculate_daily_win_rate(self, trades: List[Trade]) -> Dict[str, Decimal]:
        """Calculate win rate by day"""
        daily_data: Dict[str, Dict] = {}

        for trade in trades:
            if trade.exit_time:
                day = trade.exit_time.strftime("%Y-%m-%d")
                if day not in daily_data:
                    daily_data[day] = {"total": 0, "wins": 0}

                daily_data[day]["total"] += 1
                if trade.pnl_usd > 0:
                    daily_data[day]["wins"] += 1

        daily_win_rate = {}
        for day, data in daily_data.items():
            win_rate = (Decimal(str(data["wins"])) / Decimal(str(data["total"])) * Decimal("100")) if data["total"] > 0 else Decimal("0")
            daily_win_rate[day] = win_rate

        return daily_win_rate

    def _get_top_performers(self, trades: List[Trade], dimension: str) -> List[Dict]:
        """Get top performers"""
        performance: Dict[str, Decimal] = {}

        for trade in trades:
            if dimension == "whale":
                key = trade.whale_address
            elif dimension == "market":
                key = trade.market_id
            else:
                continue

            if key not in performance:
                performance[key] = Decimal("0")

            performance[key] += trade.pnl_usd

        # Sort and get top N
        sorted_performers = sorted(performance.items(), key=lambda x: x[1], reverse=True)

        top_performers = []
        for i, (key, pnl) in enumerate(sorted_performers[:self.config.top_performers_count], 1):
            top_performers.append({
                "rank": i,
                "id": key,
                "pnl_usd": str(pnl)
            })

        return top_performers

    def _generate_alerts(self, trades: List[Trade]) -> List[str]:
        """Generate real-time alerts"""
        alerts = []

        # Check recent large loss
        if self.recent_trades:
            last_trade = list(self.recent_trades)[-1]
            if last_trade.pnl_usd < Decimal("-500"):
                alerts.append(f"Large loss: ${last_trade.pnl_usd:,.2f} on trade {last_trade.trade_id}")

        # Check current drawdown
        peak = self.starting_capital
        for trade in trades:
            equity = self.starting_capital + sum(t.pnl_usd for t in trades if t.exit_time and t.exit_time <= (trade.exit_time or datetime.max))
            if equity > peak:
                peak = equity

        current_dd = ((peak - self.current_capital) / peak * Decimal("100")) if peak > 0 else Decimal("0")
        if current_dd > Decimal("10.0"):
            alerts.append(f"Drawdown alert: {current_dd:.1f}%")

        return alerts

    def print_dashboard(self):
        """Print dashboard to console"""
        snapshot = asyncio.run(self.get_snapshot())

        print(f"\n{'='*100}")
        print(f"REALTIME ANALYTICS DASHBOARD - {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*100}\n")

        print(f"PERFORMANCE SUMMARY:")
        print(f"  Current P&L:    ${snapshot.current_pnl:>12,.2f}")
        print(f"  Current Equity: ${snapshot.current_equity:>12,.2f}")
        print(f"  Total Trades:   {snapshot.total_trades:>12,}")
        print(f"  Win Rate:       {snapshot.win_rate_pct:>12.1f}%\n")

        if snapshot.top_whales:
            print(f"TOP PERFORMING WHALES:")
            for whale in snapshot.top_whales[:5]:
                print(f"  #{whale['rank']} {whale['id'][:20]:<20} ${whale['pnl_usd']:>10}")

        print(f"\nRECENT TRADES:")
        for trade in list(snapshot.recent_trades)[-5:]:
            status = "WIN" if trade.pnl_usd > 0 else "LOSS"
            print(f"  {trade.trade_id[:15]:<15} {status:<6} ${trade.pnl_usd:>8,.2f}")

        if snapshot.alerts:
            print(f"\nALERTS:")
            for alert in snapshot.alerts:
                print(f"  ! {alert}")

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = DashboardConfig()
        dashboard = RealtimeAnalyticsDashboard(config)

        # Add sample trades
        for i in range(20):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=f"0xwhale{i % 3}",
                market_id=f"market_{i % 5}",
                market_topic="Politics",
                side="BUY",
                entry_price=Decimal("0.55"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.52"),
                position_size_usd=Decimal("1000"),
                entry_time=datetime.now() - timedelta(hours=i),
                exit_time=datetime.now() - timedelta(hours=i-1),
                pnl_usd=Decimal("50") if i % 2 == 0 else Decimal("-30"),
                pnl_pct=Decimal("5.0") if i % 2 == 0 else Decimal("-3.0"),
                is_open=False
            )
            dashboard.add_trade(trade)

        await dashboard.start()

        # Print dashboard
        await asyncio.sleep(2)
        dashboard.print_dashboard()

        await dashboard.stop()
        print("Dashboard demo complete!")

    asyncio.run(main())
