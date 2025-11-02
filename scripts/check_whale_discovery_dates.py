#!/usr/bin/env python3
"""
Check when whales were first discovered - maybe we can pull their historical stats.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

print('=' * 80)
print('WHALE HISTORICAL STATS')
print('=' * 80)
print()

# Get elite whales
elite_whales = session.query(Whale).filter(
    Whale.is_copying_enabled == True
).order_by(Whale.quality_score.desc()).limit(10).all()

print(f'Top 10 Elite Whales:')
print('-' * 80)

for i, whale in enumerate(elite_whales, 1):
    pseudonym = whale.pseudonym or whale.address[:10]
    print(f'{i}. {pseudonym}')
    print(f'   Quality: {whale.quality_score:.1f}')
    print(f'   Total P&L: ${whale.total_pnl:.2f}' if whale.total_pnl else '   Total P&L: N/A')
    print(f'   Total Trades: {whale.total_trades}' if whale.total_trades else '   Total Trades: N/A')
    print(f'   Total Volume: ${whale.total_volume:.2f}' if whale.total_volume else '   Total Volume: N/A')
    print(f'   Win Rate: {whale.win_rate:.1f}%' if whale.win_rate else '   Win Rate: N/A')
    print(f'   Sharpe Ratio: {whale.sharpe_ratio:.2f}' if whale.sharpe_ratio else '   Sharpe Ratio: N/A')
    print()

session.close()

print()
print('NOTE: These total stats come from Polymarket\'s aggregate data.')
print('They represent the whale\'s ENTIRE trading history, potentially months/years.')
print('This is what the backtest uses to estimate avg P&L per trade.')
