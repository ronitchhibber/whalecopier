# Deep Research Prompt: Building Predictive Backtest for Polymarket Whale Copy-Trading
## For: AI Agent Implementation

---

## CONTEXT & CONSTRAINTS

### Current Situation
You are an AI agent tasked with implementing a production-grade backtest system for a Polymarket whale copy-trading strategy. You have:

**Existing Codebase:**
- `src/services/backtester.py` - Current backtest with synthetic timestamps and probabilistic outcomes
- `libs/common/models.py` - SQLAlchemy models (Market, Trade, Whale, etc.)
- 479 whale trades in database spanning only 19.5 hours
- 57 unique markets, 0 market resolutions stored
- Conservative methodology: 20% discount + 2% fees

**Technical Stack:**
- Python 3.9
- PostgreSQL database
- SQLAlchemy ORM
- AsyncIO for async operations
- No web3.py currently installed
- Limited API access (Polymarket public APIs only)

**Critical Discovery:**
- Polymarket Data API `/trades` endpoint has 10K pagination limit with NO time-based filtering
- Gamma API has historical events but from 2021-2023 (ancient)
- Cannot fetch "60 days of historical resolved markets" via standard REST APIs
- Blockchain querying is the only path to real historical data

**Your Mission:**
Build a backtest that accurately predicts live trading returns using real historical data and realistic execution modeling.

---

## RESEARCH AREAS

### 1. POLYMARKET ON-CHAIN DATA ARCHITECTURE

**Question:** How do I efficiently extract 60+ days of historical whale trades and market resolutions from Polygon blockchain without getting rate-limited or banned?

**Specific Challenges:**
- Don't have Polygon RPC node (using public RPCs)
- Don't know CTF Exchange contract ABI
- Don't know event signatures for OrderFilled events
- How to map on-chain data to Polymarket's market structure?
- How to handle pagination when querying millions of blocks?

**What I Need to Learn:**
1. **CTF Exchange Contract Details**
   - Contract address: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
   - What events does it emit? (OrderFilled, OrderCancelled, etc.)
   - How to decode event logs to extract trade data?
   - Example transaction to reverse-engineer

2. **Conditional Tokens Framework (CTF)**
   - Contract address: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
   - How are market resolutions stored on-chain?
   - What does `payoutNumerators` array mean? ([1,0] = YES, [0,1] = NO?)
   - How to query resolution status for a condition_id?

3. **Efficient Blockchain Querying**
   - Recommended Polygon RPC providers (free tier limits?)
   - How to batch event log queries (block ranges)?
   - How to checkpoint progress (avoid re-fetching)
   - Typical query: "Get all OrderFilled events where maker/taker = whale_address from block X to Y"

4. **Data Mapping**
   - On-chain `condition_id` → Polymarket `market_id` mapping
   - On-chain `token_id` → YES/NO outcome mapping
   - Price encoding (are prices stored as integers? What decimals?)
   - Size encoding (how many decimals for share amounts?)

**Provide:**
- Working Python code snippets using web3.py
- Example ABI for CTF Exchange (even if partial)
- Recommended RPC endpoints with rate limits
- Block number ranges for last 90 days on Polygon
- Error handling strategies for RPC failures

---

### 2. THE GRAPH SUBGRAPH AS ALTERNATIVE

**Question:** Can I use Polymarket's subgraph on The Graph to avoid raw blockchain queries? If so, how?

**Specific Challenges:**
- Don't know if Polymarket has a public subgraph
- Don't know GraphQL schema
- Don't know query limits (The Graph has query complexity limits)
- How to handle pagination in GraphQL?

**What I Need to Learn:**
1. **Subgraph Discovery**
   - Is there a Polymarket subgraph? URL?
   - Is it on The Graph's hosted service or decentralized network?
   - What entities are indexed? (trades, markets, users, positions?)

