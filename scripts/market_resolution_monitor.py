#!/usr/bin/env python3
"""
Market Resolution Monitor
Automatically closes positions when markets resolve and calculates P&L
Updates paper trading balance with wins/losses
"""
import sys
import os
import asyncio
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Position
from dotenv import load_dotenv
import httpx

load_dotenv()

# Paper trading balance tracking (stored in file)
BALANCE_FILE = '/tmp/paper_balance.txt'
INITIAL_BALANCE = 100.0

def get_paper_balance():
    """Get current paper trading balance"""
    try:
        with open(BALANCE_FILE, 'r') as f:
            return float(f.read().strip())
    except:
        return INITIAL_BALANCE

def set_paper_balance(balance):
    """Set paper trading balance"""
    with open(BALANCE_FILE, 'w') as f:
        f.write(str(balance))

async def check_market_resolution(market_id: str, client: httpx.AsyncClient):
    """Check if a market has resolved and get the outcome"""
    try:
        url = f"https://gamma-api.polymarket.com/markets/{market_id}"
        response = await client.get(url)

        if response.status_code == 200:
            data = response.json()

            # Check if market is closed
            if data.get('closed', False):
                # Get outcome if available
                outcome = data.get('outcome')
                return {
                    'resolved': True,
                    'outcome': outcome  # 'Yes' or 'No'
                }

        return {'resolved': False, 'outcome': None}

    except Exception as e:
        return {'resolved': False, 'outcome': None}

async def resolve_positions():
    """Check all open positions and resolve those from closed markets"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    print("=" * 80)
    print("📊 MARKET RESOLUTION MONITOR")
    print("=" * 80)

    # Get current balance
    current_balance = get_paper_balance()
    starting_balance = current_balance
    print(f"Starting Balance: ${current_balance:.2f}")
    print()

    async with httpx.AsyncClient(timeout=10.0) as client:
        with Session(engine) as session:
            # Get all open positions
            open_positions = session.query(Position).filter(Position.status == 'OPEN').all()

            if not open_positions:
                print("No open positions to check")
                return

            print(f"Checking {len(open_positions)} open positions...")
            print()

            resolved_count = 0
            total_pnl = 0.0

            for pos in open_positions:
                # Check if market has resolved
                resolution = await check_market_resolution(pos.market_id, client)

                if resolution['resolved']:
                    outcome = resolution['outcome']

                    if outcome:
                        # Calculate P&L
                        position_outcome = (pos.outcome or 'YES').upper()
                        market_outcome = outcome.upper()

                        entry_price = float(pos.avg_entry_price) if pos.avg_entry_price else 0.5
                        shares = float(pos.size) if pos.size else 0.0

                        if position_outcome == market_outcome:
                            # WIN: each share worth $1.00
                            exit_price = 1.0
                            pnl = (exit_price - entry_price) * shares
                            status_icon = "✅ WIN"
                        else:
                            # LOSS: each share worth $0.00
                            exit_price = 0.0
                            pnl = (exit_price - entry_price) * shares
                            status_icon = "❌ LOSS"

                        # Update position
                        pos.status = 'CLOSED'
                        pos.closed_at = datetime.utcnow()
                        pos.exit_price = exit_price
                        pos.realized_pnl = pnl

                        # Update balance
                        current_balance += pnl
                        total_pnl += pnl

                        print(f"{status_icon} | {(pos.market_title or 'Unknown')[:50]}")
                        print(f"     Position: {position_outcome} @ ${entry_price:.2f} x {shares:.2f} shares")
                        print(f"     Outcome: {market_outcome} → Exit @ ${exit_price:.2f}")
                        print(f"     P&L: ${pnl:+.2f}")
                        print()

                        resolved_count += 1

            # Commit all changes
            if resolved_count > 0:
                session.commit()
                set_paper_balance(current_balance)

                print("=" * 80)
                print("SETTLEMENT SUMMARY")
                print("=" * 80)
                print(f"Positions Resolved: {resolved_count}")
                print(f"Total Realized P&L: ${total_pnl:+.2f}")
                print(f"Starting Balance: ${starting_balance:.2f}")
                print(f"Ending Balance: ${current_balance:.2f}")

                pct_change = ((current_balance - starting_balance) / starting_balance * 100) if starting_balance > 0 else 0
                print(f"Change: {pct_change:+.2f}%")
                print("=" * 80)
            else:
                print("No markets have resolved yet. All positions still active.")

async def monitor_loop():
    """Continuous monitoring loop"""
    print("🔄 Starting continuous market resolution monitoring...")
    print("Checking every 5 minutes for resolved markets")
    print("Press Ctrl+C to stop")
    print()

    while True:
        try:
            await resolve_positions()
            print(f"\n⏳ Next check in 5 minutes... (Press Ctrl+C to stop)")
            await asyncio.sleep(300)  # Check every 5 minutes

        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

if __name__ == "__main__":
    # Initialize balance file if doesn't exist
    if not os.path.exists(BALANCE_FILE):
        set_paper_balance(INITIAL_BALANCE)

    # Run monitor
    asyncio.run(monitor_loop())
