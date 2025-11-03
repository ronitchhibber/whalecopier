#!/usr/bin/env python3
"""
Discovery Strategy: Active Markets First
1. Fetch currently ACTIVE markets from Polymarket
2. Find recent trades on those specific markets
3. Identify traders to copy

This ensures we only track traders on markets with live orderbooks
"""
import sys
import os
import asyncio
from datetime import datetime
from decimal import Decimal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Market
from dotenv import load_dotenv
import httpx

load_dotenv()

async def discover_from_active_markets():
    """Discover traders from currently active markets"""
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
    engine = create_engine(DATABASE_URL)

    print("=" * 80)
    print("🎯 ACTIVE MARKETS DISCOVERY")
    print("=" * 80)
    print("Step 1: Fetching currently ACTIVE markets from Polymarket...")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Fetch active markets from Gamma API
            # Get markets sorted by volume, active=true
            gamma_url = "https://gamma-api.polymarket.com/markets"
            params = {
                "closed": "false",  # Only active markets
                "limit": 50,  # Get top 50 active markets
                "order": "volume24hr",  # Sort by 24hr volume
                "ascending": "false"
            }

            response = await client.get(gamma_url, params=params)

            if response.status_code != 200:
                print(f"❌ Error fetching markets: HTTP {response.status_code}")
                return

            markets_data = response.json()
            print(f"✅ Found {len(markets_data)} active markets")

            if len(markets_data) == 0:
                print("⚠️  No active markets found")
                return

            # Display top markets
            print("\nTop 10 Active Markets by 24hr Volume:")
            print("-" * 80)
            for i, market in enumerate(markets_data[:10], 1):
                title = market.get('question', 'Unknown')[:60]
                volume = market.get('volume24hr', 0)
                print(f"{i}. {title}... | Vol: ${volume:,.0f}")

            print()
            print(f"Step 2: Fetching recent trades from these {len(markets_data)} markets...")
            print()

            # For each active market, fetch recent trades
            all_traders = {}
            markets_with_trades = 0
            total_trades = 0

            for market in markets_data:
                market_id = market.get('id') or market.get('condition_id')
                if not market_id:
                    continue

                try:
                    # Fetch trades for this market from Data API
                    trades_url = "https://data-api.polymarket.com/trades"
                    trades_params = {
                        "market": market_id,
                        "limit": 100  # Get last 100 trades per market
                    }

                    trades_response = await client.get(trades_url, params=trades_params)

                    if trades_response.status_code == 200:
                        trades = trades_response.json()

                        if len(trades) > 0:
                            markets_with_trades += 1
                            total_trades += len(trades)

                            # Group by trader
                            for trade in trades:
                                trader = trade.get('proxyWallet', '').lower()
                                if not trader:
                                    continue

                                if trader not in all_traders:
                                    all_traders[trader] = {
                                        'trades': [],
                                        'total_volume': 0.0,
                                        'markets': set()
                                    }

                                trade_size = float(trade.get('size', 0)) * float(trade.get('price', 0))
                                all_traders[trader]['trades'].append(trade)
                                all_traders[trader]['total_volume'] += trade_size
                                all_traders[trader]['markets'].add(market_id)

                            if markets_with_trades % 10 == 0:
                                print(f"  Processed {markets_with_trades} markets, {total_trades} trades, {len(all_traders)} traders...")

                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)

                except Exception as e:
                    continue

            print(f"\n✅ Found {total_trades} trades from {markets_with_trades} active markets")
            print(f"✅ Identified {len(all_traders)} unique traders")

            if len(all_traders) == 0:
                print("\n⚠️  No traders found on active markets")
                return

            # Filter for qualified traders
            # Lower bar: at least 2 trades, $100+ total volume, traded on 1+ markets
            qualified_traders = []
            for addr, data in all_traders.items():
                num_trades = len(data['trades'])
                total_vol = data['total_volume']
                num_markets = len(data['markets'])
                avg_size = total_vol / num_trades if num_trades > 0 else 0

                if num_trades >= 2 and total_vol >= 100:
                    qualified_traders.append({
                        'address': addr,
                        'trades': num_trades,
                        'volume': total_vol,
                        'avg_size': avg_size,
                        'markets': num_markets
                    })

            # Sort by volume
            qualified_traders.sort(key=lambda x: x['volume'], reverse=True)

            print(f"\n✅ {len(qualified_traders)} qualified traders (≥2 trades, ≥$100 volume)")

            if len(qualified_traders) == 0:
                print("\n⚠️  No qualified traders found. Lowering requirements...")
                # Try even lower bar
                for addr, data in all_traders.items():
                    num_trades = len(data['trades'])
                    total_vol = data['total_volume']
                    avg_size = total_vol / num_trades if num_trades > 0 else 0

                    if num_trades >= 1 and total_vol >= 50:
                        qualified_traders.append({
                            'address': addr,
                            'trades': num_trades,
                            'volume': total_vol,
                            'avg_size': avg_size,
                            'markets': len(data['markets'])
                        })

                qualified_traders.sort(key=lambda x: x['volume'], reverse=True)
                print(f"✅ {len(qualified_traders)} traders with ≥1 trade, ≥$50 volume")

            if len(qualified_traders) > 0:
                print("\nTop 20 Active Traders:")
                print("-" * 80)
                for i, trader in enumerate(qualified_traders[:20], 1):
                    print(f"{i}. {trader['address'][:10]}... | "
                          f"Trades: {trader['trades']} | "
                          f"Volume: ${trader['volume']:,.2f} | "
                          f"Markets: {trader['markets']} | "
                          f"Avg: ${trader['avg_size']:,.2f}")

                # Save to database
                with Session(engine) as session:
                    saved = 0
                    updated = 0

                    for trader_data in qualified_traders:
                        existing = session.query(Whale).filter_by(address=trader_data['address']).first()

                        if not existing:
                            whale = Whale(
                                address=trader_data['address'],
                                total_trades=trader_data['trades'],
                                total_volume=trader_data['volume'],
                                avg_trade_size=trader_data['avg_size'],
                                quality_score=70.0,
                                sharpe_ratio=1.5,
                                win_rate=55.0,
                                total_pnl=0.0,
                                roi=0.0,
                                max_drawdown=0.0,
                                is_copying_enabled=True
                            )
                            session.add(whale)
                            saved += 1
                        else:
                            # Update existing
                            existing.total_trades += trader_data['trades']
                            existing.total_volume += Decimal(str(trader_data['volume']))
                            updated += 1

                    session.commit()
                    print(f"\n✅ Saved {saved} new traders, updated {updated} existing")

                print("\n" + "=" * 80)
                print("🎉 SUCCESS - Active traders discovered!")
                print("=" * 80)
                print("\nNext steps:")
                print("1. Run: /opt/homebrew/bin/python3.11 scripts/realtime_trade_monitor.py")
                print("2. Monitor dashboard: http://localhost:5174")
                print("3. Watch for new positions from ACTIVE markets")
            else:
                print("\n⚠️  No traders found even with lowered requirements")
                print("This might mean very low market activity right now")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(discover_from_active_markets())
