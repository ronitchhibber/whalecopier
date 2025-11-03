#!/usr/bin/env python3
"""
Create trading_config table directly
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)

# Create trading_config table
create_table_sql = """
CREATE TABLE IF NOT EXISTS trading_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    copy_trading_enabled BOOLEAN NOT NULL DEFAULT true,
    max_position_size NUMERIC(20, 2) DEFAULT 1000.0,
    max_total_exposure NUMERIC(20, 2) DEFAULT 10000.0,
    max_positions INTEGER DEFAULT 1000,
    last_modified_at TIMESTAMP NOT NULL DEFAULT NOW(),
    modified_by VARCHAR(100),
    CONSTRAINT single_row_only CHECK (id = 1)
);
"""

# Insert initial row
insert_initial_sql = """
INSERT INTO trading_config (
    id,
    copy_trading_enabled,
    max_position_size,
    max_total_exposure,
    max_positions,
    last_modified_at,
    modified_by
) VALUES (
    1,
    true,
    1000.0,
    10000.0,
    1000,
    NOW(),
    'system_init'
) ON CONFLICT (id) DO NOTHING;
"""

try:
    with engine.connect() as conn:
        # Create table
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✅ Created trading_config table")

        # Insert initial row
        conn.execute(text(insert_initial_sql))
        conn.commit()
        print("✅ Inserted initial configuration row")

        # Verify
        result = conn.execute(text("SELECT * FROM trading_config WHERE id = 1"))
        row = result.fetchone()
        if row:
            print(f"\n📊 Current configuration:")
            print(f"   Copy trading enabled: {row[1]}")
            print(f"   Max position size: ${row[2]}")
            print(f"   Max total exposure: ${row[3]}")
            print(f"   Max positions: {row[4]}")

    print("\n✅ Trading config table ready!")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
