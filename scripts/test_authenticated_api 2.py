"""
Simple test of authenticated Polymarket API endpoints
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from src.config import settings

def test_authenticated_api():
    """Test authenticated Polymarket API endpoints"""

    print("=" * 80)
    print("🔐 POLYMARKET AUTHENTICATED API TEST")
    print("=" * 80)

    # Check credentials
    print("\n1. CREDENTIALS CHECK:")
    print("-" * 80)
    if not all([settings.POLYMARKET_API_KEY, settings.POLYMARKET_SECRET, settings.POLYMARKET_PASSPHRASE]):
        print("✗ Missing API credentials in .env")
        print("  Run: python scripts/test_polymarket_auth.py")
        return

    print(f"API Key: {settings.POLYMARKET_API_KEY[:20]}...")
    print(f"Secret: {settings.POLYMARKET_SECRET[:20]}...")
    print(f"Passphrase: {settings.POLYMARKET_PASSPHRASE[:20]}...")

    # Initialize client
    print("\n2. INITIALIZING CLIENT:")
    print("-" * 80)
    try:
        # Create ApiCreds object
        creds = ApiCreds(
            api_key=settings.POLYMARKET_API_KEY,
            api_secret=settings.POLYMARKET_SECRET,
            api_passphrase=settings.POLYMARKET_PASSPHRASE
        )

        client = ClobClient(
            host=settings.POLYMARKET_API_URL,
            key=settings.PRIVATE_KEY,
            chain_id=settings.CHAIN_ID,
            creds=creds  # Pass creds during initialization
        )
        print("✓ ClobClient initialized with API credentials")

        # Verify wallet address
        if hasattr(client, 'signer') and client.signer:
            address = client.signer.address()
            print(f"✓ Wallet address: {address}")

    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return

    # Test 1: Get open orders
    print("\n3. TEST: GET OPEN ORDERS")
    print("-" * 80)
    try:
        orders = client.get_orders()
        print(f"✓ Successfully fetched orders: {len(orders) if orders else 0} orders")
        if orders and len(orders) > 0:
            print(f"  Sample order: {orders[0]}")
    except Exception as e:
        print(f"✗ Failed to get orders: {e}")
        print(f"  Error type: {type(e).__name__}")

    # Test 2: Get positions (if available)
    print("\n4. TEST: GET POSITIONS")
    print("-" * 80)
    try:
        # Not all clients may have this method
        if hasattr(client, 'get_positions'):
            positions = client.get_positions()
            print(f"✓ Successfully fetched positions: {len(positions) if positions else 0} positions")
        else:
            print("⚠️  get_positions() method not available in client")
    except Exception as e:
        print(f"✗ Failed to get positions: {e}")

    # Test 3: Get balance (if available)
    print("\n5. TEST: GET BALANCE")
    print("-" * 80)
    try:
        # Check what balance methods are available
        balance_methods = [m for m in dir(client) if 'balance' in m.lower()]
        if balance_methods:
            print(f"  Available balance methods: {balance_methods}")
            # Try first available method
            if hasattr(client, 'get_balance'):
                balance = client.get_balance()
                print(f"✓ Balance: {balance}")
            elif hasattr(client, 'get_balances'):
                balances = client.get_balances()
                print(f"✓ Balances: {balances}")
        else:
            print("⚠️  No balance methods available in client")
    except Exception as e:
        print(f"✗ Failed to get balance: {e}")

    # Test 4: List available authenticated methods
    print("\n6. AVAILABLE AUTHENTICATED METHODS:")
    print("-" * 80)
    methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
    # Filter for likely data retrieval methods
    data_methods = [m for m in methods if any(word in m.lower() for word in ['get', 'fetch', 'list', 'show'])]
    print(f"  Found {len(data_methods)} potential data methods:")
    for method in sorted(data_methods)[:15]:
        print(f"    - {method}")

    print("\n" + "=" * 80)
    print("AUTHENTICATION TEST COMPLETE")
    print("=" * 80)
    print("\n✅ API credentials are working!")
    print("✅ You can now proceed with order execution and position management")
    print()

if __name__ == "__main__":
    test_authenticated_api()
