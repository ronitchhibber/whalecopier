"""
Validate that all whale profiles are publicly accessible on Polymarket.
Delete any whales that don't have public profiles or visible trades.
Get real wallet addresses for each whale.
"""

import os
import sys
import time
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def check_profile_public(username):
    """
    Check if a Polymarket profile is publicly accessible.
    Returns: (is_public, real_address, trade_count)
    """
    try:
        # Try Polymarket profile page
        profile_url = f"https://polymarket.com/profile/{username}"
        response = requests.get(profile_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        # Check if profile exists and is public
        if response.status_code == 200:
            content = response.text.lower()

            # Check for indicators that profile is private or doesn't exist
            if 'profile not found' in content or 'user not found' in content:
                return False, None, 0

            # Check for trade history section
            has_trades = 'position' in content or 'trade' in content or 'market' in content

            # Try to extract wallet address from page
            # Look for Ethereum addresses (0x followed by 40 hex chars)
            import re
            addresses = re.findall(r'0x[a-fA-F0-9]{40}', response.text)
            real_address = addresses[0] if addresses else None

            # Estimate trade count from content
            trade_indicators = content.count('position') + content.count('trade')

            return has_trades, real_address, trade_indicators

        elif response.status_code == 404:
            return False, None, 0

        else:
            print(f"  ⚠️  HTTP {response.status_code} for {username}")
            return None, None, 0  # Unknown status

    except requests.exceptions.Timeout:
        print(f"  ⏱️  Timeout checking {username}")
        return None, None, 0
    except Exception as e:
        print(f"  ❌ Error checking {username}: {e}")
        return None, None, 0


def validate_all_whales():
    """Validate all whales and delete those without public profiles."""
    print("\n" + "="*80)
    print("🔍 VALIDATING WHALE PROFILES")
    print("="*80)

    with Session(engine) as session:
        all_whales = session.query(Whale).all()
        total = len(all_whales)

        print(f"\nTotal whales to validate: {total}")
        print("\nChecking each profile on Polymarket...\n")

        valid_whales = []
        invalid_whales = []
        unknown_whales = []

        for i, whale in enumerate(all_whales, 1):
            username = whale.pseudonym or f"Unknown-{whale.address[:8]}"

            print(f"[{i}/{total}] Checking {username}...", end=" ")

            is_public, real_address, trade_count = check_profile_public(username)

            if is_public:
                print(f"✅ Public ({trade_count} trade indicators)")
                valid_whales.append(whale)

                # Update real address if found
                if real_address and real_address != whale.address:
                    whale.address = real_address
                    print(f"      Updated address: {real_address}")

            elif is_public is False:
                print(f"❌ Not public/not found")
                invalid_whales.append(whale)

            else:
                print(f"⚠️  Unknown (network error)")
                unknown_whales.append(whale)

            # Rate limiting
            time.sleep(0.5)

        print("\n" + "="*80)
        print("📊 VALIDATION SUMMARY")
        print("="*80)
        print(f"✅ Valid (public profiles): {len(valid_whales)}")
        print(f"❌ Invalid (not public): {len(invalid_whales)}")
        print(f"⚠️  Unknown (errors): {len(unknown_whales)}")

        # Delete invalid whales
        if invalid_whales:
            print(f"\n⚠️  About to DELETE {len(invalid_whales)} whales with non-public profiles:")
            for whale in invalid_whales[:10]:  # Show first 10
                print(f"   - {whale.pseudonym or whale.address[:8]}")
            if len(invalid_whales) > 10:
                print(f"   ... and {len(invalid_whales) - 10} more")

            confirm = input("\nProceed with deletion? (yes/no): ")
            if confirm.lower() == 'yes':
                for whale in invalid_whales:
                    session.delete(whale)
                session.commit()
                print(f"\n✅ Deleted {len(invalid_whales)} invalid whales")
            else:
                print("\n❌ Deletion cancelled")

        # Show final stats
        remaining = session.query(Whale).count()
        print(f"\n" + "="*80)
        print(f"✅ FINAL STATUS: {remaining} valid whales in database")
        print("="*80)

        return len(valid_whales), len(invalid_whales), len(unknown_whales)


if __name__ == "__main__":
    validate_all_whales()
