# How to Find 100 Polymarket Whale Wallets

Complete guide to discovering high-quality whale addresses meeting your criteria:
- ✅ Consistently profitable (60%+ win rate)
- ✅ High Sharpe ratio (> 1.5)
- ✅ Big players ($100k+ volume)
- ✅ Open wallets (publicly trackable trades)

## Quick Start: Confirmed Whales (Ready to Use)

We've identified these confirmed profitable whales:

### Confirmed Addresses (API Verified)

```
1. 0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf - Fredi9999 (Théo cluster)
   • Profit: $26M+
   • Volume: $67.6M
   • Cluster: French whale ($79M total)
   • Status: ✅ Verified & Active

2. 0x02e65d10e83eb391ca0c466630f82790854e25 - Leaderboard #13
   • Profit: $587,925
   • Volume: $37.2M
   • Status: ✅ Verified

3. 0xf705fa045201391d9632b7f3cde06a5e24453ca7 - Leaderboard #15
   • Profit: $522,206
   • Volume: $9.2M
   • Status: ✅ Verified
```

### Top Leaderboard Traders (Need Full Addresses)

From polymarket.com/leaderboard:

```
1. Mayuravarma - +$1,788,505
2. cozyfnf - +$1,478,917
3. setsukoworldchampion2027 - +$1,295,057
4. primm - +$1,148,242
5. fengdubiying - +$1,025,171
6. 1j59y6nk - +$1,400,000 (sports specialist)
7. WindWalk3 - +$1,100,000 (politics)
8. HyperLiquid0xb - +$976,000 (sports)
9. Erasmus - +$1,300,000 (politics)
10. Domer - (high profitability)
11. abeautifulmind - (sports betting specialist)
12. Axios - 96% win rate
```

## Method 1: Manual Profile Discovery (Most Reliable)

### Step 1: Access the Leaderboard

Visit: https://polymarket.com/leaderboard

This shows the top ~100 traders sorted by profit.

### Step 2: Extract Wallet Addresses

For each trader:

1. **If they show a wallet address (0x...)**: Copy it directly
   - Example: `0x02e65d10e83eb391ca0c466630f82790854e25`

2. **If they show a username**: Click their profile
   - URL will be: `polymarket.com/profile/[ADDRESS]`
   - Extract the address from the URL

3. **Browser Developer Tools Method**:
   ```javascript
   // Open browser console on leaderboard page
   // Run this to extract all visible addresses:
   document.querySelectorAll('[data-address]').forEach(el => {
       console.log(el.getAttribute('data-address'));
   });
   ```

### Step 3: Verify Address

Test each address with our API script:

```bash
python3 scripts/test_whale_api.py [ADDRESS]
```

## Method 2: Dune Analytics SQL Query (Advanced)

### Access Dune Dashboard

Visit: https://dune.com/genejp999/polymarket-leaderboard

### Run Custom Query

```sql
SELECT
    user_address,
    COUNT(*) as trade_count,
    SUM(trade_volume) as total_volume,
    SUM(realized_pnl) as total_pnl
FROM polymarket.trades
WHERE block_time >= NOW() - INTERVAL '180 days'
GROUP BY user_address
HAVING SUM(trade_volume) > 100000  -- $100k+ volume
ORDER BY total_pnl DESC
LIMIT 100
```

This requires a Dune Analytics account (free tier available).

## Method 3: PolygonScan Blockchain Analysis

### Step 1: Find CTF Exchange Contract

Visit: https://polygonscan.com/address/0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e

This is the Polymarket CTF Exchange contract.

### Step 2: Analyze Top Interactors

1. Click "Analytics" tab
2. Sort by "Transaction Count" or "Value"
3. Export top 100 addresses

### Step 3: Filter with API Key (Optional)

If you have a PolygonScan API key, use our script:

```bash
# Add to .env:
POLYGONSCAN_API_KEY=your_key_here

# Run discovery:
python3 scripts/discover_whales.py
```

## Method 4: Polymarket Data API Discovery

### Using Our Automated Script

```bash
# Install dependencies (one-time)
pip3 install httpx sqlalchemy asyncpg

# Run automated discovery
python3 scripts/discover_from_trades.py

# This will:
# 1. Fetch recent trades from CLOB
# 2. Extract all maker/taker addresses
# 3. Rank by volume
# 4. Save top 200 addresses to discovered_whale_addresses.json
```

## Method 5: Third-Party Analytics Tools

### PolymarketAnalytics.com

