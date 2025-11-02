#!/usr/bin/env python3
"""
Fix Missing Market Data
=======================
Fixes trades with missing market_id by extracting from token_id or other available fields.
Also populates market_title when possible.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from libs.common.models import Trade, Market
from datetime import datetime

# Database connection
db_url = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

def fix_missing_market_ids():
    """Fix trades with missing market_id by using condition_id or token_id."""
    session = Session()
    fixed_count = 0

    try:
        # Get trades with missing market_id
        trades_missing_market = session.query(Trade).filter(
            (Trade.market_id == None) | (Trade.market_id == '')
        ).all()

        print(f"Found {len(trades_missing_market)} trades with missing market_id")

        for trade in trades_missing_market:
            # Try to extract market_id from condition_id
            if trade.condition_id:
                trade.market_id = trade.condition_id
                fixed_count += 1
            # Try to extract from token_id (condition_id is first 66 chars of token_id)
            elif trade.token_id and len(trade.token_id) >= 66:
                trade.market_id = trade.token_id[:66]
                fixed_count += 1

            # Every 100 fixes, commit
            if fixed_count % 100 == 0 and fixed_count > 0:
                session.commit()
                print(f"  Fixed {fixed_count} trades...")

        session.commit()
        print(f"✅ Fixed {fixed_count} trades with missing market_id")

    except Exception as e:
        print(f"❌ Error fixing market_ids: {e}")
        session.rollback()
    finally:
        session.close()

    return fixed_count

def populate_market_titles():
    """Populate market_title field in trades by looking up from markets table."""
    session = Session()
    updated_count = 0

    try:
        # Get trades with missing market_title
        trades_missing_title = session.query(Trade).filter(
            (Trade.market_title == None) | (Trade.market_title == '')
        ).limit(1000).all()  # Process in batches

        print(f"Found {len(trades_missing_title)} trades with missing market_title")

        for trade in trades_missing_title:
            if not trade.market_id:
                continue

            # Look up market
            market = session.query(Market).filter(
                (Market.condition_id == trade.market_id) |
                (Market.condition_id == trade.condition_id)
            ).first()

            if market and market.question:
                trade.market_title = market.question
                updated_count += 1

            # Commit every 100 updates
            if updated_count % 100 == 0 and updated_count > 0:
                session.commit()
                print(f"  Updated {updated_count} trade titles...")

        session.commit()
        print(f"✅ Updated {updated_count} trades with market titles")

    except Exception as e:
        print(f"❌ Error updating titles: {e}")
        session.rollback()
    finally:
        session.close()

    return updated_count

def fix_duplicate_trades():
    """Remove duplicate trades based on transaction_hash."""
    session = Session()

    try:
        # Find duplicates
        result = session.execute(text("""
            SELECT transaction_hash, COUNT(*) as count
            FROM trades
            WHERE transaction_hash IS NOT NULL
            GROUP BY transaction_hash
            HAVING COUNT(*) > 1
        """))

        duplicates = result.fetchall()

        if duplicates:
            print(f"Found {len(duplicates)} duplicate transaction hashes")

            for tx_hash, count in duplicates:
                # Keep only the first trade, delete others
                trades = session.query(Trade).filter(
                    Trade.transaction_hash == tx_hash
                ).order_by(Trade.created_at).all()

                # Delete all but the first
                for trade in trades[1:]:
                    session.delete(trade)

            session.commit()
            print(f"✅ Removed duplicate trades")
        else:
            print("✅ No duplicate trades found")

    except Exception as e:
        print(f"❌ Error removing duplicates: {e}")
        session.rollback()
    finally:
        session.close()

def update_whale_trade_flags():
    """Update is_whale_trade flag based on trader_address."""
    session = Session()

    try:
        # Update all trades to set is_whale_trade flag correctly
        result = session.execute(text("""
            UPDATE trades
            SET is_whale_trade = true
            WHERE trader_address IN (SELECT address FROM whales)
            AND is_whale_trade = false
        """))

        updated = result.rowcount
        session.commit()

        print(f"✅ Updated {updated} trades with correct whale flag")

    except Exception as e:
        print(f"❌ Error updating whale flags: {e}")
        session.rollback()
    finally:
        session.close()

def get_statistics():
    """Get current statistics after fixes."""
    session = Session()

    try:
        stats = session.execute(text("""
            SELECT
                COUNT(*) as total_trades,
                COUNT(CASE WHEN market_id IS NOT NULL AND market_id != '' THEN 1 END) as has_market_id,
                COUNT(CASE WHEN market_title IS NOT NULL AND market_title != '' THEN 1 END) as has_title,
                COUNT(CASE WHEN is_whale_trade = true THEN 1 END) as whale_trades,
                COUNT(CASE WHEN followed = true THEN 1 END) as followed_trades
            FROM trades
        """)).fetchone()

        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Total trades: {stats[0]}")
        print(f"Has market_id: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
        print(f"Has market_title: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
        print(f"Whale trades: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
        print(f"Followed trades: {stats[4]} ({stats[4]/stats[0]*100:.1f}%)")

    except Exception as e:
        print(f"❌ Error getting statistics: {e}")
    finally:
        session.close()

def main():
    print("=" * 60)
    print("FIXING MISSING MARKET DATA")
    print("=" * 60)
    print()

    # Fix missing market_ids
    print("Step 1: Fixing missing market_ids...")
    fix_missing_market_ids()
    print()

    # Populate market titles
    print("Step 2: Populating market titles...")
    populate_market_titles()
    print()

    # Remove duplicates
    print("Step 3: Removing duplicate trades...")
    fix_duplicate_trades()
    print()

    # Update whale flags
    print("Step 4: Updating whale trade flags...")
    update_whale_trade_flags()
    print()

    # Show final statistics
    get_statistics()

    print("\n✅ Data fixes complete!")

if __name__ == '__main__':
    main()