"""
Background service to update whale 24h metrics periodically.

This service runs every 15 minutes and updates:
- trades_24h: Count of trades in last 24 hours
- volume_24h: Dollar volume in last 24 hours
- active_trades: Current number of active positions
- most_recent_trade_at: Timestamp of most recent trade
- last_trade_check_at: When we last checked for new trades
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
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


class WhaleMetricsUpdater:
    """
    Background service that periodically updates whale 24h metrics.
    """

    def __init__(self, update_interval_minutes: int = 360):
        """
        Initialize the metrics updater.

        Args:
            update_interval_minutes: How often to update metrics (default: 360 = 6 hours)
        """
        self.update_interval_minutes = update_interval_minutes
        self.running = False

        # Setup database connection
        db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_whale_profile_from_api(self, address: str) -> Optional[Dict]:
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
                logger.warning(f"API error for {address[:10]}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching profile for {address[:10]}: {e}")
            return None

    def calculate_24h_metrics_from_trades(self, session, whale_address: str) -> Dict:
        """
        Calculate 24h metrics from trades table.

        Args:
            session: Database session
            whale_address: Whale wallet address

        Returns:
            Dict with trades_24h, volume_24h, most_recent_trade_at
        """
        # Calculate 24h cutoff
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        # Query trades from last 24h
        trades_24h = session.query(Trade).filter(
            Trade.trader_address == whale_address,
            Trade.timestamp >= cutoff_time
        ).all()

        # Calculate metrics
        trades_count = len(trades_24h)
        total_volume = sum(float(t.size or 0) * float(t.price or 0) for t in trades_24h)

        # Get most recent trade across all time
        most_recent_trade = session.query(Trade).filter(
            Trade.trader_address == whale_address
        ).order_by(Trade.timestamp.desc()).first()

        most_recent_at = most_recent_trade.timestamp if most_recent_trade else None

        return {
            'trades_24h': trades_count,
            'volume_24h': round(total_volume, 2),
            'most_recent_trade_at': most_recent_at
        }

    def update_whale_metrics(self, whale: Whale, session) -> bool:
        """
        Update metrics for a single whale.

        Args:
            whale: Whale model instance
            session: Database session

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Get current profile from API
            profile = self.get_whale_profile_from_api(whale.address)

            if not profile:
                # If API fails, still update from database trades
                logger.debug(f"Using database-only metrics for {whale.pseudonym or whale.address[:10]}")

            # Calculate 24h metrics from trades table
            db_metrics = self.calculate_24h_metrics_from_trades(session, whale.address)

            # Update whale record
            whale.trades_24h = db_metrics['trades_24h']
            whale.volume_24h = db_metrics['volume_24h']
            whale.most_recent_trade_at = db_metrics['most_recent_trade_at']
            whale.last_trade_check_at = datetime.utcnow()

            # If API profile available, use it for active_trades
            if profile:
                # Active positions from API (current open positions)
                whale.active_trades = profile.get('openPositions', 0)

            session.commit()

            logger.debug(
                f"Updated {whale.pseudonym or whale.address[:10]}: "
                f"{db_metrics['trades_24h']} trades, "
                f"${db_metrics['volume_24h']:,.2f} volume (24h)"
            )

            return True

        except Exception as e:
            logger.error(f"Error updating whale {whale.address[:10]}: {e}")
            session.rollback()
            return False

    async def update_cycle(self):
        """Execute one update cycle - update all whales."""
        session = self.Session()

        try:
            # Get all active whales (or at least copy-enabled whales)
            whales = session.query(Whale).filter(
                Whale.is_active == True
            ).all()

            logger.info(f"📊 Updating metrics for {len(whales)} whales...")

            success_count = 0
            error_count = 0

            for whale in whales:
                success = self.update_whale_metrics(whale, session)
                if success:
                    success_count += 1
                else:
                    error_count += 1

            logger.info(
                f"✅ Update complete: {success_count} successful, {error_count} errors"
            )

        except Exception as e:
            logger.error(f"Error in update cycle: {e}")

        finally:
            session.close()

    async def run(self):
        """
        Main service loop - update metrics periodically.
        """
        self.running = True
        logger.info(f"🚀 Whale metrics updater started")
        logger.info(f"⏱️  Update interval: {self.update_interval_minutes} minutes")

        # Run immediately on startup
        await self.update_cycle()

        # Then run periodically
        try:
            while self.running:
                logger.info(f"⏱️  Next update in {self.update_interval_minutes} minutes...")
                await asyncio.sleep(self.update_interval_minutes * 60)

                if self.running:
                    await self.update_cycle()

        except KeyboardInterrupt:
            logger.info("⏹️  Shutting down...")
            self.running = False

    def stop(self):
        """Stop the service."""
        self.running = False


async def main():
    """Main entry point."""
    # Create and run updater (15 minute intervals)
    updater = WhaleMetricsUpdater(update_interval_minutes=15)

    try:
        await updater.run()
    except KeyboardInterrupt:
        logger.info("⏹️  Stopped by user")
        updater.stop()


if __name__ == "__main__":
    asyncio.run(main())
