#!/usr/bin/env python3
"""
Update Whale Metrics from Polymarket API
Fetches fresh profile data to populate Sharpe ratios, win rates, and other performance metrics
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from datetime import datetime
import time

print("=" * 80)
print("🔄 UPDATING WHALE METRICS FROM POLYMARKET API")
print("=" * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get all active whales
print("📊 Getting whales from database...")
whales = session.query(Whale).filter(Whale.is_active == True).all()
print(f"Found {len(whales)} active whales")
print()

print("🔍 Fetching updated metrics from Polymarket API...")
print("-" * 80)

updated_count = 0
failed_count = 0
skipped_count = 0

for i, whale in enumerate(whales, 1):
    address = whale.address
    pseudonym = whale.pseudonym or address[:10]

    # Show progress every 50 whales
    if i % 50 == 0:
        print(f"Progress: {i}/{len(whales)} whales processed ({updated_count} updated, {failed_count} failed)")

    try:
        # Fetch profile from API
        profile_url = f"https://gamma-api.polymarket.com/profile/{address}"
        response = requests.get(profile_url, timeout=10)

        if response.status_code != 200:
            failed_count += 1
            if failed_count <= 5:
                print(f"  [{i}] Failed to fetch {pseudonym}: HTTP {response.status_code}")
            continue

        profile = response.json()

        # Extract metrics
        sharpe = float(profile.get('sharpe', 0) or 0)
        win_rate = float(profile.get('winRate', 0) or 0)
        total_pnl = float(profile.get('pnl', 0) or 0)
        total_volume = float(profile.get('totalVolume', 0) or 0)
        markets_traded = int(profile.get('marketsTraded', 0) or 0)
        total_trades = int(profile.get('totalTrades', 0) or 0)

        # Check if there's new data
        has_updates = False

        if sharpe != (whale.sharpe_ratio or 0):
            whale.sharpe_ratio = sharpe
            has_updates = True

        if win_rate != (whale.win_rate or 0):
            whale.win_rate = win_rate
            has_updates = True

        if total_pnl != (whale.total_pnl or 0):
            whale.total_pnl = total_pnl
            has_updates = True

        if total_volume != (whale.total_volume or 0):
            whale.total_volume = total_volume
            has_updates = True

        if markets_traded != (whale.markets_traded or 0):
            whale.markets_traded = markets_traded
            has_updates = True

        if total_trades != (whale.total_trades or 0):
            whale.total_trades = total_trades
            has_updates = True

        # Update pseudonym if available
        if profile.get('pseudonym') and profile['pseudonym'] != whale.pseudonym:
            whale.pseudonym = profile['pseudonym']
            has_updates = True

        if has_updates:
            whale.updated_at = datetime.utcnow()
            updated_count += 1

            # Show details for whales with good metrics
            if sharpe > 1.5 and win_rate > 55:
                print(f"  ✅ [{i}] {pseudonym[:30]:30s} | Sharpe: {sharpe:5.2f} | WR: {win_rate:5.1f}% | PnL: ${total_pnl:>10,.0f}")
        else:
            skipped_count += 1

        # Commit every 100 whales
        if i % 100 == 0:
            session.commit()

        # Rate limiting - be nice to the API
        time.sleep(0.1)

    except requests.exceptions.Timeout:
        failed_count += 1
        if failed_count <= 5:
            print(f"  ⏱️  [{i}] Timeout fetching {pseudonym}")
        continue
    except Exception as e:
        failed_count += 1
        if failed_count <= 5:
            print(f"  ❌ [{i}] Error with {pseudonym}: {str(e)[:50]}")
        continue

# Final commit
session.commit()

print()
print("=" * 80)
print("WHALE METRICS UPDATE COMPLETE")
print("=" * 80)
print(f"  Total whales:     {len(whales)}")
print(f"  Updated:          {updated_count}")
print(f"  Skipped (no changes): {skipped_count}")
print(f"  Failed:           {failed_count}")
print()

# Show statistics on updated whales
print("📊 Analyzing updated metrics...")
whales_with_sharpe = session.query(Whale).filter(
    Whale.sharpe_ratio.isnot(None),
    Whale.sharpe_ratio > 0
).count()

whales_with_winrate = session.query(Whale).filter(
    Whale.win_rate.isnot(None),
    Whale.win_rate > 0
).count()

elite_whales = session.query(Whale).filter(
    Whale.sharpe_ratio > 1.5,
    Whale.win_rate > 55,
    Whale.total_pnl > 10000,
    Whale.total_volume > 50000
).count()

print(f"  Whales with Sharpe ratio: {whales_with_sharpe}")
print(f"  Whales with Win Rate:     {whales_with_winrate}")
print(f"  Elite whales (S>1.5, WR>55%, PnL>$10k, Vol>$50k): {elite_whales}")
print()

session.close()

if updated_count > 0:
    print("✅ Metrics updated successfully!")
    print("   You can now run rank_existing_whales.py to calculate quality scores")
else:
    print("⚠️  No whales were updated")
    print("   This could mean:")
    print("   - All whales already have current data")
    print("   - API is not returning expected data")
    print("   - Network/authentication issues")

print()
print("=" * 80)
