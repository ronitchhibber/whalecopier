"""
Use BitQuery GraphQL API (free tier, no key needed) to get Polymarket traders.
BitQuery indexes all blockchain data and provides easy queries.
"""

import requests
import json
import time

# BitQuery GraphQL endpoint (free, no key required)
BITQUERY_URL = "https://graphql.bitquery.io"

# Polymarket contracts
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E".lower()


def query_polymarket_traders(limit=1000, offset=0):
    """
    Query BitQuery for addresses that interacted with Polymarket contracts.
    """
    query = f"""
    {{
      ethereum(network: matic) {{
        smartContractCalls(
          smartContractAddress: {{is: "{CTF_EXCHANGE}"}}
          options: {{limit: {limit}, offset: {offset}}}
        ) {{
          caller {{
            address
          }}
          count
          amount: callDepth
        }}
      }}
    }}
    """

    try:
        response = requests.post(
            BITQUERY_URL,
            json={'query': query},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            calls = data.get('data', {}).get('ethereum', {}).get('smartContractCalls', [])

            addresses = []
            for call in calls:
                caller = call.get('caller', {})
                if caller and caller.get('address'):
                    addresses.append(caller['address'].lower())

            return addresses
        else:
            print(f"  ⚠️  BitQuery returned status {response.status_code}")
            return []

    except Exception as e:
        print(f"  ❌ BitQuery query failed: {e}")
        return []


def get_all_traders():
    """
    Paginate through BitQuery to get as many traders as possible.
    """
    print("\n" + "=" * 80)
    print("🔍 BITQUERY WHALE DISCOVERY")
    print("=" * 80)

    all_addresses = set()
    offset = 0
    batch_size = 1000

    while offset < 10000:  # Get up to 10k addresses
        print(f"\nQuerying batch {offset // batch_size + 1} (offset {offset})...")

        addresses = query_polymarket_traders(limit=batch_size, offset=offset)

        if not addresses:
            print("  No more results")
            break

        all_addresses.update(addresses)
        print(f"  ✅ Got {len(addresses)} addresses (total: {len(all_addresses)})")

        offset += batch_size
        time.sleep(2)  # Rate limiting

    # Save results
    output_file = "bitquery_whale_addresses.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total': len(all_addresses),
            'addresses': sorted(list(all_addresses))
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✅ DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total addresses: {len(all_addresses)}")
    print(f"Saved to: {output_file}")

    return list(all_addresses)


if __name__ == "__main__":
    get_all_traders()
