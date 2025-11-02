# Deep Research Prompt: Production System Optimization & Real-Time Monitoring

## Context

You have built a whale copy-trading system with:
- **41 qualified whales** tracked in real-time
- **Multiple trading strategies** (Top 5, High Sharpe, Diversified, Conservative, Aggressive)
- **Paper trading infrastructure** with $10K accounts per strategy
- **Dashboard UI** displaying real-time metrics and performance
- **Trade copying engine** that routes whale trades to active strategies

The system is functional but needs optimization for production deployment, real-time performance, and scalability.

## Current System Architecture

**Stack:**
- Backend: FastAPI (Python), PostgreSQL + TimescaleDB
- Frontend: React + Vite, auto-refreshing every 5 seconds
- Whale Discovery: Python scripts processing 1M+ trades
- Strategy Engine: 5 separate paper trading accounts

**Performance Bottlenecks Identified:**
- 24h metrics calculated on every API call (not cached)
- Whale qualification queries run repeatedly (no caching)
- Frontend polls 4 endpoints every 5 seconds (high API load)
- No real-time WebSocket updates (polling only)
- Trade copying is manual/simulated (no live integration)

## Your Mission

Research and provide recommendations for:
1. Real-time data pipeline optimization
2. Caching strategy for high-frequency metrics
3. WebSocket implementation for live updates
4. Database query optimization and indexing
5. Monitoring, alerting, and observability setup
6. Production deployment architecture
7. Failover and disaster recovery
8. Performance benchmarking and load testing

---

## Research Questions

### 1. Real-Time Data Pipeline Architecture

**Research optimal architecture for:**

a) **Whale Trade Ingestion**
   - Current: Batch scripts fetch trades every 15 minutes
   - Target: Near real-time (<10 second latency) whale trade detection
   - Options to evaluate:
     - Polymarket WebSocket API subscriptions (if available)
     - Polling with differential updates (last_trade_id tracking)
     - GraphQL subscriptions to The Graph subgraph
     - Event-driven architecture with message queue (RabbitMQ, Redis)

b) **Trade Processing Pipeline**
   ```
   [Whale Trade Detected] → [Validation] → [Strategy Matching] →
   [Position Sizing] → [Risk Checks] → [Execute Copy] → [Update Portfolio]
   ```
   - Where should each step execute? (API server, background worker, separate service?)
   - How to ensure atomic operations (all-or-nothing execution)?
   - How to handle race conditions (multiple whales trading simultaneously)?

c) **Data Flow Optimization**
   - Should whale metrics be pre-calculated and materialized?
   - Use PostgreSQL materialized views vs. Redis cache vs. in-memory store?
   - How often to refresh cached whale rankings and stats?

**Recommendation Needed:**
- Complete data pipeline architecture diagram
- Technology stack for each component
- Latency targets and SLAs for each stage
- Cost estimation (API calls, database queries, compute)

---

### 2. Caching Strategy & Performance

**Research optimal caching layers:**

a) **API Response Caching**
   - Which endpoints should be cached?
     - `/api/whales` - Cache for 30 seconds? 60 seconds?
     - `/api/stats/summary` - Cache for 15 seconds?
     - `/api/strategies` - Cache for 10 seconds?
     - `/api/trades` - Cache for 5 seconds?
   - Cache invalidation strategy:
     - Time-based TTL only?
     - Event-driven invalidation (on new trade)?
     - Hybrid approach?

b) **Database Query Caching**
   - Cache qualified whale addresses list (changes rarely)
   - Cache whale metrics (updated every 15 minutes)
   - Use Redis vs. Memcached vs. PostgreSQL query cache?
   - Cache hit rate targets (>80%? >90%?)

c) **Computed Metrics Caching**
   - Pre-calculate and store:
     - 24h trade counts per whale
     - 24h volume per whale
     - Active positions per strategy
     - Portfolio-level metrics
   - Update frequency: Real-time vs. every 1 min vs. every 5 min?

d) **Frontend State Management**
   - Should frontend cache strategy state locally?
   - Use React Context vs. Redux vs. Zustand for state?
   - Optimistic updates vs. wait-for-server confirmation?

**Recommendation Needed:**
- Complete caching architecture with TTL values
- Cache size estimations and memory requirements
- Invalidation strategy and consistency guarantees
- Performance improvement estimates (latency reduction)

