#!/usr/bin/env python3
"""
Test script to run one cycle of the metrics updater and exit.
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.whale_metrics_updater import WhaleMetricsUpdater


async def main():
    """Run one update cycle and exit."""
    print("=" * 80)
    print("🧪 TESTING WHALE METRICS UPDATER")
    print("=" * 80)
    print()

    updater = WhaleMetricsUpdater(update_interval_minutes=15)

    print("Running single update cycle...")
    await updater.update_cycle()

    print()
    print("=" * 80)
    print("✅ Test complete!")
    print("=" * 80)
    print()
    print("Check database to verify metrics were updated.")


if __name__ == "__main__":
    asyncio.run(main())
