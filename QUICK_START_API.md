# 🚀 Quick Start: Get Polymarket API Access

**Goal**: Get authenticated API access to track whale trades in real-time (no more 401 errors!)

**Time needed**: 5-10 minutes

---

## Step 1: Install Required Package

```bash
pip3 install py-clob-client
```

---

## Step 2: Get a Wallet (Choose One)

### Option A: Create New Test Wallet (Recommended)

```bash
# Creates a new Polygon wallet
python3 -c "from eth_account import Account; acc = Account.create(); print(f'Address: {acc.address}\nPrivate Key: {acc.key.hex()}')"
```

**Save both the address and private key somewhere safe!**

### Option B: Use Existing Wallet

If you have MetaMask or another wallet:
1. Go to Account Details
2. Export Private Key
3. Copy it (starts with 0x)

**⚠️ IMPORTANT**: You DON'T need funds in this wallet to READ data (only to trade)

---

## Step 3: Generate API Credentials

```bash
# Replace with YOUR actual private key
python3 scripts/generate_polymarket_api_key.py 0xYOUR_PRIVATE_KEY_HERE
```

**What this does:**
- Connects to Polymarket using your wallet
- Signs a message to prove you own the wallet
- Generates API key, secret, and passphrase
- Saves everything to `.env.polymarket`

**Expected output:**
```
🔐 POLYMARKET API CREDENTIAL GENERATOR
================================================================================

Initializing Polymarket client...
   Host: https://clob.polymarket.com
   Chain: Polygon (ID: 137)

✅ Connected successfully!
   Wallet Address: 0x1234...

🔑 Generating API credentials...

✅ API Credentials Generated Successfully!
   API Key:        abc123...
   API Secret:     def456... (hidden for security)
   API Passphrase: ghi789... (hidden for security)

💾 Credentials saved to: .env.polymarket
```

---

## Step 4: Add to Main .env File

```bash
# Append credentials to your main .env
cat .env.polymarket >> .env
```

---

## Step 5: Test API Access

```bash
python3 scripts/test_polymarket_api.py
```

**Expected output:**
```
🔍 TESTING POLYMARKET API ACCESS
================================================================================

✅ Found credentials in .env
✅ Client initialized successfully
   Wallet Address: 0x1234...

📡 Test 1: Getting server time...
   ✅ Server time: 2025-10-31T22:00:00Z

📡 Test 2: Getting your orders...
   ✅ Successfully fetched orders
   Your active orders: 0

📡 Test 3: Getting market trades...
   ✅ Successfully fetched trades
   Recent trades: 142

================================================================================
✅ API AUTHENTICATION WORKING!
================================================================================
```

---

## ✅ You're Done!

You now have authenticated API access! This means:

✅ **No more 401 errors** when fetching whale trades
✅ **Real-time access** to order book data
✅ **Can see all market trades** (not just position changes)
✅ **Optional**: Can place actual trades if you fund the wallet

---

## 🎯 Next Steps

### Update Engine to Use Authenticated API

The engine currently uses position tracking (Gamma API). To use the authenticated CLOB API for real-time trades, you would:

1. Update `src/copy_trading/engine.py` to use `ClobClient` instead of position tracking
2. Fetch whale trades directly from CLOB API with authentication
3. Get real-time updates instead of 5-minute polling

**Want me to implement this?** Just ask and I can update the engine to use the authenticated API!

---

## 📊 What You Can Access Now

### With Authenticated API:

```python
from py_clob_client.client import ClobClient
import os
from dotenv import load_dotenv

load_dotenv()

client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.getenv('POLYMARKET_PRIVATE_KEY'),
    chain_id=137
)

# Get all recent trades (no 401 error!)
trades = client.get_trades()

# Get specific whale's orders
whale_address = "0x17db3fcd93ba12d38382a0cade24b200185c5f6d"
# Filter trades for this whale
whale_trades = [t for t in trades if t.get('maker') == whale_address]

# Get order book for a market
order_book = client.get_order_book(token_id="...")

# Get your own orders
my_orders = client.get_orders()
```

---

## 🔒 Security Checklist

- [x] `.env.polymarket` added to `.gitignore`
- [x] Private key never shared or committed
- [x] Credentials stored in `.env` file (not hardcoded)
- [ ] Consider using separate wallet for API vs trading
- [ ] Keep backup of credentials somewhere safe

---

## ❓ Troubleshooting

### "POLYMARKET_PRIVATE_KEY not found in .env"
**Fix**: Run `cat .env.polymarket >> .env`

### "Invalid private key"
**Fix**: Make sure it starts with `0x` and is 66 characters long

### "Error connecting to Polymarket"
**Fix**: Check your internet connection and try again

### Still getting 401 errors?
**Fix**: Make sure you added credentials to `.env` and restarted the engine

---

## 💡 Pro Tips

1. **No Funds Needed**: You can read ALL data without any MATIC or funds in the wallet
2. **Rate Limits**: Be respectful of API rate limits (current engine checks every 5 minutes)
3. **Test First**: Always test with small amounts before automating real trades
4. **Separate Wallet**: Use different wallet for API access vs main trading funds

---

## 📚 Additional Resources

- [Full Setup Guide](./POLYMARKET_API_SETUP.md) - Detailed documentation
- [Polymarket Docs](https://docs.polymarket.com/) - Official API documentation
- [Python Client GitHub](https://github.com/Polymarket/py-clob-client) - Client source code

---

**Ready to upgrade your engine to use authenticated API? Just ask!** 🚀