2. **GraphQL Query Design**
   - Schema documentation or example queries
   - How to query trades for specific whale address?
   - How to filter by timestamp (last 90 days)?
   - Pagination strategy (skip/first vs cursor-based)

3. **Query Limits**
   - Maximum results per query (typically 1000)
   - Query complexity points (nested queries cost more)
   - Rate limiting (requests per second?)
   - How to batch queries efficiently?

4. **Data Completeness**
   - Does subgraph include market resolutions?
   - Are all trades indexed or only large ones?
   - Latency between on-chain event and subgraph indexing?

**Provide:**
- Subgraph endpoint URL (if exists)
- Example GraphQL queries for:
  - Fetching whale trades
  - Fetching market resolutions
  - Filtering by time range
- Python code using `gql` or `requests` for GraphQL queries
- Workarounds for query complexity limits

---

### 3. REALISTIC EXECUTION MODELING (PREDICTION MARKETS SPECIFIC)

**Question:** How do I model copy-trade execution in prediction markets where liquidity is thin and prices jump on news?

**Specific Challenges:**
- Prediction markets behave differently than equities (discrete events, not continuous)
- Don't have order book time-series data
- Don't know typical bid-ask spreads on Polymarket
- Don't know how fast prices move after whale trade

**What I Need to Learn:**
1. **Latency Distribution**
   - Typical WebSocket → database → decision → execution latency for copy-trading bots
   - Best case: Using WebSocket for whale trade detection (100-500ms?)
   - Typical case: REST API polling every X seconds (1-5s?)
   - Worst case: Email/Discord alert → manual execution (10-60s?)
   - How to model this as probability distribution?

2. **Slippage in Prediction Markets**
   - Typical order book depth on Polymarket (how many $ at best bid/ask?)
   - Market impact function (is square-root model appropriate?)
   - Frontrunning risk (do MEV bots exist on Polygon for Polymarket?)
   - Empirical slippage: What % slippage for $100, $1000, $10000 orders?

3. **Price Dynamics After Whale Trade**
   - Do prices immediately jump after large whale trade (information leakage)?
   - How long does it take for order book to replenish?
   - Are there "stale" prices where trade appears available but is gone by time we submit?

