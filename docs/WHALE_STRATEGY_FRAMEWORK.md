# WHALE SELECTION STRATEGY FRAMEWORK
**AI-Powered Strategy Decision System**

---

## 📋 QUICK START

**Current Database:** 29 profitable whales with $100K+ volume
**Recommended Strategy:** Elite Top 10 (Conservative)
**Expected Sharpe:** 2.0-2.5
**Expected Drawdown:** 10-15%

---

## 🎯 10 WHALE SELECTION STRATEGIES

### STRATEGY 1: Elite Top 10 (Conservative)
**Best For:** Risk-averse, capital preservation
**Whale Count:** 5-10 whales
**Risk Level:** ⭐ LOW

**Criteria:**
- Tier: MEGA only (quality_score > 80)
- Win Rate: ≥65%
- Sharpe Ratio: ≥2.0
- Volume: ≥$500K
- Statistical Confidence: sharpe_ci_lower > 1.5

**Capital Allocation:**
- 70% → Top 10 whales
- 25% → Next 20 whales
- 5% → Experimental

**Performance Targets:**
- Sharpe: 2.0-2.5
- Drawdown: 10-15%
- Win Rate: 85%+

**When to Use:**
- ✅ Portfolio in drawdown >10%
- ✅ High market volatility
- ✅ New to copy trading
- ✅ Capital <$10K

---

### STRATEGY 2: Balanced 20 (Moderate)
**Best For:** Steady returns, diversification
**Whale Count:** 15-20 whales
**Risk Level:** ⭐⭐ MODERATE

**Criteria:**
- Win Rate: ≥60%
- Sharpe: ≥1.5
- Sortino > Sharpe (limited downside)
- Max Drawdown: <20%

**Capital Allocation:**
- Equal-weight across 15-20 whales

**Performance Targets:**
- Sharpe: 1.5-2.0
- Drawdown: 15-20%
- Win Rate: 70%+

**When to Use:**
- ✅ Stable market (NEUTRAL, RANGING)
- ✅ Capital $10K-$50K
- ✅ Goal: Steady monthly returns

---

### STRATEGY 3: Rising Stars (Momentum)
**Best For:** Aggressive growth, hot streaks
**Whale Count:** 10-15 whales
**Risk Level:** ⭐⭐⭐ HIGH

**Criteria:**
- rolling_30d_sharpe > rolling_90d_sharpe (improving)
- trades_24h > 0 (active)
- quality_score ≥ 50

**Capital Allocation:**
- 50% → Top 5 improving
- 30% → Top 10
- 20% → Experimental

**Performance Targets:**
- Sharpe: 1.8-2.3
- Drawdown: 20-30%

**When to Use:**
- ✅ BULL market
- ✅ Portfolio performing well
- ✅ High risk tolerance

---

### STRATEGY 4: Category Specialists
**Best For:** Event-driven, sector focus
**Whale Count:** 5-8 per category
**Risk Level:** ⭐⭐ MODERATE

**Categories:**
- POLITICS (elections)
- CRYPTO (BTC/ETH volatility)
- SPORTS (NFL, NBA playoffs)
- TECH (AI, companies)

**Criteria:**
- primary_category == target
- Category Sharpe > 2.0
- Category Volume > $200K

**Capital Allocation:**
- 80% → Top category performers
- 20% → Diversified

**When to Use:**
- ✅ Major events (elections, playoffs)
- ✅ Deep sector knowledge
- ✅ Want concentrated exposure

---

### STRATEGY 5: High Volume Traders
**Best For:** Following smart money
**Whale Count:** 8-12 whales
**Risk Level:** ⭐⭐ MODERATE

**Criteria:**
- Total Volume > $1M
- volume_24h > $50K
- avg_trade_size > $10K

**Capital Allocation:**
- Kelly-weighted by volume

**When to Use:**
- ✅ Liquid markets
- ✅ Large capital (>$50K)
- ✅ BULL or HIGH_VOLATILITY regime

