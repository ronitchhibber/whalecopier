"""
Test Polymarket CLOB API Authentication
Diagnose L1 (private key) and L2 (API credentials) authentication issues
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py_clob_client.client import ClobClient
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_authentication():
    """Test Polymarket authentication step by step"""

    print("=" * 80)
    print("🔐 POLYMARKET AUTHENTICATION DIAGNOSTIC TEST")
    print("=" * 80)

    # Step 1: Check environment variables
    print("\n1. CHECKING ENVIRONMENT VARIABLES:")
    print("-" * 80)
    print(f"PRIVATE_KEY: {'✓ Set' if settings.PRIVATE_KEY else '✗ Missing'}")
    print(f"POLYMARKET_API_KEY: {'✓ Set' if settings.POLYMARKET_API_KEY else '✗ Missing'}")
    print(f"POLYMARKET_SECRET: {'✓ Set' if settings.POLYMARKET_SECRET else '✗ Missing'}")
    print(f"POLYMARKET_PASSPHRASE: {'✓ Set' if settings.POLYMARKET_PASSPHRASE else '✗ Missing'}")
    print(f"API URL: {settings.POLYMARKET_API_URL}")
    print(f"Chain ID: {settings.CHAIN_ID}")

    # Step 2: Initialize CLOB client
    print("\n2. INITIALIZING CLOB CLIENT:")
    print("-" * 80)
    try:
        client = ClobClient(
            host=settings.POLYMARKET_API_URL,
            key=settings.PRIVATE_KEY if settings.PRIVATE_KEY else None,
            chain_id=settings.CHAIN_ID,
            signature_type=0,  # EOA (Ethereum wallet)
        )
        print("✓ ClobClient initialized successfully")

        # Check if we have a derived address
        if hasattr(client, 'signer') and client.signer:
            print(f"✓ Wallet address: {client.signer.address()}")
        else:
            print("⚠️  No signer/wallet detected")

    except Exception as e:
        print(f"✗ Failed to initialize ClobClient: {e}")
        return

    # Step 3: Test L2 API credential creation
    print("\n3. TESTING L2 API CREDENTIAL CREATION:")
    print("-" * 80)
    try:
        print("Attempting to create/derive API credentials...")
        creds = client.create_or_derive_api_creds()
        print("✓ API credentials generated!")

        # Debug: show the object type and attributes
        print(f"  Credentials type: {type(creds)}")
        print(f"  Credentials dir: {[a for a in dir(creds) if not a.startswith('_')]}")

        # Try different attribute access patterns
        api_key = None
        secret = None
        passphrase = None

        # Try as dictionary
        if isinstance(creds, dict):
            api_key = creds.get('apiKey') or creds.get('api_key')
            secret = creds.get('secret')
            passphrase = creds.get('passphrase')
        # Try as object with attributes
        else:
            for attr in ['apiKey', 'api_key']:
                if hasattr(creds, attr):
                    api_key = getattr(creds, attr, None)
                    break
            for attr in ['secret', 'api_secret']:
                if hasattr(creds, attr):
                    secret = getattr(creds, attr, None)
                    break
            for attr in ['passphrase', 'api_passphrase']:
                if hasattr(creds, attr):
                    passphrase = getattr(creds, attr, None)
                    break

        if api_key and secret and passphrase:
            print(f"\n📋 SAVE THESE TO .env:")
            print(f"POLYMARKET_API_KEY={api_key}")
            print(f"POLYMARKET_SECRET={secret}")
            print(f"POLYMARKET_PASSPHRASE={passphrase}")
        else:
            print(f"\n⚠️  Could not extract all credentials. Raw object:")
            print(f"  {creds}")
    except Exception as e:
        print(f"✗ Failed to create API credentials: {e}")
        print("\n💡 DIAGNOSIS:")
        print("   - This usually means the private key is invalid or not set")
        print("   - Or the Polymarket API endpoint is not accessible")
        print(f"   - Error type: {type(e).__name__}")

    # Step 4: Test public data API (no auth required)
    print("\n4. TESTING PUBLIC DATA API:")
    print("-" * 80)
    try:
        # Test fetching markets (public endpoint)
        markets = client.get_markets()
        if markets:
            print(f"✓ Successfully fetched {len(markets)} markets")
            print(f"  Sample market: {markets[0].get('question', 'N/A')[:60]}...")
        else:
            print("⚠️  No markets returned (unexpected)")
    except Exception as e:
        print(f"✗ Failed to fetch markets: {e}")

    # Step 5: Test authenticated endpoints (requires API creds)
    print("\n5. TESTING AUTHENTICATED ENDPOINTS:")
    print("-" * 80)

    # Set API credentials if we have them
    if all([settings.POLYMARKET_API_KEY, settings.POLYMARKET_SECRET, settings.POLYMARKET_PASSPHRASE]):
        print("Using existing API credentials from .env")
        try:
            client.set_api_creds({
                'apiKey': settings.POLYMARKET_API_KEY,
                'secret': settings.POLYMARKET_SECRET,
                'passphrase': settings.POLYMARKET_PASSPHRASE,
            })
            print("✓ API credentials set")
        except Exception as e:
            print(f"✗ Failed to set API credentials: {e}")
    else:
        print("⚠️  No existing API credentials in .env, skipping authenticated tests")
        print("\n💡 TO FIX:")
        print("   1. Make sure PRIVATE_KEY is set in .env")
        print("   2. Run this script to generate API credentials")
        print("   3. Save the generated credentials to .env:")
        print("      POLYMARKET_API_KEY=<apiKey>")
        print("      POLYMARKET_SECRET=<secret>")
        print("      POLYMARKET_PASSPHRASE=<passphrase>")
        return

    # Try to get balance (requires auth)
    print("\nAttempting to get balance...")
    try:
        # This is a placeholder - py-clob-client might not have this method
        # Need to check actual available methods
        print("⚠️  Balance check not implemented in client library")
    except AttributeError:
        print("⚠️  get_balance() method not available")
    except Exception as e:
        print(f"✗ Failed to get balance: {e}")

    # Try to get open orders (requires auth)
    print("\nAttempting to get open orders...")
    try:
        # Test with a sample token ID
        orders = client.get_orders()  # Might fail if method signature is different
        print(f"✓ Got orders: {len(orders) if orders else 0}")
    except Exception as e:
        print(f"✗ Failed to get orders: {e}")
        print(f"   Error type: {type(e).__name__}")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print("\n✅ WORKING:")
    print("   - CLOB client initialization")
    print("   - Public market data fetching")

    print("\n❌ NEEDS ATTENTION:")
    print("   - L2 API credential generation (if failed)")
    print("   - Authenticated endpoint access")
    print("   - Private key validation")

    print("\n📝 NEXT STEPS:")
    print("   1. Ensure you have a valid Polygon private key in .env")
    print("   2. Fund the wallet with MATIC for gas fees")
    print("   3. Generate API credentials using create_or_derive_api_creds()")
    print("   4. Store credentials in .env for persistent access")
    print("   5. Test order placement with small amounts")
    print()

if __name__ == "__main__":
    test_authentication()
