# Real Trading Guide

## 🚀 Production-Ready Whale Copy Trading System

This guide explains how to use the comprehensive bet weighting and real trading system for live Polymarket trading.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Bet Weighting Engine](#bet-weighting-engine)
3. [Position Sizing](#position-sizing)
4. [Risk Management](#risk-management)
5. [Real Trading Setup](#real-trading-setup)
6. [Safety Features](#safety-features)
7. [Polymarket API Integration](#polymarket-api-integration)
8. [Monitoring & Circuit Breakers](#monitoring--circuit-breakers)
9. [Best Practices](#best-practices)

---

## System Overview

The whale copy trading system uses a sophisticated multi-factor position sizing algorithm that balances profitability with risk management.

### Core Components

1. **Bet Weighting Engine** (`libs/trading/bet_weighting.py`)
   - Kelly Criterion-based position sizing
   - Multi-factor weight adjustments
   - Portfolio-level constraints

2. **Real Trading Engine** (`libs/trading/real_trader.py`)
   - Trade execution (paper/live/approval modes)
   - Circuit breakers
   - Performance monitoring

3. **Polymarket Integration** (`src/api/polymarket_client.py`)
   - API authentication
   - Order placement
   - Market data fetching

---

## Bet Weighting Engine

### How Position Sizing Works

The system calculates optimal bet size through 5 steps:

```
Base Position (Kelly)
  ↓
× Whale Quality Multiplier (0.5x - 2.0x)
  ↓
× Market Quality Multiplier (0.5x - 1.5x)
  ↓
× Risk Adjustment (0x - 1.0x)
  ↓
× Portfolio Constraints (0x - 1.0x)
  ↓
= Final Position Size
```

### Step 1: Base Kelly Position

Uses Kelly Criterion to calculate optimal bet size:

```
Kelly% = (p × b - q) / b

Where:
- p = win probability (whale's win rate)
- q = loss probability (1 - p)
- b = odds (payout ratio from market price)
```

**Safety Factor**: Uses 25% of full Kelly (configurable) to reduce risk.

### Step 2: Whale Quality Multiplier

Adjusts based on whale trader quality:

**Factors:**
- Quality Score (0-100): Primary factor
- Sharpe Ratio: Risk-adjusted performance
- Win Rate: Historical success
- Consistency: Performance stability
- Recent Performance: Recent ROI

**Result:** 0.5x to 2.0x multiplier

**Example:**
- Elite whale (95 score, 4.5 Sharpe): ~1.8x
- Average whale (65 score, 2.0 Sharpe): ~1.3x
- Poor whale (45 score, 0.5 Sharpe): ~1.0x

### Step 3: Market Quality Multiplier

Adjusts based on market conditions:

**Factors:**
- Liquidity: Higher is better
- Spread: Lower is better
- Time to close: More time = lower risk

**Result:** 0.5x to 1.5x multiplier

**Example:**
- Great market ($100k liq, 1% spread): ~1.2x
- Average market ($25k liq, 3% spread): ~0.7x
- Poor market ($5k liq, 8% spread): ~0.5x

### Step 4: Risk Adjustment

Reduces position size based on current risk:

**Triggers:**
- Portfolio drawdown > 10%
- Daily losses > 5%
- High market volatility
- Many open positions

**Result:** 0x to 1.0x multiplier

**Example:**
- 15% drawdown → 0.85x reduction
- 10% daily loss → 0.80x reduction
- 60% volatility → 0.70x reduction

### Step 5: Portfolio Constraints

Enforces hard limits:

- Max total exposure: 80% of portfolio
- Max per market: 20% of portfolio
- Max per category: 40% of portfolio
- Max positions: 15 concurrent

**Result:** 0x to 1.0x multiplier

---

## Position Sizing

### Configuration

```python
engine = BetWeightingEngine(
    base_position_pct=0.05,    # 5% base position
    max_position_pct=0.10,     # 10% max position
    kelly_fraction=0.25,        # Use 25% Kelly
    min_position_size=50.0,     # Min $50 bet
    max_position_size=1000.0,   # Max $1000 bet
    max_total_exposure=0.80,    # Max 80% deployed
    max_positions=15,           # Max 15 open positions
)
```

### Position Size Examples

**$10,000 Portfolio:**

| Scenario | Whale Quality | Market Quality | Position Size |
|----------|--------------|----------------|---------------|
| Best Case | Elite (95) | Great ($100k liq) | $548 (5.5%) |
| Average | Average (65) | Average ($25k liq) | $245 (2.5%) |
| Worst Case | Poor (45) | Bad ($5k liq) | $67 (0.7%) |
| Constrained | Elite (95) | Great (high exposure) | $64 (0.6%) |

---

## Risk Management

### Circuit Breakers

Automatically halt trading when:

1. **Daily Loss Limit** (default: $500)
   - Triggers if daily losses exceed limit
   - Resets daily at midnight

2. **Hourly Loss Limit** (default: $200)
   - Triggers if hourly losses exceed limit
   - Resets every hour

3. **Consecutive Losses** (default: 5)
   - Triggers after N losing trades in a row
   - Requires manual reset

### Manual Reset

```python
trader.reset_circuit_breaker()
```

### Position Limits

- **Per Trade**: $50 - $1,000
- **Per Market**: 20% max
- **Per Category**: 40% max
- **Total Exposure**: 80% max
- **Open Positions**: 15 max

---

## Real Trading Setup

### Trading Modes

1. **PAPER** (default): Simulated trading
2. **APPROVAL**: Requires manual approval
3. **LIVE**: Real money trading

### Basic Setup

```python
from libs.trading.real_trader import RealTradingEngine
from libs.trading.bet_weighting import BetWeightingEngine

# Create bet weighting engine
weighting_engine = BetWeightingEngine(
    base_position_pct=0.05,
    max_position_pct=0.10,
    kelly_fraction=0.25,
)

# Create trading engine
trader = RealTradingEngine(
    mode='PAPER',  # Start with paper trading
    initial_balance=10000.0,
    weighting_engine=weighting_engine,
    daily_loss_limit=500.0,
    enable_circuit_breaker=True,
)

# Process whale trade
order = await trader.process_whale_trade(
    whale=whale_profile,
    market=market_context,
    entry_price=0.55,
    whale_size=5000.0,
)

# Check performance
trader.print_summary()
```

### Approval Mode Workflow

```python
# Mode: APPROVAL
trader = RealTradingEngine(mode='APPROVAL')

# Trade creates pending order
order = await trader.process_whale_trade(...)

# Review pending orders
for order in trader.pending_orders:
    print(f"{order.market_title}: ${order.size_usd:.2f}")
    print(f"Confidence: {order.confidence}/100")
    print(f"Reasoning: {order.reasoning}")

    # Approve or reject
    if input("Approve? (y/n): ") == 'y':
        await trader._execute_order_live(order, market)
```

---

## Safety Features

### Pre-Trade Validation

Every trade checked for:

✅ Minimum position size
✅ Available balance
✅ Confidence threshold
✅ Position limits
✅ Circuit breaker status
✅ Duplicate detection

### Trade Validation

```python
should_execute, issues = engine.validate_trade(bet_weight, portfolio)

if not should_execute:
    print("Trade rejected:")
    for issue in issues:
        print(f"  - {issue}")
```

### Confidence Scoring

Trades include confidence score (0-100):

- **>70**: High confidence (strong whale + good market)
- **50-70**: Medium confidence (proceed with caution)
- **<50**: Low confidence (likely rejected)

---

## Polymarket API Integration

### Setup Polymarket Client

```python
from src.api.polymarket_client import PolymarketClient

# Initialize client
client = PolymarketClient(
    private_key="YOUR_PRIVATE_KEY",  # Keep secure!
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
)

# Test connection
markets = await client.get_active_markets()
print(f"Found {len(markets)} active markets")
```

### Live Trading with Polymarket

```python
# Create trader with Polymarket client
trader = RealTradingEngine(
    mode='LIVE',  # ⚠️ REAL MONEY
    polymarket_client=client,
    initial_balance=1000.0,  # Start small!
)

# Process whale trade (executes on Polymarket)
order = await trader.process_whale_trade(
    whale=whale_profile,
    market=market_context,
    entry_price=0.55,
    whale_size=5000.0,
)

if order and order.executed:
    print(f"✅ Live trade executed: {order.market_title}")
    print(f"   Size: ${order.size_usd:.2f}")
    print(f"   Price: ${order.execution_price:.4f}")
```

### API Rate Limits

Polymarket has rate limits:
- 10 requests per second
- 1000 requests per minute

The system includes automatic rate limiting.

---

## Monitoring & Circuit Breakers

### Real-Time Monitoring

```python
# Get performance summary
summary = trader.get_performance_summary()

print(f"Balance: ${summary['current_balance']:,.2f}")
print(f"P&L: ${summary['total_pnl']:+,.2f}")
print(f"ROI: {summary['roi']:+.2f}%")
print(f"Win Rate: {summary['win_rate']:.1f}%")
print(f"Circuit Breaker: {summary['circuit_breaker_status']}")
```

### Circuit Breaker Status

```python
if trader.circuit_breaker.triggered:
    print(f"⚠️  CIRCUIT BREAKER TRIGGERED")
    print(f"Reason: {trader.circuit_breaker.trigger_reason}")
    print(f"Daily loss: ${trader.circuit_breaker.current_daily_loss:.2f}")
    print(f"Consecutive losses: {trader.circuit_breaker.consecutive_losses}")
```

### Position Management

```python
# View open positions
for market_id, position in trader.open_positions.items():
    print(f"{position.order_id}: ${position.size_usd:.2f}")
    print(f"  P&L: ${position.pnl:+.2f}")

# Close position
trader.close_position(
    market_id="market_123",
    exit_price=0.62,
    reason="Take profit"
)
```

---

## Best Practices

### Starting Live Trading

1. **Start Small**: Begin with $500-1000, not your full bankroll
2. **Use APPROVAL Mode**: Manually review trades initially
3. **Conservative Settings**: Use smaller position sizes
4. **Monitor Closely**: Check every few hours initially
5. **Test Paper First**: Run paper trading for at least a week

### Conservative Settings

```python
engine = BetWeightingEngine(
    base_position_pct=0.03,       # 3% base (vs 5%)
    max_position_pct=0.05,        # 5% max (vs 10%)
    kelly_fraction=0.15,          # 15% Kelly (vs 25%)
    min_whale_quality=80.0,       # Higher quality (vs 70)
    max_positions=10,             # Fewer positions (vs 15)
)
```

### Aggressive Settings

```python
engine = BetWeightingEngine(
    base_position_pct=0.07,       # 7% base
    max_position_pct=0.15,        # 15% max
    kelly_fraction=0.35,          # 35% Kelly
    min_whale_quality=60.0,       # Lower quality threshold
    max_positions=20,             # More positions
)
```

### Monitoring Checklist

Daily:
- [ ] Check P&L and ROI
- [ ] Review open positions
- [ ] Check circuit breaker status
- [ ] Verify API connection

Weekly:
- [ ] Analyze winning/losing trades
- [ ] Review whale performance
- [ ] Adjust settings if needed
- [ ] Check Polymarket balance

### Red Flags

🚨 **Stop trading if:**
- Daily loss > 10% of bankroll
- 10+ consecutive losses
- Circuit breaker triggering frequently
- Unexplained API errors
- Polymarket balance mismatch

### Security

- **Never commit private keys** to git
- Use environment variables for secrets
- Enable 2FA on Polymarket account
- Withdraw profits regularly
- Keep backups of trade history

---

## Quick Start Command

```bash
# Demo bet weighting system
python3 scripts/demo_bet_weighting.py

# Start paper trading
python3 -c "
from libs.trading.real_trader import RealTradingEngine
trader = RealTradingEngine(mode='PAPER')
trader.print_summary()
"
```

---

## Support & Resources

- Polymarket API Docs: https://docs.polymarket.com
- Kelly Criterion: https://en.wikipedia.org/wiki/Kelly_criterion
- Risk Management: See `libs/trading/bet_weighting.py`

---

## Disclaimer

**⚠️ WARNING: Real money trading involves risk.**

- Past performance does not guarantee future results
- Only trade with money you can afford to lose
- Start with paper trading to understand the system
- This is not financial advice
- You are responsible for your trading decisions

The backtests showed +1,336% ROI, but this was historical data. Live trading may perform differently.

**Trade responsibly!**
