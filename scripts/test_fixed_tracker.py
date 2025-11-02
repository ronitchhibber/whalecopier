#!/usr/bin/env python3
"""
Test the fixed copy trading tracker that uses The Graph API.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from copy_trading.tracker_fixed import WhalePositionTrackerFixed

def main():
    print("=" * 80)
    print("🧪 TESTING FIXED COPY TRADING TRACKER")
    print("=" * 80)
    print()

    tracker = WhalePositionTrackerFixed()

    # Test with a known whale address
    test_whale = "0x17db3fcd93ba12d38382a0cade24b200185c5f6d"  # fengdubiying
    print(f"Testing with whale: {test_whale}")
    print()

    # Test fetching whale trades
    print("1. Testing get_whale_trades()...")
    trades = tracker.get_whale_trades(test_whale)

    if trades:
        print(f"✅ Successfully fetched {len(trades)} trades")
        if len(trades) > 0:
            print(f"   Latest trade:")
            print(f"   - Type: {trades[0].get('type')}")
            print(f"   - Market: {trades[0].get('market', {}).get('question', 'N/A')[:60]}...")
            print(f"   - Amount: ${float(trades[0].get('amount', 0) or 0):,.2f}")
    else:
        print("⚠️  No trades found or API error")

    print()
    print("2. Testing detect_new_trades()...")
    new_trades = tracker.detect_new_trades(test_whale)

    if new_trades:
        print(f"✅ Detected {len(new_trades)} new trades")
        for trade in new_trades[:3]:
            print(f"   - {trade['type']} {trade['shares']:.2f} shares @ ${trade['price']:.3f}")
    else:
        print("💤 No new trades detected (this is normal if the whale hasn't traded recently)")

    print()
    print("3. Testing get_whale_stats()...")
    stats = tracker.get_whale_stats(test_whale)

    if stats:
        print(f"✅ Whale statistics:")
        print(f"   - 30d volume: ${stats['total_volume_30d']:,.2f}")
        print(f"   - 30d trades: {stats['total_trades_30d']}")
        print(f"   - Unique markets: {stats['unique_markets_30d']}")
        print(f"   - Avg trade size: ${stats['avg_trade_size']:,.2f}")
        if stats['last_trade_time']:
            print(f"   - Last trade: {stats['last_trade_time']}")
    else:
        print("⚠️  Could not fetch whale stats")

    print()
    print("=" * 80)
    print("✅ TRACKER TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()