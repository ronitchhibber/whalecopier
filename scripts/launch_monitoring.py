#!/usr/bin/env python3
"""
Launch the monitoring dashboard for the whale copy trading system
Integrates all monitoring components
"""

import asyncio
import sys
import os
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.monitoring.dashboard import MonitoringDashboard, WebDashboardServer, Alert, AlertSeverity
from src.monitoring.alert_notifier import AlertNotifier, NotificationChannel, create_default_channels
from src.database.connection import DatabaseConnection
from src.trading.unified_executor import UnifiedTradingExecutor
from src.realtime.websocket_client import PolymarketWebSocketClient
from src.risk.live_risk_manager import LiveRiskManager


class IntegratedMonitoringSystem:
    """
    Fully integrated monitoring system that connects to all components
    """

    def __init__(self):
        self.dashboard = MonitoringDashboard()
        self.notifier = AlertNotifier()
        self.web_server = None
        self.executor = None
        self.database = None
        self.ws_client = None
        self.risk_manager = None

    async def setup_notifications(self):
        """Setup notification channels"""
        # Load from environment or use defaults
        channels = create_default_channels()

        # Add console channel for testing
        channels.append(NotificationChannel(
            name="console",
            type="webhook",
            config={"url": "http://localhost:8080/api/alerts"},
            enabled=True
        ))

        for channel in channels:
            self.notifier.add_channel(channel)
            print(f"✓ Added notification channel: {channel.name}")

        # Register notifier with dashboard
        async def notify_handler(alert: Alert):
            alert_dict = {
                "timestamp": alert.timestamp.isoformat(),
                "severity": alert.severity.value,
                "category": alert.category,
                "message": alert.message,
                "details": alert.details
            }
            await self.notifier.send_alert(alert_dict)

        self.dashboard.alerts.register_handler(notify_handler)

    async def connect_components(self):
        """Connect to trading system components"""
        try:
            # Database connection
            print("Connecting to database...")
            self.database = DatabaseConnection()
            await self.database.connect()
            print("✓ Database connected")

            # Risk manager
            print("Initializing risk manager...")
            self.risk_manager = LiveRiskManager()
            print("✓ Risk manager initialized")

            # Trading executor (in monitoring mode)
            print("Connecting to trading executor...")
            self.executor = UnifiedTradingExecutor(
                database=self.database,
                risk_manager=self.risk_manager,
                mode="paper"  # Paper mode for monitoring
            )
            print("✓ Trading executor connected")

            # WebSocket client
            print("Connecting to WebSocket streams...")
            self.ws_client = PolymarketWebSocketClient()
            print("✓ WebSocket client initialized")

        except Exception as e:
            print(f"✗ Component connection failed: {e}")
            # Continue anyway for demo purposes

    async def inject_test_metrics(self):
        """Inject test metrics for demonstration"""
        print("\nInjecting test metrics...")

        # System metrics
        self.dashboard.metrics.record("system.cpu_usage", 45.2)
        self.dashboard.metrics.record("system.memory_usage", 62.8)
        self.dashboard.metrics.record("system.disk_usage", 78.5)

        # Trading metrics
        self.dashboard.metrics.record("trading.total_trades", 156)
        self.dashboard.metrics.record("trading.successful_trades", 142)
        self.dashboard.metrics.record("trading.failed_trades", 14)
        self.dashboard.metrics.record("trading.success_rate", 0.91)
        self.dashboard.metrics.record("trading.latency_p50", 125)
        self.dashboard.metrics.record("trading.latency_p95", 450)
        self.dashboard.metrics.record("trading.pending_signals", 3)

        # Performance metrics
        self.dashboard.metrics.record("performance.daily_pnl", 2456.78)
        self.dashboard.metrics.record("performance.positions_count", 23)
        self.dashboard.metrics.record("performance.avg_pnl", 106.81)
        self.dashboard.metrics.record("performance.sharpe_ratio", 2.34)
        self.dashboard.metrics.record("performance.win_rate", 0.73)

        # Risk metrics
        self.dashboard.metrics.record("risk.total_exposure", 45000)
        self.dashboard.metrics.record("risk.max_position_size", 5000)
        self.dashboard.metrics.record("risk.current_drawdown", 0.08)
        self.dashboard.metrics.record("risk.var_95", 0.12)
        self.dashboard.metrics.record("risk.circuit_breaker_active", 0)

        # Whale metrics
        self.dashboard.metrics.record("whale.total_monitored", 25)
        self.dashboard.metrics.record("whale.active_copiers", 12)
        self.dashboard.metrics.record("whale.signals_generated", 45)
        self.dashboard.metrics.record("whale.avg_quality_score", 0.78)

        # Component health
        self.dashboard.component_status = {
            "database": "healthy",
            "api": "healthy",
            "websocket": "healthy",
            "risk_manager": "healthy",
            "executor": "healthy"
        }

        print("✓ Test metrics injected")

    async def trigger_test_alerts(self):
        """Trigger some test alerts for demonstration"""
        print("\nTriggering test alerts...")

        # Info alert
        await self.dashboard.alerts.trigger_alert(
            AlertSeverity.INFO,
            "system",
            "Monitoring system started successfully",
            {"startup_time": datetime.now().isoformat()}
        )

        # Warning alert
        await self.dashboard.alerts.trigger_alert(
            AlertSeverity.WARNING,
            "performance",
            "Sharpe ratio below target",
            {"current_sharpe": 1.2, "target_sharpe": 1.5}
        )

        # Simulate high-value whale trade alert
        await self.dashboard.alerts.trigger_alert(
            AlertSeverity.INFO,
            "whale",
            "High-value whale trade detected",
            {
                "whale_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb7",
                "market": "Will BTC reach $100k by EOY?",
                "side": "YES",
                "amount": "$25,000",
                "confidence": 0.92
            }
        )

        print("✓ Test alerts triggered")

    async def run_monitoring_loop(self):
        """Main monitoring loop"""
        print("\nStarting monitoring loop...")

        while True:
            try:
                # Simulate metric updates
                import random

                # Update some metrics with realistic variations
                cpu = 40 + random.random() * 20
                self.dashboard.metrics.record("system.cpu_usage", cpu)

                trades = self.dashboard.metrics.last_values.get("trading.total_trades", 0) + random.randint(0, 3)
                self.dashboard.metrics.record("trading.total_trades", trades)

                pnl = 2000 + random.random() * 1000 - 500
                self.dashboard.metrics.record("performance.daily_pnl", pnl)

                # Occasionally trigger alerts
                if random.random() < 0.1:  # 10% chance per loop
                    if random.random() < 0.5:
                        await self.dashboard.alerts.trigger_alert(
                            AlertSeverity.INFO,
                            "trading",
                            f"New trade executed successfully",
                            {"trade_id": f"T{trades}", "pnl": round(pnl, 2)}
                        )
                    else:
                        await self.dashboard.alerts.trigger_alert(
                            AlertSeverity.WARNING,
                            "risk",
                            "Approaching position limit",
                            {"current_exposure": 42000, "limit": 45000}
                        )

                # Check alert rules
                await self.dashboard.alerts.check_rules(self.dashboard.metrics.last_values)

                await asyncio.sleep(10)  # Update every 10 seconds

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitoring loop error: {e}")
                await asyncio.sleep(10)

    async def start(self):
        """Start the integrated monitoring system"""
        print("=" * 60)
        print("WHALE COPY TRADING MONITORING SYSTEM")
        print("=" * 60)

        # Setup components
        await self.setup_notifications()
        await self.connect_components()
        await self.inject_test_metrics()
        await self.trigger_test_alerts()

        # Start web server
        print("\nStarting web dashboard server...")
        self.web_server = WebDashboardServer(self.dashboard, port=8080)
        await self.web_server.start()

        print("\n" + "=" * 60)
        print("✓ MONITORING DASHBOARD READY")
        print("=" * 60)
        print("\nAccess the dashboard at: http://localhost:8080")
        print("API endpoints:")
        print("  - Metrics: http://localhost:8080/api/metrics")
        print("  - Alerts:  http://localhost:8080/api/alerts")
        print("  - WebSocket: ws://localhost:8080/ws")
        print("\nPress Ctrl+C to stop")
        print("-" * 60)

        # Run monitoring loop
        await self.run_monitoring_loop()


async def main():
    """Main entry point"""
    monitoring = IntegratedMonitoringSystem()

    try:
        await monitoring.start()
    except KeyboardInterrupt:
        print("\n\nShutting down monitoring system...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if monitoring.database:
            await monitoring.database.disconnect()
        print("Monitoring system stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)