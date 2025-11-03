#!/usr/bin/env python3
"""
Calculate and apply proper P&L for closed positions based on market resolutions
"""
import sys
import os
import asyncio
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Position
from src.api.polymarket_client import PolymarketClient
from dotenv import load_dotenv
import httpx

load_dotenv()

async def fetch_market_resolution(market_id: str, client: httpx.AsyncClient):
    """Fetch market resolution from Gamma API"""
    try:
        url = f"https://gamma-api.polymarket.com/markets/{market_id}"
        response = await client.get(url)

        if response.status_code == 200:
            data = response.json()
            # Market is resolved if it's closed and has an outcome
            if data.get('closed') and 'outcome' in data:
                return data.get('outcome')  # Returns 'Yes' or 'No'
        return None
    except Exception as e:
        print(f"Error fetching market {market_id}: {e}")
        return None

async def calculate_position_pnl():
    """Calculate P&L for all closed positions"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    async with httpx.AsyncClient(timeout=10.0) as client:
        with Session(engine) as session:
            # Get all closed positions with 0 realized P&L
            closed_positions = session.query(Position).filter(
                Position.status == 'CLOSED',
                Position.realized_pnl == 0.0
            ).all()

            print(f"Found {len(closed_positions)} closed positions to calculate P&L for")

            if len(closed_positions) == 0:
                print("No positions to process")
                return

            total_pnl = 0.0
            processed = 0
            won = 0
            lost = 0
            unresolved = 0

            for pos in closed_positions:
                # Fetch market resolution
                outcome = await fetch_market_resolution(pos.market_id, client)

                if outcome is None:
                    print(f"⚠️  Could not determine outcome for {pos.market_id[:16]}... - skipping")
                    unresolved += 1
                    continue

                # Calculate P&L based on outcome
                # For binary markets: winning outcome = $1.00 per share, losing = $0.00
                position_outcome = pos.outcome.upper() if pos.outcome else 'YES'
                market_outcome = outcome.upper()

                if position_outcome == market_outcome:
                    # Position won - each share is worth $1.00
                    exit_price = 1.0
                    pnl = (exit_price - float(pos.avg_entry_price)) * float(pos.size)
                    won += 1
                    status = "✅ WON"
                else:
                    # Position lost - each share is worth $0.00
                    exit_price = 0.0
                    pnl = (exit_price - float(pos.avg_entry_price)) * float(pos.size)
                    lost += 1
                    status = "❌ LOST"

                # Update position
                pos.exit_price = exit_price
                pos.realized_pnl = pnl
                total_pnl += pnl

                print(f"{status} | Market: {pos.market_id[:16]}... | Position: {position_outcome} | Outcome: {market_outcome} | P&L: ${pnl:+.2f} (${float(pos.size):.2f} @ ${float(pos.avg_entry_price):.2f} -> ${exit_price:.2f})")

                processed += 1

            # Commit all changes
            session.commit()

            print("\n" + "="*80)
            print("SUMMARY")
            print("="*80)
            print(f"Processed: {processed} positions")
            print(f"Won: {won} positions")
            print(f"Lost: {lost} positions")
            print(f"Unresolved: {unresolved} positions")
            print(f"Total Realized P&L: ${total_pnl:+.2f}")
            print("="*80)

            # Note: The paper trading balance should be updated separately
            # by querying all positions and recalculating total P&L
            print("\nNote: Run the following to update your paper balance:")
            print("  SELECT SUM(realized_pnl) FROM positions WHERE status='CLOSED';")

if __name__ == "__main__":
    asyncio.run(calculate_position_pnl())
