"""
Automated whale discovery targeting 1000+ whales.
Uses multiple methods in parallel and combines results.
"""

import os
import sys
import requests
import time
import json
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def method_1_gamma_api_all_events():
    """Get ALL events from Gamma API and extract unique traders from activity."""
    print("\n" + "="*80)
    print("METHOD 1: Gamma API - ALL Events Analysis")
    print("="*80)

    addresses = set()

    try:
        # Get all events (not just active)
        print("📡 Fetching ALL events from Gamma API...")
        response = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={'limit': 100, 'offset': 0},
            timeout=20
        )

        if response.status_code != 200:
            print(f"❌ Failed: {response.status_code}")
            return []

        events = response.json()
        print(f"✅ Found {len(events)} events")

        # Process each event
        for i, event in enumerate(events, 1):
            if i % 10 == 0:
                print(f"   Processing event {i}/{len(events)}...")

            # Check if event has markets
            markets = event.get('markets', [])
            for market in markets:
                # Try to get market details with volume data
                try:
                    market_id = market.get('id')
                    if market_id:
                        # Polymarket markets endpoint
                        detail_response = requests.get(
                            f"https://gamma-api.polymarket.com/markets/{market_id}",
                            timeout=5
                        )
                        if detail_response.status_code == 200:
                            market_data = detail_response.json()
                            # Look for any address-like data
                            for key, value in market_data.items():
                                if isinstance(value, str) and value.startswith('0x') and len(value) == 42:
                                    addresses.add(value)
                        time.sleep(0.1)
                except:
                    pass

        print(f"✅ Method 1: Found {len(addresses)} addresses")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def method_2_clob_markets_scan():
    """Scan CLOB markets endpoint for any trader data."""
    print("\n" + "="*80)
    print("METHOD 2: CLOB Markets Deep Scan")
    print("="*80)

    addresses = set()

    try:
        print("📡 Fetching markets from CLOB...")
        response = requests.get("https://clob.polymarket.com/markets", timeout=15)

        if response.status_code != 200:
            print(f"❌ Failed: {response.status_code}")
            return []

        markets = response.json()
        print(f"✅ Found {len(markets)} markets")

        # Try to get orderbook for each market
        print("📖 Scanning orderbooks...")
        for i, market in enumerate(markets[:200], 1):  # First 200 markets
            try:
                tokens = market.get('tokens', [])
                for token in tokens:
                    token_id = token.get('token_id')
                    if token_id:
                        book_response = requests.get(
                            f"https://clob.polymarket.com/book",
                            params={'token_id': token_id},
                            timeout=3
                        )

                        if book_response.status_code == 200:
                            book = book_response.json()

                            # Extract makers from bids
                            for order in book.get('bids', []):
                                maker = order.get('maker')
                                if maker and maker.startswith('0x') and len(maker) == 42:
                                    addresses.add(maker.lower())

                            # Extract makers from asks
                            for order in book.get('asks', []):
                                maker = order.get('maker')
                                if maker and maker.startswith('0x') and len(maker) == 42:
                                    addresses.add(maker.lower())

                        time.sleep(0.2)  # Rate limiting

                if i % 20 == 0:
                    print(f"   Scanned {i}/200 markets... Found {len(addresses)} addresses so far")

            except Exception as e:
                continue

        print(f"✅ Method 2: Found {len(addresses)} addresses")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def method_3_price_history_traders():
    """Get traders from price history API endpoints."""
    print("\n" + "="*80)
    print("METHOD 3: Price History & Trading Activity")
    print("="*80)

    addresses = set()

    try:
        # Get popular markets
        print("📊 Getting popular markets...")
        response = requests.get(
            "https://gamma-api.polymarket.com/events",
            params={'limit': 50, 'active': 'true'},
            timeout=15
        )

        if response.status_code != 200:
            return []

        events = response.json()

        # For each market, try different endpoints
        market_count = 0
        for event in events:
            for market in event.get('markets', []):
                market_id = market.get('id')
                if not market_id:
                    continue

                market_count += 1
                if market_count > 100:
                    break

                # Try trade history endpoint (might work without full auth)
                endpoints_to_try = [
                    f"https://clob.polymarket.com/prices-history?market={market_id}",
                    f"https://clob.polymarket.com/trades?market={market_id}",
                    f"https://data-api.polymarket.com/trades?market={market_id}",
                ]

                for endpoint in endpoints_to_try:
                    try:
                        r = requests.get(endpoint, timeout=3)
                        if r.status_code == 200:
                            data = r.json()
                            # Look for any address fields
                            if isinstance(data, list):
                                for item in data[:50]:
                                    for key in ['maker', 'taker', 'trader', 'address']:
                                        addr = item.get(key)
                                        if addr and addr.startswith('0x') and len(addr) == 42:
                                            addresses.add(addr.lower())
                            elif isinstance(data, dict):
                                # Recursively search for addresses
                                def find_addresses(obj):
                                    if isinstance(obj, str) and obj.startswith('0x') and len(obj) == 42:
                                        addresses.add(obj.lower())
                                    elif isinstance(obj, dict):
                                        for v in obj.values():
                                            find_addresses(v)
                                    elif isinstance(obj, list):
                                        for v in obj:
                                            find_addresses(v)

                                find_addresses(data)
                        time.sleep(0.1)
                    except:
                        pass

                if market_count % 10 == 0:
                    print(f"   Checked {market_count} markets... Found {len(addresses)} addresses")

        print(f"✅ Method 3: Found {len(addresses)} addresses")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def method_4_subgraph_query():
    """Try to query Polymarket's subgraph if available."""
    print("\n" + "="*80)
    print("METHOD 4: The Graph Subgraph Query")
    print("="*80)

    addresses = set()

    # Polymarket might have a subgraph
    subgraph_urls = [
        "https://api.thegraph.com/subgraphs/name/polymarket/polymarket",
        "https://api.thegraph.com/subgraphs/name/polymarket/matic",
        "https://subgraph.satsuma-prod.com/polymarket/polymarket/api",
    ]

    # GraphQL query for traders
    query = """
    {
      users(first: 1000, orderBy: totalVolume, orderDirection: desc) {
        id
        address
        totalVolume
        tradeCount
      }
    }
    """

    for url in subgraph_urls:
        try:
            print(f"🔍 Trying subgraph: {url}")
            response = requests.post(
                url,
                json={'query': query},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                users = data.get('data', {}).get('users', [])

                if users:
                    print(f"✅ Found {len(users)} users from subgraph!")
                    for user in users:
                        addr = user.get('address') or user.get('id')
                        if addr and addr.startswith('0x') and len(addr) == 42:
                            addresses.add(addr.lower())
                    break

        except Exception as e:
            print(f"   ❌ Failed: {e}")
            continue

    print(f"✅ Method 4: Found {len(addresses)} addresses")
    return list(addresses)


def method_5_snapshot_governance():
    """Check Snapshot.org for Polymarket governance voters."""
    print("\n" + "="*80)
    print("METHOD 5: Snapshot Governance Participants")
    print("="*80)

    addresses = set()

    try:
        # Snapshot GraphQL endpoint
        url = "https://hub.snapshot.org/graphql"

        # Query for Polymarket space
        query = """
        query {
          space(id: "polymarket.eth") {
            id
            name
          }
          proposals(
            first: 100,
            where: {
              space_in: ["polymarket.eth"]
            }
          ) {
            id
            author
            votes
          }
        }
        """

        print("📊 Querying Snapshot for Polymarket governance...")
        response = requests.post(url, json={'query': query}, timeout=10)

        if response.status_code == 200:
            data = response.json()
            proposals = data.get('data', {}).get('proposals', [])

            print(f"✅ Found {len(proposals)} proposals")

            for proposal in proposals:
                # Get proposal author
                author = proposal.get('author')
                if author and author.startswith('0x'):
                    addresses.add(author.lower())

                # Get votes on this proposal
                proposal_id = proposal.get('id')
                if proposal_id:
                    vote_query = f"""
                    query {{
                      votes(
                        first: 1000,
                        where: {{
                          proposal: "{proposal_id}"
                        }}
                      ) {{
                        voter
                      }}
                    }}
                    """

                    try:
                        vote_response = requests.post(url, json={'query': vote_query}, timeout=5)
                        if vote_response.status_code == 200:
                            vote_data = vote_response.json()
                            votes = vote_data.get('data', {}).get('votes', [])
                            for vote in votes:
                                voter = vote.get('voter')
                                if voter and voter.startswith('0x'):
                                    addresses.add(voter.lower())
                    except:
                        pass

                time.sleep(0.2)

        print(f"✅ Method 5: Found {len(addresses)} addresses")
        return list(addresses)

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def method_6_dune_analytics():
    """Try Dune Analytics public dashboards for Polymarket addresses."""
    print("\n" + "="*80)
    print("METHOD 6: Dune Analytics Public Data")
    print("="*80)

    addresses = set()

    # Known Dune dashboards for Polymarket
    dune_queries = [
        "https://dune.com/queries/1234/results",  # Example - need real query IDs
    ]

    print("📊 Checking Dune Analytics...")
    print("⚠️  Note: This requires specific Dune query IDs")
    print("   Visit: https://dune.com/browse/dashboards?q=polymarket")

    # This method requires API key or web scraping Dune dashboards
    # Placeholder for now

    print(f"✅ Method 6: Found {len(addresses)} addresses")
    return list(addresses)


def combine_and_filter_addresses(all_addresses):
    """Combine addresses from all methods and filter valid ones."""
    print("\n" + "="*80)
    print("COMBINING & FILTERING RESULTS")
    print("="*80)

    # Flatten and deduplicate
    unique_addresses = set()
    for addr_list in all_addresses:
        for addr in addr_list:
            # Normalize address
            if addr.startswith('0x') and len(addr) == 42:
                unique_addresses.add(addr.lower())

    # Filter out common contracts/known non-traders
    known_contracts = {
        '0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e',  # CTF Exchange
        '0x0000000000000000000000000000000000000000',  # Zero address
        '0x0000000000000000000000000000000000000001',  # Burn address
    }

    filtered = [addr for addr in unique_addresses if addr not in known_contracts]

    print(f"✅ Total unique addresses: {len(filtered)}")
    return filtered


def add_whales_to_db(addresses, batch_size=100):
    """Add addresses to database in batches."""
    print("\n" + "="*80)
    print(f"ADDING {len(addresses)} WHALES TO DATABASE")
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

                # Checksum the address
                from eth_utils import to_checksum_address
                try:
                    checksummed = to_checksum_address(address)
                except:
                    checksummed = address

                # Add new whale
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
                if i % batch_size == 0:
                    session.commit()
                    print(f"   ✅ Committed batch {i//batch_size} ({i} addresses processed)")

                added += 1

            except Exception as e:
                session.rollback()
                print(f"   ❌ Error adding {address}: {e}")
                continue

        # Commit remaining
        session.commit()

        print(f"\n" + "="*80)
        print(f"✅ Successfully added: {added} whales")
        print(f"⏭️  Skipped (already exist): {skipped} whales")
        print("="*80)

        return added


def main():
    print("\n" + "="*80)
    print("🎯 AUTOMATED WHALE DISCOVERY - TARGET: 1000 WHALES")
    print("="*80)
    print("\nUsing 6 parallel methods:")
    print("1. Gamma API - All Events")
    print("2. CLOB Markets - Orderbook Scan")
    print("3. Price History - Trading Activity")
    print("4. The Graph - Subgraph Query")
    print("5. Snapshot - Governance Participants")
    print("6. Dune Analytics - Public Data")
    print("\nStarting discovery...")

    start_time = time.time()

    # Run methods in parallel
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(method_1_gamma_api_all_events): "Method 1",
            executor.submit(method_2_clob_markets_scan): "Method 2",
            executor.submit(method_3_price_history_traders): "Method 3",
            executor.submit(method_4_subgraph_query): "Method 4",
            executor.submit(method_5_snapshot_governance): "Method 5",
            executor.submit(method_6_dune_analytics): "Method 6",
        }

        all_addresses = []
        for future in as_completed(futures):
            method_name = futures[future]
            try:
                result = future.result()
                all_addresses.append(result)
                print(f"✅ {method_name} completed: {len(result)} addresses")
            except Exception as e:
                print(f"❌ {method_name} failed: {e}")
                all_addresses.append([])

    # Combine and filter
    filtered_addresses = combine_and_filter_addresses(all_addresses)

    if filtered_addresses:
        # Add to database
        added = add_whales_to_db(filtered_addresses)

        elapsed = time.time() - start_time

        print(f"\n" + "="*80)
        print("🎉 DISCOVERY COMPLETE")
        print("="*80)
        print(f"Total addresses discovered: {len(filtered_addresses)}")
        print(f"New whales added to database: {added}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
        print(f"\n📊 View dashboard: http://localhost:8000/dashboard")

        if added < 1000:
            print(f"\n⚠️  Only found {added} whales (target was 1000)")
            print("\nNext steps:")
            print("1. Run Selenium scraper: python3 scripts/scrape_whales_selenium.py")
            print("2. Manual collection: python3 scripts/add_whale_address.py <ADDRESS>")
            print("3. Implement full CLOB authentication for /trades access")
    else:
        print("\n❌ No addresses discovered")
        print("\nAll automated methods blocked. Recommendations:")
        print("1. Implement full CLOB API authentication (EIP-712)")
        print("2. Use Selenium for leaderboard scraping")
        print("3. Manual collection from https://polymarket.com/leaderboard")


if __name__ == "__main__":
    main()
