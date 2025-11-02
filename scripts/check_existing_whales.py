"""Quick script to check existing whale stats in database."""

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

# Get whales with stats
whales_with_volume = session.query(Whale).filter(Whale.total_volume > 0).order_by(Whale.total_pnl.desc()).limit(50).all()

print("\n" + "=" * 80)
print(f"WHALES WITH VOLUME DATA: {len(whales_with_volume)}")
print("=" * 80)

if whales_with_volume:
    print(f"{'Address':<44} {'Volume':<15} {'PnL':<15} {'Pseudonym':<20}")
    print("-" * 100)
    for whale in whales_with_volume:
        vol = f"${whale.total_volume:,.0f}" if whale.total_volume else "$0"
        pnl = f"${whale.total_pnl:,.0f}" if whale.total_pnl else "$0"
        name = whale.pseudonym[:18] if whale.pseudonym else "N/A"
        print(f"{whale.address:<44} {vol:<15} {pnl:<15} {name:<20}")

# Total stats
total_whales = session.query(Whale).count()
whales_with_data = session.query(Whale).filter(Whale.total_volume > 0).count()
whales_no_data = total_whales - whales_with_data

print(f"\n📊 SUMMARY:")
print(f"Total whales: {total_whales}")
print(f"With volume data: {whales_with_data}")
print(f"Without data: {whales_no_data}")

session.close()
