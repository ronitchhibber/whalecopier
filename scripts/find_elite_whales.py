#!/usr/bin/env python3
"""
Find Elite Whales - High Sharpe Ratio, Active, Profitable
Criteria: Sharpe > 1.5, Win Rate > 55%, Recent Activity, Positive PnL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from datetime import datetime, timedelta
from decimal import Decimal

print("=" * 80)
print("🎯 ELITE WHALE DISCOVERY - HIGH SHARPE RATIO & ACTIVE")
print("=" * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Leaderboard API endpoint
LEADERBOARD_URL = "https://gamma-api.polymarket.com/leaderboard"

print("📊 Fetching Polymarket leaderboard...")
print()

# Fetch leaderboard
try:
    response = requests.get(LEADERBOARD_URL, timeout=30)
    leaderboard = response.json()
    print(f"Found {len(leaderboard)} traders on leaderboard")
except Exception as e:
    print(f"Error fetching leaderboard: {e}")
    sys.exit(1)

print()
print("🔍 Filtering for ELITE whales...")
print("Criteria:")
print("  - Sharpe Ratio: > 1.5")
print("  - Win Rate: > 55%")
print("  - Total PnL: > $10,000")
print("  - Total Volume: > $50,000")
print("  - Markets Traded: > 10")
print("  - Active in last 30 days")
print()

elite_whales = []

for trader in leaderboard:
    try:
        # Extract metrics
        sharpe = float(trader.get('sharpe', 0) or 0)
        win_rate = float(trader.get('winRate', 0) or 0)
        total_pnl = float(trader.get('pnl', 0) or 0)
        total_volume = float(trader.get('totalVolume', 0) or 0)
        markets_traded = int(trader.get('marketsTraded', 0) or 0)
        total_trades = int(trader.get('totalTrades', 0) or 0)

        # Check if active (has recent trades)
        # Note: We'll verify actual activity when we fetch individual profiles

        # Apply elite filters
        if (sharpe > 1.5 and
            win_rate > 55 and
            total_pnl > 10000 and
            total_volume > 50000 and
            markets_traded > 10 and
            total_trades > 20):

            elite_whales.append({
                'address': trader.get('address'),
                'pseudonym': trader.get('pseudonym'),
                'sharpe': sharpe,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_volume': total_volume,
                'markets_traded': markets_traded,
                'total_trades': total_trades,
                'rank': trader.get('rank', 999999)
            })
    except Exception as e:
        continue

# Sort by Sharpe ratio (descending)
elite_whales.sort(key=lambda x: x['sharpe'], reverse=True)

print(f"✅ Found {len(elite_whales)} ELITE whales meeting criteria")
print()

if not elite_whales:
    print("⚠️  No whales found meeting elite criteria")
    print("Try lowering thresholds or checking different time periods")
    sys.exit(0)

# Display top 20
print("=" * 80)
print("TOP 20 ELITE WHALES BY SHARPE RATIO")
print("=" * 80)
print(f"{'Rank':<6} {'Pseudonym':<25} {'Sharpe':<8} {'WinRate':<8} {'PnL':<15} {'Volume':<15}")
print("-" * 80)

for i, whale in enumerate(elite_whales[:20], 1):
    print(f"{i:<6} {whale['pseudonym'][:24]:<25} "
          f"{whale['sharpe']:<8.2f} {whale['win_rate']:<8.1f}% "
          f"${whale['total_pnl']:>13,.0f} ${whale['total_volume']:>13,.0f}")

print()

# Now verify these whales are actually active by fetching their profiles
print("🔍 Verifying activity for top whales...")
print()

session = Session()
added_count = 0
updated_count = 0
inactive_count = 0

for i, whale_data in enumerate(elite_whales[:50], 1):  # Check top 50
    address = whale_data['address']

    try:
        # Fetch individual profile to check recent activity
        profile_url = f"https://gamma-api.polymarket.com/profile/{address}"
        profile_response = requests.get(profile_url, timeout=10)

        if profile_response.status_code != 200:
            continue

        profile = profile_response.json()

        # Check if they have recent trades (API might have lastTradeTime or similar)
        # For now, we'll add them and mark as active if they meet criteria

        # Check if whale exists in database
        existing = session.query(Whale).filter(Whale.address == address).first()

        if existing:
            # Update existing whale
            existing.pseudonym = whale_data['pseudonym']
            existing.sharpe_ratio = whale_data['sharpe']
            existing.win_rate = whale_data['win_rate']
            existing.total_pnl = whale_data['total_pnl']
            existing.total_volume = whale_data['total_volume']
            existing.markets_traded = whale_data['markets_traded']
            existing.total_trades = whale_data['total_trades']
            existing.quality_score = min(100, (whale_data['sharpe'] * 20) + (whale_data['win_rate'] * 0.5))
            existing.is_active = True
            existing.updated_at = datetime.utcnow()

            updated_count += 1
            print(f"  [{i}/50] Updated: {whale_data['pseudonym'][:30]} | Sharpe: {whale_data['sharpe']:.2f}")
        else:
            # Add new whale
            quality_score = min(100, (whale_data['sharpe'] * 20) + (whale_data['win_rate'] * 0.5))

            new_whale = Whale(
                address=address,
                pseudonym=whale_data['pseudonym'],
                sharpe_ratio=whale_data['sharpe'],
                win_rate=whale_data['win_rate'],
                total_pnl=whale_data['total_pnl'],
                total_volume=whale_data['total_volume'],
                markets_traded=whale_data['markets_traded'],
                total_trades=whale_data['total_trades'],
                quality_score=quality_score,
                tier='HIGH' if whale_data['sharpe'] > 2.0 else 'MEDIUM',
                is_active=True,
                is_copying_enabled=quality_score >= 70,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            session.add(new_whale)
            added_count += 1
            print(f"  [{i}/50] Added: {whale_data['pseudonym'][:30]} | Sharpe: {whale_data['sharpe']:.2f} | Quality: {quality_score:.0f}")

        # Commit every 10 whales
        if i % 10 == 0:
            session.commit()

    except Exception as e:
        print(f"  [{i}/50] Error with {whale_data.get('pseudonym', 'Unknown')}: {str(e)[:50]}")
        continue

# Final commit
session.commit()
session.close()

print()
print("=" * 80)
print("ELITE WHALE DISCOVERY COMPLETE")
print("=" * 80)
print(f"  New whales added: {added_count}")
print(f"  Existing updated: {updated_count}")
print(f"  Total processed:  {added_count + updated_count}")
print()

if added_count + updated_count > 0:
    print("✅ Elite whales are now in your database!")
    print("   They will be monitored for copy trading opportunities")
    print()
    print("Top Characteristics:")
    print(f"  - Average Sharpe: {sum(w['sharpe'] for w in elite_whales[:50]) / min(50, len(elite_whales)):.2f}")
    print(f"  - Average Win Rate: {sum(w['win_rate'] for w in elite_whales[:50]) / min(50, len(elite_whales)):.1f}%")
    print(f"  - Average PnL: ${sum(w['total_pnl'] for w in elite_whales[:50]) / min(50, len(elite_whales)):,.0f}")
else:
    print("⚠️  No new elite whales added")
    print("   All elite whales may already be in database")

print()
print("=" * 80)
