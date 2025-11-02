"""
Quick helper to add a whale address to the database

Usage:
  python scripts/add_whale_address.py 0xADDRESS_HERE

This will:
1. Validate the address
2. Fetch data from Polymarket API
3. Calculate stats
4. Add to database with copying enabled
"""

import asyncio
import sys
import os
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.models import Whale, Platform
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')


async def add_whale(address: str):
    """Add a whale address to the database"""

    # Validate address format
    if not address.startswith('0x') or len(address) != 42:
        print(f"❌ Invalid address format: {address}")
        print("   Address must be 42 characters starting with 0x")
        return False

    address = address.lower()

    print(f"\n🐋 Adding whale: {address}")
    print("="*80)

    # Fetch from API
    print("\n📡 Fetching data from Polymarket API...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://data-api.polymarket.com/activity",
                params={"user": address, "limit": 100}
            )

            if response.status_code != 200:
                print(f"❌ API returned status {response.status_code}")
                return False

            data = response.json()

            if not data:
                print(f"❌ No activity found for this address")
                print("   Make sure the address has traded on Polymarket")
                return False

            # Extract info
            first_entry = data[0]
            pseudonym = first_entry.get("name", first_entry.get("pseudonym", f"{address[:8]}..."))

            # Calculate stats
            total_volume = 0
            trades_count = 0

            for activity in data:
                if activity.get("type") in ["buy", "sell"]:
                    trades_count += 1
                    price = float(activity.get("price", 0))
                    shares = float(activity.get("shares", 0))
                    total_volume += price * shares

            print(f"\n✅ Profile Found:")
            print(f"   Pseudonym: {pseudonym}")
            print(f"   Volume: ${total_volume:,.2f}")
            print(f"   Trades: {trades_count}")

            # Add to database
            engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            async with async_session() as session:
                # Check if already exists
                result = await session.execute(
                    select(Whale).where(Whale.address == address)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"\n⚠️  Whale already exists in database!")
                    print(f"   Current copying status: {'ENABLED' if existing.is_copying_enabled else 'DISABLED'}")

                    response = input("\n   Update and enable copying? (y/n): ")
                    if response.lower() != 'y':
                        print("   Skipped.")
                        await engine.dispose()
                        return False

                    # Update
                    existing.pseudonym = pseudonym
                    existing.total_volume = Decimal(str(total_volume))
                    existing.total_trades = trades_count
                    existing.is_copying_enabled = True
                    existing.is_active = True

                    await session.commit()
                    print(f"\n✅ Updated whale: {pseudonym}")

                else:
                    # Create new
                    whale = Whale(
                        address=address,
                        pseudonym=pseudonym,
                        platform=Platform.POLYMARKET,
                        total_volume=Decimal(str(total_volume)),
                        total_trades=trades_count,
                        total_pnl=Decimal("0"),  # Will be calculated by scoring engine
                        win_rate=Decimal("60"),  # Conservative default
                        tier="MEDIUM",
                        quality_score=Decimal("70"),
                        rank=999,
                        is_active=True,
                        is_copying_enabled=True,  # Auto-enable
                        edge_status='active'
                    )

                    session.add(whale)
                    await session.commit()
                    print(f"\n✅ Added whale: {pseudonym}")
                    print(f"   ✓ Copying ENABLED")

            await engine.dispose()

            print("\n" + "="*80)
            print("✅ Success! Whale is now being monitored.")
            print(f"\nTo start ingesting trades:")
            print(f"  python services/ingestion/main.py")

            return True

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    if len(sys.argv) < 2:
        print("\nUsage: python scripts/add_whale_address.py 0xADDRESS")
        print("\nExample:")
        print("  python scripts/add_whale_address.py 0xf705fa045201391d9632b7f3cde06a5e24453ca7")
        print("\nTo add multiple addresses:")
        print("  python scripts/add_whale_address.py 0xADDRESS1 0xADDRESS2 0xADDRESS3")
        sys.exit(1)

    addresses = sys.argv[1:]

    print("\n" + "="*80)
    print(f"ADDING {len(addresses)} WHALE ADDRESS(ES)")
    print("="*80)

    success_count = 0

    for address in addresses:
        result = asyncio.run(add_whale(address))
        if result:
            success_count += 1

    print("\n" + "="*80)
    print(f"✅ Successfully added {success_count}/{len(addresses)} whales")
    print("="*80)


if __name__ == "__main__":
    main()
