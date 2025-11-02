"""
Week 9: Performance Analytics - Custom Reporting Engine

This module provides automated report generation:
- Daily performance emails
- Weekly strategy reviews
- Monthly investor reports
- CSV/Excel export functionality
- Customizable report templates
- Email delivery integration

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import csv
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Report types"""
    DAILY_PERFORMANCE = "daily"
    WEEKLY_STRATEGY = "weekly"
    MONTHLY_INVESTOR = "monthly"
    QUARTERLY_REVIEW = "quarterly"
    CUSTOM = "custom"


class ReportFormat(Enum):
    """Report output formats"""
    CSV = "csv"
    JSON = "json"
    HTML = "html"
    TEXT = "text"


@dataclass
class ReportConfig:
    """Configuration for reporting engine"""

    # Report scheduling
    generate_daily_reports: bool = True
    generate_weekly_reports: bool = True
    generate_monthly_reports: bool = True

    # Report times (24-hour format)
    daily_report_hour: int = 8  # 8 AM
    weekly_report_day: int = 1  # Monday
    monthly_report_day: int = 1  # 1st of month

    # Output settings
    reports_directory: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/reports/"
    default_format: ReportFormat = ReportFormat.CSV

    # Email settings (if enabled)
    enable_email_delivery: bool = False
    email_recipients: List[str] = field(default_factory=list)

    # Content settings
    include_trade_details: bool = True
    include_whale_breakdown: bool = True
    include_market_breakdown: bool = True
    include_benchmarks: bool = True

    # Thresholds for alerts
    alert_on_large_loss: bool = True
    large_loss_threshold_usd: Decimal = Decimal("1000")


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
class PerformanceSnapshot:
    """Performance snapshot for reporting"""
    date: datetime
    total_pnl_usd: Decimal
    daily_pnl_usd: Decimal
    total_return_pct: Decimal
    daily_return_pct: Decimal
    total_trades: int
    win_rate_pct: Decimal
    sharpe_ratio: Decimal
    max_drawdown_pct: Decimal
    current_capital: Decimal


@dataclass
class ReportData:
    """Complete report data"""

    report_type: ReportType
    report_period_start: datetime
    report_period_end: datetime
    generation_time: datetime

    # Performance summary
    starting_capital: Decimal
    ending_capital: Decimal
    total_pnl_usd: Decimal
    total_return_pct: Decimal

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal

    # Performance metrics
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    profit_factor: Decimal
    max_drawdown_pct: Decimal

    # Best and worst
    best_trade_usd: Decimal
    worst_trade_usd: Decimal
    best_day_pct: Decimal
    worst_day_pct: Decimal

    # Breakdowns
    trades_by_whale: Dict[str, Dict] = field(default_factory=dict)
    trades_by_market: Dict[str, Dict] = field(default_factory=dict)
    trades_by_topic: Dict[str, Dict] = field(default_factory=dict)

    # Daily snapshots
    daily_snapshots: List[PerformanceSnapshot] = field(default_factory=list)

    # Alerts
    alerts: List[str] = field(default_factory=list)


