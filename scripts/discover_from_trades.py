"""
Discover whales from recent CLOB trades

Uses the Polymarket CLOB Data API to find active traders
from recent market trades, then enriches with full history.

This is faster than blockchain analysis and doesn't require API keys.

Run: python scripts/discover_from_trades.py
"""

import asyncio
import json
from collections import defaultdict, Counter
from typing import List, Dict
import httpx


async def discover_traders_from_recent_trades():
    """
    Discover active traders from recent CLOB trades.

    Returns list of unique trader addresses sorted by activity.
    """
    print("\n" + "="*80)
    print("DISCOVERING TRADERS FROM RECENT CLOB TRADES")
    print("="*80)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get recent trades from all markets
        print("\n📡 Fetching recent trades from CLOB...")

        trades_url = "https://data-api.polymarket.com/trades"

        all_traders = Counter()
        trader_volumes = defaultdict(float)

        # Fetch multiple pages of trades
        for page in range(1, 11):  # 10 pages = ~1000 trades
            try:
                response = await client.get(
                    trades_url,
                    params={"limit": 100, "offset": (page-1) * 100}
                )

                if response.status_code != 200:
                    print(f"  ⚠️  Page {page}: Status {response.status_code}")
                    continue

                trades = response.json()

                if not trades:
                    print(f"  ⏹  No more trades on page {page}")
                    break

                # Extract trader addresses
                for trade in trades:
                    # Trades have maker and taker
                    maker = trade.get("maker_address", trade.get("maker", ""))
                    taker = trade.get("taker_address", trade.get("taker", ""))

                    # Calculate trade volume
                    price = float(trade.get("price", 0))
                    size = float(trade.get("size", 0))
                    volume = price * size

                    if maker:
                        all_traders[maker.lower()] += 1
                        trader_volumes[maker.lower()] += volume

                    if taker:
                        all_traders[taker.lower()] += 1
                        trader_volumes[taker.lower()] += volume

                print(f"  ✅ Page {page}: Found {len(trades)} trades ({len(all_traders)} unique traders)")

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Error on page {page}: {e}")

        print(f"\n📊 Discovery Results:")
        print(f"  Total Unique Traders: {len(all_traders)}")
        print(f"  Total Trades Analyzed: {sum(all_traders.values())}")

        # Sort by volume (best indicator of whale status)
        sorted_traders = sorted(
            [(addr, trader_volumes[addr], all_traders[addr]) for addr in all_traders],
            key=lambda x: x[1],  # Sort by volume
            reverse=True
        )

        print(f"\n🐋 Top 20 Traders by Volume:")
        print("-"*80)
        for i, (addr, volume, trades) in enumerate(sorted_traders[:20], 1):
            print(f"{i:2d}. {addr[:10]}...{addr[-6:]} - ${volume:>10,.2f} - {trades:>4} trades")

        # Return top 200 traders
        return [addr for addr, _, _ in sorted_traders[:200]]


async def enrich_trader_sample(address: str) -> Dict:
    """Get a quick profile snapshot of a trader"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"https://data-api.polymarket.com/activity",
                params={"user": address, "limit": 50}
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data:
                return None

            # Extract basic info
            first_entry = data[0]
            pseudonym = first_entry.get("name", first_entry.get("pseudonym", f"{address[:8]}..."))

            # Quick stats from sample
            trades = [a for a in data if a.get("type") in ["buy", "sell"]]
            volume = sum(float(a.get("price", 0)) * float(a.get("shares", 0)) for a in trades)

            return {
                "address": address,
                "pseudonym": pseudonym,
                "sample_volume": volume,
                "sample_trades": len(trades)
            }

        except Exception as e:
            return None


async def main():
    """Main workflow"""

    # Step 1: Discover traders from recent trades
    trader_addresses = await discover_traders_from_recent_trades()

    if not trader_addresses:
        print("\n❌ No traders found")
        return

    # Step 2: Quick enrichment of top 30 traders
    print("\n" + "="*80)
    print("ENRICHING TOP 30 TRADERS")
    print("="*80)

    enriched_traders = []

    for i, address in enumerate(trader_addresses[:30], 1):
        print(f"\n[{i}/30] Checking {address[:10]}...")

        profile = await enrich_trader_sample(address)

        if profile:
            enriched_traders.append(profile)
            print(f"  ✅ {profile['pseudonym']}: ${profile['sample_volume']:,.0f} (from 50 trades sample)")

        await asyncio.sleep(0.3)  # Rate limiting

    # Step 3: Save to file
    output_file = "discovered_whale_addresses.json"

    output_data = {
        "discovered_at": str(asyncio.get_event_loop().time()),
        "total_discovered": len(trader_addresses),
        "enriched_count": len(enriched_traders),
        "all_addresses": trader_addresses,
        "enriched_traders": enriched_traders
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print("\n" + "="*80)
    print("✅ DISCOVERY COMPLETE")
    print("="*80)
    print(f"Saved {len(trader_addresses)} addresses to {output_file}")
    print(f"\nNext step:")
    print(f"  python scripts/discover_whales.py")
    print(f"  (This will analyze all addresses in detail and save qualified whales to DB)")


if __name__ == "__main__":
    asyncio.run(main())
