#!/usr/bin/env python3
"""
Startup script for whale metrics updater service.

This service runs in the background and updates whale 24h metrics every 15 minutes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.services.whale_metrics_updater import WhaleMetricsUpdater


def main():
    """Main entry point."""
    print("=" * 80)
    print("🚀 WHALE METRICS UPDATER")
    print("=" * 80)
    print()
    print("This service will update whale 24h metrics every 15 minutes:")
    print("  • trades_24h - Count of trades in last 24 hours")
    print("  • volume_24h - Dollar volume in last 24 hours")
    print("  • active_trades - Current number of active positions")
    print("  • most_recent_trade_at - Timestamp of most recent trade")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Create and run updater
    updater = WhaleMetricsUpdater(update_interval_minutes=15)

    try:
        asyncio.run(updater.run())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        updater.stop()


if __name__ == "__main__":
    main()
