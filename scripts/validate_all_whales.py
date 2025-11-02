"""
Validate All Qualified Whales
Checks each whale in database against production qualification criteria.

Qualification Criteria:
- Enhanced WQS >= 70 (Good tier minimum)
- Total trades >= 20 (statistical significance)
- Total volume >= $10,000 (meaningful size)
- Win rate >= 52% (edge above market)
- Sharpe ratio >= 0.8 (risk-adjusted skill)
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Trade
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')

# Production qualification criteria
QUALIFICATION_CRITERIA = {
    'min_quality_score': 70.0,     # Enhanced WQS >= 70
    'min_total_trades': 20,         # At least 20 trades
    'min_total_volume': 10000.0,    # At least $10K volume
    'min_win_rate': 52.0,           # > 52% win rate
    'min_sharpe_ratio': 0.8,        # Sharpe >= 0.8
}

def validate_whale(whale: Whale) -> dict:
    """
    Validate a single whale against qualification criteria.

    Returns:
        dict with validation results and reasons
    """
    reasons = []
    is_qualified = True

    # Check each criterion
    wqs = float(whale.quality_score) if whale.quality_score else 0
    if whale.quality_score is None or wqs < QUALIFICATION_CRITERIA['min_quality_score']:
        is_qualified = False
        reasons.append(f"❌ WQS {wqs:.1f} < {QUALIFICATION_CRITERIA['min_quality_score']}")
    else:
        reasons.append(f"✅ WQS {wqs:.1f}")

    trades = whale.total_trades if whale.total_trades else 0
    if whale.total_trades is None or trades < QUALIFICATION_CRITERIA['min_total_trades']:
        is_qualified = False
        reasons.append(f"❌ Trades {trades} < {QUALIFICATION_CRITERIA['min_total_trades']}")
    else:
        reasons.append(f"✅ Trades {trades}")

    if whale.total_volume is None or float(whale.total_volume) < QUALIFICATION_CRITERIA['min_total_volume']:
        is_qualified = False
        vol = float(whale.total_volume) if whale.total_volume else 0
        reasons.append(f"❌ Volume ${vol:,.0f} < ${QUALIFICATION_CRITERIA['min_total_volume']:,.0f}")
    else:
        reasons.append(f"✅ Volume ${float(whale.total_volume):,.0f}")

    if whale.win_rate is None or float(whale.win_rate) < QUALIFICATION_CRITERIA['min_win_rate']:
        is_qualified = False
        wr = float(whale.win_rate) if whale.win_rate else 0
        reasons.append(f"❌ Win Rate {wr:.1f}% < {QUALIFICATION_CRITERIA['min_win_rate']}%")
    else:
        reasons.append(f"✅ Win Rate {float(whale.win_rate):.1f}%")

    if whale.sharpe_ratio is None or float(whale.sharpe_ratio) < QUALIFICATION_CRITERIA['min_sharpe_ratio']:
        is_qualified = False
        sharpe = float(whale.sharpe_ratio) if whale.sharpe_ratio else 0
        reasons.append(f"❌ Sharpe {sharpe:.2f} < {QUALIFICATION_CRITERIA['min_sharpe_ratio']}")
    else:
        reasons.append(f"✅ Sharpe {float(whale.sharpe_ratio):.2f}")

    return {
        'address': whale.address,
        'short_address': f"{whale.address[:6]}...{whale.address[-4:]}",
        'is_qualified': is_qualified,
        'reasons': reasons,
        'quality_score': float(whale.quality_score) if whale.quality_score else 0,
        'tier': whale.tier,
        'total_trades': whale.total_trades,
        'total_volume': float(whale.total_volume) if whale.total_volume else 0,
        'win_rate': float(whale.win_rate) if whale.win_rate else 0,
        'sharpe_ratio': float(whale.sharpe_ratio) if whale.sharpe_ratio else 0,
        'total_pnl': float(whale.total_pnl) if whale.total_pnl else 0,
    }


def main():
    """Main validation function."""
    print("=" * 100)
    print("🐋 WHALE QUALIFICATION VALIDATION")
    print("=" * 100)
    print()
    print("Qualification Criteria:")
    print(f"  • Enhanced WQS >= {QUALIFICATION_CRITERIA['min_quality_score']}")
    print(f"  • Total Trades >= {QUALIFICATION_CRITERIA['min_total_trades']}")
    print(f"  • Total Volume >= ${QUALIFICATION_CRITERIA['min_total_volume']:,.0f}")
    print(f"  • Win Rate >= {QUALIFICATION_CRITERIA['min_win_rate']}%")
    print(f"  • Sharpe Ratio >= {QUALIFICATION_CRITERIA['min_sharpe_ratio']}")
    print()
    print("=" * 100)
    print()

    # Connect to database
    engine = create_engine(DATABASE_URL)
    session = Session(engine)

    try:
        # Get all whales, ordered by quality score
        all_whales = session.query(Whale).order_by(Whale.quality_score.desc().nullslast()).all()

        print(f"Found {len(all_whales)} whales in database")
        print()

        # Validate each whale
        results = []
        for whale in all_whales:
            validation = validate_whale(whale)
            results.append(validation)

        # Separate qualified and unqualified
        qualified = [r for r in results if r['is_qualified']]
        unqualified = [r for r in results if not r['is_qualified']]

        # Summary
        print("=" * 100)
        print("📊 VALIDATION SUMMARY")
        print("=" * 100)
        print()
        print(f"Total Whales:       {len(results):,}")
        print(f"✅ Qualified:       {len(qualified):,} ({len(qualified)/len(results)*100:.1f}%)")
        print(f"❌ Unqualified:     {len(unqualified):,} ({len(unqualified)/len(results)*100:.1f}%)")
        print()

        # Tier breakdown (for qualified whales only)
        if qualified:
            elite_count = len([r for r in qualified if r['quality_score'] >= 80])
            good_count = len([r for r in qualified if 70 <= r['quality_score'] < 80])

            print("Qualified Whale Tiers:")
            print(f"  🔥 Elite (WQS ≥80):  {elite_count:,}")
            print(f"  ⭐ Good (WQS ≥70):   {good_count:,}")
            print()

            # Stats
            avg_wqs = sum(r['quality_score'] for r in qualified) / len(qualified)
            avg_sharpe = sum(r['sharpe_ratio'] for r in qualified) / len(qualified)
            avg_win_rate = sum(r['win_rate'] for r in qualified) / len(qualified)
            total_volume = sum(r['total_volume'] for r in qualified)
            total_pnl = sum(r['total_pnl'] for r in qualified)

            print(f"Qualified Whale Stats:")
            print(f"  Avg WQS:           {avg_wqs:.1f}")
            print(f"  Avg Sharpe:        {avg_sharpe:.2f}")
            print(f"  Avg Win Rate:      {avg_win_rate:.1f}%")
            print(f"  Total Volume:      ${total_volume:,.2f}")
            print(f"  Total P&L:         ${total_pnl:,.2f}")
            print()

        # Top 10 Qualified Whales
        if qualified:
            print("=" * 100)
            print("🏆 TOP 10 QUALIFIED WHALES")
            print("=" * 100)
            print()
            print(f"{'Rank':<6} {'Address':<20} {'Tier':<6} {'WQS':>6} {'Sharpe':>8} {'Win%':>6} {'Trades':>8} {'P&L':>15}")
            print("-" * 100)

            for i, whale in enumerate(qualified[:10], 1):
                tier_emoji = "🔥" if whale['quality_score'] >= 80 else "⭐"
                print(f"#{i:<5} {whale['short_address']:<20} {tier_emoji:<6} {whale['quality_score']:>6.1f} "
                      f"{whale['sharpe_ratio']:>8.2f} {whale['win_rate']:>5.1f}% {whale['total_trades']:>8,} "
                      f"${whale['total_pnl']:>14,.2f}")
            print()

        # Unqualified Whales Report
        if unqualified:
            print("=" * 100)
            print("⚠️  UNQUALIFIED WHALES (Failing Criteria)")
            print("=" * 100)
            print()

            for i, whale in enumerate(unqualified[:20], 1):  # Show max 20
                print(f"{i}. {whale['short_address']}")
                for reason in whale['reasons']:
                    print(f"   {reason}")
                print()

            if len(unqualified) > 20:
                print(f"... and {len(unqualified) - 20} more unqualified whales")
                print()

        # Export results to CSV
        df = pd.DataFrame(results)
        df = df.sort_values('quality_score', ascending=False)
        output_file = "whale_qualification_report.csv"
        df.to_csv(output_file, index=False)

        print("=" * 100)
        print(f"✅ Validation complete! Report exported to {output_file}")
        print("=" * 100)
        print()

        # Return summary
        return {
            'total': len(results),
            'qualified': len(qualified),
            'unqualified': len(unqualified),
            'elite': elite_count if qualified else 0,
            'good': good_count if qualified else 0,
        }

    finally:
        session.close()


if __name__ == "__main__":
    main()
