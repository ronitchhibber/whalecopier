"""
Reset all whales to have is_copying_enabled=False, then re-enable only the profitable ones.
"""

import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

session = Session()

print("\n" + "=" * 80)
print("🔄 RESETTING COPY TRADING FLAGS")
print("=" * 80)

# First, get count
total = session.query(Whale).count()
enabled_before = session.query(Whale).filter(Whale.is_copying_enabled == True).count()

print(f"\nBefore reset:")
print(f"  Total whales: {total}")
print(f"  Whales with copy enabled: {enabled_before}")

# Reset all whales
session.query(Whale).update({
    'is_copying_enabled': False,
    'tier': None
})
session.commit()

enabled_after = session.query(Whale).filter(Whale.is_copying_enabled == True).count()

print(f"\nAfter reset:")
print(f"  Whales with copy enabled: {enabled_after}")

print("\n✅ Reset complete!")
print("=" * 80)

session.close()
