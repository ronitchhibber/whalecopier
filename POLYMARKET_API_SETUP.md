# 🔐 How to Get Polymarket API Credentials

Complete guide to setting up authenticated access to Polymarket's CLOB API for real-time trade tracking.

---

## Prerequisites

You'll need:
1. **A Polygon wallet** (with a private key)
2. **Python 3.8+** (already have this ✅)
3. **Some MATIC tokens** (for gas fees if you plan to trade)

---

## Step 1: Get a Polygon Wallet

### Option A: Create New Wallet (Recommended for Testing)

```bash
# Install web3.py if not already installed
pip3 install web3

# Create a new wallet
python3 -c "from eth_account import Account; acc = Account.create(); print(f'Address: {acc.address}\\nPrivate Key: {acc.key.hex()}')"
```

**⚠️ SECURITY**: Save your private key securely! Anyone with this key controls the wallet.

### Option B: Use Existing Wallet

If you already have a MetaMask or other wallet on Polygon, you can export the private key:
- MetaMask: Account Details → Export Private Key
- **Never share this key or commit it to git!**

---

## Step 2: Install Polymarket Python Client

```bash
# Install the official Polymarket CLOB client
pip3 install py-clob-client

# Also install web3 for wallet management
pip3 install web3 python-dotenv
```

---

## Step 3: Generate API Credentials

Create a script to generate your API credentials:

```python
# scripts/generate_polymarket_api_key.py

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
import json

def generate_api_credentials(private_key: str):
    """
    Generate Polymarket API credentials from your private key.

    Args:
        private_key: Your Polygon wallet private key (with 0x prefix)
    """

    # Initialize client
    host = "https://clob.polymarket.com"
    chain_id = 137  # Polygon Mainnet

    client = ClobClient(
        host,
        key=private_key,
        chain_id=chain_id
    )

    print("🔐 Generating API credentials...")
    print(f"   Wallet: {client.get_address()}")

    # Generate or derive API credentials
    # This uses your private key to sign a message and create API keys
    api_creds = client.create_or_derive_api_creds()

    print(f"\\n✅ API Credentials Generated!")
    print(f"   API Key: {api_creds.api_key}")
    print(f"   API Secret: {api_creds.api_secret[:10]}... (hidden)")
    print(f"   Passphrase: {api_creds.api_passphrase[:10]}... (hidden)")

    # Save to .env file
    env_content = f"""
# Polymarket API Credentials
POLYMARKET_PRIVATE_KEY={private_key}
POLYMARKET_ADDRESS={client.get_address()}
POLYMARKET_API_KEY={api_creds.api_key}
POLYMARKET_API_SECRET={api_creds.api_secret}
POLYMARKET_API_PASSPHRASE={api_creds.api_passphrase}
"""

    with open('.env.polymarket', 'w') as f:
        f.write(env_content)

    print(f"\\n💾 Credentials saved to: .env.polymarket")
    print(f"\\n⚠️  SECURITY NOTES:")
    print(f"   1. Add .env.polymarket to .gitignore")
    print(f"   2. Never share these credentials")
    print(f"   3. Keep your private key secure")

    return api_creds

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 generate_polymarket_api_key.py <YOUR_PRIVATE_KEY>")
        print("\\nOr set PRIVATE_KEY environment variable")
        sys.exit(1)

    private_key = sys.argv[1]

    # Ensure 0x prefix
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key

    generate_api_credentials(private_key)
```

### Run the script:

```bash
# Replace with your actual private key
python3 scripts/generate_polymarket_api_key.py 0xYOUR_PRIVATE_KEY_HERE
```

This will create a `.env.polymarket` file with your credentials.

---

## Step 4: Add Credentials to Main .env

```bash
# Append Polymarket credentials to main .env file
cat .env.polymarket >> .env

# Secure the file
chmod 600 .env
```

---

## Step 5: Test API Access

Create a test script:

