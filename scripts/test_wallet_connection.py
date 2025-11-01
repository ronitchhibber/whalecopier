#!/usr/bin/env python3
"""
Test Polymarket wallet connection with provided credentials.
Verifies that the API credentials work and can authenticate to the CLOB.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

print("=" * 80)
print("POLYMARKET WALLET CONNECTION TEST")
print("=" * 80)
print()

# Display configuration (masked)
private_key = os.getenv('POLYMARKET_PRIVATE_KEY', '')
address = os.getenv('POLYMARKET_ADDRESS', '')
api_key = os.getenv('POLYMARKET_API_KEY', '')
api_secret = os.getenv('POLYMARKET_API_SECRET', '')
api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE', '')

print(f"Wallet Address:  {address}")
print(f"Private Key:     {private_key[:10]}...{private_key[-10:] if len(private_key) > 20 else ''}")
print(f"API Key:         {api_key[:20]}..." if len(api_key) > 20 else f"API Key: {api_key}")
print(f"API Secret:      {api_secret[:10]}..." if len(api_secret) > 10 else f"API Secret: {api_secret}")
print(f"API Passphrase:  {api_passphrase[:10]}..." if len(api_passphrase) > 10 else f"API Passphrase: {api_passphrase}")
print()

# Test 1: Check if all credentials are present
print("Test 1: Checking credentials...")
if not all([private_key, address, api_key, api_secret, api_passphrase]):
    print("ERROR: Missing credentials!")
    print(f"  - Private Key: {'OK' if private_key else 'MISSING'}")
    print(f"  - Address: {'OK' if address else 'MISSING'}")
    print(f"  - API Key: {'OK' if api_key else 'MISSING'}")
    print(f"  - API Secret: {'OK' if api_secret else 'MISSING'}")
    print(f"  - API Passphrase: {'OK' if api_passphrase else 'MISSING'}")
    exit(1)

print("All credentials present!")
print()

# Test 2: Verify address format
print("Test 2: Verifying address format...")
if not address.startswith('0x') or len(address) != 42:
    print(f"ERROR: Invalid Ethereum address format: {address}")
    exit(1)
print(f"Address format valid: {address}")
print()

# Test 3: Test API connection (using public profile endpoint)
print("Test 3: Testing API connection...")
import requests

try:
    # Test public API first (no auth needed)
    url = f"https://gamma-api.polymarket.com/profile/{address}"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        profile = response.json()
        print(f"Profile found!")
        print(f"  - PnL: ${profile.get('pnl', 0):,.2f}")
        print(f"  - Total Volume: ${profile.get('totalVolume', 0):,.2f}")
        print(f"  - Total Trades: {profile.get('totalTrades', 0):,}")
        print(f"  - Markets Traded: {profile.get('marketsTraded', 0):,}")
    elif response.status_code == 404:
        print("Profile not found. This is normal for new addresses.")
        print("The address is valid but hasn't made any trades yet.")
    else:
        print(f"Unexpected response: {response.status_code}")
except Exception as e:
    print(f"Error fetching profile: {e}")

print()

# Test 4: Try to initialize CLOB client (requires py-clob-client)
print("Test 4: Testing CLOB client authentication...")
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON

    # Initialize client
    host = "https://clob.polymarket.com"
    chain_id = POLYGON  # 137 for Polygon

    client = ClobClient(
        host=host,
        key=private_key,
        chain_id=chain_id,
        # API credentials
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase
    )

    print("CLOB client initialized successfully!")

    # Test API call (get markets)
    try:
        markets = client.get_markets()
        print(f"Successfully fetched {len(markets)} markets from CLOB API")
        print("API authentication working!")
    except Exception as e:
        print(f"Error calling API: {e}")
        print("API credentials may be invalid")

except ImportError:
    print("py-clob-client not installed.")
    print("Install with: pip3 install py-clob-client")
    print()
    print("Once installed, you can use the CLOB API to:")
    print("  - Fetch individual trade data from whales")
    print("  - Place orders automatically")
    print("  - Monitor order book in real-time")
except Exception as e:
    print(f"Error initializing CLOB client: {e}")

print()
print("=" * 80)
print("CONNECTION TEST COMPLETE")
print("=" * 80)
print()
print("Next steps:")
print("1. Install py-clob-client: pip3 install py-clob-client")
print("2. The system can now use your credentials to connect to Polymarket")
print("3. Start the monitoring system from the dashboard")
print()
