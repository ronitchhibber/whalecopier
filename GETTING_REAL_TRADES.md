# Getting Real Whale Trades

## Current Status

**The trades displayed are SAMPLE/DEMO trades** generated to showcase the dashboard functionality. The whales are real (from the database), but the trades are simulated.

## Why Sample Trades?

The Polymarket APIs we attempted to use returned no recent trade data:
1. **Subgraph API** - No trades found in last 48 hours
2. **Gamma API** - No recent events returned
3. **RTDS WebSocket** - Requires authenticated access for detailed trade data

## How to Get REAL Trades

### Option 1: Use Polymarket CLOB API (Recommended)

The Polymarket CLOB (Central Limit Order Book) API provides real-time trade data:

```python
# You need:
1. API Key from Polymarket
2. Private key for signing requests (EIP-712)
3. Access to CLOB REST API endpoints

# Get trades for a specific whale:
GET https://clob.polymarket.com/trades?maker={whale_address}
```

**Setup Steps:**
1. Sign up at https://polymarket.com
2. Generate API credentials
3. Update `.env` with your credentials:
   ```
   POLYMARKET_API_KEY=your_key_here
   POLYMARKET_PRIVATE_KEY=your_private_key
   ```
4. Run the trade fetcher with authentication

### Option 2: Real-Time Data Stream (RTDS WebSocket)

For live streaming trades:

```python
# Connect to Polymarket RTDS
wss://ws-subscriptions-clob.polymarket.com/ws/market/{market_id}

# Subscribe to trade events
{
  "type": "subscribe",
  "channel": "trades",
  "market": "market_id"
}
```

**Current Status:**
- The `whale_trade_monitor.py` is set up to use this
- Running every 1 minute
- Will capture trades when whales are actively trading

### Option 3: Subgraph (Historical Data)

For historical analysis:

```graphql
query {
  trades(
    where: { trader: "0xwhale_address" }
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    market
    side
    size
    price
    timestamp
  }
}
```

**Endpoint:**
```
https://gateway-arbitrum.network.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/8zsAW24güKdJRUC8gC7EQVwGPfHHckaq7FXdFcBJNbQS
```

## Current Live Monitoring

The system IS monitoring for real trades:

**Active Service:**
- `whale_trade_monitor.py` running every 1 minute
- Monitoring 50 whales
- Will automatically detect and store real trades when they occur

**To check monitor status:**
```bash
# Check if monitor is running
ps aux | grep whale_trade_monitor

# View monitor logs
tail -f logs/whale_trade_monitor.log
```

## Making the Switch to Real Trades

Once you have API access:

1. **Update credentials in `.env`:**
   ```bash
   POLYMARKET_API_KEY=your_actual_key
   POLYMARKET_PRIVATE_KEY=your_private_key
   CLOB_API_URL=https://clob.polymarket.com
   ```

2. **Clear sample trades:**
   ```bash
   python3 scripts/clear_and_restart_trades.py
   ```

3. **Run authenticated trade fetcher:**
   ```bash
   python3 scripts/fetch_real_trades.py --auth
   ```

4. **The monitor will then capture real trades automatically**

## Current Dashboard Features

Even with sample trades, the dashboard demonstrates:

✅ **Real whales** - All 50 whales are actual Polymarket traders
✅ **Clickable profiles** - Click whale names to see their real profiles
✅ **Real-time updates** - Auto-refreshes every 5 seconds
✅ **Filter tabs** - All/Buys/Sells navigation
✅ **Market info** - Shows November 2025 markets
✅ **Statistics** - Volume, counts, and metrics

## Next Steps

To get actual trade data:

1. **Get Polymarket API access** (sign up + generate credentials)
2. **Or wait for whale activity** - The monitor will capture it when it happens
3. **Or use a paid data provider** - Some services aggregate Polymarket data

The infrastructure is ready - it just needs authenticated API access or active whale trading!
