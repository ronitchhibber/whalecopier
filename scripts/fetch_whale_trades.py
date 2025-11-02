"""
Fetch recent trades from all profitable whales and populate the database.
This creates the initial trade history for the copy trading engine.
"""

import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def fetch_trades_for_whale(address, limit=100):
    """Fetch recent trades for a whale from Polymarket CLOB API."""
    trades = []

    # Try both maker and taker endpoints
    endpoints = [
        f"https://clob.polymarket.com/trades?maker={address}",
        f"https://clob.polymarket.com/trades?taker={address}"
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    trades.extend(data)
        except Exception as e:
            print(f"      Error fetching from {endpoint.split('?')[0].split('/')[-1]}: {e}")
            continue

    # Deduplicate by trade ID
    seen = set()
    unique_trades = []
    for trade in trades:
        trade_id = trade.get('id')
        if trade_id and trade_id not in seen:
            seen.add(trade_id)
            unique_trades.append(trade)

    return unique_trades[:limit]


def parse_trade_to_model(trade_data, trader_address):
    """Parse API trade data into Trade model."""
    try:
        # Extract trade details
        trade_id = trade_data.get('id')
        market_id = trade_data.get('market')
        token_id = trade_data.get('asset_id')

        # Determine side (BUY or SELL)
        side = trade_data.get('side', 'BUY').upper()
        if side not in ['BUY', 'SELL']:
            side = 'BUY'

        # Parse amounts
        size = float(trade_data.get('size', 0) or 0)
        price = float(trade_data.get('price', 0) or 0)
        amount = size * price if size and price else 0

        # Parse timestamp
        timestamp_str = trade_data.get('timestamp')
        if timestamp_str:
            if isinstance(timestamp_str, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_str)
            else:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()

        # Create Trade object
        trade = Trade(
            trade_id=trade_id,
            trader_address=trader_address.lower(),
            market_id=market_id or 'unknown',
            token_id=token_id or 'unknown',
            side=side,
            size=size,
            price=price,
            amount=amount,
            timestamp=timestamp,
            is_whale_trade=True,
            followed=False
        )

        return trade

    except Exception as e:
        print(f"        Error parsing trade: {e}")
        return None


def fetch_all_whale_trades():
    """Fetch trades for all profitable whales and store in database."""
    print("\n" + "=" * 80)
    print("📥 FETCHING WHALE TRADES")
    print("=" * 80)

    session = Session()

    # Get all whales with copy trading enabled
    whales = session.query(Whale).filter(
        Whale.is_copying_enabled == True
    ).order_by(Whale.quality_score.desc()).all()

    print(f"\n📊 Fetching trades for {len(whales)} whales")
    print(f"⏳ This may take a few minutes...\n")

    total_trades = 0
    whales_with_trades = 0

    print("=" * 80)
    print("FETCHING TRADES")
    print("=" * 80)

    for i, whale in enumerate(whales, 1):
        name = whale.pseudonym[:20] if whale.pseudonym else whale.address[:10]
        print(f"[{i:2}/{len(whales)}] {name:<22} | ", end="")

        # Fetch trades from API
        trades_data = fetch_trades_for_whale(whale.address, limit=100)

        if not trades_data:
            print(f"No trades found")
            time.sleep(0.2)
            continue

        # Parse and store trades
        new_trades = 0
        for trade_data in trades_data:
            trade = parse_trade_to_model(trade_data, whale.address)
            if trade:
                # Check if trade already exists
                existing = session.query(Trade).filter_by(trade_id=trade.trade_id).first()
                if not existing:
                    session.add(trade)
                    new_trades += 1

        if new_trades > 0:
            session.commit()
            total_trades += new_trades
            whales_with_trades += 1
            print(f"✅ {new_trades} trades added")
        else:
            print(f"⏭️  No new trades")

        time.sleep(0.2)  # Rate limiting

    print("\n" + "=" * 80)
    print("✅ TRADE FETCH COMPLETE")
    print("=" * 80)
    print(f"Whales processed: {len(whales)}")
    print(f"Whales with trades: {whales_with_trades}")
    print(f"Total trades fetched: {total_trades}")

    # Show recent trade stats
    if total_trades > 0:
        recent_trades = session.query(Trade).order_by(Trade.timestamp.desc()).limit(10).all()

        print("\n" + "=" * 80)
        print("📊 RECENT WHALE TRADES")
        print("=" * 80)
        print(f"{'Time':<20} {'Whale':<22} {'Side':<6} {'Size':<12} {'Price':<8}")
        print("-" * 80)

        for trade in recent_trades:
            whale = session.query(Whale).filter_by(address=trade.trader_address).first()
            name = whale.pseudonym[:20] if whale and whale.pseudonym else trade.trader_address[:10]
            time_str = trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            size_str = f"{trade.size:.2f}"
            price_str = f"{trade.price:.3f}" if trade.price else "N/A"

            print(f"{time_str:<20} {name:<22} {trade.side:<6} {size_str:<12} {price_str:<8}")

    session.close()

    return total_trades


if __name__ == "__main__":
    total = fetch_all_whale_trades()

    print("\n" + "=" * 80)
    print("📋 NEXT STEPS")
    print("=" * 80)
    print("1. ✅ Whale trades fetched and stored in database")
    print("2. 📊 Ready to start real-time trade monitoring")
    print("3. 🚀 Start copy trading engine to begin copying trades")
    print()
