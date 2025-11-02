"""
Clear all existing trades from the database and start fresh trade monitoring.
This script will:
1. Delete all existing trades from the trades table
2. Reset trade counters for whales
3. Start monitoring for new trades every minute

Usage: python3 scripts/clear_and_restart_trades.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:trader_password@localhost:5432/polymarket_trader')

def clear_trades():
    """Clear all trades from the database"""
    try:
        engine = create_engine(DATABASE_URL)

        with Session(engine) as session:
            # Get count before deletion
            count_result = session.execute(text("SELECT COUNT(*) FROM trades"))
            trade_count = count_result.scalar()

            logger.info(f"Found {trade_count} trades in database")

            # Delete all trades
            session.execute(text("DELETE FROM trades"))

            # Reset whale trade counters
            session.execute(text("""
                UPDATE whales
                SET trades_24h = 0,
                    volume_24h = 0,
                    active_trades = 0,
                    most_recent_trade_at = NULL
            """))

            session.commit()

            logger.info(f"✅ Deleted {trade_count} trades")
            logger.info("✅ Reset whale trade counters")
            logger.info("🎯 Database is now clean and ready for fresh data")

            return trade_count

    except Exception as e:
        logger.error(f"Error clearing trades: {e}")
        raise

if __name__ == "__main__":
    logger.info("🧹 Clearing all trades from database...")
    count = clear_trades()
    logger.info(f"✅ Successfully cleared {count} trades. Ready to start fresh!")
