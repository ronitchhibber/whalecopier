# Week 2: Core Trading Engine Architecture

**Status:** Design Complete
**Date:** November 2, 2025
**Version:** 1.0

## Executive Summary

This document defines the architecture for the core trading engine that will enable real-time whale copy trading with <500ms latency and >95% fill rate. The system builds on existing components (WebSocket client, database models, config) and adds production-ready order execution, position management, and risk controls.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     POLYMARKET WHALE COPY TRADER                │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  Polymarket      │────────▶│  WebSocket       │
│  CLOB API        │ Events  │  Client          │
│  (External)      │         │  (Existing)      │
└──────────────────┘         └────────┬─────────┘
                                      │
                             Trade Events (whale_trade, order_filled)
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TRADE SIGNAL PIPELINE                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Whale   │─▶│ Quality  │─▶│ Position │─▶│   Risk   │       │
│  │ Detector │  │ Filter   │  │ Sizer    │  │ Manager  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                    Approved Trade Signal
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ORDER EXECUTION ENGINE                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Slippage   │  │    Order     │  │     Fill     │         │
│  │  Estimator   │─▶│   Placer     │─▶│  Confirmer   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                       Order Fill Confirmed
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   POSITION MANAGEMENT SYSTEM                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Position    │  │   Real-Time  │  │  Stop-Loss/  │         │
│  │  Tracker     │─▶│  P&L Calc    │─▶│  Take-Profit │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               POSTGRESQL DATABASE (Existing Schema)             │
│  whales | trades | positions | orders | markets | events        │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. **WebSocket Client** (EXISTING - `src/realtime/websocket_client.py`)

**Status:** ✅ Already Implemented
**Purpose:** Real-time data streaming from Polymarket CLOB API
**Target Latency:** <500ms from whale trade to our system

**Key Features:**
- Auto-reconnect with exponential backoff
- Event parsing (ORDER_PLACED, ORDER_FILLED, WHALE_TRADE)
- Heartbeat/ping-pong for connection health
- Whale address monitoring

**Enhancements Needed (Week 2):**
1. Add connection pooling for multiple markets
2. Implement message deduplication (same trade_id)
3. Add failover to REST API polling if WebSocket fails
4. Improve subscription management (subscribe per whale address)

**Interface:**
```python
class PolymarketWebSocketClient:
    def add_whale(address: str) -> None
    def register_handler(event_type: EventType, handler: Callable) -> None
    async def start() -> None
    async def stop() -> None
```

---

### 2. **Order Execution Engine** (NEW - `src/trading/order_executor.py`)

**Status:** 🆕 To Be Built
**Purpose:** Execute trades via Polymarket CLOB API with high fill rate
**Target:** >95% fill rate, <2s submission time

**Components:**

#### 2.1 **SlippageEstimator**
Estimate execution slippage from order book depth.

```python
class SlippageEstimator:
    async def fetch_order_book(market_id: str, token_id: str) -> OrderBook
    async def estimate_slippage(
        size: Decimal,
        side: str,
        order_book: OrderBook
    ) -> SlippageEstimate

    # Returns: SlippageEstimate(
    #   estimated_price: Decimal,
    #   slippage_pct: Decimal,
    #   depth_available: Decimal,
    #   recommended: bool  # False if slippage > 2%
    # )
```

**Data Source:** Polymarket CLOB API `/book?token_id=...`

**Logic:**
1. Fetch order book (asks for buy, bids for sell)
2. Walk through orders to fill requested size
3. Calculate volume-weighted average price (VWAP)
4. Compare to mid-price: `slippage = (VWAP - mid_price) / mid_price`
5. Reject if slippage > 2% for limit orders, >5% for market orders

#### 2.2 **OrderPlacer**
Place orders via Polymarket API with retry logic.

```python
class OrderPlacer:
    def __init__(self, clob_client: ClobClient)

    async def place_limit_order(
        market_id: str,
        token_id: str,
        side: str,  # 'BUY' or 'SELL'
        size: Decimal,
        price: Decimal
    ) -> OrderResult

    async def place_market_order(
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal
    ) -> OrderResult

    async def cancel_order(order_id: str) -> bool
```

