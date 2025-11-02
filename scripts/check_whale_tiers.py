"""
Quick check of whale tiers in database.
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

# Get whales with copy trading enabled
whales = session.query(Whale).filter(
    Whale.is_copying_enabled == True
).order_by(Whale.total_pnl.desc().nullslast()).all()

print(f"\nTotal whales with is_copying_enabled=True: {len(whales)}\n")

print(f"{'Name':<25} {'Tier':<8} {'PnL':<15} {'Volume':<15}")
print("-" * 70)

for whale in whales[:20]:
    name = whale.pseudonym[:23] if whale.pseudonym else whale.address[:10]
    pnl = f"${whale.total_pnl:,.0f}" if whale.total_pnl else "$0"
    vol = f"${whale.total_volume:,.0f}" if whale.total_volume else "$0"
    tier = whale.tier or "N/A"
    print(f"{name:<25} {tier:<8} {pnl:<15} {vol:<15}")

session.close()
