#!/usr/bin/env python3
"""
Rank Existing Whales by Quality Metrics
Find the best performers based on Sharpe, Win Rate, PnL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from datetime import datetime

print("=" * 80)
print("🎯 RANKING EXISTING WHALES - FINDING THE BEST")
print("=" * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get all whales with metrics
print("📊 Analyzing all whales in database...")
whales = session.query(Whale).filter(
    Whale.total_pnl.isnot(None),
    Whale.total_volume.isnot(None)
).all()

print(f"Found {len(whales)} whales with performance data")
print()

# Calculate composite quality scores
whale_scores = []

for whale in whales:
    try:
        # Extract metrics (handle None values)
        sharpe = float(whale.sharpe_ratio or 0)
        win_rate = float(whale.win_rate or 0)
        total_pnl = float(whale.total_pnl or 0)
        total_volume = float(whale.total_volume or 0)
        markets_traded = int(whale.markets_traded or 0)
        total_trades = int(whale.total_trades or 0)

        # Calculate activity score (0-100)
        # Based on volume and number of trades
        if total_volume > 0 and total_trades > 0:
            volume_score = min(100, (total_volume / 10000) * 10)  # $100k = 100 points
            trade_score = min(100, (total_trades / 100) * 100)    # 100 trades = 100 points
            activity_score = (volume_score + trade_score) / 2
        else:
            activity_score = 0

        # Calculate profitability score (0-100)
        if total_pnl > 0:
            profit_score = min(100, (total_pnl / 10000) * 50)  # $10k = 50 points
        else:
            profit_score = max(0, 50 + (total_pnl / 1000) * 5)  # Negative PnL reduces score

        # Calculate consistency score (0-100)
        # Based on Sharpe ratio and win rate
        sharpe_score = min(100, sharpe * 33.33) if sharpe > 0 else 0  # Sharpe of 3 = 100 points
        win_rate_score = win_rate                                      # Already 0-100

        consistency_score = (sharpe_score + win_rate_score) / 2

        # Composite quality score (weighted average)
        composite_score = (
            consistency_score * 0.4 +  # 40% weight on consistency
            profit_score * 0.3 +        # 30% weight on profitability
            activity_score * 0.3        # 30% weight on activity
        )

        whale_scores.append({
            'address': whale.address,
            'pseudonym': whale.pseudonym or whale.address[:10],
            'sharpe': sharpe,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_volume': total_volume,
            'markets_traded': markets_traded,
            'total_trades': total_trades,
            'composite_score': composite_score,
            'consistency_score': consistency_score,
            'profit_score': profit_score,
            'activity_score': activity_score,
            'whale_obj': whale
        })
    except Exception as e:
        continue

# Sort by composite score
whale_scores.sort(key=lambda x: x['composite_score'], reverse=True)

print("=" * 80)
print("TOP 50 WHALES BY COMPOSITE QUALITY SCORE")
print("=" * 80)
print()

# Display top 50
print(f"{'Rank':<6} {'Pseudonym':<25} {'Score':<7} {'Sharpe':<8} {'WinRate':<8} {'PnL':<12} {'Trades':<8}")
print("-" * 95)

for i, whale in enumerate(whale_scores[:50], 1):
    print(f"{i:<6} {whale['pseudonym'][:24]:<25} "
          f"{whale['composite_score']:<7.1f} "
          f"{whale['sharpe']:<8.2f} "
          f"{whale['win_rate']:<8.1f}% "
          f"${whale['total_pnl']:>10,.0f} "
          f"{whale['total_trades']:<8}")

print()
print("=" * 80)

# Identify elite whales (top 10%)
elite_count = max(10, len(whale_scores) // 10)
elite_whales = whale_scores[:elite_count]

print(f"🏆 ELITE WHALES (Top {elite_count})")
print("=" * 80)
print()

# Update database - mark elite whales and enable copying
updated_count = 0
enabled_count = 0

for whale_data in elite_whales:
    whale = whale_data['whale_obj']

    # Update quality score
    whale.quality_score = whale_data['composite_score']

    # Set tier based on score
    if whale_data['composite_score'] >= 80:
        whale.tier = 'MEGA'
    elif whale_data['composite_score'] >= 60:
        whale.tier = 'HIGH'
    elif whale_data['composite_score'] >= 40:
        whale.tier = 'MEDIUM'
    else:
        whale.tier = 'LOW'

    # Enable copying for high-quality whales
    if whale_data['composite_score'] >= 60 and not whale.is_copying_enabled:
        whale.is_copying_enabled = True
        enabled_count += 1

    whale.updated_at = datetime.utcnow()
    updated_count += 1

session.commit()

print(f"✅ Updated {updated_count} elite whales")
print(f"✅ Enabled copying for {enabled_count} whales")
print()

# Show distribution
mega = len([w for w in whale_scores if w['composite_score'] >= 80])
high = len([w for w in whale_scores if 60 <= w['composite_score'] < 80])
medium = len([w for w in whale_scores if 40 <= w['composite_score'] < 60])
low = len([w for w in whale_scores if w['composite_score'] < 40])

print("TIER DISTRIBUTION:")
print(f"  MEGA (≥80):    {mega:4d} whales")
print(f"  HIGH (60-79):  {high:4d} whales")
print(f"  MEDIUM (40-59): {medium:4d} whales")
print(f"  LOW (<40):     {low:4d} whales")
print()

# Show averages for top 50
if len(elite_whales) > 0:
    avg_sharpe = sum(w['sharpe'] for w in elite_whales) / len(elite_whales)
    avg_wr = sum(w['win_rate'] for w in elite_whales) / len(elite_whales)
    avg_pnl = sum(w['total_pnl'] for w in elite_whales) / len(elite_whales)
    avg_trades = sum(w['total_trades'] for w in elite_whales) / len(elite_whales)

    print("ELITE WHALE AVERAGES:")
    print(f"  Sharpe Ratio:  {avg_sharpe:.2f}")
    print(f"  Win Rate:      {avg_wr:.1f}%")
    print(f"  Total PnL:     ${avg_pnl:,.0f}")
    print(f"  Total Trades:  {avg_trades:.0f}")

print()
print("=" * 80)
print("RECOMMENDATION: Start with TOP 10 whales for copy trading")
print("=" * 80)

session.close()
