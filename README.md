# Polymarket Whale Copy-Trading System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Production-grade, institutional-quality automated whale copy-trading system for Polymarket prediction markets.**

## Features

- **Statistical Whale Selection**: Multi-factor scoring with James-Stein shrinkage, bootstrapped confidence intervals
- **Real-Time Execution**: WebSocket-based trade detection with sub-second latency
- **Advanced Risk Management**: Stop-losses, circuit breakers, Kelly Criterion position sizing
- **Event-Driven Architecture**: Kafka streaming + RabbitMQ work queues for scalability
- **Comprehensive Monitoring**: Grafana dashboards, Prometheus metrics, performance analytics

## Target Performance

| Metric | Target | Notes |
|--------|--------|-------|
| **Sharpe Ratio** | > 2.0 | Risk-adjusted returns |
| **Annual ROI** | > 20% | Conservative estimate |
| **Win Rate** | > 58% | Blended across whales |
| **Max Drawdown** | < 20% | Portfolio-level limit |
| **System Uptime** | > 99% | Redundant infrastructure |

## Architecture

```
┌─────────────────────────────────────────┐
│        Data Ingestion Layer             │
│  WebSocket Feeds │ REST API │ Historical│
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│     Message Bus (Kafka + RabbitMQ)      │
│  whale_trades │ order_updates │ prices  │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│         Analytics & Scoring             │
│  Whale Selection │ Risk Scoring │ ML    │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│      Execution & Risk Management        │
│  Order Router │ Position Tracking │ P&L │
└─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Polymarket account with API credentials
- Polygon wallet with USDC

### Installation

1. **Clone and setup**
```bash
cd polymarket-copy-trader
cp .env.example .env
# Edit .env with your credentials
```

2. **Start infrastructure**
```bash
docker-compose up -d postgres redis kafka rabbitmq
```

3. **Initialize database**
```bash
docker-compose exec postgres psql -U trader -d polymarket_trader -f /docker-entrypoint-initdb.d/init_db.sql
```

4. **Install Python dependencies**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

5. **Run the system**
```bash
python src/main.py
```

## Configuration

### Environment Variables

Key variables in `.env`:

```bash
# Polymarket API
POLYMARKET_API_KEY=your_key
POLYMARKET_SECRET=your_secret
POLYMARKET_PASSPHRASE=your_passphrase

# Wallet
PRIVATE_KEY=your_private_key
WALLET_ADDRESS=0x...

# Risk Limits
MAX_POSITION_SIZE=1000.0      # Max $ per position
MAX_DAILY_LOSS=500.0          # Circuit breaker threshold
STOP_LOSS_PCT=0.15            # 15% stop-loss
KELLY_FRACTION=0.25           # Quarter-Kelly sizing

# Whale Selection
MIN_WHALE_WIN_RATE=0.65       # 65% minimum
MIN_WHALE_SHARPE=1.0          # Sharpe > 1.0
WHALE_SCORE_THRESHOLD=70      # Quality score threshold
```

## Project Structure

```
polymarket-copy-trader/
├── src/
│   ├── api/              # Polymarket API clients
│   ├── database/         # Database models & queries
│   ├── scoring/          # Whale selection algorithms
│   ├── execution/        # Order execution engine
│   ├── risk/             # Risk management
│   ├── monitoring/       # Metrics & alerting
│   └── utils/            # Helper functions
├── config/               # Configuration files
├── scripts/              # Utility scripts
├── tests/                # Unit & integration tests
├── docs/                 # Documentation
├── docker-compose.yml    # Infrastructure setup
└── requirements.txt      # Python dependencies
```

## Whale Selection Methodology

The system uses a robust, multi-factor scoring model:

1. **Metric Calculation**: EWMA-weighted Sharpe ratio, win rate, profit factor
2. **Normalization**: MAD-based z-scores to handle outliers
3. **Shrinkage**: James-Stein estimator to reduce estimation error
4. **Confidence Intervals**: Ledoit-Wolf bootstrap for robust Sharpe estimation
5. **Final Score**: `0.7 * Sharpe_Z + 0.3 * WinRate_Z`

Whales ranked by lower bound of bootstrapped confidence interval, not point estimate.

## Risk Management

### Position-Level Controls
- **Stop-Loss**: Hard 15% per position
- **Take-Profit**: 30% target (3:1 reward-to-risk)
- **Position Sizing**: Fractional Kelly (k=0.25)
- **Max Concentration**: 5-10% per position

### Portfolio-Level Controls
- **Circuit Breaker**: 5% daily loss → halt trading
- **Max Drawdown**: 20% from peak → reduce exposure by 50%
- **Whale Concentration**: Max 30% allocated to single whale
- **Rate Limiting**: 10 orders/minute

### Market Filters
- **Min Liquidity**: $50,000 24hr volume
- **Max Spread**: 3% bid-ask
- **Resolution Risk**: Exit 2-3 hours before resolution (UMA oracle risk)

## Monitoring

### Grafana Dashboards

Access at `http://localhost:3000` (default: admin/admin123)

