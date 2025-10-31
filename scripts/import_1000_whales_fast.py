"""
Fast import of 1000 whale addresses to database without API validation.
Validation will happen asynchronously via the tracking system.
"""

import json
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
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
                print(f"  ✅ Loaded {len(addresses):,} from {fname}")
        except FileNotFoundError:
            print(f"  ⏭️  Skipped {fname} (not found)")

    return list(all_addresses)


def import_whales_fast(addresses, target=1000):
    """
    Fast import of whale addresses without API validation.
    """
    print("\n" + "=" * 80)
    print(f"⚡ FAST IMPORT: TOP {target} WHALES")
    print("=" * 80)
    print(f"Total addresses: {len(addresses):,}")
    print()

    session = Session()

    # Get existing whales
    existing = session.query(Whale).all()
    existing_addresses = {w.address.lower() for w in existing}
    print(f"✅ Existing whales in database: {len(existing_addresses)}")

    # Filter out existing
    new_addresses = [a for a in addresses if a.lower() not in existing_addresses]
    print(f"📊 New addresses to import: {len(new_addresses):,}\n")

    if len(new_addresses) == 0:
        print("✅ No new whales to import")
        session.close()
        return 0

    # Limit to target
    if len(new_addresses) > target:
        print(f"⚠️  Limiting to {target} addresses\n")
        new_addresses = new_addresses[:target]

    # Import addresses quickly
    print(f"{'=' * 80}")
    print(f"📝 Importing {len(new_addresses)} whales...")
    print(f"{'=' * 80}\n")

    imported = 0
    now = datetime.utcnow()

    for i, address in enumerate(new_addresses):
        try:
            # Create whale entry with minimal data
            # first_seen and last_active will be set automatically by database
            whale = Whale(
                address=address.lower(),
                total_volume=0,  # Will be updated by sync
                total_trades=0   # Will be updated by sync
            )

            session.add(whale)
            imported += 1

            if (i + 1) % 100 == 0:
                session.commit()
                print(f"  [{i+1:4}/{len(new_addresses)}] Imported {i+1} whales...")

        except Exception as e:
            print(f"  ❌ Error importing {address}: {e}")
            continue

    # Final commit
    session.commit()

    print("\n" + "=" * 80)
    print("✅ FAST IMPORT COMPLETE")
    print("=" * 80)
    print(f"Imported: {imported} addresses")

    # Final count
    total_whales = session.query(Whale).count()
    print(f"\n🐋 Total whales in database: {total_whales}")
    print("\n💡 Note: Whale stats will be synced automatically by the tracking system")

    session.close()

    return imported


def main():
    print("\n" + "=" * 80)
    print("🐋 FAST WHALE IMPORT")
    print("=" * 80)

    # Load addresses
    print("\n📂 Loading discovered addresses...")
    addresses = load_all_addresses()
    print(f"\n✅ Total unique addresses: {len(addresses):,}")

    # Import to database
    import_whales_fast(addresses, target=1000)

    print("\n✅ Process complete!")


if __name__ == "__main__":
    main()
