"""
Find Polymarket whales by analyzing Polygon blockchain data directly.
Query CTF Exchange contract for high-volume traders.
"""

import os
import sys
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY', '')

# Polymarket CTF Exchange contract on Polygon
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

engine = create_engine(DATABASE_URL)


def get_top_traders_from_blockchain():
    """
    Query PolygonScan for transactions to CTF Exchange contract.
    Find addresses with highest transaction volume.
    """
    print("\n" + "="*80)
    print("⛓️  ANALYZING POLYGON BLOCKCHAIN DATA")
    print("="*80)

    if not POLYGONSCAN_API_KEY:
        print("\n⚠️  No POLYGONSCAN_API_KEY in .env")
        print("Get free key at: https://polygonscan.com/apis")
        print("Add to .env: POLYGONSCAN_API_KEY=your_key_here")
        return []

    print(f"\n📡 Querying PolygonScan API...")
    print(f"   Contract: {CTF_EXCHANGE_ADDRESS}")

    # Get recent transactions to CTF Exchange
    base_url = "https://api.polygonscan.com/api"

    try:
        # Get normal transactions
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': CTF_EXCHANGE_ADDRESS,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': 10000,  # Max allowed
            'sort': 'desc',
            'apikey': POLYGONSCAN_API_KEY
        }

        response = requests.get(base_url, params=params, timeout=30)
        data = response.json()

        if data['status'] != '1':
            print(f"\n❌ PolygonScan API error: {data.get('message', 'Unknown error')}")
            if 'rate limit' in str(data.get('result', '')).lower():
                print("   Rate limited. Wait a moment and try again.")
            return []

        txs = data['result']
        print(f"✅ Retrieved {len(txs)} recent transactions")

        # Count transactions per address
        address_activity = defaultdict(lambda: {'count': 0, 'volume': 0})

        for tx in txs:
            from_addr = tx['from'].lower()
            to_addr = tx['to'].lower()
            value = int(tx.get('value', 0))

            # Track both senders and receivers
            if from_addr != CTF_EXCHANGE_ADDRESS.lower():
                address_activity[from_addr]['count'] += 1
                address_activity[from_addr]['volume'] += value

            if to_addr != CTF_EXCHANGE_ADDRESS.lower():
                address_activity[to_addr]['count'] += 1
                address_activity[to_addr]['volume'] += value

        # Sort by transaction count
        sorted_addresses = sorted(
            address_activity.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )

        print(f"\n📊 Found {len(sorted_addresses)} unique addresses")

        # Filter for active traders (>10 txs)
        whales = []
        print("\n🐋 Top Traders by Activity:")
        print("-" * 80)

        for i, (address, stats) in enumerate(sorted_addresses[:50], 1):
            if stats['count'] >= 10:  # At least 10 transactions
                checksum_addr = format_address(address)
                whales.append(checksum_addr)
                print(f"{i:2d}. {checksum_addr} - {stats['count']:4d} txs")

        return whales

    except requests.exceptions.Timeout:
        print("❌ Request timeout. PolygonScan may be slow.")
        return []
    except Exception as e:
        print(f"❌ Error querying blockchain: {e}")
        return []


def format_address(address):
    """Format address with proper checksum."""
    from eth_utils import to_checksum_address
    try:
        return to_checksum_address(address)
    except:
        return address


def get_whales_from_dexscreener():
    """Alternative: Check DEXScreener for Polymarket token holders."""
    print("\n" + "="*80)
    print("🔍 CHECKING DEXSCREENER FOR POLYMARKET ACTIVITY")
    print("="*80)

    try:
        # Polymarket's UMA token on Polygon
        url = "https://api.dexscreener.com/latest/dex/search/?q=polymarket"

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []

        data = response.json()
        pairs = data.get('pairs', [])

        print(f"Found {len(pairs)} trading pairs")

        # This won't give us individual traders, but validates the approach
        return []

    except Exception as e:
        print(f"Error: {e}")
        return []


def add_whales_to_db(addresses):
    """Add discovered whale addresses to database."""
    if not addresses:
        print("\n❌ No addresses to add")
        return

    print("\n" + "="*80)
    print(f"💾 ADDING {len(addresses)} WHALES TO DATABASE")
    print("="*80)

    with Session(engine) as session:
        added = 0
        skipped = 0

        for address in addresses:
            try:
                # Check if already exists
                existing = session.query(Whale).filter(Whale.address == address).first()

                if existing:
                    skipped += 1
                    continue

                # Add new whale
                whale = Whale(
                    address=address,
                    pseudonym=f"Whale_{address[:8]}",
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
                session.commit()

                print(f"✅ Added: {address}")
                added += 1

            except Exception as e:
                print(f"❌ Error adding {address}: {e}")
                session.rollback()
                continue

        print(f"\n✅ Added: {added} | Skipped: {skipped}")


def main():
    print("\n" + "="*80)
    print("🐋 WHALE DISCOVERY - BLOCKCHAIN ANALYSIS METHOD")
    print("="*80)

    whales = get_top_traders_from_blockchain()

    if whales:
        add_whales_to_db(whales)
        print(f"\n🎉 Success! Found {len(whales)} active traders")
        print("\nNext steps:")
        print("1. View dashboard: http://localhost:8000/dashboard")
        print("2. Score whales: python3 scripts/score_whales.py")
    else:
        print("\n⚠️  No whales found via blockchain method")
        print("\nAlternatives:")
        print("1. Try Selenium scraping: python3 scripts/scrape_whales_selenium.py")
        print("2. Manual entry: python3 scripts/add_whale_address.py <ADDRESS>")
        print("3. Use confirmed whales: python3 scripts/seed_whales.py")


if __name__ == "__main__":
    main()