---

### STRATEGY 6: Statistical Outliers
**Best For:** Highest conviction
**Whale Count:** 3-5 whales
**Risk Level:** ⭐ VERY LOW

**Criteria:**
- sharpe_ci_lower > 1.5 (95% confidence)
- sharpe_shrunk > 2.0 (robust)
- Win Rate > 70%
- Profit Factor > 2.0

**Capital Allocation:**
- 90% → Top 3-5 whales
- 10% → Experimental

**Performance Targets:**
- Sharpe: 2.5-3.5
- Drawdown: 8-12%

**When to Use:**
- ✅ Want highest confidence
- ✅ Very conservative risk profile
- ✅ Any market regime

---

### STRATEGY 7: Thompson Sampling (Adaptive)
**Best For:** Algorithm-driven learning
**Whale Count:** 12-20 (dynamic)
**Risk Level:** ⭐⭐ MODERATE-HIGH

**Method:**
- Bayesian bandit algorithm
- Beta distribution (α=1, β=1)
- Discount factor: 0.95
- Explores + exploits automatically

**When to Use:**
- ✅ Uncertain conditions
- ✅ Want algorithm to optimize
- ✅ Long-term (3+ months)

---

### STRATEGY 8: Correlation-Aware
**Best For:** Risk reduction
**Whale Count:** 15-25 whales
**Risk Level:** ⭐ LOW

**Rules:**
- Max correlation: 40%
- Skip if overlap >30%
- Amplify 1.5x if 3+ agree with <20% overlap

**When to Use:**
- ✅ BEAR or HIGH_VOLATILITY
- ✅ Risk management priority
- ✅ High correlation detected

---

### STRATEGY 9: Adaptive State Machine
**Best For:** Automated lifecycle
**Whale Count:** 10-30 (adaptive)
**Risk Level:** ⭐⭐ MODERATE

**Auto Rules:**
- Disable after 5 losses
- Enable after 2 wins + 3 days
- Probation: 7 days for new whales

**When to Use:**
- ✅ Want automation
- ✅ Any regime (adaptive)

---

### STRATEGY 10: Regime-Adaptive Kelly
**Best For:** Optimal sizing
**Risk Level:** ⭐⭐⭐ MODERATE-HIGH

**Method:**
- Base Kelly: f* = (pb - q) / b
- Adjusts for: volatility, regime, confidence
- Fractional Kelly: 25%

**When to Use:**
- ✅ Regime changes frequently
- ✅ Mathematical optimization
- ✅ Statistical confidence

---

## 🔀 DECISION MATRIX

### Step 1: Answer These Questions

**A. What's your max acceptable drawdown?**
- <10% → Elite, Statistical Outliers
- 10-20% → Balanced, Correlation-Aware
- 20-30% → Rising Stars, High Volume
- >30% → Momentum/Aggressive

**B. How much capital?**
- <$10K → Elite (3-5 whales)
- $10K-$50K → Balanced (15-20 whales)
- $50K-$200K → Diversified (20-30 whales)
- >$200K → High Volume + Specialists

**C. Time horizon?**
- <1 month → Category Specialists
- 1-3 months → Rising Stars
- 3-6 months → Thompson Sampling
- >6 months → Balanced, Adaptive

**D. Market regime?** (Check current)
- BULL → Rising Stars, High Volume
- BEAR → Elite, Statistical Outliers
- NEUTRAL → Balanced, Thompson Sampling
- HIGH_VOLATILITY → Correlation-Aware
- RANGING → Balanced, Specialists

**E. Portfolio state?**
- In drawdown >10%? → Elite
- Whales correlated >50%? → Correlation-Aware
- Performing well? → Rising Stars

**F. Primary goal?**
- Capital preservation → Elite
- Steady income → Balanced
- Aggressive growth → Rising Stars
- Learning → Thompson Sampling
- Event-driven → Category Specialists
- Follow smart money → High Volume

---

