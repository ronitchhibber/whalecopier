"""
Fetch real-time trades from Polymarket public Data API.
Uses the public Data API to get actual trades happening right now - NO AUTHENTICATION REQUIRED!

Usage: python3 scripts/fetch_realtime_trades.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Trade
from dotenv import load_dotenv
import logging
import requests
from datetime import datetime
from decimal import Decimal
import time

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:trader_password@localhost:5432/polymarket_trader')

def fetch_recent_market_trades(limit=200):
    """
    Fetch recent trades from Polymarket public Data API.
    This endpoint requires NO AUTHENTICATION!
    """
    try:
        url = "https://data-api.polymarket.com/trades"

        params = {
            "limit": limit,
            "offset": 0
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Fetched {len(data) if isinstance(data, list) else 0} trades from Data API")
            return data if isinstance(data, list) else []
        else:
            logger.error(f"API returned {response.status_code}: {response.text}")
            return []

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return []

def is_tracked_whale(trader_address, session):
    """Check if trader is one of our tracked whales"""
    whale = session.query(Whale).filter(
        Whale.address.ilike(trader_address),
        Whale.is_copying_enabled == True
    ).first()
    return whale

def store_real_trade(session, trade_data):
    """Store a real trade from Polymarket Data API"""
    try:
        # Parse trade data from Data API
        trade_id = trade_data.get('transactionHash', '')
        trader_address = trade_data.get('proxyWallet', '').lower()

        # Check if trader is a tracked whale
        whale = is_tracked_whale(trader_address, session)
        if not whale:
            return False  # Not a tracked whale

        # Check if trade already exists
        existing = session.query(Trade).filter(Trade.trade_id == trade_id).first()
        if existing:
            return False

        # Parse trade details
        side = trade_data.get('side', 'BUY').upper()
        size = float(trade_data.get('size', 0))
        price = float(trade_data.get('price', 0))
        amount = size * price

        # Get timestamp
        timestamp = trade_data.get('timestamp')
        if isinstance(timestamp, (int, float)):
            trade_time = datetime.fromtimestamp(timestamp)
        else:
            trade_time = datetime.now()

        # Market info
        market_id = trade_data.get('conditionId', '')
        token_id = trade_data.get('asset', '')
        market_title = trade_data.get('title', '')
        outcome = trade_data.get('outcome', '')

        # Create trade
        trade = Trade(
            trade_id=trade_id,
            trader_address=trader_address,
            market_id=str(market_id),
            token_id=str(token_id),
            market_title=market_title,
            side=side,
            size=Decimal(str(size)),
            price=Decimal(str(price)),
            amount=Decimal(str(amount)),
            timestamp=trade_time,
            is_whale_trade=True,
            followed=False
        )

        session.add(trade)

        logger.info(
            f"💰 WHALE TRADE | {whale.pseudonym or trader_address[:10]} | "
            f"{side} {size:.2f} @ ${price:.4f} = ${amount:.2f} | {market_title} ({outcome})"
        )

        return True

    except Exception as e:
        logger.error(f"Error storing trade: {e}")
        return False

def fetch_and_store_realtime_trades():
    """Main function to fetch and store real trades"""

    engine = create_engine(DATABASE_URL)

    logger.info("🔄 Fetching real-time trades from Polymarket CLOB API...")

    # Fetch recent trades
    trades_data = fetch_recent_market_trades(limit=200)

    if not trades_data:
        logger.warning("⚠️  No trades returned from API")
        return 0

    with Session(engine) as session:
        # Get our tracked whales for quick lookup
        whales = session.query(Whale).filter(
            Whale.is_copying_enabled == True
        ).all()

        logger.info(f"📊 Processing {len(trades_data)} recent trades...")
        logger.info(f"🐋 Checking against {len(whales)} tracked whales...")

        stored_count = 0

        for trade_data in trades_data:
            if store_real_trade(session, trade_data):
                stored_count += 1

                # Commit every 10 trades
                if stored_count % 10 == 0:
                    session.commit()

        # Final commit
        session.commit()

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Real-time fetch complete!")
        logger.info(f"  Trades processed: {len(trades_data)}")
        logger.info(f"  Whale trades stored: {stored_count}")
        logger.info("=" * 80)

        return stored_count

def continuous_fetch(interval_seconds=60):
    """Continuously fetch trades at regular intervals"""
    logger.info("🚀 Starting continuous real-time trade fetcher...")
    logger.info(f"⏱️  Fetch interval: {interval_seconds} seconds")
    logger.info("")

    while True:
        try:
            count = fetch_and_store_realtime_trades()

            if count > 0:
                logger.info(f"✅ Stored {count} new whale trades")
            else:
                logger.info("⏭️  No new whale trades this cycle")

            logger.info(f"⏱️  Next fetch in {interval_seconds} seconds...")
            logger.info("")

            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("\n⏹️  Stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in continuous fetch: {e}")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch real-time Polymarket trades')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Fetch interval in seconds (default: 60)')

    args = parser.parse_args()

    if args.continuous:
        continuous_fetch(interval_seconds=args.interval)
    else:
        count = fetch_and_store_realtime_trades()
        logger.info(f"\n✅ Done! Stored {count} whale trades")
