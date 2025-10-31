"""
Ultra-aggressive whale discovery with 20 concurrent threads.
Explores every possible data source simultaneously.
"""

import os
import sys
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def scan_markets_batch(offset):
    """Scan a batch of markets."""
    addresses = set()
    try:
        response = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={'limit': 100, 'offset': offset},
            timeout=10
        )

        if response.status_code == 200:
            markets = response.json()

            for market in markets:
                # Extract addresses from all fields
                for key, value in market.items():
                    if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
                        addresses.add(value.lower())

                # Get orderbook for each token
                for token_id in market.get('clobTokenIds', []):
                    if token_id:
                        try:
                            book_resp = requests.get(
                                f"https://clob.polymarket.com/book",
                                params={'token_id': token_id},
                                timeout=2
                            )
                            if book_resp.status_code == 200:
                                book = book_resp.json()
                                for order in book.get('bids', []) + book.get('asks', []):
                                    maker = order.get('maker')
                                    if maker and maker.startswith('0x'):
                                        addresses.add(maker.lower())
                        except:
                            pass

            print(f"  Batch {offset//100}: Found {len(addresses)} addresses from {len(markets)} markets")
            return addresses
    except:
        pass

    return addresses


def scan_events_batch(offset):
    """Scan a batch of events."""
    addresses = set()
    try:
        response = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={'limit': 100, 'offset': offset},
            timeout=10
        )

        if response.status_code == 200:
            events = response.json()

            for event in events:
                # Deep scan all fields
                def extract(obj):
                    if isinstance(obj, str) and obj.startswith('0x') and len(obj) == 42:
                        addresses.add(obj.lower())
                    elif isinstance(obj, dict):
                        for v in obj.values():
                            extract(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            extract(v)

                extract(event)

            print(f"  Events batch {offset//100}: Found {len(addresses)} addresses")
            return addresses
    except:
        pass

    return addresses


def scan_closed_markets_batch(offset):
    """Scan closed markets."""
    addresses = set()
    try:
        response = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={'limit': 100, 'offset': offset, 'closed': 'true'},
            timeout=10
        )

        if response.status_code == 200:
            markets = response.json()

            for market in markets:
                for token_id in market.get('clobTokenIds', []):
                    if token_id:
                        try:
                            book_resp = requests.get(
                                f"https://clob.polymarket.com/book",
                                params={'token_id': token_id},
                                timeout=2
                            )
                            if book_resp.status_code == 200:
                                book = book_resp.json()
                                for order in book.get('bids', []) + book.get('asks', []):
                                    maker = order.get('maker')
                                    if maker and maker.startswith('0x'):
                                        addresses.add(maker.lower())
                        except:
                            pass

            print(f"  Closed batch {offset//100}: Found {len(addresses)} addresses")
            return addresses
    except:
        pass

    return addresses


def scan_market_details(market_id):
    """Get detailed market info."""
    addresses = set()
    try:
        response = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=3
        )

        if response.status_code == 200:
            data = response.json()

            # Deep extract
            def extract(obj):
                if isinstance(obj, str) and obj.startswith('0x') and len(obj) == 42:
                    addresses.add(obj.lower())
                elif isinstance(obj, dict):
                    for v in obj.values():
                        extract(v)
                elif isinstance(obj, list):
                    for v in obj:
                        extract(v)

            extract(data)
    except:
        pass

    return addresses


def get_all_market_ids():
    """Get all market IDs first."""
    market_ids = []
    offset = 0

    while offset < 2000:  # Check up to 2000 markets
        try:
            response = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={'limit': 100, 'offset': offset},
                timeout=10
            )

            if response.status_code != 200:
                break

            markets = response.json()
            if not markets:
                break

            for market in markets:
                mid = market.get('id')
                if mid:
                    market_ids.append(mid)

            offset += 100
        except:
            break

    print(f"📋 Found {len(market_ids)} total market IDs")
    return market_ids


