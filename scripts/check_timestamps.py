#!/usr/bin/env python3
"""
Check timestamps in trades table to diagnose timestamp accuracy issue.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Trade
from datetime import datetime

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

print('=' * 80)
print('TIMESTAMP ANALYSIS FOR WHALE TRADES')
print('=' * 80)
print()

# Get all whale trades
whale_trades = session.query(Trade).filter(
    Trade.is_whale_trade == True
).order_by(Trade.timestamp.desc()).all()

print(f'Total whale trades: {len(whale_trades)}')
print()

if len(whale_trades) > 0:
    # Show timestamp range
    min_ts = min(t.timestamp for t in whale_trades)
    max_ts = max(t.timestamp for t in whale_trades)

    print(f'Earliest trade: {min_ts}')
    print(f'Latest trade:   {max_ts}')
    print(f'Time span:      {max_ts - min_ts}')
    print()

    # Show first 20 trades with timestamps
    print('First 20 trades:')
    print('-' * 80)
    for i, trade in enumerate(whale_trades[:20], 1):
        print(f'{i:2d}. {trade.timestamp} | {trade.trader_address[:10]} | ${trade.amount:.2f}')

    print()

    # Check if all timestamps are the same
    unique_timestamps = set(t.timestamp for t in whale_trades)
    print(f'Unique timestamps: {len(unique_timestamps)}')

    if len(unique_timestamps) <= 5:
        print()
        print('All unique timestamps:')
        for ts in sorted(unique_timestamps):
            count = sum(1 for t in whale_trades if t.timestamp == ts)
            print(f'  {ts}: {count} trades')

session.close()
