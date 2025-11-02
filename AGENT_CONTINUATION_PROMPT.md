# Agent Continuation Prompt: Complete Real Historical Backtest System

## Context

You are continuing work on a Polymarket whale copy-trading system. The previous session successfully implemented a historical data fetcher that collects 60 days of real whale trades from Goldsky subgraphs. The data collection is likely complete or nearly complete. Your job is to finish the implementation by updating the backtester to use real data instead of synthetic data.

## What Has Been Completed

### ✅ Data Collection System (DONE)

1. **Script Created**: `scripts/fetch_graph_historical_data.py`
   - Fetches whale trades (>$1,000) from Goldsky Orderbook subgraph
   - Fetches market resolutions from Goldsky PNL subgraph
   - Uses cursor-based pagination (handles unlimited data)
   - Stores in PostgreSQL with deduplication
   - NO API KEY REQUIRED (public Goldsky endpoints)

2. **Data Sources**:
   - Orderbook: `https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn`
   - PNL: `https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/pnl-subgraph/0.0.1/gn`

3. **Expected Data**:
   - 200,000+ whale trades over 60 days
   - Real blockchain timestamps
   - Actual market outcomes (YES/NO resolutions)
   - Unique traders, markets, volumes

### 📝 Documentation Created

- `GRAPH_IMPLEMENTATION_SUCCESS.md` - Implementation details
- `FINAL_STATUS_AND_NEXT_STEPS.md` - Original research findings
- `BLOCKCHAIN_DATA_FINDINGS.md` - Technical analysis
- `IMPLEMENTATION_SUMMARY.md` - Quick-start guide

## Your Mission

Complete the backtesting system by making it use real historical data instead of synthetic data.

## Step-by-Step Implementation Plan

### Phase 1: Verify Data Collection (15 minutes)

**Goal**: Confirm the data fetch completed successfully

**Tasks**:
1. Check if fetch process is still running:
   ```bash
   ps aux | grep fetch_graph_historical_data
   ```

2. If running, wait for completion or check progress in `/tmp/graph_fetch.log`

3. Run data validation script:
   ```bash
   python3 scripts/check_data_status.py
   ```

4. **Expected Output**:
   ```
   📊 WHALE TRADES
      Date range: 2025-09-03 to 2025-11-02
      Duration: ~60 days
      Total trades: 150,000-250,000
      Unique markets: 500-1,000

   📋 MARKETS
      Total markets: 500-1,000
      Resolved markets: 400-800 (70-90%)
   ```

5. **If data is missing**: Run the fetcher manually:
   ```bash
   python3 scripts/fetch_graph_historical_data.py
   ```
   (Takes 10-15 minutes, fetches all 60 days automatically)

### Phase 2: Update Database Schema (15 minutes)

**Goal**: Add proper constraints for deduplication

**File to Check**: `libs/common/models.py`

**Required Changes**:

1. **Add `log_index` column to Trade model** (if missing):
   ```python
   class Trade(Base):
       __tablename__ = 'trades'

       id = Column(Integer, primary_key=True)
       transaction_hash = Column(String, nullable=False)
       log_index = Column(Integer, default=0)  # ADD THIS
       # ... rest of columns

       # ADD THIS CONSTRAINT
       __table_args__ = (
           UniqueConstraint('transaction_hash', 'log_index', name='uq_trade_tx_log'),
       )
   ```

2. **Create migration script** `scripts/migrate_trade_constraints.py`:
   ```python
   from sqlalchemy import create_engine, text

   db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
   engine = create_engine(db_url)

   with engine.connect() as conn:
       # Add log_index if missing
       conn.execute(text("""
           ALTER TABLE trades
           ADD COLUMN IF NOT EXISTS log_index INTEGER DEFAULT 0;
       """))

       # Add unique constraint (drop old one if exists)
       conn.execute(text("""
           ALTER TABLE trades DROP CONSTRAINT IF EXISTS uq_trade_tx_log;
       """))
       conn.execute(text("""
           ALTER TABLE trades
           ADD CONSTRAINT uq_trade_tx_log
           UNIQUE (transaction_hash, log_index);
       """))

       conn.commit()

   print("✅ Migration complete")
   ```

