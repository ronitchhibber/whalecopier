# Polymarket API Authentication - Step-by-Step Guide

## Overview

Polymarket uses a **2-tier authentication system**:
1. **Level 1 (L1)**: Your private key - Controls funds, signs orders
2. **Level 2 (L2)**: API credentials - For routine API calls without exposing private key

**Important:** Your private key NEVER leaves your machine. The API credentials are derived deterministically.

---

## 🚀 Quick Start (Easiest Path)

### Step 1: Get Your Private Key

You have **3 options**:

#### Option A: Use Existing Polymarket Wallet (Recommended)

If you already have a Polymarket account:

1. **For Email/Magic Link users:**
   - Go to https://reveal.magic.link/polymarket
   - Log in with your email
   - Click "Reveal Private Key"
   - Copy the private key (starts with `0x`)

2. **For MetaMask/WalletConnect users:**
   - Open MetaMask
   - Click the 3 dots → Account Details
   - Click "Export Private Key"
   - Enter password
   - Copy the private key

#### Option B: Create New Wallet (For Testing)

```bash
# We'll generate one automatically in Step 2
# Skip to Step 2
```

#### Option C: Use Test Private Key (Demo Only)

```bash
# DO NOT use this for real trading - for demo purposes only
PRIVATE_KEY="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
```

---

### Step 2: Run Our Authentication Script

We've created an easy script that does everything for you:

```bash
cd /Users/ronitchhibber/Desktop/Whale.Trader-v0.1

# Install required library (if not installed)
pip3 install py-clob-client

# Run the authentication script
python3 scripts/polymarket_authenticate.py
```

**The script will:**
1. ✅ Check if you have a private key
2. ✅ Generate one if needed (or use yours)
3. ✅ Create API credentials via py-clob-client
4. ✅ Save to `.env` file automatically
5. ✅ Test API access
6. ✅ Start fetching trades

---

### Step 3: Verify It's Working

After running the script:

1. **Check `.env` file:**
```bash
cat .env | grep POLYMARKET
```

You should see:
```bash
POLYMARKET_PRIVATE_KEY=0x...
POLYMARKET_WALLET_ADDRESS=0x...
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_API_PASSPHRASE=...
```

2. **Check trades are fetching:**
```bash
# View recent trades in database
psql postgresql://trader:trader_password@localhost:5432/polymarket_trader \
  -c "SELECT COUNT(*) FROM trades;"
```

3. **View in dashboard:**
   - Go to http://localhost:5174
   - Click "Trades" tab
   - You should see real trades appearing

---

## 📖 Manual Setup (Advanced)

If you prefer to do it manually:

### Step 1: Install py-clob-client

```bash
pip3 install py-clob-client
```

### Step 2: Create Credentials Script

Save this as `create_creds.py`:

```python
from py_clob_client.client import ClobClient

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon Mainnet
PRIVATE_KEY = "<your-private-key-here>"  # Replace this

# Create client
client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=1  # Use 1 for email/Magic, 0 for MetaMask
)

# Generate API credentials (deterministic - same key = same creds)
creds = client.create_or_derive_api_creds()

print(f"API Key: {creds['apiKey']}")
print(f"Secret: {creds['secret']}")
print(f"Passphrase: {creds['passphrase']}")
```

### Step 3: Run and Save Credentials

```bash
python3 create_creds.py
```

Copy the output to `.env`:

```bash
POLYMARKET_PRIVATE_KEY=0xyour_private_key
POLYMARKET_API_KEY=the_api_key_from_output
POLYMARKET_API_SECRET=the_secret_from_output
POLYMARKET_API_PASSPHRASE=the_passphrase_from_output
```

### Step 4: Start Trade Fetcher

```bash
python3 scripts/fetch_realtime_trades.py --continuous
```

---

## 🔍 Understanding the Authentication

### What Happens Behind the Scenes:

1. **Your private key** signs an EIP-712 message:
   ```
   "This message attests that I control the given wallet"
   ```

