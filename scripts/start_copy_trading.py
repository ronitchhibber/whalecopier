"""
Start the copy trading engine.
This script launches the main copy trading engine that monitors whale trades
and executes copy trades based on configured rules.
"""

import sys
import os
import asyncio

# Add project root and src to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from copy_trading.engine import CopyTradingEngine


def main():
    """Main entry point."""
    print("\n" + "=" * 80)
    print("🚀 POLYMARKET COPY TRADING SYSTEM")
    print("=" * 80)
    print()
    print("Starting copy trading engine...")
    print("Monitoring 46 profitable whales")
    print("Press Ctrl+C to stop")
    print()

    # Create and start engine
    engine = CopyTradingEngine()

    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        print("\n\n⏹️  Engine stopped by user")
    except Exception as e:
        print(f"\n\n❌ Engine crashed: {e}")
        raise


if __name__ == "__main__":
    main()
