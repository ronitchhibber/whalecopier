"""
Aggressive whale discovery - target 1000+ addresses.
Uses expanded API scanning and recursive market exploration.
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


def discover_from_all_markets_paginated():
    """Scan ALL markets with pagination."""
    print("\n" + "="*80)
    print("AGGRESSIVE METHOD: All Markets + Orderbooks")
    print("="*80)

    addresses = set()

    try:
        # Get ALL markets (paginated)
        offset = 0
        limit = 100
        total_markets = 0

        while True:
            print(f"\n📡 Fetching markets (offset={offset})...")
            response = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={'limit': limit, 'offset': offset, 'closed': 'false'},
                timeout=20
            )

            if response.status_code != 200:
                break

            markets = response.json()
            if not markets:
                break

            print(f"✅ Got {len(markets)} markets")
            total_markets += len(markets)

            # For each market, get orderbook
            for i, market in enumerate(markets, 1):
                try:
                    # Get token IDs
                    clob_token_ids = market.get('clobTokenIds', [])

                    for token_id in clob_token_ids:
                        if not token_id:
                            continue

                        # Get orderbook
                        book_response = requests.get(
                            "https://clob.polymarket.com/book",
                            params={'token_id': token_id},
                            timeout=3
                        )

                        if book_response.status_code == 200:
                            book = book_response.json()

                            # Extract all makers
                            for order in book.get('bids', []):
                                maker = order.get('maker')
                                if maker and maker.startswith('0x'):
                                    addresses.add(maker.lower())

                            for order in book.get('asks', []):
                                maker = order.get('maker')
                                if maker and maker.startswith('0x'):
                                    addresses.add(maker.lower())

                        time.sleep(0.1)  # Rate limit

                    if i % 10 == 0:
                        print(f"   Scanned {i}/{len(markets)} markets... Found {len(addresses)} addresses")

                except Exception as e:
                    continue

            offset += limit

            # Stop if we've found enough
            if len(addresses) >= 1000:
                print(f"\n🎉 Reached target! Found {len(addresses)} addresses")
                break

            # Limit total markets to prevent infinite loop
            if total_markets >= 1000:
                print(f"\n⚠️  Reached market limit (1000 markets scanned)")
                break

        print(f"\n✅ Total markets scanned: {total_markets}")
        print(f"✅ Total addresses found: {len(addresses)}")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return list(addresses)


def discover_from_events_recursive():
    """Recursively explore all events and their markets."""
    print("\n" + "="*80)
    print("RECURSIVE METHOD: Events + Markets + Tokens")
    print("="*80)

    addresses = set()

    try:
        offset = 0
        limit = 100

        while True:
            print(f"\n📡 Fetching events (offset={offset})...")
            response = requests.get(
                "https://gamma-api.polymarket.com/events",
                params={'limit': limit, 'offset': offset},
                timeout=15
            )

            if response.status_code != 200:
                break

            events = response.json()
            if not events:
                break

            print(f"✅ Got {len(events)} events")

            for event in events:
                # Get event ID
                event_id = event.get('id')

                # Get all markets for this event
                markets = event.get('markets', [])

                for market in markets:
                    # Extract any addresses from market data
                    for key, value in market.items():
                        if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
                            addresses.add(value.lower())

                    # Get detailed market data
                    market_id = market.get('id')
                    if market_id:
                        try:
                            detail_response = requests.get(
                                f"https://gamma-api.polymarket.com/markets/{market_id}",
                                timeout=5
                            )
                            if detail_response.status_code == 200:
                                details = detail_response.json()

                                # Recursively search for addresses
                                def extract_addresses(obj):
                                    if isinstance(obj, str):
                                        if obj.startswith('0x') and len(obj) == 42:
                                            addresses.add(obj.lower())
                                    elif isinstance(obj, dict):
                                        for v in obj.values():
                                            extract_addresses(v)
                                    elif isinstance(obj, list):
                                        for v in obj:
                                            extract_addresses(v)

                                extract_addresses(details)

                            time.sleep(0.05)
                        except:
                            pass

            print(f"   Found {len(addresses)} addresses so far")

            offset += limit

            if len(addresses) >= 1000:
                break

            if offset >= 500:  # Stop after 500 events
                break

        print(f"\n✅ Total addresses found: {len(addresses)}")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return list(addresses)


def discover_from_historical_markets():
    """Get addresses from closed/historical markets."""
    print("\n" + "="*80)
    print("HISTORICAL METHOD: Closed Markets Analysis")
    print("="*80)

    addresses = set()

    try:
        # Get closed markets
        offset = 0
        limit = 100

        while len(addresses) < 500:
            print(f"\n📊 Fetching closed markets (offset={offset})...")
            response = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={'limit': limit, 'offset': offset, 'closed': 'true'},
                timeout=15
            )

            if response.status_code != 200 or not response.json():
                break

            markets = response.json()
            print(f"✅ Got {len(markets)} closed markets")

            for market in markets:
                # Get orderbook snapshots (might have old orders)
                clob_token_ids = market.get('clobTokenIds', [])

                for token_id in clob_token_ids:
                    if token_id:
                        try:
                            book_response = requests.get(
                                f"https://clob.polymarket.com/book",
                                params={'token_id': token_id},
                                timeout=2
                            )

                            if book_response.status_code == 200:
                                book = book_response.json()

                                for order in book.get('bids', []) + book.get('asks', []):
                                    maker = order.get('maker')
                                    if maker and maker.startswith('0x'):
                                        addresses.add(maker.lower())

                            time.sleep(0.05)
                        except:
                            pass

            print(f"   Found {len(addresses)} addresses")
            offset += limit

            if offset >= 500:
                break

        print(f"\n✅ Total addresses from historical: {len(addresses)}")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return list(addresses)


def add_whales_to_db(addresses):
    """Add discovered addresses to database."""
    print("\n" + "="*80)
    print(f"💾 ADDING {len(addresses)} WHALES TO DATABASE")
    print("="*80)

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

                # Add whale
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

                if i % 100 == 0:
                    session.commit()
                    print(f"   ✅ Batch {i//100}: {added} added, {skipped} skipped")

                added += 1

            except Exception as e:
                session.rollback()
                continue

        session.commit()

        print(f"\n✅ Added: {added} | Skipped: {skipped}")
        return added


def main():
    print("\n" + "="*80)
    print("🚀 AGGRESSIVE WHALE DISCOVERY")
    print("="*80)

    all_addresses = set()

    # Method 1: All markets with pagination
    print("\n[1/3] Scanning all active markets...")
    addresses1 = discover_from_all_markets_paginated()
    all_addresses.update(addresses1)
    print(f"Running total: {len(all_addresses)} addresses")

    if len(all_addresses) < 1000:
        # Method 2: Recursive event exploration
        print("\n[2/3] Recursive event exploration...")
        addresses2 = discover_from_events_recursive()
        all_addresses.update(addresses2)
        print(f"Running total: {len(all_addresses)} addresses")

    if len(all_addresses) < 1000:
        # Method 3: Historical markets
        print("\n[3/3] Historical markets analysis...")
        addresses3 = discover_from_historical_markets()
        all_addresses.update(addresses3)
        print(f"Running total: {len(all_addresses)} addresses")

    # Filter out contracts
    filtered = [addr for addr in all_addresses if addr != '0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e']

    print(f"\n" + "="*80)
    print(f"📊 DISCOVERY SUMMARY")
    print("="*80)
    print(f"Total unique addresses: {len(filtered)}")

    if filtered:
        added = add_whales_to_db(filtered)

        print(f"\n" + "="*80)
        print("🎉 SUCCESS")
        print("="*80)
        print(f"New whales added: {added}")
        print(f"View dashboard: http://localhost:8000/dashboard")

        if added + 111 >= 1000:  # 111 already in DB
            print(f"\n🎯 TARGET REACHED! {added + 111} total whales in database")
        else:
            print(f"\n⚠️  Progress: {added + 111}/1000 whales")
            print("Run again or use manual collection for remaining whales")


if __name__ == "__main__":
    main()
