# Deep Research Prompt: Strategy Discovery & Alpha Generation

## Context

You have identified **41 high-quality whale traders** on Polymarket with proven track records. You've implemented 5 basic copy-trading strategies (Top 5, High Sharpe, Diversified, Conservative, Aggressive). Now you need to discover new, innovative strategies that can generate alpha beyond simple whale copying.

## Your Mission

Research and discover novel trading strategies that:
1. Leverage whale behavior patterns and signals
2. Combine multiple data sources and signals
3. Identify market inefficiencies and edge opportunities
4. Adapt to changing market conditions
5. Outperform simple whale copying (target: Sharpe >2.5)

---

## Research Questions

### 1. Whale Behavior Pattern Strategies

**Research strategies based on whale trading patterns:**

a) **Consensus vs. Contrarian**
   - **Consensus Strategy**: Copy only when ≥3 whales agree on same outcome
     - Hypothesis: Multiple expert opinions = higher confidence
     - Risk: Delayed entry, worse prices
     - Test: Does consensus improve win rate by >10%?

   - **Contrarian Strategy**: Fade whale consensus (take opposite side)
     - Hypothesis: Whale herding creates overvalued outcomes
     - Entry: When 80%+ of whale money on one side
     - Exit: When consensus weakens or market corrects
     - Test: Are there contrarian opportunities in extreme whale positioning?

b) **Whale Copy Timing**
   - **Fast Follow** (within 5 minutes of whale trade)
     - Pros: Best prices, early entry
     - Cons: Might be catching falling knife, less conviction

   - **Delayed Follow** (wait 1-4 hours after whale trade)
     - Pros: Price confirmation, avoid false signals
     - Cons: Worse prices, missed opportunities
     - Test: Optimal delay time for best risk-adjusted returns?

   - **Smart Entry** (wait for price retracement after whale trade)
     - Entry: Whale buys YES at 65%, we wait for dip to 62%
     - Hypothesis: Whale impact moves price, creates entry opportunity
     - Test: Does waiting for 3-5% retracement improve returns?

c) **Whale Specialization**
   - **Politics Specialist Strategy**: Copy only whales with >80% politics trades
   - **Sports Specialist Strategy**: Copy only sports-focused whales
   - **Generalist Diversified**: Prefer whales who trade all categories
   - Test: Do specialists outperform generalists in their domain?

d) **Whale Confidence Signals**
   - **Large Position Strategy**: Copy only when whale trades 2x+ their average size
     - Hypothesis: Outsized position = high conviction
     - Test: Do whale "conviction trades" have higher win rate?

   - **Repeated Position**: Copy when whale adds to existing position
     - Hypothesis: Doubling down = strong belief
     - Test: Are follow-on trades more profitable?

   - **Rapid Entry**: Copy when whale enters within 24h of market creation
     - Hypothesis: Early entry = information edge
     - Test: Are early whale trades more profitable?

**Deliverable:**
- 5 whale behavior strategies with hypotheses
- Backtestable strategy specifications
- Expected Sharpe ratio and win rate

---

### 2. Market Microstructure Strategies

**Research strategies based on market characteristics:**

a) **Liquidity Arbitrage**
   - **Low Liquidity Sniping**: Target markets with <$50K volume where whale trades can move price
     - Entry: Whale buys YES, we buy YES before market absorbs order
     - Exit: Quick flip (15-30 min) or hold to resolution
     - Risk: Illiquid exit, slippage
     - Test: Can we profit from whale-induced price impact?

   - **Liquidity Recovery**: Fade whale impact, bet on mean reversion
     - Entry: Whale buys YES at 65% (was 60%), we sell YES at 65%
     - Exit: Price reverts to 61-62%
     - Test: Does temporary price impact reverse predictably?

b) **Spread Exploitation**
   - **Wide Spread Opportunity**: Only copy when spread <3% (tight market)
     - Hypothesis: Tight spread = efficient pricing, better execution
     - Avoid: Markets with >5% spread (inefficient, costly)
     - Test: Does spread width predict profitability?

   - **Bid-Ask Balance**: Monitor order book depth
     - Entry: If whale buys YES, check YES bid depth vs. NO bid depth
     - Hypothesis: Deep bid support = sustained price move
     - Test: Does order book depth predict price stability?

