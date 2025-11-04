#!/usr/bin/env python3
"""
Apply trading_config table migration to fix kill switch functionality.

This script fixes the trading_config table schema to match the TradingConfig model.
It reads the DATABASE_URL from Railway environment variables.

Usage:
    python3 scripts/apply_trading_config_migration.py
"""

import os
import sys
import psycopg2
from pathlib import Path

def main():
    # Get DATABASE_URL from environment
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("\nPlease set your Railway DATABASE_URL:")
        print("  export DATABASE_URL='postgresql://postgres:...@...railway.app/railway'")
        sys.exit(1)

    print("🔄 Applying trading_config migration...")
    print(f"   Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")

    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        # Read migration SQL
        migration_file = Path(__file__).parent / 'migrations' / '001_fix_trading_config.sql'
        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Execute migration
        print("\n📝 Executing migration SQL...")
        cur.execute(migration_sql)

        # Commit changes
        conn.commit()

        # Verify the result
        print("\n✅ Verifying migration...")
        cur.execute("""
            SELECT
                id,
                copy_trading_enabled,
                max_position_size,
                max_total_exposure,
                max_positions,
                modified_by
            FROM trading_config
            WHERE id = 1;
        """)
        result = cur.fetchone()

        if result:
            print(f"\n✅ Migration applied successfully!")
            print(f"\n   Trading Config (id={result[0]}):")
            print(f"   • Copy Trading: {'ENABLED' if result[1] else 'DISABLED'}")
            print(f"   • Max Position: ${result[2]}")
            print(f"   • Max Exposure: ${result[3]}")
            print(f"   • Max Positions: {result[4]}")
            print(f"   • Modified By: {result[5]}")
            print(f"\n🎉 Kill switch is now functional!")
            print(f"   Test it at: https://whalecopier-production.up.railway.app")
        else:
            print("\n⚠️  WARNING: No trading_config row found after migration")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ Migration file not found: {migration_file}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
