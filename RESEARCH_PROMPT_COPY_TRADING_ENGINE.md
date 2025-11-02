# Deep Research Prompt: Whale Copy-Trading Engine Configuration & Position Sizing

## Context

You are building a production-grade whale copy-trading engine for Polymarket prediction markets. You have already identified and qualified 41 high-performing whale traders through rigorous analysis. These whales have:
- Enhanced Whale Quality Score (WQS) ≥ 70
- Total trades ≥ 20
- Total volume ≥ $10,000
- Win rate ≥ 52%
- Sharpe ratio ≥ 0.8

The whales have been ranked and scored using a 5-factor Enhanced WQS model that considers:
- Sharpe Ratio (30% weight)
- Information Ratio (25% weight)
- Calmar Ratio (20% weight)
- Win Rate (15% weight)
- Consistency Score (10% weight)

## Your Mission

Design a comprehensive copy-trading engine configuration that determines:
1. How much capital to allocate per whale trade
2. How to dynamically adjust position sizes based on whale quality and market conditions
3. Risk management parameters and position limits
4. Trade filtering and signal validation rules
5. Portfolio-level risk controls

## Current System Architecture

**Database Schema:**
- 41 qualified whales with complete metrics (Sharpe, win rate, volume, P&L, etc.)
- Historical trades for each whale (timestamp, side, outcome, amount, price)
- Real-time 24h metrics updated every 15 minutes

**Available Metrics Per Whale:**
- `quality_score` (Enhanced WQS 0-100)
- `sharpe_ratio` (risk-adjusted returns)
- `win_rate` (percentage of profitable trades)
- `total_pnl` (cumulative profit/loss)
- `total_volume` (lifetime trading volume)
- `total_trades` (number of trades executed)
- `avg_position_size` (average trade size)
- `max_drawdown` (largest peak-to-trough decline)
- `tier` (MEGA, HIGH, MEDIUM - based on quality)

**Current Strategy Framework:**
- 5 paper trading strategies already implemented
- Each strategy can have different position sizing rules
- Trades are copied when whale matches strategy criteria

## Research Questions

### 1. Position Sizing Algorithm

**Research the optimal position sizing formula that considers:**

a) **Whale Quality Factor**
   - How should quality_score (70-100) translate to position size multiplier?
   - Should Sharpe ratio override quality_score for highly risk-adjusted whales?
   - How to weight consistency vs. absolute performance?

b) **Trade Size Relative to Whale's Average**
   - If whale usually trades $1,000 and this trade is $5,000, is it a high-conviction signal?
   - Should we scale our position proportionally (5x our base size)?
   - What's the cap on position size ratio (2x? 3x? Dynamic based on whale tier)?

c) **Account Balance Percentage**
   - What % of total capital should be the base position size? (Current: 5%)
   - Should this vary by whale tier? (MEGA: 7%, HIGH: 5%, MEDIUM: 3%)
   - How to prevent over-concentration in single positions?

d) **Kelly Criterion Application**
   - Given whale's win_rate and average profit ratio, what's the optimal Kelly fraction?
   - Should we use full Kelly, half Kelly, or quarter Kelly?
   - How to adjust Kelly for prediction markets with bounded outcomes?

**Proposed Formula to Validate:**
```
position_size = base_capital * base_pct * quality_factor * trade_size_ratio * kelly_fraction
```

Where:
- `base_capital` = current account balance
- `base_pct` = strategy's base position size (3-7%)
- `quality_factor` = (whale.quality_score / 100) ^ 0.5  (dampened to avoid extremes)
- `trade_size_ratio` = min(whale_trade_amount / whale_avg_trade, max_ratio_cap)
- `kelly_fraction` = 0.25 * whale.win_rate (quarter Kelly, conservative)

**Questions:**
- Is this formula sound for prediction markets?
- Should we add a volatility adjustment factor?
- How to handle whales with limited trade history?

---

### 2. Dynamic Risk Adjustments

**Research how to dynamically adjust position sizing based on:**

a) **Recent Whale Performance**
   - If whale's last 10 trades had 80% win rate vs. lifetime 60%, increase allocation?
   - If whale has 3 consecutive losses, reduce allocation temporarily?
   - How to implement performance decay detection (CUSUM, moving averages)?

b) **Market Volatility**
   - During high volatility periods (measured how?), reduce all positions by X%?
   - Should we track prediction market-wide volatility or per-market?
   - How to measure volatility in binary outcome markets?

c) **Correlation Between Whales**
   - If multiple whales take same position, is this confirmation or risk concentration?
   - Should we reduce position size if ≥3 whales are on same side of same market?
   - How to detect and handle correlated whale behavior?

