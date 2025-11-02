"""
Whale trade monitoring service - runs every 15 minutes.

This service:
1. Checks each enabled whale's profile every 15 minutes
2. Detects when new trades have been made
3. Updates the most_recent_trade_at timestamp
4. Logs trade activity for tracking

Note: Individual trade details require authenticated CLOB API access.
Once authentication is set up, this can be enhanced to fetch actual trade data.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import live trader for copy trading execution
try:
    from simple_live_trader import trader as live_trader
    LIVE_TRADER_AVAILABLE = True
    logger.info("Live trader loaded successfully")
except ImportError as e:
    logger.warning(f"Live trader not available: {e}")
    LIVE_TRADER_AVAILABLE = False
    live_trader = None

# Import trade fetcher for getting individual trade details
try:
    from whale_trade_fetcher import trade_fetcher
    TRADE_FETCHER_AVAILABLE = True
    logger.info("Trade fetcher loaded successfully")
except ImportError as e:
    logger.warning(f"Trade fetcher not available: {e}")
    TRADE_FETCHER_AVAILABLE = False
    trade_fetcher = None


class WhaleTradeMonitor:
    """
    Monitors whale trades every 15 minutes by checking for profile changes.
    """

    def __init__(self, check_interval_minutes: int = 5):
        """
        Initialize the trade monitor.

        Args:
            check_interval_minutes: How often to check for trades (default: 5)
        """
        self.check_interval_minutes = check_interval_minutes
        self.running = False

        # Setup database connection
        db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

        # Cache of last known state for each whale
        self.last_state = {}

    def get_whale_profile(self, address: str) -> Optional[Dict]:
        """
        Fetch whale profile from Polymarket Gamma API.

        Args:
            address: Whale wallet address

        Returns:
            Profile data dict or None if error
        """
        try:
            url = f"https://gamma-api.polymarket.com/profile/{address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.error(f"Error fetching profile for {address[:10]}: {e}")
            return None

    def detect_new_trades(self, whale: Whale, current_profile: Dict) -> Dict:
        """
        Detect if whale has made new trades since last check.

        Args:
            whale: Whale model instance
            current_profile: Current profile data from API

        Returns:
            Dict with trade activity info
        """
        # Get current metrics
        current_trades = current_profile.get('totalTrades', 0)
        current_volume = float(current_profile.get('totalVolume', 0) or 0)
        current_pnl = float(current_profile.get('pnl', 0) or 0)

        # Get last known state
        last_state = self.last_state.get(whale.address, {})
        last_trades = last_state.get('total_trades', whale.total_trades or 0)
        last_volume = last_state.get('total_volume', float(whale.total_volume or 0))

        # Calculate changes
        new_trades = current_trades - last_trades
        volume_change = current_volume - last_volume

        # Update cache
        self.last_state[whale.address] = {
            'total_trades': current_trades,
            'total_volume': current_volume,
            'total_pnl': current_pnl,
            'checked_at': datetime.utcnow()
        }

        return {
            'has_new_trades': new_trades > 0,
            'new_trades_count': new_trades,
            'volume_change': volume_change,
            'current_trades': current_trades,
            'current_volume': current_volume,
            'current_pnl': current_pnl
        }

    def monitor_whale(self, whale: Whale, session) -> bool:
        """
        Monitor a single whale for new trade activity.

        Args:
            whale: Whale model instance
            session: Database session

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Fetch current profile
            profile = self.get_whale_profile(whale.address)

            if not profile:
                logger.debug(f"No profile available for {whale.pseudonym or whale.address[:10]}")
                return False

            # Detect new trades
            activity = self.detect_new_trades(whale, profile)

            # Update whale record
            whale.total_trades = activity['current_trades']
            whale.total_volume = activity['current_volume']
            whale.total_pnl = activity['current_pnl']
            whale.last_trade_check_at = datetime.utcnow()

            # If new trades detected, update most_recent_trade_at
            if activity['has_new_trades']:
                whale.most_recent_trade_at = datetime.utcnow()

                logger.info(
                    f"🔔 New activity: {whale.pseudonym or whale.address[:10]} | "
                    f"+{activity['new_trades_count']} trades | "
                    f"${activity['volume_change']:,.0f} volume"
                )

                # Execute copy trades if trade fetcher and live trader are available
                if TRADE_FETCHER_AVAILABLE and LIVE_TRADER_AVAILABLE and trade_fetcher and live_trader:
                    logger.info(
                        f"Fetching trade details for {whale.pseudonym or whale.address[:10]}..."
                    )

                    # Fetch new trades from Data API
                    new_trades = trade_fetcher.get_new_trades_for_whale(whale)

                    logger.info(f"Found {len(new_trades)} new trade(s) for copying")

                    # Execute each trade
                    for trade_data in new_trades:
                        parsed = trade_fetcher.parse_trade_for_copy(trade_data)

                        if not parsed:
                            continue

                        # Save whale's trade to database
                        trade_fetcher.save_whale_trade(whale, parsed)

                        # Execute copy trade
                        logger.info(
                            f"Copy trading: {parsed['side']} {parsed['outcome']} "
                            f"on '{parsed['market_title'][:50]}' @ ${parsed['price']}"
                        )

                        result = live_trader.execute_trade(
                            whale=whale,
                            market_id=parsed['market_id'],
                            side=parsed['side'],
                            price=parsed['price']
                        )

                        if result:
                            logger.info(f"  ✓ Copy trade executed: {result['mode']} mode")
                        else:
                            logger.warning(f"  ✗ Copy trade skipped or failed")

            session.commit()
            return True

        except Exception as e:
            logger.error(f"Error monitoring whale {whale.address[:10]}: {e}")
            session.rollback()
            return False

    async def monitoring_cycle(self):
        """Execute one monitoring cycle - check all enabled whales."""
        session = self.Session()

        try:
            # Get all whales enabled for copy trading
            whales = session.query(Whale).filter(
                Whale.is_copying_enabled == True,
                Whale.is_active == True
            ).all()

            logger.info(f"🔍 Monitoring {len(whales)} whales for new trades...")

            success_count = 0
            activity_count = 0
            error_count = 0

            for whale in whales:
                success = self.monitor_whale(whale, session)
                if success:
                    success_count += 1

                    # Check if activity was detected
                    last_state = self.last_state.get(whale.address, {})
                    if last_state.get('checked_at'):
                        # This whale was checked before
                        if whale.most_recent_trade_at and \
                           (datetime.utcnow() - whale.most_recent_trade_at).total_seconds() < 900:
                            activity_count += 1
                else:
                    error_count += 1

            logger.info(
                f"✅ Monitoring complete: {success_count} checked, "
                f"{activity_count} active, {error_count} errors"
            )

        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")

        finally:
            session.close()

    async def run(self):
        """
        Main service loop - monitor trades every 15 minutes.
        """
        self.running = True
        logger.info(f"🚀 Whale trade monitor started")
        logger.info(f"⏱️  Check interval: {self.check_interval_minutes} minutes")

        # Run immediately on startup
        await self.monitoring_cycle()

        # Then run periodically
        try:
            while self.running:
                logger.info(f"⏱️  Next check in {self.check_interval_minutes} minutes...")
                await asyncio.sleep(self.check_interval_minutes * 60)

                if self.running:
                    await self.monitoring_cycle()

        except KeyboardInterrupt:
            logger.info("⏹️  Shutting down...")
            self.running = False

    def stop(self):
        """Stop the service."""
        self.running = False


async def main():
    """Main entry point."""
    # Create and run monitor (15 minute intervals)
    monitor = WhaleTradeMonitor(check_interval_minutes=15)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("⏹️  Stopped by user")
        monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
