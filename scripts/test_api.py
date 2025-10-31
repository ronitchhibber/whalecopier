#!/usr/bin/env python3
"""
Quick test script to verify Polymarket API connectivity
Run this after setting up your .env file
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.polymarket_client import PolymarketClient
from src.config import settings


async def test_api():
    """Test basic API functionality"""
    print("🧪 Testing Polymarket API Client")
    print("=" * 50)
    print()

    # Check credentials
    print("📋 Checking configuration...")
    if not settings.PRIVATE_KEY:
        print("❌ Error: PRIVATE_KEY not set in .env")
        return False

    if not settings.WALLET_ADDRESS:
        print("❌ Error: WALLET_ADDRESS not set in .env")
        return False

    print(f"   Wallet: {settings.WALLET_ADDRESS[:10]}...{settings.WALLET_ADDRESS[-8:]}")
    print(f"   Chain ID: {settings.CHAIN_ID}")
    print(f"   API URL: {settings.POLYMARKET_API_URL}")
    print("   ✅ Configuration loaded")
    print()

    try:
        async with PolymarketClient() as client:
            # Test 1: Get active markets
            print("🧪 Test 1: Fetching active markets...")
            markets = await client.get_markets(active=True, limit=5)
            print(f"   ✅ Found {len(markets)} active markets")

            if markets:
                first_market = markets[0]
                print(f"   Example: {first_market.get('question', 'N/A')[:60]}...")
            print()

            # Test 2: Get whale trades
            print("🧪 Test 2: Fetching whale trades (>$10k)...")
            whale_trades = await client.get_whale_trades(min_trade_size=10000, limit=10)
            print(f"   ✅ Found {len(whale_trades)} large trades")

            if whale_trades:
                first_trade = whale_trades[0]
                print(f"   Example: {first_trade.get('side')} {first_trade.get('size')} @ ${first_trade.get('price')}")
            print()

            # Test 3: Get recent trades
            print("🧪 Test 3: Fetching recent trades...")
            recent_trades = await client.get_trades(limit=5)
            print(f"   ✅ Found {len(recent_trades)} recent trades")
            print()

            # Test 4: Get price data (if we have a market)
            if markets:
                print("🧪 Test 4: Fetching price data...")
                token_id = markets[0].get('tokens', [{}])[0].get('token_id')

                if token_id:
                    try:
                        midpoint = client.get_midpoint(token_id)
                        print(f"   ✅ Midpoint price: ${midpoint:.4f}")
                    except Exception as e:
                        print(f"   ⚠️  Could not fetch price: {e}")
                print()

            print("=" * 50)
            print("✨ All tests passed! API client is working.")
            print()
            print("📝 Next steps:")
            print("   1. Start the infrastructure: ./scripts/start.sh")
            print("   2. Initialize database: docker-compose exec postgres psql -U trader -d polymarket_trader")
            print("   3. Begin whale data collection")
            print()
            return True

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Troubleshooting:")
        print("   - Verify your .env file has correct credentials")
        print("   - Check if Polymarket API is accessible")
        print("   - Ensure your wallet address is correct")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_api())
    sys.exit(0 if success else 1)
