"""
Extract whale addresses directly from Polygon blockchain by analyzing
Polymarket contract transactions over time.
"""

import requests
import json
import time
from collections import Counter

# Free Polygon RPC
POLYGON_RPC = "https://polygon-rpc.com"

# Polymarket contracts
CONTRACTS = {
    "CTF_EXCHANGE": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NEG_RISK": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
}


def get_block_range():
    """Get recent block range to query."""
    try:
        response = requests.post(
            POLYGON_RPC,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=10
        )
        latest = int(response.json()['result'], 16)
        return latest - 500000, latest  # Last ~500k blocks (about 2 weeks)
    except:
        return 78000000, 78500000  # Fallback range


def extract_addresses_from_transactions(contract_address, from_block, to_block, batch_size=10000):
    """
    Query blockchain for all transactions to a contract.
    Extract unique wallet addresses.
    """
    print(f"\n🔍 Querying {contract_address[:10]}... (blocks {from_block:,} to {to_block:,})")

    addresses = set()
    current_block = from_block

    while current_block < to_block:
        end_block = min(current_block + batch_size, to_block)

        try:
            # Get logs in batches
            response = requests.post(
                POLYGON_RPC,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(current_block),
                        "toBlock": hex(end_block),
                        "address": contract_address
                    }],
                    "id": 1
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json().get('result', [])

                # Extract addresses from logs
                for log in result:
                    # Get address from 'address' field (contract)
                    # Get addresses from topics (indexed parameters)
                    topics = log.get('topics', [])

                    for topic in topics[1:]:  # Skip first topic (event signature)
                        if len(topic) == 66:  # 0x + 64 hex chars
                            # Address is last 40 chars
                            addr = '0x' + topic[-40:]
                            if addr != '0x' + '0' * 40:  # Not zero address
                                addresses.add(addr.lower())

                    # Also check transaction sender
                    tx_hash = log.get('transactionHash')
                    if tx_hash:
                        tx_response = requests.post(
                            POLYGON_RPC,
                            json={
                                "jsonrpc": "2.0",
                                "method": "eth_getTransactionByHash",
                                "params": [tx_hash],
                                "id": 1
                            },
                            timeout=10
                        )

                        if tx_response.status_code == 200:
                            tx = tx_response.json().get('result', {})
                            if tx and tx.get('from'):
                                addresses.add(tx['from'].lower())

                print(f"  Block {current_block:,} - {end_block:,}: {len(addresses)} addresses so far")

            current_block = end_block + 1
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  ⚠️  Error at block {current_block}: {e}")
            current_block += batch_size

    return list(addresses)


def main():
    print("\n" + "=" * 80)
    print("🔗 BLOCKCHAIN WHALE EXTRACTION")
    print("=" * 80)

    from_block, to_block = get_block_range()
    print(f"\nBlock range: {from_block:,} to {to_block:,}")

    all_addresses = set()

    # Query each contract
    for name, contract in CONTRACTS.items():
        print(f"\n📝 Processing {name}...")
        addresses = extract_addresses_from_transactions(contract, from_block, to_block)
        all_addresses.update(addresses)
        print(f"   ✅ {len(addresses)} addresses from {name}")

    # Save results
    output_file = "blockchain_whale_addresses.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'addresses': sorted(list(all_addresses)),
            'block_range': {'from': from_block, 'to': to_block}
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✅ EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")

    return list(all_addresses)


if __name__ == "__main__":
    main()