**Retry Logic:**
- Max 3 retries with exponential backoff (1s, 2s, 4s)
- Retry on: Connection errors, timeout, rate limit
- No retry on: Insufficient balance, invalid market

**Order State Machine:**
```
PENDING → SUBMITTED → FILLED → CONFIRMED
    ↓           ↓
FAILED     CANCELLED
```

**Timeout Handling:**
- Cancel PENDING orders after 5 seconds
- Cancel SUBMITTED orders after 30 seconds (unfilled)
- Move to FAILED state after 3 retry failures

#### 2.3 **FillConfirmer**
Monitor order fill status and handle partial fills.

```python
class FillConfirmer:
    async def wait_for_fill(
        order_id: str,
        timeout: int = 30
    ) -> FillStatus

    async def get_fill_status(order_id: str) -> FillStatus

    # FillStatus(
    #   status: str,  # 'FILLED', 'PARTIALLY_FILLED', 'UNFILLED'
    #   filled_size: Decimal,
    #   avg_fill_price: Decimal,
    #   fills: List[Fill]
    # )
```

**Fill Monitoring:**
1. Poll for fill status every 500ms
2. Subscribe to WebSocket fill events (faster)
3. Reconcile fills with expected positions
4. Handle partial fills:
   - If >80% filled: Accept and close
   - If <80% filled: Retry remaining amount

---

### 3. **Position Management System** (ENHANCE - `src/trading/position_manager.py`)

**Status:** ⚠️ Partially Exists (needs enhancement)
**Purpose:** Track positions, calculate real-time P&L, manage lifecycle
**Target:** <1s P&L update latency

**Components:**

#### 3.1 **PositionTracker**
Track all open positions in real-time.

```python
class PositionTracker:
    def __init__(self, db_engine: Engine)

    async def open_position(
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        source_whale: str
    ) -> Position

    async def update_position(
        position_id: str,
        size_delta: Decimal,
        price: Decimal
    ) -> Position

    async def close_position(
        position_id: str,
        exit_price: Decimal
    ) -> ClosedPosition

    async def get_open_positions() -> List[Position]
    async def get_position_by_market(market_id: str) -> Optional[Position]
```

**Database Integration:**
- Read/Write to `positions` table
- Update `active_positions` count in `whales` table
- Create `Event` records for position lifecycle

#### 3.2 **PnLCalculator**
Calculate real-time profit & loss.

```python
class PnLCalculator:
    async def fetch_current_prices(
        markets: List[str]
    ) -> Dict[str, Decimal]

    async def calculate_position_pnl(
        position: Position,
        current_price: Decimal
    ) -> PnLMetrics

    # PnLMetrics(
    #   unrealized_pnl: Decimal,
    #   pnl_pct: Decimal,
    #   current_value: Decimal,
    #   profit_target_hit: bool,  # Take-profit triggered
    #   stop_loss_hit: bool        # Stop-loss triggered
    # )

    async def calculate_portfolio_pnl() -> PortfolioPnL
```

**Price Fetching:**
- Fetch current market prices every 1 second
- Cache in Redis with 1s TTL
- Use WebSocket price updates when available
- Fallback to REST API: `/markets?id=...`

**P&L Calculation:**
```python
# For BUY positions
unrealized_pnl = (current_price - entry_price) * size

# For SELL positions (shorts)
unrealized_pnl = (entry_price - current_price) * size

# Percentage
pnl_pct = unrealized_pnl / (entry_price * size) * 100
```

#### 3.3 **StopLossTakeProfitManager**
Automated position exits based on P&L thresholds.

```python
class StopLossTakeProfitManager:
    def __init__(
        self,
        stop_loss_pct: float = 0.15,  # -15%
        take_profit_pct: float = 0.30  # +30%
    )

    async def check_exit_triggers(
        position: Position,
        current_price: Decimal
    ) -> Optional[ExitSignal]

    async def set_stop_loss(
        position_id: str,
        stop_loss_price: Decimal
    ) -> None

    async def set_take_profit(
        position_id: str,
        take_profit_price: Decimal
    ) -> None
```

