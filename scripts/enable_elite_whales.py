#!/usr/bin/env python3
"""
Enable Elite Whales for Copy Trading
Focuses on the 40+ whales that already have Sharpe > 1.5 and Win Rate > 55%
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale
from datetime import datetime

print('=' * 80)
print('🎯 ENABLING ELITE WHALES FOR COPY TRADING')
print('=' * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get elite whales (Sharpe > 1.5, Win Rate > 55%)
print('📊 Finding elite whales...')
elite_whales = session.query(Whale).filter(
    Whale.sharpe_ratio > 1.5,
    Whale.win_rate > 55,
    Whale.total_pnl > 0  # Must be profitable
).order_by(Whale.sharpe_ratio.desc()).all()

print(f'Found {len(elite_whales)} elite whales meeting criteria')
print()

if not elite_whales:
    print('⚠️  No elite whales found with Sharpe > 1.5 and Win Rate > 55%')
    sys.exit(0)

# Display elite whales
print('=' * 80)
print('ELITE WHALES TO BE ENABLED')
print('=' * 80)
print(f'{"#":<4} {"Pseudonym":<25} {"Sharpe":<8} {"WinRate":<8} {"PnL":<15}')
print('-' * 80)

for i, whale in enumerate(elite_whales, 1):
    pseudo = (whale.pseudonym or whale.address[:10])[:24]
    sharpe = whale.sharpe_ratio or 0
    wr = whale.win_rate or 0
    pnl = whale.total_pnl or 0
    print(f'{i:<4} {pseudo:<25} {sharpe:<8.2f} {wr:<8.1f}% ${pnl:>13,.0f}')

print()

# Update each elite whale
print('🔧 Updating elite whales...')
print('-' * 80)

enabled_count = 0
updated_count = 0

for whale in elite_whales:
    # Calculate quality score
    # Formula: (Sharpe * 20) + (Win Rate * 0.5)
    # This gives Sharpe more weight
    sharpe_val = float(whale.sharpe_ratio) if whale.sharpe_ratio else 0
    wr_val = float(whale.win_rate) if whale.win_rate else 0
    quality_score = min(100, (sharpe_val * 20) + (wr_val * 0.5))

    # Set tier based on quality score
    if quality_score >= 80:
        tier = 'MEGA'
    elif quality_score >= 70:
        tier = 'HIGH'
    elif quality_score >= 60:
        tier = 'MEDIUM'
    else:
        tier = 'LOW'

    # Update whale
    whale.quality_score = quality_score
    whale.tier = tier
    whale.is_active = True

    # Enable copying for high-quality whales (score >= 60)
    if quality_score >= 60 and not whale.is_copying_enabled:
        whale.is_copying_enabled = True
        enabled_count += 1

    whale.updated_at = datetime.utcnow()
    updated_count += 1

    pseudo = (whale.pseudonym or whale.address[:10])[:24]
    print(f'   {pseudo:<25} | Quality: {quality_score:5.1f} | Tier: {tier:<6} | Copy: {"✅ ENABLED" if whale.is_copying_enabled else "⚠️  Disabled"}')

# Commit changes
session.commit()

print()
print('=' * 80)
print('✅ ELITE WHALES UPDATE COMPLETE')
print('=' * 80)
print(f'   Total elite whales: {len(elite_whales)}')
print(f'   Updated: {updated_count}')
print(f'   Newly enabled for copying: {enabled_count}')
print()

# Show tier distribution
tier_counts = {}
for whale in elite_whales:
    tier = whale.tier or 'NONE'
    tier_counts[tier] = tier_counts.get(tier, 0) + 1

print('TIER DISTRIBUTION:')
for tier in ['MEGA', 'HIGH', 'MEDIUM', 'LOW']:
    count = tier_counts.get(tier, 0)
    print(f'   {tier:<8}: {count:3d} whales')

print()

# Show average metrics
if elite_whales:
    avg_sharpe = sum(w.sharpe_ratio for w in elite_whales) / len(elite_whales)
    avg_wr = sum(w.win_rate for w in elite_whales) / len(elite_whales)
    avg_pnl = sum(w.total_pnl for w in elite_whales) / len(elite_whales)
    avg_quality = sum(w.quality_score for w in elite_whales) / len(elite_whales)

    print('ELITE WHALE AVERAGES:')
    print(f'   Sharpe Ratio:  {avg_sharpe:.2f}')
    print(f'   Win Rate:      {avg_wr:.1f}%')
    print(f'   Total PnL:     ${avg_pnl:,.0f}')
    print(f'   Quality Score: {avg_quality:.1f}')

print()
print('=' * 80)
print('🚀 READY FOR BACKTESTING!')
print('=' * 80)

session.close()
