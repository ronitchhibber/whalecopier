"""
Execution Analytics Dashboard
Week 7: Slippage & Execution Optimization - Analytics Dashboard
Comprehensive execution analytics, monitoring, and alerting system
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import json

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class AlertSeverity(Enum):
    """Alert severity level"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class MetricStatus(Enum):
    """Metric health status"""
    EXCELLENT = "EXCELLENT"  # Exceeding targets
    GOOD = "GOOD"            # Meeting targets
    WARNING = "WARNING"      # Below targets
    CRITICAL = "CRITICAL"    # Significantly below targets


@dataclass
class ExecutionMetrics:
    """Aggregated execution metrics for a time period"""
    time_period: str  # "1h", "24h", "7d", "all"
    start_time: datetime
    end_time: datetime

    # Order volume
    total_orders: int
    total_volume_usd: Decimal

    # Slippage metrics
    avg_slippage_pct: Decimal
    p95_slippage_pct: Decimal
    p99_slippage_pct: Decimal
    orders_skipped_slippage: int

    # Fill rate metrics
    fill_rate_pct: Decimal
    avg_time_to_fill_seconds: Decimal
    orders_cancelled: int
    cancellation_rate_pct: Decimal

    # Latency metrics
    avg_latency_ms: Decimal
    p50_latency_ms: Decimal
    p95_latency_ms: Decimal
    p99_latency_ms: Decimal

    # Execution quality score (0-100)
    execution_quality_score: Decimal

    # Status
    overall_status: MetricStatus

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketPerformance:
    """Execution performance for a specific market"""
    market_id: str
    market_name: Optional[str]

    # Volume
    order_count: int
    total_volume_usd: Decimal

    # Performance
    avg_slippage_pct: Decimal
    fill_rate_pct: Decimal
    avg_latency_ms: Decimal

    # Issues
    orders_skipped: int
    orders_cancelled: int

    # Score
    performance_score: Decimal
    status: MetricStatus


@dataclass
class ExecutionAlert:
    """Execution quality alert"""
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str

    # Context
    metric_name: str
    current_value: Decimal
    target_value: Decimal
    threshold_value: Decimal

    market_id: Optional[str]
    time_period: str

    # Actions
    recommended_actions: List[str]

    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False


@dataclass
class ExecutionReport:
    """Comprehensive execution report"""
    report_id: str
    report_type: str  # "hourly", "daily", "weekly", "custom"
    start_time: datetime
    end_time: datetime

    # Summary metrics
    summary: ExecutionMetrics

    # Market breakdown
    market_performance: List[MarketPerformance]

    # Alerts
    active_alerts: List[ExecutionAlert]

    # Trends
    slippage_trend: str  # "IMPROVING", "STABLE", "DEGRADING"
    fill_rate_trend: str
    latency_trend: str

    # Recommendations
    recommendations: List[str]

    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DashboardConfig:
    """Configuration for execution analytics dashboard"""
    # Target metrics
    target_slippage_pct: Decimal = Decimal("1.0")  # Target <1% slippage
    target_fill_rate_pct: Decimal = Decimal("95")  # Target >95% fill rate
    target_latency_ms: Decimal = Decimal("200")    # Target <200ms p50 latency

    # Alert thresholds
    alert_slippage_warning: Decimal = Decimal("1.5")  # Warn at 1.5%
    alert_slippage_critical: Decimal = Decimal("2.5")  # Critical at 2.5%

    alert_fill_rate_warning: Decimal = Decimal("90")  # Warn at 90%
    alert_fill_rate_critical: Decimal = Decimal("85")  # Critical at 85%

    alert_latency_warning: Decimal = Decimal("300")  # Warn at 300ms
    alert_latency_critical: Decimal = Decimal("500")  # Critical at 500ms

    alert_cancellation_warning: Decimal = Decimal("15")  # Warn at 15%
    alert_cancellation_critical: Decimal = Decimal("25")  # Critical at 25%

    # Monitoring
    monitoring_interval_seconds: int = 300  # Check every 5 minutes
    alert_cooldown_seconds: int = 3600      # 1 hour between duplicate alerts

    # Reporting
    enable_hourly_reports: bool = True
    enable_daily_reports: bool = True
    report_retention_days: int = 30


# ==================== Execution Analytics Dashboard ====================