def ultra_aggressive_discovery():
    """Ultra-aggressive multi-threaded discovery."""
    print("\n" + "="*80)
    print("🚀 ULTRA-AGGRESSIVE WHALE DISCOVERY")
    print("="*80)
    print("Using 20 concurrent threads to maximize discovery speed...")

    all_addresses = set()

    # Phase 1: Parallel market scanning (20 threads)
    print("\n[Phase 1] Scanning ALL active markets in parallel...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        # Submit 20 batches
        for offset in range(0, 2000, 100):
            futures.append(executor.submit(scan_markets_batch, offset))

        for future in as_completed(futures):
            try:
                addresses = future.result()
                all_addresses.update(addresses)
            except:
                pass

    print(f"✅ Phase 1 complete: {len(all_addresses)} addresses")

    # Phase 2: Parallel event scanning
    print("\n[Phase 2] Scanning ALL events in parallel...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        for offset in range(0, 1000, 100):
            futures.append(executor.submit(scan_events_batch, offset))

        for future in as_completed(futures):
            try:
                addresses = future.result()
                all_addresses.update(addresses)
            except:
                pass

    print(f"✅ Phase 2 complete: {len(all_addresses)} addresses")

    # Phase 3: Closed markets
    print("\n[Phase 3] Scanning closed markets...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        for offset in range(0, 1000, 100):
            futures.append(executor.submit(scan_closed_markets_batch, offset))

        for future in as_completed(futures):
            try:
                addresses = future.result()
                all_addresses.update(addresses)
            except:
                pass

    print(f"✅ Phase 3 complete: {len(all_addresses)} addresses")

    # Phase 4: Deep market details scan
    print("\n[Phase 4] Deep scanning market details...")
    market_ids = get_all_market_ids()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        for market_id in market_ids[:500]:  # First 500 markets
            futures.append(executor.submit(scan_market_details, market_id))

        completed = 0
        for future in as_completed(futures):
            try:
                addresses = future.result()
                all_addresses.update(addresses)
                completed += 1

                if completed % 50 == 0:
                    print(f"  Scanned {completed}/500 markets... Total: {len(all_addresses)} addresses")
            except:
                pass

    print(f"✅ Phase 4 complete: {len(all_addresses)} addresses")

    # Filter out contract addresses
    contracts = {
        '0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e',  # CTF Exchange
        '0x0000000000000000000000000000000000000000',
    }

    filtered = [addr for addr in all_addresses if addr not in contracts]

    print(f"\n" + "="*80)
    print(f"📊 TOTAL DISCOVERED: {len(filtered)} unique addresses")
    print("="*80)

    return filtered


def add_to_database(addresses):
    """Add addresses to database."""
    if not addresses:
        return 0

    print(f"\n💾 Adding {len(addresses)} addresses to database...")

    with Session(engine) as session:
        added = 0
        skipped = 0

        for i, address in enumerate(addresses, 1):
            try:
                existing = session.query(Whale).filter(Whale.address == address).first()

                if existing:
                    skipped += 1
                    continue

                from eth_utils import to_checksum_address
                try:
                    checksummed = to_checksum_address(address)
                except:
                    checksummed = address

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
                    print(f"  ✅ Batch {i//100}: {added} added, {skipped} skipped")

                added += 1
            except:
                session.rollback()
                continue

        session.commit()

        print(f"\n✅ Added: {added} | Skipped: {skipped}")

        total = session.query(Whale).count()
        print(f"📊 Total whales in database: {total}")

        return added


def main():
    print("\n" + "="*80)
    print("🎯 ULTRA-AGGRESSIVE WHALE DISCOVERY - 20 THREADS")
    print("="*80)

    start_time = time.time()

    # Ultra-aggressive discovery
    addresses = ultra_aggressive_discovery()

    # Add to database
    if addresses:
        added = add_to_database(addresses)

        elapsed = time.time() - start_time

        print(f"\n" + "="*80)
        print("🎉 DISCOVERY COMPLETE")
        print("="*80)
        print(f"Time: {elapsed:.1f} seconds")
        print(f"New whales: {added}")
        print(f"Dashboard: http://localhost:8000/dashboard")

        with Session(engine) as session:
            total = session.query(Whale).count()

        if total >= 1000:
            print(f"\n🎯 TARGET REACHED: {total} whales!")
        else:
            print(f"\n📈 Progress: {total}/1000 whales")
            print("\nTo reach 1000:")
            print("1. Use CSV bulk import: python3 scripts/bulk_import_whales.py")
            print("2. Or manually collect from https://polymarket.com/leaderboard")


if __name__ == "__main__":
    main()
