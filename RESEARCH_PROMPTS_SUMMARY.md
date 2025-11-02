# Research Prompts Summary

## Overview

Three comprehensive research prompts have been created to guide the development of a production-grade whale copy-trading system:

1. **RESEARCH_PROMPT_COPY_TRADING_ENGINE.md** - Position sizing and trade execution configuration
2. **RESEARCH_PROMPT_SYSTEM_OPTIMIZATION.md** - Production deployment and system optimization
3. **RESEARCH_PROMPT_STRATEGY_DISCOVERY.md** - Novel strategy discovery and alpha generation

---

## 1. Copy-Trading Engine Configuration (6,500+ words)

**Purpose:** Design optimal position sizing, risk management, and trade filtering rules

**Key Research Areas:**
- Position sizing algorithms (Kelly criterion, quality factors, trade size ratios)
- Dynamic risk adjustments based on whale performance
- Trade filtering rules (market quality, whale behavior, portfolio limits)
- Risk management parameters (position limits, circuit breakers, concentration limits)
- Whale-specific sizing rules by tier (MEGA/HIGH/MEDIUM)
- Edge decay detection and quarantine procedures
- Market-specific adjustments (liquidity, age, probability)
- Backtesting validation methodology

**Expected Deliverables:**
- Complete position sizing formula with all parameters
- Risk parameter configuration table
- Trade filtering checklist (must-have vs. nice-to-have)
- Edge decay detection system with statistical methods
- 4-week implementation roadmap
- Python pseudocode for key algorithms

**Target Performance:**
- Sharpe Ratio: ≥2.0 (research paper target: 2.07)
- Max Drawdown: ≤15% (research paper: 11.2%)
- Win Rate: ≥55%
- Monthly positive return rate: ≥70%

---

## 2. System Optimization & Production Deployment (5,800+ words)

**Purpose:** Optimize performance, scalability, and reliability for production deployment

**Key Research Areas:**
- Real-time data pipeline architecture (WebSocket, event-driven)
- Caching strategy (API responses, database queries, computed metrics)
- WebSocket implementation for live updates
- Database optimization (indexes, query rewriting, TimescaleDB features)
- Monitoring and observability (metrics, logging, alerting)
- Production deployment options (VPS, containers, serverless, hybrid)
- Failover and disaster recovery procedures
- Performance benchmarking and load testing
- Security hardening (API, database, network)
- Cost optimization strategies

**Expected Deliverables:**
- Production architecture diagram with all components
- Caching strategy with TTL values and hit rate targets
- WebSocket message protocol specification
- Database index strategy with rationale
- Monitoring dashboard mockup with key metrics
- Deployment guide with step-by-step instructions
- Disaster recovery runbook
- Monthly infrastructure cost estimate with scaling projections

**Performance Targets:**
- API response time: <200ms (p95), <500ms (p99)
- Database query time: <50ms (p95), <100ms (p99)
- WebSocket latency: <100ms
- Cache hit rate: >90%
- System availability: >99.5%
- Target monthly cost: <$200 for 41 whales

---

## 3. Strategy Discovery & Alpha Generation (7,200+ words)

**Purpose:** Discover and validate novel trading strategies beyond simple whale copying

**Key Research Areas:**

**Whale Behavior Strategies:**
- Consensus vs. Contrarian (copy when multiple whales agree vs. fade consensus)
- Timing strategies (fast follow, delayed follow, smart entry on retracement)
- Whale specialization (politics specialists, sports experts, generalists)
- Confidence signals (large positions, repeated positions, rapid entry)

**Market Microstructure Strategies:**
- Liquidity arbitrage (low liquidity sniping, liquidity recovery)
- Spread exploitation (tight spread opportunities, bid-ask balance)
- Market age dynamics (new markets, mature markets, pre-resolution)

**Multi-Signal Strategies:**
- Whale + Sentiment (combine with Twitter/Discord sentiment)
- Whale + Volume (volume spike confirmation)
- Whale + Momentum (price momentum indicators)
- Multi-filter combinations (consensus + liquidity + spread + age)

**Dynamic Portfolio Strategies:**
- Risk parity across categories
- Volatility-adjusted position sizing
- Drawdown-responsive allocation
- Whale performance weighting (hot hand / cold hand)

