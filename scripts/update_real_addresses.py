"""
Fetch real wallet addresses from Polymarket leaderboard API and update our database.
Delete any whales we can't match (no real address = can't track trades).
"""

import os
import sys
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def fetch_leaderboard_with_addresses():
    """Fetch full leaderboard from Polymarket API."""
    print("\n🔍 Fetching Polymarket leaderboard...")

    try:
        response = requests.get(
            "https://data-api.polymarket.com/leaderboard",
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0'}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data)} traders on leaderboard")

            # Create username -> address mapping
            username_to_address = {}
            for trader in data:
                username = trader.get('user_name')
                address = trader.get('user_id')
                if username and address:
                    username_to_address[username.lower()] = address

            return username_to_address
        else:
            print(f"❌ API returned status {response.status_code}")
            return {}

    except Exception as e:
        print(f"❌ Error fetching leaderboard: {e}")
        return {}


def update_whale_addresses():
    """Update whale addresses and delete unmatchable whales."""
    print("\n" + "="*80)
    print("🔄 UPDATING WHALE ADDRESSES")
    print("="*80)

    # Fetch leaderboard
    leaderboard = fetch_leaderboard_with_addresses()

    if not leaderboard:
        print("\n❌ Could not fetch leaderboard data. Aborting.")
        return

    print(f"\n📊 Leaderboard has {len(leaderboard)} traders with addresses")

    with Session(engine) as session:
        all_whales = session.query(Whale).all()
        total = len(all_whales)

        print(f"📊 Database has {total} whales to match\n")

        matched = []
        unmatched = []
        updated = []

        for whale in all_whales:
            username = whale.pseudonym
            current_address = whale.address

            if not username:
                print(f"⚠️  Whale {current_address[:8]}... has no username")
                unmatched.append(whale)
                continue

            # Try to find real address
            real_address = leaderboard.get(username.lower())

            if real_address:
                if current_address != real_address:
                    print(f"✅ {username}: {current_address[:8]}... → {real_address[:8]}...")
                    whale.address = real_address
                    updated.append(whale)
                else:
                    print(f"✓  {username}: Already has correct address")
                matched.append(whale)
            else:
                print(f"❌ {username}: Not found on leaderboard")
                unmatched.append(whale)

        # Commit address updates
        session.commit()

        print("\n" + "="*80)
        print("📊 MATCHING SUMMARY")
        print("="*80)
        print(f"✅ Matched: {len(matched)} whales")
        print(f"🔄 Updated addresses: {len(updated)} whales")
        print(f"❌ Unmatched: {len(unmatched)} whales")

        # Delete unmatched whales (can't track without real address)
        if unmatched:
            print(f"\n⚠️  {len(unmatched)} whales cannot be tracked (not on leaderboard)")
            print("   Showing first 20:")
            for whale in unmatched[:20]:
                volume = f"${whale.total_volume:,.0f}" if whale.total_volume else "N/A"
                print(f"   - {whale.pseudonym or 'Unknown'} ({volume})")

            if len(unmatched) > 20:
                print(f"   ... and {len(unmatched) - 20} more")

            delete = input("\n⚠️  Delete unmatched whales? (yes/no): ")
            if delete.lower() == 'yes':
                for whale in unmatched:
                    session.delete(whale)
                session.commit()
                print(f"\n✅ Deleted {len(unmatched)} unmatched whales")
            else:
                print("\n❌ Kept unmatched whales (they won't be trackable)")

        # Final stats
        remaining = session.query(Whale).count()
        print(f"\n" + "="*80)
        print(f"✅ FINAL: {remaining} whales with real, trackable addresses")
        print("="*80)

        return len(matched), len(unmatched), len(updated)


if __name__ == "__main__":
    update_whale_addresses()