2. **Polymarket server** verifies the signature and generates:
   - API Key (like a username)
   - API Secret (like a password)
   - Passphrase (encryption key)

3. **Deterministic generation** means:
   - Same private key = Same API credentials every time
   - You can regenerate them anytime

4. **Your private key NEVER** goes to Polymarket servers
   - Only the signature is sent
   - Your funds are safe

### Security Notes:

✅ **Good Practices:**
- Keep private key in `.env` file (never commit to git)
- Use `.gitignore` to exclude `.env`
- API credentials can be revoked and regenerated
- Different private key = Different account

❌ **Don't:**
- Share your private key
- Commit `.env` to version control
- Use production keys for testing
- Reuse keys across projects (for production)

---

## 🛠️ Troubleshooting

### Issue 1: "Invalid L1 Request headers"

**Cause:** Wrong signature format or chain ID

**Fix:**
```python
# Make sure using Chain ID 137 (Polygon)
CHAIN_ID = 137

# And correct signature type:
signature_type=1  # For email/Magic wallet
# OR
signature_type=0  # For MetaMask/hardware wallet
```

### Issue 2: "401 Unauthorized" on API calls

**Cause:** API credentials not set correctly

**Fix:**
```bash
# Regenerate credentials
python3 scripts/polymarket_authenticate.py

# Check they're in .env
cat .env | grep POLYMARKET
```

### Issue 3: No trades appearing

**Possible causes:**
1. Whales aren't trading right now (normal)
2. API credentials expired
3. Trade fetcher not running

**Fix:**
```bash
# Check if fetcher is running
ps aux | grep fetch_realtime

# Restart if needed
python3 scripts/fetch_realtime_trades.py --continuous &
```

### Issue 4: Module not found error

**Cause:** py-clob-client not installed

**Fix:**
```bash
pip3 install py-clob-client web3 eth-account
```

---

## 📊 Expected Behavior

### Immediate (0-5 minutes):
- ✅ API credentials generated
- ✅ Credentials saved to `.env`
- ✅ Trade fetcher starts
- ✅ Connects to CLOB API successfully

### Short-term (5-60 minutes):
- ⏳ Fetcher checks for trades every minute
- ⏳ May not find whale trades immediately (depends on activity)
- ⏳ Dashboard updates every 5 seconds

### Long-term (1+ hours):
- ✅ Trades accumulate in database
- ✅ Dashboard shows real activity
- ✅ Paper trading can execute
- ✅ Agents analyze patterns

**Note:** If no trades appear after 1 hour, your tracked whales may not be actively trading. This is normal! Whale trading is intermittent.

---

## 🎯 Next Steps After Authentication

Once authenticated and trades are flowing:

### 1. Enable Paper Trading
```bash
# Go to http://localhost:5174
# Click "Trading" tab
# Click "Start Paper Trading"
# System will automatically copy whale trades
```

### 2. Monitor Agents
```bash
# Click "Agents" tab
# View all 6 agents
# Check their metrics
# Execute agent tasks
```

### 3. Analyze Performance
```bash
# Check whale rankings
# Review trade patterns
# Monitor P&L attribution
# Adjust copy trading settings
```

---

## 📞 Support

**If you get stuck:**

1. Check `POLYMARKET_AUTH_GUIDE.md` (this file)
2. Check `POLYMARKET_API_STATUS.md` for status
3. Review `GETTING_REAL_TRADES.md` for alternatives
4. Check official docs: https://docs.polymarket.com/developers/CLOB/authentication

**For issues with:**
- Private key export → Contact your wallet provider
- API generation → Check Chain ID (must be 137)
- Trade fetching → Verify credentials in `.env`
- Dashboard → Check console for errors

---

## ✨ You're All Set!

Once you complete these steps:
- ✅ Your system will fetch real trades
- ✅ Paper trading will work
- ✅ All 6 agents will analyze data
- ✅ Dashboard will show live activity

**The whale copy-trading system is now LIVE!** 🐋📈
