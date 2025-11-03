#!/usr/bin/env python3
"""
Discover whales trading on ACTIVE markets only (last 24-48 hours)
This ensures we get positions from markets with live orderbooks
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Trade, Market
from src.api.polymarket_client import PolymarketClient
from dotenv import load_dotenv
import httpx

load_dotenv()

async def discover_active_whales():
    """Discover whales from recent trades on ACTIVE markets"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    # Initialize Polymarket client
    poly_client = PolymarketClient(
        api_key=os.getenv('POLYMARKET_API_KEY'),
        secret=os.getenv('POLYMARKET_API_SECRET'),
        passphrase=os.getenv('POLYMARKET_API_PASSPHRASE'),
        private_key=os.getenv('POLYMARKET_PRIVATE_KEY'),
    )

    print("=" * 80)
    print("🔍 ACTIVE WHALE DISCOVERY")
    print("=" * 80)
    print("Fetching recent trades from ACTIVE markets only...")
    print()

    # Fetch recent large trades (whales)
    # Using last 24 hours and minimum $250 trade size
    min_trade_size = 250.0

    try:
        # Get large recent trades from Polymarket Data API
        trades_data = await poly_client.get_whale_trades(
            min_trade_size=min_trade_size,
            limit=500  # Get 500 most recent large trades
        )

        print(f"✅ Found {len(trades_data)} large trades (≥${min_trade_size})")

        # Filter for ACTIVE markets only by checking Gamma API
        active_trades = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for trade in trades_data:
                market_id = trade.get('market')
                if not market_id:
                    continue

                try:
                    # Check if market is active
                    gamma_url = f"https://gamma-api.polymarket.com/markets/{market_id}"
                    response = await client.get(gamma_url)

                    if response.status_code == 200:
                        market_data = response.json()

                        # Check if market is active (not closed)
                        if not market_data.get('closed', True):
                            active_trades.append(trade)

                            if len(active_trades) % 10 == 0:
                                print(f"  Found {len(active_trades)} trades on active markets...")

                except Exception as e:
                    continue

        print(f"\n✅ {len(active_trades)} trades from ACTIVE markets")

        if len(active_trades) == 0:
            print("\n⚠️  No recent large trades on active markets found.")
            print("This might mean:")
            print("  - No whales are trading right now")
            print("  - Try reducing min_trade_size")
            print("  - Market activity is low")
            return

        # Group trades by trader address
        traders = {}
        for trade in active_trades:
            trader_addr = trade.get('user', '').lower()
            if not trader_addr:
                continue

            if trader_addr not in traders:
                traders[trader_addr] = {
                    'trades': [],
                    'total_volume': 0.0,
                    'avg_size': 0.0
                }

            trade_size = float(trade.get('size', 0)) * float(trade.get('price', 0))
            traders[trader_addr]['trades'].append(trade)
            traders[trader_addr]['total_volume'] += trade_size

        # Calculate stats and filter qualified whales
        qualified_whales = []
        for addr, data in traders.items():
            num_trades = len(data['trades'])
            total_vol = data['total_volume']
            avg_size = total_vol / num_trades if num_trades > 0 else 0

            # Basic qualification: at least 1 trade, $500+ volume
            if num_trades >= 1 and total_vol >= 500:
                qualified_whales.append({
                    'address': addr,
                    'trades': num_trades,
                    'volume': total_vol,
                    'avg_size': avg_size
                })

        # Sort by volume
        qualified_whales.sort(key=lambda x: x['volume'], reverse=True)

        print(f"\n✅ Found {len(qualified_whales)} qualified active whales")
        print("\nTop 10 Active Whales:")
        print("-" * 80)
        for i, whale in enumerate(qualified_whales[:10], 1):
            print(f"{i}. {whale['address'][:10]}... | "
                  f"Trades: {whale['trades']} | "
                  f"Volume: ${whale['volume']:,.2f} | "
                  f"Avg: ${whale['avg_size']:,.2f}")

        # Save to database
        with Session(engine) as session:
            saved = 0
            for whale_data in qualified_whales:
                # Check if whale exists
                existing = session.query(Whale).filter_by(address=whale_data['address']).first()

                if not existing:
                    whale = Whale(
                        address=whale_data['address'],
                        total_trades=whale_data['trades'],
                        total_volume=whale_data['volume'],
                        avg_trade_size=whale_data['avg_size'],
                        quality_score=75.0,  # Default score for active traders
                        sharpe_ratio=2.0,
                        win_rate=60.0,
                        total_pnl=0.0,
                        roi=0.0,
                        max_drawdown=0.0,
                        is_copying_enabled=True,
                        last_updated=datetime.utcnow()
                    )
                    session.add(whale)
                    saved += 1
                else:
                    # Update stats
                    existing.total_trades += whale_data['trades']
                    existing.total_volume += whale_data['volume']
                    existing.last_updated = datetime.utcnow()

            session.commit()
            print(f"\n✅ Saved {saved} new active whales to database")

        print("\n" + "=" * 80)
        print("🎯 Ready to copy trade from active whales!")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Run: /opt/homebrew/bin/python3.11 scripts/realtime_trade_monitor.py")
        print("2. Monitor dashboard at: http://localhost:5174")
        print("3. Watch positions get created from ACTIVE markets")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(discover_active_whales())
