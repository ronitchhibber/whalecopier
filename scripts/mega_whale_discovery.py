"""
AGGRESSIVE WHALE DISCOVERY - Target: 1000 whales
Uses every possible source to build comprehensive whale list.
"""

import os
import sys
import requests
import time
import json
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Polymarket contracts on Polygon
POLYMARKET_CTF = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # CTF Exchange
POLYMARKET_NEG_RISK = "0xC5d563A36AE78145C45a50134d48A1215220f80a"  # Neg Risk Adapter
USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC on Polygon

# Free Polygon RPC endpoints
POLYGON_RPCS = [
    "https://polygon-rpc.com",
    "https://rpc-mainnet.matic.network",
    "https://rpc-mainnet.maticvigil.com",
    "https://polygon-mainnet.public.blastapi.io",
]


def get_whale_addresses_from_rpc():
    """
    Query Polygon blockchain for addresses interacting with Polymarket contracts.
    """
    print("\n🔍 METHOD 1: Blockchain RPC Query")
    print("=" * 80)

    addresses = set()

    for rpc in POLYGON_RPCS[:2]:  # Try first 2 RPCs
        try:
            print(f"\nTrying RPC: {rpc}")

            # Get recent blocks
            response = requests.post(
                rpc,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                latest_block = int(result.get('result', '0x0'), 16)
                print(f"  Latest block: {latest_block:,}")

                # Query logs for Polymarket contracts (last 10k blocks)
                from_block = hex(latest_block - 10000)
                to_block = hex(latest_block)

                # Get Transfer events from CTF contract
                log_response = requests.post(
                    rpc,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getLogs",
                        "params": [{
                            "fromBlock": from_block,
                            "toBlock": to_block,
                            "address": POLYMARKET_CTF
                        }],
                        "id": 1
                    },
                    timeout=30
                )

                if log_response.status_code == 200:
                    logs = log_response.json().get('result', [])
                    print(f"  Found {len(logs)} events")

                    # Extract unique addresses from topics
                    for log in logs:
                        topics = log.get('topics', [])
                        for topic in topics[1:]:  # Skip event signature
                            # Topics are padded addresses
                            if len(topic) == 66:  # 0x + 64 chars
                                addr = '0x' + topic[-40:]
                                if addr != '0x' + '0' * 40:  # Skip zero address
                                    addresses.add(addr.lower())

                    print(f"  ✅ Extracted {len(addresses)} unique addresses")

                    if len(addresses) > 100:
                        break  # Got enough from this source

        except Exception as e:
            print(f"  ❌ RPC {rpc} failed: {e}")
            continue

    return list(addresses)


def get_whale_addresses_from_moralis():
    """
    Use Moralis free tier to get wallet interactions.
    """
    print("\n🔍 METHOD 2: Moralis Blockchain API")
    print("=" * 80)

    # Moralis has a free tier
    moralis_key = os.getenv('MORALIS_API_KEY', '')

    if not moralis_key:
        print("  ⚠️  No Moralis API key (sign up for free at moralis.io)")
        return []

    addresses = set()

    try:
        # Get NFT transfers for CTF tokens (they're ERC-1155)
        url = f"https://deep-index.moralis.io/api/v2/nft/{POLYMARKET_CTF}/transfers"
        headers = {"X-API-Key": moralis_key}

        response = requests.get(url, headers=headers, params={'chain': 'polygon'}, timeout=15)

        if response.status_code == 200:
            data = response.json()
            transfers = data.get('result', [])

            for transfer in transfers:
                addresses.add(transfer.get('from_address', '').lower())
                addresses.add(transfer.get('to_address', '').lower())

            print(f"  ✅ Found {len(addresses)} addresses from NFT transfers")
        else:
            print(f"  ⚠️  Moralis returned status {response.status_code}")

    except Exception as e:
        print(f"  ❌ Moralis query failed: {e}")

    return list(addresses)