---

### 3. WebSocket Real-Time Updates

**Research WebSocket implementation:**

a) **What Should Be Pushed via WebSocket?**
   - New whale trades (immediately as detected)
   - Strategy performance updates (every 10 seconds)
   - Portfolio balance changes (on trade execution)
   - System alerts (risk limit breaches, whale quarantines)
   - Dashboard metrics (replace 5-second polling)

b) **WebSocket Architecture**
   - Use existing FastAPI WebSocket support or separate WebSocket server?
   - How to scale WebSockets (sticky sessions, Redis Pub/Sub, Socket.io)?
   - Authentication and authorization for WebSocket connections?
   - Reconnection strategy (exponential backoff, resume from checkpoint)?

c) **Message Protocol Design**
   ```json
   {
     "type": "whale_trade",
     "whale_address": "0x...",
     "whale_name": "MrSparkly",
     "market_id": "...",
     "side": "BUY",
     "amount": 5000,
     "price": 0.65,
     "timestamp": "2025-11-02T23:15:00Z",
     "strategies_matched": ["top_5_whales", "high_sharpe"]
   }
   ```
   - What message types are needed?
   - Payload size optimization (minimize bandwidth)?
   - Message queue or direct push?

d) **Frontend Integration**
   - Replace polling with WebSocket listeners
   - Fallback to polling if WebSocket disconnects
   - Visual indicators for real-time updates (flash animation?)
   - Rate limiting (max 10 updates/second to avoid UI thrashing?)

**Recommendation Needed:**
- WebSocket architecture diagram
- Message protocol specification
- Frontend integration code structure
- Performance benchmarks (bandwidth, latency, connection count)

---

### 4. Database Optimization & Indexing

**Research query optimization:**

a) **Critical Query Performance**
   - `SELECT * FROM whales WHERE quality_score >= 70 AND ...` (runs every 5 seconds)
   - `SELECT COUNT(*) FROM trades WHERE timestamp >= NOW() - INTERVAL '24 hours'`
   - Strategy whale matching queries
   - Current query times? Target query times?

b) **Index Strategy**
   ```sql
   -- Current indexes (review and optimize)
   CREATE INDEX idx_whales_quality ON whales(quality_score);
   CREATE INDEX idx_whales_tier ON whales(tier);
   CREATE INDEX idx_trades_timestamp ON trades(timestamp);
   CREATE INDEX idx_trades_trader ON trades(trader_address);

   -- Potential composite indexes
   CREATE INDEX idx_whales_qualified ON whales(quality_score, total_trades, total_volume, win_rate, sharpe_ratio);
   CREATE INDEX idx_trades_24h ON trades(timestamp DESC, trader_address);
   ```
   - Which indexes are most valuable?
   - Index size vs. query performance tradeoff?
   - Partial indexes for qualified whales only?

c) **Query Rewriting**
   - Use CTEs vs. subqueries vs. joins?
   - Aggregate pushdown opportunities?
   - Query plan analysis (EXPLAIN ANALYZE)

d) **TimescaleDB Optimizations**
   - Continuous aggregates for 24h metrics?
   - Hypertable compression for old trades?
   - Retention policies (archive trades >6 months)?

**Recommendation Needed:**
- Complete index strategy with rationale
- Query rewrite examples for critical paths
- TimescaleDB optimization checklist
- Expected query performance improvements

---

### 5. Monitoring & Observability

**Research monitoring stack:**

a) **Metrics to Track**
   - **System Metrics:**
     - API response times (p50, p95, p99)
     - Database query times
     - Cache hit rates
     - WebSocket connection count
     - Memory usage, CPU usage

   - **Business Metrics:**
     - Active strategies count
     - Trades copied per hour
     - Strategy P&L per day
     - Whale discovery rate
     - Qualification rate (% of discovered whales)

   - **Error Metrics:**
     - Failed trade copies
     - API error rates (4xx, 5xx)
     - Database connection errors
     - Whale data fetch failures

b) **Monitoring Tools**
   - Prometheus + Grafana (open source)
   - Datadog or New Relic (commercial)
   - CloudWatch (if on AWS)
   - Custom dashboard vs. off-the-shelf?

