"""
MASSIVE BLOCKCHAIN SAMPLING
Sample thousands of blocks and extract ALL addresses that interacted with Polymarket.
Target: Get 1000+ unique whale addresses.
"""

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Multiple free Polygon RPCs for load balancing
POLYGON_RPCS = [
    "https://polygon-rpc.com",
    "https://polygon-mainnet.public.blastapi.io",
    "https://rpc.ankr.com/polygon",
    "https://polygon-bor.publicnode.com",
]

CTF_CONTRACT = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E".lower()


def get_latest_block(rpc):
    """Get latest block number."""
    try:
        response = requests.post(
            rpc,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=5
        )
        return int(response.json()['result'], 16)
    except:
        return None


def get_block_transactions(rpc, block_number):
    """Get all transactions in a block."""
    try:
        response = requests.post(
            rpc,
            json={
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": [hex(block_number), True],  # True = full tx objects
                "id": 1
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json().get('result', {})
            if result:
                txs = result.get('transactions', [])

                # Filter for Polymarket transactions
                polymarket_addresses = set()
                for tx in txs:
                    to_addr = tx.get('to', '').lower()
                    from_addr = tx.get('from', '').lower()

                    # Check if interacting with Polymarket contract
                    if to_addr == CTF_CONTRACT:
                        polymarket_addresses.add(from_addr)

                return list(polymarket_addresses)

        return []

    except Exception as e:
        return []


def sample_blocks_parallel(start_block, end_block, num_samples=1000):
    """
    Sample random blocks in parallel and extract addresses.
    """
    import random

    print(f"\n🔍 Sampling {num_samples} blocks between {start_block:,} and {end_block:,}")

    # Generate random block numbers to sample
    block_numbers = random.sample(range(start_block, end_block), min(num_samples, end_block - start_block))

    all_addresses = set()
    processed = 0

    # Use thread pool for parallel requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Cycle through RPCs for load balancing
        futures = {}
        for i, block_num in enumerate(block_numbers):
            rpc = POLYGON_RPCS[i % len(POLYGON_RPCS)]
            future = executor.submit(get_block_transactions, rpc, block_num)
            futures[future] = block_num

        # Process results as they complete
        for future in as_completed(futures):
            block_num = futures[future]
            try:
                addresses = future.result()
                if addresses:
                    all_addresses.update(addresses)
                    print(f"  Block {block_num:,}: +{len(addresses)} addresses (total: {len(all_addresses)})")
                processed += 1

                if processed % 50 == 0:
                    print(f"  Progress: {processed}/{num_samples} blocks processed")

            except Exception as e:
                pass

    return list(all_addresses)


def main():
    print("\n" + "=" * 80)
    print("🚀 MASSIVE BLOCKCHAIN SAMPLING - TARGET: 1000 ADDRESSES")
    print("=" * 80)

    # Get latest block from any working RPC
    latest_block = None
    for rpc in POLYGON_RPCS:
        latest_block = get_latest_block(rpc)
        if latest_block:
            print(f"\n✅ Latest block: {latest_block:,}")
            break

    if not latest_block:
        print("❌ Could not connect to any RPC")
        return []

    # Sample last 1 million blocks (roughly last 1-2 months of Polygon)
    start_block = max(latest_block - 1000000, 40000000)  # Polygon started around block 40M
    end_block = latest_block

    print(f"📊 Sampling range: blocks {start_block:,} to {end_block:,}")
    print(f"💡 Strategy: Sample 2000 random blocks and extract Polymarket traders\n")

    # Sample blocks
    addresses = sample_blocks_parallel(start_block, end_block, num_samples=2000)

    # Load existing addresses from other sources
    existing = set()
    try:
        with open('whale_addresses_discovered.json', 'r') as f:
            data = json.load(f)
            existing.update(data.get('addresses', []))
    except:
        pass

    # Combine
    all_addresses = existing.union(set(addresses))

    # Save
    output_file = "sampled_whale_addresses.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'from_sampling': len(addresses),
            'from_existing': len(existing),
            'addresses': sorted(list(all_addresses))
        }, f, indent=2)

    print("\n" + "=" * 80)
    print("✅ SAMPLING COMPLETE")
    print("=" * 80)
    print(f"New addresses from sampling: {len(addresses)}")
    print(f"Existing addresses: {len(existing)}")
    print(f"Total unique addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")

    if len(all_addresses) < 1000:
        shortfall = 1000 - len(all_addresses)
        print(f"\n⚠️  Still need {shortfall} more addresses to reach 1000")
        print(f"💡 Recommendation: Sample more blocks or use API keys")

    return list(all_addresses)


if __name__ == "__main__":
    main()
