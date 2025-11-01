#!/usr/bin/env python3
"""
Analyze what historical trade data we have available for real backtesting.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from libs.common.models import Trade

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)

print('=' * 80)
print('HISTORICAL TRADE DATA ANALYSIS')
print('=' * 80)
print()

with engine.connect() as conn:
    # Check date range of all trades
    result = conn.execute(text('''
        SELECT
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest,
            COUNT(*) as total_trades,
            COUNT(DISTINCT market_id) as unique_markets,
            COUNT(DISTINCT whale_address) as unique_whales
        FROM trades
        WHERE is_whale_trade = true
    ''')).fetchone()

    if result and result[0]:
        earliest = result[0]
        latest = result[1]
        total = result[2]
        markets = result[3]
        whales = result[4]

        date_range = latest - earliest

        print(f'📊 TRADE DATA SUMMARY')
        print('-' * 80)
        print(f'Earliest trade: {earliest}')
        print(f'Latest trade:   {latest}')
        print(f'Date range:     {date_range}')
        print(f'Total trades:   {total:,}')
        print(f'Unique markets: {markets:,}')
        print(f'Unique whales:  {whales:,}')
        print()

        # Check if we have 60+ days of data
        if date_range.days >= 60:
            print(f'✅ We have {date_range.days} days of data - sufficient for 60-day backtest')
        else:
            print(f'⚠️  We only have {date_range.days} days of data - need to fetch more historical trades')
        print()

        # Check trades per day distribution
        print('📈 TEMPORAL DISTRIBUTION')
        print('-' * 80)
        result = conn.execute(text('''
            SELECT
                DATE(timestamp) as trade_date,
                COUNT(*) as trades_count
            FROM trades
            WHERE is_whale_trade = true
            GROUP BY DATE(timestamp)
            ORDER BY trade_date DESC
            LIMIT 10
        ''')).fetchall()

        print('Recent 10 days:')
        for row in result:
            print(f'  {row[0]}: {row[1]:,} trades')
        print()

        # Check if we have market outcome/resolution data
        print('🎯 MARKET RESOLUTION DATA')
        print('-' * 80)

        # Check what columns we have in trades table
        result = conn.execute(text('''
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'trades'
            AND column_name LIKE '%outcome%' OR column_name LIKE '%result%' OR column_name LIKE '%resolved%'
        ''')).fetchall()

        if result:
            print('Resolution columns found:')
            for col in result:
                print(f'  - {col[0]} ({col[1]})')
        else:
            print('❌ No resolution/outcome columns found in trades table')
            print('   We need to fetch market resolution data from Polymarket API')
        print()

        # Check markets table if it exists
        result = conn.execute(text('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'markets'
            )
        ''')).fetchone()

        if result[0]:
            print('📋 MARKETS TABLE FOUND')
            print('-' * 80)

            # Check markets columns
            result = conn.execute(text('''
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'markets'
                ORDER BY ordinal_position
            ''')).fetchall()

            print('Markets table columns:')
            for col in result:
                print(f'  - {col[0]} ({col[1]})')
            print()

            # Check how many markets we have data for
            result = conn.execute(text('''
                SELECT COUNT(*) as total_markets,
                       COUNT(CASE WHEN closed = true THEN 1 END) as closed_markets
                FROM markets
            ''')).fetchone()

            if result:
                print(f'Total markets: {result[0]:,}')
                print(f'Closed markets: {result[1]:,}')
                print()
        else:
            print('⚠️  No markets table found')
            print()
    else:
        print('❌ No whale trades found in database')
        print()

print('=' * 80)
print('RECOMMENDATION')
print('=' * 80)
print()
print('To build a real 60-day backtest with actual market resolutions:')
print()
print('1. Fetch historical whale trades going back 60+ days from Polymarket API')
print('2. For each unique market, fetch the market resolution/outcome')
print('3. Store market resolutions in a markets table or add outcome column to trades')
print('4. Randomly sample trades from 60-day window (not just recent)')
print('5. Calculate P&L based on actual market outcomes, not probabilities')
print()
