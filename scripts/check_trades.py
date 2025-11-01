#!/usr/bin/env python3
"""Quick script to check trades in database"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Trade

db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Check whale trades
whale_trades = session.query(Trade).filter(Trade.is_whale_trade == True).count()
print(f'Whale trades in database: {whale_trades}')

# Check our trades
our_trades = session.query(Trade).filter(Trade.is_whale_trade == False).count()
print(f'Our copy trades in database: {our_trades}')

# Get recent trades
recent = session.query(Trade).order_by(Trade.timestamp.desc()).limit(5).all()
print(f'\nMost recent {len(recent)} trades:')
for t in recent:
    whale_type = "WHALE" if t.is_whale_trade else "OUR  "
    print(f'  [{whale_type}] {t.timestamp} - {t.side:4s} ${t.amount:8.2f} - {t.market_id[:20]}')

session.close()
