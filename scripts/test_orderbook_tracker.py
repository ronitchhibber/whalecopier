#!/usr/bin/env python3
"""
Test the orderbook-based copy trading tracker.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from copy_trading.orderbook_tracker import OrderbookTracker

def main():
    print("=" * 80)
    print("🧪 TESTING ORDERBOOK TRACKER")
    print("=" * 80)
    print()

    tracker = OrderbookTracker()

    # Test with a known whale address
    test_whale = "0x17db3fcd93ba12d38382a0cade24b200185c5f6d"  # fengdubiying
    print(f"Testing with whale: {test_whale}")
    print()

    # Test fetching whale orders
    print("1. Testing get_whale_orders()...")
    orders = tracker.get_whale_orders(test_whale)

    if orders:
        print(f"✅ Successfully fetched {len(orders)} orders")
        if len(orders) > 0:
            order = orders[0]
            print(f"   Latest order:")
            print(f"   - Timestamp: {order.get('timestamp')}")
            print(f"   - Taker amount: {float(order.get('takerAmountFilled', 0))/1e6:.2f}")
            print(f"   - Maker amount: {float(order.get('makerAmountFilled', 0))/1e6:.2f}")
            print(f"   - Tx hash: {order.get('transactionHash', '')[:20]}...")
    else:
        print("⚠️  No orders found or API error")

    print()
    print("2. Testing detect_new_trades()...")
    new_trades = tracker.detect_new_trades(test_whale)

    if new_trades:
        print(f"✅ Detected {len(new_trades)} new trades")
        for trade in new_trades[:3]:
            print(f"   - {trade['type']} {trade['shares']:.2f} shares @ ${trade['price']:.3f} = ${trade['amount']:.2f}")
    else:
        print("💤 No new trades detected (this is normal if the whale hasn't traded recently)")

    print()
    print("3. Testing get_recent_volume()...")
    volume = tracker.get_recent_volume(test_whale, days=30)
    print(f"   30-day volume: ${volume:,.2f}")

    print()
    print("=" * 80)
    print("✅ ORDERBOOK TRACKER TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()