"""
System Manager - Controls all background services.

This manages:
1. Trade Monitor (every 15 minutes)
2. Metrics Updater (every 6 hours)

Can be started/stopped via API endpoints.
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional

from whale_trade_monitor import WhaleTradeMonitor
from whale_metrics_updater import WhaleMetricsUpdater

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemManager:
    """
    Manages all background monitoring services.
    """

    def __init__(self):
        self.trade_monitor = WhaleTradeMonitor(check_interval_minutes=5)
        self.metrics_updater = WhaleMetricsUpdater(update_interval_minutes=360)

        self.trade_monitor_thread: Optional[threading.Thread] = None
        self.metrics_updater_thread: Optional[threading.Thread] = None

        self.running = False
        self.started_at: Optional[datetime] = None

    def start(self):
        """Start all monitoring services."""
        if self.running:
            logger.warning("System already running")
            return False

        logger.info("🚀 Starting Whale Monitoring System...")

        self.running = True
        self.started_at = datetime.utcnow()

        # Start trade monitor in separate thread
        self.trade_monitor_thread = threading.Thread(
            target=self._run_trade_monitor,
            daemon=True,
            name="TradeMonitor"
        )
        self.trade_monitor_thread.start()
        logger.info("✅ Trade Monitor started (checks every 5 minutes)")

        # Start metrics updater in separate thread
        self.metrics_updater_thread = threading.Thread(
            target=self._run_metrics_updater,
            daemon=True,
            name="MetricsUpdater"
        )
        self.metrics_updater_thread.start()
        logger.info("✅ Metrics Updater started (updates every 6 hours)")

        logger.info("🎯 System is now monitoring whales!")
        return True

    def stop(self):
        """Stop all monitoring services."""
        if not self.running:
            logger.warning("System not running")
            return False

        logger.info("⏹️  Stopping Whale Monitoring System...")

        self.running = False

        # Stop services
        self.trade_monitor.stop()
        self.metrics_updater.stop()

        logger.info("✅ System stopped")
        return True

    def _run_trade_monitor(self):
        """Run trade monitor in async event loop."""
        try:
            asyncio.run(self.trade_monitor.run())
        except Exception as e:
            logger.error(f"Trade monitor error: {e}")
            self.running = False

    def _run_metrics_updater(self):
        """Run metrics updater in async event loop."""
        try:
            asyncio.run(self.metrics_updater.run())
        except Exception as e:
            logger.error(f"Metrics updater error: {e}")
            self.running = False

    def get_status(self):
        """Get current system status."""
        return {
            "running": self.running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "trade_monitor_active": self.trade_monitor_thread and self.trade_monitor_thread.is_alive() if self.trade_monitor_thread else False,
            "metrics_updater_active": self.metrics_updater_thread and self.metrics_updater_thread.is_alive() if self.metrics_updater_thread else False,
            "uptime_seconds": (datetime.utcnow() - self.started_at).total_seconds() if self.started_at and self.running else 0
        }


# Global system manager instance
system_manager = SystemManager()
