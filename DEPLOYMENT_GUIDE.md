# Whale Trader v0.1 - Deployment Guide

## ✅ System Status

**Test Coverage:** 100% (85/85 tests passing)
**Database:** PostgreSQL connected with 3,332 whales and 908 trades
**Code Quality:** All 7 critical bugs fixed
**Ready for Deployment:** ✅ YES

---

## Quick Deployment (Without Docker)

The system is **already partially deployed** with:
- ✅ Database running (PostgreSQL on localhost:5432)
- ✅ 3,332 whales tracked
- ✅ 908 whale trades available for copying
- ✅ All tests passing (100%)

### Option 1: Simple Python Deployment (Recommended for Development)

```bash
cd /Users/ronitchhibber/Desktop/Whale.Trader-v0.1

# 1. Start API Server
nohup python3 api/main.py > logs/api.log 2>&1 &

# 2. Verify it's running
sleep 3
curl http://localhost:8000/health

# 3. Check whale stats
curl http://localhost:8000/api/stats/summary | python3 -m json.tool

# 4. View API documentation
open http://localhost:8000/docs
```

**System will be available at:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Full Docker Deployment (Production Infrastructure)

### Prerequisites
- Docker Desktop installed and running
- At least 8GB RAM allocated to Docker
- 20GB disk space

### Step 1: Start Core Infrastructure

```bash
cd /Users/ronitchhibber/Desktop/Whale.Trader-v0.1

# Start PostgreSQL (TimescaleDB)
docker-compose up -d postgres

# Wait for database to be ready
sleep 10

# Run migrations
alembic upgrade head
```

### Step 2: Start Monitoring Stack

```bash
# Start Prometheus, Grafana, Loki, Jaeger
docker-compose up -d prometheus grafana loki promtail jaeger otel-collector

# Access dashboards:
# - Grafana: http://localhost:3000 (admin/admin123)
# - Prometheus: http://localhost:9090
# - Jaeger: http://localhost:16686
```

### Step 3: Start Message Queue (Optional for Production)

```bash
# Start Kafka + Zookeeper
docker-compose up -d zookeeper kafka

# Start RabbitMQ
docker-compose up -d rabbitmq

# RabbitMQ Management: http://localhost:15672 (trader/changeme123)
```

### Step 4: Start Redis (Optional)

```bash
docker-compose up -d redis
```

### Step 5: Verify All Services

```bash
docker-compose ps

# Should show:
# - postgres (healthy)
# - redis (healthy)
# - kafka (healthy)
# - prometheus (running)
# - grafana (running)
# - jaeger (running)
```

---

## Post-Deployment Verification

### 1. Check Database

```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from src.database import SessionLocal
from src.database.models import Whale, Trade

session = SessionLocal()
whale_count = session.query(Whale).count()
trade_count = session.query(Trade).filter(Trade.is_whale_trade == True).count()
print(f'✓ Database connected')
print(f'✓ {whale_count} whales tracked')
print(f'✓ {trade_count} whale trades available')
session.close()
"
```

### 2. Run System Tests

```bash
python3 test_comprehensive_system.py
# Should show: Success Rate: 100% (85/85 tests)
```

### 3. Check API Health

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

### 4. Get Top Whales

```bash
curl http://localhost:8000/api/whales/top?limit=10 | python3 -m json.tool
```

---

## Service Management

### View Logs

```bash
# API logs
tail -f logs/api.log

# Docker service logs
docker-compose logs -f postgres
docker-compose logs -f kafka
docker-compose logs -f grafana
```

### Stop Services

```bash
# Stop API
pkill -f "python3 api/main.py"

# Stop Docker services
docker-compose down

# Stop and remove volumes (CAUTION: deletes data)
docker-compose down -v
```

### Restart Services

```bash
# Restart API
pkill -f "python3 api/main.py"
nohup python3 api/main.py > logs/api.log 2>&1 &

# Restart Docker services
docker-compose restart
```

---

## Monitoring & Dashboards

### Grafana Dashboards
- **URL:** http://localhost:3000
- **Username:** admin
- **Password:** admin123

Available dashboards:
- Whale Trading Performance
- System Metrics
- API Performance
- Database Queries

### Prometheus Metrics
- **URL:** http://localhost:9090
- Query system metrics, API latency, database performance

### Jaeger Tracing
- **URL:** http://localhost:16686
- Distributed tracing for request flows

---

## Environment Configuration

Critical variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://trader:trader_password@localhost:5432/polymarket_trader

# API Keys (set for production)
POLYMARKET_API_KEY=your_key_here
POLYMARKET_SECRET=your_secret_here
PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here

# Risk Management
MAX_POSITION_SIZE=1000.0
MAX_DAILY_LOSS_PCT=0.05
MAX_DRAWDOWN_PCT=0.20

# Features
ENABLE_COPY_TRADING=false  # Set to true when ready
DRY_RUN_MODE=true          # Test mode (no real trades)
```

---

## Production Checklist

Before enabling live trading:

- [ ] All tests passing (100%)
- [ ] Database backups configured
- [ ] Production API keys set in .env
- [ ] Wallet funded with USDC
- [ ] Risk limits configured appropriately
- [ ] Monitoring dashboards reviewed
- [ ] Alert notifications configured
- [ ] DRY_RUN_MODE tested thoroughly
- [ ] Team reviewed deployment
- [ ] Rollback plan documented

---

## Troubleshooting

### Issue: API won't start

```bash
# Check if port 8000 is in use
lsof -ti:8000

# Kill existing process
lsof -ti:8000 | xargs kill -9

# Check logs
tail -50 logs/api.log
```

### Issue: Database connection fails

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres | tail -50

# Verify connection string
grep DATABASE_URL .env
```

### Issue: Docker services won't start

```bash
# Check Docker is running
docker info

# Check disk space
df -h

# Check container status
docker-compose ps

# View service logs
docker-compose logs <service_name>
```

---

## Support & Documentation

- **API Docs:** http://localhost:8000/docs
- **System Architecture:** See COMPLETE_16_WEEK_SUMMARY.md
- **Bug Reports:** See BUG_TESTING_REPORT.md
- **Test Results:** See README_TESTING_RESULTS.md

---

## Next Steps

1. ✅ **Phase 1 Complete:** System deployed and tested
2. 🔜 **Phase 2:** Enable copy trading in dry-run mode
3. 🔜 **Phase 3:** Gradual rollout with small position sizes
4. 🔜 **Phase 4:** Full production deployment

**Status:** Ready for Phase 2 - Dry Run Testing