3. Run migration:
   ```bash
   python3 scripts/migrate_trade_constraints.py
   ```

### Phase 3: Refactor Backtester (60 minutes)

**Goal**: Remove synthetic data generation, use real outcomes

**File to Modify**: `src/services/backtester.py`

**Critical Changes Needed**:

#### 3.1: Remove Synthetic Timestamp Generation

**FIND AND DELETE**:
```python
# Any code that generates fake timestamps like:
synthetic_time = start_time + timedelta(...)
trade_time = beta_distribution.rvs(...)
```

**REPLACE WITH**:
```python
# Use actual timestamp from database
trade_time = trade.timestamp
```

#### 3.2: Remove Probabilistic Outcome Calculation

**FIND AND DELETE**:
```python
# Code that estimates outcomes like:
if random.random() < whale_win_rate:
    pnl = shares * (1 - price) - cost
else:
    pnl = -cost
```

**REPLACE WITH**:
```python
def calculate_real_pnl(trade, market):
    """Calculate P&L using actual market outcome"""

    if not market or not market.outcome:
        return None  # Skip unresolved markets

    # Winning trade: shares are worth $1.00 each
    if market.outcome == trade.outcome:
        final_value = trade.shares * Decimal('1.00')
        pnl = final_value - (trade.shares * trade.price)

    # Losing trade: shares are worth $0.00
    else:
        pnl = -(trade.shares * trade.price)

    return pnl
```

#### 3.3: Update Query to Use Only Resolved Markets

**FIND**:
```python
trades = session.query(Trade).filter(
    Trade.is_whale_trade == True
).all()
```

**REPLACE WITH**:
```python
from sqlalchemy.orm import joinedload

trades = session.query(Trade).join(Market).filter(
    Trade.is_whale_trade == True,
    Market.outcome != None,  # Only resolved markets
    Market.closed == True
).options(
    joinedload(Trade.market)  # Eager load market data
).order_by(
    Trade.timestamp.asc()  # Chronological order
).all()
```

#### 3.4: Update Backtest Loop

**REPLACE THE MAIN BACKTEST LOOP** with:

```python
def run_backtest(starting_capital=10000, max_concurrent_positions=5):
    """Run backtest using real historical data"""

    session = Session()

    # Get all trades with resolved markets
    trades = session.query(Trade).join(Market).filter(
        Trade.is_whale_trade == True,
        Market.outcome != None,
        Market.closed == True
    ).options(
        joinedload(Trade.market)
    ).order_by(
        Trade.timestamp.asc()
    ).all()

    if not trades:
        print("❌ No resolved trades found")
        return None

    print(f"📊 Backtesting {len(trades):,} resolved trades")
    print(f"   Date range: {trades[0].timestamp} to {trades[-1].timestamp}")
    print()

    # Backtest state
    capital = Decimal(str(starting_capital))
    positions = []
    completed_trades = []
    equity_curve = []

    for trade in trades:
        market = trade.market

        # Calculate position size (e.g., 5% of capital per trade)
        position_size = capital * Decimal('0.05')
        position_size = min(position_size, capital)  # Don't exceed available capital

        if position_size < Decimal('100'):  # Min position
            continue

        # Calculate shares we would buy
        shares = position_size / trade.price
        cost = shares * trade.price

        # Calculate P&L using real outcome
        pnl = calculate_real_pnl(
            type('Trade', (), {
                'outcome': trade.outcome,
                'shares': shares,
                'price': trade.price
            })(),
            market
        )

        if pnl is None:
            continue

        # Update capital
        capital += pnl

        # Track trade result
        completed_trades.append({
            'timestamp': trade.timestamp,
            'market_id': trade.market_id,
            'outcome': trade.outcome,
            'market_outcome': market.outcome,
            'shares': shares,
            'price': trade.price,
            'cost': cost,
            'pnl': pnl,
            'capital': capital,
            'won': (market.outcome == trade.outcome)
        })

        # Track equity curve
        equity_curve.append({
            'timestamp': trade.timestamp,
            'capital': capital
        })

    session.close()

    # Calculate metrics
    total_trades = len(completed_trades)
    wins = sum(1 for t in completed_trades if t['won'])
    losses = total_trades - wins
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    total_return = (capital - starting_capital) / starting_capital * 100

    # Calculate Sharpe ratio
    returns = [float(t['pnl'] / t['cost']) for t in completed_trades]
    if len(returns) > 1:
        import numpy as np
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    # Calculate max drawdown
    peak = float(starting_capital)
    max_dd = 0
    for point in equity_curve:
        cap = float(point['capital'])
        if cap > peak:
            peak = cap
        dd = (peak - cap) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        'starting_capital': starting_capital,
        'final_capital': capital,
        'total_return_pct': total_return,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'equity_curve': equity_curve,
        'completed_trades': completed_trades,
        'date_range': {
            'start': trades[0].timestamp,
            'end': trades[-1].timestamp
        }
    }
```

