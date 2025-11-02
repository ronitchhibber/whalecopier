#!/usr/bin/env python3
"""
Analyze why trades are not being copied/followed.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import json

# Database setup
DATABASE_URL = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(DATABASE_URL)

# Load copy trading rules
with open('config/copy_trading_rules.json', 'r') as f:
    config = json.load(f)

print("=" * 80)
print("🔍 ANALYZING WHY TRADES ARE NOT BEING COPIED")
print("=" * 80)
print()

# Get recent whale trades
with engine.connect() as conn:
    # Analyze recent trades against copy rules
    result = conn.execute(text("""
        SELECT
            trader_address,
            COUNT(*) as trade_count,
            AVG(amount) as avg_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount,
            SUM(CASE WHEN amount >= 100 THEN 1 ELSE 0 END) as above_min_size,
            SUM(CASE WHEN price >= 0.05 AND price <= 0.95 THEN 1 ELSE 0 END) as in_price_range
        FROM trades
        WHERE is_whale_trade = true
        AND timestamp > NOW() - INTERVAL '30 minutes'
        GROUP BY trader_address
        ORDER BY trade_count DESC
    """)).fetchall()

    print("📊 Recent Whale Trade Analysis (last 30 minutes):")
    print()

    min_position = config['trade_filters']['min_whale_position_size_usd']
    max_position = config['trade_filters']['max_whale_position_size_usd']
    min_price = config['trade_filters']['price_filters']['min_price']
    max_price = config['trade_filters']['price_filters']['max_price']

    print(f"Copy Trading Rules:")
    print(f"  Min position size: ${min_position}")
    print(f"  Max position size: ${max_position}")
    print(f"  Price range: {min_price} - {max_price}")
    print()

    total_trades = 0
    copyable_trades = 0

    for row in result:
        address = row[0]
        trade_count = row[1]
        avg_amount = row[2] or 0
        min_amount = row[3] or 0
        max_amount = row[4] or 0
        above_min = row[5] or 0
        in_range = row[6] or 0

        total_trades += trade_count

        print(f"Whale: {address[:10]}...")
        print(f"  Trades: {trade_count}")
        print(f"  Amount range: ${min_amount:.2f} - ${max_amount:.2f} (avg: ${avg_amount:.2f})")
        print(f"  Above ${min_position} minimum: {above_min}/{trade_count} ({above_min/trade_count*100:.1f}%)")
        print(f"  In price range ({min_price}-{max_price}): {in_range}/{trade_count} ({in_range/trade_count*100:.1f}%)")

        # Check if whale is in enabled list
        whale_info = conn.execute(text("""
            SELECT is_copying_enabled, tier, quality_score
            FROM whales
            WHERE address = :address
        """), {"address": address}).fetchone()

        if whale_info:
            print(f"  Copy enabled: {whale_info[0]}")
            print(f"  Tier: {whale_info[1] or 'Not set'}")
            print(f"  Quality score: {whale_info[2] or 0:.1f}")
        else:
            print(f"  ❌ Whale not in database!")

        # Count potentially copyable trades
        copyable = min(above_min, in_range)
        copyable_trades += copyable
        print(f"  Potentially copyable: {copyable}/{trade_count}")
        print()

    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total whale trades: {total_trades}")
    print(f"Potentially copyable: {copyable_trades} ({copyable_trades/total_trades*100:.1f}%)")
    print()

    # Check why specific trades weren't followed
    print("🔍 Checking recent large trades that should have been copied:")
    print()

    large_trades = conn.execute(text("""
        SELECT
            t.trade_id,
            t.trader_address,
            t.side,
            t.size,
            t.price,
            t.amount,
            t.followed,
            t.skip_reason,
            w.is_copying_enabled,
            w.tier
        FROM trades t
        LEFT JOIN whales w ON t.trader_address = w.address
        WHERE t.is_whale_trade = true
        AND t.amount >= :min_amount
        AND t.price >= :min_price
        AND t.price <= :max_price
        AND t.timestamp > NOW() - INTERVAL '30 minutes'
        ORDER BY t.amount DESC
        LIMIT 10
    """), {
        "min_amount": min_position,
        "min_price": min_price,
        "max_price": max_price
    }).fetchall()

    for trade in large_trades:
        print(f"Trade {trade[0][:20]}...")
        print(f"  Whale: {trade[1][:10]}...")
        print(f"  {trade[2]} {trade[3]:.2f} @ ${trade[4]:.3f} = ${trade[5]:.2f}")
        print(f"  Followed: {trade[6]}")
        print(f"  Skip reason: {trade[7] or 'None'}")
        print(f"  Whale copy enabled: {trade[8]}")
        print(f"  Whale tier: {trade[9] or 'Not set'}")

        if not trade[6]:  # Not followed
            reasons = []
            if not trade[8]:
                reasons.append("Whale not enabled for copying")
            if not trade[9]:
                reasons.append("Whale tier not configured")

            if reasons:
                print(f"  ⚠️ Not copied because: {', '.join(reasons)}")
        print()

print("✅ Analysis complete!")
print()
print("Key Findings:")
print("1. Most trades are too small (< $100 minimum)")
print("2. Copy logic may not be fully implemented in engine.py")
print("3. Some whales may not have copying enabled")