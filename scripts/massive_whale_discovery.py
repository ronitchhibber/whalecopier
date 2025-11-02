"""
MASSIVE WHALE DISCOVERY ENGINE
Discovers 5000+ profitable Polymarket whales

Target: 5000 whales with:
- Volume ≥ $100K
- Profitable (P&L > $0)
- Good Sharpe ratio (>1.5)
- Public trades available

Strategy:
1. Fetch ALL recent trades from Data API (100K+ trades)
2. Extract unique trader addresses
3. Analyze each trader's complete history
4. Filter by profitability, volume, Sharpe
5. Store to database

Usage: python3 scripts/massive_whale_discovery.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from collections import defaultdict
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from libs.common.models import Whale, Platform
from dotenv import load_dotenv
import statistics

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
DATA_API = "https://data-api.polymarket.com"

# Discovery criteria
CRITERIA = {
    "min_volume": 100000,      # $100K+ volume
    "min_profit": 0,           # Must be profitable
    "min_sharpe": 1.5,         # Good risk-adjusted returns
    "min_trades": 30,          # Statistical significance
    "min_win_rate": 55,        # Better than coinflip
}

class MassiveWhaleDiscovery:
    """Discovers thousands of profitable whales"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.discovered_whales = {}
        self.trader_trades = defaultdict(list)
        self.total_trades_fetched = 0

    async def fetch_batch_trades(self, offset: int, limit: int = 1000):
        """Fetch a batch of trades from Data API"""
        try:
            url = f"{DATA_API}/trades"
            params = {"limit": limit, "offset": offset}
            response = await self.http_client.get(url, params=params)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Error {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            print(f"❌ Fetch error at offset {offset}: {e}")
            return []

    async def discover_traders_from_trades(self, max_trades: int = 100000):
        """Discover traders by fetching massive amounts of trades"""
        print("\n" + "=" * 80)
        print("🚀 MASSIVE WHALE DISCOVERY ENGINE")
        print("=" * 80)
        print(f"Target: 5000 whales | Scanning: {max_trades:,} trades")
        print()

        offset = 0
        batch_size = 1000
        unique_traders = set()

        while self.total_trades_fetched < max_trades:
            print(f"📥 Fetching trades {offset:,} - {offset+batch_size:,}...", end=" ")

            trades = await self.fetch_batch_trades(offset, batch_size)

            if not trades or len(trades) == 0:
                print("⚠️  No more trades available")
                break

            # Extract trader addresses and store their trades
            for trade in trades:
                trader_addr = trade.get('proxyWallet', '').lower()
                if trader_addr and trader_addr not in ('', '0x'):
                    unique_traders.add(trader_addr)
                    self.trader_trades[trader_addr].append(trade)

            self.total_trades_fetched += len(trades)
            print(f"✅ {len(trades)} trades | {len(unique_traders):,} unique traders")

            offset += batch_size

            # Progress update every 10K trades
            if self.total_trades_fetched % 10000 == 0:
                print(f"\n📊 Progress: {self.total_trades_fetched:,} trades | {len(unique_traders):,} traders\n")

            # Brief delay to avoid rate limiting
            await asyncio.sleep(0.1)

        print(f"\n✅ Discovery complete: {self.total_trades_fetched:,} trades from {len(unique_traders):,} unique traders")
        return unique_traders

    def analyze_trader(self, address: str, trades: list) -> dict:
        """Analyze a trader's performance"""
        if not trades or len(trades) < CRITERIA['min_trades']:
            return None

        # Calculate metrics
        total_volume = sum(float(t.get('size', 0)) * float(t.get('price', 0)) for t in trades)

        if total_volume < CRITERIA['min_volume']:
            return None

        # P&L calculation (simplified - assumes all positions closed at fair value)
        pnl_trades = []
        for t in trades:
            side = t.get('side', 'BUY')
            size = float(t.get('size', 0))
            price = float(t.get('price', 0))

            # Simplified P&L: assume winning if bought low (<0.5) or sold high (>0.5)
            if side == 'BUY' and price < 0.5:
                pnl = size * (0.5 - price)  # Profit if price rises to fair value
            elif side == 'SELL' and price > 0.5:
                pnl = size * (price - 0.5)  # Profit if price falls to fair value
            else:
                pnl = -size * abs(price - 0.5) * 0.5  # Loss estimate

            pnl_trades.append(pnl)

        total_pnl = sum(pnl_trades)

        if total_pnl <= CRITERIA['min_profit']:
            return None

        # Win rate
        wins = sum(1 for pnl in pnl_trades if pnl > 0)
        win_rate = (wins / len(pnl_trades)) * 100 if pnl_trades else 0

        if win_rate < CRITERIA['min_win_rate']:
            return None

        # Sharpe ratio (simplified)
        if len(pnl_trades) > 1:
            avg_pnl = statistics.mean(pnl_trades)
            std_pnl = statistics.stdev(pnl_trades) if len(pnl_trades) > 1 else 1
            sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0
        else:
            sharpe = 0

        if sharpe < CRITERIA['min_sharpe']:
            return None

        # Qualified whale!
        return {
            'address': address,
            'pseudonym': trades[0].get('pseudonym', trades[0].get('name', address[:10])),
            'total_volume': total_volume,
            'total_trades': len(trades),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe,
            'platform': Platform.POLYMARKET,
            'quality_score': min(100, (win_rate + sharpe * 10) / 2),  # Composite score
        }

    def analyze_all_traders(self):
        """Analyze all discovered traders"""
        print("\n" + "=" * 80)
        print("📊 ANALYZING TRADER PERFORMANCE")
        print("=" * 80)

        total_traders = len(self.trader_trades)
        qualified_whales = []

        for i, (address, trades) in enumerate(self.trader_trades.items(), 1):
            if i % 100 == 0:
                print(f"Progress: {i:,}/{total_traders:,} traders analyzed | {len(qualified_whales)} whales found")

            whale_data = self.analyze_trader(address, trades)
            if whale_data:
                qualified_whales.append(whale_data)
                self.discovered_whales[address] = whale_data

        print(f"\n✅ Analysis complete: {len(qualified_whales):,} qualified whales")
        return qualified_whales

    def save_whales_to_db(self, whales: list):
        """Save discovered whales to database"""
        print("\n" + "=" * 80)
        print("💾 SAVING WHALES TO DATABASE")
        print("=" * 80)

        engine = create_engine(DATABASE_URL)

        with Session(engine) as session:
            saved_count = 0
            updated_count = 0

            for whale_data in whales:
                # Check if whale already exists
                existing = session.query(Whale).filter(
                    Whale.address == whale_data['address']
                ).first()

                if existing:
                    # Update existing whale
                    existing.total_volume = Decimal(str(whale_data['total_volume']))
                    existing.total_trades = whale_data['total_trades']
                    existing.total_pnl = Decimal(str(whale_data['total_pnl']))
                    existing.win_rate = Decimal(str(whale_data['win_rate']))
                    existing.sharpe_ratio = Decimal(str(whale_data['sharpe_ratio']))
                    existing.quality_score = Decimal(str(whale_data['quality_score']))
                    existing.is_copying_enabled = True
                    existing.updated_at = datetime.now()
                    updated_count += 1
                else:
                    # Create new whale
                    whale = Whale(
                        address=whale_data['address'],
                        pseudonym=whale_data['pseudonym'],
                        platform=whale_data['platform'],
                        total_volume=Decimal(str(whale_data['total_volume'])),
                        total_trades=whale_data['total_trades'],
                        total_pnl=Decimal(str(whale_data['total_pnl'])),
                        win_rate=Decimal(str(whale_data['win_rate'])),
                        sharpe_ratio=Decimal(str(whale_data['sharpe_ratio'])),
                        quality_score=Decimal(str(whale_data['quality_score'])),
                        is_active=True,
                        is_copying_enabled=True,
                        tier="MEGA" if whale_data['quality_score'] >= 80 else "LARGE",
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    session.add(whale)
                    saved_count += 1

            session.commit()
            print(f"✅ Saved: {saved_count} new whales")
            print(f"✅ Updated: {updated_count} existing whales")
            print(f"✅ Total: {saved_count + updated_count} whales in database")

    def print_summary(self, whales: list):
        """Print discovery summary"""
        print("\n" + "=" * 80)
        print("🎯 DISCOVERY SUMMARY")
        print("=" * 80)

        whales_sorted = sorted(whales, key=lambda x: x['total_pnl'], reverse=True)

        print(f"\nTotal Trades Scanned: {self.total_trades_fetched:,}")
        print(f"Unique Traders Found: {len(self.trader_trades):,}")
        print(f"Qualified Whales: {len(whales):,}")
        print()

        print("TOP 20 DISCOVERED WHALES:")
        print("-" * 80)
        print(f"{'Whale':<25} {'Volume':>12} {'P&L':>12} {'Win%':>8} {'Sharpe':>8}")
        print("-" * 80)

        for whale in whales_sorted[:20]:
            name = whale['pseudonym'][:24]
            vol = whale['total_volume']
            pnl = whale['total_pnl']
            wr = whale['win_rate']
            sr = whale['sharpe_ratio']
            print(f"{name:<25} ${vol:>11,.0f} ${pnl:>11,.0f} {wr:>7.1f}% {sr:>7.2f}")

        print("\n" + "=" * 80)
        print(f"✅ GOAL: {len(whales):,} / 5,000 whales discovered")
        print("=" * 80)

async def main():
    """Main discovery process"""
    discovery = MassiveWhaleDiscovery()

    # Phase 1: Discover traders from trades
    await discovery.discover_traders_from_trades(max_trades=100000)  # Scan 100K trades

    # Phase 2: Analyze trader performance
    whales = discovery.analyze_all_traders()

    # Phase 3: Save to database
    if whales:
        discovery.save_whales_to_db(whales)
        discovery.print_summary(whales)
    else:
        print("\n❌ No whales found meeting criteria")

    await discovery.http_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
