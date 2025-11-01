#!/usr/bin/env python3
"""Quick check of what data we have for real backtesting."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)

print('=' * 80)
print('DATA AVAILABILITY CHECK')
print('=' * 80)
print()

with engine.connect() as conn:
    # Check trades
    result = conn.execute(text('''
        SELECT
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest,
            COUNT(*) as total,
            COUNT(DISTINCT market_id) as markets
        FROM trades
        WHERE is_whale_trade = true
    ''')).fetchone()

    if result and result[0]:
        print(f'📊 WHALE TRADES')
        print(f'   Date range: {result[0]} to {result[1]}')
        print(f'   Duration: {result[1] - result[0]}')
        print(f'   Total trades: {result[2]:,}')
        print(f'   Unique markets: {result[3]:,}')
        print()

    # Check if markets table exists and has resolution data
    result = conn.execute(text('''
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'markets'
        )
    ''')).fetchone()

    if result[0]:
        result = conn.execute(text('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN closed = true THEN 1 END) as closed,
                COUNT(CASE WHEN outcome IS NOT NULL THEN 1 END) as resolved
            FROM markets
        ''')).fetchone()

        print(f'📋 MARKETS')
        print(f'   Total markets: {result[0]:,}')
        print(f'   Closed markets: {result[1]:,}')
        print(f'   Resolved markets: {result[2]:,}')
        print()

        if result[2] > 0:
            print(f'✅ We have {result[2]:,} resolved markets - can use real outcomes!')
        else:
            print(f'❌ No market resolutions found - need to fetch from API')
    else:
        print('⚠️  No markets table found')

    print()
