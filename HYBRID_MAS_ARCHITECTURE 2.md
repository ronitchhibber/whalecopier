# Whale Trader - Hybrid Multi-Agent System Architecture

**Version:** 2.0
**Date:** November 2025
**Status:** Design Complete → Implementation In Progress

---

## Executive Summary

This document describes the **Hybrid Multi-Agent System (MAS)** architecture for Whale Trader v2.0, combining:

1. **Institutional-grade statistical modules** (Research Brief #1: Precision Whale-Filtering)
2. **Multi-agent orchestration** (Research Brief #2: From Single Brain to Swarm Alpha)

The key insight: **Statistical modules are the "brains" of specialized agents**, while the MAS provides coordination, messaging, and resilience. This architecture is projected to:

- **+28% Sharpe Ratio improvement** (from dynamic whale allocation)
- **-26% drawdown reduction** (from dedicated Risk Agent veto power)
- **-60% decision latency** (from parallel agent processing)
- **+23% ranking accuracy lift** (from XGBoost learning-to-rank)

---

## 1. System Architecture: Statistical Engines + Agent Orchestration

### 1.1 Architectural Paradigm

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                           │
│              (LangGraph / CrewAI Coordinator)                        │
│  - Task delegation                                                   │
│  - Conflict resolution                                               │
│  - Agent lifecycle management                                        │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┬───────────┐
             ▼              ▼              ▼              ▼           ▼
┌───────────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────┐ ┌─────────────┐
│ WHALE DISCOVERY   │ │  MARKET      │ │   RISK     │ │ EXECUTION│ │ ATTRIBUTION │
│      AGENT        │ │ INTELLIGENCE │ │ MANAGEMENT │ │  AGENT   │ │   AGENT     │
│                   │ │    AGENT     │ │   AGENT    │ │          │ │             │
│ ┌───────────────┐ │ │              │ │            │ │          │ │             │
│ │ Composite     │ │ │ ┌──────────┐ │ │            │ │          │ │             │
│ │ Whale Scorer  │ │ │ │ Anomaly  │ │ │            │ │          │ │             │
│ │ (XGBoost)     │ │ │ │ Detector │ │ │            │ │          │ │             │
│ └───────────────┘ │ │ │ (EWMA)   │ │ │            │ │          │ │             │
│ ┌───────────────┐ │ │ └──────────┘ │ │            │ │          │ │             │
│ │ Skill vs Luck │ │ │              │ │            │ │          │ │             │
│ │ Analyzer      │ │ │              │ │            │ │          │ │             │
│ │ (DSR, PSR)    │ │ │              │ │            │ │          │ │             │
│ └───────────────┘ │ │              │ │            │ │          │ │             │
└───────────────────┘ └──────────────┘ └────────────┘ └──────────┘ └─────────────┘
             │              │              │              │              │
             └──────────────┴──────────────┴──────────────┴──────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EVENT-DRIVEN MESSAGING LAYER                      │
│  - Kafka: High-throughput event streaming (trades, market data)     │
│  - NATS/JetStream: Low-latency command/control                      │
│  - Redis: Real-time state cache (whale scores, risk metrics)        │
└─────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PERSISTENT STORAGE LAYER                         │
│  - PostgreSQL + TimescaleDB: Event sourcing + time-series           │
│  - Materialize: Real-time materialized views (CQRS read side)       │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Design Principles

1. **Statistical Modules as Agent Capabilities**
   - Each agent encapsulates 1-2 statistical/analytical modules
   - Modules are stateless, pure functions (easy to test and scale)
   - Agents handle state management, messaging, and orchestration

2. **Event-Driven Communication**
   - All inter-agent communication via message bus (Kafka/NATS)
   - Exactly-once semantics via Transactional Outbox Pattern
   - Asynchronous by default, synchronous only for critical decisions

3. **CQRS for State Management**
   - Write side: Event sourcing (append-only log in PostgreSQL)
   - Read side: Materialized views (Materialize/Redis)
   - Strong consistency for writes, eventual for reads

4. **Hybrid Agent Framework Strategy**
   - **LangGraph** for production trading pipeline (durability, checkpointing)
   - **CrewAI** for research/analytical agents (rapid prototyping)
   - Both frameworks can coexist, communicating via message bus

---

## 2. Agent Specifications: Roles, Capabilities, and Statistical Engines

### 2.1 Whale Discovery Agent

**Role:** Continuously discover, score, and rank high-quality whales; prune underperformers.

**Statistical Engines:**
- `CompositeWhaleScorer` (src/scoring/composite_whale_scorer.py)
- `SkillVsLuckAnalyzer` (src/scoring/skill_vs_luck_analyzer.py)

**Core Logic:**
```python
# Discovery Loop (runs every 10 minutes)
1. Fetch new whale candidates from Polymarket Subgraphs (PNL, Positions)
2. For each whale:
   a. Extract features (volume, PnL, concentration, timing)
   b. Calculate Deflated Sharpe Ratio (DSR)
   c. Calculate Probabilistic Sharpe Ratio (PSR)
   d. Run skill persistence test (rolling window regression)
   e. Compute composite score (XGBoost learning-to-rank)
3. Rank whales by lower confidence bound (conservative)
4. Apply Thompson Sampling for dynamic allocation weights
5. Publish WhaleDiscovery events to Kafka

# Pruning Loop (runs every 24 hours)
1. For existing whales:
   a. Run CUSUM changepoint detection on returns
   b. Check if PSR < threshold or DSR < 0
   c. Flag for removal if 3 consecutive failures
2. Publish WhalePruning events to Kafka
```

**Message Contracts:**
- **Subscribes:** `MarketDataUpdate` (for context)
- **Publishes:** `WhaleDiscovered`, `WhaleScoreUpdated`, `WhalePruned`

**Configuration:**
```yaml
whale_discovery:
  scan_interval_seconds: 600  # 10 minutes
  min_trades_for_significance: 30
  target_sharpe_ratio: 2.0
  psr_threshold: 0.85  # 85% probability SR > target
  dsr_threshold: 0.0  # Must be positive after selection bias correction
  thompson_sampling:
    prior_alpha: 1.0
    prior_beta: 1.0
    discount_factor: 0.95  # For non-stationary environment
```

---

### 2.2 Market Intelligence Agent

**Role:** Real-time monitoring of market conditions and anomalous whale activity.

**Statistical Engines:**
- `RealTimeAnomalyDetector` (src/analytics/realtime_anomaly_detector.py)

**Core Logic:**
```python
# Real-time Processing (event-driven)
1. Subscribe to Polymarket RTDS WebSocket (activity.trades topic)
2. For each incoming trade:
   a. Update EWMA baseline (60-minute window)
   b. Calculate Z-score
   c. If Z-score > 3.0 AND trade.is_whale:
      - Publish AnomalyAlert event (P1/P2/P3 priority)
      - Check cooldown state
      - Suppress if alert storm detected
3. Publish MarketRegimeChange events when volatility shifts detected

# Market Regime Detection (runs every 5 minutes)
1. Calculate rolling volatility (30-day EWMA)
2. Use Bai-Perron test for structural breaks
3. Classify regime: TRENDING, RANGING, HIGH_VOLATILITY, LOW_LIQUIDITY
4. Publish regime to Redis + Kafka
```

**Message Contracts:**
- **Subscribes:** `activity.trades` (RTDS), `MarketDataUpdate`
- **Publishes:** `AnomalyAlert`, `MarketRegimeChange`

**Performance Target:**
- End-to-end latency: < 2 seconds
- Alert capture rate: > 92% for significant whale trades
- False positive rate: < 1 alert / 5 minutes

---

### 2.3 Risk Management Agent

**Role:** The **ultimate arbiter** of capital allocation with absolute veto power.

**Statistical Engines:**
- Fractional Kelly Criterion
- CVaR (Expected Shortfall) calculator
- Portfolio correlation analyzer (Ledoit-Wolf)

**Core Logic:**
```python
# Trade Approval Flow (synchronous RPC)
1. Receive TradeProposal event from Orchestrator
2. Fetch current portfolio state from Materialize
3. Calculate proposed position size using Fractional Kelly (k=0.25)
4. Enforce hard constraints:
   a. '2% Rule': No single trade > 2% of portfolio
   b. Portfolio CVaR(97.5%) < 5%
   c. Correlation check: New trade correlation with portfolio < 0.7
   d. Daily loss circuit breaker: If daily loss > 5%, HALT all trading
5. If all checks pass:
   - Publish ApprovedTrade event
   Else:
   - Publish RejectedTrade event with reason
   - Log to audit trail

# Portfolio Risk Monitoring (runs every 60 seconds)
1. Calculate realized + unrealized P&L
2. Update underwater plot (drawdown from HWM)
3. If drawdown > 20%:
   - Reduce exposure by 50% (emergency de-risk)
   - Publish EmergencyDeRisk event
4. Check for correlated blowups (all top whales losing simultaneously)
```

**Message Contracts:**
- **Subscribes:** `TradeProposal`, `OrderFilled`, `MarketDataUpdate`
- **Publishes:** `ApprovedTrade`, `RejectedTrade`, `EmergencyDeRisk`, `RiskAlert`

**Configuration:**
```yaml
risk_management:
  kelly_fraction: 0.25  # Quarter-Kelly (conservative)
  max_position_pct: 2.0  # 2% per trade
  max_portfolio_cvar: 5.0  # 5% CVaR at 97.5% confidence
  max_correlation: 0.7
  circuit_breaker:
    daily_loss_pct: 5.0
    max_drawdown_pct: 20.0
    emergency_deleverage_pct: 50.0
```

**Projected Impact:**
- **-26% drawdown reduction** (from veto authority)
- **+15% capital efficiency** (from optimal Kelly sizing)

---

### 2.4 Execution Agent

**Role:** The **only** agent with private key access; executes approved trades with sub-second latency.

**Core Logic:**
```python
# Order Execution Flow
1. Receive ApprovedTrade event from Risk Agent
2. Fetch current orderbook from Polymarket CLOB API
3. Construct EIP-712 order message:
   - Calculate optimal limit price (improve on mid by 2 ticks)
   - Set expiration (5 minutes)
4. Sign order with private key (HSM/MPC)
5. Submit to CLOB REST API
6. Monitor order status via WebSocket:
   a. If partial fill after 30s → cancel + retry
   b. If no fill after 60s → cancel + re-assess
7. On fill:
   - Publish OrderFilled event
   - Update position tracking in Redis

# Smart Order Routing (SOR)
1. If order size > 10% of best bid/ask depth:
   - Split into iceberg orders (show 10% at a time)
2. If spread > 3%:
   - Place passive maker order (capture spread)
3. If urgent (anomaly alert):
   - Take liquidity aggressively
```

**Message Contracts:**
- **Subscribes:** `ApprovedTrade`
- **Publishes:** `OrderSubmitted`, `OrderFilled`, `OrderCancelled`, `ExecutionError`

**Security:**
- Private keys stored in AWS KMS or Fireblocks MPC
- All order signatures use EIP-712 standard
- Dual control: Requires approval from Risk Agent before execution

**Performance Target:**
- Order submission latency: < 500ms
- Fill rate: > 95% for limit orders within 60s

---

### 2.5 Performance Attribution Agent

**Role:** Post-trade analysis to attribute P&L and recommend rebalancing.

**Statistical Engines:**
- Market impact analyzer (Section 7 of Brief #1)
- Shapley value calculator (for fair attribution)
- Signal decay analyzer (IC half-life)

**Core Logic:**
```python
# Attribution Analysis (runs every 6 hours)
1. For each whale:
   a. Calculate realized + unrealized P&L
   b. Calculate Shapley value (contribution to portfolio)
   c. Analyze correlation with other whales
   d. Calculate Information Coefficient (IC)
   e. Estimate IC half-life (how fast alpha decays)
2. Identify unique alpha sources:
   - Whales with low correlation (<0.3) to portfolio
   - Whales with persistent IC (half-life > 7 days)
3. Generate rebalancing recommendations:
   - Increase allocation to unique, high-Shapley whales
   - Decrease allocation to redundant, high-correlation whales
4. Publish PortfolioAttribution report

# Market Impact Measurement (event-driven)
1. For each OrderFilled event:
   a. Fetch pre-trade orderbook state (from cache)
   b. Fetch post-trade orderbook state (5 minutes after)
   c. Calculate immediate price impact
   d. Calculate permanent vs transient impact
   e. Store in TimescaleDB for analytics
```

**Message Contracts:**
- **Subscribes:** `OrderFilled`, `MarketDataUpdate`
- **Publishes:** `PortfolioAttribution`, `RebalancingRecommendation`

---

### 2.6 Orchestrator Agent

**Role:** Coordinates all agents, manages task delegation, and resolves conflicts.

**Core Logic:**
```python
# Decision Orchestration Flow
1. Whale Discovery Agent identifies new opportunity
   ↓ Publishes WhaleDiscovered event
2. Orchestrator receives event, creates task graph:
   Task 1: Market Intelligence Agent → assess current regime
   Task 2: Risk Agent → check portfolio constraints
   (Tasks 1 & 2 run in parallel)
3. Orchestrator aggregates responses:
   - If Market Intelligence: regime = HIGH_VOLATILITY
     → Reduce position size by 50%
   - If Risk Agent: veto = TRUE
     → Abort, do not execute
4. If all checks pass:
   - Send TradeProposal to Risk Agent for final approval
   - On approval, forward to Execution Agent
5. Track task completion, handle failures with retries

# Agent Health Management
1. Monitor agent heartbeats (every 30s)
2. If agent unresponsive > 90s:
   - Restart agent (Kubernetes rolling restart)
3. If agent error rate > 10%:
   - Publish AgentHealthDegraded event
   - Activate circuit breaker for that agent
```

**Framework:** LangGraph (for stateful orchestration with checkpointing)

**Message Contracts:**
- **Subscribes:** All agent events
- **Publishes:** `TaskAssigned`, `TaskCompleted`, `OrchestratorDecision`

---

## 3. Event-Driven Messaging Layer

### 3.1 Message Bus Architecture

**Primary:** Apache Kafka (event streaming)
- Topics: `whale.discovered`, `trade.approved`, `order.filled`, `market.data`
- Partitioning: By market_id for parallel processing
- Retention: 7 days (configurable)
- Exactly-once semantics: Kafka transactions + idempotent producers

**Secondary:** NATS JetStream (command/control)
- For synchronous RPC (Risk Agent approval requests)
- Lower latency than Kafka (<10ms)
- Subject-based routing: `risk.approve.{market_id}`

**Cache:** Redis
- Real-time state: current whale scores, portfolio P&L, orderbook snapshots
- TTL: 5 minutes
- Use cases: Fast reads for dashboards, agent queries

### 3.2 Message Schema (AsyncAPI)

```yaml
# Example: WhaleDiscovered event
WhaleDiscovered:
  type: object
  properties:
    event_id:
      type: string
      format: uuid
    timestamp:
      type: string
      format: date-time
    whale_address:
      type: string
      pattern: '^0x[a-fA-F0-9]{40}$'
    composite_score:
      type: number
      minimum: 0
      maximum: 100
    score_components:
      type: object
      properties:
        profitability_score: {type: number}
        market_impact_score: {type: number}
        risk_control_score: {type: number}
    statistical_significance:
      type: object
      properties:
        deflated_sharpe_ratio: {type: number}
        probabilistic_sharpe_ratio: {type: number}
        is_significant: {type: boolean}
    thompson_sampling_weight:
      type: number
      description: "Allocation weight from bandit model"
```

### 3.3 Exactly-Once Semantics

**Problem:** Duplicate trades due to at-least-once delivery can cause capital leaks.

**Solution:** Transactional Outbox Pattern
```python
# Pseudo-code for Execution Agent
@transactional
def execute_trade(approved_trade):
    # 1. Write trade to database (outbox table)
    db.outbox.insert({
        'event_type': 'OrderSubmitted',
        'payload': approved_trade,
        'status': 'PENDING'
    })
    db.commit()  # Atomic commit

    # 2. CDC tool (Debezium) reads outbox table
    # 3. Publishes event to Kafka (exactly-once)
    # 4. Updates outbox status to 'PUBLISHED'
```

---

## 4. Real-Time Learning Loop

### 4.1 Dynamic Whale Allocation (Thompson Sampling)

**Algorithm:** Discounted Thompson Sampling (for non-stationary environment)

```python
# Thompson Sampling Update (after each trade)
def update_whale_allocation(whale_address, trade_pnl):
    # Fetch current beta distribution parameters
    alpha, beta = bandit_state[whale_address]

    # Update based on trade outcome
    if trade_pnl > 0:
        alpha += 1 * discount_factor ** time_since_last_trade
    else:
        beta += 1 * discount_factor ** time_since_last_trade

    # Sample from posterior
    sampled_probability = np.random.beta(alpha, beta)

    # Allocation weight proportional to sampled probability
    allocation_weight = sampled_probability / sum(all_sampled_probabilities)

    return allocation_weight
```

**Configuration:**
```yaml
thompson_sampling:
  discount_factor: 0.95  # Emphasize recent performance
  retraining_interval_hours: 168  # Weekly
  exploration_bonus: 0.1  # Bonus for under-sampled whales
  min_trades_before_pruning: 10
```

**Projected Impact:**
- **+28% Sharpe Ratio improvement**
- **Automatic pruning of 17% of degraded whales**

### 4.2 RL Position Sizing (Future Enhancement)

**Algorithm:** Proximal Policy Optimization (PPO)

**State Space:**
- Current portfolio value
- Whale's recent Sharpe ratio (30-day)
- Market volatility regime
- Portfolio correlation with new trade

**Action Space:**
- Position size (continuous, 0-5% of portfolio)

**Reward Function:**
- Differential Sharpe Ratio (incremental contribution to portfolio SR)

**Implementation:** To be added in Phase 2 (Week 8-12)

---

## 5. Deployment Architecture

### 5.1 Kubernetes Deployment

```yaml
# Example: Whale Discovery Agent
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whale-discovery-agent
spec:
  replicas: 2  # Active-passive HA
  template:
    spec:
      containers:
      - name: agent
        image: whale-trader/discovery-agent:v2.0
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          periodSeconds: 10
        env:
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: kafka:9092
        - name: POSTGRES_DSN
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: dsn
```

### 5.2 Observability Stack

**Metrics:** Prometheus + Grafana Mimir
- Agent-specific KPIs: whale discovery rate, approval rate, execution latency
- System health: Kafka consumer lag, CPU/memory utilization
- Business metrics: portfolio P&L, Sharpe ratio, max drawdown

**Logs:** Grafana Loki
- Structured logging (JSON)
- Correlation IDs for distributed tracing

**Traces:** Grafana Tempo + OpenTelemetry
- End-to-end trace from whale discovery → execution
- Latency breakdown by agent

**Dashboards:**
1. **Executive Dashboard:** Portfolio P&L, Sharpe, drawdown
2. **Agent Performance:** Task completion rate, error rate, latency
3. **Risk Dashboard:** Current CVaR, position concentration, circuit breaker status
4. **Discovery Dashboard:** New whales found, whale score distribution, Thompson Sampling weights

---

## 6. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2) ✅ COMPLETED
- [x] Composite Whale Scorer
- [x] Skill vs Luck Analyzer
- [x] Real-Time Anomaly Detector
- [x] Hybrid architecture design

### Phase 2: Agent Development (Weeks 3-4)
- [ ] Whale Discovery Agent
- [ ] Risk Management Agent
- [ ] Market Intelligence Agent
- [ ] Execution Agent
- [ ] Performance Attribution Agent
- [ ] Orchestrator Agent

### Phase 3: Messaging & Persistence (Week 5)
- [ ] Kafka cluster setup (3-node)
- [ ] NATS JetStream setup
- [ ] PostgreSQL + TimescaleDB
- [ ] Materialize for real-time views
- [ ] Redis cluster for caching

### Phase 4: Integration & Testing (Week 6)
- [ ] Agent integration tests
- [ ] End-to-end simulation (paper trading)
- [ ] Backtest on historical data (6 months)
- [ ] Chaos testing (kill agents, network partition)

### Phase 5: Canary Deployment (Week 7)
- [ ] 1% capital allocation
- [ ] Monitor for 48 hours
- [ ] Validate: P&L, latency, error rate
- [ ] Scale to 10% → 50% → 100%

---

## 7. Success Metrics

| Metric | Baseline (v0.1) | Target (v2.0) | Measurement |
|--------|----------------|---------------|-------------|
| **Sharpe Ratio** | 1.8 | 2.3 (+28%) | Daily returns, rolling 90-day |
| **Max Drawdown** | -38% | -28% (-26%) | Peak-to-trough |
| **Decision Latency** | 120s | 45s (-63%) | Discovery → execution |
| **Whale Ranking Accuracy** | - | +23% NDCG | Backtested ranking vs realized P&L |
| **System Uptime** | 97% | 99.9% | Kubernetes liveness probes |
| **False Positive Alerts** | - | < 1 / 5 min | Anomaly detector precision |

---

## 8. Next Steps

1. **Implement Whale Discovery Agent** (Week 3)
2. **Implement Risk Management Agent** (Week 3)
3. **Set up Kafka cluster** (Week 5)
4. **Integrate agents with LangGraph orchestrator** (Week 4)
5. **Deploy to staging for paper trading** (Week 6)

---

## References

- Research Brief #1: *Precision Whale-Filtering on Polymarket: From Raw Streams to Actionable Alpha*
- Research Brief #2: *From Single Brain to Swarm Alpha: How a Multi-Agent Copy-Trading Stack Can Lift Sharpe 30%*
- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- Apache Kafka Documentation: https://kafka.apache.org/documentation/
- Polymarket API Documentation: https://docs.polymarket.com/
