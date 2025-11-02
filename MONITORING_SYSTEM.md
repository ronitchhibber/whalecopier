# Whale Monitoring System

## Overview

The system now has **two separate background services** for comprehensive whale tracking:

### 1. **Trade Monitor** (Every 15 minutes)
Monitors whale activity in real-time by detecting when new trades are made.

**File**: `src/services/whale_trade_monitor.py`
**Frequency**: Every 15 minutes
**Purpose**: Real-time trade detection

**What it does**:
- Checks each enabled whale's Polymarket profile
- Detects when total_trades count increases (= new trade made)
- Updates `most_recent_trade_at` timestamp
- Logs trade activity in real-time
- Provides immediate alerts when whales make moves

### 2. **Metrics Updater** (Every 6 hours)
Updates comprehensive 24-hour metrics for all whales.

**File**: `src/services/whale_metrics_updater.py`
**Frequency**: Every 6 hours (4 times per day)
**Purpose**: 24h aggregate metrics

**What it does**:
- Calculates `trades_24h` from database trades
- Calculates `volume_24h` from database trades
- Updates `active_trades` from API
- Updates `most_recent_trade_at` if newer trades found
- Updates `last_trade_check_at` timestamp

## Database Schema

New columns added to `whales` table:

```sql
-- 24h metrics (for real-time insights)
trades_24h INTEGER              -- Count of trades in last 24 hours
volume_24h NUMERIC(20, 2)       -- Dollar volume in last 24 hours
active_trades INTEGER            -- Current number of active positions
most_recent_trade_at TIMESTAMP  -- Timestamp of most recent trade
last_trade_check_at TIMESTAMP   -- When we last checked for new trades
```

## How to Run

### Start Trade Monitor (15-minute checks):
```bash
python3 scripts/start_trade_monitor.py
```

### Start Metrics Updater (6-hour updates):
```bash
python3 scripts/start_metrics_updater.py
```

### Run Both Services (recommended):
```bash
# Terminal 1
python3 scripts/start_trade_monitor.py

# Terminal 2
python3 scripts/start_metrics_updater.py
```

## Monitoring Schedule

```
Time          Trade Monitor    Metrics Updater
----------------------------------------------------
00:00         ✓ Check          ✓ Update 24h metrics
00:15         ✓ Check
00:30         ✓ Check
00:45         ✓ Check
01:00         ✓ Check
...
06:00         ✓ Check          ✓ Update 24h metrics
...
12:00         ✓ Check          ✓ Update 24h metrics
...
18:00         ✓ Check          ✓ Update 24h metrics
```

**Result**: Whales are checked 96 times per day (every 15 min), with comprehensive metrics updated 4 times per day.

## API Response

The `/api/whales` endpoint now returns:

```json
{
  "address": "0x...",
  "pseudonym": "fengdubiying",
  "quality_score": 85.4,
  "total_pnl": 686420.00,
  "tier": "MEGA",

  // Real-time monitoring data
  "trades_24h": 15,
  "volume_24h": 45230.50,
  "active_trades": 3,
  "most_recent_trade_at": "2025-10-31T23:15:00Z",
  "last_trade_check_at": "2025-10-31T23:30:00Z"
}
```

## Whale Quality Filtering

Use `scripts/filter_quality_whales.py` to filter whales based on:

**Quality Scoring (0-100)**:
- PnL (30%): Higher profit = higher score
- ROI (30%): Better return on volume = higher score
- Volume (15%): More trading activity
- Total Trades (15%): More experience
- Markets Traded (10%): Better diversification

**Filtering Criteria**:
- Minimum quality score: 30
- Minimum PnL: $1,000
- Minimum trades: 10
- Must have public profile available

**Run Filtering**:
```bash
python3 scripts/filter_quality_whales.py
```

This will:
- Check all 3,332 whales for public profile availability
- Calculate quality scores
- Enable copy trading for high-quality whales
- Disable copy trading for low-quality or unavailable whales
- Show top 20 whales for tracking

## Important Notes

### Current Limitations

