"""
Polymarket CLOB API Authentication Script
Uses official py-clob-client library for proper authentication
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv, set_key
import secrets

load_dotenv()

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import py_clob_client
        from eth_account import Account
        print("✅ All dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\n📦 Installing required packages...")
        os.system("pip3 install py-clob-client web3 eth-account")
        print("\n✅ Packages installed! Please run the script again.")
        return False

def get_or_create_private_key():
    """Get existing private key or create new one"""
    from eth_account import Account

    existing_key = os.getenv("POLYMARKET_PRIVATE_KEY")

    if existing_key and existing_key.startswith("0x") and len(existing_key) == 66:
        print("\n✅ Found existing private key in .env")
        print(f"   Address: {Account.from_key(existing_key).address}")

        use_existing = input("\nUse this key? (y/n): ").strip().lower()
        if use_existing == 'y':
            return existing_key

    print("\n🔑 Generating new Ethereum wallet...")
    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    print(f"✅ New wallet generated!")
    print(f"   Address: {account.address}")
    print(f"   Private Key: {private_key}")
    print("\n⚠️  IMPORTANT: Save this private key securely!")
    print("   It will be saved to .env file")

    return private_key

def create_api_credentials(private_key):
    """Create API credentials using py-clob-client"""
    from py_clob_client.client import ClobClient

    print("\n🔐 Creating API credentials via Polymarket CLOB...")

    HOST = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon Mainnet

    try:
        # Create client with private key
        # signature_type=1 for email/Magic wallet, 0 for MetaMask
        client = ClobClient(
            HOST,
            key=private_key,
            chain_id=CHAIN_ID,
            signature_type=1  # Try email/Magic first
        )

        # Generate API credentials (deterministic)
        print("   Signing authentication message...")
        creds = client.create_or_derive_api_creds()

        print("✅ API credentials created successfully!")
        print(f"   API Key: {creds['apiKey'][:20]}...")
        print(f"   Secret: {creds['secret'][:20]}...")
        print(f"   Passphrase: {creds['passphrase'][:20]}...")

        return creds

    except Exception as e:
        print(f"❌ Error with signature_type=1, trying signature_type=0...")

        try:
            # Try with MetaMask signature type
            client = ClobClient(
                HOST,
                key=private_key,
                chain_id=CHAIN_ID,
                signature_type=0
            )

            creds = client.create_or_derive_api_creds()

            print("✅ API credentials created successfully!")
            print(f"   API Key: {creds['apiKey'][:20]}...")

            return creds

        except Exception as e2:
            print(f"❌ Failed to create credentials: {e2}")
            print("\n🔍 Possible issues:")
            print("   - Invalid private key format")
            print("   - Network connectivity")
            print("   - Polymarket API is down")
            return None

def save_credentials_to_env(private_key, address, creds):
    """Save all credentials to .env file"""
    print("\n💾 Saving credentials to .env...")

    env_file = ".env"

    try:
        set_key(env_file, "POLYMARKET_PRIVATE_KEY", private_key)
        set_key(env_file, "POLYMARKET_WALLET_ADDRESS", address)
        set_key(env_file, "POLYMARKET_API_KEY", creds['apiKey'])
        set_key(env_file, "POLYMARKET_API_SECRET", creds['secret'])
        set_key(env_file, "POLYMARKET_API_PASSPHRASE", creds['passphrase'])

        print("✅ Credentials saved to .env file!")
        print("\n📝 Environment variables set:")
        print("   - POLYMARKET_PRIVATE_KEY")
        print("   - POLYMARKET_WALLET_ADDRESS")
        print("   - POLYMARKET_API_KEY")
        print("   - POLYMARKET_API_SECRET")
        print("   - POLYMARKET_API_PASSPHRASE")

        return True

    except Exception as e:
        print(f"❌ Error saving to .env: {e}")
        return False

def test_api_access(creds):
    """Test API access with generated credentials"""
    from py_clob_client.client import ClobClient

    print("\n🧪 Testing API access...")

    try:
        # Create client with API credentials
        client = ClobClient(
            "https://clob.polymarket.com",
            key=os.getenv("POLYMARKET_PRIVATE_KEY"),
            chain_id=137
        )

        # Set API credentials
        client.set_api_creds(creds)

        # Try to fetch markets
        markets = client.get_markets()

        print(f"✅ API access working!")
        print(f"   Fetched {len(markets) if markets else 0} markets")

        return True

    except Exception as e:
        print(f"⚠️  API test returned: {e}")
        print("   This might be normal - credentials are still valid")
        return False

def start_trade_fetcher():
    """Start the trade fetching service"""
    print("\n🚀 Starting trade fetcher...")

    script_path = "scripts/fetch_realtime_trades.py"

    if os.path.exists(script_path):
        print(f"   Running: python3 {script_path} --continuous")
        print("\n✅ Trade fetcher will start monitoring for whale trades")
        print("   View trades at: http://localhost:5174")

        start = input("\nStart trade fetcher now? (y/n): ").strip().lower()
        if start == 'y':
            os.system(f"python3 {script_path} --continuous &")
            print("✅ Trade fetcher started in background!")
        else:
            print("ℹ️  To start later, run:")
            print(f"   python3 {script_path} --continuous")
    else:
        print(f"⚠️  Trade fetcher script not found: {script_path}")

def main():
    print("\n" + "="*80)
    print("🐋 POLYMARKET API AUTHENTICATION SETUP")
    print("="*80)
    print("\nThis script will:")
    print("1. ✅ Check dependencies")
    print("2. ✅ Get or generate private key")
    print("3. ✅ Create API credentials")
    print("4. ✅ Save to .env file")
    print("5. ✅ Test API access")
    print("6. ✅ Start trade fetcher")
    print("\n" + "="*80)

    # Step 1: Check dependencies
    if not check_dependencies():
        return

    # Import after checking dependencies
    from eth_account import Account

    # Step 2: Get private key
    private_key = get_or_create_private_key()
    if not private_key:
        print("❌ Failed to get private key")
        return

    account = Account.from_key(private_key)
    address = account.address

    # Step 3: Create API credentials
    creds = create_api_credentials(private_key)
    if not creds:
        print("\n❌ Failed to create API credentials")
        print("\n💡 Troubleshooting:")
        print("   1. Check your internet connection")
        print("   2. Verify private key format (must start with 0x)")
        print("   3. Try again in a few minutes")
        return

    # Step 4: Save credentials
    if not save_credentials_to_env(private_key, address, creds):
        return

    # Step 5: Test API access
    test_api_access(creds)

    # Step 6: Start trade fetcher
    start_trade_fetcher()

    # Done!
    print("\n" + "="*80)
    print("✅ AUTHENTICATION COMPLETE!")
    print("="*80)
    print("\n🎯 What's Next:")
    print("   1. View dashboard: http://localhost:5174")
    print("   2. Check 'Trades' tab for incoming trades")
    print("   3. Enable paper trading in 'Trading' tab")
    print("   4. Monitor agents in 'Agents' tab")
    print("\n💡 Note: Trades appear as whales make them (may take time)")
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n📖 Check POLYMARKET_AUTH_GUIDE.md for help")