**Exotic Strategies:**
- Anti-whale (fade losing traders)
- Whale rotation (copy top 10 by recent performance)
- Market maker (provide liquidity, exit on whale entry)
- News event strategy (piggyback on news-triggered whale trades)
- Cross-market arbitrage

**Machine Learning Strategies:**
- Whale trade classification (predict profitable trades)
- Price prediction models (predict price after whale trade)
- Optimal position sizing via reinforcement learning
- Market regime detection (identify bull/bear/choppy periods)

**Risk-Optimized Strategies:**
- Low volatility (Sharpe >2.0, drawdown <10%)
- High growth (returns >50%, accept drawdown <30%)
- Market neutral (long-short pairs, delta-neutral)
- Income strategy (high-frequency, small positions)

**Expected Deliverables:**
- Catalog of 10+ strategy candidates with hypotheses
- Detailed specifications for top 5 strategies
- Performance projections (Sharpe, drawdown, win rate)
- Strategy correlation matrix
- Recommended portfolio allocation
- 10-week implementation roadmap
- Strategy validation framework

**Target Performance:**
- Best strategies: Sharpe >2.5
- Portfolio Sharpe: >2.0 with diversification
- Win rate: >60%
- Max drawdown: <15%

---

## How to Use These Prompts

### Step 1: Choose Your Focus Area

**If you need to configure the copy-trading engine:**
→ Use **RESEARCH_PROMPT_COPY_TRADING_ENGINE.md**
- Feed to Claude/GPT-4 with your current whale data
- Ask for specific position sizing recommendations
- Request backtest validation plan

**If you need to deploy to production:**
→ Use **RESEARCH_PROMPT_SYSTEM_OPTIMIZATION.md**
- Get infrastructure architecture recommendations
- Optimize database and caching
- Set up monitoring and alerting

**If you need new trading strategies:**
→ Use **RESEARCH_PROMPT_STRATEGY_DISCOVERY.md**
- Discover novel alpha strategies
- Get validation frameworks
- Build strategy portfolio

### Step 2: Customize the Prompt

Each prompt has sections you can expand or remove:
- Add your specific constraints
- Include your current metrics
- Specify your risk tolerance
- Define your capital constraints

### Step 3: Iterate on Results

- Start with high-level recommendations
- Drill down into specific areas
- Request code implementation examples
- Ask for parameter sensitivity analysis

### Step 4: Validate and Implement

- Backtest recommended strategies
- Paper trade for 30 days
- Monitor performance vs. projections
- Iterate and optimize

---

## Combined Workflow

**Week 1-2: Engine Configuration**
- Use Prompt 1 to design position sizing
- Implement base formula and risk limits
- Backtest on historical data

**Week 3-4: Strategy Discovery**
- Use Prompt 3 to identify top 5 strategies
- Implement and backtest each strategy
- Select best 3 for paper trading

**Week 5-6: System Optimization**
- Use Prompt 2 for production architecture
- Optimize database and caching
- Set up monitoring

**Week 7-8: Paper Trading**
- Deploy top 3 strategies with virtual capital
- Monitor performance for 30 days
- Compare live vs. backtest results

**Week 9-10: Live Deployment**
- Scale up successful strategies
- Deploy to production with real capital
- Continue monitoring and optimization

---

## Research Prompt Files

1. **RESEARCH_PROMPT_COPY_TRADING_ENGINE.md** (6,500 words)
   - Position sizing
   - Risk management
   - Trade filtering
   - Edge decay detection

2. **RESEARCH_PROMPT_SYSTEM_OPTIMIZATION.md** (5,800 words)
   - Production architecture
   - Performance optimization
   - Monitoring and alerting
   - Deployment guide

3. **RESEARCH_PROMPT_STRATEGY_DISCOVERY.md** (7,200 words)
   - 10+ strategy types
   - ML strategies
   - Portfolio construction
   - Validation framework

**Total:** 19,500+ words of comprehensive research guidance

---

## Next Steps

1. **Review each prompt** to understand the full scope
2. **Prioritize research areas** based on your immediate needs
3. **Feed prompts to AI** (Claude, GPT-4) with your data
4. **Implement recommendations** following the roadmaps
5. **Validate with backtesting** before live deployment
6. **Iterate and optimize** based on results

Good luck building your whale copy-trading system!