**Individual Trade Details**: To fetch individual trade data (not just aggregate metrics), you need:
1. Authenticated CLOB API access
2. Python 3.9.10+ (currently have 3.9.6)
3. `py-clob-client` package installed
4. API credentials generated

**Workaround**: The current system detects when trades are made by monitoring profile changes, but doesn't capture individual trade details (market, side, price, size). Once API authentication is set up, we can enhance the trade monitor to fetch full trade data.

### Setup Instructions for Full Trade Data

See `QUICK_START_API.md` for complete setup instructions. You'll need to:

1. Upgrade Python to 3.9.10+
2. Install: `pip3 install py-clob-client`
3. Generate credentials:
   ```bash
   python3 scripts/generate_polymarket_api_key.py 0xYOUR_PRIVATE_KEY
   ```
4. Test API:
   ```bash
   python3 scripts/test_polymarket_api.py
   ```

Wallet already created:
- Address: `0x845e0238643AB0fc52FD0E2EB592B60361757C19`
- Private Key: (in `wallet_info.txt`)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MONITORING SYSTEM                         │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│  Trade Monitor       │         │  Metrics Updater     │
│  (Every 15 min)      │         │  (Every 6 hours)     │
│                      │         │                      │
│  • Check profiles    │         │  • Calculate 24h     │
│  • Detect new trades │         │  • Update aggregates │
│  • Update timestamps │         │  • Refresh scores    │
│  • Log activity      │         │  • Update API data   │
└──────────┬───────────┘         └──────────┬───────────┘
           │                                │
           │         ┌──────────────────────┤
           │         │                      │
           └─────────▼──────────────────────▼─────────┐
                     │    PostgreSQL Database          │
                     │    (whales table)               │
                     └─────────────┬───────────────────┘
                                   │
                     ┌─────────────▼───────────────┐
                     │    FastAPI Endpoints        │
                     │    /api/whales              │
                     │    /api/stats/summary       │
                     └─────────────────────────────┘
```

## Testing

### Test Single Monitoring Cycle:
```bash
# Test trade monitor
python3 -c "
import asyncio
from src.services.whale_trade_monitor import WhaleTradeMonitor
monitor = WhaleTradeMonitor()
asyncio.run(monitor.monitoring_cycle())
"

# Test metrics updater
python3 scripts/test_metrics_update.py
```

### Check Database:
```bash
# Connect to postgres
docker-compose exec postgres psql -U trader -d polymarket_trader

# Query whales with recent activity
SELECT
  pseudonym,
  trades_24h,
  volume_24h,
  most_recent_trade_at,
  last_trade_check_at
FROM whales
WHERE is_copying_enabled = true
ORDER BY most_recent_trade_at DESC NULLS LAST
LIMIT 10;
```

## Performance

- **Trade Monitor**: ~0.2 seconds per whale × enabled whales ≈ 5-10 seconds per cycle
- **Metrics Updater**: ~0.3 seconds per whale × all whales ≈ 10-15 minutes per cycle
- **Database Queries**: Instant (using indexed columns)
- **API Response**: <100ms (reading from database, no external calls)

## Maintenance

**Daily Tasks**:
- None (services run automatically)

**Weekly Tasks**:
- Review whale quality scores
- Check for new high-performing whales
- Remove consistently unprofitable whales

**Monthly Tasks**:
- Run full whale discovery again
- Update quality filtering thresholds
- Review and optimize monitoring frequency

## Troubleshooting

**Monitor not detecting trades**:
- Check whale profile is publicly available
- Verify whale is marked `is_copying_enabled = true`
- Check logs for API errors

**Metrics not updating**:
- Verify metrics updater is running
- Check database connection
- Review alembic migrations applied

**API returning null metrics**:
- Run metrics updater at least once
- Ensure `trades` table has data for whales
- Check database schema has new columns

## Next Steps

1. **Complete whale filtering** - Run `filter_quality_whales.py` to identify best whales
2. **Start both services** - Run trade monitor and metrics updater
3. **Set up API authentication** - Follow `QUICK_START_API.md` to enable full trade data
4. **Monitor performance** - Watch logs and verify trades are being detected
5. **Integrate copy trading** - Enable automatic trade copying for high-quality whales
