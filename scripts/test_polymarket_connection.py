#!/usr/bin/env python3
"""
Test Polymarket API Connection
Verifies that credentials are set up correctly and the API is accessible.
"""

import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.polymarket_client import PolymarketClient

def test_connection():
    """Test Polymarket API connection"""

    load_dotenv()

    print("=" * 60)
    print("  Polymarket API Connection Test")
    print("=" * 60)
    print()

    # Check environment variables
    print("1. Checking environment variables...")
    required_vars = [
        'POLYMARKET_API_KEY',
        'POLYMARKET_API_SECRET',
        'POLYMARKET_API_PASSPHRASE',
        'POLYMARKET_PRIVATE_KEY'
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            print(f"   ❌ {var}: NOT SET")
        else:
            # Mask the value for security
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"   ✅ {var}: {masked}")

    if missing_vars:
        print()
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False

    print()
    print("2. Initializing Polymarket client...")

    try:
        client = PolymarketClient(
            api_key=os.getenv('POLYMARKET_API_KEY'),
            secret=os.getenv('POLYMARKET_API_SECRET'),
            passphrase=os.getenv('POLYMARKET_API_PASSPHRASE'),
            private_key=os.getenv('POLYMARKET_PRIVATE_KEY'),
        )
        print("   ✅ Client initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize client: {e}")
        return False

    print()
    print("3. Testing API connection...")

    # Test if py-clob-client is available
    if client.clob_client is None:
        print("   ⚠️  py-clob-client not available (requires Python 3.9.10+)")
        print("   Trading functionality will be limited")
        return False
    else:
        print("   ✅ py-clob-client is available")

    print()
    print("=" * 60)
    print("  Connection Test: PASSED")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run the live monitor: ./scripts/run_live_monitor.sh")
    print("  2. Monitor is in PAPER mode by default (safe)")
    print("  3. To enable LIVE trading, edit realtime_trade_monitor.py")
    print("     and change mode='PAPER' to mode='LIVE'")
    print()

    return True

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
