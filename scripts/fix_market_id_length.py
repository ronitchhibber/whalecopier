#!/usr/bin/env python3
"""
Fix the market_id field length issue in the database and engine.
The market_id from the orderbook is a 78-character number, but our database only allows 66 chars.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

# Database setup
DATABASE_URL = 'postgresql://trader:changeme123@localhost:5432/polymarket_trader'
engine = create_engine(DATABASE_URL)

print("=" * 80)
print("🔧 FIXING MARKET_ID FIELD LENGTH")
print("=" * 80)
print()

with engine.connect() as conn:
    # Check current column type
    result = conn.execute(text("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'trades'
        AND column_name IN ('market_id', 'token_id', 'condition_id')
    """)).fetchall()

    print("Current column definitions:")
    for col in result:
        print(f"  {col[0]}: {col[1]}({col[2]})")
    print()

    # Alter the columns to allow longer values (market IDs from orderbook are 78 chars)
    print("Updating column lengths to 100 characters...")

    try:
        # Alter market_id column
        conn.execute(text("ALTER TABLE trades ALTER COLUMN market_id TYPE VARCHAR(100)"))
        conn.commit()
        print("  ✅ Updated market_id to VARCHAR(100)")

        # Alter token_id column
        conn.execute(text("ALTER TABLE trades ALTER COLUMN token_id TYPE VARCHAR(100)"))
        conn.commit()
        print("  ✅ Updated token_id to VARCHAR(100)")

        # Alter condition_id column if it exists
        conn.execute(text("ALTER TABLE trades ALTER COLUMN condition_id TYPE VARCHAR(100)"))
        conn.commit()
        print("  ✅ Updated condition_id to VARCHAR(100)")

        print()
        print("✅ Database schema updated successfully!")

    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        conn.rollback()

    # Verify the changes
    print()
    print("Verifying updated column definitions:")
    result = conn.execute(text("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'trades'
        AND column_name IN ('market_id', 'token_id', 'condition_id')
    """)).fetchall()

    for col in result:
        print(f"  {col[0]}: {col[1]}({col[2]})")

print()
print("✅ Fix complete! Restart the copy trading engine to continue saving trades.")