# How to Get 1000 Whales Automatically

## Quick Start (30-60 minutes)

### Step 1: Get Free PolygonScan API Key (2 minutes)

1. Visit: https://polygonscan.com/apis
2. Click "Register" (free)
3. Verify email
4. Generate API key

### Step 2: Add API Key to Environment

```bash
cd /Users/ronitchhibber/polymarket-copy-trader

# Add to .env file
echo "POLYGONSCAN_API_KEY=YOUR_API_KEY_HERE" >> .env
```

### Step 3: Install Dependencies

```bash
# Install Python dependencies
pip3 install httpx sqlalchemy asyncpg python-dotenv

# Or install all project dependencies
pip3 install -e ".[dev]"
```

### Step 4: Start Database

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Wait for it to be ready (10 seconds)
sleep 10

# Initialize database schema
# (Skip this if you've already run it)
pip3 install alembic psycopg2-binary
alembic upgrade head
```

### Step 5: Run 1000 Whale Discovery

```bash
python3 scripts/discover_1000_whales.py
```

## What Happens

The script will:

1. **Phase 1: Address Discovery** (5-10 minutes)
   - Scans 10,000+ PolygonScan CTF Exchange transactions
   - Fetches 5,000+ recent CLOB trades
   - Analyzes 20 high-volume markets
   - **Result**: 2,000-3,000 unique addresses

2. **Phase 2: Enrichment & Qualification** (20-40 minutes)
   - Enriches each address via Polymarket API
   - Calculates: volume, win rate, Sharpe ratio, consistency
   - Filters to only qualified whales
   - **Progress displayed every batch**

3. **Phase 3: Database Insertion** (1-2 minutes)
   - Deduplicates addresses
   - Saves to database
   - Enables copying automatically
   - **Result**: 1,000 qualified whales ready

## Expected Output

```
================================================================================
MASS WHALE DISCOVERY - TARGET: 1000 WHALES
================================================================================

📋 Relaxed Criteria for Volume:
  • Min Volume: $50,000
  • Min Win Rate: 55%
  • Min Sharpe: 1.2
  • Min Trades: 20
  • Min Profit: $1,000

================================================================================
PHASE 1: ADDRESS DISCOVERY
================================================================================

METHOD 1: POLYGONSCAN BLOCKCHAIN ANALYSIS
  Page 1: +1000 txs (total addresses: 342)
  Page 2: +1000 txs (total addresses: 687)
  ...
  Page 10: +1000 txs (total addresses: 2,134)

✅ PolygonScan: Found 2,134 unique addresses

METHOD 2: CLOB RECENT TRADES
  Page 10: Total addresses: 456
  Page 20: Total addresses: 892
  ...
  Page 50: Total addresses: 1,847

✅ CLOB Trades: Found 1,847 unique addresses

METHOD 3: HIGH-VOLUME MARKETS
  [1/20] Will Trump win the 2024 election?...
    +100 trades (total addresses: 78)
  ...
  [20/20] Will Fed cut rates in December?...
    +95 trades (total addresses: 423)

✅ Markets: Found 423 unique addresses

================================================================================
✅ TOTAL UNIQUE ADDRESSES DISCOVERED: 3,289
================================================================================

================================================================================
PHASE 2: ENRICHMENT & QUALIFICATION
================================================================================

Processing 3,289 addresses in 66 batches of 50...

[Batch 1/66] Processing 50 addresses...
  ✅ +12 qualified whales (Total: 12)

[Batch 2/66] Processing 50 addresses...
  ✅ +8 qualified whales (Total: 20)

...

[Batch 25/66] Processing 50 addresses...
  ✅ +19 qualified whales (Total: 486)
  💾 Progress saved

...

[Batch 42/66] Processing 50 addresses...
  ✅ +23 qualified whales (Total: 1,003)

🎯 Reached target of 1000 whales!

================================================================================
PHASE 3: DATABASE INSERTION
================================================================================

✅ Saved 1,000 new whales to database

================================================================================
DISCOVERY SUMMARY
================================================================================
Addresses Discovered: 3,289
Addresses Processed: 2,100
Qualified Whales: 1,003
Saved to Database: 1,000

Tier Breakdown:
  MEGA:   47
  HIGH:   312
  MEDIUM: 641

Top 10 Whales by Quality Score:
--------------------------------------------------------------------------------
 1. MegaWhale2024            - Score:  92.3 - $  5,234,567 - WR: 73.2%
 2. Fredi9999                - Score:  91.8 - $ 67,668,524 - WR: 65.0%
 3. SharpTrader              - Score:  89.5 - $  3,421,890 - WR: 71.5%
 4. ConsistentWinner         - Score:  87.2 - $  2,156,743 - WR: 68.9%
 5. HighVolumePlayer         - Score:  85.6 - $ 12,345,678 - WR: 62.3%
 6. ProfitMaster             - Score:  84.1 - $  1,987,654 - WR: 67.8%
 7. SportsSpecialist         - Score:  82.9 - $  4,567,890 - WR: 64.5%
 8. PoliticsGuru             - Score:  81.4 - $  3,789,012 - WR: 66.2%
 9. MarketExpert             - Score:  79.8 - $  2,543,210 - WR: 63.7%
