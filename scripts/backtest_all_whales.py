#!/usr/bin/env python3
"""
Fetch historical trades from ALL whales and run comprehensive backtest
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
print("COMPREHENSIVE BACKTEST - ALL WHALES")
print("=" * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get ALL active whales
print("📊 Getting ALL whales from database...")
all_whales = session.query(Whale).filter(
    Whale.is_active == True
).order_by(Whale.quality_score.desc()).all()

print(f"Found {len(all_whales)} total whales\n")

# Group whales by quality tier
mega_whales = [w for w in all_whales if w.quality_score and w.quality_score >= 80]
high_whales = [w for w in all_whales if w.quality_score and 60 <= w.quality_score < 80]
medium_whales = [w for w in all_whales if w.quality_score and 40 <= w.quality_score < 60]
low_whales = [w for w in all_whales if w.quality_score and w.quality_score < 40]

print("Whale Distribution:")
print(f"  MEGA (≥80):   {len(mega_whales)} whales")
print(f"  HIGH (60-79): {len(high_whales)} whales")
print(f"  MED (40-59):  {len(medium_whales)} whales")
print(f"  LOW (<40):    {len(low_whales)} whales")
print()

# Fetch trades for each whale
print("🔍 Fetching historical trades...")
print("-" * 80)

total_fetched = 0
failed_count = 0

for i, whale in enumerate(all_whales, 1):
    pseudonym = whale.pseudonym or whale.address[:10]
    quality = whale.quality_score or 0

    # Show progress every 10 whales
    if i % 10 == 0:
        print(f"Progress: {i}/{len(all_whales)} whales processed, {total_fetched} trades fetched")

    try:
        # Fetch last 50 trades per whale (to not overload)
        trades = trade_fetcher.fetch_whale_trades(whale.address, limit=50)

        if trades:
            saved = 0
            for trade_data in trades:
                parsed = trade_fetcher.parse_trade_for_copy(trade_data)
                if parsed and trade_fetcher.save_whale_trade(whale, parsed):
                    saved += 1

            if saved > 0:
                total_fetched += saved

    except Exception as e:
        failed_count += 1
        if failed_count <= 5:  # Only show first 5 errors
            print(f"  Error with {pseudonym}: {str(e)[:50]}")

print()
print(f"✅ Fetching complete!")
print(f"   Total trades fetched: {total_fetched}")
print(f"   Failed whales: {failed_count}")
print()

session.close()

# Check how many whale trades we have total
session = Session()
total_whale_trades = session.query(Trade).filter(Trade.is_whale_trade == True).count()
print(f"📈 Total whale trades in database: {total_whale_trades}")
session.close()

if total_whale_trades == 0:
    print("⚠️  No whale trades in database - cannot run backtest")
    sys.exit(0)

print()
print("=" * 80)
print("🔬 RUNNING COMPREHENSIVE BACKTEST")
print("=" * 80)
print()

# Run multiple backtests with different strategies
strategies = [
    {
        "name": "Conservative (Quality ≥70)",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('50.0'),
            max_daily_loss=Decimal('300.0'),
            min_whale_quality=70,
            position_size_pct=Decimal('0.03'),  # 3%
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
    {
        "name": "Balanced (Quality ≥50)",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('100.0'),
            max_daily_loss=Decimal('500.0'),
            min_whale_quality=50,
            position_size_pct=Decimal('0.05'),  # 5%
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
    {
        "name": "Aggressive (Quality ≥30)",
        "config": BacktestConfig(
            starting_balance=Decimal('1000.0'),
            max_position_usd=Decimal('150.0'),
            max_daily_loss=Decimal('700.0'),
            min_whale_quality=30,
            position_size_pct=Decimal('0.08'),  # 8%
            start_date=datetime.utcnow() - timedelta(days=30)
        )
    },
]

results = []

for strategy in strategies:
    print(f"\n{'=' * 80}")
    print(f"STRATEGY: {strategy['name']}")
    print(f"{'=' * 80}")

    backtester = Backtester(strategy['config'])
    result = backtester.run_backtest()
    results.append((strategy['name'], result))

    print(f"\nPerformance:")
    print(f"  Starting:  ${result.starting_balance:,.2f}")
    print(f"  Ending:    ${result.ending_balance:,.2f}")
    print(f"  P&L:       ${result.total_pnl:,.2f} ({result.total_pnl_pct:+.1f}%)")
    print(f"\nStatistics:")
    print(f"  Trades:    {result.total_trades} ({result.winning_trades}W / {result.losing_trades}L)")
    print(f"  Win Rate:  {result.win_rate:.1f}%")
    print(f"\nRisk:")
    print(f"  Max DD:    ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.1f}%)")
    print(f"  Sharpe:    {result.sharpe_ratio:.2f}")

# Final comparison
print()
print("=" * 80)
print("📊 STRATEGY COMPARISON")
print("=" * 80)
print()

print(f"{'Strategy':<30} {'Trades':<10} {'Win%':<10} {'P&L':<15} {'ROI%':<10}")
print("-" * 80)

for name, result in results:
    pnl_str = f"${result.total_pnl:+,.2f}"
    roi_str = f"{result.total_pnl_pct:+.1f}%"
    print(f"{name:<30} {result.total_trades:<10} {result.win_rate:<9.1f}% {pnl_str:<15} {roi_str:<10}")

print()
print("=" * 80)

# Best strategy
best_strategy = max(results, key=lambda x: x[1].total_pnl)
print(f"\n🏆 BEST PERFORMING STRATEGY: {best_strategy[0]}")
print(f"   Return: {best_strategy[1].total_pnl_pct:+.1f}%")
print(f"   Ending Balance: ${best_strategy[1].ending_balance:,.2f}")

print()
print("=" * 80)