d) **Time-Based Adjustments**
   - Do prediction markets behave differently near resolution time?
   - Should we reduce position sizes for markets resolving in <24h?
   - Are there optimal times of day/week for copying trades?

---

### 3. Trade Filtering & Signal Quality

**Research criteria for rejecting whale trades even if whale is qualified:**

a) **Market Quality Filters**
   - Minimum liquidity threshold for market (e.g., ≥$10K volume)?
   - Maximum bid-ask spread (e.g., ≤5%)?
   - Avoid markets with <100 traders to prevent manipulation?

b) **Whale Behavior Filters**
   - Reject trades where whale is taking <1% of their average position?
   - Reject if whale's recent win rate dropped >20% from baseline?
   - Flag if whale suddenly trades 10x their normal size (potential error/manipulation)?

c) **Portfolio-Level Filters**
   - Max number of concurrent open positions (e.g., 20)?
   - Max exposure to single market (e.g., 15% of portfolio)?
   - Max exposure to single category (e.g., Politics: 30%, Sports: 40%)?

d) **Timing Filters**
   - Avoid copying trades in first 1 hour after market creation?
   - Avoid copying trades in last 6 hours before market resolution?
   - Wait for N minutes after whale trade to check for price stability?

---

### 4. Risk Management Parameters

**Research optimal risk limits:**

a) **Position-Level Limits**
   - Max position size as % of portfolio: 10%? 15%?
   - Should this vary by market liquidity?
   - Hard stop-loss per position: -20%? -30%?

b) **Portfolio-Level Limits**
   - Max daily loss before circuit breaker halts trading: -5%? -10%?
   - Max weekly loss tolerance?
   - Max drawdown from peak equity before reducing position sizes?

c) **Whale-Level Limits**
   - Max allocation to single whale across all positions: 25%? 30%?
   - Auto-quarantine whale after N consecutive losses (N = 5? 7?)?
   - Re-qualification period after quarantine: 14 days? 30 days?

d) **Concentration Limits**
   - Max positions in same category: 40%?
   - Max correlated positions (same outcome, different markets): 20%?
   - Diversification requirements: min number of whales (3?) and markets (5?)?

---

### 5. Whale-Specific Position Sizing Rules

**Research how to differentiate position sizing by whale characteristics:**

a) **By Whale Tier**
   ```
   MEGA (WQS ≥ 90, Sharpe ≥ 3.0):
     - Base position: 7% of capital
     - Max position: 12% of capital
     - Kelly fraction: 0.30 (more aggressive)

   HIGH (WQS 80-90, Sharpe ≥ 2.0):
     - Base position: 5% of capital
     - Max position: 10% of capital
     - Kelly fraction: 0.25

   MEDIUM (WQS 70-80, Sharpe ≥ 1.5):
     - Base position: 3% of capital
     - Max position: 6% of capital
     - Kelly fraction: 0.20 (more conservative)
   ```
   - Are these tiers and allocations appropriate?
   - Should tiers be dynamic based on rolling performance?

b) **By Trading Style**
   - High frequency whales (>100 trades): smaller positions, faster turnover?
   - Patient whales (<50 trades, high win rate): larger positions, longer hold?
   - How to classify whale trading styles automatically?

c) **By Specialization**
   - Whales who specialize in Politics (80%+ trades): increase position size for politics markets?
   - Generalist whales: standard position sizing?
   - How to detect and leverage whale specialization?

---

### 6. Edge Decay Detection & Adaptation

**Research how to detect when a whale's edge is diminishing:**

a) **Statistical Tests**
   - CUSUM (Cumulative Sum) control chart for win rate?
   - Rolling Sharpe ratio with 30-day window?
   - Chi-square test for distribution changes?

b) **Trigger Conditions**
   - Win rate drops >15% from lifetime average for >20 trades?
   - Sharpe ratio drops below 1.0 for >30 days?
   - 3 consecutive months of negative P&L?

c) **Response Actions**
   - Reduce position size by 50% for 14 days (probation)?
   - Disable copying entirely (quarantine)?
   - Require re-qualification through new backtest?

d) **Whale Recovery**
   - How to detect when a quarantined whale regains edge?
   - Gradual position size ramp-up (25% → 50% → 75% → 100%)?
   - Minimum performance period before full reinstatement?

---

### 7. Market-Specific Adjustments

**Research how market characteristics should affect position sizing:**

