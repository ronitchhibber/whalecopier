#!/usr/bin/env python3
"""
Filter whales based on:
1. Public availability (has active Polymarket profile)
2. Quality metrics (profitability, win rate, consistency)

This script will:
- Check which whales have publicly available profiles
- Score whales based on multiple quality factors
- Disable copy trading for low-quality or unavailable whales
- Enable copy trading for high-quality, publicly available whales
"""

import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale


def get_whale_profile(address: str) -> dict:
    """
    Fetch whale profile from Polymarket Gamma API.

    Returns:
        dict with profile data or None if not available
    """
    try:
        url = f"https://gamma-api.polymarket.com/profile/{address}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"Error fetching {address[:10]}: {e}")
        return None


def calculate_quality_score(profile: dict) -> float:
    """
    Calculate a quality score (0-100) based on multiple factors.

    Factors:
    - PnL (40%): Higher is better
    - Win Rate (20%): Higher is better
    - Volume (15%): Shows activity level
    - Total Trades (15%): Shows experience
    - Markets Traded (10%): Shows diversification
    """
    pnl = float(profile.get('pnl', 0) or 0)
    volume = float(profile.get('totalVolume', 0) or 0)
    trades = int(profile.get('totalTrades', 0) or 0)
    markets = int(profile.get('marketsTraded', 0) or 0)

    # Calculate ROI (PnL / Volume)
    roi = (pnl / volume * 100) if volume > 0 else 0

    # Score components (0-100 each)

    # PnL score: $100K+ = 100, logarithmic scale
    if pnl > 0:
        pnl_score = min(100, (pnl / 1000) ** 0.5 * 10)
    else:
        pnl_score = 0

    # ROI score: 50%+ ROI = 100
    roi_score = min(100, abs(roi) * 2)

    # Volume score: $1M+ = 100
    volume_score = min(100, (volume / 10000) ** 0.5 * 10)

    # Trades score: 1000+ trades = 100
    trades_score = min(100, (trades / 10) ** 0.5 * 10)

    # Markets score: 100+ markets = 100
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


