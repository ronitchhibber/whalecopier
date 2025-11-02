"""
Setup CLOB API Authentication for Polymarket

This script helps you authenticate with Polymarket's CLOB API to fetch real trades.

Steps:
1. Generate API credentials
2. Create EIP-712 signature
3. Get API key
4. Store credentials securely

Usage: python3 scripts/setup_clob_auth.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from eth_account import Account
from eth_account.messages import encode_defunct
import secrets
from dotenv import load_dotenv, set_key

load_dotenv()

def generate_wallet():
    """Generate a new Ethereum wallet for API access"""
    print("\n🔐 Generating new Ethereum wallet for CLOB API...")
    print("=" * 80)

    # Generate private key
    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    print(f"✅ Wallet generated!")
    print(f"Address: {account.address}")
    print(f"Private Key: {private_key}")
    print("\n⚠️  IMPORTANT: Save this private key securely!")
    print("=" * 80)

    return private_key, account.address

def create_api_credentials(private_key, passphrase=""):
    """Create CLOB API credentials"""
    print("\n🔑 Creating CLOB API credentials...")

    account = Account.from_key(private_key)

    # CLOB API credential creation endpoint
    url = "https://clob.polymarket.com/auth/api-key"

    # Create nonce
    nonce = secrets.randbelow(1000000)

    # Create message to sign
    message = f"This request is for API Key creation\nNonce: {nonce}"

    # Sign message (EIP-191)
    message_hash = encode_defunct(text=message)
    signed_message = account.sign_message(message_hash)

    payload = {
        "address": account.address,
        "signature": signed_message.signature.hex(),
        "nonce": nonce,
        "passphrase": passphrase
    }

    try:
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            api_key = data.get('apiKey')
            api_secret = data.get('secret')
            api_passphrase = data.get('passphrase')

            print("✅ API credentials created successfully!")
            print(f"API Key: {api_key}")
            print(f"API Secret: {api_secret}")
            print(f"API Passphrase: {api_passphrase}")

            return api_key, api_secret, api_passphrase
        else:
            print(f"❌ Failed to create credentials: {response.status_code}")
            print(f"Response: {response.text}")
            return None, None, None

    except Exception as e:
        print(f"❌ Error creating credentials: {e}")
        return None, None, None

def save_credentials_to_env(private_key, address, api_key, api_secret, api_passphrase):
    """Save credentials to .env file"""
    print("\n💾 Saving credentials to .env...")

    env_file = ".env"

    try:
        set_key(env_file, "POLYMARKET_PRIVATE_KEY", private_key)
        set_key(env_file, "POLYMARKET_WALLET_ADDRESS", address)
        set_key(env_file, "POLYMARKET_API_KEY", api_key)
        set_key(env_file, "POLYMARKET_API_SECRET", api_secret)
        set_key(env_file, "POLYMARKET_API_PASSPHRASE", api_passphrase)

        print("✅ Credentials saved to .env file!")
        print("\n📝 Added environment variables:")
        print("  - POLYMARKET_PRIVATE_KEY")
        print("  - POLYMARKET_WALLET_ADDRESS")
        print("  - POLYMARKET_API_KEY")
        print("  - POLYMARKET_API_SECRET")
        print("  - POLYMARKET_API_PASSPHRASE")

    except Exception as e:
        print(f"❌ Error saving to .env: {e}")

def test_api_access(api_key, api_secret):
    """Test API access"""
    print("\n🧪 Testing API access...")

    url = "https://clob.polymarket.com/markets"

    headers = {
        "POLY-API-KEY": api_key,
        "POLY-SECRET": api_secret,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            print("✅ API access working! You can now fetch real trades.")
            return True
        else:
            print(f"⚠️  API returned {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False

def main():
    """Main setup flow"""
    print("\n" + "=" * 80)
    print("🚀 POLYMARKET CLOB API AUTHENTICATION SETUP")
    print("=" * 80)

    print("\nThis script will:")
    print("1. Generate a new Ethereum wallet (or use existing)")
    print("2. Create CLOB API credentials")
    print("3. Save credentials to .env file")
    print("4. Test API access")

    choice = input("\n\n📌 Do you want to:\n  1) Generate new wallet\n  2) Use existing wallet\n\nEnter choice (1 or 2): ").strip()

    if choice == "1":
        # Generate new wallet
        private_key, address = generate_wallet()

        save = input("\n💾 Save this wallet to .env? (y/n): ").strip().lower()
        if save == 'y':
            env_file = ".env"
            set_key(env_file, "POLYMARKET_PRIVATE_KEY", private_key)
            set_key(env_file, "POLYMARKET_WALLET_ADDRESS", address)
            print("✅ Wallet saved to .env")

    elif choice == "2":
        # Use existing wallet
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

        if not private_key:
            print("\n❌ No POLYMARKET_PRIVATE_KEY found in .env")
            private_key = input("Enter your private key (with 0x prefix): ").strip()

        account = Account.from_key(private_key)
        address = account.address
        print(f"\n✅ Using wallet: {address}")

    else:
        print("❌ Invalid choice")
        return

    # Create API credentials
    print("\n" + "=" * 80)
    api_key, api_secret, api_passphrase = create_api_credentials(private_key)

    if api_key:
        # Save to .env
        save_credentials_to_env(private_key, address, api_key, api_secret, api_passphrase)

        # Test access
        test_api_access(api_key, api_secret)

        print("\n" + "=" * 80)
        print("✅ SETUP COMPLETE!")
        print("=" * 80)
        print("\n🎯 Next steps:")
        print("1. Run: python3 scripts/fetch_realtime_trades.py --continuous")
        print("2. This will fetch REAL trades from Polymarket every minute")
        print("3. Check your dashboard at http://localhost:5174")
        print("\n" + "=" * 80)

    else:
        print("\n❌ Setup failed. Please check the errors above.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Setup cancelled by user")
