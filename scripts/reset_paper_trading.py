#!/usr/bin/env python3
"""
Reset Paper Trading Account
- Delete all positions (open and closed)
- Reset balance to initial amount
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from libs.common.models import Position
from dotenv import load_dotenv

load_dotenv()

def reset_paper_trading():
    """Reset paper trading account to fresh state"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    with Session(engine) as session:
        # Count positions before deletion
        total_positions = session.query(Position).count()
        open_positions = session.query(Position).filter(Position.status == 'OPEN').count()
        closed_positions = session.query(Position).filter(Position.status == 'CLOSED').count()

        print("="*80)
        print("PAPER TRADING ACCOUNT RESET")
        print("="*80)
        print(f"Current Positions:")
        print(f"  - Total: {total_positions}")
        print(f"  - Open: {open_positions}")
        print(f"  - Closed: {closed_positions}")
        print()

        # Delete all positions
        if total_positions > 0:
            session.query(Position).delete()
            session.commit()
            print(f"✅ Deleted {total_positions} positions")
        else:
            print("ℹ️  No positions to delete")

        print()
        print("Paper Trading Account Reset Complete!")
        print("="*80)
        print("Starting fresh with:")
        print("  - Balance: $100.00 (configured in realtime_trade_monitor.py)")
        print("  - Positions: 0")
        print("  - P&L: $0.00")
        print()
        print("Ready to start copy-trading!")
        print("="*80)

if __name__ == "__main__":
    confirm = input("⚠️  This will DELETE ALL paper trading positions. Continue? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        reset_paper_trading()
    else:
        print("Reset cancelled.")
