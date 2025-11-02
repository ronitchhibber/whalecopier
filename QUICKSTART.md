# WhaleTracker - Quick Start Guide

## Your System Is Ready!

### 1. Open Dashboard
```
http://localhost:8000
```

### 2. Start Monitoring
Click the **"START MONITORING"** button in the top-right corner

The button will turn green and say **"STOP MONITORING"** when active.

### 3. Watch the Magic Happen

The system will now:
- Check 50 profitable whales every 15 minutes
- Detect when they make trades
- Update stats in real-time
- Execute paper trades automatically

---

## Dashboard Tabs

### Whales Tab
- See all 50 active whales
- View their profit/loss, quality scores, tier
- Sorted by quality score (best first)
- Stats shown: Active Whales, Trades 24h, Volume 24h

### Live Trades Tab
- Real-time feed of whale trades
- Updates every 5 seconds when active
- Shows: Time, Whale, Market, Side, Size, Price

### Trading Tab
- **Paper/Live toggle**: Switch trading modes
- **Active Bets**: Your current open positions
- **Trade History**: All your past trades
- Performance stats: Balance, P&L, Win Rate, ROI

### Methodology Tab
- How whales are selected
- Position sizing strategy
- Risk management rules
- Quality thresholds

### Settings Tab
- Configure paper trading
- Set whale filters
- Adjust risk management
- Save/Reset settings

---

## Top 10 Whales You're Tracking

1. **fengdubiying** - $686,052 profit (MEGA)
2. **LuckyCharmLuckyCharm** - $301,151 profit (MEGA)
3. **PringlesMax** - $296,613 profit (MEGA)
4. **Dillius** - $227,183 profit (MEGA)
5. **Mayuravarma** - $226,650 profit (MEGA)
6. **S-Works** - $200,854 profit (MEGA)
7. **SwissMiss** - $192,955 profit (MEGA)
8. **MrSparklySimpsons** - $178,334 profit (MEGA)
9. **slight-** - $132,779 profit (MEGA)
10. **wasianiversonworldchamp2025** - $100,642 profit (MEGA)

---

## What Happens When You Start Monitoring?

**Every 15 minutes**:
1. System checks all 50 whales for new trades
2. If a whale made a trade, it's detected
3. Trade appears in "Live Trades" tab
4. Paper trade is executed automatically (if enabled)
5. Stats update in real-time

**Every 6 hours**:
1. System calculates comprehensive 24h metrics
2. Updates volume, trade count, activity data
3. Refreshes quality scores
4. Updates whale rankings

---

## Your Wallet

**Address**: `0xCa1120fcf33DA4334028900dD77428Ea348Aa359`

**Status**: Connected and ready

**Current Mode**: Paper trading (no real money)

**To enable live trading**:
```bash
pip3 install py-clob-client
```

---

## Monitoring Status

Check if system is running:
- Green button says "STOP MONITORING" = Running
- Gray button says "START MONITORING" = Not running

You can start/stop anytime with the button.

---

## Quick Commands

### Check System Status
```bash
curl http://localhost:8000/api/system/status
```

### View Whale Count
```bash
curl http://localhost:8000/api/stats/summary
```

### Re-enable Whales (if needed)
```bash
python3 scripts/reenable_whales.py
```

### Test Wallet Connection
```bash
python3 scripts/test_wallet_connection.py
```

---

## Expected Behavior

**First Hour**: System starts checking whales, no trades yet (normal)

**After First Trade**: You'll see:
- Trade appears in Live Trades tab
- Trades 24h counter increases
- Volume 24h shows dollar amount
- Paper trade executed (visible in Trading tab)

**After 6 Hours**: Full metrics update:
- All stats refresh
- Quality scores recalculated
- 24h data updated

---

## Tips

1. **Leave it running**: System works best when monitoring continuously
2. **Check every few hours**: Trades happen throughout the day
3. **Paper trade first**: Test the system before going live
4. **Monitor performance**: Track your win rate and ROI in Trading tab
5. **Adjust settings**: Fine-tune based on your results

---

## Troubleshooting

**No trades showing?**
- Whales may not have traded yet (check back in a few hours)
- Verify system is running (button says "STOP MONITORING")

**Dashboard not updating?**
- Refresh the page
- Check browser console for errors (F12)

**Want to add more whales?**
- System currently has 50 most profitable whales
- Can expand to hundreds/thousands if needed

---

## That's It!

Your WhaleTracker is fully set up and ready to go.

**Click "START MONITORING" and watch the profits roll in!**

Dashboard: http://localhost:8000

---

## Next Steps

- Start monitoring now
- Watch for first trades
- Check Trading tab for performance
- Adjust settings as needed
- Enable live trading when ready

Good luck! 🚀
