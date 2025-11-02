#!/usr/bin/env python3
"""
Simple test script for The Graph API connection
"""

import requests
import json

def test_graph_connection():
    """Test connection to The Graph Protocol"""

    print("=" * 60)
    print("Testing connection to The Graph Protocol...")
    print("=" * 60)

    # Orderbook subgraph endpoint
    url = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"

    # Simple test query to get latest order filled event
    query = """
    {
        orderFilledEvents(first: 1, orderBy: timestamp, orderDirection: desc) {
            id
            taker
            maker
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
            timestamp
            transactionHash
        }
    }
    """

    try:
        # Make request
        response = requests.post(
            url,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            if "errors" in data:
                print(f"✗ GraphQL errors: {data['errors']}")
                return False

            if "data" in data and data["data"].get("orderFilledEvents"):
                event = data["data"]["orderFilledEvents"][0]
                print("✓ Connection successful!")
                print("\nLatest order filled event:")
                print(f"  ID: {event['id'][:20]}...")
                print(f"  Taker: {event['taker']}")
                print(f"  Maker: {event['maker']}")
                print(f"  Maker Amount: {event['makerAmountFilled']}")
                print(f"  Taker Amount: {event['takerAmountFilled']}")
                print(f"  Timestamp: {event['timestamp']}")

                # Convert timestamp
                from datetime import datetime
                dt = datetime.fromtimestamp(int(event['timestamp']))
                print(f"  Date: {dt.isoformat()}")

                return True
            else:
                print("✗ No data returned")
                return False

        else:
            print(f"✗ HTTP {response.status_code}: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("✗ Request timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_alternative_endpoints():
    """Test alternative Graph endpoints"""

    print("\n" + "=" * 60)
    print("Testing alternative endpoints...")
    print("=" * 60)

    endpoints = [
        ("Conditional Tokens", "https://api.thegraph.com/subgraphs/name/polymarket/conditional-tokens-gnosis"),
        ("Orderbook Alt", "https://api.thegraph.com/subgraphs/name/polymarket/orderbook"),
    ]

    simple_query = """
    {
        _meta {
            block {
                number
            }
        }
    }
    """

    for name, url in endpoints:
        print(f"\nTesting {name}...")
        print(f"  URL: {url}")

        try:
            response = requests.post(
                url,
                json={"query": simple_query},
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    print(f"  ✓ Connected! Block: {data.get('data', {}).get('_meta', {}).get('block', {}).get('number', 'N/A')}")
                else:
                    print(f"  ✗ No data returned")
            else:
                print(f"  ✗ HTTP {response.status_code}")

        except Exception as e:
            print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    # Test main endpoint
    success = test_graph_connection()

    # Test alternatives
    test_alternative_endpoints()

    print("\n" + "=" * 60)
    if success:
        print("✓ GRAPH API TEST PASSED")
        print("Ready to fetch historical data!")
    else:
        print("✗ GRAPH API TEST FAILED")
        print("Please check network connection and endpoints")
    print("=" * 60)