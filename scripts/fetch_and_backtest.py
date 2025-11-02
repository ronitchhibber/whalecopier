#!/usr/bin/env python3
"""
Fetch historical whale trades and run backtest
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade
from src.services.whale_trade_fetcher import trade_fetcher
from src.services.backtester import Backtester, BacktestConfig
from datetime import datetime, timedelta
from decimal import Decimal

print("=" * 80)
print("FETCH HISTORICAL TRADES & RUN BACKTEST")
print("=" * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get top quality whales
print("📊 Finding top quality whales...")
whales = session.query(Whale).filter(
    Whale.quality_score >= 50,
    Whale.is_active == True
).order_by(Whale.quality_score.desc()).limit(10).all()

print(f"Found {len(whales)} quality whales to fetch trades from\n")

# Fetch trades for each whale
total_fetched = 0
for i, whale in enumerate(whales, 1):
    print(f"[{i}/{len(whales)}] Fetching trades for {whale.pseudonym or whale.address[:10]}...")
    print(f"         Quality: {whale.quality_score:.0f} | Total Volume: ${whale.total_volume:,.0f}")

    # Fetch last 100 trades for this whale
    trades = trade_fetcher.fetch_whale_trades(whale.address, limit=100)

    if trades:
        print(f"         Found {len(trades)} trades")

        # Save each trade
        saved = 0
        for trade_data in trades:
            parsed = trade_fetcher.parse_trade_for_copy(trade_data)
            if parsed and trade_fetcher.save_whale_trade(whale, parsed):
                saved += 1

        print(f"         Saved {saved} new trades to database")
        total_fetched += saved
    else:
        print(f"         No trades found")

    print()

print(f"✅ Total historical trades fetched: {total_fetched}\n")
print("=" * 80)

# Close session
session.close()

if total_fetched == 0:
    print("⚠️  No trades fetched - cannot run backtest")
    print("This could mean:")
    print("  - Whales haven't traded recently")
    print("  - API access issues")
    print("  - Trades already in database")
    sys.exit(0)

# Run backtest
print("🔬 Running backtest with fetched data...")
print("=" * 80)
print()

# Configure backtest - last 30 days
config = BacktestConfig(
    starting_balance=Decimal('1000.0'),
    max_position_usd=Decimal('100.0'),
    max_daily_loss=Decimal('500.0'),
    min_whale_quality=50,
    position_size_pct=Decimal('0.05'),  # 5%
    start_date=datetime.utcnow() - timedelta(days=30)
)

backtester = Backtester(config)
result = backtester.run_backtest()

print()
print("=" * 80)
print("📈 BACKTEST RESULTS")
print("=" * 80)
print()

print("PERFORMANCE SUMMARY")
print(f"  Starting Balance:  ${result.starting_balance:,.2f}")
print(f"  Ending Balance:    ${result.ending_balance:,.2f}")
print(f"  Total P&L:         ${result.total_pnl:,.2f} ({result.total_pnl_pct:+.1f}%)")
print()

print("TRADE STATISTICS")
print(f"  Total Trades:      {result.total_trades}")
print(f"  Winning Trades:    {result.winning_trades} (green)")
print(f"  Losing Trades:     {result.losing_trades} (red)")
print(f"  Win Rate:          {result.win_rate:.1f}%")
print()

print("RISK METRICS")
print(f"  Max Drawdown:      ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.1f}%)")
print(f"  Sharpe Ratio:      {result.sharpe_ratio:.2f}")
print(f"  Test Period:       {result.days} days")
print()

if result.whale_performance:
    print("TOP PERFORMING WHALES")
    print("-" * 80)

    # Sort whales by P&L
    sorted_whales = sorted(
        result.whale_performance.items(),
        key=lambda x: x[1]['total_pnl'],
        reverse=True
    )[:5]

    for whale_addr, perf in sorted_whales:
        win_rate = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
        pnl_sign = '+' if perf['total_pnl'] >= 0 else ''
        print(f"  {perf['pseudonym']:25s} | "
              f"Q:{perf['quality']:3.0f} | "
              f"{perf['trades']:3d} trades | "
              f"{win_rate:5.1f}% WR | "
              f"{pnl_sign}${perf['total_pnl']:8.2f}")

print()
print("=" * 80)

# Show verdict
print()
if result.total_pnl > 0:
    roi = result.total_pnl_pct
    print(f"🎉 PROFITABLE STRATEGY!")
    print(f"   {roi:+.1f}% return over {result.days} days")
    if roi > 10:
        print(f"   This is an excellent return!")
    elif roi > 5:
        print(f"   This is a solid return!")
    else:
        print(f"   Small but positive return")
elif result.total_pnl < 0:
    print(f"⚠️  LOSING STRATEGY")
    print(f"   {result.total_pnl_pct:.1f}% loss over {result.days} days")
    print(f"   Consider adjusting parameters or whale selection")
else:
    print(f"➖ BREAK-EVEN")
    print(f"   No profit or loss over {result.days} days")

print()
print("=" * 80)
