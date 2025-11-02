# Quick Authentication Steps

## ⚡ IMPORTANT: Authentication is OPTIONAL

**Good News!** The whale copy-trading system works **WITHOUT authentication** for:
- ✅ Fetching real-time trades (uses public Data API)
- ✅ Viewing trades in dashboard
- ✅ Tracking whale activity
- ✅ Analyzing markets

**Authentication ONLY needed for:**
- ❌ Placing actual trades on Polymarket
- ❌ Copying whale trades automatically (live trading)

## 🚀 Quick Start (No Auth Needed)

### Step 1: Start Trade Fetcher
```bash
python3 scripts/fetch_realtime_trades.py --continuous --interval 60 &
```

### Step 2: View Dashboard
```
http://localhost:5174
```

**That's it!** Trades are now flowing in automatically every 60 seconds.

---

## 🔐 Optional: Setup Authentication (For Live Trading)

Only follow these steps if you want to **place actual trades** on Polymarket.

### Step 1: Install Library
```bash
pip3 install py-clob-client
```

### Step 2: Run Authentication Script
```bash
python3 scripts/polymarket_authenticate.py
```

### Step 3: Follow Prompts
- Script will generate a wallet (or use yours)
- Creates API credentials automatically
- Saves everything to `.env`

**Note:** This enables LIVE trading. Use paper trading mode first!

---

## 📱 What You'll See

### During Setup:
```
🐋 POLYMARKET API AUTHENTICATION SETUP
================================================================================
1. ✅ Check dependencies
2. ✅ Get or generate private key
3. ✅ Create API credentials
4. ✅ Save to .env file
5. ✅ Test API access
6. ✅ Start trade fetcher
================================================================================

🔑 Generating new Ethereum wallet...
✅ New wallet generated!
   Address: 0x1234...5678
   Private Key: 0xabcd...ef01

🔐 Creating API credentials via Polymarket CLOB...
   Signing authentication message...
✅ API credentials created successfully!
   API Key: a1b2c3d4...
   Secret: x9y8z7w6...
   Passphrase: p0o9i8u7...

💾 Saving credentials to .env...
✅ Credentials saved to .env file!

🧪 Testing API access...
✅ API access working!

🚀 Starting trade fetcher...
✅ Trade fetcher started in background!

================================================================================
✅ AUTHENTICATION COMPLETE!
================================================================================
```

### After Setup:
- Go to http://localhost:5174
- Click "Trades" tab
- Wait for whale trades to appear
- Enable paper trading in "Trading" tab

---

## 🔑 Using Your Own Wallet (Optional)

If you have an existing Polymarket account:

### Option A: Export from MetaMask
1. Open MetaMask
2. Click 3 dots → Account Details
3. Export Private Key
4. Enter password
5. Copy key (starts with `0x`)

### Option B: Export from Magic Link
1. Go to https://reveal.magic.link/polymarket
2. Log in with your email
3. Click "Reveal Private Key"
4. Copy key

### Then:
```bash
# Add to .env before running script
echo 'POLYMARKET_PRIVATE_KEY=0xyour_key_here' >> .env

# Run authentication
python3 scripts/polymarket_authenticate.py
```

---

## ✅ Verify It's Working

### Check .env file:
```bash
cat .env | grep POLYMARKET
```

Should show:
```
POLYMARKET_PRIVATE_KEY=0x...
POLYMARKET_WALLET_ADDRESS=0x...
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_API_PASSPHRASE=...
```

### Check trades are coming in:
```bash
# After a few minutes, check database
psql postgresql://trader:trader_password@localhost:5432/polymarket_trader \
  -c "SELECT COUNT(*) FROM trades WHERE timestamp > NOW() - INTERVAL '1 hour';"
```

### Check dashboard:
- http://localhost:5174 → Trades tab
- Should see trades appearing (if whales are active)

---

## 🆘 Troubleshooting

### "Module not found: py_clob_client"
```bash
pip3 install py-clob-client web3 eth-account
```

### "Invalid L1 Request headers"
- Make sure private key is correct format (starts with `0x`, 66 chars)
- Script tries both signature types automatically

### "No trades appearing"
- Normal! Whales trade intermittently
- Check after 30-60 minutes
- Verify fetcher is running: `ps aux | grep fetch_realtime`

### "401 Unauthorized"
```bash
# Regenerate credentials
rm .env
python3 scripts/polymarket_authenticate.py
```

---

## 📚 Full Documentation

For detailed information:
- **Full Guide:** `POLYMARKET_AUTH_GUIDE.md`
- **API Status:** `POLYMARKET_API_STATUS.md`
- **Trade Setup:** `GETTING_REAL_TRADES.md`

---

## 🎉 You're Done!

Your whale copy-trading system is now LIVE and fetching real trades from Polymarket!

**Next:** Explore the dashboard at http://localhost:5174