c) **Alerting Rules**
   - Alert on: API response time >1 second for 5 minutes
   - Alert on: Database query time >500ms
   - Alert on: Strategy daily loss >-5%
   - Alert on: Whale discovery pipeline stopped for >1 hour
   - Alert on: Error rate >1% for 10 minutes

d) **Logging Strategy**
   - Structured logging (JSON) vs. text logs
   - Log levels: DEBUG, INFO, WARN, ERROR, CRITICAL
   - What to log:
     - Every whale trade detected
     - Every trade copy decision (execute or reject + reason)
     - Every risk limit breach
     - Every API request/response (sample 10%?)
   - Log retention: 30 days? 90 days?
   - ELK stack vs. CloudWatch Logs vs. Loki?

**Recommendation Needed:**
- Monitoring dashboard mockup (key metrics to display)
- Alerting rules with thresholds
- Logging infrastructure recommendations
- Estimated monitoring costs

---

### 6. Production Deployment Architecture

**Research production infrastructure:**

a) **Deployment Options**
   - **Option 1: Single VPS** (DigitalOcean, Linode)
     - Pros: Simple, cheap ($20-50/month)
     - Cons: No redundancy, manual scaling

   - **Option 2: Container Orchestration** (Kubernetes, Docker Swarm)
     - Pros: Auto-scaling, rolling deployments
     - Cons: Complex, higher cost

   - **Option 3: Serverless** (AWS Lambda, Cloud Run)
     - Pros: Auto-scaling, pay-per-use
     - Cons: Cold starts, state management challenges

   - **Option 4: Hybrid** (Managed services + VPS)
     - Pros: Best of both worlds
     - Cons: Multi-cloud complexity

b) **Service Architecture**
   ```
   [Load Balancer] → [API Server (2 instances)]
                  → [WebSocket Server (2 instances)]
                  → [Background Worker (2 instances)]

   [PostgreSQL Primary] → [PostgreSQL Replica (read)]
   [Redis Cache]
   [Message Queue]
   ```
   - How many instances of each service?
   - Vertical vs. horizontal scaling strategy?
   - Database: managed (RDS, Cloud SQL) vs. self-hosted?

c) **CI/CD Pipeline**
   - GitHub Actions vs. GitLab CI vs. Jenkins?
   - Deployment stages: dev → staging → production
   - Automated testing: unit tests, integration tests, load tests
   - Rollback strategy: blue-green deployment, canary deployment?

d) **Environment Configuration**
   - Separate .env files for dev/staging/prod
   - Secret management: AWS Secrets Manager, HashiCorp Vault, .env?
   - Feature flags for gradual rollout?

**Recommendation Needed:**
- Production architecture diagram
- Infrastructure cost estimate (monthly)
- Deployment process documentation
- Scaling strategy and triggers

---

### 7. Failover & Disaster Recovery

**Research resilience:**

a) **Failure Modes to Plan For**
   - API server crash (restart automatically)
   - Database connection lost (reconnect with exponential backoff)
   - Whale data source unavailable (failover to backup source?)
   - Disk space full (log rotation, auto-cleanup)
   - Memory leak (monitoring + auto-restart)

b) **High Availability Setup**
   - Active-passive vs. active-active deployment?
   - Health checks and automatic failover
   - Database replication (streaming replication, logical replication?)
   - Session state management (sticky sessions, shared Redis)

c) **Backup Strategy**
   - Database backups: daily full + hourly incremental?
   - Configuration backups (code, .env, nginx configs)
   - Backup retention: 30 days? 90 days?
   - Backup testing: monthly restore drills?

d) **Disaster Recovery Plan**
   - RTO (Recovery Time Objective): 1 hour? 4 hours?
   - RPO (Recovery Point Objective): 15 minutes? 1 hour?
   - Runbook for common failure scenarios
   - Contact list and escalation procedures

**Recommendation Needed:**
- Failure mode matrix (probability x impact)
- High availability architecture
- Backup and restore procedures
- DR runbook template

---

### 8. Performance Benchmarking & Load Testing

**Research testing strategy:**

a) **Load Testing Scenarios**
   - Concurrent users: 10, 50, 100 dashboard viewers
   - API requests: 100/sec, 500/sec, 1000/sec
   - Database queries: 50/sec, 200/sec, 500/sec
   - WebSocket connections: 100, 500, 1000 clients

