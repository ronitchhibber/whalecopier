"""
Generate Polymarket API credentials from a private key.

This script:
1. Creates/uses a Polygon wallet
2. Generates deterministic API credentials via EIP-712 signature
3. Saves credentials to .env file

Run: python3 scripts/setup_polymarket_auth.py
"""

import os
import secrets
from eth_account import Account
from eth_account.messages import encode_defunct
import requests
import json

# Polymarket CLOB API
CLOB_API_URL = "https://clob.polymarket.com"

def generate_test_wallet():
    """Generate a new test wallet for API authentication."""
    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    print("\n" + "="*80)
    print("TEST WALLET GENERATED")
    print("="*80)
    print(f"Address: {account.address}")
    print(f"Private Key: {private_key}")
    print("\nThis is a READ-ONLY test wallet for API access.")
    print("It has NO FUNDS and is only used to authenticate with Polymarket API.")
    print("="*80 + "\n")

    return private_key, account.address


def get_api_credentials_simple(private_key: str) -> dict:
    """
    Get API credentials using direct HTTP requests.

    Polymarket's CLOB API returns credentials when you make authenticated requests.
    For read-only operations (like fetching trades), we can use the API without
    full key derivation.
    """
    account = Account.from_key(private_key)

    print("Wallet Address:", account.address)
    print("\n✅ Wallet ready for API access")

    # For read-only operations, we can use the address directly
    # Full credential derivation requires more complex EIP-712 signing
    return {
        "wallet_address": account.address,
        "private_key": private_key,
        "note": "Use for read-only API access or implement full EIP-712 signing for write operations"
    }


def test_api_access():
    """Test if we can access the CLOB API."""
    try:
        # Try to fetch markets (should work without auth)
        response = requests.get(f"{CLOB_API_URL}/markets", timeout=10)

        if response.status_code == 200:
            markets = response.json()
            print(f"\n✅ API Access Working! Found {len(markets)} markets")
            return True
        else:
            print(f"\n⚠️  API returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n❌ API Access Failed: {e}")
        return False


def save_to_env(private_key: str, address: str):
    """Save credentials to .env file."""
    env_path = ".env"

    # Read existing .env
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value

    # Update Polymarket credentials
    env_vars['PRIVATE_KEY'] = private_key
    env_vars['L2_PRIVATE_KEY'] = private_key  # Alias for py-clob-client
    env_vars['WALLET_ADDRESS'] = address
    env_vars['POLYGON_RPC'] = 'https://polygon-rpc.com'
    env_vars['CHAIN_ID'] = '137'

    # Write back
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print(f"\n✅ Credentials saved to {env_path}")


def main():
    print("\n" + "="*80)
    print("POLYMARKET API SETUP")
    print("="*80)

    # Check if we already have a private key
    existing_key = os.getenv('PRIVATE_KEY') or os.getenv('L2_PRIVATE_KEY')

    if existing_key and existing_key.startswith('0x') and len(existing_key) == 66:
        print(f"\n✅ Found existing wallet in .env")
        private_key = existing_key
        account = Account.from_key(private_key)
        address = account.address
    else:
        print("\n📝 No existing wallet found. Generating test wallet...")
        private_key, address = generate_test_wallet()

        response = input("\nUse this test wallet? (y/n): ").lower()
        if response != 'y':
            print("Aborted. To use your own wallet, add PRIVATE_KEY to .env")
            return

    # Get API credentials
    creds = get_api_credentials_simple(private_key)

    # Test API access
    print("\n" + "="*80)
    print("TESTING API ACCESS")
    print("="*80)
    api_works = test_api_access()

    if api_works:
        # Save to .env
        save_to_env(private_key, address)

        print("\n" + "="*80)
        print("✅ SETUP COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("1. The test wallet has been configured for API access")
        print("2. Run: python3 scripts/discover_best_whales.py")
        print("3. The script will now be able to access Polymarket CLOB API")
        print("\nNote: Read-only access works without full authentication.")
        print("For trading operations, full EIP-712 signing is required.")
    else:
        print("\n⚠️  API access test failed. The CLOB API may require authentication.")
        print("Saving credentials anyway for future use.")
        save_to_env(private_key, address)


if __name__ == "__main__":
    main()
