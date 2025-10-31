"""
Remove whales with placeholder/baseline stats.
Keep only whales with real verified statistics.
"""

import os
import sys
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.common.models import Whale
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)


def clean_baseline_whales(auto_confirm=False):
    """Remove whales with baseline/estimated stats."""
    print("\n" + "="*80)
    print("🧹 CLEANING WHALES WITH FAKE STATS")
    print("="*80)

    with Session(engine) as session:
        # Find whales with baseline stats (55% win rate, $100k volume, etc.)
        fake_whales = session.query(Whale).filter(
            Whale.total_volume == 100000,
            Whale.win_rate == 55.0,
            Whale.sharpe_ratio == 1.2
        ).all()

        print(f"\n📊 Found {len(fake_whales)} whales with baseline stats")

        if not fake_whales:
            print("✅ No fake whales to remove!")
            return 0

        # Show what will be kept
        real_whales = session.query(Whale).filter(
            (Whale.total_volume != 100000) |
            (Whale.win_rate != 55.0) |
            (Whale.sharpe_ratio != 1.2)
        ).all()

        print(f"\n✅ Will KEEP {len(real_whales)} whales with real stats:")
        for whale in real_whales:
            print(f"   • {whale.pseudonym}: ${whale.total_volume:,.0f} vol, {whale.win_rate}% WR, {whale.tier} tier")

        print(f"\n❌ Will REMOVE {len(fake_whales)} whales with fake stats")

        # Confirm
        if not auto_confirm:
            response = input("\n⚠️  Continue? This will delete whales from database. (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return 0
        else:
            print("\n⚠️  Auto-confirm enabled, proceeding with cleanup...")

        # Delete fake whales
        for whale in fake_whales:
            session.delete(whale)

        session.commit()

        print(f"\n✅ Removed {len(fake_whales)} whales")
        print(f"✅ Kept {len(real_whales)} whales with real stats")

        return len(fake_whales)


def main():
    parser = argparse.ArgumentParser(
        description='Remove whales with placeholder/baseline stats',
        epilog='Examples:\n'
               '  python3 scripts/clean_fake_whales.py         # Interactive mode\n'
               '  python3 scripts/clean_fake_whales.py --yes   # Auto-confirm',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Auto-confirm deletion without prompting')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("🎯 CLEAN FAKE WHALE STATS")
    print("="*80)
    print("\nThis will remove all whales with baseline/estimated stats")
    print("and keep only whales with real verified statistics.")

    removed = clean_baseline_whales(auto_confirm=args.yes)

    if removed > 0:
        with Session(engine) as session:
            remaining = session.query(Whale).count()

        print(f"\n" + "="*80)
        print("✅ CLEANUP COMPLETE")
        print("="*80)
        print(f"Removed: {removed} whales")
        print(f"Remaining: {remaining} whales")
        print(f"\n🌐 Dashboard: http://localhost:8000/dashboard")
        print("\n📝 Next steps:")
        print("1. Dashboard now shows only real whales")
        print("2. Add more whales manually from https://polymarket.com/leaderboard")
        print("3. Use: python3 scripts/add_whale_with_stats.py")


if __name__ == "__main__":
    main()
