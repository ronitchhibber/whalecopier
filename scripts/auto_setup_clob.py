"""
Automatic CLOB API Authentication Setup (Non-Interactive)
Generates wallet and CLOB credentials automatically
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
    """Generate a new Ethereum wallet"""
    print("\n🔐 Generating new Ethereum wallet for CLOB API...")

    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    print(f"✅ Wallet generated!")
    print(f"   Address: {account.address}")
    print(f"   Private Key: {private_key}")

    return private_key, account.address

def create_api_credentials(private_key, passphrase=""):
    """Create CLOB API credentials"""
    print("\n🔑 Creating CLOB API credentials...")

    account = Account.from_key(private_key)
    url = "https://clob.polymarket.com/auth/api-key"

    nonce = secrets.randbelow(1000000)
    message = f"This request is for API Key creation\nNonce: {nonce}"

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
            print(f"   API Key: {api_key[:20]}...")

            return api_key, api_secret, api_passphrase
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None, None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

def save_to_env(private_key, address, api_key, api_secret, api_passphrase):
    """Save credentials to .env"""
    print("\n💾 Saving credentials to .env...")

    env_file = ".env"

    try:
        set_key(env_file, "POLYMARKET_PRIVATE_KEY", private_key)
        set_key(env_file, "POLYMARKET_WALLET_ADDRESS", address)
        set_key(env_file, "POLYMARKET_API_KEY", api_key)
        set_key(env_file, "POLYMARKET_API_SECRET", api_secret)
        set_key(env_file, "POLYMARKET_API_PASSPHRASE", api_passphrase)

        print("✅ Credentials saved to .env file!")

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
            print("✅ API access working!")
            return True
        else:
            print(f"⚠️  API returned {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("🚀 AUTOMATIC POLYMARKET CLOB API SETUP")
    print("="*80)

    # Generate wallet
    private_key, address = generate_wallet()

    # Create API credentials
    api_key, api_secret, api_passphrase = create_api_credentials(private_key)

    if api_key:
        # Save to .env
        save_to_env(private_key, address, api_key, api_secret, api_passphrase)

        # Test access
        test_api_access(api_key, api_secret)

        print("\n" + "="*80)
        print("✅ SETUP COMPLETE!")
        print("="*80)
        print("\n🎯 Next steps:")
        print("1. Run: python3 scripts/fetch_realtime_trades.py --continuous")
        print("2. Real trades will be fetched every minute")
        print("3. View at http://localhost:5174")
        print("\n" + "="*80)

    else:
        print("\n❌ Setup failed. Please check errors above.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Setup cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
