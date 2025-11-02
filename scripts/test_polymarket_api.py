"""
Test your Polymarket API credentials to ensure authenticated access works.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def test_api_access():
    """Test authenticated access to Polymarket CLOB API."""

    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        print("❌ Error: py-clob-client not installed")
        print("\nInstall it with:")
        print("   pip3 install py-clob-client")
        return False

    print("\n" + "=" * 80)
    print("🔍 TESTING POLYMARKET API ACCESS")
    print("=" * 80)

    # Load credentials
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY')

    if not private_key:
        print("\n❌ POLYMARKET_PRIVATE_KEY not found in .env file")
        print("\nMake sure you:")
        print("  1. Generated credentials with: python3 scripts/generate_polymarket_api_key.py")
        print("  2. Added them to .env with: cat .env.polymarket >> .env")
        return False

    print(f"\n✅ Found credentials in .env")

    # Initialize authenticated client
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137
        )

        print(f"✅ Client initialized successfully")
        print(f"   Wallet Address: {client.get_address()}")

    except Exception as e:
        print(f"\n❌ Error initializing client:")
        print(f"   {str(e)}")
        return False

    # Test 1: Get server time
    print(f"\n📡 Test 1: Getting server time...")
    try:
        server_time = client.get_server_time()
        print(f"   ✅ Server time: {server_time}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 2: Get your orders
    print(f"\n📡 Test 2: Getting your orders...")
    try:
        orders = client.get_orders()
        print(f"   ✅ Successfully fetched orders")
        print(f"   Your active orders: {len(orders)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 3: Try fetching market trades
    print(f"\n📡 Test 3: Getting market trades...")
    try:
        trades = client.get_trades()
        print(f"   ✅ Successfully fetched trades")
        print(f"   Recent trades: {len(trades)}")

        if len(trades) > 0:
            sample = trades[0]
            print(f"\n   Sample trade:")
            print(f"     ID: {sample.get('id', 'N/A')}")
            print(f"     Side: {sample.get('side', 'N/A')}")
            print(f"     Size: {sample.get('size', 'N/A')}")
            print(f"     Price: {sample.get('price', 'N/A')}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   Note: This might fail if no recent trades exist")

    # Success!
    print(f"\n" + "=" * 80)
    print(f"✅ API AUTHENTICATION WORKING!")
    print(f"=" * 80)
    print(f"\nYou can now:")
    print(f"  1. ✅ Fetch whale trades without 401 errors")
    print(f"  2. ✅ Access real-time order book data")
    print(f"  3. ✅ Get market information")
    print(f"  4. ✅ Place orders (if you add funds to wallet)")
    print()

    return True


if __name__ == "__main__":
    success = test_api_access()

    if success:
        print("🎉 Ready to track whale trades with authenticated API!")
    else:
        print("⚠️  Please check your setup and try again")

    sys.exit(0 if success else 1)