a) **By Market Liquidity**
   ```
   High Liquidity (>$100K volume):
     - Standard position sizing
     - Faster execution, lower slippage

   Medium Liquidity ($10K-$100K):
     - Reduce position size by 25%
     - Higher slippage risk

   Low Liquidity (<$10K):
     - Reduce position size by 50% OR skip trade
     - Manipulation risk
   ```

b) **By Market Age**
   - New markets (<7 days old): reduce position by 30%?
   - Mature markets (>30 days): standard sizing?
   - Markets near resolution (<48h): reduce by 50% (lower edge)?

c) **By Outcome Probability**
   - Extreme probabilities (>90% or <10%): smaller positions?
   - Balanced markets (40-60%): standard positions?
   - How to avoid value traps in extreme probability markets?

---

### 8. Backtesting Validation

**Research what metrics to validate position sizing against:**

a) **Target Performance Metrics**
   - Sharpe ratio: ≥2.0 (from research paper target: 2.07)
   - Max drawdown: ≤15% (research paper: 11.2%)
   - Win rate: ≥55%
   - Monthly positive return rate: ≥70%

b) **Risk Metrics to Monitor**
   - Value at Risk (VaR) at 95% confidence
   - Conditional VaR (expected loss in worst 5% of outcomes)
   - Maximum consecutive losses
   - Time to recovery from drawdowns

c) **Validation Approach**
   - Walk-forward backtest with 24-month historical data
   - 12-month in-sample, 3-month out-of-sample, rolling
   - Monte Carlo simulation with 1,000 trials
   - Stress testing with worst historical periods

---

### 9. Implementation Priorities

**Research what to build first:**

a) **Phase 1: Core Position Sizing (Week 1)**
   - Implement basic formula with quality_factor and trade_size_ratio
   - Add position limits (max % per trade)
   - Test on 10 whales, $10K virtual capital

b) **Phase 2: Risk Management (Week 2)**
   - Add circuit breakers (daily loss limits)
   - Implement whale-level allocation caps
   - Add portfolio diversification rules

c) **Phase 3: Dynamic Adjustments (Week 3)**
   - Add recent performance tracking
   - Implement edge decay detection
   - Dynamic Kelly fraction adjustment

d) **Phase 4: Market Filters (Week 4)**
   - Liquidity and spread filters
   - Timing-based filters
   - Correlation detection

---

## Research Deliverables

Please provide:

1. **Recommended Position Sizing Formula**
   - Complete mathematical formula with all parameters
   - Justification for each component
   - Example calculations for MEGA, HIGH, MEDIUM tier whales

2. **Risk Parameter Configuration**
   - Exact numerical limits for all risk controls
   - Tiered parameters by whale quality
   - Justification based on prediction market research

3. **Trade Filtering Rules**
   - Prioritized list of filters (must-have vs. nice-to-have)
   - Implementation complexity estimate
   - Expected impact on strategy performance

4. **Edge Decay Detection System**
   - Statistical method recommendation
   - Trigger thresholds with confidence intervals
   - Response action decision tree

5. **Backtesting Strategy**
   - Validation metrics and target values
   - Walk-forward test design
   - Success criteria for production deployment

6. **Implementation Roadmap**
   - Week-by-week build plan
   - Dependencies between components
   - Testing checkpoints

---

## Key Constraints

- **Prediction Market Specific**: Binary outcomes, bounded probabilities (0-100%)
- **Capital Constraints**: Starting with $10K-$100K virtual capital per strategy
- **Execution Limitations**: Cannot execute trades <$10 or >$5,000 initially
- **Data Availability**: 24h metrics updated every 15 minutes, not real-time tick data
- **Whale Sample Size**: 41 qualified whales (not thousands, so avoid overfitting)

---

## Research References

Include in your research:
- Kelly Criterion applications in prediction markets
- Position sizing in portfolio management (Tharp, Jones, etc.)
- Risk parity and risk budgeting approaches
- Statistical process control (CUSUM, EWMA) for trader monitoring
- Market microstructure of prediction markets (liquidity, spreads)
- The "Copy-Trading the Top 0.5%" research paper findings (Sharpe 2.07, 11.2% drawdown targets)

---

## Output Format

Structure your response as:

### Executive Summary
(Key recommendations in 3-5 bullets)

### Position Sizing Formula
(Complete formula with parameter definitions)

### Risk Management Configuration
(Table of all limits and thresholds)

### Trade Filtering Rules
(Prioritized checklist)

### Edge Decay System
(Statistical method + decision tree)

### Backtesting Plan
(Validation approach + success criteria)

### Implementation Roadmap
(4-week build plan)

### Code Snippets
(Python pseudocode for key algorithms)