4. **Order Types & Fill Probability**
   - Does Polymarket support limit orders? (Yes, it's an order book)
   - What % of limit orders fill within 30 seconds?
   - If limit order doesn't fill, should I submit market order? (worse price)
   - How to model "order doesn't fill, whale trade idea invalidated"?

**Provide:**
- Empirical data from Polymarket if available (research papers, blog posts)
- Proxy metrics from similar prediction markets (Augur, Kalshi)
- Code for modeling latency as log-normal distribution
- Market impact model calibrated to thin order books
- Decision tree: When to use market vs limit order

---

### 4. BACKTEST OVERFITTING PREVENTION (PRACTICAL)

**Question:** How do I ensure my backtest doesn't overfit to the specific whales/markets in my limited dataset?

**Specific Challenges:**
- Only have 479 trades (small sample size)
- Only 57 unique markets (market selection bias?)
- Whales discovered based on recent performance (survivorship bias)
- Testing multiple parameters (whale quality threshold, position size, etc.)

**What I Need to Learn:**
1. **Multiple Testing Correction**
   - I'm testing ~50 whales. How to adjust Sharpe ratio for this?
   - Bonferroni correction too conservative? What about False Discovery Rate?
   - Practical implementation: Given N whales tested, what p-value threshold?

2. **Sample Size Requirements**
   - Minimum number of trades for statistical significance?
   - Rules of thumb: Need 100+ trades? 500+? 1000+?
   - What if I only have 479 trades? Are results even meaningful?
   - How to calculate confidence intervals with small sample?

3. **Cross-Validation with Time-Series**
   - Walk-forward analysis: How many folds? What window size?
   - With only 19.5 hours of data, is cross-validation even possible?
   - Should I wait to collect more data before backtesting?

4. **Look-Ahead Bias Detection**
   - How to verify I'm not using future information?
   - Example: Am I using whale's "final quality score" to select which trades to copy?
   - Should whale quality be calculated on rolling window (only past data)?

**Provide:**
- Decision framework: "Is my dataset large enough to backtest?" checklist
- Code for Deflated Sharpe Ratio with multiple testing correction
- Minimum sample size calculators
- Walk-forward validation code that works with small datasets
- Automated look-ahead bias detector

---

### 5. REALISTIC POSITION SIZING (PORTFOLIO CONSTRAINTS)

**Question:** How do I size positions when I have limited capital and multiple whale signals competing?

**Specific Challenges:**
- Total capital: $10,000 (example)
- Can't copy every whale trade (would be over-leveraged)
- Multiple whales might trade the same market (duplication)
- Some markets have low liquidity (can't deploy large size)

**What I Need to Learn:**
1. **Kelly Criterion for Binary Bets**
   - Formula for prediction markets (different from stocks?)
   - Fractional Kelly: What fraction? (25%? 50%?)
   - How to estimate win probability (use whale's historical win rate?)
   - How to estimate win/loss magnitude (average gain vs loss per trade)

2. **Portfolio-Level Constraints**
   - Max % of capital per position (10%?)
   - Max % to single whale (30%?)
   - Max % to single market (20%?)
   - Max number of simultaneous positions (20?)
   - How to prioritize when multiple signals compete?

3. **Correlation Handling**
   - If 3 whales all buy "Trump wins 2024", should I 3x the position or cap at 1x?
   - How to measure correlation between whale trades?
   - How to adjust position size for correlated bets?

4. **Liquidity Constraints**
   - How to check if market has enough liquidity for my order?
   - Should I reduce size if liquidity is low?
   - How to query order book depth from Polymarket API?

**Provide:**
- Kelly criterion calculator for binary prediction markets
- Position sizing algorithm with multiple constraints
- Code to check Polymarket order book depth via API
- Correlation-adjusted position sizing formula
- Priority queue logic for competing signals

---

### 6. EDGE DECAY DETECTION (ACTIONABLE SIGNALS)

**Question:** How do I detect when a whale's edge has degraded and I should stop copying them?

**Specific Challenges:**
- Don't know how to implement CUSUM test
- Don't have enough data per whale for statistical tests
- Need real-time detection (not just post-hoc analysis)
- What threshold triggers "stop copying"?

**What I Need to Learn:**
1. **CUSUM Implementation**
   - Step-by-step CUSUM algorithm for returns time-series
   - How to choose threshold parameter (h)?
   - How to choose drift parameter (k)?
   - Can it work with only 20-50 trades per whale?

2. **Alternative Methods**
   - Page-Hinkley test (simpler than CUSUM?)
   - Simple rolling Sharpe ratio (last 20 trades)
   - Win rate regression (current vs historical)
   - Which method is most reliable with small sample?

3. **Real-Time Detection**
   - How to update CUSUM statistic after each new trade?
   - How to avoid false positives (random variance vs real decay)?
   - What's acceptable false positive rate? (10%? 5%? 1%?)

4. **Action Thresholds**
   - If CUSUM triggers, do I immediately stop? Or reduce allocation?
   - Should I have a "probation period" (watch but don't copy)?
   - How to handle "whale comes back" (edge returns)?

**Provide:**
- Working Python CUSUM implementation
- Calibration guide for threshold parameters
- Code for rolling window performance metrics
- Decision flowchart: "When to stop copying a whale"
- False positive rate calculator

---

### 7. MONTE CARLO VALIDATION (UNCERTAINTY QUANTIFICATION)

**Question:** How do I use Monte Carlo simulation to provide confidence intervals on backtest results?

**Specific Challenges:**
- Don't know how to bootstrap time-series data (can't just shuffle)
- Don't know how many simulations (100? 1000? 10000?)
- What distributions to use (normal? log-normal? empirical?)
- How to present results (mean? median? 5th percentile?)

**What I Need to Learn:**
1. **Bootstrap for Time-Series**
   - Block bootstrap (preserves temporal correlation)
   - Stationary bootstrap (random block lengths)
   - Can I just resample trades with replacement? (probably not)
   - How to preserve trade clustering effects?

2. **Simulation Design**
   - How many Monte Carlo runs for stable results?
   - What random variables to simulate?
     - Trade outcomes (win/loss)?
     - Trade sizes?
     - Trade arrival times?
     - Whale selection?

3. **Distribution Fitting**
   - Should I fit normal distribution to returns? (probably not)
   - Should I use empirical distribution (histogram)?
   - How to handle fat tails (large wins/losses)?
   - Use mixture models?

4. **Results Presentation**
   - Report median return (not mean) because of skewness?
   - Report 5th-95th percentile range (90% confidence interval)?
   - Plot distribution of returns?
   - What does "backtest return = $X ± $Y" mean?

**Provide:**
- Block bootstrap implementation for trade data
- Monte Carlo simulation code (1000+ runs)
- Code to fit distributions to empirical data
- Visualization code for return distribution
- Template for reporting: "Expected return: $X (90% CI: [$Y, $Z])"

---

### 8. DATA PIPELINE & WORKFLOW

**Question:** What's the practical workflow for collecting data, running backtests, and validating results?

**Specific Challenges:**
- Don't want to re-fetch blockchain data every time (slow)
- Need to cache/checkpoint progress
- Database migrations for new fields (market resolutions)
- How to incrementally update dataset?

**What I Need to Learn:**
1. **Data Collection Workflow**
   - Step 1: Fetch historical trades (one-time, save to DB)
   - Step 2: Fetch market resolutions (one-time, save to DB)
   - Step 3: Set up hourly cron job for new data
   - How to handle failures/retries?
   - How to avoid duplicate trades?

2. **Database Schema Updates**
   - Need to add `market_resolution` column to markets table
   - Need to add `order_book_snapshot` to trades table?
   - Migration strategy (Alembic?)
   - Backward compatibility with existing code?

3. **Checkpoint/Resume Logic**
   - Save "last processed block number" to config
   - Resume from checkpoint if script crashes
   - How to verify data integrity after resume?

4. **Backtest Execution Flow**
   - Query database for all trades with resolutions
   - Run backtest engine (execution model + P&L calc)
   - Run validation (Monte Carlo, walk-forward)
   - Generate report (HTML/PDF)
   - Update dashboard with new results
   - How to automate this pipeline?

**Provide:**
- SQL migration scripts for new columns
- Checkpoint/resume implementation
- ETL pipeline code (Extract blockchain → Transform → Load DB)
- Automated backtest runner script
- Data quality checker (detect missing resolutions, gaps in data)

---

### 9. PERFORMANCE OPTIMIZATION

**Question:** How do I make blockchain data collection and backtesting fast enough to be practical?

**Specific Challenges:**
- Querying 90 days of Polygon blocks could take hours
- Running 1000 Monte Carlo simulations could be slow
- Need results quickly to iterate

**What I Need to Learn:**
1. **Parallel Blockchain Queries**
   - Can I query multiple block ranges in parallel?
   - Use `asyncio` with multiple RPC endpoints?
   - Rate limiting strategy (exponential backoff?)
   - How many parallel requests before RPC bans me?

2. **Database Optimization**
   - Indexes on timestamp, whale_address, market_id?
   - Use PostgreSQL JSONB for order book snapshots?
   - Batch inserts (1000s of trades at once)?
   - Connection pooling?

3. **Backtest Performance**
   - Vectorize calculations with NumPy/Pandas?
   - Avoid Python loops over trades?
   - Use Numba JIT compilation?
   - Profile code to find bottlenecks?

4. **Caching Strategy**
   - Cache market resolutions (don't re-query)
   - Cache whale statistics (recompute only when new trades)
   - Use Redis for fast lookups?

**Provide:**
- Async blockchain querying code (parallel requests)
- Database schema with proper indexes
- Vectorized backtest engine (Pandas/NumPy)
- Profiling results showing bottlenecks
- Caching decorator for expensive computations

---

### 10. ERROR HANDLING & ROBUSTNESS

**Question:** How do I handle all the things that can go wrong in a complex data pipeline?

**Specific Challenges:**
- RPC endpoints go down
- Markets never resolve (disputed/abandoned)
- Whales get blacklisted (address changes)
- Database connection drops mid-query
- Backtest runs out of memory

**What I Need to Learn:**
1. **RPC Failover**
   - List of backup Polygon RPC endpoints
   - Automatic failover when primary fails
   - Detect rate limiting vs actual errors
   - Exponential backoff retry logic

2. **Missing Data Handling**
   - What if market resolution is not available?
   - What if trade is missing order book data?
   - Should I exclude trade from backtest or impute?
   - How to track data quality metrics?

3. **Database Resilience**
   - Connection pooling with auto-reconnect
   - Transaction rollback on error
   - Deadlock detection and retry
   - Data validation before insert

4. **Memory Management**
   - What if querying 100K trades loads all into memory?
   - Streaming/chunking strategies
   - Garbage collection tuning
   - Monitoring memory usage

**Provide:**
- Robust RPC client with failover
- Data quality validator (checks for missing fields)
- Chunked database queries (process 1000 trades at a time)
- Error logging and alerting setup
- Memory profiling tools

---

## OUTPUT FORMAT

For each research area, provide:

### 1. DIRECT ANSWERS
- Specific values (RPC URLs, contract addresses, block numbers)
- Working code snippets (not pseudocode)
- Configuration examples

### 2. DECISION FRAMEWORKS
- "Should I use X or Y?" → Decision tree
- "How do I know if Z?" → Checklist
- "When to stop W?" → Threshold rules

### 3. CODE TEMPLATES
- Complete, runnable Python functions
- Error handling included
- Type hints and docstrings
- Example usage

### 4. VALIDATION CRITERIA
- "How do I know if this is correct?" → Unit tests
- "What should the output look like?" → Example outputs
- "How do I debug if it fails?" → Troubleshooting guide

---

## SUCCESS METRICS

This research is successful if it enables me to:

1. ✅ Fetch 60+ days of whale trades from blockchain in <2 hours
2. ✅ Get market resolutions for 100% of closed markets
3. ✅ Run backtest with realistic execution model (latency + slippage)
4. ✅ Produce statistically significant results (p < 0.05)
5. ✅ Provide confidence intervals (5th-95th percentile)
6. ✅ Detect edge decay in real-time
7. ✅ Size positions optimally with Kelly criterion
8. ✅ Generate automated backtest report
9. ✅ Deploy continuous data collection pipeline
10. ✅ Validate against live trading (if data available)

---

## CONSTRAINTS

- **Time:** Need working implementation in 1-2 weeks
- **Budget:** $0 (use free tier APIs only)
- **Data:** Limited to public blockchain + Polymarket public APIs
- **Compute:** Running on MacBook (no GPU, no cloud)
- **Expertise:** I'm an AI agent (no human intuition for edge cases)

---

## IMMEDIATE NEXT STEPS

Based on this research, I will:

1. **Week 1:** Implement blockchain data collector
2. **Week 2:** Build execution model + validation suite
3. **Week 3:** Deploy, test, validate

Please provide research that is:
- ✅ **Actionable** (I can write code from it)
- ✅ **Specific** (exact URLs, block numbers, parameters)
- ✅ **Complete** (no "TODO" or "left as exercise")
- ✅ **Tested** (you've verified it works or provided test cases)

Thank you! This research will directly determine whether I can build a production-grade backtest system or have to settle for a toy simulation.
