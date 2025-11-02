"""
Test Etherscan API V2 to verify the API key works and understand the error.
"""

import requests
import json

ETHERSCAN_API_KEY = "W7K9R9J1JIJ6N37DM1QSIK1TTNFQEKCTYD"
ETHERSCAN_BASE_URL = "https://api.polygonscan.com/api"

print("\n" + "=" * 80)
print("🧪 TESTING ETHERSCAN API V2")
print("=" * 80)
print(f"API Key: {ETHERSCAN_API_KEY}")
print(f"Base URL: {ETHERSCAN_BASE_URL}\n")

# Test 1: Check API key status
print("Test 1: Account balance (verifies API key)")
print("-" * 80)

test_address = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Polymarket CTF contract

params = {
    "module": "account",
    "action": "balance",
    "address": test_address,
    "tag": "latest",
    "apikey": ETHERSCAN_API_KEY
}

response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=10)
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}\n")

# Test 2: Get transactions for CTF contract
print("Test 2: Get transactions for Polymarket CTF contract")
print("-" * 80)

params = {
    "module": "account",
    "action": "txlist",
    "address": test_address,
    "startblock": 0,
    "endblock": 99999999,
    "page": 1,
    "offset": 10,
    "sort": "desc",
    "apikey": ETHERSCAN_API_KEY
}

response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=10)
print(f"Status Code: {response.status_code}")
data = response.json()
print(f"Response Status: {data.get('status')}")
print(f"Response Message: {data.get('message')}")

if data.get('result'):
    if isinstance(data['result'], list):
        print(f"Number of transactions: {len(data['result'])}")
        if data['result']:
            print(f"Sample transaction: {json.dumps(data['result'][0], indent=2)}")
    else:
        print(f"Result: {data['result']}")
else:
    print("No results")

print()

# Test 3: Get ERC-1155 transfers
print("Test 3: Get ERC-1155 transfers")
print("-" * 80)

params = {
    "module": "account",
    "action": "token1155tx",
    "contractaddress": test_address,
    "page": 1,
    "offset": 10,
    "sort": "desc",
    "apikey": ETHERSCAN_API_KEY
}

response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=10)
print(f"Status Code: {response.status_code}")
data = response.json()
print(f"Response Status: {data.get('status')}")
print(f"Response Message: {data.get('message')}")

if data.get('result'):
    if isinstance(data['result'], list):
        print(f"Number of transfers: {len(data['result'])}")
        if data['result']:
            print(f"Sample transfer: {json.dumps(data['result'][0], indent=2)}")
    else:
        print(f"Result: {data['result']}")
else:
    print("No results")

print()

# Test 4: Try a known active Ethereum address for comparison
print("Test 4: Get transactions for a known active address (sanity check)")
print("-" * 80)

known_address = "0x0000000000000000000000000000000000001010"  # Polygon fee collector

params = {
    "module": "account",
    "action": "txlist",
    "address": known_address,
    "startblock": 0,
    "endblock": 99999999,
    "page": 1,
    "offset": 5,
    "sort": "desc",
    "apikey": ETHERSCAN_API_KEY
}

response = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=10)
print(f"Status Code: {response.status_code}")
data = response.json()
print(f"Response Status: {data.get('status')}")
print(f"Response Message: {data.get('message')}")

if data.get('result'):
    if isinstance(data['result'], list):
        print(f"Number of transactions: {len(data['result'])}")
    else:
        print(f"Result: {data['result']}")

print("\n" + "=" * 80)
print("✅ TESTS COMPLETE")
print("=" * 80)
