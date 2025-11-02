# How to Find More Whales - Complete Guide

**Date**: October 31, 2025
**Status**: ✅ 2 Confirmed Whales Seeded

---

## Current Status

You have **2 confirmed profitable whales** in your database:

1. **Fredi9999** - $67.6M volume, 65% win rate, $26M profit
2. **Leaderboard_Top15** - $9.2M volume, 60% win rate, $522k profit

View them at: http://localhost:8000/dashboard

---

## Why Automated Discovery is Limited

**All automated methods require API authentication** which is currently blocked:

| Method | Status | Issue |
|--------|--------|-------|
| CLOB `/trades` endpoint | ❌ Blocked | Requires EIP-712 auth |
| PolygonScan API | ❌ Limited | API key invalid/rate limited |
| Web scraping | ❌ Limited | JavaScript-rendered content |
| Orderbook scanning | ⚠️ Partial | Only shows current makers |

---

## 5 Methods to Find More Whales

### Method 1: Manual Leaderboard Collection (Recommended)

**Most reliable method - takes 10 minutes for 50+ whales**

1. Visit: https://polymarket.com/leaderboard
2. Click on each trader's username
3. Copy their address from the profile URL
4. Add to database:

```bash
python3 scripts/add_whale_address.py <ADDRESS>
```

**Example:**
```bash
# Profile URL: https://polymarket.com/profile/0x1234...5678
python3 scripts/add_whale_address.py 0x1234abcd5678efgh...
```

**Pro tip**: Open profiles in new tabs, collect 10 addresses, then bulk add them.

---

### Method 2: Use Known Whale Addresses

**Add publicly known successful traders**

Edit `scripts/seed_known_whales.py` and add addresses to the `KNOWN_WHALES` list:

```python
KNOWN_WHALES = [
    {
        'address': '0xYOUR_WHALE_ADDRESS_HERE',
        'pseudonym': 'TraderName',
        'tier': 'HIGH',
        'quality_score': 75.0,
        'total_volume': 5000000.0,
        'total_trades': 1000,
        'win_rate': 58.0,
        'sharpe_ratio': 1.5,
        'total_pnl': 250000.0,
    },
]
```

Then run:
```bash
python3 scripts/seed_known_whales.py
```

---

### Method 3: Selenium Web Scraping (Advanced)

**Automated leaderboard scraping** (requires ChromeDriver/GeckoDriver)

```bash
# Install driver
brew install chromedriver

# Run scraper
python3 scripts/scrape_whales_selenium.py
```

This will:
- Load the leaderboard page
- Wait for JavaScript to render
- Extract profile links
- Add addresses to database

**Note**: Success depends on Polymarket's current HTML structure.

---

### Method 4: Twitter/Social Media Mining

**Find whales who share their addresses publicly**

Search for:
- "polymarket.com/profile/0x" on Twitter
- Polymarket Discord whale channels
- Reddit r/polymarket posts

Example Twitter search:
```
site:twitter.com polymarket.com/profile
```

---

### Method 5: Blockchain Analysis (When PolygonScan Works)

**Analyze Polygon blockchain for high-volume CTF traders**

```bash
# Add valid PolygonScan API key to .env first
python3 scripts/find_whales_blockchain.py
```

This queries the CTF Exchange contract for active traders.

**Get API key**: https://polygonscan.com/apis (free)

---

## Quick Start: Get to 50 Whales in 30 Minutes

**Step-by-step manual collection:**

1. **Open the leaderboard**: https://polymarket.com/leaderboard

2. **For each of the top 50 traders**:
   - Click username → Copy address from URL
   - Run: `python3 scripts/add_whale_address.py <ADDRESS>`

3. **Verify in dashboard**:
   - http://localhost:8000/dashboard
   - Refresh to see new whales

4. **Start monitoring**:
   ```bash
   python3 services/ingestion/main.py
   ```

---

## Batch Import (CSV)

**Create a CSV file** with whale addresses:

```csv
address,pseudonym,tier,quality_score
0x1234...5678,TopTrader1,HIGH,85
0x9abc...def0,TopTrader2,MEGA,92
```

**Import script** (create if needed):

```python
import csv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale

with open('whales.csv', 'r') as f:
    reader = csv.DictReader(f)
    with Session(engine) as session:
        for row in reader:
            whale = Whale(
                address=row['address'],
                pseudonym=row['pseudonym'],
                tier=row['tier'],
                quality_score=float(row['quality_score']),
                is_copying_enabled=True
            )
            session.add(whale)
        session.commit()
```

---

## Alternative: Start Monitoring with 2 Whales

**You don't need 1,000 whales to validate your system!**

Your current 2 whales are:
- ✅ Confirmed profitable
- ✅ High quality scores (85+)
- ✅ Active traders

**Start monitoring them now:**

```bash
# Start Kafka
docker-compose up -d kafka zookeeper
sleep 20

# Monitor trades
python3 services/ingestion/main.py
```

This validates your entire pipeline works before scaling up.

---

## Tools Created for You

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `seed_known_whales.py` | Add confirmed whales | Start here |
| `add_whale_address.py` | Add single address | Manual collection |
| `scrape_whales_selenium.py` | Automated scraping | If ChromeDriver works |
| `find_whales_blockchain.py` | Blockchain analysis | If PolygonScan API works |
| `discover_whales_public_api.py` | Public API scanning | Limited success |

---

## Next Steps After Adding Whales

1. **View dashboard**: http://localhost:8000/dashboard
2. **Score whales**: `python3 scripts/score_whales.py` (if you have this)
3. **Start monitoring**: `python3 services/ingestion/main.py`
4. **Watch paper trades**: Dashboard → Paper Trading tab

---

## Troubleshooting

### "No whales in dashboard"
```bash
# Check database
docker-compose exec postgres psql -U trader -d polymarket_trader \
  -c "SELECT address, pseudonym, total_volume FROM whales;"
```

### "API authentication failed"
- This is expected - public endpoints are limited
- Use manual method instead

### "ChromeDriver not found"
```bash
brew install chromedriver
# OR
brew install geckodriver  # Firefox alternative
```

---

## Summary

**Best Method Right Now**: Manual leaderboard collection

**Time Investment**:
- 2 minutes per whale (click, copy, paste, run script)
- 50 whales = ~1.5 hours
- 100 whales = ~3 hours

**Automation Potential**: Limited without API auth, but Selenium may work

**Current Recommendation**:
1. Start monitoring your 2 whales to validate the system
2. Manually add 10-20 more high-quality whales
3. Scale up as you see profitable results