def get_whale_addresses_from_covalent():
    """
    Use Covalent free tier for blockchain data.
    """
    print("\n🔍 METHOD 3: Covalent Blockchain API")
    print("=" * 80)

    covalent_key = os.getenv('COVALENT_API_KEY', '')

    if not covalent_key:
        print("  ⚠️  No Covalent API key (sign up for free at covalenthq.com)")
        return []

    addresses = set()

    try:
        # Get token holders for USDC on Polygon (whales likely hold USDC)
        url = f"https://api.covalenthq.com/v1/137/tokens/{USDC_POLYGON}/token_holders/"
        params = {
            'key': covalent_key,
            'page-size': 1000
        }

        response = requests.get(url, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            holders = data.get('data', {}).get('items', [])

            # Filter for holders with >$50k
            for holder in holders:
                balance = float(holder.get('balance', 0)) / 1e6  # USDC has 6 decimals
                if balance > 50000:
                    addresses.add(holder.get('address', '').lower())

            print(f"  ✅ Found {len(addresses)} USDC whales (>$50K)")
        else:
            print(f"  ⚠️  Covalent returned status {response.status_code}")

    except Exception as e:
        print(f"  ❌ Covalent query failed: {e}")

    return list(addresses)


def get_whale_addresses_from_github():
    """
    Scrape GitHub repos for whale address lists.
    """
    print("\n🔍 METHOD 4: GitHub Repositories")
    print("=" * 80)

    addresses = set()

    # Known repos with Polymarket data
    repos_to_check = [
        "PolyTrader/polymarket-info",
        "Polymarket/examples",
        "tanaerao/polymarket-midterms",
    ]

    for repo in repos_to_check:
        try:
            print(f"\n  Checking {repo}...")

            # Search for JSON files with addresses
            api_url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
            response = requests.get(api_url, timeout=10)

            if response.status_code == 200:
                tree = response.json().get('tree', [])

                # Look for data files
                for item in tree:
                    path = item.get('path', '')
                    if any(x in path.lower() for x in ['address', 'whale', 'trader', 'leaderboard']):
                        if path.endswith(('.json', '.csv', '.txt')):
                            # Try to fetch the file
                            file_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
                            file_response = requests.get(file_url, timeout=10)

                            if file_response.status_code == 200:
                                content = file_response.text

                                # Extract ethereum addresses (0x + 40 hex chars)
                                import re
                                found_addrs = re.findall(r'0x[a-fA-F0-9]{40}', content)
                                addresses.update([a.lower() for a in found_addrs])

                                print(f"    ✅ {path}: {len(found_addrs)} addresses")

        except Exception as e:
            print(f"    ❌ Error: {e}")
            continue

    print(f"\n  ✅ Total from GitHub: {len(addresses)} addresses")
    return list(addresses)


def get_whale_addresses_from_subgraph():
    """
    Query The Graph subgraphs for Polymarket data.
    """
    print("\n🔍 METHOD 5: The Graph Subgraphs")
    print("=" * 80)

    addresses = set()

    # The Graph has public access
    subgraph_urls = [
        "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets",
        "https://api.studio.thegraph.com/query/polymarket/matic-markets/",
    ]

    query = """
    {
      users(first: 1000, orderBy: volumeUSD, orderDirection: desc) {
        id
        volumeUSD
        numTrades
      }
    }
    """

    for url in subgraph_urls:
        try:
            response = requests.post(
                url,
                json={'query': query},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                users = data.get('data', {}).get('users', [])

                for user in users:
                    addr = user.get('id', '')
                    volume = float(user.get('volumeUSD', 0))

                    if volume > 50000:  # >$50K volume
                        addresses.add(addr.lower())

                print(f"  ✅ Found {len(addresses)} whales from subgraph")

                if addresses:
                    break  # Got data, stop trying other URLs

        except Exception as e:
            print(f"  ⚠️  Subgraph failed: {e}")
            continue

    return list(addresses)


def aggregate_all_sources():
    """
    Main function: Get whales from ALL sources and aggregate.
    """
    print("\n" + "=" * 80)
    print("🐋 MEGA WHALE DISCOVERY - TARGET: 1000 WHALES")
    print("=" * 80)

    all_addresses = set()

    # Method 1: Blockchain RPC
    rpc_addresses = get_whale_addresses_from_rpc()
    all_addresses.update(rpc_addresses)
    print(f"\n📊 Running total: {len(all_addresses)} addresses")

    # Method 2: Moralis
    moralis_addresses = get_whale_addresses_from_moralis()
    all_addresses.update(moralis_addresses)
    print(f"📊 Running total: {len(all_addresses)} addresses")

    # Method 3: Covalent
    covalent_addresses = get_whale_addresses_from_covalent()
    all_addresses.update(covalent_addresses)
    print(f"📊 Running total: {len(all_addresses)} addresses")

    # Method 4: GitHub
    github_addresses = get_whale_addresses_from_github()
    all_addresses.update(github_addresses)
    print(f"📊 Running total: {len(all_addresses)} addresses")

    # Method 5: The Graph
    subgraph_addresses = get_whale_addresses_from_subgraph()
    all_addresses.update(subgraph_addresses)
    print(f"📊 Running total: {len(all_addresses)} addresses")

    # Save to file
    output_file = "whale_addresses_discovered.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'timestamp': datetime.utcnow().isoformat(),
            'addresses': sorted(list(all_addresses)),
            'sources': {
                'rpc': len(rpc_addresses),
                'moralis': len(moralis_addresses),
                'covalent': len(covalent_addresses),
                'github': len(github_addresses),
                'subgraph': len(subgraph_addresses)
            }
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✅ DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total unique addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")

    return list(all_addresses)


if __name__ == "__main__":
    addresses = aggregate_all_sources()

    print(f"\n📝 Next steps:")
    print(f"1. Verify these addresses have Polymarket activity")
    print(f"2. Fetch stats for each address")
    print(f"3. Filter for quality whales (>$50K volume, good performance)")
    print(f"4. Import to database")