**Exit Logic:**
- Stop-Loss: Close position at -15% loss
- Take-Profit: Close at +30% gain
- Trailing Stop: Move stop-loss as position profits (optional)

---

### 4. **Risk Management System** (ENHANCE - `src/risk/live_risk_manager.py`)

**Status:** ⚠️ Partially Exists (needs enhancement)
**Purpose:** Portfolio-level risk controls and circuit breakers
**Target:** 100% compliance with risk limits

**Components:**

#### 4.1 **Circuit Breakers**

```python
class CircuitBreakers:
    async def check_daily_loss_limit(
        total_pnl_today: Decimal,
        limit: Decimal = 500
    ) -> RiskDecision

    async def check_max_drawdown(
        current_value: Decimal,
        peak_value: Decimal,
        max_dd_pct: float = 0.10  # 10%
    ) -> RiskDecision

    async def check_consecutive_losses(
        recent_trades: List[Trade],
        max_losses: int = 5
    ) -> RiskDecision
```

**Actions:**
- Daily loss > $500: **HALT all trading**
- Drawdown > 10%: **REDUCE position sizes by 50%**
- 5 consecutive losses: **PAUSE for 1 hour**

#### 4.2 **Position Limits**

```python
class PositionLimitChecker:
    async def check_position_size(
        size: Decimal,
        max_position: Decimal = 1000
    ) -> bool

    async def check_market_exposure(
        market_id: str,
        new_size: Decimal,
        max_exposure: Decimal = 5000
    ) -> bool

    async def check_whale_exposure(
        whale_address: str,
        new_size: Decimal,
        max_whale_exposure: Decimal = 10000
    ) -> bool

    async def check_total_exposure(
        new_size: Decimal,
        portfolio_value: Decimal,
        max_exposure_pct: float = 0.20
    ) -> bool
```

**Limits:**
- Max position size: $1,000
- Max exposure per market: $5,000
- Max exposure per whale: $10,000
- Max portfolio allocation: 20% per market

---

### 5. **Whale Trade Detector** (ENHANCE WebSocket Client)

**Status:** ⚠️ Basic version exists
**Purpose:** Detect whale trades in real-time
**Target:** <500ms detection latency

**Enhancement:**
Add to existing WebSocket client:

```python
class WhaleTradeDetector:
    def __init__(
        self,
        whale_addresses: Set[str],
        min_trade_size: Decimal = 1000
    )

    async def detect_whale_trade(
        event: StreamEvent
    ) -> Optional[WhaleTrade]

    async def classify_trade_significance(
        trade: WhaleTrade,
        whale_quality_score: float
    ) -> TradeSignificance  # HIGH, MEDIUM, LOW
```

**Classification:**
- **HIGH:** WQS > 0.8, size > $10,000
- **MEDIUM:** WQS 0.5-0.8, size $1,000-$10,000
- **LOW:** WQS < 0.5 or size < $1,000

---

## Data Flow

### Trade Execution Flow

```
1. WebSocket receives WHALE_TRADE event
   ↓
2. WhaleTradeDetector validates and classifies
   ↓
3. Create TradeSignal
   ↓
4. WQS Filter: Check whale quality score (>0.5)
   ↓
5. ThreeStageFilter: Market quality, liquidity, timing
   ↓
6. AdaptiveKellySizer: Calculate position size
   ↓
7. RiskManager: Check all risk limits
   ↓
8. SlippageEstimator: Estimate execution cost
   ↓
9. OrderPlacer: Submit order to Polymarket
   ↓
10. FillConfirmer: Wait for fill (WebSocket + polling)
    ↓
11. PositionTracker: Record new position
    ↓
12. Database: Update positions, orders, trades tables
    ↓
13. PnLCalculator: Start real-time P&L tracking
```