Key dashboards:
- **Portfolio P&L**: Real-time unrealized/realized P&L
- **Underwater Plot**: Drawdown from high-water mark
- **Whale Performance**: Heat-map of whale metrics
- **System Health**: API latency, order fill rate, WebSocket uptime

### Prometheus Metrics

Access at `http://localhost:9090`

Key metrics:
- `trading_pnl_total`: Cumulative P&L
- `trading_positions_open`: Number of open positions
- `trading_orders_submitted`: Order submission rate
- `api_requests_total`: API call volume
- `websocket_events_total`: Event stream health

## Development

### Running Tests
```bash
pytest tests/ -v --cov=src
```

### Code Quality
```bash
black src/
flake8 src/
mypy src/
```

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Backtesting

Run Monte Carlo simulation with historical data:

```bash
python scripts/backtest.py --start-date 2024-01-01 --end-date 2024-10-31 --simulations 1000
```

Generates:
- Distribution of Sharpe ratios
- Maximum drawdown statistics
- Deflated Sharpe Ratio (DSR) validation
- Performance attribution by whale

## Production Deployment

### Infrastructure Requirements
- **Compute**: 4 vCPU, 8GB RAM minimum
- **Storage**: 100GB SSD for database
- **Network**: Low-latency connection to Polygon RPC

### Recommended Stack
- **Cloud**: AWS/GCP multi-AZ deployment
- **Database**: RDS PostgreSQL with TimescaleDB
- **Message Queue**: MSK (Kafka) or Amazon MQ (RabbitMQ)
- **Monitoring**: CloudWatch + Grafana Cloud

### Cost Estimate
- Polymarket Premium API: $99/mo
- Cloud infrastructure: $100-200/mo
- Polygon RPC (QuickNode): $50/mo
- **Total**: ~$250-350/mo

## Security

- **Private Keys**: Never commit to git, use environment variables or secrets manager
- **API Keys**: Rotate regularly, use least-privilege access
- **Database**: Strong passwords, firewall rules, encrypted connections
- **Monitoring**: Alert on suspicious activity (unusual order volume, API errors)

## Troubleshooting

### WebSocket Disconnects
```bash
# Check WebSocket health
docker-compose logs -f app | grep "WebSocket"

# Restart app container
docker-compose restart app
```

### Database Connection Issues
```bash
# Check PostgreSQL status
docker-compose ps postgres
docker-compose logs postgres

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d postgres
```

### Circuit Breaker Stuck
```bash
# Reset via database
docker-compose exec postgres psql -U trader -d polymarket_trader
UPDATE system_state SET value='false' WHERE key='circuit_breaker_active';
```

## Contributing

This is a private trading system. Do not share strategies, API keys, or performance data publicly.

## Disclaimer

This software is for educational purposes. Prediction markets involve financial risk. Past performance does not guarantee future returns. Always conduct your own due diligence and never risk more than you can afford to lose.

## License

Proprietary - All Rights Reserved

## Support

For issues or questions, review the documentation in `/docs` or check logs:
```bash
docker-compose logs -f app
tail -f logs/trading.log
```
