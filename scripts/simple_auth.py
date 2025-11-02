"""
Simple Polymarket Authentication (No external library needed)
Works with Python 3.9.6+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import secrets
from eth_account import Account
from eth_account.messages import encode_structured_data
from dotenv import load_dotenv, set_key

load_dotenv()

def generate_or_get_wallet():
    """Generate new wallet or use existing"""
    existing_key = os.getenv("POLYMARKET_PRIVATE_KEY")

    if existing_key and existing_key.startswith("0x"):
        print("\n✅ Found existing private key in .env")
        account = Account.from_key(existing_key)
        print(f"   Address: {account.address}")

        use_it = input("\nUse this wallet? (y/n): ").strip().lower()
        if use_it == 'y':
            return existing_key, account.address

    print("\n🔑 Generating new Ethereum wallet...")
    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)

    print(f"✅ Wallet generated!")
    print(f"   Address: {account.address}")
    print(f"   Private Key: {private_key}")
    print("\n⚠️  Save this private key securely!")

    return private_key, account.address

def sign_clob_auth(private_key, address):
    """Sign EIP-712 message for CLOB authentication"""
    print("\n🔐 Signing authentication message...")

    account = Account.from_key(private_key)
    timestamp = str(int(__import__('time').time()))
    nonce = 0

    # EIP-712 structured data
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "ClobAuth": [
                {"name": "address", "type": "address"},
                {"name": "timestamp", "type": "string"},
                {"name": "nonce", "type": "uint256"},
                {"name": "message", "type": "string"},
            ]
        },
        "primaryType": "ClobAuth",
        "domain": {
            "name": "ClobAuthDomain",
            "version": "1",
            "chainId": 137,  # Polygon
        },
        "message": {
            "address": address,
            "timestamp": timestamp,
            "nonce": nonce,
            "message": "This message attests that I control the given wallet",
        }
    }

    # Sign the structured data
    signed_message = account.sign_message(encode_structured_data(structured_data))
    signature = signed_message.signature.hex()

    print("✅ Message signed successfully!")

    return signature, timestamp, nonce

def create_api_key(address, signature, timestamp, nonce):
    """Create API key via CLOB API"""
    print("\n📡 Creating API credentials...")

    url = "https://clob.polymarket.com/auth/api-key"

    headers = {
        "Content-Type": "application/json",
        "POLY_ADDRESS": address,
        "POLY_SIGNATURE": signature,
        "POLY_TIMESTAMP": str(timestamp),
        "POLY_NONCE": str(nonce),
    }

    try:
        response = requests.post(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print("✅ API credentials created!")
            print(f"   API Key: {data.get('apiKey', '')[:20]}...")

            return {
                'apiKey': data.get('apiKey'),
                'secret': data.get('secret'),
                'passphrase': data.get('passphrase')
            }
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def save_to_env(private_key, address, creds):
    """Save credentials to .env"""
    print("\n💾 Saving to .env...")

    try:
        set_key(".env", "POLYMARKET_PRIVATE_KEY", private_key)
        set_key(".env", "POLYMARKET_WALLET_ADDRESS", address)
        set_key(".env", "POLYMARKET_API_KEY", creds['apiKey'])
        set_key(".env", "POLYMARKET_API_SECRET", creds['secret'])
        set_key(".env", "POLYMARKET_API_PASSPHRASE", creds['passphrase'])

        print("✅ Credentials saved!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("🐋 POLYMARKET AUTHENTICATION (SIMPLE METHOD)")
    print("="*80)
    print("\nThis works with Python 3.9.6+ (no external library needed)")
    print("\n" + "="*80)

    # Step 1: Get wallet
    private_key, address = generate_or_get_wallet()

    # Step 2: Sign message
    try:
        signature, timestamp, nonce = sign_clob_auth(private_key, address)
    except Exception as e:
        print(f"\n❌ Failed to sign message: {e}")
        print("\nThis might be due to:")
        print("  - Invalid private key format")
        print("  - Missing eth-account library")
        print("\nTry: pip3 install eth-account web3")
        return

    # Step 3: Create API key
    creds = create_api_key(address, signature, timestamp, nonce)

    if not creds:
        print("\n❌ Failed to create API credentials")
        print("\n💡 This is likely because:")
        print("  1. Polymarket requires a registered account")
        print("  2. Need to use a wallet that's signed up on Polymarket.com")
        print("\n📖 See POLYMARKET_AUTH_GUIDE.md for full instructions")
        return

    # Step 4: Save
    if save_to_env(private_key, address, creds):
        print("\n" + "="*80)
        print("✅ AUTHENTICATION COMPLETE!")
        print("="*80)
        print("\n🎯 Next steps:")
        print("   1. Run: python3 scripts/fetch_realtime_trades.py --continuous")
        print("   2. View dashboard: http://localhost:5174")
        print("="*80 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