class ExecutionAnalyticsDashboard:
    """
    Execution Analytics Dashboard

    Comprehensive execution monitoring and analytics system that:
    1. **Aggregates Metrics:** Combines slippage, fill rate, latency metrics
    2. **Real-Time Monitoring:** Continuous monitoring with configurable intervals
    3. **Alert System:** Multi-level alerts (INFO/WARNING/CRITICAL)
    4. **Market Analysis:** Identifies problematic markets
    5. **Trend Detection:** Detects improving/degrading trends
    6. **Automated Reports:** Hourly, daily, weekly execution reports
    7. **Quality Scoring:** 0-100 execution quality score

    Execution Quality Score:
    - Slippage: 30% weight (lower is better)
    - Fill Rate: 35% weight (higher is better)
    - Latency: 20% weight (lower is better)
    - Cancellation Rate: 15% weight (lower is better)
    - Score 90-100: EXCELLENT
    - Score 75-90: GOOD
    - Score 60-75: WARNING
    - Score <60: CRITICAL
    """

    def __init__(
        self,
        depth_analyzer=None,
        order_router=None,
        latency_optimizer=None,
        fill_rate_optimizer=None,
        config: Optional[DashboardConfig] = None
    ):
        """
        Initialize execution analytics dashboard

        Args:
            depth_analyzer: Order book depth analyzer instance
            order_router: Smart order router instance
            latency_optimizer: Latency optimizer instance
            fill_rate_optimizer: Fill rate optimizer instance
            config: Dashboard configuration
        """
        self.config = config or DashboardConfig()

        # Execution components (optional - will use if provided)
        self.depth_analyzer = depth_analyzer
        self.order_router = order_router
        self.latency_optimizer = latency_optimizer
        self.fill_rate_optimizer = fill_rate_optimizer

        # Metrics storage
        self.metrics_history: deque = deque(maxlen=10000)  # Last 10k metric records
        self.market_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Alerts
        self.active_alerts: Dict[str, ExecutionAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.last_alert_time: Dict[str, datetime] = {}  # For cooldown

        # Reports
        self.report_history: deque = deque(maxlen=100)

        # Background tasks
        self.monitor_task: Optional[asyncio.Task] = None
        self.report_task: Optional[asyncio.Task] = None

        # Alert counter
        self.alert_counter = 0

        logger.info(
            f"ExecutionAnalyticsDashboard initialized: "
            f"target_slippage={self.config.target_slippage_pct}%, "
            f"target_fill_rate={self.config.target_fill_rate_pct}%, "
            f"target_latency={self.config.target_latency_ms}ms"
        )

    async def initialize(self):
        """Start background monitoring and reporting"""
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

        if self.config.enable_hourly_reports or self.config.enable_daily_reports:
            self.report_task = asyncio.create_task(self._reporting_loop())

        logger.info("ExecutionAnalyticsDashboard monitoring started")

    async def shutdown(self):
        """Shutdown dashboard"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        if self.report_task:
            self.report_task.cancel()
            try:
                await self.report_task
            except asyncio.CancelledError:
                pass

        logger.info("ExecutionAnalyticsDashboard shutdown complete")

    def record_execution(
        self,
        market_id: str,
        order_size_usd: Decimal,
        slippage_pct: Optional[Decimal] = None,
        fill_rate_pct: Optional[Decimal] = None,
        latency_ms: Optional[Decimal] = None,
        time_to_fill_seconds: Optional[Decimal] = None,
        was_cancelled: bool = False,
        was_skipped: bool = False
    ):
        """
        Record an execution event

        Args:
            market_id: Market identifier
            order_size_usd: Order size
            slippage_pct: Slippage percentage (if applicable)
            fill_rate_pct: Fill rate percentage
            latency_ms: Execution latency
            time_to_fill_seconds: Time to fill order
            was_cancelled: Whether order was cancelled
            was_skipped: Whether order was skipped
        """
        record = {
            "market_id": market_id,
            "timestamp": datetime.now(),
            "order_size_usd": order_size_usd,
            "slippage_pct": slippage_pct,
            "fill_rate_pct": fill_rate_pct,
            "latency_ms": latency_ms,
            "time_to_fill_seconds": time_to_fill_seconds,
            "was_cancelled": was_cancelled,
            "was_skipped": was_skipped
        }

        self.metrics_history.append(record)
        self.market_metrics[market_id].append(record)

    def get_execution_metrics(
        self,
        time_period: str = "24h",
        market_id: Optional[str] = None
    ) -> ExecutionMetrics:
        """
        Get aggregated execution metrics

        Args:
            time_period: "1h", "24h", "7d", "all"
            market_id: Specific market (None for all)

        Returns:
            Aggregated execution metrics
        """
        # Determine time window
        if time_period == "1h":
            cutoff = datetime.now() - timedelta(hours=1)
        elif time_period == "24h":
            cutoff = datetime.now() - timedelta(hours=24)
        elif time_period == "7d":
            cutoff = datetime.now() - timedelta(days=7)
        else:  # "all"
            cutoff = datetime.min

        # Filter records
        if market_id:
            records = [
                r for r in self.market_metrics[market_id]
                if r["timestamp"] >= cutoff
            ]
        else:
            records = [r for r in self.metrics_history if r["timestamp"] >= cutoff]

        if not records:
            return self._empty_metrics(time_period, cutoff)

        # Calculate metrics
        total_orders = len(records)
        total_volume = sum(r["order_size_usd"] for r in records)

        # Slippage
        slippage_values = [r["slippage_pct"] for r in records if r["slippage_pct"] is not None]
        avg_slippage = sum(slippage_values) / len(slippage_values) if slippage_values else Decimal("0")
        p95_slippage = self._percentile(slippage_values, 95) if slippage_values else Decimal("0")
        p99_slippage = self._percentile(slippage_values, 99) if slippage_values else Decimal("0")
        skipped_slippage = sum(1 for r in records if r["was_skipped"])

        # Fill rate
        fill_rates = [r["fill_rate_pct"] for r in records if r["fill_rate_pct"] is not None]
        avg_fill_rate = sum(fill_rates) / len(fill_rates) if fill_rates else Decimal("100")
        cancelled = sum(1 for r in records if r["was_cancelled"])
        cancellation_rate = (Decimal(str(cancelled)) / Decimal(str(total_orders))) * Decimal("100")

        # Time to fill
        fill_times = [r["time_to_fill_seconds"] for r in records if r["time_to_fill_seconds"] is not None]
        avg_time_to_fill = sum(fill_times) / len(fill_times) if fill_times else Decimal("0")

        # Latency
        latencies = [r["latency_ms"] for r in records if r["latency_ms"] is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else Decimal("0")
        p50_latency = self._percentile(latencies, 50) if latencies else Decimal("0")
        p95_latency = self._percentile(latencies, 95) if latencies else Decimal("0")
        p99_latency = self._percentile(latencies, 99) if latencies else Decimal("0")

        # Calculate execution quality score
        quality_score = self._calculate_quality_score(
            avg_slippage, avg_fill_rate, p50_latency, cancellation_rate
        )

        # Determine overall status
        overall_status = self._determine_status(quality_score)

        return ExecutionMetrics(
            time_period=time_period,
            start_time=cutoff,
            end_time=datetime.now(),
            total_orders=total_orders,
            total_volume_usd=total_volume,
            avg_slippage_pct=avg_slippage,
            p95_slippage_pct=p95_slippage,
            p99_slippage_pct=p99_slippage,
            orders_skipped_slippage=skipped_slippage,
            fill_rate_pct=avg_fill_rate,
            avg_time_to_fill_seconds=avg_time_to_fill,
            orders_cancelled=cancelled,
            cancellation_rate_pct=cancellation_rate,
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            execution_quality_score=quality_score,
            overall_status=overall_status
        )

    def get_market_performance(
        self,
        time_period: str = "24h"
    ) -> List[MarketPerformance]:
        """
        Get performance breakdown by market

        Args:
            time_period: "1h", "24h", "7d", "all"

        Returns:
            List of market performance metrics
        """
        market_performances = []

        for market_id in self.market_metrics.keys():
            metrics = self.get_execution_metrics(time_period, market_id)

            if metrics.total_orders == 0:
                continue

            # Calculate performance score
            performance_score = self._calculate_quality_score(
                metrics.avg_slippage_pct,
                metrics.fill_rate_pct,
                metrics.p50_latency_ms,
                metrics.cancellation_rate_pct
            )

            status = self._determine_status(performance_score)

            market_performances.append(MarketPerformance(
                market_id=market_id,
                market_name=None,  # Could fetch from market registry
                order_count=metrics.total_orders,
                total_volume_usd=metrics.total_volume_usd,
                avg_slippage_pct=metrics.avg_slippage_pct,
                fill_rate_pct=metrics.fill_rate_pct,
                avg_latency_ms=metrics.avg_latency_ms,
                orders_skipped=metrics.orders_skipped_slippage,
                orders_cancelled=metrics.orders_cancelled,
                performance_score=performance_score,
                status=status
            ))

        # Sort by volume (most traded first)
        market_performances.sort(key=lambda m: m.total_volume_usd, reverse=True)

        return market_performances

    def detect_trends(self, time_window_hours: int = 24) -> Dict[str, str]:
        """
        Detect metric trends (improving, stable, degrading)

        Args:
            time_window_hours: Hours to analyze

        Returns:
            Dict of metric trends
        """
        # Get metrics for two periods
        now = datetime.now()
        midpoint = now - timedelta(hours=time_window_hours / 2)
        start = now - timedelta(hours=time_window_hours)

        # Recent period
        recent_records = [
            r for r in self.metrics_history
            if midpoint <= r["timestamp"] <= now
        ]

        # Earlier period
        earlier_records = [
            r for r in self.metrics_history
            if start <= r["timestamp"] < midpoint
        ]

        if not recent_records or not earlier_records:
            return {
                "slippage_trend": "INSUFFICIENT_DATA",
                "fill_rate_trend": "INSUFFICIENT_DATA",
                "latency_trend": "INSUFFICIENT_DATA"
            }

        # Calculate averages for each period
        def calc_avg(records, key):
            values = [r[key] for r in records if r[key] is not None]
            return sum(values) / len(values) if values else Decimal("0")

        # Slippage trend (lower is better, so reverse logic)
        earlier_slippage = calc_avg(earlier_records, "slippage_pct")
        recent_slippage = calc_avg(recent_records, "slippage_pct")
        slippage_change_pct = ((recent_slippage - earlier_slippage) / earlier_slippage * Decimal("100")) if earlier_slippage > 0 else Decimal("0")

        if slippage_change_pct < -Decimal("10"):  # 10% reduction
            slippage_trend = "IMPROVING"
        elif slippage_change_pct > Decimal("10"):  # 10% increase
            slippage_trend = "DEGRADING"
        else:
            slippage_trend = "STABLE"

        # Fill rate trend (higher is better)
        earlier_fill_rate = calc_avg(earlier_records, "fill_rate_pct")
        recent_fill_rate = calc_avg(recent_records, "fill_rate_pct")
        fill_rate_change_pct = recent_fill_rate - earlier_fill_rate

        if fill_rate_change_pct > Decimal("2"):  # 2% improvement
            fill_rate_trend = "IMPROVING"
        elif fill_rate_change_pct < -Decimal("2"):  # 2% degradation
            fill_rate_trend = "DEGRADING"
        else:
            fill_rate_trend = "STABLE"

        # Latency trend (lower is better)
        earlier_latency = calc_avg(earlier_records, "latency_ms")
        recent_latency = calc_avg(recent_records, "latency_ms")
        latency_change_pct = ((recent_latency - earlier_latency) / earlier_latency * Decimal("100")) if earlier_latency > 0 else Decimal("0")

        if latency_change_pct < -Decimal("10"):  # 10% reduction
            latency_trend = "IMPROVING"
        elif latency_change_pct > Decimal("10"):  # 10% increase
            latency_trend = "DEGRADING"
        else:
            latency_trend = "STABLE"

        return {
            "slippage_trend": slippage_trend,
            "fill_rate_trend": fill_rate_trend,
            "latency_trend": latency_trend
        }

    def generate_report(
        self,
        report_type: str = "hourly",
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
    ) -> ExecutionReport:
        """
        Generate comprehensive execution report

        Args:
            report_type: "hourly", "daily", "weekly", "custom"
            custom_start: Custom start time (for custom reports)
            custom_end: Custom end time (for custom reports)

        Returns:
            Execution report
        """
        # Determine time period
        if report_type == "hourly":
            time_period = "1h"
        elif report_type == "daily":
            time_period = "24h"
        elif report_type == "weekly":
            time_period = "7d"
        else:  # custom
            time_period = "custom"

        # Get summary metrics
        summary = self.get_execution_metrics(time_period)

        # Get market breakdown
        market_performance = self.get_market_performance(time_period)

        # Get active alerts
        active_alerts = list(self.active_alerts.values())

        # Detect trends
        trends = self.detect_trends(24)

        # Generate recommendations
        recommendations = self._generate_recommendations(summary, market_performance, trends)

        # Create report
        report = ExecutionReport(
            report_id=f"exec_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            report_type=report_type,
            start_time=summary.start_time,
            end_time=summary.end_time,
            summary=summary,
            market_performance=market_performance,
            active_alerts=active_alerts,
            slippage_trend=trends["slippage_trend"],
            fill_rate_trend=trends["fill_rate_trend"],
            latency_trend=trends["latency_trend"],
            recommendations=recommendations
        )

        self.report_history.append(report)

        logger.info(
            f"Generated {report_type} report: "
            f"quality={summary.execution_quality_score:.1f}, "
            f"status={summary.overall_status.value}, "
            f"alerts={len(active_alerts)}"
        )

        return report

    def print_report(self, report: ExecutionReport):
        """Print formatted execution report"""
        print(f"\n{'='*80}")
        print(f"EXECUTION ANALYTICS REPORT - {report.report_type.upper()}")
        print(f"{'='*80}")
        print(f"Period: {report.start_time.strftime('%Y-%m-%d %H:%M')} to {report.end_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Summary
        s = report.summary
        print(f"📊 SUMMARY")
        print(f"{'─'*80}")
        print(f"  Orders: {s.total_orders:,} | Volume: ${s.total_volume_usd:,.2f}")
        print(f"  Execution Quality Score: {s.execution_quality_score:.1f}/100 [{s.overall_status.value}]")
        print()

        # Slippage
        print(f"  💸 Slippage:")
        print(f"     Avg: {s.avg_slippage_pct:.2f}% | P95: {s.p95_slippage_pct:.2f}% | P99: {s.p99_slippage_pct:.2f}%")
        print(f"     Skipped (excessive slippage): {s.orders_skipped_slippage}")
        print(f"     Trend: {report.slippage_trend}")
        print()

        # Fill Rate
        print(f"  ✅ Fill Rate:")
        print(f"     Fill Rate: {s.fill_rate_pct:.1f}%")
        print(f"     Avg Time to Fill: {s.avg_time_to_fill_seconds:.1f}s")
        print(f"     Cancelled: {s.orders_cancelled} ({s.cancellation_rate_pct:.1f}%)")
        print(f"     Trend: {report.fill_rate_trend}")
        print()

        # Latency
        print(f"  ⚡ Latency:")
        print(f"     Avg: {s.avg_latency_ms:.0f}ms | P50: {s.p50_latency_ms:.0f}ms | P95: {s.p95_latency_ms:.0f}ms | P99: {s.p99_latency_ms:.0f}ms")
        print(f"     Trend: {report.latency_trend}")
        print()

        # Market Performance
        if report.market_performance:
            print(f"🏪 TOP MARKETS BY VOLUME")
            print(f"{'─'*80}")
            for i, market in enumerate(report.market_performance[:5], 1):
                print(f"  {i}. {market.market_id}")
                print(f"     Orders: {market.order_count} | Volume: ${market.total_volume_usd:,.2f}")
                print(f"     Slippage: {market.avg_slippage_pct:.2f}% | Fill Rate: {market.fill_rate_pct:.1f}% | Latency: {market.avg_latency_ms:.0f}ms")
                print(f"     Score: {market.performance_score:.1f}/100 [{market.status.value}]")
                print()

        # Alerts
        if report.active_alerts:
            print(f"🚨 ACTIVE ALERTS ({len(report.active_alerts)})")
            print(f"{'─'*80}")
            for alert in report.active_alerts[:5]:
                severity_icon = "🔴" if alert.severity == AlertSeverity.CRITICAL else "🟡"
                print(f"  {severity_icon} [{alert.severity.value}] {alert.title}")
                print(f"     {alert.message}")
                print()

        # Recommendations
        if report.recommendations:
            print(f"💡 RECOMMENDATIONS")
            print(f"{'─'*80}")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
            print()

        print(f"{'='*80}\n")

    # ==================== Private Methods ====================

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        logger.info("Execution monitoring loop started")

        while True:
            try:
                await asyncio.sleep(self.config.monitoring_interval_seconds)

                # Get current metrics
                metrics = self.get_execution_metrics("1h")

                # Check for alert conditions
                self._check_alerts(metrics)

            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {str(e)}")

    async def _reporting_loop(self):
        """Background reporting loop"""
        logger.info("Reporting loop started")

        last_hourly_report = datetime.now()
        last_daily_report = datetime.now()

        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = datetime.now()

                # Hourly reports
                if self.config.enable_hourly_reports:
                    if (now - last_hourly_report).total_seconds() >= 3600:
                        report = self.generate_report("hourly")
                        logger.info(f"Generated hourly report: {report.report_id}")
                        last_hourly_report = now

                # Daily reports
                if self.config.enable_daily_reports:
                    if (now - last_daily_report).total_seconds() >= 86400:
                        report = self.generate_report("daily")
                        logger.info(f"Generated daily report: {report.report_id}")
                        self.print_report(report)
                        last_daily_report = now

            except asyncio.CancelledError:
                logger.info("Reporting loop cancelled")
                break
            except Exception as e:
                logger.error(f"Reporting loop error: {str(e)}")

    def _check_alerts(self, metrics: ExecutionMetrics):
        """Check metrics and generate alerts"""
        # Slippage alerts
        if metrics.avg_slippage_pct >= self.config.alert_slippage_critical:
            self._create_alert(
                "SLIPPAGE_CRITICAL",
                AlertSeverity.CRITICAL,
                "Critical Slippage Detected",
                f"Average slippage {metrics.avg_slippage_pct:.2f}% exceeds critical threshold",
                "avg_slippage_pct",
                metrics.avg_slippage_pct,
                self.config.target_slippage_pct,
                self.config.alert_slippage_critical,
                None,
                [
                    "Review order sizing - may be too large for market depth",
                    "Consider using TWAP for large orders",
                    "Check if markets have sufficient liquidity"
                ]
            )
        elif metrics.avg_slippage_pct >= self.config.alert_slippage_warning:
            self._create_alert(
                "SLIPPAGE_WARNING",
                AlertSeverity.WARNING,
                "Elevated Slippage",
                f"Average slippage {metrics.avg_slippage_pct:.2f}% above target",
                "avg_slippage_pct",
                metrics.avg_slippage_pct,
                self.config.target_slippage_pct,
                self.config.alert_slippage_warning,
                None,
                ["Monitor slippage trends", "Consider reducing order sizes"]
            )

        # Fill rate alerts
        if metrics.fill_rate_pct <= self.config.alert_fill_rate_critical:
            self._create_alert(
                "FILL_RATE_CRITICAL",
                AlertSeverity.CRITICAL,
                "Critical Fill Rate",
                f"Fill rate {metrics.fill_rate_pct:.1f}% below critical threshold",
                "fill_rate_pct",
                metrics.fill_rate_pct,
                self.config.target_fill_rate_pct,
                self.config.alert_fill_rate_critical,
                None,
                [
                    "Use more aggressive pricing strategies",
                    "Increase timeout for order fills",
                    "Review market liquidity conditions"
                ]
            )
        elif metrics.fill_rate_pct <= self.config.alert_fill_rate_warning:
            self._create_alert(
                "FILL_RATE_WARNING",
                AlertSeverity.WARNING,
                "Low Fill Rate",
                f"Fill rate {metrics.fill_rate_pct:.1f}% below target",
                "fill_rate_pct",
                metrics.fill_rate_pct,
                self.config.target_fill_rate_pct,
                self.config.alert_fill_rate_warning,
                None,
                ["Monitor fill rate trends", "Consider adjusting pricing strategy"]
            )

        # Latency alerts
        if metrics.p50_latency_ms >= self.config.alert_latency_critical:
            self._create_alert(
                "LATENCY_CRITICAL",
                AlertSeverity.CRITICAL,
                "Critical Latency",
                f"P50 latency {metrics.p50_latency_ms:.0f}ms exceeds critical threshold",
                "p50_latency_ms",
                metrics.p50_latency_ms,
                self.config.target_latency_ms,
                self.config.alert_latency_critical,
                None,
                [
                    "Check network connectivity",
                    "Review API response times",
                    "Consider geographic proximity to exchange"
                ]
            )

        # Cancellation rate alerts
        if metrics.cancellation_rate_pct >= self.config.alert_cancellation_critical:
            self._create_alert(
                "CANCELLATION_CRITICAL",
                AlertSeverity.CRITICAL,
                "High Cancellation Rate",
                f"Cancellation rate {metrics.cancellation_rate_pct:.1f}% is critically high",
                "cancellation_rate_pct",
                metrics.cancellation_rate_pct,
                Decimal("0"),
                self.config.alert_cancellation_critical,
                None,
                [
                    "Use more aggressive pricing",
                    "Increase order timeout",
                    "Review market conditions"
                ]
            )

    def _create_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        title: str,
        message: str,
        metric_name: str,
        current_value: Decimal,
        target_value: Decimal,
        threshold_value: Decimal,
        market_id: Optional[str],
        recommended_actions: List[str]
    ):
        """Create an alert with cooldown"""
        # Check cooldown
        if alert_type in self.last_alert_time:
            time_since_last = (datetime.now() - self.last_alert_time[alert_type]).total_seconds()
            if time_since_last < self.config.alert_cooldown_seconds:
                return  # Skip - still in cooldown

        self.alert_counter += 1
        alert_id = f"alert_{self.alert_counter}"

        alert = ExecutionAlert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            target_value=target_value,
            threshold_value=threshold_value,
            market_id=market_id,
            time_period="1h",
            recommended_actions=recommended_actions
        )

        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.last_alert_time[alert_type] = datetime.now()

        logger.warning(f"🚨 ALERT [{severity.value}]: {title} - {message}")

    def _calculate_quality_score(
        self,
        slippage_pct: Decimal,
        fill_rate_pct: Decimal,
        latency_ms: Decimal,
        cancellation_rate_pct: Decimal
    ) -> Decimal:
        """Calculate execution quality score (0-100)"""
        # Slippage score (30% weight) - lower is better
        if slippage_pct <= self.config.target_slippage_pct:
            slippage_score = Decimal("100")
        elif slippage_pct >= self.config.alert_slippage_critical:
            slippage_score = Decimal("0")
        else:
            # Linear interpolation
            slippage_score = Decimal("100") * (
                (self.config.alert_slippage_critical - slippage_pct) /
                (self.config.alert_slippage_critical - self.config.target_slippage_pct)
            )

        # Fill rate score (35% weight) - higher is better
        if fill_rate_pct >= self.config.target_fill_rate_pct:
            fill_rate_score = Decimal("100")
        elif fill_rate_pct <= self.config.alert_fill_rate_critical:
            fill_rate_score = Decimal("0")
        else:
            fill_rate_score = Decimal("100") * (
                (fill_rate_pct - self.config.alert_fill_rate_critical) /
                (self.config.target_fill_rate_pct - self.config.alert_fill_rate_critical)
            )

        # Latency score (20% weight) - lower is better
        if latency_ms <= self.config.target_latency_ms:
            latency_score = Decimal("100")
        elif latency_ms >= self.config.alert_latency_critical:
            latency_score = Decimal("0")
        else:
            latency_score = Decimal("100") * (
                (self.config.alert_latency_critical - latency_ms) /
                (self.config.alert_latency_critical - self.config.target_latency_ms)
            )

        # Cancellation rate score (15% weight) - lower is better
        if cancellation_rate_pct <= Decimal("5"):  # <5% is excellent
            cancellation_score = Decimal("100")
        elif cancellation_rate_pct >= self.config.alert_cancellation_critical:
            cancellation_score = Decimal("0")
        else:
            cancellation_score = Decimal("100") * (
                (self.config.alert_cancellation_critical - cancellation_rate_pct) /
                (self.config.alert_cancellation_critical - Decimal("5"))
            )

        # Weighted average
        quality_score = (
            slippage_score * Decimal("0.30") +
            fill_rate_score * Decimal("0.35") +
            latency_score * Decimal("0.20") +
            cancellation_score * Decimal("0.15")
        )

        return max(Decimal("0"), min(Decimal("100"), quality_score))

    def _determine_status(self, quality_score: Decimal) -> MetricStatus:
        """Determine metric status from quality score"""
        if quality_score >= Decimal("90"):
            return MetricStatus.EXCELLENT
        elif quality_score >= Decimal("75"):
            return MetricStatus.GOOD
        elif quality_score >= Decimal("60"):
            return MetricStatus.WARNING
        else:
            return MetricStatus.CRITICAL

    def _generate_recommendations(
        self,
        summary: ExecutionMetrics,
        market_performance: List[MarketPerformance],
        trends: Dict[str, str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Slippage recommendations
        if summary.avg_slippage_pct > self.config.target_slippage_pct:
            recommendations.append(
                f"Slippage {summary.avg_slippage_pct:.2f}% exceeds target - "
                "consider using TWAP for orders >$1000"
            )

        # Fill rate recommendations
        if summary.fill_rate_pct < self.config.target_fill_rate_pct:
            recommendations.append(
                f"Fill rate {summary.fill_rate_pct:.1f}% below target - "
                "use more aggressive pricing strategies"
            )

        # Latency recommendations
        if summary.p50_latency_ms > self.config.target_latency_ms:
            recommendations.append(
                f"Latency {summary.p50_latency_ms:.0f}ms exceeds target - "
                "review network and API performance"
            )

        # Problematic markets
        problem_markets = [m for m in market_performance if m.status == MetricStatus.CRITICAL]
        if problem_markets:
            recommendations.append(
                f"Consider blacklisting {len(problem_markets)} markets with poor execution: "
                f"{', '.join(m.market_id for m in problem_markets[:3])}"
            )

        # Trend recommendations
        if trends["slippage_trend"] == "DEGRADING":
            recommendations.append("Slippage is trending worse - investigate market conditions")

        if trends["fill_rate_trend"] == "DEGRADING":
            recommendations.append("Fill rate is declining - review pricing and timeout settings")

        if not recommendations:
            recommendations.append("Execution quality is excellent - no action needed")

        return recommendations

    def _percentile(self, values: List[Decimal], percentile: int) -> Decimal:
        """Calculate percentile of a list"""
        if not values:
            return Decimal("0")
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _empty_metrics(self, time_period: str, cutoff: datetime) -> ExecutionMetrics:
        """Return empty metrics"""
        return ExecutionMetrics(
            time_period=time_period,
            start_time=cutoff,
            end_time=datetime.now(),
            total_orders=0,
            total_volume_usd=Decimal("0"),
            avg_slippage_pct=Decimal("0"),
            p95_slippage_pct=Decimal("0"),
            p99_slippage_pct=Decimal("0"),
            orders_skipped_slippage=0,
            fill_rate_pct=Decimal("100"),
            avg_time_to_fill_seconds=Decimal("0"),
            orders_cancelled=0,
            cancellation_rate_pct=Decimal("0"),
            avg_latency_ms=Decimal("0"),
            p50_latency_ms=Decimal("0"),
            p95_latency_ms=Decimal("0"),
            p99_latency_ms=Decimal("0"),
            execution_quality_score=Decimal("100"),
            overall_status=MetricStatus.EXCELLENT
        )


# ==================== Example Usage ====================

async def main():
    """Example usage of ExecutionAnalyticsDashboard"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize dashboard
    dashboard = ExecutionAnalyticsDashboard()
    await dashboard.initialize()

    print("\n=== Execution Analytics Dashboard Test ===\n")

    try:
        # Simulate some executions
        import random

        print("Simulating 50 order executions...\n")

        markets = ["market_A", "market_B", "market_C", "market_D"]

        for i in range(50):
            market_id = random.choice(markets)
            order_size = Decimal(str(random.uniform(100, 2000)))
            slippage = Decimal(str(random.uniform(0.1, 2.5)))
            fill_rate = Decimal(str(random.uniform(85, 100)))
            latency = Decimal(str(random.uniform(50, 400)))
            time_to_fill = Decimal(str(random.uniform(1, 30)))
            was_cancelled = random.random() < 0.1
            was_skipped = random.random() < 0.05

            dashboard.record_execution(
                market_id=market_id,
                order_size_usd=order_size,
                slippage_pct=slippage,
                fill_rate_pct=fill_rate,
                latency_ms=latency,
                time_to_fill_seconds=time_to_fill,
                was_cancelled=was_cancelled,
                was_skipped=was_skipped
            )

            await asyncio.sleep(0.01)  # Small delay

        # Generate and print report
        report = dashboard.generate_report("hourly")
        dashboard.print_report(report)

    finally:
        await dashboard.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