class ReportingEngine:
    """
    Automated report generation engine.

    Generates:
    - Daily performance reports (P&L, trades, alerts)
    - Weekly strategy reviews (performance analysis, top whales, adjustments)
    - Monthly investor reports (comprehensive performance summary)
    - Custom reports on demand

    Exports to CSV, JSON, HTML, or plain text.
    """

    def __init__(self, config: ReportConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.starting_capital: Decimal = Decimal("100000")
        self.current_capital: Decimal = Decimal("100000")

        # Report history
        self.last_daily_report: Optional[datetime] = None
        self.last_weekly_report: Optional[datetime] = None
        self.last_monthly_report: Optional[datetime] = None

        # Create reports directory
        Path(self.config.reports_directory).mkdir(parents=True, exist_ok=True)

        # Background task
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("ReportingEngine initialized")

    async def start(self):
        """Start the reporting engine"""
        if self.is_running:
            logger.warning("ReportingEngine already running")
            return

        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())

        logger.info("ReportingEngine started")

    async def stop(self):
        """Stop the reporting engine"""
        self.is_running = False

        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("ReportingEngine stopped")

    async def _scheduler_loop(self):
        """Background scheduler for automatic reports"""
        while self.is_running:
            try:
                now = datetime.now()

                # Check for daily report
                if self.config.generate_daily_reports:
                    if self._should_generate_daily(now):
                        logger.info("Generating daily report...")
                        await self.generate_report(ReportType.DAILY_PERFORMANCE)
                        self.last_daily_report = now

                # Check for weekly report
                if self.config.generate_weekly_reports:
                    if self._should_generate_weekly(now):
                        logger.info("Generating weekly report...")
                        await self.generate_report(ReportType.WEEKLY_STRATEGY)
                        self.last_weekly_report = now

                # Check for monthly report
                if self.config.generate_monthly_reports:
                    if self._should_generate_monthly(now):
                        logger.info("Generating monthly report...")
                        await self.generate_report(ReportType.MONTHLY_INVESTOR)
                        self.last_monthly_report = now

                # Check every hour
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    def _should_generate_daily(self, now: datetime) -> bool:
        """Check if should generate daily report"""
        if not self.last_daily_report:
            return now.hour == self.config.daily_report_hour

        return (
            now.hour == self.config.daily_report_hour and
            now.date() > self.last_daily_report.date()
        )

    def _should_generate_weekly(self, now: datetime) -> bool:
        """Check if should generate weekly report"""
        if not self.last_weekly_report:
            return now.weekday() == self.config.weekly_report_day

        return (
            now.weekday() == self.config.weekly_report_day and
            (now - self.last_weekly_report).days >= 7
        )

    def _should_generate_monthly(self, now: datetime) -> bool:
        """Check if should generate monthly report"""
        if not self.last_monthly_report:
            return now.day == self.config.monthly_report_day

        return (
            now.day == self.config.monthly_report_day and
            now.month != self.last_monthly_report.month
        )

    def add_trade(self, trade: Trade):
        """Add trade to history"""
        self.trades.append(trade)

        if not trade.is_open:
            self.current_capital += trade.pnl_usd

        logger.debug(f"Added trade {trade.trade_id} to reporting history")

    async def generate_report(self, report_type: ReportType,
                             custom_period_days: Optional[int] = None) -> ReportData:
        """
        Generate a report.

        Args:
            report_type: Type of report to generate
            custom_period_days: Custom lookback period (for custom reports)

        Returns:
            ReportData object
        """

        # Determine report period
        end_time = datetime.now()

        if report_type == ReportType.DAILY_PERFORMANCE:
            start_time = end_time - timedelta(days=1)
        elif report_type == ReportType.WEEKLY_STRATEGY:
            start_time = end_time - timedelta(days=7)
        elif report_type == ReportType.MONTHLY_INVESTOR:
            start_time = end_time - timedelta(days=30)
        elif report_type == ReportType.QUARTERLY_REVIEW:
            start_time = end_time - timedelta(days=90)
        elif report_type == ReportType.CUSTOM and custom_period_days:
            start_time = end_time - timedelta(days=custom_period_days)
        else:
            start_time = end_time - timedelta(days=1)

        # Collect report data
        report_data = await self._collect_report_data(report_type, start_time, end_time)

        # Export report
        await self._export_report(report_data)

        # Send email if enabled
        if self.config.enable_email_delivery:
            await self._send_email_report(report_data)

        logger.info(f"Generated {report_type.value} report for period {start_time.date()} to {end_time.date()}")

        return report_data

    async def _collect_report_data(self, report_type: ReportType,
                                   start_time: datetime, end_time: datetime) -> ReportData:
        """Collect all data for the report"""

        # Filter trades in period
        period_trades = [
            t for t in self.trades
            if not t.is_open and t.exit_time and start_time <= t.exit_time <= end_time
        ]

        # Calculate performance metrics
        total_pnl = sum(t.pnl_usd for t in period_trades)
        total_return_pct = (total_pnl / self.starting_capital) * Decimal("100") if period_trades else Decimal("0")

        # Trade statistics
        total_trades = len(period_trades)
        winning = [t for t in period_trades if t.pnl_usd > 0]
        losing = [t for t in period_trades if t.pnl_usd < 0]

        winning_count = len(winning)
        losing_count = len(losing)
        win_rate = (Decimal(str(winning_count)) / Decimal(str(total_trades)) * Decimal("100")) if total_trades > 0 else Decimal("0")

        # Performance metrics
        sharpe, sortino = self._calculate_risk_metrics(period_trades)
        profit_factor = self._calculate_profit_factor(winning, losing)
        max_dd = self._calculate_max_drawdown(period_trades)

        # Best/worst
        best_trade = max((t.pnl_usd for t in period_trades), default=Decimal("0"))
        worst_trade = min((t.pnl_usd for t in period_trades), default=Decimal("0"))

        # Daily performance
        daily_snapshots = self._calculate_daily_snapshots(period_trades, start_time, end_time)

        best_day = max((s.daily_return_pct for s in daily_snapshots), default=Decimal("0"))
        worst_day = min((s.daily_return_pct for s in daily_snapshots), default=Decimal("0"))

        # Breakdowns
        by_whale = self._breakdown_by_dimension(period_trades, "whale")
        by_market = self._breakdown_by_dimension(period_trades, "market")
        by_topic = self._breakdown_by_dimension(period_trades, "topic")

        # Alerts
        alerts = self._generate_alerts(period_trades, total_pnl, max_dd)

        return ReportData(
            report_type=report_type,
            report_period_start=start_time,
            report_period_end=end_time,
            generation_time=datetime.now(),
            starting_capital=self.starting_capital,
            ending_capital=self.current_capital,
            total_pnl_usd=total_pnl,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate_pct=win_rate,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            profit_factor=profit_factor,
            max_drawdown_pct=max_dd,
            best_trade_usd=best_trade,
            worst_trade_usd=worst_trade,
            best_day_pct=best_day,
            worst_day_pct=worst_day,
            trades_by_whale=by_whale,
            trades_by_market=by_market,
            trades_by_topic=by_topic,
            daily_snapshots=daily_snapshots,
            alerts=alerts
        )

    def _calculate_risk_metrics(self, trades: List[Trade]) -> Tuple[Decimal, Decimal]:
        """Calculate Sharpe and Sortino ratios"""
        if not trades:
            return Decimal("0"), Decimal("0")

        returns = [t.pnl_pct for t in trades]
        mean_return = sum(returns) / Decimal(str(len(returns)))

        # Sharpe
        variance = sum((r - mean_return) ** 2 for r in returns) / Decimal(str(len(returns)))
        std_dev = variance ** Decimal("0.5")
        sharpe = mean_return / std_dev if std_dev > 0 else Decimal("0")

        # Sortino (downside deviation)
        negative_returns = [r for r in returns if r < 0]
        if negative_returns:
            mean_neg = sum(negative_returns) / Decimal(str(len(negative_returns)))
            downside_var = sum((r - mean_neg) ** 2 for r in negative_returns) / Decimal(str(len(negative_returns)))
            downside_dev = downside_var ** Decimal("0.5")
            sortino = mean_return / downside_dev if downside_dev > 0 else Decimal("0")
        else:
            sortino = Decimal("999")

        return sharpe, sortino

    def _calculate_profit_factor(self, winning: List[Trade], losing: List[Trade]) -> Decimal:
        """Calculate profit factor"""
        gross_profit = sum(t.pnl_usd for t in winning)
        gross_loss = abs(sum(t.pnl_usd for t in losing))

        return gross_profit / gross_loss if gross_loss > 0 else Decimal("999")

    def _calculate_max_drawdown(self, trades: List[Trade]) -> Decimal:
        """Calculate max drawdown"""
        equity = self.starting_capital
        peak = equity
        max_dd = Decimal("0")

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            equity += trade.pnl_usd

            if equity > peak:
                peak = equity
            else:
                dd = ((peak - equity) / peak) * Decimal("100")
                if dd > max_dd:
                    max_dd = dd

        return max_dd

    def _calculate_daily_snapshots(self, trades: List[Trade],
                                   start_time: datetime, end_time: datetime) -> List[PerformanceSnapshot]:
        """Calculate daily performance snapshots"""

        # Group by date
        daily_pnl: Dict[str, Decimal] = {}

        current_date = start_time.date()
        while current_date <= end_time.date():
            daily_pnl[current_date.isoformat()] = Decimal("0")
            current_date += timedelta(days=1)

        # Aggregate trades
        for trade in trades:
            if trade.exit_time:
                date_key = trade.exit_time.date().isoformat()
                if date_key in daily_pnl:
                    daily_pnl[date_key] += trade.pnl_usd

        # Create snapshots
        snapshots = []
        cumulative_pnl = Decimal("0")
        equity = self.starting_capital

        for date_str in sorted(daily_pnl.keys()):
            daily_pnl_value = daily_pnl[date_str]
            cumulative_pnl += daily_pnl_value
            equity += daily_pnl_value

            daily_return = (daily_pnl_value / equity) * Decimal("100") if equity > 0 else Decimal("0")
            total_return = (cumulative_pnl / self.starting_capital) * Decimal("100")

            snapshots.append(PerformanceSnapshot(
                date=datetime.fromisoformat(date_str),
                total_pnl_usd=cumulative_pnl,
                daily_pnl_usd=daily_pnl_value,
                total_return_pct=total_return,
                daily_return_pct=daily_return,
                total_trades=0,  # Could calculate if needed
                win_rate_pct=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                max_drawdown_pct=Decimal("0"),
                current_capital=equity
            ))

        return snapshots

    def _breakdown_by_dimension(self, trades: List[Trade], dimension: str) -> Dict[str, Dict]:
        """Break down performance by dimension"""
        breakdown: Dict[str, Dict] = {}

        for trade in trades:
            if dimension == "whale":
                key = trade.whale_address
            elif dimension == "market":
                key = trade.market_id
            elif dimension == "topic":
                key = trade.market_topic
            else:
                continue

            if key not in breakdown:
                breakdown[key] = {
                    "pnl_usd": Decimal("0"),
                    "trades": 0,
                    "wins": 0,
                    "losses": 0
                }

            breakdown[key]["pnl_usd"] += trade.pnl_usd
            breakdown[key]["trades"] += 1

            if trade.pnl_usd > 0:
                breakdown[key]["wins"] += 1
            elif trade.pnl_usd < 0:
                breakdown[key]["losses"] += 1

        return breakdown

    def _generate_alerts(self, trades: List[Trade], total_pnl: Decimal, max_dd: Decimal) -> List[str]:
        """Generate alerts for the report"""
        alerts = []

        # Large loss alert
        if self.config.alert_on_large_loss:
            large_losses = [t for t in trades if t.pnl_usd < -self.config.large_loss_threshold_usd]
            if large_losses:
                alerts.append(f"WARNING: {len(large_losses)} trades exceeded loss threshold of ${self.config.large_loss_threshold_usd}")

        # Drawdown alert
        if max_dd > Decimal("15.0"):
            alerts.append(f"WARNING: Max drawdown of {max_dd:.1f}% exceeds 15% threshold")

        # Negative period alert
        if total_pnl < 0:
            alerts.append(f"ALERT: Negative period P&L of ${total_pnl:,.2f}")

        return alerts

    async def _export_report(self, report_data: ReportData):
        """Export report to file"""

        # Generate filename
        timestamp = report_data.generation_time.strftime("%Y%m%d_%H%M%S")
        filename_base = f"{report_data.report_type.value}_report_{timestamp}"

        # Export to CSV
        csv_path = Path(self.config.reports_directory) / f"{filename_base}.csv"
        await self._export_csv(report_data, csv_path)

        # Export to JSON
        json_path = Path(self.config.reports_directory) / f"{filename_base}.json"
        await self._export_json(report_data, json_path)

        logger.info(f"Exported report to {csv_path} and {json_path}")

    async def _export_csv(self, report_data: ReportData, file_path: Path):
        """Export report to CSV"""

        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header section
            writer.writerow(["PERFORMANCE REPORT"])
            writer.writerow(["Report Type", report_data.report_type.value])
            writer.writerow(["Period", f"{report_data.report_period_start.date()} to {report_data.report_period_end.date()}"])
            writer.writerow(["Generated", report_data.generation_time.isoformat()])
            writer.writerow([])

            # Performance summary
            writer.writerow(["PERFORMANCE SUMMARY"])
            writer.writerow(["Starting Capital", str(report_data.starting_capital)])
            writer.writerow(["Ending Capital", str(report_data.ending_capital)])
            writer.writerow(["Total P&L", str(report_data.total_pnl_usd)])
            writer.writerow(["Total Return %", str(report_data.total_return_pct)])
            writer.writerow([])

            # Trade statistics
            writer.writerow(["TRADE STATISTICS"])
            writer.writerow(["Total Trades", report_data.total_trades])
            writer.writerow(["Winning Trades", report_data.winning_trades])
            writer.writerow(["Losing Trades", report_data.losing_trades])
            writer.writerow(["Win Rate %", str(report_data.win_rate_pct)])
            writer.writerow([])

            # Performance metrics
            writer.writerow(["PERFORMANCE METRICS"])
            writer.writerow(["Sharpe Ratio", str(report_data.sharpe_ratio)])
            writer.writerow(["Sortino Ratio", str(report_data.sortino_ratio)])
            writer.writerow(["Profit Factor", str(report_data.profit_factor)])
            writer.writerow(["Max Drawdown %", str(report_data.max_drawdown_pct)])
            writer.writerow([])

            # Alerts
            if report_data.alerts:
                writer.writerow(["ALERTS"])
                for alert in report_data.alerts:
                    writer.writerow([alert])
                writer.writerow([])

            # Daily snapshots
            writer.writerow(["DAILY PERFORMANCE"])
            writer.writerow(["Date", "Daily P&L", "Daily Return %", "Cumulative P&L", "Total Return %"])

            for snapshot in report_data.daily_snapshots:
                writer.writerow([
                    snapshot.date.date().isoformat(),
                    str(snapshot.daily_pnl_usd),
                    str(snapshot.daily_return_pct),
                    str(snapshot.total_pnl_usd),
                    str(snapshot.total_return_pct)
                ])

    async def _export_json(self, report_data: ReportData, file_path: Path):
        """Export report to JSON"""

        # Convert to dict (handle Decimal serialization)
        report_dict = {
            "report_type": report_data.report_type.value,
            "period_start": report_data.report_period_start.isoformat(),
            "period_end": report_data.report_period_end.isoformat(),
            "generation_time": report_data.generation_time.isoformat(),
            "performance": {
                "starting_capital": str(report_data.starting_capital),
                "ending_capital": str(report_data.ending_capital),
                "total_pnl_usd": str(report_data.total_pnl_usd),
                "total_return_pct": str(report_data.total_return_pct),
            },
            "trades": {
                "total": report_data.total_trades,
                "winning": report_data.winning_trades,
                "losing": report_data.losing_trades,
                "win_rate_pct": str(report_data.win_rate_pct)
            },
            "metrics": {
                "sharpe_ratio": str(report_data.sharpe_ratio),
                "sortino_ratio": str(report_data.sortino_ratio),
                "profit_factor": str(report_data.profit_factor),
                "max_drawdown_pct": str(report_data.max_drawdown_pct)
            },
            "alerts": report_data.alerts
        }

        with open(file_path, 'w') as jsonfile:
            json.dump(report_dict, jsonfile, indent=2)

    async def _send_email_report(self, report_data: ReportData):
        """Send report via email (placeholder)"""
        # In production, would use email library (smtplib, sendgrid, etc.)
        logger.info(f"Email delivery not implemented - would send to {self.config.email_recipients}")


