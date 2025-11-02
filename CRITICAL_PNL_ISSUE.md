# CRITICAL: P&L Calculation Issue

## Problem

Whale `0x53757615de1c42b83f893b79d4241a009dc2aeea` has:
- **Database P&L**: +$99,508.73 (profit)
- **Actual P&L (Polymarket)**: -$1,690,202.90 (loss)
- **Discrepancy**: $1,789,711.63 error

## Impact

**HIGH SEVERITY** - This affects whale qualification:
- Whale appears qualified with positive P&L
- Actually has massive losses
- Should NOT be copied
- Likely affects other whales too

## Root Cause Analysis

### Possible Causes:

1. **Unrealized Losses Not Included**
   - We only count realized P&L from closed trades
   - Polymarket includes open positions (mark-to-market)
   - This whale likely has large open losing positions

2. **Market Resolution Data Missing**
   - We don't track which markets resolved and how
   - Can't calculate true realized P&L without resolution data
   - Trade P&L calculated from entry/exit prices, not resolution outcomes

3. **Calculation Method**
   ```python
   # Current (WRONG):
   pnl = sum((exit_price - entry_price) * size for each trade)

   # Correct (NEEDS MARKET RESOLUTIONS):
   pnl = sum((resolution_price - entry_price) * size for each trade)
   ```

4. **Missing Fees and Slippage**
   - Not accounting for trading fees (0.5-2%)
   - Not accounting for slippage
   - Real P&L lower than calculated

## Immediate Actions Required

### 1. Sync Real P&L from Polymarket API (P0 - CRITICAL)

**Endpoint**: `https://gamma-api.polymarket.com/profile/{address}`

```python
import requests

def fetch_real_pnl(address: str) -> float:
    """Fetch actual P&L from Polymarket API"""
    url = f"https://gamma-api.polymarket.com/profile/{address}"
    response = requests.get(url)
    data = response.json()

    # Extract real P&L
    total_pnl = data.get('total_pnl', 0)  # or whatever the field is called
    return float(total_pnl)
```

**Script to run**: `scripts/sync_real_pnl_from_polymarket.py`

### 2. Re-qualify All Whales (P0 - CRITICAL)

After syncing real P&L:
- Run qualification check again
- Expected: Many "qualified" whales will fail
- Update `is_copying_enabled` flag
- Quarantine whales with negative P&L

### 3. Implement Market Resolution Tracking (P1 - HIGH)

File already exists: `libs/common/market_resolver.py`

Need to:
- Sync historical market resolutions
- Track which markets resolved and outcomes
- Recalculate P&L based on resolution data
- Update whale metrics

### 4. Add Open Position Tracking (P1 - HIGH)

Track unrealized P&L:
```python
# For each whale, track open positions
open_positions = {
    'market_id': {
        'side': 'YES',
        'shares': 100,
        'entry_price': 0.65,
        'current_price': 0.45,  # mark-to-market
        'unrealized_pnl': (0.45 - 0.65) * 100  # -$20
    }
}
```

## Temporary Workaround

**IMMEDIATELY**:
1. Disable copying for whale `0x53757615de1c42b83f893b79d4241a009dc2aeea`
   ```sql
   UPDATE whales
   SET is_copying_enabled = FALSE
   WHERE address = '0x53757615de1c42b83f893b79d4241a009dc2aeea';
   ```

2. Add warning to dashboard:
   ```
   ⚠️ WARNING: P&L data may be inaccurate.
   Market resolution tracking not implemented.
   Verify whale performance on Polymarket before copying.
   ```

## Long-Term Fix

### Phase 1: Data Correction (Week 1)
- [ ] Build Polymarket API scraper for real P&L
- [ ] Sync real P&L for all 41 qualified whales
- [ ] Re-run qualification checks
- [ ] Update dashboard with corrected data

### Phase 2: Market Resolution System (Week 2)
- [ ] Sync historical market resolutions from Polymarket
- [ ] Build market_resolutions table
- [ ] Recalculate all whale P&L from resolution data
- [ ] Implement ongoing resolution tracking

### Phase 3: Open Position Tracking (Week 3)
- [ ] Track open positions per whale
- [ ] Calculate unrealized P&L (mark-to-market)
- [ ] Display realized + unrealized P&L separately
- [ ] Alert on large unrealized losses

## Testing After Fix

Validate with known whales:
- `0x53757615de1c42b83f893b79d4241a009dc2aeea`: Should show -$1.69M
- Check top 5 whales: Verify P&L matches Polymarket
- Run qualification: Expect different whale list

## Related Files

- `libs/common/market_resolver.py` - Market resolution tracker (built, not used)
- `scripts/sync_market_resolutions.py` - Sync script (needs to be run)
- `alembic/versions/002_add_market_resolutions.py` - Database migration

## Status

**UNRESOLVED** - Documented for immediate attention

**Priority**: P0 CRITICAL - Affects core system integrity

**Estimated Fix Time**: 2-3 days for full resolution tracking

**Quick Fix Time**: 2-4 hours to sync real P&L from API