### Phase 4: Create Real Backtest Runner (30 minutes)

**Create New File**: `scripts/run_real_backtest.py`

```python
#!/usr/bin/env python3
"""
Real Historical Backtest Runner
================================

Runs backtest using actual historical whale trades and market outcomes.
NO synthetic data, NO probabilistic outcomes - 100% real historical results.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.backtester import run_backtest
from decimal import Decimal
import json

print('=' * 80)
print('REAL HISTORICAL BACKTEST - 60 DAYS')
print('=' * 80)
print()
print('Strategy: Copy all whale trades >$1,000')
print('Data: Real blockchain trades with actual market outcomes')
print('Date Range: Last 60 days')
print()

# Run backtest
results = run_backtest(
    starting_capital=10000,
    max_concurrent_positions=5
)

if not results:
    print('❌ Backtest failed - check data availability')
    sys.exit(1)

# Display results
print()
print('=' * 80)
print('BACKTEST RESULTS')
print('=' * 80)
print()
print(f"📅 Date Range:")
print(f"   Start: {results['date_range']['start']}")
print(f"   End: {results['date_range']['end']}")
print()
print(f"💰 Performance:")
print(f"   Starting Capital: ${results['starting_capital']:,.2f}")
print(f"   Final Capital: ${float(results['final_capital']):,.2f}")
print(f"   Total Return: {float(results['total_return_pct']):.2f}%")
print()
print(f"📊 Trade Statistics:")
print(f"   Total Trades: {results['total_trades']:,}")
print(f"   Wins: {results['wins']} ({results['win_rate']:.1f}%)")
print(f"   Losses: {results['losses']} ({100-results['win_rate']:.1f}%)")
print()
print(f"📈 Risk Metrics:")
print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")
print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")
print()
print('=' * 80)
print('✅ REAL HISTORICAL DATA - NO SYNTHETIC ESTIMATES')
print('=' * 80)
print()

# Save detailed results
with open('backtest_results.json', 'w') as f:
    # Convert Decimals to float for JSON
    json_results = {
        k: (float(v) if isinstance(v, Decimal) else v)
        for k, v in results.items()
        if k not in ['equity_curve', 'completed_trades']
    }
    json.dump(json_results, f, indent=2, default=str)

print('📁 Detailed results saved to: backtest_results.json')
```

### Phase 5: Test & Validate (30 minutes)

**Run the backtest**:
```bash
python3 scripts/run_real_backtest.py
```

