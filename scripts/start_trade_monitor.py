#!/usr/bin/env python3
"""
Startup script for whale trade monitoring service.

This service runs in the background and checks for new whale trades every 15 minutes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.services.whale_trade_monitor import WhaleTradeMonitor


def main():
    """Main entry point."""
    print("=" * 80)
    print("🚀 WHALE TRADE MONITOR")
    print("=" * 80)
    print()
    print("This service will monitor whale trades every 15 minutes:")
    print("  • Check all enabled whales for new activity")
    print("  • Detect when new trades are made")
    print("  • Update most_recent_trade_at timestamp")
    print("  • Log trade activity in real-time")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Create and run monitor
    monitor = WhaleTradeMonitor(check_interval_minutes=15)

    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        monitor.stop()


if __name__ == "__main__":
    main()
