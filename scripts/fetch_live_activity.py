"""
Fetch live market activity from Polymarket Gamma API.
This pulls real trades and market data from Polymarket's public endpoints.

Usage: python3 scripts/fetch_live_activity.py --continuous
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

def fetch_live_markets():
    """Get currently active/hot markets from Gamma API"""
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "closed": "false",
            "limit": 20,
            "_sort": "volume24hr",
            "_order": "DESC"
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            markets = response.json()
            logger.info(f"✅ Found {len(markets)} active markets")
            return markets if isinstance(markets, list) else []
        else:
            logger.warning(f"Markets API returned {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []

def fetch_market_activity(market_id, limit=50):
    """Fetch recent activity for a specific market"""
    try:
        url = f"https://gamma-api.polymarket.com/events"

        params = {
            "market": market_id,
            "limit": limit
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            events = response.json()
            return events if isinstance(events, list) else []
        else:
            return []

    except Exception as e:
        logger.error(f"Error fetching market activity: {e}")
        return []

def is_tracked_whale(address, whales_dict):
    """Check if address is a tracked whale"""
    address_lower = address.lower()
    for whale_addr, whale in whales_dict.items():
        if whale_addr.lower() == address_lower:
            return whale
    return None

def store_activity_as_trade(session, event, market_info, whales_dict):
    """Convert market activity event to trade"""
    try:
        # Get trader address
        trader = event.get('user', event.get('trader', ''))
        if not trader:
            return False

        # Check if tracked whale
        whale = is_tracked_whale(trader, whales_dict)
        if not whale:
            return False

        # Create trade ID
        event_id = event.get('id', '')
        trade_id = f"live_{event_id}_{int(time.time())}"

        # Check if exists
        existing = session.query(Trade).filter(Trade.trade_id == trade_id).first()
        if existing:
            return False

        # Parse event
        event_type = event.get('type', 'trade')
        side = "BUY" if event_type in ['buy', 'mint'] else "SELL"

        # Get amount/size
        size = float(event.get('shares', event.get('amount', 0)))
        price = float(event.get('price', 0.5))
        amount = size * price

        # Timestamp
        timestamp_val = event.get('timestamp', event.get('t'))
        if timestamp_val:
            if isinstance(timestamp_val, (int, float)):
                trade_time = datetime.fromtimestamp(timestamp_val if timestamp_val > 1e10 else timestamp_val / 1000)
            else:
                try:
                    trade_time = datetime.fromisoformat(str(timestamp_val).replace('Z', '+00:00'))
                    trade_time = trade_time.replace(tzinfo=None)
                except:
                    trade_time = datetime.now()
        else:
            trade_time = datetime.now()

        # Market info
        market_id = market_info.get('id', '')
        market_title = market_info.get('question', market_info.get('title', 'Unknown Market'))

        # Create trade
        trade = Trade(
            trade_id=trade_id,
            trader_address=trader,
            market_id=str(market_id),
            token_id=str(market_id),
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
            f"💰 LIVE | {whale.pseudonym or trader[:10]} | "
            f"{side} {size:.2f} @ ${price:.4f} | "
            f"{market_title[:40]}..."
        )

        return True

    except Exception as e:
        logger.error(f"Error storing activity: {e}")
        return False

def fetch_and_store_live_activity():
    """Main function to fetch live activity"""

    engine = create_engine(DATABASE_URL)

    with Session(engine) as session:
        # Get tracked whales
        whales = session.query(Whale).filter(
            Whale.is_copying_enabled == True
        ).all()

        whales_dict = {w.address: w for w in whales}

        logger.info(f"🐋 Monitoring {len(whales)} whales for activity...")

        # Get active markets
        markets = fetch_live_markets()

        if not markets:
            logger.warning("⚠️  No active markets found")
            return 0

        logger.info(f"📊 Checking {len(markets)} active markets for whale activity...")

        stored_count = 0

        for market in markets[:10]:  # Check top 10 markets
            market_id = market.get('id', '')
            market_title = market.get('question', market.get('title', ''))[:50]

            logger.info(f"  Checking: {market_title}...")

            # Get activity for this market
            events = fetch_market_activity(market_id, limit=100)

            for event in events:
                if store_activity_as_trade(session, event, market, whales_dict):
                    stored_count += 1

                    if stored_count % 5 == 0:
                        session.commit()

            time.sleep(0.5)  # Rate limiting

        # Final commit
        session.commit()

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Live activity fetch complete!")
        logger.info(f"  Markets checked: {len(markets[:10])}")
        logger.info(f"  Whale trades found: {stored_count}")
        logger.info("=" * 80)

        return stored_count

def continuous_fetch(interval_seconds=60):
    """Continuously fetch live activity"""
    logger.info("🚀 Starting continuous live activity fetcher...")
    logger.info(f"⏱️  Fetch interval: {interval_seconds} seconds")
    logger.info("")

    while True:
        try:
            count = fetch_and_store_live_activity()

            if count > 0:
                logger.info(f"✅ Found {count} new whale trades")
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

    parser = argparse.ArgumentParser(description='Fetch live Polymarket activity')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Fetch interval in seconds')

    args = parser.parse_args()

    if args.continuous:
        continuous_fetch(interval_seconds=args.interval)
    else:
        count = fetch_and_store_live_activity()
        logger.info(f"\n✅ Done! Found {count} whale trades")
