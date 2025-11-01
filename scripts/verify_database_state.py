#!/usr/bin/env python3
"""
Verify Database State - Check whale addresses, schema, and data availability
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade

print('=' * 80)
print('DATABASE STATE VERIFICATION')
print('=' * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Check whale addresses
print('1. WHALE ADDRESS VERIFICATION')
print('-' * 80)
sample_whales = session.query(Whale).limit(5).all()
for whale in sample_whales:
    print(f'   Address: {whale.address} (length: {len(whale.address)} chars)')
    print(f'   Pseudonym: {whale.pseudonym or "None"}')
    sharpe = whale.sharpe_ratio or 0
    wr = whale.win_rate or 0
    print(f'   Sharpe: {sharpe:.2f}, Win Rate: {wr:.1f}%')
    print()

# Check schema with raw SQL
print('2. DATABASE SCHEMA CHECK')
print('-' * 80)
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'whales' AND column_name = 'address'
    '''))
    for row in result:
        print(f'   whales.address: {row[1]}({row[2]})')

    result = conn.execute(text('''
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'trades' AND column_name = 'token_id'
    '''))
    for row in result:
        print(f'   trades.token_id: {row[1]}({row[2]})')

print()

# Count whales by data availability
print('3. WHALE DATA AVAILABILITY')
print('-' * 80)
total_whales = session.query(Whale).count()
active_whales = session.query(Whale).filter(Whale.is_active == True).count()
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
    Whale.win_rate > 55
).count()

print(f'   Total whales: {total_whales}')
print(f'   Active whales: {active_whales}')
print(f'   Whales with Sharpe ratio: {whales_with_sharpe}')
print(f'   Whales with Win rate: {whales_with_winrate}')
print(f'   Elite whales (Sharpe>1.5, WR>55%): {elite_whales}')
print()

# Check trades
print('4. TRADE DATA AVAILABILITY')
print('-' * 80)
total_trades = session.query(Trade).count()
whale_trades = session.query(Trade).filter(Trade.is_whale_trade == True).count()

print(f'   Total trades: {total_trades}')
print(f'   Whale trades: {whale_trades}')
print()

# Top whales by quality
print('5. TOP 10 WHALES BY SHARPE RATIO')
print('-' * 80)
top_whales = session.query(Whale).filter(
    Whale.sharpe_ratio.isnot(None)
).order_by(Whale.sharpe_ratio.desc()).limit(10).all()

if top_whales:
    print(f'   {"Pseudonym":<25} {"Sharpe":<8} {"WinRate":<8} {"PnL":<12}')
    print('   ' + '-' * 60)
    for whale in top_whales:
        pseudo = (whale.pseudonym or whale.address[:10])[:24]
        sharpe = whale.sharpe_ratio or 0
        wr = whale.win_rate or 0
        pnl = whale.total_pnl or 0
        print(f'   {pseudo:<25} {sharpe:<8.2f} {wr:<8.1f}% ${pnl:>10,.0f}')
else:
    print('   No whales with Sharpe ratio data found')

print()
print('=' * 80)
print('VERIFICATION COMPLETE')
print('=' * 80)

session.close()
