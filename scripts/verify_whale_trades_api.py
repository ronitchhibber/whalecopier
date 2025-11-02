"""
Verify whale profiles by checking if we can fetch their trades via Polymarket API.
This is more reliable than HTML scraping.
"""

import os
import sys
import time
import requests
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def check_trades_via_api(username, address):
    """
    Try to fetch trades for a whale using Polymarket CLOB API.
    Returns: (has_trades, trade_count, sample_trade)
    """
    try:
        # Try multiple endpoints
        endpoints = [
            f"https://clob.polymarket.com/trades?maker={address}",
            f"https://clob.polymarket.com/trades?taker={address}",
        ]

        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0'
                })

                if response.status_code == 200:
                    data = response.json()

                    if isinstance(data, list) and len(data) > 0:
                        return True, len(data), data[0]
                    elif isinstance(data, dict) and data.get('data'):
                        trades = data['data']
                        if len(trades) > 0:
                            return True, len(trades), trades[0]

            except Exception as e:
                continue

        # No trades found on any endpoint
        return False, 0, None

    except Exception as e:
        print(f"  ❌ API error for {username}: {e}")
        return None, 0, None


def verify_all_whales_via_api():
    """Verify all whales by checking if their trades are accessible via API."""
    print("\n" + "="*80)
    print("🔍 VERIFYING WHALE TRADES VIA POLYMARKET API")
    print("="*80)

    with Session(engine) as session:
        # Get all whales, ordered by quality
        all_whales = session.query(Whale).order_by(
            desc(Whale.total_volume)
        ).all()

        total = len(all_whales)
        print(f"\nTotal whales to verify: {total}")
        print("\nChecking trade accessibility via API...\n")

        valid_whales = []
        invalid_whales = []
        unknown_whales = []

        for i, whale in enumerate(all_whales, 1):
            username = whale.pseudonym or f"Unknown-{whale.address[:8]}"
            address = whale.address

            print(f"[{i}/{total}] {username} ({address[:8]}...)...", end=" ")

            has_trades, trade_count, sample = check_trades_via_api(username, address)

            if has_trades:
                print(f"✅ {trade_count} trades found")
                valid_whales.append(whale)

            elif has_trades is False:
                print(f"❌ No trades accessible")
                invalid_whales.append(whale)

            else:
                print(f"⚠️  API error")
                unknown_whales.append(whale)

            # Rate limiting
            time.sleep(0.3)

        print("\n" + "="*80)
        print("📊 VERIFICATION SUMMARY")
        print("="*80)
        print(f"✅ Valid (trades accessible): {len(valid_whales)}")
        print(f"❌ Invalid (no trades found): {len(invalid_whales)}")
        print(f"⚠️  Unknown (API errors): {len(unknown_whales)}")

        # Show some invalid whales for inspection
        if invalid_whales:
            print(f"\n⚠️  Whales without accessible trades:")
            for whale in invalid_whales[:20]:
                print(f"   - {whale.pseudonym or 'Unknown'} (${whale.total_volume:,.0f} volume)")

        # Show decision point
        if invalid_whales:
            print(f"\n⚠️  {len(invalid_whales)} whales don't have accessible trades via API")
            print("   This likely means:")
            print("   1. The address is incorrect/pseudonymous")
            print("   2. They haven't traded recently")
            print("   3. API permissions issue")

        return len(valid_whales), len(invalid_whales), len(unknown_whales)


if __name__ == "__main__":
    verify_all_whales_via_api()
