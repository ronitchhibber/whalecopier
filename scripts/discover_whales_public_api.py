"""
Discover whales using public Polymarket APIs (no authentication required).
Strategy: Find popular markets, extract maker addresses from order books.
"""

import os
import sys
import requests
import time
from collections import defaultdict
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def get_popular_markets():
    """Get popular markets from Gamma API."""
    print("\n📊 Fetching popular markets from Gamma API...")

    try:
        response = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={
                'limit': 50,
                'active': 'true',
                'archived': 'false'
            },
            timeout=15
        )

        if response.status_code != 200:
            print(f"❌ Gamma API returned {response.status_code}")
            return []

        events = response.json()
        markets = []

        for event in events:
            for market in event.get('markets', []):
                token_id = market.get('clobTokenIds', [''])[0]
                if token_id:
                    markets.append({
                        'token_id': token_id,
                        'question': market.get('question', 'Unknown'),
                        'volume': market.get('volume', 0)
                    })

        # Sort by volume
        markets.sort(key=lambda x: float(x.get('volume', 0)), reverse=True)

        print(f"✅ Found {len(markets)} active markets")
        return markets[:30]  # Top 30 by volume

    except Exception as e:
        print(f"❌ Error fetching markets: {e}")
        return []


def extract_traders_from_orderbook(token_id):
    """Extract maker addresses from orderbook."""
    try:
        response = requests.get(
            f"https://clob.polymarket.com/book",
            params={'token_id': token_id},
            timeout=5
        )

        if response.status_code != 200:
            return []

        book = response.json()
        makers = set()

        # Extract from bids
        for order in book.get('bids', [])[:20]:
            maker = order.get('maker', '')
            if maker and maker.startswith('0x'):
                makers.add(maker)

        # Extract from asks
        for order in book.get('asks', [])[:20]:
            maker = order.get('maker', '')
            if maker and maker.startswith('0x'):
                makers.add(maker)

        return list(makers)

    except Exception as e:
        return []


def get_recent_trades_from_market(token_id):
    """Try to get recent trades from a market."""
    try:
        # Try the trades endpoint (may not work without auth)
        response = requests.get(
            f"https://clob.polymarket.com/trades",
            params={'market': token_id},
            timeout=5
        )

        if response.status_code == 200:
            trades = response.json()
            traders = set()

            for trade in trades[:50]:
                maker = trade.get('maker', '')
                taker = trade.get('taker', '')

                if maker and maker.startswith('0x'):
                    traders.add(maker)
                if taker and taker.startswith('0x'):
                    traders.add(taker)

            return list(traders)

        return []

    except:
        return []


def discover_whales():
    """Main whale discovery logic."""
    print("\n" + "="*80)
    print("🐋 WHALE DISCOVERY - PUBLIC API METHOD")
    print("="*80)

    markets = get_popular_markets()

    if not markets:
        print("❌ No markets found")
        return []

    all_traders = defaultdict(int)

    print(f"\n🔍 Analyzing top {len(markets)} markets for active traders...")
    print("-" * 80)

    for i, market in enumerate(markets, 1):
        question = market['question'][:60]
        token_id = market['token_id']

        print(f"\n[{i}/{len(markets)}] {question}...")

        # Method 1: Orderbook makers
        makers = extract_traders_from_orderbook(token_id)
        if makers:
            print(f"   📖 Found {len(makers)} makers in orderbook")
            for maker in makers:
                all_traders[maker] += 1

        # Method 2: Recent trades (may not work without auth)
        traders = get_recent_trades_from_market(token_id)
        if traders:
            print(f"   📈 Found {len(traders)} traders in recent trades")
            for trader in traders:
                all_traders[trader] += 1

        # Rate limiting
        time.sleep(0.3)

    # Sort by frequency (traders appearing in multiple markets)
    sorted_traders = sorted(
        all_traders.items(),
        key=lambda x: x[1],
        reverse=True
    )

    print(f"\n" + "="*80)
    print(f"📊 DISCOVERY RESULTS")
    print("="*80)
    print(f"Total unique traders found: {len(sorted_traders)}")

    if sorted_traders:
        print(f"\n🐋 Top Traders (by market presence):")
        print("-" * 80)

        whales = []
        for i, (address, count) in enumerate(sorted_traders[:100], 1):
            if count >= 2:  # Present in at least 2 markets
                whales.append(address)
                print(f"{i:3d}. {address} - Present in {count} markets")

        return whales
    else:
        return []


def add_whales_to_db(addresses):
    """Add discovered whale addresses to database."""
    if not addresses:
        print("\n❌ No addresses to add")
        return 0

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
                    pseudonym=f"Whale_{address[2:10]}",
                    tier="MEDIUM",
                    quality_score=50.0,
                    total_volume=0.0,
                    total_trades=0,
                    win_rate=0.0,
                    sharpe_ratio=0.0,
                    total_pnl=0.0,
                    is_copying_enabled=True,
                    last_active=datetime.utcnow(),
                    discovered_at=datetime.utcnow()
                )

                session.add(whale)
                session.commit()

                added += 1

            except Exception as e:
                print(f"❌ Error adding {address}: {e}")
                session.rollback()
                continue

        print(f"\n✅ Successfully added: {added} whales")
        print(f"⏭️  Skipped (already exist): {skipped} whales")
        print("="*80)

        return added


def main():
    print("\n" + "="*80)
    print("🎯 WHALE DISCOVERY - NO AUTH REQUIRED")
    print("="*80)
    print("\nStrategy:")
    print("1. Fetch popular markets from Gamma API")
    print("2. Extract maker addresses from order books")
    print("3. Find traders present in multiple markets")
    print("4. Add to database for monitoring")

    whales = discover_whales()

    if whales:
        added = add_whales_to_db(whales)

        if added > 0:
            print(f"\n🎉 SUCCESS! Discovered and added {added} new whales")
            print("\n" + "="*80)
            print("NEXT STEPS")
            print("="*80)
            print("1. View whales: http://localhost:8000/dashboard")
            print("2. Start monitoring: python3 services/ingestion/main.py")
            print("\nNote: These whales need scoring to determine quality.")
            print("      They're currently set to default values.")
        else:
            print("\n⚠️  All discovered whales already in database")
            print("Check dashboard: http://localhost:8000/dashboard")
    else:
        print("\n❌ No whales discovered")
        print("\nTroubleshooting:")
        print("1. Check internet connection")
        print("2. Verify Polymarket APIs are accessible")
        print("3. Try manual method: python3 scripts/add_whale_address.py <ADDRESS>")


if __name__ == "__main__":
    main()