**Expected Output**:
```
================================================================================
REAL HISTORICAL BACKTEST - 60 DAYS
================================================================================

Strategy: Copy all whale trades >$1,000
Data: Real blockchain trades with actual market outcomes
Date Range: Last 60 days

📊 Backtesting 45,234 resolved trades
   Date range: 2025-09-03 to 2025-11-02

================================================================================
BACKTEST RESULTS
================================================================================

📅 Date Range:
   Start: 2025-09-03 00:04:16
   End: 2025-11-02 13:34:22

💰 Performance:
   Starting Capital: $10,000.00
   Final Capital: $12,456.00
   Total Return: +24.56%

📊 Trade Statistics:
   Total Trades: 342
   Wins: 189 (55.3%)
   Losses: 153 (44.7%)

📈 Risk Metrics:
   Sharpe Ratio: 1.23
   Max Drawdown: -8.4%

================================================================================
✅ REAL HISTORICAL DATA - NO SYNTHETIC ESTIMATES
================================================================================
```

**Validation Checklist**:

- [ ] Backtest completes without errors
- [ ] Trade count is reasonable (100-1,000 trades)
- [ ] Win rate is realistic (50-60%)
- [ ] Return is plausible (-20% to +50% for 60 days)
- [ ] Sharpe ratio is calculated (typically 0.5 to 2.0)
- [ ] Max drawdown is reasonable (5-20%)
- [ ] Date range matches data collection period
- [ ] NO "synthetic" or "estimated" disclaimers needed

## Troubleshooting Guide

### Problem: No trades in database

**Solution**:
```bash
python3 scripts/fetch_graph_historical_data.py
```
Wait 10-15 minutes for completion

### Problem: No resolved markets

**Check**:
```sql
SELECT COUNT(*) FROM markets WHERE outcome IS NOT NULL;
```

**If zero**: The PNL subgraph query may have failed. Check:
```python
# In fetch_graph_historical_data.py, verify PNL URL is correct
PNL_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/pnl-subgraph/0.0.1/gn"
```

### Problem: Backtest shows 0% return

**Debug**:
```python
# Add debug print in calculate_real_pnl
print(f"Trade outcome: {trade.outcome}, Market outcome: {market.outcome}, PNL: {pnl}")
```

Check if outcomes are matching correctly (should see some matches)

### Problem: Token ID decoding errors

**Fix**: The token ID format is `(condition_id << 8) | outcome_index`
```python
token_id = int(trade['takerAssetId'])
condition_id = hex(token_id >> 8)
outcome_index = token_id & 0xFF
outcome = "YES" if outcome_index == 0 else "NO"
```

## Success Criteria

You've completed the mission when:

1. ✅ Database contains 50,000+ resolved trades
2. ✅ Backtest runs without errors
3. ✅ Results show real dates (not synthetic)
4. ✅ Win rate is between 45-65% (realistic)
5. ✅ No disclaimers about "estimated" or "synthetic" data needed
6. ✅ Performance metrics are calculated (return, Sharpe, drawdown)
7. ✅ Results are saved to `backtest_results.json`

## Files You Will Modify

1. `libs/common/models.py` - Add unique constraint
2. `src/services/backtester.py` - Remove synthetic data logic
3. `scripts/run_real_backtest.py` - New file (create)
4. `scripts/migrate_trade_constraints.py` - New file (create)

## Files You Should NOT Modify

- `scripts/fetch_graph_historical_data.py` (already working)
- Database connection configs
- API endpoints

## Time Estimate

- Phase 1 (Verification): 15 minutes
- Phase 2 (Schema): 15 minutes
- Phase 3 (Backtester): 60 minutes
- Phase 4 (Runner): 30 minutes
- Phase 5 (Testing): 30 minutes

**Total: 2.5 hours**

## Final Deliverable

When complete, run:
```bash
python3 scripts/run_real_backtest.py > final_backtest_results.txt
```

This will produce a clean output file showing the real historical backtest results that can be shared or presented.

---

**Remember**: This is REAL historical data with ACTUAL market outcomes. No estimates, no synthetic data, no probabilities. Just raw blockchain truth.

Good luck! 🚀
