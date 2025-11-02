"""
MASSIVE WHALE DISCOVERY ENGINE - 1M TRADES
Discovers 5000+ profitable Polymarket whales by scanning 1M+ trades

Enhanced version with:
- 1M trade scan capacity
- Optimized P&L calculation
- Better progress tracking
- Batch database saves

Target: 5000 whales with:
- Volume ≥ $100K
- Profitable (P&L > $0)
- Good Sharpe ratio (>1.5)
- Public trades available

Usage: python3 scripts/massive_whale_discovery_1M.py
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

class MassiveWhaleDiscovery1M:
    """Discovers thousands of profitable whales from 1M+ trades"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.discovered_whales = {}
        self.trader_trades = defaultdict(list)
        self.total_trades_fetched = 0
        self.whales_found = 0

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

    async def discover_traders_from_trades(self, max_trades: int = 1000000):
        """Discover traders by fetching 1M+ trades"""
        print("\n" + "="*80)
        print("🚀 MASSIVE WHALE DISCOVERY ENGINE - 1M TRADES")
        print("="*80)
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

            # Progress update every 50K trades
            if self.total_trades_fetched % 50000 == 0:
                print(f"\n📊 Progress: {self.total_trades_fetched:,} trades | {len(unique_traders):,} traders")

                # Incremental analysis every 50K trades
                if self.total_trades_fetched % 100000 == 0:
                    print("🔍 Running incremental analysis...")
                    self.incremental_analysis()
                print()

            # Brief delay to avoid rate limiting
            await asyncio.sleep(0.05)  # Reduced delay for faster fetching

        print(f"\n✅ Discovery complete: {self.total_trades_fetched:,} trades from {len(unique_traders):,} unique traders")
        return unique_traders

    def analyze_trader(self, address: str, trades: list) -> dict:
        """Analyze a trader's performance with improved P&L calculation"""
        if not trades or len(trades) < CRITERIA['min_trades']:
            return None

        # Calculate metrics
        total_volume = sum(float(t.get('size', 0)) * float(t.get('price', 0)) for t in trades)

        if total_volume < CRITERIA['min_volume']:
            return None

        # Improved P&L calculation
        # Group trades by market to estimate position-level P&L
        market_positions = defaultdict(list)

        for t in trades:
            market_id = t.get('market', t.get('asset_id', 'unknown'))
            market_positions[market_id].append(t)

        total_pnl = 0
        pnl_trades = []

        for market_id, market_trades in market_positions.items():
            # Calculate position-level P&L for this market
            position = 0
            avg_price = 0

            for t in market_trades:
                side = t.get('side', 'BUY')
                size = float(t.get('size', 0))
                price = float(t.get('price', 0))

                if side == 'BUY':
                    # Buying shares
                    if position >= 0:
                        # Adding to long position
                        avg_price = ((avg_price * position) + (price * size)) / (position + size) if position > 0 else price
                        position += size
                    else:
                        # Closing short or flipping to long
                        close_size = min(size, abs(position))
                        pnl = close_size * (avg_price - price)
                        pnl_trades.append(pnl)
                        total_pnl += pnl

                        position += size
                        if position > 0:
                            avg_price = price
                else:  # SELL
                    # Selling shares
                    if position <= 0:
                        # Adding to short position
                        avg_price = ((avg_price * abs(position)) + (price * size)) / (abs(position) + size) if position < 0 else price
                        position -= size
                    else:
                        # Closing long or flipping to short
                        close_size = min(size, position)
                        pnl = close_size * (price - avg_price)
                        pnl_trades.append(pnl)
                        total_pnl += pnl

                        position -= size
                        if position < 0:
                            avg_price = price

            # Mark-to-market open position at fair value (0.5)
            if position != 0:
                mtm_pnl = position * (0.5 - avg_price)
                pnl_trades.append(mtm_pnl)
                total_pnl += mtm_pnl

        if total_pnl <= CRITERIA['min_profit']:
            return None

        # Win rate
        wins = sum(1 for pnl in pnl_trades if pnl > 0)
        win_rate = (wins / len(pnl_trades)) * 100 if pnl_trades else 0

        if win_rate < CRITERIA['min_win_rate']:
            return None

        # Sharpe ratio
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
            'quality_score': min(100, (win_rate + sharpe * 10) / 2),
        }

    def incremental_analysis(self):
        """Analyze traders incrementally and save to DB"""
        print(f"  Analyzing {len(self.trader_trades):,} traders...")

        qualified_whales = []

        for address, trades in self.trader_trades.items():
            if address in self.discovered_whales:
                continue  # Already analyzed

            whale_data = self.analyze_trader(address, trades)
            if whale_data:
                qualified_whales.append(whale_data)
                self.discovered_whales[address] = whale_data

        if qualified_whales:
            self.save_whales_to_db(qualified_whales, incremental=True)
            self.whales_found += len(qualified_whales)
            print(f"  ✅ Found {len(qualified_whales)} new whales (Total: {self.whales_found})")

    def analyze_all_traders(self):
        """Analyze all discovered traders"""
        print("\n" + "="*80)
        print("📊 FINAL TRADER PERFORMANCE ANALYSIS")
        print("="*80)

        total_traders = len(self.trader_trades)
        qualified_whales = []

        for i, (address, trades) in enumerate(self.trader_trades.items(), 1):
            if address in self.discovered_whales:
                qualified_whales.append(self.discovered_whales[address])
                continue  # Already analyzed in incremental pass

            if i % 500 == 0:
                print(f"Progress: {i:,}/{total_traders:,} traders analyzed | {len(qualified_whales)} whales found")

            whale_data = self.analyze_trader(address, trades)
            if whale_data:
                qualified_whales.append(whale_data)
                self.discovered_whales[address] = whale_data

        print(f"\n✅ Analysis complete: {len(qualified_whales):,} qualified whales")
        return qualified_whales

    def save_whales_to_db(self, whales: list, incremental: bool = False):
        """Save discovered whales to database"""
        if not incremental:
            print("\n" + "="*80)
            print("💾 SAVING WHALES TO DATABASE")
            print("="*80)

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

            if not incremental:
                print(f"✅ Saved: {saved_count} new whales")
                print(f"✅ Updated: {updated_count} existing whales")
                print(f"✅ Total: {saved_count + updated_count} whales in database")

    def print_summary(self, whales: list):
        """Print discovery summary"""
        print("\n" + "="*80)
        print("🎯 DISCOVERY SUMMARY")
        print("="*80)

        whales_sorted = sorted(whales, key=lambda x: x['total_pnl'], reverse=True)

        print(f"\nTotal Trades Scanned: {self.total_trades_fetched:,}")
        print(f"Unique Traders Found: {len(self.trader_trades):,}")
        print(f"Qualified Whales: {len(whales):,}")
        print()

        print("TOP 20 DISCOVERED WHALES:")
        print("-"*80)
        print(f"{'Whale':<25} {'Volume':>12} {'P&L':>12} {'Win%':>8} {'Sharpe':>8}")
        print("-"*80)

        for whale in whales_sorted[:20]:
            name = whale['pseudonym'][:24]
            vol = whale['total_volume']
            pnl = whale['total_pnl']
            wr = whale['win_rate']
            sr = whale['sharpe_ratio']
            print(f"{name:<25} ${vol:>11,.0f} ${pnl:>11,.0f} {wr:>7.1f}% {sr:>7.2f}")

        print("\n" + "="*80)
        print(f"✅ GOAL: {len(whales):,} / 5,000 whales discovered")
        print("="*80)

async def main():
    """Main discovery process"""
    discovery = MassiveWhaleDiscovery1M()

    # Phase 1: Discover traders from 1M trades
    print("\n🎯 GOAL: Discover 5000 whales from 1M+ trades")
    print("⏱️  Estimated time: 60-90 minutes")
    print()

    await discovery.discover_traders_from_trades(max_trades=1000000)

    # Phase 2: Final analysis of any remaining traders
    whales = discovery.analyze_all_traders()

    # Phase 3: Save final results
    if whales:
        discovery.save_whales_to_db(whales)
        discovery.print_summary(whales)
    else:
        print("\n❌ No whales found meeting criteria")

    await discovery.http_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
