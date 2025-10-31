"""
ETHERSCAN API V2 WHALE DISCOVERY - OPTIMIZED
Use block range pagination to work around PageNo × Offset ≤ 10000 limit.
Query historical blocks in chunks to maximize address discovery.
"""

import requests
import json
import time

# Etherscan API V2 for Polygon
ETHERSCAN_API_KEY = "W7K9R9J1JIJ6N37DM1QSIK1TTNFQEKCTYD"
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"
POLYGON_CHAIN_ID = "137"

# Polymarket contracts
POLYMARKET_CONTRACTS = {
    "CTF_EXCHANGE": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NEG_RISK": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
}

# Polygon block range (Polymarket launched around block 40M)
# Current block is around 78M
BLOCK_RANGES = [
    (40000000, 45000000),   # Early days
    (45000000, 50000000),
    (50000000, 55000000),
    (55000000, 60000000),
    (60000000, 65000000),
    (65000000, 70000000),
    (70000000, 75000000),
    (75000000, 80000000),   # Recent
]


def get_transactions_for_block_range(contract_address, start_block, end_block, offset=10000):
    """
    Get all transactions for a contract in a specific block range.
    Uses page=1, offset=10000 to maximize results per call (10000 tx limit).
    """
    try:
        params = {
            "chainid": POLYGON_CHAIN_ID,
            "module": "account",
            "action": "txlist",
            "address": contract_address,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": offset,
            "sort": "asc",  # Ascending to get oldest first
            "apikey": ETHERSCAN_API_KEY
        }

        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transactions = data["result"]

                # Extract unique addresses
                addresses = set()
                for tx in transactions:
                    from_addr = tx.get("from", "").lower()
                    if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(from_addr)

                return list(addresses), len(transactions)
            else:
                return [], 0
        else:
            return [], 0

    except Exception as e:
        print(f"    ❌ Error: {e}")
        return [], 0


def discover_whales_by_block_ranges():
    """
    Discover whales by querying block ranges systematically.
    This works around the PageNo × Offset ≤ 10000 API limit.
    """
    print("\n" + "=" * 80)
    print("🔍 ETHERSCAN API V2 WHALE DISCOVERY (OPTIMIZED)")
    print("=" * 80)
    print(f"Strategy: Query {len(BLOCK_RANGES)} block ranges × {len(POLYMARKET_CONTRACTS)} contracts")
    print(f"Max per query: 10,000 transactions")
    print()

    all_addresses = set()

    # Load existing addresses
    try:
        with open('whale_addresses_discovered.json', 'r') as f:
            data = json.load(f)
            all_addresses.update(data.get('addresses', []))
        with open('sampled_whale_addresses.json', 'r') as f:
            data = json.load(f)
            all_addresses.update(data.get('addresses', []))
        print(f"✅ Loaded {len(all_addresses)} existing addresses\n")
    except:
        pass

    total_queries = len(BLOCK_RANGES) * len(POLYMARKET_CONTRACTS)
    query_count = 0

    for contract_name, contract_address in POLYMARKET_CONTRACTS.items():
        print(f"\n{'=' * 80}")
        print(f"📝 Contract: {contract_name}")
        print(f"{'=' * 80}")

        for start_block, end_block in BLOCK_RANGES:
            query_count += 1
            print(f"  [{query_count}/{total_queries}] Blocks {start_block:,} - {end_block:,}...", end=" ")

            addresses, tx_count = get_transactions_for_block_range(
                contract_address,
                start_block,
                end_block
            )

            if addresses:
                before = len(all_addresses)
                all_addresses.update(addresses)
                new_count = len(all_addresses) - before
                print(f"✅ {tx_count} txs, +{new_count} new (total: {len(all_addresses)})")
            else:
                print(f"No transactions")

            time.sleep(0.3)  # Rate limiting (5 calls/second = 200ms, we use 300ms to be safe)

    # Also try to get recent transactions with smaller offset for more pages
    print(f"\n{'=' * 80}")
    print("📝 Recent Transactions (Last 500k blocks, paginated)")
    print(f"{'=' * 80}")

    for contract_name, contract_address in POLYMARKET_CONTRACTS.items():
        print(f"\n  Contract: {contract_name}")

        # Use smaller offset (1000) to allow more pages (up to page 10)
        for page in range(1, 11):  # Pages 1-10
            print(f"    Page {page}/10...", end=" ")

            try:
                params = {
                    "chainid": POLYGON_CHAIN_ID,
                    "module": "account",
                    "action": "txlist",
                    "address": contract_address,
                    "startblock": 77500000,  # Last ~500k blocks
                    "endblock": 99999999,
                    "page": page,
                    "offset": 1000,  # Small offset for more pages
                    "sort": "desc",
                    "apikey": ETHERSCAN_API_KEY
                }

                response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()

                    if data.get("status") == "1" and data.get("result"):
                        transactions = data["result"]

                        before = len(all_addresses)
                        for tx in transactions:
                            from_addr = tx.get("from", "").lower()
                            if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                                all_addresses.add(from_addr)

                        new_count = len(all_addresses) - before
                        print(f"✅ +{new_count} new (total: {len(all_addresses)})")

                        if len(transactions) < 1000:  # Last page
                            print(f"    Reached end ({len(transactions)} txs)")
                            break
                    else:
                        print("No more results")
                        break

                time.sleep(0.3)

            except Exception as e:
                print(f"Error: {e}")
                break

    # Save results
    output_file = "etherscan_whale_addresses_optimized.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'addresses': sorted(list(all_addresses)),
            'source': 'Etherscan API V2 (Optimized with block ranges)',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)

    print("\n" + "=" * 80)
    print("✅ OPTIMIZED DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total unique addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")
    print()

    if len(all_addresses) >= 1000:
        print(f"🎉 SUCCESS! Discovered {len(all_addresses)} addresses (target: 1000)")
    else:
        shortfall = 1000 - len(all_addresses)
        print(f"📊 Progress: {len(all_addresses)}/1000 ({100*len(all_addresses)//1000}%)")
        print(f"⚠️  Still need {shortfall} more addresses")

    return list(all_addresses)


if __name__ == "__main__":
    addresses = discover_whales_by_block_ranges()
