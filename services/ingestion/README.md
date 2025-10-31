# Data Ingestion Service - Real-time Whale Trade Monitoring

Sub-100ms latency WebSocket service for monitoring Polymarket whale trades.

## Features

- 🔌 WebSocket connection to Polymarket CLOB
- 🐋 Real-time whale trade detection
- 📊 Prometheus metrics for observability
- 🔄 Auto-reconnection with exponential backoff
- 📨 Event streaming to Kafka
- 🎯 Sub-100ms target latency

## Architecture

```
Polymarket WebSocket → PolymarketWebSocketClient → Kafka Topics
                              ↓
                        Prometheus Metrics
```

## Prerequisites

1. **PostgreSQL** with whale database
2. **Kafka** (+ Zookeeper) for event streaming
3. **Python 3.11+** with dependencies installed

## Setup

### 1. Install Dependencies

```bash
# From project root
pip install -e ".[dev]"
```

### 2. Start Infrastructure

```bash
# Start docker-compose services
docker-compose up -d postgres kafka zookeeper

# Wait for services to be ready
docker-compose ps
```

### 3. Initialize Database

```bash
# Run Alembic migrations
alembic upgrade head

# Seed whale database
python scripts/seed_whales.py
```

### 4. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://trader:changeme123@localhost:5432/polymarket_trader

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Polymarket WebSocket
POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws

# Prometheus
PROMETHEUS_PORT=9090
```

## Running the Service

### Production Mode

```bash
python services/ingestion/main.py
```

### Development Mode (with auto-reload)

```bash
# Install watchdog
pip install watchdog

# Run with auto-reload
watchmedo auto-restart \
  --patterns="*.py" \
  --recursive \
  python services/ingestion/main.py
```

## Expected Output

```
================================================================================
POLYMARKET DATA INGESTION SERVICE
Real-time Whale Trade Monitoring
================================================================================

✅ Prometheus metrics: http://localhost:9090
✅ Connected to Kafka: localhost:9092

📊 Loaded 1 whales from database

Connecting to Polymarket WebSocket... (attempt 1/5)
✅ Connected to Polymarket WebSocket

🔔 Subscribing to 1 whale channels...
  ✅ Subscribed to whale: 0x1f2dd6d4...

✅ Monitoring 1 whales in real-time
Press Ctrl+C to stop

🐋 Whale trade: 0x1f2dd6... BUY 1000@0.54 ($540.00)
🐋 Whale trade: 0x1f2dd6... SELL 500@0.56 ($280.00)
```

## Kafka Topics

Events are published to the following topics:

1. **`whale_activity`** - All whale events (trades, orders, positions)
   - Trade events
   - Order placement/cancellation
   - Position open/close

2. **`market_trades`** - Market-wide trade data (future use)

3. **`order_books`** - Order book snapshots (future use)

## Prometheus Metrics

Available at `http://localhost:9090/metrics`:

- `whale_trades_detected_total` - Counter of detected whale trades (by address, side)
- `websocket_messages_received_total` - Counter of WebSocket messages (by type)
- `trade_processing_latency_seconds` - Histogram of processing latency
- `active_whale_subscriptions` - Gauge of active whale subscriptions
- `websocket_reconnections_total` - Counter of reconnection attempts

## Message Format

### Whale Trade Event

```json
{
  "event_type": "whale_trade",
  "trade_id": "0x123...",
  "trader_address": "0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf",
  "market_id": "0xabc...",
  "token_id": "1234",
  "side": "BUY",
  "size": 1000.0,
  "price": 0.54,
  "amount": 540.0,
  "timestamp": "2024-11-01T12:34:56Z",
  "detected_at": "2024-11-01T12:34:56.123Z"
}
```

### Whale Order Event

```json
{
  "event_type": "whale_order",
  "order_id": "0x456...",
  "trader_address": "0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf",
  "status": "OPEN",
  "market_id": "0xabc...",
  "side": "BUY",
  "size": 2000,
  "price": 0.52,
  "timestamp": "2024-11-01T12:34:56Z"
}
```

## Adding More Whales

### Option 1: Via Database

```sql
-- Enable copying for existing whale
UPDATE whales
SET is_copying_enabled = true
WHERE address = '0x...';

-- Service will auto-detect on next load
```

### Option 2: Via Script

Edit `scripts/seed_whales.py` and add whale to `FAMOUS_WHALES` list:

```python
{
    "address": "0xYOUR_WHALE_ADDRESS",
    "pseudonym": "WhaleName",
    "tier": "MEGA",
    "notes": "Description",
    "cluster_name": "Optional Cluster",
    "is_famous": True,
    "estimated_pnl": 1000000,
    "primary_category": "politics",
    "win_rate": 65.0,
    "total_volume": 2000000,
    "is_confirmed": True
}
```

Then run:

```bash
python scripts/seed_whales.py
```

## Troubleshooting

### WebSocket Connection Failed

- Check if Polymarket WebSocket URL is correct
- Verify network connectivity
- Check if VPN is blocking connection

### No Whales Found

Run seed script:

```bash
python scripts/seed_whales.py
```

Then enable copying:

```sql
UPDATE whales SET is_copying_enabled = true WHERE address = '0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf';
```

### Kafka Connection Failed

```bash
# Check Kafka status
docker-compose ps kafka

# Check Kafka logs
docker-compose logs kafka

# Restart Kafka
docker-compose restart kafka
```

### High Latency (> 100ms)

Check:
- Database query performance
- Kafka producer buffer settings
- Network latency to Polymarket
- System resource usage

## Testing

### Manual Test

```bash
# Terminal 1: Start Kafka consumer
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic whale_activity \
  --from-beginning

# Terminal 2: Start ingestion service
python services/ingestion/main.py

# Watch for events in Terminal 1
```

### Load Test

```bash
# Run load test (future)
python tests/load_test_ingestion.py
```

## Performance Targets

- **WebSocket Message Processing**: < 50ms (p99)
- **Kafka Publish Latency**: < 30ms (p99)
- **End-to-End Latency**: < 100ms (p99)
- **Reconnection Time**: < 5s
- **Memory Usage**: < 500MB per instance

## Monitoring

### Grafana Dashboard

Import dashboard from `infrastructure/grafana/dashboards/ingestion.json`

Key panels:
- Whale trades per minute
- Processing latency (p50, p95, p99)
- WebSocket connection status
- Kafka publish rate

### Alerts

Configured in `infrastructure/prometheus/alerts/ingestion.yml`:
- High latency (> 100ms for 5min)
- WebSocket disconnections (> 3 in 10min)
- No trades detected (> 30min for active whale)

## Deployment

### Single Instance

```bash
python services/ingestion/main.py
```

### Production (Docker)

```bash
docker-compose up ingestion
```

### Kubernetes

```bash
kubectl apply -f infrastructure/k8s/ingestion-deployment.yaml
```

## Next Steps

1. ✅ Complete whale database with more addresses
2. ⏳ Add order book subscription
3. ⏳ Implement market-wide trade monitoring
4. ⏳ Add anomaly detection for manipulation
5. ⏳ Build whale clustering from on-chain data
