#!/usr/bin/env python3
"""
Fetch whale trades using the Goldsky orderbook subgraph.
This replaces the broken CLOB/Gamma API methods.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade
import time

# Database setup
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Goldsky orderbook endpoint
ORDERBOOK_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"


def fetch_recent_whale_trades(limit_per_whale=50):
    """Fetch recent trades for all whales using orderbook subgraph."""
    session = Session()

    try:
        # Get enabled whales
        whales = session.query(Whale).filter(
            Whale.is_copying_enabled == True
        ).order_by(Whale.quality_score.desc()).limit(20).all()

        print(f"Fetching trades for {len(whales)} top whales...")

        total_trades = 0
        since = int((datetime.utcnow() - timedelta(days=7)).timestamp())

        for whale in whales:
            print(f"\nProcessing {whale.pseudonym or whale.address[:10]}...")

            # Query for whale's recent orders
            query = """
            query GetWhaleOrders($taker: String!, $since: BigInt!, $limit: Int!) {
              orderFilledEvents(
                first: $limit
                orderBy: timestamp
                orderDirection: desc
                where: {
                  taker: $taker
                  timestamp_gte: $since
                }
              ) {
                id
                timestamp
                transactionHash
                taker
                maker
                makerAssetId
                takerAssetId
                makerAmountFilled
                takerAmountFilled
              }
            }
            """

            variables = {
                "taker": whale.address.lower(),
                "since": str(since),
                "limit": limit_per_whale
            }

            try:
                response = requests.post(
                    ORDERBOOK_URL,
                    json={'query': query, 'variables': variables},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()

                    if 'data' in data and 'orderFilledEvents' in data['data']:
                        orders = data['data']['orderFilledEvents']

                        for order in orders:
                            # Check if we already have this trade
                            trade_id = order['id'][:100] if len(order['id']) > 100 else order['id']
                            existing = session.query(Trade).filter_by(trade_id=trade_id).first()
                            if existing:
                                continue

                            # Parse order into trade
                            timestamp = datetime.fromtimestamp(int(order['timestamp']))

                            # Determine trade direction
                            taker_asset = order.get('takerAssetId', '')
                            is_buy = taker_asset.endswith('0' * 40)  # USDC

                            maker_amount = float(order.get('makerAmountFilled', 0) or 0) / 1e6
                            taker_amount = float(order.get('takerAmountFilled', 0) or 0) / 1e6

                            # Calculate price
                            if is_buy and maker_amount > 0:
                                price = taker_amount / maker_amount
                            elif not is_buy and taker_amount > 0:
                                price = maker_amount / taker_amount
                            else:
                                price = 0

                            # Create trade record
                            trade = Trade(
                                trade_id=trade_id,
                                trader_address=whale.address.lower(),
                                market_id=order.get('makerAssetId') if is_buy else order.get('takerAssetId'),
                                market_title='',  # We don't have titles from orderbook
                                token_id=order.get('makerAssetId') if is_buy else order.get('takerAssetId'),
                                side='BUY' if is_buy else 'SELL',
                                size=maker_amount if is_buy else taker_amount,
                                price=price,
                                amount=taker_amount if is_buy else maker_amount,
                                timestamp=timestamp,
                                transaction_hash=order.get('transactionHash', ''),
                                is_whale_trade=True,
                                followed=False
                            )

                            session.add(trade)
                            total_trades += 1

                            if total_trades % 10 == 0:
                                print(f"  Added {total_trades} trades...")

                        session.commit()
                        print(f"  ✅ Fetched {len(orders)} orders for {whale.pseudonym or whale.address[:10]}")

                time.sleep(0.2)  # Rate limiting

            except Exception as e:
                print(f"  ❌ Error fetching orders: {e}")
                continue

        print(f"\n✅ Total new trades added: {total_trades}")

    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()


def main():
    print("=" * 80)
    print("FETCHING WHALE TRADES FROM ORDERBOOK SUBGRAPH")
    print("=" * 80)
    print()

    fetch_recent_whale_trades()

    # Show statistics
    session = Session()
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN market_id IS NOT NULL AND market_id != '' THEN 1 END) as has_market_id,
                COUNT(CASE WHEN is_whale_trade = true THEN 1 END) as whale_trades,
                MIN(timestamp) as oldest_trade,
                MAX(timestamp) as newest_trade
            FROM trades
        """)).fetchone()

        print("\n" + "=" * 80)
        print("DATABASE STATISTICS")
        print("=" * 80)
        print(f"Total trades: {result[0]}")
        print(f"Has market_id: {result[1]} ({result[1]/result[0]*100:.1f}%)")
        print(f"Whale trades: {result[2]}")
        print(f"Date range: {result[3]} to {result[4]}")

    except Exception as e:
        print(f"Error getting stats: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    main()