**Latency Budget (Total: <2s):**
- Event detection: <500ms
- Signal processing: <300ms
- Risk checks: <200ms
- Order submission: <500ms
- Fill confirmation: <500ms

---

## Database Schema Updates

### Required Changes

#### New Indexes (for performance)
```sql
-- Fast position lookup
CREATE INDEX idx_positions_user_status ON positions(user_address, status);
CREATE INDEX idx_positions_market_status ON positions(market_id, status);

-- Fast order lookup
CREATE INDEX idx_orders_status_time ON orders(status, created_at DESC);
CREATE INDEX idx_orders_whale ON orders(source_whale, created_at DESC);

-- Fast trade lookup
CREATE INDEX idx_trades_whale_time ON trades(trader_address, timestamp DESC);
```

#### New Columns (if needed)
```sql
-- Add to orders table
ALTER TABLE orders ADD COLUMN slippage_estimate NUMERIC(5, 4);
ALTER TABLE orders ADD COLUMN execution_latency_ms INTEGER;

-- Add to positions table
ALTER TABLE positions ADD COLUMN trailing_stop_price NUMERIC(10, 6);
ALTER TABLE positions ADD COLUMN last_pnl_update TIMESTAMP;
```

---

## Week 2 Implementation Plan

### Task 1: Design Core Architecture ✅ (You Are Here)
**Duration:** 1 day
**Deliverable:** This document

---

### Task 2: Implement Order Execution Engine
**Duration:** 2-3 days
**Priority:** CRITICAL

**Subtasks:**
1. Build `SlippageEstimator`
   - Fetch order book from Polymarket API
   - Calculate VWAP and slippage
   - Add 2%/5% threshold checks

2. Build `OrderPlacer`
   - Integrate with `py-clob-client`
   - Implement retry logic with exponential backoff
   - Add order state machine

3. Build `FillConfirmer`
   - Poll for fill status (500ms interval)
   - Subscribe to WebSocket fill events
   - Handle partial fills

4. Write unit tests
   - Test slippage calculation
   - Test order placement with mocked API
   - Test retry logic and timeout handling

**Files to Create:**
- `src/trading/order_executor.py`
- `src/trading/slippage_estimator.py`
- `tests/test_order_executor.py`

---

### Task 3: Enhance Position Management System
**Duration:** 2 days
**Priority:** CRITICAL

**Subtasks:**
1. Build `PositionTracker`
   - CRUD operations for positions
   - Database integration
   - Position lifecycle management

2. Build `PnLCalculator`
   - Fetch current prices (WebSocket + REST)
   - Calculate unrealized P&L
   - Redis caching for prices (1s TTL)

3. Build `StopLossTakeProfitManager`
   - Check exit triggers every second
   - Auto-close positions on stop-loss/take-profit
   - Emit events for exits

4. Write integration tests
   - Test position opening/closing
   - Test P&L calculation accuracy
   - Test stop-loss/take-profit triggers

**Files to Create:**
- `src/trading/position_manager.py` (enhance existing)
- `src/trading/pnl_calculator.py`
- `src/trading/stop_loss_manager.py`
- `tests/test_position_manager.py`

---

### Task 4: Enhance WebSocket Client & Whale Detection
**Duration:** 1 day
**Priority:** HIGH

**Subtasks:**
1. Add message deduplication
2. Improve subscription management (per-whale subscriptions)
3. Add connection pooling for multiple markets
4. Implement REST API fallback
5. Add `WhaleTradeDetector` class

**Files to Modify:**
- `src/realtime/websocket_client.py`

---

### Task 5: Enhance Risk Management
**Duration:** 1 day
**Priority:** HIGH

**Subtasks:**
1. Implement circuit breakers
   - Daily loss limit ($500)
   - Max drawdown (10%)
   - Consecutive losses (5)

2. Add position limit checks
   - Per-position size ($1,000)
   - Per-market exposure ($5,000)
   - Per-whale exposure ($10,000)

3. Add risk monitoring dashboard endpoint
4. Write risk tests

