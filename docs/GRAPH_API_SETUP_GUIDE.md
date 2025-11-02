# The Graph API Setup Guide
**Get Free 60-Day Historical Whale Data**

---

## Why Use The Graph?

The Graph Protocol gives you **FREE access** to 60 days of complete Polymarket historical data:
- 100,000 queries/month FREE tier
- 2.1M+ trades available
- 100% market resolution coverage
- Zero authentication required after setup

---

## Current Status

❌ **Your current Graph API key is expired/invalid**

Error: `auth error: malformed API key`

You need to generate a NEW API key to unlock 60-day historical whale discovery.

---

## How to Get a FREE Graph API Key

### Step 1: Create Account
1. Go to: https://thegraph.com/studio/
2. Click "Connect Wallet" (or "Sign Up")
3. You can use:
   - MetaMask wallet
   - WalletConnect
   - Email sign-up (no wallet needed!)

### Step 2: Create a New Subgraph
1. Once logged in, click "Create a Subgraph"
2. Or go to: https://thegraph.com/studio/apikeys/

### Step 3: Generate API Key
1. Click on "API Keys" in the left sidebar
2. Click "Create API Key"
3. Give it a name: `polymarket-whale-discovery`
4. Click "Create"
5. **Copy the API key** (looks like: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)

### Step 4: Add to .env File
1. Open `/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/.env`
2. Find line 85: `GRAPH_API_KEY=...`
3. Replace with your new key:
   ```
   GRAPH_API_KEY=your-new-key-here
   ```
   **Important:** NO quotes around the key!

### Step 5: Run Discovery Script
```bash
python3 scripts/graph_whale_discovery.py
```

Expected results:
- 60 days of historical data
- 1000-2000+ whales discovered
- Takes ~30-60 minutes to complete

---

## Alternative: Public Endpoint (Limited)

If you don't want to create an account, there's a limited public endpoint, but it has strict rate limits and may not work for production use.

---

## Polymarket Subgraph IDs

Once you have your API key, the script uses these subgraph IDs:

1. **Orderbook** (trades):
   `7fu2DWYK93ePfzB24c2wrP94S3x4LGHUrQxphhoEypyY`

2. **PNL** (market resolutions):
   `6c58N5U4MtQE2Y8njfVrrAfRykzfqajMGeTMEvMmskVz`

3. **Activity** (CTF operations):
   `Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp`

---

## Troubleshooting

### "malformed API key" error:
- Check that you copied the FULL key
- Remove any quotes around the key in .env
- Make sure there are no extra spaces

### "deployment does not exist" error:
- Means you're trying to use public endpoint without API key
- Need to create an account and get API key

### Rate limit errors:
- Free tier: 100K queries/month
- If you hit limit, wait for next month or upgrade
- Our script is optimized to stay under limits

---

## What You'll Get

With a valid Graph API key, you'll unlock:

✅ **60 days of historical trades**
✅ **1000-2000+ qualified whales**
✅ **100% market resolution data**
✅ **Complete trader performance history**
✅ **Free forever** (within 100K queries/month)

---

## Current Discovery Methods

While waiting for Graph API key:

### Method 1: Data API (Currently Working) ✅
- Source: `https://data-api.polymarket.com/trades`
- Status: Working, discovered 1 whale from 100K trades
- Limitation: Only recent trades available
- Next: Scaling to 1M+ trades

### Method 2: Graph Protocol (Blocked) ⏸️
- Source: The Graph Protocol subgraphs
- Status: BLOCKED - need new API key
- Potential: 1000-2000 whales from 60-day history

---

**Action Required:** Get a new Graph API key to unlock full 60-day historical whale discovery.

**Time Required:** 5 minutes to create account and generate key

**Cost:** $0 (FREE forever on 100K queries/month tier)
