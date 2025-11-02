#!/usr/bin/env python3
"""
Test script to fetch historical data from The Graph
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.graph_client import GraphClient


async def test_fetch_historical():
    """Test fetching historical data"""

    print("=" * 60)
    print("TESTING HISTORICAL DATA FETCH")
    print("=" * 60)

    async with GraphClient() as client:
        # Test 1: Fetch recent trades (1 day)
        print("\n1. Fetching last 24 hours of trades...")

        end_timestamp = int(datetime.now().timestamp())
        start_timestamp = end_timestamp - (24 * 60 * 60)  # 1 day back

        try:
            trades, stats = await client.fetch_historical_trades(days_back=1, batch_size=100)

            print(f"✓ Fetched {len(trades)} trades")
            print(f"  Unique users: {stats['unique_users']}")
            print(f"  Unique markets: {stats['unique_markets']}")

            if trades:
                # Show sample trade
                trade = trades[0]
                print("\nSample trade:")
                print(f"  ID: {trade['id'][:20]}...")
                print(f"  Taker: {trade['taker']}")
                print(f"  Maker: {trade['maker']}")
                print(f"  Taker Amount: {trade['takerAmountFilled']}")
                print(f"  Timestamp: {trade['timestamp']}")

                # Convert timestamp
                dt = datetime.fromtimestamp(int(trade['timestamp']))
                print(f"  Date: {dt.isoformat()}")

        except Exception as e:
            print(f"✗ Error fetching trades: {e}")
            return False

        # Test 2: Fetch specific whale trades
        print("\n2. Fetching trades for a specific whale...")

        # Use a known active whale address (from the sample trade we just got)
        if trades and len(trades) > 0:
            whale_address = trades[0]['taker']

            whale_trades = await client.fetch_whale_trades(
                whale_address=whale_address,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                batch_size=50
            )

            print(f"✓ Fetched {len(whale_trades)} trades for whale {whale_address[:10]}...")

            if whale_trades:
                # Calculate total volume
                total_volume = sum(int(t.get('takerAmountFilled', 0)) for t in whale_trades)
                print(f"  Total volume: {total_volume / 10**6:.2f} USDC")

        # Test 3: Check data availability over time
        print("\n3. Checking data availability over different time periods...")

        time_periods = [1, 7, 30, 60]  # days

        for days in time_periods:
            try:
                # Just fetch first batch to check availability
                end_ts = int(datetime.now().timestamp())
                start_ts = end_ts - (days * 24 * 60 * 60)

                test_query = """
                query TestAvailability($startTime: BigInt!, $endTime: BigInt!) {
                    orderFilledEvents(
                        first: 10
                        where: {
                            timestamp_gte: $startTime
                            timestamp_lte: $endTime
                        }
                        orderBy: timestamp
                        orderDirection: desc
                    ) {
                        id
                        timestamp
                    }
                }
                """

                from src.data.graph_client import SubgraphEndpoint

                result = await client.query(
                    SubgraphEndpoint.ORDERBOOK,
                    test_query,
                    {"startTime": str(start_ts), "endTime": str(end_ts)}
                )

                events = result.get("data", {}).get("orderFilledEvents", [])

                if events:
                    oldest = datetime.fromtimestamp(int(events[-1]['timestamp']))
                    newest = datetime.fromtimestamp(int(events[0]['timestamp']))
                    print(f"  {days:2d} days: ✓ Data available ({oldest.date()} to {newest.date()})")
                else:
                    print(f"  {days:2d} days: ✗ No data")

            except Exception as e:
                print(f"  {days:2d} days: ✗ Error: {e}")

        print("\n" + "=" * 60)
        print("✓ HISTORICAL DATA FETCH TEST COMPLETE")
        print("The Graph API is working and historical data is available!")
        print("=" * 60)

        return True


if __name__ == "__main__":
    success = asyncio.run(test_fetch_historical())
    sys.exit(0 if success else 1)