def categorize_tier(pnl: float) -> str:
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
    """Main execution."""
    print("=" * 80)
    print("🔍 WHALE QUALITY FILTER")
    print("=" * 80)
    print()

    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get all whales
    whales = session.query(Whale).all()
    print(f"📊 Checking {len(whales)} whales...")
    print()

    # Quality thresholds
    MIN_QUALITY_SCORE = 30  # Minimum quality score to enable copying
    MIN_PNL = 1000  # Minimum $1K profit

    # Results tracking
    results = {
        'publicly_available': 0,
        'not_available': 0,
        'high_quality': 0,
        'medium_quality': 0,
        'low_quality': 0,
        'enabled_for_copy': 0,
        'disabled_from_copy': 0,
        'errors': 0
    }

    high_quality_whales = []

    for i, whale in enumerate(whales, 1):
        if i % 100 == 0:
            print(f"Progress: {i}/{len(whales)} ({i/len(whales)*100:.1f}%)")

        # Fetch profile
        profile = get_whale_profile(whale.address)

        if not profile:
            # Profile not available
            results['not_available'] += 1

            # Disable copy trading if currently enabled
            if whale.is_copying_enabled:
                whale.is_copying_enabled = False
                whale.blacklist_reason = "Profile not publicly available"
                results['disabled_from_copy'] += 1

            time.sleep(0.1)  # Rate limiting
            continue

        # Profile is available
        results['publicly_available'] += 1

        # Extract metrics
        pnl = float(profile.get('pnl', 0) or 0)
        volume = float(profile.get('totalVolume', 0) or 0)
        trades = int(profile.get('totalTrades', 0) or 0)
        markets = int(profile.get('marketsTraded', 0) or 0)

        # Calculate quality score
        quality_score = calculate_quality_score(profile)

        # Update whale record
        whale.total_pnl = pnl
        whale.total_volume = volume
        whale.total_trades = trades
        whale.quality_score = quality_score
        whale.tier = categorize_tier(pnl)
        whale.last_active = datetime.utcnow()
        whale.is_active = True

        # Categorize quality
        if quality_score >= 60:
            results['high_quality'] += 1
            quality_category = "HIGH"
        elif quality_score >= 30:
            results['medium_quality'] += 1
            quality_category = "MEDIUM"
        else:
            results['low_quality'] += 1
            quality_category = "LOW"

        # Check last activity (must be within last 30 days)
        last_activity = profile.get('lastTradeDate')
        is_recently_active = False

        if last_activity:
            try:
                from dateutil import parser
                last_trade_date = parser.parse(last_activity)
                days_since_trade = (datetime.utcnow() - last_trade_date.replace(tzinfo=None)).days
                is_recently_active = days_since_trade <= 30
            except:
                # If can't parse date, check if they have trades
                is_recently_active = trades > 0

        # Decide if should enable copy trading
        should_enable = (
            quality_score >= MIN_QUALITY_SCORE and
            pnl >= MIN_PNL and
            trades >= 10 and
            volume > 0 and
            is_recently_active  # Must have traded in last 30 days
        )

        if should_enable and not whale.is_copying_enabled:
            whale.is_copying_enabled = True
            whale.is_blacklisted = False
            whale.blacklist_reason = None
            results['enabled_for_copy'] += 1

            # Track high quality whales
            high_quality_whales.append({
                'address': whale.address,
                'pseudonym': whale.pseudonym,
                'pnl': pnl,
                'quality_score': quality_score,
                'tier': whale.tier,
                'trades': trades,
                'volume': volume
            })

        elif not should_enable and whale.is_copying_enabled:
            whale.is_copying_enabled = False
            whale.blacklist_reason = f"Quality score too low ({quality_score:.1f})"
            results['disabled_from_copy'] += 1

        time.sleep(0.1)  # Rate limiting

    # Commit all changes
    session.commit()

    # Print results
    print()
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print()
    print(f"Public Availability:")
    print(f"  ✅ Publicly available:  {results['publicly_available']:,}")
    print(f"  ❌ Not available:       {results['not_available']:,}")
    print()
    print(f"Quality Distribution (of available whales):")
    print(f"  🌟 High quality (60+):  {results['high_quality']:,}")
    print(f"  ⭐ Medium quality (30-60): {results['medium_quality']:,}")
    print(f"  💀 Low quality (<30):   {results['low_quality']:,}")
    print()
    print(f"Copy Trading Status:")
    print(f"  🟢 Enabled:             {results['enabled_for_copy']:,}")
    print(f"  🔴 Disabled:            {results['disabled_from_copy']:,}")
    print()

    # Show top whales
    if high_quality_whales:
        print("=" * 80)
        print(f"🏆 TOP QUALITY WHALES (Enabled for Copy Trading)")
        print("=" * 80)
        print()

        # Sort by quality score
        high_quality_whales.sort(key=lambda x: x['quality_score'], reverse=True)

        for i, w in enumerate(high_quality_whales[:20], 1):
            pseudonym = w['pseudonym'] or w['address'][:10]
            print(f"{i:2d}. {pseudonym:20s} | "
                  f"Score: {w['quality_score']:5.1f} | "
                  f"Tier: {w['tier']:6s} | "
                  f"PnL: ${w['pnl']:>12,.0f} | "
                  f"Trades: {w['trades']:>6,}")

        if len(high_quality_whales) > 20:
            print(f"\n   ... and {len(high_quality_whales) - 20} more")

    print()
    print("=" * 80)
    print(f"✅ Quality filtering complete!")
    print(f"   {len(high_quality_whales)} whales enabled for copy trading")
    print("=" * 80)
    print()

    session.close()


if __name__ == "__main__":
    main()
