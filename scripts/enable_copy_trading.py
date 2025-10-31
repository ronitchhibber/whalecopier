"""
Enable copy trading for profitable whales and configure tiers.
"""

import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def load_copy_trading_rules():
    """Load copy trading rules from config."""
    with open('config/copy_trading_rules.json', 'r') as f:
        return json.load(f)


def categorize_whale_by_pnl(pnl):
    """Categorize whale into tier based on PnL."""
    if pnl >= 100000:
        return "MEGA"
    elif pnl >= 10000:
        return "LARGE"
    elif pnl >= 1000:
        return "MEDIUM"
    else:
        return "SMALL"


def enable_copy_trading():
    """Enable copy trading for profitable whales and assign tiers."""
    print("\n" + "=" * 80)
    print("🚀 ENABLING COPY TRADING")
    print("=" * 80)

    # Load rules
    rules = load_copy_trading_rules()
    print(f"\n✅ Loaded copy trading rules v{rules['version']}")

    session = Session()

    # Get all whales with volume
    whales = session.query(Whale).filter(Whale.total_volume > 0).all()
    print(f"📊 Found {len(whales)} whales with trading data\n")

    # Stats
    enabled_count = 0
    mega_count = 0
    large_count = 0
    medium_count = 0

    print("=" * 80)
    print("CONFIGURING WHALES")
    print("=" * 80)

    for whale in whales:
        # Categorize by tier
        tier = categorize_whale_by_pnl(whale.total_pnl or 0)

        # Determine if auto-copy should be enabled
        if tier == "MEGA":
            whale.is_copying_enabled = True
            whale.tier = "MEGA"
            enabled_count += 1
            mega_count += 1
            status = "✅ AUTO-COPY"
        elif tier == "LARGE":
            whale.is_copying_enabled = True
            whale.tier = "LARGE"
            enabled_count += 1
            large_count += 1
            status = "✅ AUTO-COPY"
        elif tier == "MEDIUM":
            whale.is_copying_enabled = False  # Require manual approval
            whale.tier = "MEDIUM"
            medium_count += 1
            status = "⏸️  MANUAL"
        else:
            whale.is_copying_enabled = False
            whale.tier = "SMALL"
            status = "⏭️  DISABLED"

        # Calculate quality score (simplified)
        if whale.total_volume and whale.total_volume > 0:
            roi = (whale.total_pnl / whale.total_volume) if whale.total_volume else 0
            # Score from 0-10 based on PnL and ROI
            pnl_score = min(whale.total_pnl / 100000 * 5, 5)  # Up to 5 points for PnL
            roi_score = min(roi * 5, 5)  # Up to 5 points for ROI
            whale.quality_score = pnl_score + roi_score
        else:
            whale.quality_score = 0

        whale.is_active = True
        whale.updated_at = datetime.utcnow()

        # Print status
        name = whale.pseudonym[:20] if whale.pseudonym else whale.address[:20]
        pnl = f"${whale.total_pnl:,.0f}" if whale.total_pnl else "$0"
        print(f"{status} [{tier:6}] {name:<22} | PnL: {pnl:<12} | Score: {whale.quality_score:.2f}")

    # Commit changes
    session.commit()

    print("\n" + "=" * 80)
    print("✅ COPY TRADING ENABLED")
    print("=" * 80)
    print(f"Total whales configured: {len(whales)}")
    print(f"Auto-copy enabled: {enabled_count}")
    print()
    print(f"🦑 MEGA whales (auto-copy): {mega_count}")
    print(f"🐋 LARGE whales (auto-copy): {large_count}")
    print(f"🐟 MEDIUM whales (manual): {medium_count}")

    # Show top whales for copy trading
    print("\n" + "=" * 80)
    print("🏆 TOP 10 WHALES FOR COPY TRADING")
    print("=" * 80)

    top_whales = session.query(Whale).filter(
        Whale.is_copying_enabled == True
    ).order_by(Whale.quality_score.desc()).limit(10).all()

    print(f"{'Rank':<6} {'Name':<22} {'Tier':<8} {'Score':<8} {'PnL':<15}")
    print("-" * 80)

    for i, whale in enumerate(top_whales, 1):
        name = whale.pseudonym[:20] if whale.pseudonym else whale.address[:10]
        pnl = f"${whale.total_pnl:,.0f}" if whale.total_pnl else "$0"
        print(f"{i:<6} {name:<22} {whale.tier:<8} {whale.quality_score:<8.2f} {pnl:<15}")

    # Save summary
    summary = {
        'enabled_at': datetime.utcnow().isoformat(),
        'total_whales': len(whales),
        'auto_copy_enabled': enabled_count,
        'tier_breakdown': {
            'MEGA': mega_count,
            'LARGE': large_count,
            'MEDIUM': medium_count
        },
        'top_10': [
            {
                'address': w.address,
                'pseudonym': w.pseudonym,
                'tier': w.tier,
                'score': float(w.quality_score) if w.quality_score else 0,
                'pnl': float(w.total_pnl) if w.total_pnl else 0
            }
            for w in top_whales
        ]
    }

    with open('copy_trading_status.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n💾 Saved copy trading status to: copy_trading_status.json")

    session.close()

    return enabled_count


if __name__ == "__main__":
    enabled_count = enable_copy_trading()

    print("\n" + "=" * 80)
    print("📋 NEXT STEPS")
    print("=" * 80)
    print("1. Review copy_trading_status.json for whale configuration")
    print("2. Adjust config/copy_trading_rules.json if needed")
    print("3. Start the copy trading engine to begin following whales")
    print("4. Monitor trades in real-time via dashboard")
    print()
    print("✅ Copy trading system is ready!")
