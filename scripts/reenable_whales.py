#!/usr/bin/env python3
"""
Re-enable the original 46 profitable whales that were in the database.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

def main():
    print("=" * 80)
    print("RE-ENABLING PROFITABLE WHALES")
    print("=" * 80)
    print()

    # Connect to database
    db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find whales with decent metrics
    whales = session.query(Whale).filter(
        Whale.total_pnl != None,
        Whale.total_pnl > 1000,  # At least $1k profit
        Whale.total_trades != None,
        Whale.total_trades > 10  # At least 10 trades
    ).all()

    print(f"Found {len(whales)} whales with PnL > $1,000 and > 10 trades")
    print()

    # Enable them
    enabled = 0
    for whale in whales:
        whale.is_copying_enabled = True
        whale.is_blacklisted = False
        whale.blacklist_reason = None
        whale.is_active = True

        # Set a default quality score if missing
        if not whale.quality_score or whale.quality_score == 0:
            # Simple score based on PnL and volume
            pnl = float(whale.total_pnl or 0)
            volume = float(whale.total_volume or 1)
            roi = (pnl / volume * 100) if volume > 0 else 0
            whale.quality_score = min(100, max(30, roi * 2))  # Basic score

        # Set tier if missing
        if not whale.tier:
            pnl = float(whale.total_pnl or 0)
            if pnl >= 100000:
                whale.tier = "MEGA"
            elif pnl >= 10000:
                whale.tier = "LARGE"
            elif pnl >= 1000:
                whale.tier = "MEDIUM"
            else:
                whale.tier = "SMALL"

        enabled += 1
        print(f"✓ {whale.pseudonym or whale.address[:10]}: "
              f"PnL ${whale.total_pnl:,.0f}, "
              f"Score {whale.quality_score:.1f}, "
              f"Tier {whale.tier}")

    # Commit
    session.commit()

    print()
    print("=" * 80)
    print(f"RE-ENABLED {enabled} WHALES")
    print("=" * 80)
    print()

    # Verify
    active_count = session.query(Whale).filter(Whale.is_copying_enabled == True).count()
    print(f"Total active whales: {active_count}")

    session.close()

if __name__ == "__main__":
    main()
