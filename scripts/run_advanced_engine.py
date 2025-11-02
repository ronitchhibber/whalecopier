#!/usr/bin/env python3
"""
Launch the Advanced Copy Trading Engine with all research-based features
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import asyncio
import logging
from copy_trading.advanced_engine import AdvancedCopyTradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    print("=" * 80)
    print(" " * 20 + "🚀 ADVANCED COPY TRADING ENGINE 🚀")
    print("=" * 80)
    print()
    print("Implementing ALL research-based strategies:")
    print("  ✓ 5-Factor Whale Quality Score (WQS)")
    print("  ✓ Bayesian Win-Rate Adjustment")
    print("  ✓ 3-Stage Signal Filtering Pipeline")
    print("  ✓ Adaptive Kelly Position Sizing")
    print("  ✓ Cornish-Fisher Modified VaR")
    print("  ✓ Market Regime Detection (EWMA λ=0.94)")
    print("  ✓ Performance Attribution System")
    print()
    print("Target Performance Metrics:")
    print("  • Sharpe Ratio: 2.07")
    print("  • Max Drawdown: 11.2%")
    print("  • Win Rate: 58.2%")
    print("  • Annual Return: 31%")
    print("  • Calmar Ratio: 2.77")
    print()
    print("=" * 80)
    print()

    # Initialize and start engine
    engine = AdvancedCopyTradingEngine(
        config_path="config/advanced_copy_trading.json"
    )

    try:
        await engine.start()
    except KeyboardInterrupt:
        logger.info("\n⏸️ Shutting down gracefully...")
        await engine.stop()

        # Display final performance
        summary = await engine.get_performance_summary()

        print()
        print("=" * 80)
        print("📊 FINAL PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"Trades Evaluated: {summary['engine_metrics']['trades_evaluated']}")
        print(f"Trades Copied: {summary['engine_metrics']['trades_copied']}")

        if summary['engine_metrics']['trades_evaluated'] > 0:
            copy_rate = (summary['engine_metrics']['trades_copied'] /
                        summary['engine_metrics']['trades_evaluated'] * 100)
            print(f"Copy Rate: {copy_rate:.1f}%")

        print(f"Total P&L: ${summary['portfolio_state']['total_pnl']:.2f}")
        print(f"Current NAV: ${summary['portfolio_state']['nav']:.2f}")

        print()
        print("Filter Rejections:")
        rejections = summary['engine_metrics']['filter_stage_rejections']
        print(f"  Stage 1 (Whale): {rejections['stage1']}")
        print(f"  Stage 2 (Trade/Market): {rejections['stage2']}")
        print(f"  Stage 3 (Portfolio): {rejections['stage3']}")

        print()
        print("Current Market Regime: " + summary['regime'])

        # Show recommendations
        if summary['recommendations']:
            print()
            print("📌 OPTIMIZATION RECOMMENDATIONS:")
            for i, rec in enumerate(summary['recommendations'][:3], 1):
                print(f"{i}. [{rec['priority'].upper()}] {rec['area']}: {rec['recommendation']}")

        print("=" * 80)
        print("✅ Engine stopped successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")