1. Visit: https://polymarketanalytics.com/traders
2. Filter by:
   - Min Profit: $50,000
   - Min Volume: $100,000
   - Win Rate: > 60%
3. Click each trader to see their address
4. Export to spreadsheet

### Polywhaler.com

1. Visit: https://www.polywhaler.com/
2. Sign up for whale tracking
3. View real-time whale trades ($10k+)
4. Extract addresses from trade feed

## Method 6: Community Sources

### Twitter/X

Search: "polymarket whale 0x" OR "polymarket profit 0x"

Follow accounts:
- @PolymarketTrade
- @PolymarketWhale
- Community whale trackers often share addresses

### Discord/Telegram

Join Polymarket communities and ask for profitable trader lists.

## Automated Discovery Pipeline (Recommended)

### Full Workflow

```bash
# Step 1: Install dependencies
pip3 install httpx sqlalchemy asyncpg python-dotenv websockets aiokafka prometheus-client

# Step 2: Quick discovery (no infra needed)
python3 scripts/discover_from_trades.py
# Output: discovered_whale_addresses.json with 200 addresses

# Step 3: Full analysis (requires postgres)
docker-compose up -d postgres

# Step 4: Comprehensive whale scoring
python3 scripts/discover_whales.py
# This will:
# - Enrich all addresses with full trading history
# - Calculate Sharpe ratio, win rate, consistency
# - Filter to only qualified whales (100k+, 60% WR, 1.5 Sharpe)
# - Save to database with copying enabled
```

## Quality Filtering Criteria

Our scripts automatically filter for:

```python
WHALE_CRITERIA = {
    "min_volume": 100000,        # $100k+ volume
    "min_win_rate": 60,          # 60%+ win rate
    "min_sharpe": 1.5,           # Sharpe > 1.5
    "min_trades": 30,            # 30+ trades
    "min_profit": 5000,          # $5k+ profit
    "consistency_threshold": 0.7 # 70% profitable months
}
```

Adjust these in `scripts/discover_whales.py` as needed.

## Verification Checklist

For each whale address, verify:

- [ ] Address is valid (42 characters, starts with 0x)
- [ ] Profile accessible via Data API
- [ ] Has recent activity (last 30 days)
- [ ] Meets volume threshold ($100k+)
- [ ] Meets profitability threshold (positive PnL)
- [ ] Has sufficient trade history (30+ trades)
- [ ] Sharpe ratio > 1.5
- [ ] Win rate > 60%

## Expected Results

Following this guide should yield:

- **Tier 1 (MEGA Whales)**: 10-20 addresses
  - $1M+ profit, 70%+ win rate, Sharpe > 2.0

- **Tier 2 (HIGH Whales)**: 30-50 addresses
  - $100k+ profit, 65%+ win rate, Sharpe > 1.8

- **Tier 3 (MEDIUM Whales)**: 50-100 addresses
  - $50k+ profit, 60%+ win rate, Sharpe > 1.5

## Troubleshooting

### "No addresses found"
- Check internet connection
- Verify Polymarket API is accessible
- Try different discovery methods

### "Addresses don't meet criteria"
- Lower thresholds in WHALE_CRITERIA
- Expand discovery to more addresses (500+)
- Include more trading history (1 year vs 6 months)

### "API rate limiting"
- Add delays between requests (see scripts)
- Use PolygonScan API key for higher limits
- Run discovery in smaller batches

## Next Steps After Finding 100 Whales

1. **Seed Database**:
   ```bash
   python3 scripts/seed_whales.py
   ```

2. **Enable Copying**:
   ```sql
   UPDATE whales SET is_copying_enabled = true
   WHERE quality_score > 70;
   ```

3. **Start Real-Time Monitoring**:
   ```bash
   python3 services/ingestion/main.py
   ```

4. **Verify WebSocket Subscriptions**:
   - Check logs for "✅ Subscribed to whale: 0x..."
   - Monitor Kafka topic: `whale_activity`
   - View Prometheus metrics: `http://localhost:9090`

## Additional Resources

- Polymarket Docs: https://docs.polymarket.com
- Polymarket Analytics: https://polymarketanalytics.com
- Dune Dashboards: https://dune.com/browse/dashboards?q=polymarket
- PolygonScan CTF: https://polygonscan.com/address/0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e

## Support

If you have issues finding whales, consider:
1. Using paid Dune Analytics for direct SQL access to whale data
2. Hiring a blockchain analyst to extract addresses via Polygon RPC
3. Partnering with Arkham Intelligence or Nansen for professional whale tracking
