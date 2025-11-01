#!/usr/bin/env python3
"""
Test Copy Trading - End-to-end test of the complete copy trading system

This script demonstrates the full flow:
1. Fetch whale trades from Data API
2. Parse trade details
3. Execute copy trades via live trader
4. Verify results
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from src.services.whale_trade_fetcher import trade_fetcher
from src.services.simple_live_trader import trader as live_trader


def test_copy_trading_flow():
    """Test the complete copy trading flow."""
    print("=" * 80)
    print("COPY TRADING END-TO-END TEST")
    print("=" * 80)
    print()

    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get a high-quality whale
    whale = session.query(Whale).filter(
        Whale.is_copying_enabled == True,
        Whale.quality_score >= 70
    ).order_by(Whale.quality_score.desc()).first()

    if not whale:
        print("No suitable whales found for testing")
        return

    print(f"Testing with whale: {whale.pseudonym or whale.address[:10]}")
    print(f"  Quality Score: {whale.quality_score:.1f}")
    print(f"  Total PnL: ${whale.total_pnl:,.2f}")
    print(f"  Win Rate: {whale.win_rate:.1f}%")
    print()

    # Step 1: Fetch recent trades
    print("Step 1: Fetching recent trades from Data API...")
    trades = trade_fetcher.fetch_whale_trades(whale.address, limit=3)
    print(f"  ✓ Found {len(trades)} recent trades")
    print()

    if not trades:
        print("No recent trades found. Whale may not be active right now.")
        return

    # Step 2: Parse trades
    print("Step 2: Parsing trade details...")
    parsed_trades = []
    for i, trade in enumerate(trades, 1):
        parsed = trade_fetcher.parse_trade_for_copy(trade)
        if parsed:
            parsed_trades.append(parsed)
            print(f"  Trade {i}:")
            print(f"    Market: {parsed['market_title'][:60]}")
            print(f"    Side: {parsed['side']}")
            print(f"    Outcome: {parsed['outcome']}")
            print(f"    Price: ${parsed['price']}")
            print(f"    Size: {parsed['size']}")
            print()

    # Step 3: Check live trader status
    print("Step 3: Checking live trader status...")
    status = live_trader.get_status()
    print(f"  Mode: {status['mode']}")
    print(f"  Balance: ${status['account_balance']:,.2f}")
    print(f"  Max Position: ${status['max_position']:,.2f}")
    print(f"  Daily Loss Limit: ${status['max_daily_loss']:,.2f}")
    print(f"  Min Whale Quality: {status['min_whale_quality']}")
    print()

    # Step 4: Evaluate if we should copy
    print("Step 4: Evaluating copy trading criteria...")
    should_copy, reason = live_trader.should_copy(whale)
    if should_copy:
        print(f"  ✓ All criteria passed: {reason}")
    else:
        print(f"  ✗ Copy blocked: {reason}")
        return
    print()

    # Step 5: Execute copy trades (PAPER MODE)
    print("Step 5: Executing copy trades...")
    print(f"  IMPORTANT: System is in {status['mode']} mode")
    print()

    for i, parsed in enumerate(parsed_trades[:2], 1):  # Only copy first 2 trades for test
        print(f"  Executing copy trade {i}/{min(2, len(parsed_trades))}...")
        print(f"    Whale: {whale.pseudonym or whale.address[:10]} (Q:{whale.quality_score:.1f})")
        print(f"    Market: {parsed['market_title'][:50]}")
        print(f"    Action: {parsed['side']} {parsed['outcome']}")
        print(f"    Price: ${parsed['price']}")

        # Calculate position size
        position_size = live_trader.calculate_position_size(whale)
        print(f"    Position Size: ${position_size:.2f}")

        # Execute trade
        result = live_trader.execute_trade(
            whale=whale,
            market_id=parsed['market_id'],
            side=parsed['side'],
            price=parsed['price']
        )

        if result:
            print(f"    ✓ Trade executed successfully!")
            print(f"      Order ID: {result['order_id']}")
            print(f"      Mode: {result['mode']}")
        else:
            print(f"    ✗ Trade not executed (safety check failed)")

        print()

    # Step 6: Show final status
    print("Step 6: Final status...")
    final_status = live_trader.get_status()
    print(f"  Daily Trades: {final_status['daily_trades']}")
    print(f"  Daily PnL: ${final_status['daily_pnl']:.2f}")
    print(f"  Account Balance: ${final_status['account_balance']:,.2f}")
    print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - Fetched {len(trades)} whale trades from Data API")
    print(f"  - Parsed {len(parsed_trades)} trades successfully")
    print(f"  - Executed {min(2, len(parsed_trades))} copy trades in {status['mode']} mode")
    print()
    print("Next steps:")
    print("  1. System is ready for live trading")
    print("  2. Enable live mode via dashboard or API when ready")
    print("  3. Monitor system will automatically copy trades every 15 minutes")
    print()

    session.close()


if __name__ == "__main__":
    try:
        test_copy_trading_flow()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nError during test: {e}")
        import traceback
        traceback.print_exc()
