"""
Analytics Integration Layer - Connects all analytics modules to the copy trading system

This module provides a unified interface to all analytics systems:
- Performance Metrics Engine (Sharpe, Sortino, Calmar ratios)
- Trade Attribution Analyzer (P&L breakdown)
- Benchmarking System (Alpha, beta calculations)
- Reporting Engine (Automated reports)
- Real-time Analytics Dashboard
- Edge Detection System
- CUSUM Edge Decay Detector
- Market Efficiency Analyzer
- Whale Lifecycle Tracker
- Adaptive Threshold Manager

Integration points:
1. Trade feed from copy trading engine
2. Whale performance monitoring
3. Market efficiency tracking
4. Dynamic allocation recommendations
5. Automated alerts and reports

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

# Import all analytics modules
from .performance_metrics_engine import (
    PerformanceMetricsEngine,
    PerformanceConfig,
    Trade as PerfTrade,
    TimeWindow
)
from .trade_attribution_analyzer import (
    TradeAttributionAnalyzer,
    AttributionConfig,
    Trade as AttrTrade
)
from .benchmarking_system import (
    BenchmarkingSystem,
    BenchmarkConfig,
    Trade as BenchTrade
)
from .reporting_engine import (
    ReportingEngine,
    ReportConfig,
    Trade as ReportTrade,
    ReportType
)
from .realtime_analytics_dashboard import (
    RealtimeAnalyticsDashboard,
    DashboardConfig,
    Trade as DashTrade
)
from .edge_detection_system import (
    EdgeDetectionSystem,
    EdgeConfig,
    Trade as EdgeTrade
)
from .cusum_edge_decay_detector import (
    CUSUMEdgeDecayDetector,
    CUSUMConfig,
    Trade as CUSUMTrade
)
from .market_efficiency_analyzer import (
    MarketEfficiencyAnalyzer,
    EfficiencyConfig,
    Trade as EffTrade
)
from .whale_lifecycle_tracker import (
    WhaleLifecycleTracker,
    LifecycleConfig,
    Trade as LifeTrade
)
from .adaptive_threshold_manager import (
    AdaptiveThresholdManager,
    AdaptiveConfig,
    Trade as ThreshTrade
)

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsIntegrationConfig:
    """Configuration for analytics integration"""
    enable_performance_metrics: bool = True
    enable_attribution: bool = True
    enable_benchmarking: bool = True
    enable_reporting: bool = True
    enable_realtime_dashboard: bool = True
    enable_edge_detection: bool = True
    enable_cusum_decay: bool = True
    enable_market_efficiency: bool = True
    enable_lifecycle_tracking: bool = True
    enable_adaptive_thresholds: bool = True

    # Starting capital
    starting_capital_usd: Decimal = Decimal("10000")

    # Update intervals
    metrics_update_interval_seconds: int = 60
    reports_update_interval_seconds: int = 3600
    dashboard_update_interval_seconds: int = 5


class AnalyticsIntegration:
    """
    Unified analytics integration layer for the copy trading system.

    This class:
    1. Initializes all analytics modules
    2. Feeds trade data from the copy trading engine
    3. Provides unified access to all analytics
    4. Generates recommendations for trading decisions
    5. Sends alerts and reports
    """

    def __init__(self, config: AnalyticsIntegrationConfig):
        self.config = config

        # Analytics modules
        self.performance_metrics: Optional[PerformanceMetricsEngine] = None
        self.attribution_analyzer: Optional[TradeAttributionAnalyzer] = None
        self.benchmarking: Optional[BenchmarkingSystem] = None
        self.reporting: Optional[ReportingEngine] = None
        self.dashboard: Optional[RealtimeAnalyticsDashboard] = None
        self.edge_detection: Optional[EdgeDetectionSystem] = None
        self.cusum_decay: Optional[CUSUMEdgeDecayDetector] = None
        self.market_efficiency: Optional[MarketEfficiencyAnalyzer] = None
        self.lifecycle_tracker: Optional[WhaleLifecycleTracker] = None
        self.adaptive_thresholds: Optional[AdaptiveThresholdManager] = None

        # State
        self.is_running: bool = False
        self.background_tasks: List[asyncio.Task] = []

        logger.info("AnalyticsIntegration initialized")

    async def initialize(self):
        """Initialize all analytics modules"""
        logger.info("Initializing analytics modules...")

        # Performance Metrics
        if self.config.enable_performance_metrics:
            perf_config = PerformanceConfig(
                starting_capital=self.config.starting_capital_usd,
                update_interval_seconds=self.config.metrics_update_interval_seconds
            )
            self.performance_metrics = PerformanceMetricsEngine(perf_config)
            logger.info("✓ Performance Metrics Engine initialized")

        # Attribution Analyzer
        if self.config.enable_attribution:
            attr_config = AttributionConfig()
            self.attribution_analyzer = TradeAttributionAnalyzer(attr_config)
            logger.info("✓ Trade Attribution Analyzer initialized")

        # Benchmarking System
        if self.config.enable_benchmarking:
            bench_config = BenchmarkConfig(
                starting_capital=self.config.starting_capital_usd
            )
            self.benchmarking = BenchmarkingSystem(bench_config)
            logger.info("✓ Benchmarking System initialized")

        # Reporting Engine
        if self.config.enable_reporting:
            report_config = ReportingConfig(
                starting_capital=self.config.starting_capital_usd
            )
            self.reporting = ReportingEngine(report_config)
            logger.info("✓ Reporting Engine initialized")

        # Real-time Dashboard
        if self.config.enable_realtime_dashboard:
            dash_config = DashboardConfig(
                starting_capital=self.config.starting_capital_usd,
                update_interval_seconds=self.config.dashboard_update_interval_seconds
            )
            self.dashboard = RealtimeAnalyticsDashboard(dash_config)
            logger.info("✓ Real-time Analytics Dashboard initialized")

        # Edge Detection
        if self.config.enable_edge_detection:
            edge_config = EdgeConfig()
            self.edge_detection = EdgeDetectionSystem(edge_config)
            logger.info("✓ Edge Detection System initialized")

        # CUSUM Decay Detector
        if self.config.enable_cusum_decay:
            cusum_config = CUSUMConfig()
            self.cusum_decay = CUSUMEdgeDecayDetector(cusum_config)
            logger.info("✓ CUSUM Edge Decay Detector initialized")

        # Market Efficiency Analyzer
        if self.config.enable_market_efficiency:
            eff_config = EfficiencyConfig()
            self.market_efficiency = MarketEfficiencyAnalyzer(eff_config)
            logger.info("✓ Market Efficiency Analyzer initialized")

        # Whale Lifecycle Tracker
        if self.config.enable_lifecycle_tracking:
            life_config = LifecycleConfig()
            self.lifecycle_tracker = WhaleLifecycleTracker(life_config)
            logger.info("✓ Whale Lifecycle Tracker initialized")

        # Adaptive Threshold Manager
        if self.config.enable_adaptive_thresholds:
            adapt_config = AdaptiveConfig()
            self.adaptive_thresholds = AdaptiveThresholdManager(adapt_config)
            logger.info("✓ Adaptive Threshold Manager initialized")

        logger.info("All analytics modules initialized successfully")

    async def start(self):
        """Start all analytics modules"""
        if self.is_running:
            return

        logger.info("Starting analytics modules...")
        self.is_running = True

        # Start all modules
        if self.performance_metrics:
            await self.performance_metrics.start()

        if self.attribution_analyzer:
            await self.attribution_analyzer.start()

        if self.benchmarking:
            await self.benchmarking.start()

        if self.reporting:
            await self.reporting.start()

        if self.dashboard:
            await self.dashboard.start()

        if self.edge_detection:
            await self.edge_detection.start()

        if self.cusum_decay:
            await self.cusum_decay.start()

        if self.market_efficiency:
            await self.market_efficiency.start()

        if self.lifecycle_tracker:
            await self.lifecycle_tracker.start()

        if self.adaptive_thresholds:
            await self.adaptive_thresholds.start()

        logger.info("All analytics modules started")

    async def stop(self):
        """Stop all analytics modules"""
        logger.info("Stopping analytics modules...")
        self.is_running = False

        # Stop all modules
        if self.performance_metrics:
            await self.performance_metrics.stop()

        if self.attribution_analyzer:
            await self.attribution_analyzer.stop()

        if self.benchmarking:
            await self.benchmarking.stop()

        if self.reporting:
            await self.reporting.stop()

        if self.dashboard:
            await self.dashboard.stop()

        if self.edge_detection:
            await self.edge_detection.stop()

        if self.cusum_decay:
            await self.cusum_decay.stop()

        if self.market_efficiency:
            await self.market_efficiency.stop()

        if self.lifecycle_tracker:
            await self.lifecycle_tracker.stop()

        if self.adaptive_thresholds:
            await self.adaptive_thresholds.stop()

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("All analytics modules stopped")

    def on_trade(self, trade_data: Dict):
        """
        Handle new trade from copy trading engine.
        Converts trade to appropriate format and feeds to all analytics modules.
        """

        # Convert to standard trade format
        trade_id = trade_data.get('trade_id', '')
        whale_address = trade_data.get('trader_address', '')
        market_id = trade_data.get('market_id', '')
        entry_time = trade_data.get('timestamp', datetime.now())
        entry_price = Decimal(str(trade_data.get('price', 0)))
        size = Decimal(str(trade_data.get('size', 0)))
        pnl_usd = Decimal(str(trade_data.get('pnl', 0)))
        is_open = trade_data.get('is_open', True)

        exit_time = trade_data.get('exit_time')
        exit_price = Decimal(str(trade_data.get('exit_price', 0))) if trade_data.get('exit_price') else None

        # Feed to Performance Metrics
        if self.performance_metrics:
            perf_trade = PerfTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                size=size,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.performance_metrics.add_trade(perf_trade)

        # Feed to Attribution Analyzer
        if self.attribution_analyzer:
            attr_trade = AttrTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                topic=trade_data.get('topic', 'unknown'),
                entry_time=entry_time,
                exit_time=exit_time,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.attribution_analyzer.add_trade(attr_trade)

        # Feed to Benchmarking System
        if self.benchmarking:
            bench_trade = BenchTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.benchmarking.add_trade(bench_trade)

        # Feed to Reporting Engine
        if self.reporting:
            report_trade = ReportTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.reporting.add_trade(report_trade)

        # Feed to Dashboard
        if self.dashboard:
            dash_trade = DashTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.dashboard.add_trade(dash_trade)

        # Feed to Edge Detection
        if self.edge_detection:
            edge_trade = EdgeTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.edge_detection.add_trade(edge_trade)

        # Feed to CUSUM Decay Detector
        if self.cusum_decay:
            cusum_trade = CUSUMTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.cusum_decay.add_trade(cusum_trade)

        # Feed to Market Efficiency Analyzer
        if self.market_efficiency:
            eff_trade = EffTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.market_efficiency.add_trade(eff_trade)

        # Feed to Lifecycle Tracker
        if self.lifecycle_tracker:
            life_trade = LifeTrade(
                trade_id=trade_id,
                whale_address=whale_address,
                market_id=market_id,
                entry_time=entry_time,
                exit_time=exit_time,
                pnl_usd=pnl_usd,
                is_open=is_open
            )
            self.lifecycle_tracker.add_trade(life_trade)

        # Feed to Adaptive Thresholds
        if self.adaptive_thresholds:
            thresh_trade = ThreshTrade(
                trade_id=trade_id,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_usd / entry_price * Decimal("100") if entry_price > 0 else Decimal("0"),
                is_open=is_open
            )
            self.adaptive_thresholds.add_trade(thresh_trade)

        logger.debug(f"Trade {trade_id} fed to all analytics modules")

    def get_whale_recommendation(self, whale_address: str) -> Dict:
        """
        Get comprehensive recommendation for a whale.
        Returns allocation multiplier and reasons.
        """
        recommendations = {
            "whale_address": whale_address,
            "allocation_multiplier": Decimal("1.0"),
            "should_copy": True,
            "reasons": []
        }

        # Check edge detection
        if self.edge_detection:
            edge_metrics = self.edge_detection.edge_metrics.get(whale_address)
            if edge_metrics:
                if edge_metrics.edge_status.value in ["minimal", "negative"]:
                    recommendations["should_copy"] = False
                    recommendations["reasons"].append(f"Low edge: {edge_metrics.current_edge:.3f}")

                if edge_metrics.should_disable:
                    recommendations["allocation_multiplier"] = Decimal("0")
                    recommendations["should_copy"] = False
                    recommendations["reasons"].append("Edge detection recommends disable")

        # Check CUSUM decay
        if self.cusum_decay:
            cusum_state = self.cusum_decay.cusum_states.get(whale_address)
            if cusum_state:
                if cusum_state.should_disable:
                    recommendations["allocation_multiplier"] = Decimal("0")
                    recommendations["should_copy"] = False
                    recommendations["reasons"].append("CUSUM decay detected - disable")
                elif cusum_state.should_reduce_allocation:
                    recommendations["allocation_multiplier"] = min(
                        recommendations["allocation_multiplier"],
                        cusum_state.allocation_multiplier
                    )
                    recommendations["reasons"].append(f"CUSUM recommends reduce to {cusum_state.allocation_multiplier:.0%}")

        # Check lifecycle tracker
        if self.lifecycle_tracker:
            lifecycle_status = self.lifecycle_tracker.whale_lifecycles.get(whale_address)
            if lifecycle_status:
                lifecycle_mult = lifecycle_status.allocation_recommendation
                recommendations["allocation_multiplier"] = min(
                    recommendations["allocation_multiplier"],
                    lifecycle_mult
                )

                if lifecycle_status.phase.value in ["declining", "retired"]:
                    recommendations["should_copy"] = False
                    recommendations["reasons"].append(f"Whale in {lifecycle_status.phase.value} phase")
                elif lifecycle_status.phase.value == "hot_streak":
                    recommendations["allocation_multiplier"] = max(
                        recommendations["allocation_multiplier"],
                        Decimal("1.5")
                    )
                    recommendations["reasons"].append("Whale in hot streak - increase allocation")

        # Final decision
        if recommendations["allocation_multiplier"] == Decimal("0"):
            recommendations["should_copy"] = False

        if recommendations["should_copy"] and not recommendations["reasons"]:
            recommendations["reasons"].append("All checks passed")

        return recommendations

    def get_market_recommendation(self, market_id: str) -> Dict:
        """
        Get recommendation for a market.
        Returns whether market is profitable for copying.
        """
        recommendations = {
            "market_id": market_id,
            "should_trade": True,
            "efficiency_level": "unknown",
            "reasons": []
        }

        # Check market efficiency
        if self.market_efficiency:
            metrics = self.market_efficiency.market_metrics.get(market_id)
            if metrics:
                recommendations["efficiency_level"] = metrics.efficiency_level.value

                if not metrics.is_profitable_for_copying:
                    recommendations["should_trade"] = False
                    recommendations["reasons"].append(
                        f"Market too efficient - edge disappears in {metrics.avg_time_to_equilibrium:.1f}h"
                    )
                else:
                    recommendations["reasons"].append(
                        f"Market suitable - edge persists {metrics.avg_time_to_equilibrium:.1f}h"
                    )

        if recommendations["should_trade"] and not recommendations["reasons"]:
            recommendations["reasons"].append("No efficiency data - proceed with caution")

        return recommendations

    def get_current_edge_thresholds(self) -> Dict:
        """Get current adaptive edge thresholds"""
        if self.adaptive_thresholds and self.adaptive_thresholds.current_thresholds:
            t = self.adaptive_thresholds.current_thresholds
            return {
                "min_edge": float(t.min_edge_threshold),
                "good_edge": float(t.good_edge_threshold),
                "excellent_edge": float(t.excellent_edge_threshold),
                "market_regime": t.market_regime.value,
                "volatility": float(t.current_volatility)
            }

        return {
            "min_edge": 0.05,
            "good_edge": 0.10,
            "excellent_edge": 0.15,
            "market_regime": "normal",
            "volatility": 15.0
        }

    async def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "performance_metrics": {},
            "attribution": {},
            "edge_detection": {},
            "lifecycle": {}
        }

        # Performance metrics
        if self.performance_metrics and self.performance_metrics.current_metrics:
            metrics = self.performance_metrics.current_metrics
            summary["performance_metrics"] = {
                "total_return_pct": float(metrics.total_return_pct),
                "sharpe_ratio": float(metrics.sharpe_ratio),
                "sortino_ratio": float(metrics.sortino_ratio),
                "win_rate_pct": float(metrics.win_rate_pct),
                "total_trades": metrics.total_trades
            }

        # Attribution
        if self.attribution_analyzer:
            top_whales = self.attribution_analyzer.get_top_contributors(5)
            summary["attribution"]["top_whales"] = [
                {
                    "whale": attr.segment_value,
                    "pnl": float(attr.total_pnl_usd),
                    "contribution_pct": float(attr.contribution_pct)
                }
                for attr in top_whales
            ]

        # Edge detection
        if self.edge_detection:
            positive_edge_whales = len([
                m for m in self.edge_detection.edge_metrics.values()
                if m.edge_status.value not in ["minimal", "negative"]
            ])
            summary["edge_detection"]["whales_with_positive_edge"] = positive_edge_whales

        # Lifecycle
        if self.lifecycle_tracker:
            by_phase = {}
            for status in self.lifecycle_tracker.whale_lifecycles.values():
                phase = status.phase.value
                by_phase[phase] = by_phase.get(phase, 0) + 1
            summary["lifecycle"]["whales_by_phase"] = by_phase

        return summary

    def print_summary(self):
        """Print comprehensive analytics summary"""
        print("\n" + "=" * 100)
        print("ANALYTICS INTEGRATION SUMMARY")
        print("=" * 100 + "\n")

        # Performance Metrics
        if self.performance_metrics:
            self.performance_metrics.print_metrics_summary()

        # Edge Detection
        if self.edge_detection:
            self.edge_detection.print_edge_summary()

        # CUSUM Decay
        if self.cusum_decay:
            self.cusum_decay.print_cusum_summary()

        # Market Efficiency
        if self.market_efficiency:
            self.market_efficiency.print_efficiency_summary()

        # Lifecycle Tracker
        if self.lifecycle_tracker:
            self.lifecycle_tracker.print_lifecycle_summary()

        # Adaptive Thresholds
        if self.adaptive_thresholds:
            self.adaptive_thresholds.print_threshold_summary()

        print("=" * 100 + "\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = AnalyticsIntegrationConfig()
        integration = AnalyticsIntegration(config)

        await integration.initialize()
        await integration.start()

        # Simulate some trades
        print("Simulating trades...")
        for i in range(50):
            trade_data = {
                "trade_id": f"trade_{i}",
                "trader_address": "0xwhale1" if i % 2 == 0 else "0xwhale2",
                "market_id": f"market_{i % 5}",
                "timestamp": datetime.now() - timedelta(days=30-i),
                "price": 0.50 + (i * 0.01),
                "size": 100 + (i * 10),
                "pnl": 50 if i % 3 != 0 else -30,
                "is_open": False
            }
            integration.on_trade(trade_data)

        # Wait for analytics to process
        await asyncio.sleep(2)

        # Get recommendations
        print("\nWhale Recommendation:")
        rec = integration.get_whale_recommendation("0xwhale1")
        print(f"  Should copy: {rec['should_copy']}")
        print(f"  Allocation: {rec['allocation_multiplier']:.0%}")
        print(f"  Reasons: {', '.join(rec['reasons'])}")

        print("\nMarket Recommendation:")
        market_rec = integration.get_market_recommendation("market_1")
        print(f"  Should trade: {market_rec['should_trade']}")
        print(f"  Efficiency: {market_rec['efficiency_level']}")
        print(f"  Reasons: {', '.join(market_rec['reasons'])}")

        print("\nCurrent Edge Thresholds:")
        thresholds = integration.get_current_edge_thresholds()
        print(f"  Min edge: {thresholds['min_edge']:.3f}")
        print(f"  Good edge: {thresholds['good_edge']:.3f}")
        print(f"  Market regime: {thresholds['market_regime']}")

        # Print summary
        integration.print_summary()

        await integration.stop()
        print("\nAnalytics integration demo complete!")

    asyncio.run(main())
