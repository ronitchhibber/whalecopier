"""
Fetch trades from Polymarket public CLOB API (no authentication required)
This uses public endpoints to get recent market trades
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

def fetch_recent_trades(limit=100):
    """Fetch recent trades from public CLOB API"""
    try:
        url = "https://clob.polymarket.com/trades"
        params = {"limit": limit}

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            trades = response.json()
            logger.info(f"✅ Fetched {len(trades)} recent trades")
            return trades if isinstance(trades, list) else []
        else:
            logger.error(f"API returned {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return []

def is_tracked_whale(address, session):
    """Check if address is a tracked whale"""
    whale = session.query(Whale).filter(
        Whale.address.ilike(address),
        Whale.is_copying_enabled == True
    ).first()
    return whale

def store_trade(session, trade_data):
    """Store a trade if it's from a tracked whale"""
    try:
        trade_id = trade_data.get('id', trade_data.get('tradeId'))

        # Check both maker and taker
        maker = trade_data.get('maker', '')
        taker = trade_data.get('taker', '')

        whale = is_tracked_whale(maker, session)
        trader_address = maker if whale else None

        if not trader_address:
            whale = is_tracked_whale(taker, session)
            if whale:
                trader_address = taker

        if not trader_address or not whale:
            return False

        # Check if exists
        existing = session.query(Trade).filter(Trade.trade_id == trade_id).first()
        if existing:
            return False

        # Parse trade
        side = trade_data.get('side', 'BUY').upper()
        size = float(trade_data.get('size', 0))
        price = float(trade_data.get('price', 0))
        amount = size * price

        timestamp = trade_data.get('timestamp')
        if timestamp:
            if isinstance(timestamp, (int, float)):
                trade_time = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
            else:
                try:
                    trade_time = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                    trade_time = trade_time.replace(tzinfo=None)
                except:
                    trade_time = datetime.now()
        else:
            trade_time = datetime.now()

        market_id = trade_data.get('asset_id', trade_data.get('market', ''))
        token_id = trade_data.get('token_id', market_id)

        trade = Trade(
            trade_id=trade_id,
            trader_address=trader_address,
            market_id=str(market_id),
            token_id=str(token_id),
            market_title=None,
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
            f"💰 {whale.pseudonym or trader_address[:10]} | "
            f"{side} {size:.2f} @ ${price:.4f}"
        )

        return True

    except Exception as e:
        logger.error(f"Error storing trade: {e}")
        return False

def main(continuous=False, interval=60):
    """Main function"""
    engine = create_engine(DATABASE_URL)

    logger.info("🚀 Starting public trade fetcher...")
    logger.info(f"📡 Using public CLOB API (no auth required)")

    while True:
        try:
            with Session(engine) as session:
                whales = session.query(Whale).filter(
                    Whale.is_copying_enabled == True
                ).all()

                logger.info(f"🐋 Monitoring {len(whales)} whales")

                trades_data = fetch_recent_trades(limit=200)

                if not trades_data:
                    logger.warning("⚠️  No trades returned")
                else:
                    stored = 0
                    for trade_data in trades_data:
                        if store_trade(session, trade_data):
                            stored += 1
                            if stored % 10 == 0:
                                session.commit()

                    session.commit()
                    logger.info(f"✅ Stored {stored} whale trades")

            if not continuous:
                break

            logger.info(f"⏱️  Next fetch in {interval} seconds...")
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("\n⏹️  Stopped")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            if continuous:
                time.sleep(interval)
            else:
                break

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch public Polymarket trades')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Fetch interval in seconds')

    args = parser.parse_args()

    main(continuous=args.continuous, interval=args.interval)
