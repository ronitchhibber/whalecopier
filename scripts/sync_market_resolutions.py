"""
Sync Market Resolutions Script
Run daily to keep market outcomes up-to-date.

Usage:
    python3 scripts/sync_market_resolutions.py

Features:
- Fetches all markets from Polymarket
- Updates resolution status
- Reconciles whale trade outcomes
- Calculates true win rates and P&L
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.market_resolver import MarketResolver
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale
from decimal import Decimal
from datetime import datetime

async def main():
    """Sync resolutions and update whale metrics."""

    print("\n" + "="*80)
    print("🔄 MARKET RESOLUTION SYNC")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S PST')}")
    print()

    resolver = MarketResolver()

    try:
        # Step 1: Sync all market resolutions
        print("\n📥 Step 1: Syncing market resolutions from Polymarket...")
        total_markets, resolved_markets = await resolver.sync_market_resolutions(batch_size=100)

        print(f"\n✅ Synced {total_markets} markets")
        print(f"✅ {resolved_markets} markets resolved")
        print(f"📊 Resolution rate: {(resolved_markets/total_markets*100):.1f}%")

        # Step 2: Check for pending resolutions
        print("\n🔍 Step 2: Checking for pending resolutions...")
        pending = await resolver.check_pending_resolutions()

        if pending:
            print(f"⚠️  {len(pending)} markets past end date but not yet resolved")
            print(f"   These may resolve soon - check back tomorrow")
        else:
            print(f"✅ No pending resolutions")

        # Step 3: Reconcile whale trades
        print("\n🐋 Step 3: Reconciling whale trades with resolutions...")

        database_url = os.getenv('DATABASE_URL',
            'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        engine = create_engine(database_url)

        with Session(engine) as session:
            whales = session.query(Whale).all()

            print(f"Found {len(whales)} whales to reconcile")
            print()

            updated_whales = 0
            total_resolved_trades = 0

            for i, whale in enumerate(whales, 1):
                if i % 10 == 0:
                    print(f"   Progress: {i}/{len(whales)} whales...")

                # Reconcile this whale's trades
                results = await resolver.reconcile_trade_outcomes(whale.address)

                if results['wins'] + results['losses'] > 0:
                    # Update whale with TRUE win rate and P&L
                    whale.win_rate = Decimal(str(results['win_rate'] * 100))
                    whale.total_pnl = Decimal(str(results['total_pnl']))
                    whale.updated_at = datetime.now()

                    updated_whales += 1
                    total_resolved_trades += results['wins'] + results['losses']

            session.commit()

            print(f"\n✅ Updated {updated_whales} whales with true P&L")
            print(f"✅ Reconciled {total_resolved_trades} resolved trades")

        # Step 4: Summary
        print("\n" + "="*80)
        print("📊 SYNC SUMMARY")
        print("="*80)
        print(f"Markets synced:        {total_markets:,}")
        print(f"Markets resolved:      {resolved_markets:,}")
        print(f"Whales updated:        {updated_whales}")
        print(f"Trades reconciled:     {total_resolved_trades:,}")
        print(f"Pending resolutions:   {len(pending)}")
        print()
        print("✅ Sync complete!")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S PST')}")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await resolver.close()


if __name__ == "__main__":
    asyncio.run(main())
