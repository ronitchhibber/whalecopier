"""
Copy Trading Engine - Main orchestrator for monitoring and copying whale trades.
Uses position tracking via Gamma API to detect whale activity.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from libs.common.models import Whale, Trade, Order, Market
from copy_trading.orderbook_tracker import OrderbookTracker as WhalePositionTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CopyTradingEngine:
    """
    Main copy trading engine that monitors whale trades and executes copy trades.
    """

    def __init__(self, config_path: str = "config/copy_trading_rules.json"):
        """Initialize the copy trading engine."""
        self.config = self.load_config(config_path)
        self.running = False
        self.last_check = {}  # Track last check time per whale
        self.tracker = WhalePositionTracker()  # Position tracker for monitoring

        # Database setup
        from dotenv import load_dotenv
        import os
        load_dotenv()

        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def load_config(self, config_path: str) -> dict:
        """Load copy trading configuration."""
        with open(config_path, 'r') as f:
            return json.load(f)

    async def start(self):
        """Start the copy trading engine."""
        logger.info("=" * 80)
        logger.info("🚀 COPY TRADING ENGINE STARTING")
        logger.info("=" * 80)

        self.running = True

        # Log configuration
        logger.info(f"Max exposure: ${self.config['risk_management']['global_limits']['max_total_exposure_usd']:,}")
        logger.info(f"Max positions: {self.config['risk_management']['global_limits']['max_positions']}")
        logger.info(f"Max daily loss: ${self.config['risk_management']['global_limits']['max_loss_per_day_usd']:,}")

        # Get whales to monitor
        session = self.Session()
        whales = session.query(Whale).filter(Whale.is_copying_enabled == True).all()
        logger.info(f"Monitoring {len(whales)} whales for trades")
        session.close()

        logger.info("=" * 80)
        logger.info("✅ Engine started - Monitoring for whale trades...")
        logger.info("=" * 80)

        # Main monitoring loop - Check every 5 minutes
        try:
            while self.running:
                await self.monitor_cycle()
                logger.info("⏱️  Next check in 5 minutes...")
                await asyncio.sleep(300)  # Check every 5 minutes (300 seconds)
        except KeyboardInterrupt:
            logger.info("\n⏸️  Stopping engine...")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Engine error: {e}")
            raise

    async def monitor_cycle(self):
        """Execute one monitoring cycle - check whales for position changes."""
        session = self.Session()

        try:
            # Get whales to monitor
            whales = session.query(Whale).filter(
                Whale.is_copying_enabled == True
            ).order_by(Whale.quality_score.desc()).all()

            logger.info(f"🔍 Checking {len(whales)} whales for activity...")

            activity_detected = 0

            for whale in whales:
                # Monitor whale for new trades
                new_trades = self.tracker.monitor_whale(whale.address)

                if new_trades:
                    activity_detected += 1

                    for trade in new_trades:
                        # Log activity
                        logger.info(f"📈 New trade detected:")
                        logger.info(f"   Whale: {whale.pseudonym or whale.address[:10]}")
                        logger.info(f"   Type: {trade['type']}")
                        logger.info(f"   Market: {trade.get('market_title', 'Unknown')[:50] if trade.get('market_title') else 'Unknown'}")
                        logger.info(f"   Shares: {trade['shares']:,.2f}")
                        logger.info(f"   Price: ${trade['price']:.3f}")
                        logger.info(f"   Amount: ${trade['amount']:,.0f}")

                        # Save trade to database
                        self.save_whale_trade(trade, whale, session)

                        # Check if we should copy this trade
                        should_copy, reason = self.should_copy_trade(trade, whale, session)

                        if should_copy:
                            logger.info(f"✅ Trade meets copy criteria: {reason}")
                            # Execute the copy trade
                            await self.execute_copy_trade(trade, whale, session)
                        else:
                            logger.info(f"⏭️  Skipping trade: {reason}")

            if activity_detected > 0:
                logger.info(f"✅ Detected activity from {activity_detected} whales")
            else:
                logger.info(f"💤 No new activity detected from {len(whales)} whales")

        except Exception as e:
            logger.error(f"Error in monitor cycle: {e}")
        finally:
            session.close()

    def save_whale_trade(self, trade_data: Dict, whale: Whale, session: Session):
        """Save a whale trade to the database."""
        try:
            # Check if trade already exists
            existing = session.query(Trade).filter_by(
                trade_id=trade_data.get('id', '')
            ).first()

            if existing:
                return

            # Create new trade record
            trade = Trade(
                trade_id=trade_data.get('id', '')[:100] if trade_data.get('id') else '',  # Truncate to 100 chars
                trader_address=whale.address.lower(),
                market_id=trade_data.get('market_id', ''),
                market_title=trade_data.get('market_title', ''),
                token_id=trade_data.get('market_id', ''),  # Use market_id as token_id
                side=trade_data.get('type', 'BUY').upper(),
                size=trade_data.get('shares', 0),
                price=trade_data.get('price', 0),
                amount=trade_data.get('amount', 0),
                timestamp=trade_data.get('timestamp', datetime.utcnow()),
                transaction_hash=trade_data.get('tx_hash', ''),
                is_whale_trade=True,
                followed=False
            )

            session.add(trade)
            session.commit()

            logger.info(f"💾 Saved new whale trade: {trade.trade_id}")

        except Exception as e:
            logger.error(f"Error saving whale trade: {e}")
            session.rollback()

    async def check_whale_for_new_trades(self, whale: Whale, session: Session) -> List[Trade]:
        """Check a specific whale for new trades since last check."""
        import requests

        # Get last check time for this whale
        last_check = self.last_check.get(whale.address, datetime.utcnow() - timedelta(hours=1))

        new_trades = []

        try:
            # Query CLOB API for recent trades
            endpoints = [
                f"https://clob.polymarket.com/trades?maker={whale.address}",
                f"https://clob.polymarket.com/trades?taker={whale.address}"
            ]

            all_trades = []
            for endpoint in endpoints:
                response = requests.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        all_trades.extend(data)

            # Check for trades newer than last check
            for trade_data in all_trades:
                trade_id = trade_data.get('id')

                # Check if we already have this trade
                existing = session.query(Trade).filter_by(trade_id=trade_id).first()
                if existing:
                    continue

                # Parse timestamp
                timestamp_str = trade_data.get('timestamp')
                if timestamp_str:
                    if isinstance(timestamp_str, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                    # Only process if newer than last check
                    if timestamp > last_check:
                        trade = self.parse_trade(trade_data, whale.address)
                        if trade:
                            session.add(trade)
                            new_trades.append(trade)

            # Update last check time
            self.last_check[whale.address] = datetime.utcnow()

            if new_trades:
                session.commit()
                logger.info(f"✅ New trade from {whale.pseudonym or whale.address[:10]}: {len(new_trades)} trades")

        except Exception as e:
            logger.error(f"Error checking whale {whale.address[:10]}: {e}")

        return new_trades

    def parse_trade(self, trade_data: dict, trader_address: str) -> Optional[Trade]:
        """Parse trade data from API into Trade model."""
        try:
            side = trade_data.get('side', 'BUY').upper()
            if side not in ['BUY', 'SELL']:
                side = 'BUY'

            size = float(trade_data.get('size', 0) or 0)
            price = float(trade_data.get('price', 0) or 0)

            timestamp_str = trade_data.get('timestamp')
            if timestamp_str:
                if isinstance(timestamp_str, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_str)
                else:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.utcnow()

            trade = Trade(
                trade_id=trade_data.get('id'),
                trader_address=trader_address.lower(),
                market_id=trade_data.get('market', 'unknown'),
                token_id=trade_data.get('asset_id', 'unknown'),
                side=side,
                size=size,
                price=price,
                amount=size * price,
                timestamp=timestamp,
                is_whale_trade=True,
                followed=False
            )

            return trade

        except Exception as e:
            logger.error(f"Error parsing trade: {e}")
            return None

    def should_copy_trade(self, trade: Dict, whale: Whale, session: Session) -> tuple:
        """
        Evaluate if a trade should be copied based on rules.
        Returns (should_copy: bool, reason: str)
        """

        # Check if whale is in our enabled list
        if not whale.is_copying_enabled:
            return False, "Whale not enabled for copying"

        # Check position size filters
        trade_value = float(trade.get('amount', 0))
        min_size = self.config['trade_filters']['min_whale_position_size_usd']
        max_size = self.config['trade_filters']['max_whale_position_size_usd']

        if trade_value < min_size:
            return False, f"Trade too small (${trade_value:.0f} < ${min_size})"

        if trade_value > max_size:
            return False, f"Trade too large (${trade_value:.0f} > ${max_size})"

        # Check price filters
        price = trade.get('price', 0)
        if price:
            min_price = self.config['trade_filters']['price_filters']['min_price']
            max_price = self.config['trade_filters']['price_filters']['max_price']

            if price < min_price or price > max_price:
                return False, f"Price outside range ({price:.3f})"

        # Check global exposure limits
        total_exposure = self.get_current_exposure(session)
        max_exposure = self.config['risk_management']['global_limits']['max_total_exposure_usd']

        if total_exposure >= max_exposure:
            return False, f"Max exposure reached (${total_exposure:.0f}/${max_exposure})"

        # Check max positions
        open_positions = self.get_open_positions_count(session)
        max_positions = self.config['risk_management']['global_limits']['max_positions']

        if open_positions >= max_positions:
            return False, f"Max positions reached ({open_positions}/{max_positions})"

        # All checks passed
        return True, "All checks passed"

    def get_current_exposure(self, session: Session) -> float:
        """Calculate current total exposure."""
        # This would calculate total value of open positions
        # Simplified for now
        return 0.0

    def get_open_positions_count(self, session: Session) -> int:
        """Get count of open positions."""
        # This would count open positions
        # Simplified for now
        return 0

    async def execute_copy_trade(self, trade: Dict, whale: Whale, session: Session):
        """Execute a copy trade based on whale's trade."""
        logger.info("=" * 80)
        logger.info(f"🎯 COPYING TRADE from {whale.pseudonym or whale.address[:10]}")
        logger.info("=" * 80)

        # Calculate position size based on whale tier
        whale_tier = whale.tier or "LARGE"
        tier_config = self.config['whale_tiers'].get(whale_tier.lower(), {})

        copy_percentage = tier_config.get('copy_percentage', 75) / 100
        max_position = tier_config.get('max_position_size_usd', 500)

        # Calculate our position size
        whale_position_value = float(trade.get('amount', 0))
        our_position_value = min(whale_position_value * copy_percentage, max_position)

        # Calculate size based on price
        price = float(trade.get('price', 0))
        if price > 0:
            our_size = our_position_value / price
        else:
            our_size = 0

        side = trade.get('type', 'BUY').upper()
        shares = float(trade.get('shares', 0))

        logger.info(f"Whale trade: {side} {shares:.2f} @ ${price:.3f} = ${whale_position_value:.2f}")
        logger.info(f"Our trade: {side} {our_size:.2f} @ ${price:.3f} = ${our_position_value:.2f}")
        logger.info(f"Copy ratio: {copy_percentage*100:.0f}% (tier: {whale_tier})")

        # Create order record
        order = Order(
            order_id=f"copy_{trade.get('id', '')}_{datetime.utcnow().timestamp()}",
            market_id=trade.get('market_id', ''),
            token_id=trade.get('market_id', ''),
            side=side,
            order_type="LIMIT",
            price=price,
            size=our_size,
            status="PENDING",
            source_whale=whale.address,
            source_trade_id=trade.get('id', ''),
            copy_ratio=Decimal(str(copy_percentage))
        )

        session.add(order)

        # Update the saved trade record to mark as followed
        saved_trade = session.query(Trade).filter_by(
            trade_id=trade.get('id', '')[:100] if trade.get('id') else ''
        ).first()

        if saved_trade:
            saved_trade.followed = True
            saved_trade.copy_reason = f"Copied from {whale_tier} tier whale"

        session.commit()

        logger.info(f"✅ Order created: {order.order_id}")
        logger.info(f"📊 Status: {order.status}")
        logger.info("=" * 80)

    async def stop(self):
        """Stop the copy trading engine."""
        logger.info("🛑 Stopping copy trading engine...")
        self.running = False


async def main():
    """Main entry point for copy trading engine."""
    engine = CopyTradingEngine()
    await engine.start()


if __name__ == "__main__":
    asyncio.run(main())