b) **Performance Targets**
   - API response time: <200ms (p95), <500ms (p99)
   - Database query time: <50ms (p95), <100ms (p99)
   - WebSocket message delivery: <100ms
   - Cache hit rate: >90%
   - System availability: >99.5% (43 hours downtime/year)

c) **Load Testing Tools**
   - k6, Locust, JMeter, Artillery?
   - Scripting realistic user behavior
   - Gradual ramp-up vs. spike testing
   - Sustained load testing (24 hours)

d) **Stress Testing**
   - Find breaking point (max load before failures)
   - Identify bottlenecks (CPU, memory, database, network)
   - Test recovery after overload

**Recommendation Needed:**
- Load testing script examples
- Performance benchmarking plan
- Bottleneck identification methodology
- Optimization priority matrix

---

### 9. Security Considerations

**Research security hardening:**

a) **API Security**
   - Rate limiting (per IP, per user)
   - Input validation and sanitization
   - CORS configuration
   - HTTPS only (SSL/TLS certificates)

b) **Database Security**
   - Connection encryption (SSL)
   - Least privilege access (read-only user for queries)
   - Audit logging for sensitive operations
   - SQL injection prevention (parameterized queries)

c) **Secrets Management**
   - Environment variables vs. secret management service
   - API key rotation policy
   - Encryption at rest for sensitive data

d) **Network Security**
   - Firewall rules (only required ports)
   - Private network for database
   - DDoS protection (Cloudflare, AWS Shield)

**Recommendation Needed:**
- Security checklist for production deployment
- Threat model (STRIDE analysis)
- Security testing plan (penetration testing, vulnerability scanning)

---

### 10. Cost Optimization

**Research cost-effective infrastructure:**

a) **Infrastructure Costs**
   - Compute: $X/month (API servers, workers)
   - Database: $X/month (managed PostgreSQL)
   - Cache: $X/month (Redis)
   - Bandwidth: $X/month (API responses, WebSocket)
   - Monitoring: $X/month (Datadog, CloudWatch)

   - **Target total:** <$200/month for 41 whales, 5 strategies?

b) **Cost Optimization Strategies**
   - Use spot instances for non-critical workloads
   - Reserved instances for predictable load
   - Optimize database instance size (start small, scale up)
   - Cache aggressively to reduce database queries
   - Compress WebSocket messages to save bandwidth

c) **Scaling Cost Model**
   - Cost at 41 whales: $X
   - Cost at 100 whales: $Y
   - Cost at 1,000 whales: $Z
   - Where do costs increase most? (Database? API calls?)

**Recommendation Needed:**
- Infrastructure cost breakdown
- Cost optimization checklist
- Scaling cost projections
- ROI analysis (cost vs. trading returns)

---

## Research Deliverables

Please provide:

1. **Production Architecture Diagram**
   - Complete system architecture with all components
   - Data flow and communication paths
   - Failover and redundancy setup

2. **Performance Optimization Plan**
   - Caching strategy with TTL values
   - Database indexes and query optimizations
   - Expected performance improvements

3. **Real-Time System Design**
   - WebSocket implementation plan
   - Message protocol specification
   - Frontend integration approach

4. **Monitoring & Alerting Setup**
   - Key metrics dashboard
   - Alerting rules and thresholds
   - Logging infrastructure

5. **Deployment Guide**
   - Step-by-step deployment instructions
   - CI/CD pipeline configuration
   - Environment setup checklist

6. **Disaster Recovery Plan**
   - Backup and restore procedures
   - Failover scenarios and responses
   - DR runbook

7. **Cost Estimate**
   - Monthly infrastructure costs
   - Scaling cost projections
   - Cost optimization recommendations

---

## Output Format

Structure your response as:

### Executive Summary
(Top 3-5 recommendations for immediate implementation)

### Production Architecture
(Diagram + component descriptions)

### Performance Optimization Roadmap
(Prioritized list of optimizations with impact estimates)

### Real-Time Data Pipeline
(Architecture + implementation plan)

### Monitoring Setup
(Dashboard mockup + alerting rules + logging strategy)

### Deployment Plan
(Infrastructure provisioning + CI/CD setup + rollout strategy)

### Cost Analysis
(Current costs + optimized costs + scaling projections)

### Implementation Timeline
(Week-by-week plan with milestones)
