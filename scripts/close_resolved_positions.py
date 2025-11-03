#!/usr/bin/env python3
"""
Close all open positions from resolved/closed Polymarket markets
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Position
from dotenv import load_dotenv

load_dotenv()

def close_all_open_positions():
    """Close all positions that are marked as OPEN"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    with Session(engine) as session:
        # Get all open positions
        open_positions = session.query(Position).filter(Position.status == 'OPEN').all()

        print(f"Found {len(open_positions)} open positions to close")

        if len(open_positions) == 0:
            print("No open positions found")
            return

        # Close each position
        for pos in open_positions:
            pos.status = 'CLOSED'
            pos.closed_at = datetime.utcnow()
            pos.exit_price = pos.avg_entry_price  # Use entry price as exit since markets are resolved
            pos.realized_pnl = 0.0  # No realized P&L since we're just marking them closed

            print(f"Closed position {pos.position_id} - Market: {pos.market_id[:16]}... | Size: {pos.size} @ {pos.avg_entry_price}")

        # Commit changes
        session.commit()
        print(f"\n✅ Successfully closed {len(open_positions)} positions")

if __name__ == "__main__":
    close_all_open_positions()