10. SmartBettor              - Score:  78.5 - $  1,876,543 - WR: 65.1%

================================================================================
✅ MASS DISCOVERY COMPLETE
================================================================================
```

## Progress Tracking

The script saves progress to `whale_discovery_progress.json`.

If interrupted, you can restart and it will resume from where it left off:

```bash
# Script was interrupted? Just run again
python3 scripts/discover_1000_whales.py

# Output will show:
# "Loaded progress: 3,289 addresses discovered, 542 processed"
```

## Verification

After completion, check your database:

```bash
# Connect to database
docker-compose exec postgres psql -U trader -d polymarket_trader

# Check whale count
SELECT COUNT(*) FROM whales WHERE is_copying_enabled = true;
# Should show: 1000

# Check tier distribution
SELECT tier, COUNT(*) FROM whales GROUP BY tier;
#  tier  | count
# -------+-------
#  MEGA  |    47
#  HIGH  |   312
#  MEDIUM|   641

# View top 10 by quality score
SELECT pseudonym, quality_score, total_volume, win_rate
FROM whales
ORDER BY quality_score DESC
LIMIT 10;
```

## Start Monitoring

Once you have 1000 whales:

```bash
# Start Kafka
docker-compose up -d kafka zookeeper

# Start ingestion service
python3 services/ingestion/main.py

# Expected output:
# ✅ Monitoring 1,000 whales in real-time
# 🐋 Whale trade: 0x1f2dd6... BUY 1000@0.54 ($540.00)
# 🐋 Whale trade: 0xf705fa... SELL 500@0.56 ($280.00)
# ...
```

## Performance Notes

- **Without API Key**: ~90 minutes (uses only known addresses + CLOB)
- **With API Key**: ~30-45 minutes (full blockchain analysis)
- **Network dependent**: Times vary based on internet speed
- **Rate limited**: ~10 requests/second to avoid blocking

## Criteria Adjustment

The script uses **relaxed criteria** to reach 1000 whales:

```python
WHALE_CRITERIA = {
    "min_volume": 50000,         # $50k (was $100k)
    "min_win_rate": 55,          # 55% (was 60%)
    "min_sharpe": 1.2,           # 1.2 (was 1.5)
    "min_trades": 20,            # 20 trades
    "min_profit": 1000,          # $1k profit
    "consistency_threshold": 0.6 # 60% profitable months
}
```

To get **higher quality** whales (may result in fewer than 1000):

Edit `scripts/discover_1000_whales.py`:

```python
WHALE_CRITERIA = {
    "min_volume": 100000,        # $100k - stricter
    "min_win_rate": 60,          # 60% - stricter
    "min_sharpe": 1.5,           # 1.5 - stricter
    "min_trades": 30,            # 30 trades - stricter
    "min_profit": 5000,          # $5k profit - stricter
    "consistency_threshold": 0.7 # 70% profitable - stricter
}
```

This will give you fewer whales but higher quality.

## Troubleshooting

### "No addresses found"
```bash
# Check if API key is set
grep POLYGONSCAN_API_KEY .env

# If empty, add it:
echo "POLYGONSCAN_API_KEY=YOUR_KEY" >> .env
```

### "Database connection failed"
```bash
# Start postgres
docker-compose up -d postgres

# Check if running
docker-compose ps postgres
```

### "Module not found: httpx"
```bash
# Install dependencies
pip3 install httpx sqlalchemy asyncpg python-dotenv
```

### "Only found 200 qualified whales"
```bash
# Lower the criteria in discover_1000_whales.py
# Or discover more addresses by increasing pages:

# Line 123: Change from 10 to 20 pages
for page in range(1, 21):  # Was: range(1, 11)

# Line 189: Change from 50 to 100 pages
for page in range(1, 101):  # Was: range(1, 51)
```

## What's Next

After getting 1000 whales:

1. **Monitor trades** - Real-time WebSocket feeds active
2. **Score whales** - Run advanced scoring engine (Phase 2.1)
3. **Cluster wallets** - Identify multi-account entities (Phase 2.1)
4. **Detect edge decay** - CUSUM tests for degrading whales (Phase 2.2)
5. **Execute trades** - Copy whale trades (Phase 3.1)

## Cost

- PolygonScan API: **FREE** (5 requests/second limit)
- Polymarket API: **FREE** (unlimited)
- Infrastructure: **~$0** (local Docker)
- Total: **$0**

## Time Investment

- Setup: 5 minutes
- Discovery: 30-60 minutes
- Verification: 2 minutes
- **Total: ~40-70 minutes**

Then you have 1,000 profitable whales being monitored 24/7.
