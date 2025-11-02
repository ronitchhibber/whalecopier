"""
Bulk import whale addresses from CSV file.
This is the fastest way to add 1000+ whales.
"""

import os
import sys
import csv
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def import_from_csv(csv_file="whale_addresses.csv"):
    """Import whales from CSV file."""
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        print("\nCreate a CSV file with this format:")
        print("address")
        print("0x1234567890123456789012345678901234567890")
        print("0x0987654321098765432109876543210987654321")
        return 0

    print("\n" + "="*80)
    print(f"📥 BULK IMPORT FROM {csv_file}")
    print("="*80)

    addresses = []

    # Read CSV
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)

        # Handle different CSV formats
        for row in reader:
            # Try to get address from various possible column names
            address = (
                row.get('address') or
                row.get('Address') or
                row.get('wallet') or
                row.get('Wallet') or
                list(row.values())[0]  # First column if no header match
            )

            if address and address.startswith('0x') and len(address) == 42:
                addresses.append(address.lower())

    print(f"✅ Read {len(addresses)} addresses from CSV")

    # Import to database
    with Session(engine) as session:
        added = 0
        skipped = 0

        for i, address in enumerate(addresses, 1):
            try:
                # Check if exists
                existing = session.query(Whale).filter(Whale.address == address).first()

                if existing:
                    skipped += 1
                    continue

                # Checksum
                from eth_utils import to_checksum_address
                try:
                    checksummed = to_checksum_address(address)
                except:
                    checksummed = address

                # Create whale
                whale = Whale(
                    address=checksummed,
                    pseudonym=f"Whale_{checksummed[2:10]}",
                    tier="MEDIUM",
                    quality_score=50.0,
                    total_volume=0.0,
                    total_trades=0,
                    win_rate=0.0,
                    sharpe_ratio=0.0,
                    total_pnl=0.0,
                    is_copying_enabled=True,
                    last_active=datetime.utcnow()
                )

                session.add(whale)

                # Commit in batches
                if i % 100 == 0:
                    session.commit()
                    print(f"   ✅ Batch {i//100}: {added} added, {skipped} skipped")

                added += 1

            except Exception as e:
                session.rollback()
                print(f"   ❌ Error: {address} - {e}")
                continue

        session.commit()

        print(f"\n" + "="*80)
        print(f"✅ Successfully added: {added} whales")
        print(f"⏭️  Skipped (already exist): {skipped} whales")
        print("="*80)

        # Show total count
        total = session.query(Whale).count()
        print(f"\n📊 Total whales in database: {total}")

        if total >= 1000:
            print("🎯 TARGET REACHED: 1000+ whales!")
        else:
            print(f"📈 Progress: {total}/1000 whales")

        return added


def create_template_csv():
    """Create a template CSV file."""
    template_file = "whale_addresses_template.csv"

    with open(template_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['address'])

        # Add example addresses (these are placeholders)
        writer.writerow(['# Add wallet addresses below (one per line)'])
        writer.writerow(['# Get addresses from https://polymarket.com/leaderboard'])
        writer.writerow(['# Click each trader → copy address from profile URL'])

    print(f"✅ Created template: {template_file}")
    print("\nNext steps:")
    print("1. Rename to whale_addresses.csv")
    print("2. Add addresses from https://polymarket.com/leaderboard")
    print("3. Run: python3 scripts/bulk_import_whales.py")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Bulk import whale addresses')
    parser.add_argument('--csv', default='whale_addresses.csv', help='CSV file to import')
    parser.add_argument('--template', action='store_true', help='Create template CSV')

    args = parser.parse_args()

    if args.template:
        create_template_csv()
    else:
        added = import_from_csv(args.csv)

        if added > 0:
            print(f"\n🎉 Import complete!")
            print(f"View dashboard: http://localhost:8000/dashboard")


if __name__ == "__main__":
    main()
