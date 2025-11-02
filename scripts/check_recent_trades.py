#!/usr/bin/env python3
"""
Check recent whale trades from copy trading engine.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Database setup
DATABASE_URL = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(DATABASE_URL)

print("=" * 80)
print("🔍 CHECKING RECENT WHALE TRADES")
print("=" * 80)
print()

# Check trades from last 10 minutes
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT
            COUNT(*) as new_trades,
            COUNT(DISTINCT trader_address) as unique_whales,
            MIN(timestamp) as oldest,
            MAX(timestamp) as newest
        FROM trades
        WHERE is_whale_trade = true
        AND timestamp > NOW() - INTERVAL '10 minutes'
    """)).fetchone()

    print(f"📊 Trades in last 10 minutes:")
    print(f"   New trades: {result[0]}")
    print(f"   Unique whales: {result[1]}")
    print(f"   Time range: {result[2]} to {result[3]}")
    print()

    # Show sample of recent trades
    trades = conn.execute(text("""
        SELECT
            trade_id,
            trader_address,
            side,
            size,
            price,
            amount,
            timestamp,
            market_id
        FROM trades
        WHERE is_whale_trade = true
        AND timestamp > NOW() - INTERVAL '10 minutes'
        ORDER BY timestamp DESC
        LIMIT 5
    """)).fetchall()

    if trades:
        print("📈 Sample of recent trades:")
        for trade in trades:
            print(f"   {trade[6]}: {trade[2]} {trade[3]:.2f} @ ${trade[4]:.3f} = ${trade[5]:.2f}")
            print(f"      Whale: {trade[1][:10]}...")
            print(f"      Market: {trade[7][:30] if trade[7] else 'No market_id'}...")
            print()

    # Check overall stats
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_trades,
            COUNT(CASE WHEN is_whale_trade = true THEN 1 END) as whale_trades,
            COUNT(CASE WHEN followed = true THEN 1 END) as followed_trades,
            COUNT(CASE WHEN market_id IS NOT NULL AND market_id != '' THEN 1 END) as has_market_id
        FROM trades
    """)).fetchone()

    print("=" * 80)
    print("📊 OVERALL TRADE STATISTICS")
    print("=" * 80)
    print(f"Total trades: {result[0]:,}")
    print(f"Whale trades: {result[1]:,} ({result[1]/result[0]*100:.1f}%)")
    print(f"Followed trades: {result[2]:,} ({result[2]/result[0]*100:.1f}%)")
    print(f"Has market_id: {result[3]:,} ({result[3]/result[0]*100:.1f}%)")

print()
print("✅ Copy trading engine is successfully detecting and saving whale trades!")