# Example usage
if __name__ == "__main__":
    async def main():
        config = ReportConfig()
        engine = ReportingEngine(config)

        # Add sample trades
        print("Adding sample trades...")

        for i in range(50):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=f"0xwhale{i % 3}",
                market_id=f"market_{i % 5}",
                market_topic="Politics" if i % 2 == 0 else "Crypto",
                side="BUY",
                entry_price=Decimal("0.55"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.52"),
                position_size_usd=Decimal("1000"),
                entry_time=datetime.now() - timedelta(days=7, hours=i),
                exit_time=datetime.now() - timedelta(days=7-i//10, hours=i),
                pnl_usd=Decimal("50") if i % 2 == 0 else Decimal("-30"),
                pnl_pct=Decimal("5.0") if i % 2 == 0 else Decimal("-3.0"),
                is_open=False
            )
            engine.add_trade(trade)

        # Generate reports
        print("\nGenerating daily report...")
        daily_report = await engine.generate_report(ReportType.DAILY_PERFORMANCE)

        print("\nGenerating weekly report...")
        weekly_report = await engine.generate_report(ReportType.WEEKLY_STRATEGY)

        print(f"\nReports generated in: {config.reports_directory}")
        print(f"Daily Report - Total P&L: ${daily_report.total_pnl_usd:,.2f} ({daily_report.total_return_pct:.2f}%)")
        print(f"Weekly Report - Total P&L: ${weekly_report.total_pnl_usd:,.2f} ({weekly_report.total_return_pct:.2f}%)")

        if daily_report.alerts:
            print("\nAlerts:")
            for alert in daily_report.alerts:
                print(f"  - {alert}")

        print("\nReporting engine demo complete!")

    asyncio.run(main())
