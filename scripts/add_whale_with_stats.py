"""
Add a whale with specific statistics from manual observation.
Use this when collecting whales from the leaderboard webpage.
"""

import os
import sys
import argparse
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def add_whale_with_stats(address, pseudonym, volume, pnl, win_rate, sharpe, trades):
    """Add a whale with specific statistics."""

    with Session(engine) as session:
        # Check if exists
        existing = session.query(Whale).filter(Whale.address == address).first()

        if existing:
            print(f"Whale {address} already exists. Updating stats...")
            whale = existing
        else:
            from eth_utils import to_checksum_address
            try:
                checksummed = to_checksum_address(address)
            except:
                checksummed = address

            whale = Whale(
                address=checksummed,
                pseudonym=pseudonym or f"Whale_{checksummed[2:10]}",
                is_copying_enabled=True,
                last_active=datetime.utcnow()
            )
            session.add(whale)

        # Update stats
        whale.total_volume = volume
        whale.total_pnl = pnl
        whale.win_rate = win_rate
        whale.sharpe_ratio = sharpe
        whale.total_trades = trades

        # Determine tier
        if volume > 50000000:  # >$50M
            whale.tier = 'MEGA'
            whale.quality_score = 90.0
        elif volume > 5000000:  # >$5M
            whale.tier = 'HIGH'
            whale.quality_score = 75.0
        elif volume > 500000:  # >$500k
            whale.tier = 'MEDIUM'
            whale.quality_score = 65.0
        else:
            whale.tier = 'MEDIUM'
            whale.quality_score = 55.0

        session.commit()

        print(f"\n✅ {'Updated' if existing else 'Added'} whale:")
        print(f"   Address: {whale.address}")
        print(f"   Name: {whale.pseudonym}")
        print(f"   Tier: {whale.tier}")
        print(f"   Volume: ${whale.total_volume:,.0f}")
        print(f"   P&L: ${whale.total_pnl:,.0f}")
        print(f"   Win Rate: {whale.win_rate}%")
        print(f"   Sharpe: {whale.sharpe_ratio}")
        print(f"   Quality Score: {whale.quality_score}")

        return whale


def main():
    parser = argparse.ArgumentParser(
        description='Add a whale with specific statistics',
        epilog='''
Examples:
  # Add a MEGA whale
  python3 scripts/add_whale_with_stats.py 0x1234... --pseudonym "TopTrader" \\
    --volume 25000000 --pnl 8000000 --win-rate 68 --sharpe 2.1 --trades 5000

  # Add a HIGH whale
  python3 scripts/add_whale_with_stats.py 0x5678... --pseudonym "GoodTrader" \\
    --volume 7500000 --pnl 450000 --win-rate 61 --sharpe 1.7 --trades 2000

Collect stats from: https://polymarket.com/leaderboard
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('address', help='Ethereum address (0x...)')
    parser.add_argument('--pseudonym', default=None, help='Trader name/pseudonym')
    parser.add_argument('--volume', type=float, required=True, help='Total volume in USD')
    parser.add_argument('--pnl', type=float, required=True, help='Total P&L in USD')
    parser.add_argument('--win-rate', type=float, default=55.0, help='Win rate percentage (default: 55)')
    parser.add_argument('--sharpe', type=float, default=1.2, help='Sharpe ratio (default: 1.2)')
    parser.add_argument('--trades', type=int, default=100, help='Total trades (default: 100)')

    args = parser.parse_args()

    # Validate address
    if not args.address.startswith('0x') or len(args.address) != 42:
        print("❌ Invalid Ethereum address format")
        sys.exit(1)

    # Add whale
    add_whale_with_stats(
        args.address.lower(),
        args.pseudonym,
        args.volume,
        args.pnl,
        args.win_rate,
        args.sharpe,
        args.trades
    )

    print(f"\n🌐 View in dashboard: http://localhost:8000/dashboard")


if __name__ == "__main__":
    main()