c) **Market Age Dynamics**
   - **New Market Strategy**: Copy only in first 7 days (information edge period)
     - Hypothesis: Early markets have more mispricing
     - Test: Are new market returns higher than mature markets?

   - **Mature Market Strategy**: Copy only in markets >30 days old (stability)
     - Hypothesis: Mature markets have validated liquidity
     - Test: Are mature market trades safer (lower volatility)?

   - **Pre-Resolution Strategy**: Trade only markets resolving in <7 days
     - Hypothesis: Short-duration = predictable, less risk
     - Test: Are short-dated markets more profitable?

**Deliverable:**
- 3 market microstructure strategies
- Entry/exit rules and risk parameters
- Expected return profile and Sharpe

---

### 3. Multi-Signal Combination Strategies

**Research strategies combining multiple signals:**

a) **Whale + Sentiment Strategy**
   - Combine whale trades with social sentiment (Twitter, Discord)
   - Entry: Whale buys YES + positive sentiment spike
   - Hypothesis: Whale trades backed by crowd sentiment are stronger
   - Data sources: Twitter API, Polymarket Discord, Reddit
   - Test: Does sentiment confirmation improve win rate by >15%?

b) **Whale + Volume Strategy**
   - Combine whale trade with volume spike detection
   - Entry: Whale buys YES + 24h volume >3x average
   - Hypothesis: Volume confirms conviction, reduces false signals
   - Test: Does volume filter improve Sharpe by >0.3?

c) **Whale + Price Momentum**
   - Combine whale trade with price momentum indicators
   - Entry: Whale buys YES + price up 5% in last 24h
   - Hypothesis: Momentum + whale trade = trend confirmation
   - Test: Does momentum filter catch winning trends?

d) **Multi-Whale Consensus + Market Quality**
   - Entry criteria:
     - ≥2 whales agree on same outcome
     - Market has >$100K volume (liquid)
     - Spread <3% (efficient)
     - Market age 7-30 days (sweet spot)
   - Hypothesis: Multiple filters create high-quality signal
   - Test: Does combined filter achieve Sharpe >3.0?

**Deliverable:**
- 4 multi-signal strategies
- Signal combination logic (AND, OR, weighted scoring)
- Expected performance vs. single-signal strategies

---

### 4. Dynamic Portfolio Strategies

**Research adaptive portfolio management:**

a) **Risk Parity Across Categories**
   - Allocate capital equally to Politics, Sports, Crypto, Tech, etc.
   - Rebalance weekly to maintain equal risk contribution
   - Hypothesis: Diversification reduces drawdowns
   - Test: Compare to concentrated strategies

b) **Volatility-Adjusted Sizing**
   - Reduce position size in high-volatility markets
   - Increase position size in stable markets
   - Volatility metric: 7-day price standard deviation
   - Test: Does volatility adjustment improve risk-adjusted returns?

c) **Drawdown-Responsive Allocation**
   - If portfolio down -5%, reduce all positions by 50%
   - If portfolio down -10%, stop trading (circuit breaker)
   - If portfolio up +10%, increase position sizes by 25%
   - Hypothesis: Adaptive sizing preserves capital in downturns
   - Test: Does dynamic sizing reduce max drawdown?

d) **Whale Performance Weighting**
   - Dynamically adjust whale allocations based on recent performance
   - Hot hand: Whale with 5 consecutive wins → increase allocation by 50%
   - Cold hand: Whale with 3 consecutive losses → reduce by 50%
   - Test: Does performance-based weighting improve returns?

**Deliverable:**
- 4 dynamic portfolio strategies
- Rebalancing rules and triggers
- Simulation results vs. static allocation

---

### 5. Exotic Strategy Concepts

**Research unconventional approaches:**

a) **Anti-Whale Strategy**
   - Identify losing whales (win rate <50%, negative P&L)
   - Take opposite side of their trades
   - Hypothesis: Bad traders are consistently bad, profitable to fade
   - Test: Are there persistently unprofitable traders to exploit?

b) **Whale Rotation Strategy**
   - Track 30-day rolling performance of all 41 whales
   - Copy only top 10 whales by recent performance
   - Rotate monthly (drop worst, add best)
   - Hypothesis: Recent performance predicts near-term edge
   - Test: Does momentum-based rotation beat buy-and-hold?

c) **Market Maker Strategy**
   - Provide liquidity: Buy at 48%, Sell at 52% (earn spread)
   - Exit when whale enters (price likely to move)
   - Hypothesis: Earn consistent spread, avoid directional risk
   - Test: Can we profit from bid-ask spread while avoiding whale impact?