**Files to Modify:**
- `src/risk/live_risk_manager.py`
- `tests/test_risk_manager.py`

---

### Task 6: End-to-End Integration Testing
**Duration:** 1 day
**Priority:** CRITICAL

**Subtasks:**
1. Create integration test suite
2. Test complete trade flow (whale trade → execution → position)
3. Test error handling (API failures, WebSocket disconnects)
4. Load testing (simulate 100 concurrent trades)
5. Latency benchmarking (target: <2s end-to-end)

**Files to Create:**
- `tests/integration/test_trade_flow.py`
- `tests/integration/test_error_handling.py`
- `tests/performance/test_latency.py`

---

### Task 7: Documentation & Deployment
**Duration:** 0.5 day
**Priority:** MEDIUM

**Subtasks:**
1. API documentation (function signatures, parameters)
2. Deployment guide (environment setup, config)
3. Monitoring setup (Prometheus metrics, Grafana dashboards)
4. Runbook (common issues, troubleshooting)

**Files to Create:**
- `docs/API_REFERENCE.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/MONITORING.md`
- `docs/RUNBOOK.md`

---

## Success Metrics (Week 2)

### Performance Metrics
- ✅ **Latency:** <500ms from whale trade detection to signal generation
- ✅ **Order Submission:** <2s from signal to order placement
- ✅ **Fill Rate:** >95% of orders filled successfully
- ✅ **P&L Update:** <1s latency for position P&L updates
- ✅ **WebSocket Uptime:** >99.9% connection availability

### Functionality Metrics
- ✅ **Order Execution:** Successfully place limit and market orders
- ✅ **Slippage Protection:** Reject orders with >2% slippage
- ✅ **Position Tracking:** 100% accuracy in position records
- ✅ **Risk Compliance:** 0 trades exceeding risk limits
- ✅ **Stop-Loss/Take-Profit:** Auto-close positions at thresholds

### Testing Metrics
- ✅ **Unit Test Coverage:** >80% code coverage
- ✅ **Integration Tests:** All critical flows tested
- ✅ **Error Handling:** Graceful degradation on failures
- ✅ **Load Testing:** System handles 100 concurrent trades

---

## Technology Stack

### Core Components
- **Language:** Python 3.11
- **Async Framework:** asyncio, aiohttp
- **WebSocket:** websockets library
- **Database:** PostgreSQL 15 (existing schema)
- **Cache:** Redis (for price caching)
- **API Client:** py-clob-client 0.20.0 (Polymarket SDK)

### Testing
- **Unit Tests:** pytest
- **Mocking:** pytest-mock, unittest.mock
- **Integration Tests:** pytest-asyncio
- **Load Testing:** locust or pytest-benchmark

### Monitoring (Week 14+)
- **Metrics:** Prometheus
- **Dashboards:** Grafana
- **Logging:** structlog
- **Tracing:** OpenTelemetry (future)

---

## Risk Mitigation

### Technical Risks

#### Risk 1: WebSocket Disconnections
**Impact:** Loss of real-time data, missed whale trades
**Mitigation:**
- Auto-reconnect with exponential backoff
- Buffer events during disconnection
- Fallback to REST API polling (15s interval)
- Alert on >30s disconnect

#### Risk 2: Order Placement Failures
**Impact:** Missed trades, reduced profitability
**Mitigation:**
- Retry logic (3 attempts, exponential backoff)
- Dead letter queue for failed orders
- Manual review dashboard
- Alert on >10% failure rate

#### Risk 3: Slippage Exceeds Estimates
**Impact:** Higher execution costs, reduced returns
**Mitigation:**
- Conservative slippage estimates (add 20% buffer)
- Cancel and retry if actual slippage >2x estimate
- Log slippage for analysis
- Adjust limits based on historical data

#### Risk 4: Position P&L Calculation Errors
**Impact:** Incorrect risk assessment, bad decisions
**Mitigation:**
- Reconcile with Polymarket API every 5 minutes
- Alert on >5% discrepancy
- Manual audit trail for all P&L changes
- Unit tests with known scenarios

