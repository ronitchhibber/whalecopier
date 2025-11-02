"""
Simple test script to verify Polymarket API whale data enrichment.
Tests the Data API without requiring database or infrastructure.

Run: python scripts/test_whale_api.py
"""

import asyncio
import httpx


async def test_whale_api():
    """Test fetching whale data from Polymarket Data API"""

    # Test with confirmed Fredi9999 address
    test_address = "0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf"

    print("\n" + "="*80)
    print("POLYMARKET API TEST - Whale Data Enrichment")
    print("="*80)
    print(f"\nTesting with address: {test_address}")
    print(f"Whale: Fredi9999 (Théo cluster)")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n📡 Fetching data from Polymarket Data API...")

            response = await client.get(
                "https://data-api.polymarket.com/activity",
                params={"user": test_address, "limit": 10}
            )

            if response.status_code != 200:
                print(f"❌ API returned status {response.status_code}")
                return

            data = response.json()

            if not data or len(data) == 0:
                print("⚠️  No activity data returned")
                return

            print(f"✅ Received {len(data)} activity records\n")

            # Extract profile
            first_entry = data[0]
            pseudonym = first_entry.get("name", first_entry.get("pseudonym", "Unknown"))

            print("="*80)
            print(f"WHALE PROFILE")
            print("="*80)
            print(f"Pseudonym: {pseudonym}")
            print(f"Address: {test_address}")

            # Calculate stats
            total_volume = 0
            trades_count = 0
            buy_count = 0
            sell_count = 0

            print(f"\nRecent Activity (last {len(data)} events):")
            print("-"*80)

            for i, activity in enumerate(data[:5], 1):  # Show first 5
                activity_type = activity.get("type", "unknown")
                market = activity.get("market", {}).get("question", "Unknown market")[:50]
                price = float(activity.get("price", 0))
                shares = float(activity.get("shares", 0))
                value = price * shares
                timestamp = activity.get("timestamp", "")

                if activity_type in ["buy", "sell"]:
                    trades_count += 1
                    total_volume += value
                    if activity_type == "buy":
                        buy_count += 1
                    else:
                        sell_count += 1

                print(f"{i}. [{activity_type.upper()}] {market}...")
                print(f"   Price: ${price:.2f} | Shares: {shares:.0f} | Value: ${value:.2f}")
                print(f"   Time: {timestamp}")

            print("\n" + "="*80)
            print("TRADING STATISTICS")
            print("="*80)
            print(f"Total Volume (from sample): ${total_volume:,.2f}")
            print(f"Total Trades: {trades_count}")
            print(f"Buy Orders: {buy_count}")
            print(f"Sell Orders: {sell_count}")

            print("\n✅ API test successful! Whale data enrichment is working.")
            print("\nYou can now run:")
            print("  1. python scripts/seed_whales.py - Seed database with whales")
            print("  2. python services/ingestion/main.py - Start real-time monitoring")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_whale_api())