d) **News Event Strategy**
   - Monitor news APIs for breaking events
   - If major news breaks, check if whales are trading
   - Entry: Whale trades within 30 min of news → follow
   - Hypothesis: Whales react quickly to news, we can piggyback
   - Test: Are news-triggered whale trades more profitable?

e) **Arbitrage Strategy**
   - Identify related markets (e.g., "Trump wins" vs. "Republican wins")
   - If whale trades one side, check for arbitrage in related market
   - Entry: Price discrepancy >5% between related outcomes
   - Hypothesis: Market inefficiencies exist across related markets
   - Test: Can we exploit cross-market arbitrage?

**Deliverable:**
- 5 exotic strategy concepts
- Feasibility assessment
- Data requirements and API dependencies

---

### 6. Machine Learning Strategies

**Research ML-powered approaches:**

a) **Whale Trade Classification**
   - Train model to predict: Will whale trade be profitable?
   - Features: Whale stats, market features, timing, size
   - Model: Random Forest, XGBoost, Neural Network
   - Output: Probability of profitable trade (0-100%)
   - Entry: Copy only if model predicts >70% profit probability
   - Test: Does ML filter beat rule-based filters?

b) **Price Prediction Model**
   - Train model to predict: Price 1 hour after whale trade
   - Features: Whale entry price, volume, spread, order book
   - Model: LSTM, Transformer, Gradient Boosting
   - Entry: If predicted price >5% above entry, copy trade
   - Test: Can we predict short-term price moves?

c) **Optimal Position Sizing Model**
   - Train model to predict: Optimal position size per trade
   - Features: Whale quality, market liquidity, portfolio state
   - Model: Reinforcement Learning (Q-Learning, PPO)
   - Output: Position size as % of capital
   - Test: Does RL-based sizing beat Kelly criterion?

d) **Market Regime Detection**
   - Cluster historical periods into regimes (bull, bear, choppy)
   - Use different strategies for different regimes
   - Features: Market volatility, volume, whale activity
   - Model: Hidden Markov Model, K-Means clustering
   - Test: Does regime-aware trading improve consistency?

**Deliverable:**
- 4 ML strategy architectures
- Feature engineering plans
- Training data requirements (size, period)
- Expected performance vs. rule-based strategies

---

### 7. Risk-Adjusted Strategy Design

**Research strategies optimized for specific risk profiles:**

a) **Low Volatility Strategy**
   - Target: Sharpe >2.0, Max Drawdown <10%
   - Approach: Copy only safest whale trades
     - Whale tier: MEGA only (WQS >90)
     - Win rate: >70%
     - Market: Mature (>30 days), liquid (>$100K)
     - Position: Small (2-3% of capital)
   - Test: Can we achieve consistent 15-20% annual returns?

b) **High Growth Strategy**
   - Target: Annual returns >50%, accept drawdowns <30%
   - Approach: Aggressive whale copying
     - Whale tier: Any (but prefer high Sharpe)
     - Market: New (<7 days), any liquidity
     - Position: Large (7-12% of capital)
     - Leverage: Consider using 1.5x leverage (borrow)
   - Test: Can we achieve 50%+ returns with acceptable risk?

c) **Market Neutral Strategy**
   - Target: Zero correlation to overall market direction
   - Approach: Long-short pairs
     - Long: Whale buys YES in Market A
     - Short: Sell YES in negatively correlated Market B
     - Hedge: Maintain delta-neutral portfolio
   - Test: Can we profit regardless of market direction?

d) **Income Strategy**
   - Target: Consistent weekly profits, low volatility
   - Approach: High-frequency, small position trading
     - Copy all qualified whale trades >$500
     - Position: Tiny (1-2% of capital)
     - Exit: Quick flips (1-4 hours) or hold to resolution
     - Goal: 70%+ win rate, small losses
   - Test: Can we generate steady income stream?

**Deliverable:**
- 4 risk-optimized strategies
- Performance targets and constraints
- Expected return distributions
- Suitability for different investor profiles

---

### 8. Strategy Validation Framework

**Research how to validate new strategies:**

a) **Backtesting Requirements**
   - Historical data: Minimum 12 months
   - Walk-forward validation: 6-month in-sample, 3-month out-sample, roll forward
   - Monte Carlo simulation: 1,000 trials with bootstrapped returns
   - Stress testing: Test on worst historical periods