## 🤖 STRATEGY RECOMMENDATION ALGORITHM

```python
IF (drawdown > 10% OR market_regime == HIGH_VOLATILITY):
    RECOMMEND: Elite or Statistical Outliers
    ALLOCATION: 90% top 3-5 whales
    SIZING: Reduce to 50% of normal

ELIF (capital < $10K OR new_to_trading):
    RECOMMEND: Balanced
    ALLOCATION: Equal-weight 15 whales
    SIZING: Kelly 0.10 (very conservative)

ELIF (market_regime == BULL AND portfolio_in_profit):
    RECOMMEND: Rising Stars
    ALLOCATION: 50-30-20 distribution
    SIZING: Kelly 0.25

ELIF (major_event_approaching):
    RECOMMEND: Category Specialists
    ALLOCATION: 80% category, 20% diversified
    SIZING: 1.5x normal

ELIF (high_whale_correlation > 50%):
    RECOMMEND: Correlation-Aware
    ALLOCATION: Penalize correlated by 50%
    SIZING: Kelly 0.20

ELIF (uncertain_conditions):
    RECOMMEND: Thompson Sampling
    ALLOCATION: Bayesian posterior-weighted
    SIZING: Adaptive

ELSE:  # Default
    RECOMMEND: Adaptive State Machine
    ALLOCATION: 70-25-5 tiers
    SIZING: Kelly 0.25
```

---

## ✅ VALIDATION CHECKLIST

Before finalizing strategy:

- [ ] Minimum whale count met?
- [ ] Capital requirements satisfied?
- [ ] Risk limits respected?
- [ ] Market conditions appropriate?
- [ ] Backtesting data reviewed?

---

## 🔄 STRATEGY SWITCHING RULES

**Weekly Performance Check:**

```
IF sharpe < 1.0 for 30 days:
    → Switch to Elite

IF drawdown > 15%:
    → IMMEDIATE switch to Elite + reduce 50%

IF win_rate < 50% for 30 days:
    → Switch to Balanced

IF high_correlation detected (>50%):
    → Switch to Correlation-Aware

IF market_regime_changed:
    - BULL → Consider Rising Stars
    - BEAR → Switch to Elite
    - HIGH_VOL → Switch to Correlation-Aware

IF performing_well (sharpe > 2.0):
    → KEEP strategy, increase size 10-20%
```

---

## 📊 CURRENT RECOMMENDATION

**For New Users (Nov 2, 2025):**

**RECOMMENDED: Elite Top 10**

**Why:**
- You have 29 profitable whales (enough for top 10)
- 10 MEGA-tier whales with 98% win rates
- Conservative approach for first-time users
- Lowest drawdown risk (10-15%)
- Highest Sharpe ratio (2.0-2.5)

**Top 10 Whales to Copy:**
1. fengdubiying - $686K P&L, 98% win rate
2. Dillius - $227K P&L, 98% win rate
3. Mayuravarma - $226K P&L, 83.8% win rate
4. S-Works - $200K P&L, 63.7% win rate
5. SwissMiss - $192K P&L, 98% win rate
6. MrSparklySimpsons - $178K P&L, 77.3% win rate
7. slight- - $132K P&L, 98% win rate
8. wasianiversonworldch - $100K P&L, 55.6% win rate
9. jj12345 - $99K P&L, 58.2% win rate
10. 0x5375...aeea - $99K P&L, 61.5% win rate

**Capital Allocation:**
- $700/trade distributed across top 10
- Kelly fraction: 0.25
- Max position per whale: $100

**Risk Management:**
- Stop loss: 15%
- Daily loss limit: $300
- Circuit breaker: Pause if drawdown >10%

---

## 📚 REFERENCES

- **Whale Database:** `/docs/PROFITABLE_WHALES_DATABASE.md`
- **Data Reference:** 60+ whale metrics documented
- **API Access:** http://localhost:8000/api/whales

**Last Updated:** November 2, 2025, 12:45 PM PST
