#!/usr/bin/env python3
"""
Fetch whales directly from Polymarket's leaderboard.
This is the most reliable way to get whales with public profiles and real data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from datetime import datetime

def fetch_leaderboard():
    """Fetch top traders from Polymarket leaderboard."""
    print("Fetching Polymarket leaderboard...")

    # Polymarket leaderboard endpoint
    url = "https://gamma-api.polymarket.com/leaderboard"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return None

def calculate_quality_score(whale_data):
    """Calculate quality score from leaderboard data."""
    pnl = float(whale_data.get('pnl', 0) or 0)
    volume = float(whale_data.get('volume', 0) or 0)
    trades = int(whale_data.get('trades', 0) or 0)
    markets = int(whale_data.get('markets', 0) or 0)

    # ROI
    roi = (pnl / volume * 100) if volume > 0 else 0

    # Score components (0-100 each)
    pnl_score = min(100, (abs(pnl) / 1000) ** 0.5 * 10) if pnl > 0 else 0
    roi_score = min(100, abs(roi) * 2)
    volume_score = min(100, (volume / 10000) ** 0.5 * 10)
    trades_score = min(100, (trades / 10) ** 0.5 * 10)
    markets_score = min(100, markets)

    # Weighted average
    quality_score = (
        pnl_score * 0.30 +
        roi_score * 0.30 +
        volume_score * 0.15 +
        trades_score * 0.15 +
        markets_score * 0.10
    )

    return round(quality_score, 2)

def categorize_tier(pnl):
    """Categorize whale into tier based on PnL."""
    if pnl >= 100000:
        return "MEGA"
    elif pnl >= 10000:
        return "LARGE"
    elif pnl >= 1000:
        return "MEDIUM"
    else:
        return "SMALL"

def main():
    print("=" * 80)
    print("POLYMARKET LEADERBOARD WHALE IMPORT")
    print("=" * 80)
    print()

    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Fetch leaderboard
    leaderboard = fetch_leaderboard()

    if not leaderboard:
        print("Failed to fetch leaderboard")
        return

    print(f"Found {len(leaderboard)} traders on leaderboard")
    print()

    # Import whales
    imported = 0
    updated = 0
    enabled = 0

    for trader in leaderboard:
        address = trader.get('address')
        if not address:
            continue

        # Check if whale exists
        whale = session.query(Whale).filter(Whale.address == address).first()

        # Extract data
        pnl = float(trader.get('pnl', 0) or 0)
        volume = float(trader.get('volume', 0) or 0)
        trades = int(trader.get('trades', 0) or 0)
        markets = int(trader.get('markets', 0) or 0)
        pseudonym = trader.get('username') or trader.get('name')

        # Calculate quality
        quality_score = calculate_quality_score(trader)
        tier = categorize_tier(pnl)

        # Quality thresholds
        MIN_QUALITY_SCORE = 30
        MIN_PNL = 1000
        MIN_TRADES = 10

        should_enable = (
            quality_score >= MIN_QUALITY_SCORE and
            pnl >= MIN_PNL and
            trades >= MIN_TRADES and
            volume > 0
        )

        if whale:
            # Update existing
            whale.pseudonym = pseudonym
            whale.total_pnl = pnl
            whale.total_volume = volume
            whale.total_trades = trades
            whale.quality_score = quality_score
            whale.tier = tier
            whale.last_active = datetime.utcnow()
            whale.is_active = True
            whale.is_copying_enabled = should_enable
            whale.is_blacklisted = not should_enable
            if not should_enable:
                whale.blacklist_reason = f"Quality score too low ({quality_score:.1f})"
            else:
                whale.blacklist_reason = None
            updated += 1
        else:
            # Create new
            whale = Whale(
                address=address,
                pseudonym=pseudonym,
                total_pnl=pnl,
                total_volume=volume,
                total_trades=trades,
                quality_score=quality_score,
                tier=tier,
                last_active=datetime.utcnow(),
                is_active=True,
                is_copying_enabled=should_enable,
                is_blacklisted=not should_enable,
                blacklist_reason=f"Quality score too low ({quality_score:.1f})" if not should_enable else None
            )
            session.add(whale)
            imported += 1

        if should_enable:
            enabled += 1
            print(f"✓ {pseudonym or address[:10]}: PnL ${pnl:,.0f}, Quality {quality_score:.1f}, Tier {tier}")

    # Commit
    session.commit()

    print()
    print("=" * 80)
    print("IMPORT COMPLETE")
    print("=" * 80)
    print(f"Imported: {imported} new whales")
    print(f"Updated: {updated} existing whales")
    print(f"Enabled for copying: {enabled} whales")
    print()

    # Show top whales
    print("Top 10 whales by quality score:")
    print()
    top_whales = session.query(Whale).filter(
        Whale.is_copying_enabled == True
    ).order_by(Whale.quality_score.desc()).limit(10).all()

    for i, w in enumerate(top_whales, 1):
        print(f"{i:2d}. {w.pseudonym or w.address[:10]:20s} | "
              f"Score: {w.quality_score:5.1f} | "
              f"Tier: {w.tier:6s} | "
              f"PnL: ${w.total_pnl:>12,.0f}")

    session.close()

if __name__ == "__main__":
    main()
