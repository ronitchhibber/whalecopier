"""
Check Database Statistics
Quick script to see current whale and trade counts.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.models import Whale, Trade
from sqlalchemy import func


def main():
    db = next(get_db_session())

    try:
        # Count trades
        total_trades = db.query(func.count(Trade.id)).scalar()

        # Count whales
        total_whales = db.query(func.count(Whale.id)).scalar()
        elite_whales = db.query(func.count(Whale.id)).filter(Whale.quality_score >= 80).scalar()
        good_whales = db.query(func.count(Whale.id)).filter(Whale.quality_score >= 70).scalar()

        # Sum volumes and P&L
        total_volume = db.query(func.sum(Whale.total_volume)).scalar() or 0
        total_pnl = db.query(func.sum(Whale.total_pnl)).scalar() or 0

        # Get top whales
        top_whales = db.query(Whale).order_by(Whale.quality_score.desc()).limit(5).all()

        print("=" * 80)
        print("📊 DATABASE STATISTICS")
        print("=" * 80)
        print()
        print(f"Total Trades:         {total_trades:,}")
        print(f"Total Whales:         {total_whales:,}")
        print(f"  Elite (WQS ≥80):    {elite_whales:,}")
        print(f"  Good (WQS ≥70):     {good_whales:,}")
        print()
        print(f"Total Volume:         ${total_volume:,.2f}")
        print(f"Total P&L:            ${total_pnl:,.2f}")
        print()
        print("TOP 5 WHALES BY WQS:")
        print("-" * 80)
        print(f"{'Address':<45} {'WQS':>6} {'Sharpe':>8} {'P&L':>15}")
        print("-" * 80)

        for whale in top_whales:
            short_address = f"{whale.address[:6]}...{whale.address[-4:]}"
            print(f"{short_address:<45} {whale.quality_score:>6.1f} {whale.sharpe_ratio:>8.2f} ${whale.total_pnl:>14,.2f}")

        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