b) **Performance Metrics**
   - Sharpe Ratio: Target ≥2.5
   - Calmar Ratio: Target ≥2.0
   - Win Rate: Target ≥60%
   - Max Drawdown: Target ≤15%
   - Profit Factor: Target ≥2.0
   - Average Win / Average Loss: Target ≥2.0

c) **Robustness Tests**
   - Parameter sensitivity: Change parameters ±20%, expect <10% performance change
   - Data snooping: Test on unseen data (future data after backtest)
   - Transaction costs: Include 2-5% slippage, 0.5% fees
   - Latency: Assume 10-60 second execution delay

d) **Live Paper Trading**
   - Run strategy for 30 days with virtual capital
   - Compare live performance to backtest
   - Accept: If live Sharpe within 20% of backtest Sharpe
   - Reject: If live drawdown >2x backtest drawdown

**Deliverable:**
- Strategy validation checklist
- Acceptance criteria
- Rejection criteria (when to abandon strategy)

---

### 9. Strategy Portfolio Construction

**Research how to combine strategies:**

a) **Diversification Benefits**
   - How many strategies needed for diversification? (5? 10? 20?)
   - Correlation between strategies: Target <0.3
   - Allocate capital: Equal weight vs. risk parity vs. Sharpe-weighted?

b) **Strategy Allocation**
   ```
   Portfolio Allocation:
   - 30%: Conservative (Low Vol)
   - 30%: Core (Top 5 Whales)
   - 20%: Growth (High Sharpe)
   - 10%: Momentum (Hot Hand Rotation)
   - 10%: Experimental (New Strategies)
   ```
   - Is this allocation optimal?
   - How often to rebalance? (Daily, weekly, monthly?)

c) **Strategy Lifecycle Management**
   - When to add new strategy to portfolio?
   - When to remove underperforming strategy?
   - How to scale up successful strategies?

**Deliverable:**
- Optimal strategy portfolio composition
- Allocation weights with rationale
- Rebalancing rules
- Strategy lifecycle policy

---

### 10. Implementation Priorities

**Research what to build first:**

**Phase 1: Quick Wins (Week 1-2)**
- Implement top 3 whale behavior strategies
- Backtest on 12 months historical data
- Deploy to paper trading

**Phase 2: Multi-Signal (Week 3-4)**
- Build 2 multi-signal strategies
- Integrate external data sources (sentiment, volume)
- Validate with walk-forward testing

**Phase 3: Dynamic Portfolio (Week 5-6)**
- Implement risk parity allocation
- Add drawdown-responsive sizing
- Test portfolio-level risk controls

**Phase 4: ML Experimentation (Week 7-8)**
- Collect training data
- Build simple ML classifier
- Compare to rule-based strategies

**Phase 5: Optimization (Week 9-10)**
- Optimize top 5 performing strategies
- Combine strategies into portfolio
- Prepare for live trading

---

## Research Deliverables

Please provide:

1. **Top 10 Strategy Candidates**
   - Strategy name, description, hypothesis
   - Expected Sharpe ratio and max drawdown
   - Implementation complexity (1-5)
   - Priority ranking (P0, P1, P2)

2. **Detailed Strategy Specifications** (Top 5)
   - Complete entry/exit rules
   - Position sizing formula
   - Risk parameters
   - Backtest results

3. **Strategy Comparison Matrix**
   - Compare all strategies on key metrics
   - Correlation matrix between strategies
   - Recommended portfolio allocation

4. **Implementation Roadmap**
   - Week-by-week build plan
   - Data requirements and API dependencies
   - Testing and validation checkpoints

5. **Strategy Validation Framework**
   - Backtesting methodology
   - Performance acceptance criteria
   - Live testing protocol

---

## Output Format

Structure your response as:

### Executive Summary
(Top 3 strategy recommendations with expected performance)

### Strategy Catalog
(Detailed descriptions of 10+ strategies)

### Strategy Specifications
(Complete specifications for top 5 strategies)

### Performance Projections
(Backtested Sharpe, drawdown, win rate for each strategy)

### Strategy Portfolio
(Recommended portfolio allocation across strategies)

### Implementation Plan
(10-week roadmap with priorities and milestones)

### Risk Analysis
(Failure modes, risk mitigation, worst-case scenarios)

### Code Pseudocode
(Python implementation sketches for key strategies)
