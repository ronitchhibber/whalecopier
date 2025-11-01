"""
Test Polymarket CLOB API connection and verify we can fetch whale trades.
"""

import sys
import os
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

print("\n" + "=" * 80)
print("🔍 TESTING POLYMARKET API CONNECTION")
print("=" * 80)

session = Session()

# Get top 5 whales
whales = session.query(Whale).filter(
    Whale.is_copying_enabled == True
).order_by(Whale.total_pnl.desc()).limit(5).all()

print(f"\nTesting API with top 5 whales:\n")

total_trades_found = 0

for i, whale in enumerate(whales, 1):
    name = whale.pseudonym[:20] if whale.pseudonym else whale.address[:10]
    print(f"[{i}/5] {name:<22} | ", end="", flush=True)

    endpoints = [
        f"https://clob.polymarket.com/trades?maker={whale.address}",
        f"https://clob.polymarket.com/trades?taker={whale.address}"
    ]

    trades = []
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    trades.extend(data)
                    print(f".", end="", flush=True)
            else:
                print(f"E{response.status_code}", end="", flush=True)
        except Exception as e:
            print(f"X", end="", flush=True)

    # Deduplicate
    unique_trades = {}
    for trade in trades:
        trade_id = trade.get('id')
        if trade_id:
            unique_trades[trade_id] = trade

    trade_count = len(unique_trades)
    total_trades_found += trade_count

    if trade_count > 0:
        print(f" ✅ {trade_count} trades found")

        # Show sample trade
        sample = list(unique_trades.values())[0]
        print(f"     Sample: {sample.get('side', 'N/A')} {float(sample.get('size', 0)):.2f} @ {float(sample.get('price', 0)):.3f}")
        print(f"     Market: {sample.get('market', 'unknown')[:30]}")
        print(f"     Time: {sample.get('timestamp', 'unknown')}")
    else:
        print(f" ⚠️  No trades found")

print("\n" + "=" * 80)
print(f"TOTAL TRADES FOUND: {total_trades_found}")
print("=" * 80)

if total_trades_found == 0:
    print("\n⚠️  WARNING: No trades found for any whales!")
    print("This could mean:")
    print("  1. These whales haven't traded recently")
    print("  2. The CLOB API only shows certain order types")
    print("  3. Trades are cleared after a certain time period")
    print("\nLet me try a few known active addresses...")

    # Try some known active Polymarket addresses
    test_addresses = [
        "0x17db3fcd93ba12d38382a0cade24b200185c5f6d",  # fengdubiying
        "0x0bf7c1c865bdc795fe21f1e8f88dba2a7135d54f",  # Another known trader
    ]

    print("\nTesting with specific addresses:")
    for addr in test_addresses:
        print(f"\nAddress: {addr[:20]}...")
        url = f"https://clob.polymarket.com/trades?maker={addr}"
        try:
            response = requests.get(url, timeout=10)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Response type: {type(data)}")
                if isinstance(data, list):
                    print(f"  Trades count: {len(data)}")
                    if len(data) > 0:
                        print(f"  Sample trade: {json.dumps(data[0], indent=2)[:200]}...")
                elif isinstance(data, dict):
                    print(f"  Response keys: {data.keys()}")
        except Exception as e:
            print(f"  Error: {e}")

session.close()

print("\n" + "=" * 80)
print("API Test Complete")
print("=" * 80)
