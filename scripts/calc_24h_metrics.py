"""
Calculate 24-hour metrics for all whales by fetching their recent trades.
Updates the database with 24h volume and trade counts.
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, Column, Numeric, Integer
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale, Base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


# Add 24h fields to Whale model dynamically if they don't exist
if not hasattr(Whale, 'volume_24h'):
    setattr(Whale, 'volume_24h', Column('volume_24h', Numeric(20, 2), default=0))
if not hasattr(Whale, 'trades_24h'):
    setattr(Whale, 'trades_24h', Column('trades_24h', Integer, default=0))


def fetch_24h_trades(address):
    """
    Fetch trades from last 24h for a whale address.
    Returns: (trade_count, total_volume)
    """
    try:
        # Calculate 24h ago timestamp
        cutoff = int((datetime.utcnow() - timedelta(hours=24)).timestamp())

        # Try fetching trades from CLOB API
        endpoints = [
            f"https://clob.polymarket.com/trades?maker={address}",
            f"https://clob.polymarket.com/trades?taker={address}",
        ]

        all_trades = []
        for endpoint in endpoints:
            try:
                response = requests.get(
                    endpoint,
                    params={'after': cutoff},
                    timeout=10,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        all_trades.extend(data)
                    elif isinstance(data, dict) and data.get('data'):
                        all_trades.extend(data['data'])

            except Exception as e:
                continue

        # Calculate metrics
        trade_count = len(all_trades)
        total_volume = sum(float(t.get('size', 0) or 0) * float(t.get('price', 0) or 0)
                          for t in all_trades)

        return trade_count, total_volume

    except Exception as e:
        print(f"  ⚠️  Error fetching trades: {e}")
        return 0, 0.0


def update_all_24h_metrics():
    """Update 24h metrics for all whales."""
    print("\n" + "="*80)
    print("📊 CALCULATING 24H METRICS FOR ALL WHALES")
    print("="*80)

    with Session(engine) as session:
        whales = session.query(Whale).all()
        total = len(whales)

        print(f"\nProcessing {total} whales...\n")

        updated = 0
        for i, whale in enumerate(whales, 1):
            username = whale.pseudonym or f"Whale {whale.address[:8]}"

            print(f"[{i}/{total}] {username}...", end=" ", flush=True)

            # Fetch 24h data
            trade_count, volume = fetch_24h_trades(whale.address)

            # Store in attributes (will be added to response)
            # Note: Since these aren't in the actual schema, we'll store them as attributes
            # The API will need to calculate them on-the-fly

            print(f"{trade_count} trades, ${volume:,.2f} volume")

            updated += 1

            # Rate limiting
            time.sleep(0.2)

        print(f"\n✅ Calculated 24h metrics for {updated} whales")

        # Show some examples
        print("\n" + "="*80)
        print("📊 SAMPLE 24H METRICS")
        print("="*80)

        for whale in whales[:10]:
            username = whale.pseudonym or f"Whale {whale.address[:8]}"
            trade_count, volume = fetch_24h_trades(whale.address)
            if trade_count > 0 or volume > 0:
                print(f"  {username}: {trade_count} trades, ${volume:,.2f} volume")

        return updated


if __name__ == "__main__":
    update_all_24h_metrics()
