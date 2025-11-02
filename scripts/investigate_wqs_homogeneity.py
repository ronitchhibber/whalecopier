"""
Investigate WQS Homogeneity Issue
Checks if 38 whales really have identical scores or if there's a calculation/data issue.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Trade
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')


def main():
    """Investigate WQS homogeneity."""
    print("=" * 100)
    print("🔍 INVESTIGATING WQS HOMOGENEITY ISSUE")
    print("=" * 100)
    print()

    engine = create_engine(DATABASE_URL)
    session = Session(engine)

    try:
        # Get all qualified whales (WQS >= 70)
        qualified_whales = session.query(Whale).filter(
            Whale.quality_score >= 70.0,
            Whale.total_trades >= 20,
            Whale.total_volume >= 10000,
            Whale.win_rate >= 52.0,
            Whale.sharpe_ratio >= 0.8
        ).order_by(Whale.quality_score.desc()).all()

        print(f"Found {len(qualified_whales)} qualified whales")
        print()

        # Group by WQS and Sharpe
        wqs_distribution = {}
        sharpe_distribution = {}

        for whale in qualified_whales:
            wqs = float(whale.quality_score)
            sharpe = float(whale.sharpe_ratio)

            if wqs not in wqs_distribution:
                wqs_distribution[wqs] = 0
            wqs_distribution[wqs] += 1

            if sharpe not in sharpe_distribution:
                sharpe_distribution[sharpe] = 0
            sharpe_distribution[sharpe] += 1

        print("WQS DISTRIBUTION:")
        print("-" * 100)
        for wqs in sorted(wqs_distribution.keys(), reverse=True):
            count = wqs_distribution[wqs]
            print(f"  WQS {wqs:>6.1f}: {count:>3} whales ({count/len(qualified_whales)*100:>5.1f}%)")
        print()

        print("SHARPE DISTRIBUTION:")
        print("-" * 100)
        for sharpe in sorted(sharpe_distribution.keys(), reverse=True):
            count = sharpe_distribution[sharpe]
            print(f"  Sharpe {sharpe:>6.2f}: {count:>3} whales ({count/len(qualified_whales)*100:>5.1f}%)")
        print()

        # Check score_components JSONB field for detailed breakdown
        print("DETAILED WQS COMPONENTS (First 10 Whales):")
        print("-" * 100)

        for i, whale in enumerate(qualified_whales[:10], 1):
            print(f"\n{i}. {whale.address[:10]}... (WQS: {whale.quality_score}, Sharpe: {whale.sharpe_ratio})")
            print(f"   Trades: {whale.total_trades}, Volume: ${float(whale.total_volume):,.0f}, Win Rate: {float(whale.win_rate):.1f}%")

            if whale.score_components:
                print(f"   Score Components: {whale.score_components}")
            else:
                print("   ❌ No score_components data!")

        # Check if there's variation in the underlying stats
        print()
        print("=" * 100)
        print("UNDERLYING STATS VARIATION:")
        print("=" * 100)
        print()

        stats = []
        for whale in qualified_whales:
            stats.append({
                'address': whale.address[:10],
                'wqs': float(whale.quality_score),
                'sharpe': float(whale.sharpe_ratio),
                'calmar': float(whale.calmar_ratio) if whale.calmar_ratio else 0,
                'sortino': float(whale.sortino_ratio) if whale.sortino_ratio else 0,
                'win_rate': float(whale.win_rate),
                'total_trades': whale.total_trades,
                'total_volume': float(whale.total_volume),
                'total_pnl': float(whale.total_pnl) if whale.total_pnl else 0,
            })

        df = pd.DataFrame(stats)

        print("STATISTICS SUMMARY:")
        print(df.describe())
        print()

        # Check for unique values
        print("UNIQUE VALUES:")
        print(f"  Unique WQS values:     {df['wqs'].nunique()}")
        print(f"  Unique Sharpe values:  {df['sharpe'].nunique()}")
        print(f"  Unique Calmar values:  {df['calmar'].nunique()}")
        print(f"  Unique Win Rate vals:  {df['win_rate'].nunique()}")
        print()

        # Show whales with WQS != 100
        non_perfect = df[df['wqs'] != 100.0]
        if len(non_perfect) > 0:
            print(f"WHALES WITH WQS != 100.0 ({len(non_perfect)} found):")
            print("-" * 100)
            print(non_perfect.to_string(index=False))
        else:
            print("⚠️  ALL QUALIFIED WHALES HAVE WQS = 100.0!")
            print("This suggests WQS calculation may be capping at 100 or not differentiating properly.")
        print()

        # Investigation conclusion
        print("=" * 100)
        print("🔍 INVESTIGATION CONCLUSION:")
        print("=" * 100)
        print()

        if len(wqs_distribution) == 1 and 100.0 in wqs_distribution:
            print("❌ ISSUE CONFIRMED: All qualified whales have identical WQS = 100.0")
            print()
            print("Possible causes:")
            print("  1. WQS calculation is capping at 100 maximum")
            print("  2. score_components JSONB field is not being populated")
            print("  3. Enhanced WQS calculator not being used during whale discovery")
            print("  4. Default/placeholder values being assigned instead of calculated scores")
            print()
            print("Recommended fixes:")
            print("  1. Re-run Enhanced WQS calculation on all qualified whales")
            print("  2. Check massive_whale_discovery.py to ensure it's using calculate_enhanced_wqs()")
            print("  3. Verify score_components is being stored in database")
            print("  4. Consider using raw component scores (Sharpe, IR, Calmar) for differentiation")

        elif df['sharpe'].nunique() == 1:
            print("❌ ISSUE CONFIRMED: All qualified whales have identical Sharpe = 4.50")
            print()
            print("This suggests Sharpe ratio calculation may have a fixed value or cap.")
            print()
            print("Recommended fix:")
            print("  Re-calculate Sharpe ratios from raw trade P&L data")

        else:
            print("✅ NO MAJOR ISSUE: WQS and Sharpe show proper variation across whales")

        print()
        print("=" * 100)

    finally:
        session.close()


if __name__ == "__main__":
    main()
