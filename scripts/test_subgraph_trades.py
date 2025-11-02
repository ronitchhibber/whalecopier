"""
Test fetching trades from Polymarket's Subgraph (The Graph).
This is the proper way to get on-chain trade data.
"""

import requests
import json
from datetime import datetime

# Polymarket Subgraph endpoint
SUBGRAPH_URL = "https://api.thegraph.com/subgraphs/name/polymarket/matic-positions"

# Test query to get recent trades for a whale
def get_whale_trades(address, limit=10):
    """Fetch recent trades for a whale from The Graph."""

    query = """
    query GetTrades($address: String!, $limit: Int!) {
      trades(
        first: $limit
        orderBy: timestamp
        orderDirection: desc
        where: {user: $address}
      ) {
        id
        user {
          id
        }
        market {
          id
          question
        }
        outcomeIndex
        type
        shares
        price
        amount
        timestamp
      }
    }
    """

    variables = {
        "address": address.lower(),
        "limit": limit
    }

    response = requests.post(
        SUBGRAPH_URL,
        json={'query': query, 'variables': variables},
        timeout=30
    )

    if response.status_code == 200:
        return response.json()
    else:
        return {'error': f'Status {response.status_code}'}

print("\n" + "=" * 80)
print("🔍 TESTING POLYMARKET SUBGRAPH FOR WHALE TRADES")
print("=" * 80)

# Test with top whale address
test_address = "0x17db3fcd93ba12d38382a0cade24b200185c5f6d"  # fengdubiying

print(f"\nFetching trades for: {test_address[:20]}...")

result = get_whale_trades(test_address, limit=5)

print(f"\nResponse status: {200 if 'data' in result else 'Error'}")
print(f"Response: {json.dumps(result, indent=2)[:500]}...")

if 'data' in result and 'trades' in result['data']:
    trades = result['data']['trades']
    print(f"\n✅ Found {len(trades)} trades!")

    if len(trades) > 0:
        print("\nSample trade:")
        trade = trades[0]
        print(f"  Type: {trade.get('type')}")
        print(f"  Shares: {trade.get('shares')}")
        print(f"  Price: {trade.get('price')}")
        print(f"  Amount: {trade.get('amount')}")
        timestamp = int(trade.get('timestamp', 0))
        print(f"  Time: {datetime.fromtimestamp(timestamp)}")
        print(f"  Market: {trade.get('market', {}).get('question', 'N/A')[:60]}...")
else:
    print("\n⚠️  No trades found or API error")

print("\n" + "=" * 80)