#### Risk 5: Circuit Breaker False Triggers
**Impact:** Trading halted unnecessarily
**Mitigation:**
- Conservative thresholds ($500 daily loss, 10% drawdown)
- Manual override capability
- Review circuit breaker triggers weekly
- Adjust thresholds based on performance

---

## Next Steps

1. ✅ **Review this architecture document** (you are here)
2. 🚧 **Begin Task 2:** Implement Order Execution Engine
3. 🚧 **Begin Task 3:** Enhance Position Management System
4. 🚧 **Begin Task 4:** Enhance WebSocket Client
5. 🚧 **Begin Task 5:** Enhance Risk Management
6. 🚧 **Begin Task 6:** Integration Testing
7. 🚧 **Begin Task 7:** Documentation

**Estimated Timeline:** 7 days (Week 2 of roadmap)

---

## Appendix: Code Templates

### Example: Order Executor

```python
# src/trading/order_executor.py

from typing import Optional, Dict, Any
from decimal import Decimal
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
import logging

logger = logging.getLogger(__name__)

class OrderExecutor:
    """Execute orders on Polymarket CLOB API"""

    def __init__(self, clob_client: ClobClient):
        self.client = clob_client
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    async def execute_limit_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal
    ) -> Dict[str, Any]:
        """
        Execute a limit order with retry logic

        Returns:
            {
                'success': bool,
                'order_id': str,
                'status': str,
                'error': Optional[str]
            }
        """
        for attempt in range(self.max_retries):
            try:
                # Create order arguments
                order_args = OrderArgs(
                    token_id=token_id,
                    price=float(price),
                    size=float(size),
                    side=side,
                    fee_rate_bps=0  # Will be calculated by API
                )

                # Place order
                result = self.client.create_order(order_args)

                logger.info(f"Order placed successfully: {result.order_id}")

                return {
                    'success': True,
                    'order_id': result.order_id,
                    'status': 'SUBMITTED',
                    'error': None
                }

            except Exception as e:
                logger.error(f"Order placement failed (attempt {attempt+1}): {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                else:
                    return {
                        'success': False,
                        'order_id': None,
                        'status': 'FAILED',
                        'error': str(e)
                    }
```

### Example: Position Manager

```python
# src/trading/position_manager.py

from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy import select, update
from src.database.models import Position
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    """Manage trading positions"""

    def __init__(self, db_session):
        self.session = db_session

    async def open_position(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        source_whale: str
    ) -> Position:
        """Open a new position"""

        position = Position(
            position_id=f"{market_id}_{int(datetime.now().timestamp())}",
            user_address="our_wallet_address",
            market_id=market_id,
            token_id=token_id,
            outcome="YES" if "yes" in token_id.lower() else "NO",
            size=size,
            avg_entry_price=entry_price,
            current_price=entry_price,
            initial_value=size * entry_price,
            current_value=size * entry_price,
            cash_pnl=Decimal(0),
            percent_pnl=Decimal(0),
            source_whale=source_whale,
            status='OPEN'
        )

        self.session.add(position)
        await self.session.commit()

        logger.info(f"Opened position: {position.position_id}")

        return position

    async def update_pnl(
        self,
        position_id: str,
        current_price: Decimal
    ) -> Position:
        """Update position P&L with current market price"""

        position = await self.session.get(Position, position_id)

        if not position:
            raise ValueError(f"Position not found: {position_id}")

        # Calculate P&L
        if position.outcome == "YES":
            pnl = (current_price - position.avg_entry_price) * position.size
        else:
            pnl = (position.avg_entry_price - current_price) * position.size

        # Update position
        position.current_price = current_price
        position.current_value = position.size * current_price
        position.cash_pnl = pnl
        position.percent_pnl = (pnl / position.initial_value) * 100

        await self.session.commit()

        return position
```

---

**Document Version:** 1.0
**Last Updated:** November 2, 2025
**Next Review:** After Week 2 completion
