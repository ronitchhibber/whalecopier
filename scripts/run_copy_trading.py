#!/usr/bin/env python3
"""
Run the copy trading engine with the new OrderbookTracker.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_copy_trading():
    """Run the copy trading engine."""
    try:
        # Import here after path setup
        from src.copy_trading.engine import CopyTradingEngine

        logger.info("=" * 80)
        logger.info("🚀 STARTING COPY TRADING ENGINE WITH ORDERBOOK TRACKER")
        logger.info("=" * 80)

        # Create and start the engine
        engine = CopyTradingEngine()

        # Run for a limited time for testing
        logger.info("Running copy trading engine for 2 monitoring cycles (10 minutes)...")

        # Start the engine in the background
        engine_task = asyncio.create_task(engine.start())

        # Wait for 10 minutes (2 cycles)
        await asyncio.sleep(600)

        # Stop the engine
        logger.info("Stopping engine after test period...")
        await engine.stop()

        # Cancel the task
        engine_task.cancel()

    except Exception as e:
        logger.error(f"Error running copy trading engine: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_copy_trading())