```python
# scripts/test_polymarket_api.py

from py_clob_client.client import ClobClient
from dotenv import load_dotenv
import os

load_dotenv()

def test_api_access():
    """Test authenticated access to Polymarket CLOB API."""

    print("🔍 Testing Polymarket API Access...")

    # Load credentials
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY')

    if not private_key:
        print("❌ POLYMARKET_PRIVATE_KEY not found in .env")
        return False

    # Initialize authenticated client
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137
    )

    print(f"✅ Client initialized")
    print(f"   Address: {client.get_address()}")

    # Test: Get your own orders (will be empty if you haven't traded)
    try:
        orders = client.get_orders()
        print(f"\\n✅ API Authentication Working!")
        print(f"   Your orders: {len(orders)}")
        return True
    except Exception as e:
        print(f"\\n❌ API Error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_access()

    if success:
        print(f"\\n🎉 You're ready to track whale trades with authenticated API!")
    else:
        print(f"\\n⚠️  Check your credentials and try again")
```

---

## Step 6: Update Copy Trading Engine

Now you can fetch whale trades with authentication. Here's how to integrate it:

```python
# src/copy_trading/clob_tracker.py

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

class AuthenticatedCLOBTracker:
    """
    Tracks whale trades using authenticated CLOB API access.
    """

    def __init__(self):
        load_dotenv()

        private_key = os.getenv('POLYMARKET_PRIVATE_KEY')

        if not private_key:
            raise ValueError("POLYMARKET_PRIVATE_KEY not set in .env")

        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137
        )

        logger.info(f"✅ Authenticated CLOB client initialized")
        logger.info(f"   Address: {self.client.get_address()}")

    def get_whale_trades(self, whale_address: str, limit: int = 100):
        """
        Fetch recent trades for a specific whale address.

        With authentication, this will work without 401 errors!
        """
        try:
            # Query trades for this address
            # Note: The CLOB client provides various methods to query trades

            # Get market trades (this works with auth)
            trades = self.client.get_trades()  # Gets all recent trades

            # Filter for specific whale
            whale_trades = [
                t for t in trades
                if t.get('maker', '').lower() == whale_address.lower()
                or t.get('taker', '').lower() == whale_address.lower()
            ]

            return whale_trades[:limit]

        except Exception as e:
            logger.error(f"Error fetching trades for {whale_address[:10]}: {e}")
            return []

    def get_all_recent_trades(self):
        """Get all recent trades from the CLOB."""
        try:
            return self.client.get_trades()
        except Exception as e:
            logger.error(f"Error fetching all trades: {e}")
            return []
```

---

## 🔒 Security Best Practices

### 1. Add to .gitignore

```bash
echo ".env.polymarket" >> .gitignore
```

### 2. Use Environment Variables

Never hardcode credentials in your code. Always use environment variables.

### 3. Separate Wallets

Consider using a separate wallet for API access (not your main trading wallet).

### 4. Monitor Activity

Regularly check your wallet activity on Polygonscan.

---

## 📊 What You Can Do With Authenticated API

✅ **Get whale trades in real-time** (no more 401 errors!)
✅ **Access order book data**
✅ **See market liquidity**
✅ **Place orders** (if you want to auto-trade)
✅ **Get fills and order history**
✅ **Stream websocket updates**

---

## 🚀 Quick Start

```bash
# 1. Generate credentials
python3 scripts/generate_polymarket_api_key.py 0xYOUR_PRIVATE_KEY

# 2. Test access
python3 scripts/test_polymarket_api.py

# 3. Start tracking with authentication
python3 scripts/start_copy_trading.py
```

---

## 📚 Resources

- [Polymarket CLOB Docs](https://docs.polymarket.com/developers/CLOB/authentication)
- [Python Client GitHub](https://github.com/Polymarket/py-clob-client)
- [API Reference](https://docs.polymarket.com/)

---

## ⚠️ Important Notes

1. **Read-Only Access**: You don't need funds in the wallet to READ data, only to place trades
2. **Gas Fees**: If you plan to trade, keep some MATIC in the wallet
3. **Rate Limits**: Be respectful of API rate limits
4. **Testing**: Test on small amounts first if planning to auto-trade

---

*Last Updated: October 31, 2025*
