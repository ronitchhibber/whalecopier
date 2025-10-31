"""
Query the CTF (Conditional Token Framework) ERC-1155 token contract directly.
This represents ALL position tokens on Polymarket, so we should find many more traders.
"""

import requests
import json
import time

# Etherscan API V2
ETHERSCAN_API_KEY = "W7K9R9J1JIJ6N37DM1QSIK1TTNFQEKCTYD"
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"
POLYGON_CHAIN_ID = "137"

# Polymarket Conditional Tokens contract (ERC-1155)
CTF_TOKEN_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Block ranges
BLOCK_RANGES = [
    (40000000, 45000000),
    (45000000, 50000000),
    (50000000, 55000000),
    (55000000, 60000000),
    (60000000, 65000000),
    (65000000, 70000000),
    (70000000, 75000000),
    (75000000, 78500000),
]


def get_erc1155_transfers_for_range(contract_address, start_block, end_block):
    """
    Get ERC-1155 token transfers for a specific block range.
    """
    try:
        params = {
            "chainid": POLYGON_CHAIN_ID,
            "module": "account",
            "action": "token1155tx",
            "contractaddress": contract_address,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": 10000,
            "sort": "asc",
            "apikey": ETHERSCAN_API_KEY
        }

        response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transfers = data["result"]

                # Extract unique addresses
                addresses = set()
                for transfer in transfers:
                    from_addr = transfer.get("from", "").lower()
                    to_addr = transfer.get("to", "").lower()

                    # Add both sender and receiver
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
        print(f"    ❌ Error: {e}")
        return [], 0


def get_normal_transactions_for_range(contract_address, start_block, end_block):
    """
    Get normal transactions to/from the CTF contract.
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
            "offset": 10000,
            "sort": "asc",
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
                    if from_addr and from_addr != "0x0000000000000000000000000000000000000000":
                        addresses.add(from_addr)

                return list(addresses), len(transactions)
            else:
                return [], 0
        else:
            return [], 0

    except Exception as e:
        return [], 0


def discover_ctf_token_holders():
    """
    Discover whale addresses by querying the CTF token contract.
    """
    print("\n" + "=" * 80)
    print("🪙 CTF TOKEN CONTRACT WHALE DISCOVERY")
    print("=" * 80)
    print(f"Contract: {CTF_TOKEN_CONTRACT}")
    print(f"Strategy: Query ERC-1155 transfers across {len(BLOCK_RANGES)} block ranges")
    print()

    all_addresses = set()

    # Load existing addresses
    try:
        files = [
            'whale_addresses_discovered.json',
            'sampled_whale_addresses.json',
            'etherscan_whale_addresses_optimized.json'
        ]
        for fname in files:
            try:
                with open(fname, 'r') as f:
                    data = json.load(f)
                    all_addresses.update(data.get('addresses', []))
            except:
                pass
        print(f"✅ Loaded {len(all_addresses)} existing addresses\n")
    except:
        pass

    # Query ERC-1155 transfers
    print("=" * 80)
    print("📝 Method 1: ERC-1155 Token Transfers")
    print("=" * 80)

    for i, (start_block, end_block) in enumerate(BLOCK_RANGES):
        print(f"  [{i+1}/{len(BLOCK_RANGES)}] Blocks {start_block:,} - {end_block:,}...", end=" ")

        addresses, transfer_count = get_erc1155_transfers_for_range(
            CTF_TOKEN_CONTRACT,
            start_block,
            end_block
        )

        if addresses:
            before = len(all_addresses)
            all_addresses.update(addresses)
            new_count = len(all_addresses) - before
            print(f"✅ {transfer_count} transfers, +{new_count} new (total: {len(all_addresses)})")
        else:
            print("No transfers")

        time.sleep(0.3)

    # Query normal transactions
    print("\n" + "=" * 80)
    print("📝 Method 2: Normal Transactions to CTF Contract")
    print("=" * 80)

    for i, (start_block, end_block) in enumerate(BLOCK_RANGES):
        print(f"  [{i+1}/{len(BLOCK_RANGES)}] Blocks {start_block:,} - {end_block:,}...", end=" ")

        addresses, tx_count = get_normal_transactions_for_range(
            CTF_TOKEN_CONTRACT,
            start_block,
            end_block
        )

        if addresses:
            before = len(all_addresses)
            all_addresses.update(addresses)
            new_count = len(all_addresses) - before
            print(f"✅ {tx_count} txs, +{new_count} new (total: {len(all_addresses)})")
        else:
            print("No transactions")

        time.sleep(0.3)

    # Save results
    output_file = "etherscan_ctf_whale_addresses.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'addresses': sorted(list(all_addresses)),
            'source': 'Etherscan API V2 - CTF Token Contract',
            'contract': CTF_TOKEN_CONTRACT,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)

    print("\n" + "=" * 80)
    print("✅ CTF TOKEN DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total unique addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")
    print()

    if len(all_addresses) >= 1000:
        print(f"🎉 SUCCESS! Discovered {len(all_addresses):,} addresses (target: 1000)")
    else:
        progress = (len(all_addresses) * 100) // 1000
        print(f"📊 Progress: {len(all_addresses)}/1000 ({progress}%)")
        shortfall = 1000 - len(all_addresses)
        print(f"⚠️  Still need {shortfall} more addresses")

    return list(all_addresses)


if __name__ == "__main__":
    addresses = discover_ctf_token_holders()
