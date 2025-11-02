#!/usr/bin/env python3
"""
Test The Graph API connection and basic query
"""
import os
from dotenv import load_dotenv
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

# Load environment variables
load_dotenv()

print('=' * 80)
print('THE GRAPH API CONNECTION TEST')
print('=' * 80)
print()

# Get API key from environment
API_KEY = os.getenv("GRAPH_API_KEY")
if not API_KEY:
    print("❌ GRAPH_API_KEY not found in environment")
    print("   Make sure .env file is loaded")
    exit(1)

print(f"✅ API key found: {API_KEY[:20]}...")
print()

# Test all three Polymarket subgraphs
subgraphs = {
    "Orderbook": "7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY",
    "PNL": "6c58N5U4MtQE2Y8njfVrrAfRykzfqajMGeTMEvMmskVz",
    "Activity": "Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp"
}

for name, subgraph_id in subgraphs.items():
    print(f"Testing {name} subgraph...")
    print(f"  ID: {subgraph_id}")

    url = f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{subgraph_id}"

    try:
        transport = RequestsHTTPTransport(url=url)
        client = Client(transport=transport, fetch_schema_from_transport=False)

        # Query depends on subgraph type
        if name == "Orderbook":
            query = gql("""
            {
              orderFilledEvents(first: 5, orderBy: timestamp, orderDirection: desc) {
                id
                timestamp
                taker
                tradeAmount
              }
            }
            """)
        elif name == "PNL":
            query = gql("""
            {
              conditions(first: 5) {
                id
                payoutNumerators
              }
            }
            """)
        else:  # Activity
            query = gql("""
            {
              tokenOperations(first: 5) {
                id
                timestamp
              }
            }
            """)

        result = client.execute(query)
        print(f"  ✅ Connected successfully!")
        print(f"  Sample data: {len(result[list(result.keys())[0]])} records fetched")
        print()

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        print()

print('=' * 80)
print('CONNECTION TEST COMPLETE')
print('=' * 80)
