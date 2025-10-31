"""
Filter and verify whale profitability using Polymarket API.
Fetch stats for all whales and identify profitable traders.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import requests
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_whale_stats_from_api(address):
    """Fetch whale stats from Polymarket Gamma API."""
    try:
        url = f"https://gamma-api.polymarket.com/profile/{address}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            return {
                'address': address,
                'volume': float(data.get('totalVolume', 0) or 0),
                'pnl': float(data.get('pnl', 0) or 0),
                'markets_traded': int(data.get('marketsTraded', 0) or 0),
                'total_trades': int(data.get('totalTrades', 0) or 0),
                'pseudonym': data.get('pseudonym'),
                'has_data': True
            }
        else:
            return {
                'address': address,
                'volume': 0,
                'pnl': 0,
                'markets_traded': 0,
                'total_trades': 0,
                'pseudonym': None,
                'has_data': False
            }
    except Exception as e:
        return {
            'address': address,
            'volume': 0,
            'pnl': 0,
            'markets_traded': 0,
            'total_trades': 0,
            'pseudonym': None,
            'has_data': False,
            'error': str(e)
        }


def filter_profitable_whales():
    """Filter whales by profitability and update database."""
    print("\n" + "=" * 80)
    print("🔍 FILTERING PROFITABLE WHALES")
    print("=" * 80)

    session = Session()

    # Get all whales
    whales = session.query(Whale).all()
    print(f"\n📊 Total whales in database: {len(whales)}")
    print(f"⏳ Fetching stats from Polymarket API...\n")

    # Stats tracking
    profitable_whales = []
    updated_count = 0
    verified_count = 0
    no_data_count = 0

    # Process each whale
    for i, whale in enumerate(whales):
        # Fetch stats from API
        stats = get_whale_stats_from_api(whale.address)

        if stats['has_data'] and stats['volume'] > 0:
            verified_count += 1

            # Update whale in database
            whale.total_volume = stats['volume']
            whale.total_pnl = stats['pnl']
            whale.total_trades = stats['total_trades']
            whale.pseudonym = stats['pseudonym']
            whale.last_active = datetime.utcnow()

            updated_count += 1

            # Track profitable whales
            if stats['pnl'] > 0:
                profitable_whales.append({
                    'address': whale.address,
                    'pseudonym': stats['pseudonym'] or whale.address[:10],
                    'pnl': stats['pnl'],
                    'volume': stats['volume'],
                    'roi': (stats['pnl'] / stats['volume'] * 100) if stats['volume'] > 0 else 0,
                    'markets': stats['markets_traded'],
                    'trades': stats['total_trades']
                })

                status = "🐋 PROFITABLE"
            else:
                status = "📉 Losing" if stats['pnl'] < 0 else "➖ Break-even"
        else:
            no_data_count += 1
            status = "⏭️  No data"

        # Progress update
        if (i + 1) % 50 == 0:
            session.commit()
            print(f"  [{i+1:4}/{len(whales)}] Processed {i+1} whales | Verified: {verified_count} | Profitable: {len(profitable_whales)} | No data: {no_data_count}")

        # Rate limiting
        time.sleep(0.15)  # 6.7 req/s

    # Final commit
    session.commit()

    # Sort profitable whales by PnL
    profitable_whales.sort(key=lambda x: x['pnl'], reverse=True)

    # Print results
    print("\n" + "=" * 80)
    print("✅ FILTERING COMPLETE")
    print("=" * 80)
    print(f"Total whales processed: {len(whales)}")
    print(f"Whales with data: {verified_count}")
    print(f"Whales with no data: {no_data_count}")
    print(f"Database records updated: {updated_count}")
    print()
    print(f"🐋 PROFITABLE WHALES: {len(profitable_whales)}")
    print(f"📉 Losing whales: {verified_count - len(profitable_whales)}")

    if len(profitable_whales) > 0:
        print("\n" + "=" * 80)
        print("🏆 TOP 20 PROFITABLE WHALES")
        print("=" * 80)
        print(f"{'Rank':<6} {'Name':<20} {'PnL':<15} {'Volume':<15} {'ROI':<10} {'Markets':<10}")
        print("-" * 80)

        for i, whale in enumerate(profitable_whales[:20], 1):
            name = whale['pseudonym'][:18] if whale['pseudonym'] else whale['address'][:18]
            pnl_str = f"${whale['pnl']:,.0f}"
            vol_str = f"${whale['volume']:,.0f}"
            roi_str = f"{whale['roi']:.1f}%"

            print(f"{i:<6} {name:<20} {pnl_str:<15} {vol_str:<15} {roi_str:<10} {whale['markets']:<10}")

    # Save profitable whales to file
    import json
    output_file = "profitable_whales.json"
    with open(output_file, 'w') as f:
        json.dump({
            'total_profitable': len(profitable_whales),
            'total_verified': verified_count,
            'timestamp': datetime.utcnow().isoformat(),
            'whales': profitable_whales
        }, f, indent=2)

    print(f"\n💾 Saved profitable whales to: {output_file}")

    # Stats by PnL tier
    print("\n" + "=" * 80)
    print("📊 PROFITABILITY BREAKDOWN")
    print("=" * 80)

    mega_whales = [w for w in profitable_whales if w['pnl'] >= 100000]  # $100K+
    large_whales = [w for w in profitable_whales if 10000 <= w['pnl'] < 100000]  # $10K-$100K
    medium_whales = [w for w in profitable_whales if 1000 <= w['pnl'] < 10000]  # $1K-$10K
    small_profit = [w for w in profitable_whales if w['pnl'] < 1000]  # <$1K

    print(f"🦑 MEGA ($100K+):     {len(mega_whales):4} whales")
    print(f"🐋 LARGE ($10K-100K): {len(large_whales):4} whales")
    print(f"🐟 MEDIUM ($1K-10K):  {len(medium_whales):4} whales")
    print(f"🦐 SMALL (<$1K):      {len(small_profit):4} whales")

    # Volume requirements
    print("\n" + "=" * 80)
    print("📊 WHALE CRITERIA ($50K+ VOLUME)")
    print("=" * 80)

    high_volume_whales = [w for w in profitable_whales if w['volume'] >= 50000]
    print(f"Profitable whales with $50K+ volume: {len(high_volume_whales)}")

    if len(high_volume_whales) > 0:
        total_pnl = sum(w['pnl'] for w in high_volume_whales)
        avg_roi = sum(w['roi'] for w in high_volume_whales) / len(high_volume_whales)
        print(f"Combined PnL: ${total_pnl:,.0f}")
        print(f"Average ROI: {avg_roi:.2f}%")

    session.close()

    return profitable_whales


if __name__ == "__main__":
    profitable_whales = filter_profitable_whales()
