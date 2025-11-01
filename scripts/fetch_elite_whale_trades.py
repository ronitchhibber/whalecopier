#!/usr/bin/env python3
"""
Fetch recent trades for all elite whales to populate the Live Trades view.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade
import requests
from datetime import datetime
import time

print('=' * 80)
print('FETCHING TRADES FOR ELITE WHALES')
print('=' * 80)
print()

# Connect to database
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

# Get elite whales (enabled for copying)
print('Finding elite whales...')
elite_whales = session.query(Whale).filter(
    Whale.is_copying_enabled == True
).order_by(Whale.quality_score.desc()).all()

print(f'Found {len(elite_whales)} elite whales enabled for copying')
print()

total_trades_added = 0
total_whales_processed = 0

for i, whale in enumerate(elite_whales, 1):
    address = whale.address
    pseudonym = whale.pseudonym or address[:10]

    print(f'[{i}/{len(elite_whales)}] Fetching trades for {pseudonym} (Q:{whale.quality_score:.1f})...')

    try:
        # Fetch recent trades from Polymarket Data API
        url = f'https://data-api.polymarket.com/trades?trader={address}&limit=50'
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            print(f'  ⚠️  API returned {response.status_code}')
            continue

        trades_data = response.json()

        if not trades_data:
            print(f'  No recent trades found')
            continue

        trades_added = 0

        for trade in trades_data:
            try:
                # Create unique trade ID from transaction hash + log index
                trade_id = trade.get('transactionHash', '') or f"trade-{int(time.time())}-{trade.get('id')}"

                # Check if trade already exists
                existing = session.query(Trade).filter(Trade.trade_id == trade_id).first()
                if existing:
                    continue

                # Parse timestamp (API returns seconds, not milliseconds)
                timestamp_seconds = trade.get('timestamp')
                if timestamp_seconds:
                    timestamp = datetime.fromtimestamp(int(timestamp_seconds))
                else:
                    timestamp = datetime.utcnow()

                # Create trade record
                new_trade = Trade(
                    trade_id=trade_id,
                    trader_address=address,
                    market_id=trade.get('market', '')[:66],
                    token_id=trade.get('tokenID', '')[:78] or trade.get('market', '')[:78],
                    side=trade.get('side', '').upper(),
                    size=float(trade.get('size', 0)),
                    price=float(trade.get('price', 0)),
                    amount=float(trade.get('size', 0)) * float(trade.get('price', 0)),
                    timestamp=timestamp,
                    is_whale_trade=True,
                    followed=False
                )

                session.add(new_trade)
                trades_added += 1

            except Exception as e:
                print(f'  Error processing trade: {str(e)[:50]}')
                continue

        if trades_added > 0:
            session.commit()
            total_trades_added += trades_added
            total_whales_processed += 1
            print(f'  ✅ Added {trades_added} trades')
        else:
            print(f'  No new trades (all already in database)')

        # Rate limiting
        time.sleep(0.5)

    except requests.exceptions.Timeout:
        print(f'  ⏱️  Timeout')
        continue
    except Exception as e:
        print(f'  ❌ Error: {str(e)[:50]}')
        session.rollback()
        continue

print()
print('=' * 80)
print('FETCH COMPLETE')
print('=' * 80)
print(f'Whales processed: {total_whales_processed}/{len(elite_whales)}')
print(f'Total trades added: {total_trades_added}')
print()

# Show final count
total_whale_trades = session.query(Trade).filter(Trade.is_whale_trade == True).count()
unique_whales = session.query(Trade.trader_address).filter(Trade.is_whale_trade == True).distinct().count()

print(f'Database now has:')
print(f'  {total_whale_trades} total whale trades')
print(f'  {unique_whales} unique whales with trades')
print()
print('=' * 80)

session.close()
