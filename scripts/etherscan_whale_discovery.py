"""
ETHERSCAN API V2 WHALE DISCOVERY
Use Etherscan API V2 (formerly PolygonScan) to get all addresses that interacted with Polymarket.
Target: Get 1000+ unique whale addresses.
"""

import requests
import json
import time
from collections import Counter

# Etherscan API V2 for Polygon
ETHERSCAN_API_KEY = "W7K9R9J1JIJ6N37DM1QSIK1TTNFQEKCTYD"
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"
POLYGON_CHAIN_ID = "137"  # Polygon chain ID for V2 API

# Polymarket contracts
POLYMARKET_CONTRACTS = {
    "CTF_EXCHANGE": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NEG_RISK": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
}


def get_contract_transactions(contract_address, page=1, offset=10000, start_block=0):
    """
    Get transactions for a contract using Etherscan API V2.
    Returns list of unique addresses that interacted with the contract.
    """
    try:
        params = {
            "chainid": POLYGON_CHAIN_ID,
            "module": "account",
            "action": "txlist",
            "address": contract_address,
            "startblock": start_block,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",  # Most recent first
            "apikey": ETHERSCAN_API_KEY
        }

        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transactions = data["result"]

                # Extract unique addresses (from field - senders)
                addresses = set()
                for tx in transactions:
                    from_addr = tx.get("from", "").lower()
                    if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(from_addr)

                return list(addresses), len(transactions)
            else:
                message = data.get("message", "Unknown error")
                print(f"  ⚠️  API returned: {message}")
                return [], 0
        else:
            print(f"  ❌ HTTP {response.status_code}")
            return [], 0

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return [], 0


def get_internal_transactions(contract_address, page=1, offset=10000, start_block=0):
    """
    Get internal transactions for a contract.
    """
    try:
        params = {
            "chainid": POLYGON_CHAIN_ID,
            "module": "account",
            "action": "txlistinternal",
            "address": contract_address,
            "startblock": start_block,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }

        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transactions = data["result"]

                addresses = set()
                for tx in transactions:
                    from_addr = tx.get("from", "").lower()
                    to_addr = tx.get("to", "").lower()

                    if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(from_addr)
                    if to_addr and to_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(to_addr)

                return list(addresses), len(transactions)
            else:
                return [], 0
        else:
            return [], 0

    except Exception as e:
        return [], 0


def get_erc1155_transfers(contract_address, page=1, offset=10000):
    """
    Get ERC-1155 token transfers (Polymarket uses ERC-1155 for prediction markets).
    """
    try:
        params = {
            "chainid": POLYGON_CHAIN_ID,
            "module": "account",
            "action": "token1155tx",
            "contractaddress": contract_address,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY
        }

        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transfers = data["result"]

                addresses = set()
                for transfer in transfers:
                    from_addr = transfer.get("from", "").lower()
                    to_addr = transfer.get("to", "").lower()

                    if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(from_addr)
                    if to_addr and to_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(to_addr)

                return list(addresses), len(transfers)
            else:
                return [], 0
        else:
            return [], 0

    except Exception as e:
        return [], 0


def discover_whales_comprehensive():
    """
    Comprehensive whale discovery using all Etherscan API methods.
    """
    print("\n" + "=" * 80)
    print("🔍 ETHERSCAN API V2 WHALE DISCOVERY")
    print("=" * 80)
    print(f"API Key: {ETHERSCAN_API_KEY[:10]}...{ETHERSCAN_API_KEY[-10:]}")
    print()

    all_addresses = set()

    # Try to load existing addresses
    try:
        with open('whale_addresses_discovered.json', 'r') as f:
            data = json.load(f)
            all_addresses.update(data.get('addresses', []))
            print(f"✅ Loaded {len(all_addresses)} existing addresses")
    except:
        print("No existing addresses file")

    try:
        with open('sampled_whale_addresses.json', 'r') as f:
            data = json.load(f)
            all_addresses.update(data.get('addresses', []))
            print(f"✅ Loaded addresses from sampling (total: {len(all_addresses)})")
    except:
        pass

    print()

    for contract_name, contract_address in POLYMARKET_CONTRACTS.items():
        print(f"\n{'=' * 80}")
        print(f"📝 Processing {contract_name}: {contract_address}")
        print(f"{'=' * 80}")

        # Method 1: Normal transactions (paginated)
        print("\n🔍 Method 1: Normal Transactions")
        page = 1
        max_pages = 10  # Get up to 100k transactions (10k per page)

        while page <= max_pages:
            print(f"  Page {page}/{max_pages}...", end=" ")

            addresses, tx_count = get_contract_transactions(
                contract_address,
                page=page,
                offset=10000
            )

            if addresses:
                all_addresses.update(addresses)
                print(f"✅ +{len(addresses)} addresses (total: {len(all_addresses)})")
            else:
                print(f"No more results")
                break

            if tx_count < 10000:  # Last page
                print(f"  Reached last page ({tx_count} transactions)")
                break

            page += 1
            time.sleep(0.5)  # Rate limiting (5 calls/second for free tier)

        # Method 2: Internal transactions
        print("\n🔍 Method 2: Internal Transactions")
        page = 1
        max_pages = 5

        while page <= max_pages:
            print(f"  Page {page}/{max_pages}...", end=" ")

            addresses, tx_count = get_internal_transactions(
                contract_address,
                page=page,
                offset=10000
            )

            if addresses:
                all_addresses.update(addresses)
                print(f"✅ +{len(addresses)} addresses (total: {len(all_addresses)})")
            else:
                print(f"No results")
                break

            if tx_count < 10000:
                break

            page += 1
            time.sleep(0.5)

        # Method 3: ERC-1155 transfers (Polymarket uses ERC-1155)
        print("\n🔍 Method 3: ERC-1155 Token Transfers")
        page = 1
        max_pages = 10

        while page <= max_pages:
            print(f"  Page {page}/{max_pages}...", end=" ")

            addresses, transfer_count = get_erc1155_transfers(
                contract_address,
                page=page,
                offset=10000
            )

            if addresses:
                all_addresses.update(addresses)
                print(f"✅ +{len(addresses)} addresses (total: {len(all_addresses)})")
            else:
                print(f"No results")
                break

            if transfer_count < 10000:
                break

            page += 1
            time.sleep(0.5)

    # Save results
    output_file = "etherscan_whale_addresses.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'addresses': sorted(list(all_addresses)),
            'source': 'Etherscan API V2',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)

    print("\n" + "=" * 80)
    print("✅ ETHERSCAN DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total unique addresses discovered: {len(all_addresses)}")
    print(f"Saved to: {output_file}")
    print()

    if len(all_addresses) >= 1000:
        print(f"🎉 SUCCESS! Discovered {len(all_addresses)} addresses (target: 1000)")
    else:
        shortfall = 1000 - len(all_addresses)
        print(f"⚠️  Need {shortfall} more addresses to reach 1000")
        print(f"💡 Try: Increase max_pages or query more historical blocks")

    return list(all_addresses)


if __name__ == "__main__":
    addresses = discover_whales_comprehensive()
