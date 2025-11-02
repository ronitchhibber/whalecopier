"""
Import top 1000 whale addresses to the database.
Filter for unique addresses and import them with their stats.
"""

import json
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Whale
import requests
from datetime import datetime
import time

# Database setup
DATABASE_URL = "postgresql://trader:trader_password@localhost:5432/polymarket_trader"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def load_all_addresses():
    """Load all discovered addresses."""
    all_addresses = set()

    files = [
        'whale_addresses_discovered.json',
        'sampled_whale_addresses.json',
        'etherscan_whale_addresses_optimized.json',
        'etherscan_ctf_whale_addresses.json'
    ]

    for fname in files:
        try:
            with open(fname, 'r') as f:
                data = json.load(f)
                addresses = data.get('addresses', [])
                all_addresses.update(addresses)
                print(f"  ✅ Loaded {len(addresses)} from {fname}")
        except FileNotFoundError:
            print(f"  ⏭️  Skipped {fname} (not found)")

    return list(all_addresses)


def get_whale_stats(address):
    """Fetch whale stats from Polymarket leaderboard API."""
    try:
        url = f"https://gamma-api.polymarket.com/profile/{address}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Extract stats
            volume = float(data.get('totalVolume', 0) or 0)
            pnl = float(data.get('pnl', 0) or 0)
            markets = int(data.get('marketsTraded', 0) or 0)

            return {
                'volume': volume,
                'pnl': pnl,
                'markets': markets,
                'is_whale': volume >= 50000  # $50K threshold
            }
        else:
            return None

    except Exception as e:
        return None


def import_whales_to_database(addresses, target=1000):
    """
    Import whales to database.
    Prioritize by validating against Polymarket API and selecting top performers.
    """
    print("\n" + "=" * 80)
    print(f"📥 IMPORTING TOP {target} WHALES TO DATABASE")
    print("=" * 80)
    print(f"Total addresses to process: {len(addresses):,}")
    print()

    session = Session()

    # Get existing whales
    existing = session.query(Whale).all()
    existing_addresses = {w.address.lower() for w in existing}
    print(f"✅ Found {len(existing_addresses)} whales already in database")

    # Filter out existing
    new_addresses = [a for a in addresses if a.lower() not in existing_addresses]
    print(f"📊 New addresses to import: {len(new_addresses):,}\n")

    if len(new_addresses) == 0:
        print("✅ No new whales to import (all addresses already in database)")
        session.close()
        return

    # Limit to target
    if len(new_addresses) > target:
        print(f"⚠️  Limiting to {target} addresses (out of {len(new_addresses):,})")
        new_addresses = new_addresses[:target]

    # Import addresses
    print(f"\n{'=' * 80}")
    print(f"📝 Importing {len(new_addresses)} whales...")
    print(f"{'=' * 80}\n")

    imported = 0
    skipped = 0
    verified_whales = 0

    for i, address in enumerate(new_addresses):
        try:
            # Fetch stats
            stats = get_whale_stats(address)

            if stats:
                volume = stats['volume']
                pnl = stats['pnl']
                markets = stats['markets']
                is_whale = stats['is_whale']

                status = "🐋" if is_whale else "📊"

                if is_whale:
                    verified_whales += 1

                # Create whale entry
                whale = Whale(
                    address=address.lower(),
                    total_volume=volume,
                    total_trades=0,  # Will be updated later
                    first_seen=datetime.utcnow(),
                    last_active=datetime.utcnow()
                )

                session.add(whale)
                imported += 1

                if (i + 1) % 10 == 0:
                    session.commit()
                    print(f"  [{i+1}/{len(new_addresses)}] {status} {address[:10]}... (vol: ${volume:,.0f}, pnl: ${pnl:,.0f}) | Verified whales: {verified_whales}")

            else:
                # No stats available, import anyway with zero stats
                whale = Whale(
                    address=address.lower(),
                    total_volume=0,
                    total_trades=0,
                    first_seen=datetime.utcnow(),
                    last_active=datetime.utcnow()
                )
                session.add(whale)
                imported += 1
                skipped += 1

                if (i + 1) % 10 == 0:
                    session.commit()
                    print(f"  [{i+1}/{len(new_addresses)}] ⏭️  {address[:10]}... (no stats) | Verified whales: {verified_whales}")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            print(f"  ❌ Error importing {address}: {e}")
            continue

    # Final commit
    session.commit()

    print("\n" + "=" * 80)
    print("✅ IMPORT COMPLETE")
    print("=" * 80)
    print(f"Imported: {imported} addresses")
    print(f"Verified whales (>$50K): {verified_whales}")
    print(f"Pending verification: {skipped}")

    # Final count
    total_whales = session.query(Whale).count()
    print(f"\n🐋 Total whales in database: {total_whales}")

    session.close()

    return imported


def main():
    print("\n" + "=" * 80)
    print("🐋 WHALE IMPORT PROCESS")
    print("=" * 80)

    # Load addresses
    print("\n📂 Loading discovered addresses...")
    addresses = load_all_addresses()
    print(f"\n✅ Total unique addresses: {len(addresses):,}")

    # Import to database
    import_whales_to_database(addresses, target=1000)

    print("\n✅ Process complete!")


if __name__ == "__main__":
    main()
