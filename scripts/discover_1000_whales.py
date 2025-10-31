"""
Automated discovery of 1000+ Polymarket whales

Multi-source discovery strategy:
1. PolygonScan: Top interactors with CTF Exchange (500+ addresses)
2. CLOB Trades: Active traders from recent markets (1000+ addresses)
3. High-volume markets: Extract all participants (500+ addresses)
4. Parallel enrichment with API
5. Statistical filtering for quality
6. Database insertion with deduplication

Run: python scripts/discover_1000_whales.py

Estimated time: 30-60 minutes for 1000 whales
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Set, Optional
from collections import defaultdict, Counter
from decimal import Decimal
import statistics

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.models import Base, Whale, Platform
from dotenv import load_dotenv

load_dotenv()

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY', '')
POLYGONSCAN_BASE = "https://api.polygonscan.com/api"

CTF_EXCHANGE = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
NEG_RISK_CTF_EXCHANGE = "0xc5d563a36ae78145c45a50134d48a1215220f80a"

# Relaxed criteria for 1000 whales (can tighten later)
WHALE_CRITERIA = {
    "min_volume": 50000,         # $50k (lower for more whales)
    "min_win_rate": 55,          # 55% (lower for more whales)
    "min_sharpe": 1.2,           # 1.2 (lower for more whales)
    "min_trades": 20,            # 20 trades
    "min_profit": 1000,          # $1k profit
    "consistency_threshold": 0.6 # 60% profitable months
}

# Progress tracking
PROGRESS_FILE = "whale_discovery_progress.json"


class MassWhaleDiscovery:
    """Discovers 1000+ whales using multi-source parallel approach"""

    def __init__(self, target_count: int = 1000):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.data_api_base = "https://data-api.polymarket.com"
        self.gamma_api_base = "https://gamma-api.polymarket.com"

        self.target_count = target_count
        self.discovered_addresses: Set[str] = set()
        self.qualified_whales: List[Dict] = []
        self.processed_addresses: Set[str] = set()

        self.semaphore = asyncio.Semaphore(10)  # Rate limiting

    async def discover_from_polygonscan(self) -> Set[str]:
        """
        Discover addresses from PolygonScan CTF Exchange interactions.

        Target: 500-1000 addresses
        """
        print("\n" + "="*80)
        print("METHOD 1: POLYGONSCAN BLOCKCHAIN ANALYSIS")
        print("="*80)

        addresses = set()

        try:
            # Method 1a: Recent transactions to CTF Exchange
            print("\n🔍 Fetching recent CTF Exchange transactions...")

            for page in range(1, 11):  # 10 pages = 10,000 transactions
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": CTF_EXCHANGE,
                    "page": page,
                    "offset": 1000,
                    "sort": "desc"
                }

                if POLYGONSCAN_API_KEY:
                    params["apikey"] = POLYGONSCAN_API_KEY

                try:
                    response = await self.http_client.get(POLYGONSCAN_BASE, params=params)
                    data = response.json()

                    if data.get("status") == "1" and data.get("result"):
                        for tx in data["result"]:
                            addr = tx.get("from", "").lower()
                            if addr and addr != CTF_EXCHANGE.lower():
                                addresses.add(addr)

                        print(f"  Page {page}: +{len(data['result'])} txs (total addresses: {len(addresses)})")
                    else:
                        print(f"  Page {page}: No more data")
                        break

                    await asyncio.sleep(0.2)  # Rate limiting

                except Exception as e:
                    print(f"  ⚠️  Page {page} error: {e}")

            # Method 1b: Neg Risk CTF Exchange
            print(f"\n🔍 Fetching Neg Risk CTF Exchange transactions...")

            for page in range(1, 6):  # 5 pages
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": NEG_RISK_CTF_EXCHANGE,
                    "page": page,
                    "offset": 1000,
                    "sort": "desc"
                }

                if POLYGONSCAN_API_KEY:
                    params["apikey"] = POLYGONSCAN_API_KEY

                try:
                    response = await self.http_client.get(POLYGONSCAN_BASE, params=params)
                    data = response.json()

                    if data.get("status") == "1" and data.get("result"):
                        for tx in data["result"]:
                            addr = tx.get("from", "").lower()
                            if addr and addr != NEG_RISK_CTF_EXCHANGE.lower():
                                addresses.add(addr)

                        print(f"  Page {page}: +{len(data['result'])} txs (total addresses: {len(addresses)})")

                    await asyncio.sleep(0.2)

                except Exception as e:
                    print(f"  ⚠️  Page {page} error: {e}")

        except Exception as e:
            print(f"❌ PolygonScan error: {e}")

        print(f"\n✅ PolygonScan: Found {len(addresses)} unique addresses")
        return addresses

    async def discover_from_clob_trades(self) -> Set[str]:
        """
        Discover addresses from CLOB recent trades.

        Target: 500-1000 addresses
        """
        print("\n" + "="*80)
        print("METHOD 2: CLOB RECENT TRADES")
        print("="*80)

        addresses = set()

        print("\n📡 Fetching recent trades from all markets...")

        # Fetch many pages of trades
        for page in range(1, 51):  # 50 pages = 5,000 trades
            try:
                response = await self.http_client.get(
                    f"{self.data_api_base}/trades",
                    params={"limit": 100, "offset": (page-1) * 100}
                )

                if response.status_code != 200:
                    print(f"  ⚠️  Page {page}: Status {response.status_code}")
                    break

                trades = response.json()

                if not trades:
                    print(f"  ⏹  Page {page}: No more trades")
                    break

                for trade in trades:
                    maker = trade.get("maker_address", trade.get("maker", ""))
                    taker = trade.get("taker_address", trade.get("taker", ""))

                    if maker:
                        addresses.add(maker.lower())
                    if taker:
                        addresses.add(taker.lower())

                if page % 10 == 0:
                    print(f"  Page {page}: Total addresses: {len(addresses)}")

                await asyncio.sleep(0.3)  # Rate limiting

            except Exception as e:
                print(f"  ⚠️  Page {page} error: {e}")

        print(f"\n✅ CLOB Trades: Found {len(addresses)} unique addresses")
        return addresses

    async def discover_from_markets(self) -> Set[str]:
        """
        Discover addresses from high-volume markets.

        Target: 200-500 addresses
        """
        print("\n" + "="*80)
        print("METHOD 3: HIGH-VOLUME MARKETS")
        print("="*80)

        addresses = set()

        try:
            # Get popular markets
            print("\n📡 Fetching popular markets...")

            response = await self.http_client.get(
                f"{self.gamma_api_base}/markets",
                params={"closed": "false", "limit": 50}
            )

            if response.status_code != 200:
                print(f"  ⚠️  Markets API: Status {response.status_code}")
                return addresses

            markets = response.json()

            print(f"  Found {len(markets)} active markets")

            # For each market, get trades to find participants
            for i, market in enumerate(markets[:20], 1):  # Top 20 markets
                market_id = market.get("condition_id")
                market_question = market.get("question", "Unknown")[:50]

                if not market_id:
                    continue

                print(f"\n  [{i}/20] {market_question}...")

                try:
                    # Get trades for this market
                    response = await self.http_client.get(
                        f"{self.data_api_base}/trades",
                        params={"market": market_id, "limit": 100}
                    )

                    if response.status_code == 200:
                        trades = response.json()

                        for trade in trades:
                            maker = trade.get("maker_address", trade.get("maker", ""))
                            taker = trade.get("taker_address", trade.get("taker", ""))

                            if maker:
                                addresses.add(maker.lower())
                            if taker:
                                addresses.add(taker.lower())

                        print(f"    +{len(trades)} trades (total addresses: {len(addresses)})")

                    await asyncio.sleep(0.5)

                except Exception as e:
                    print(f"    ⚠️  Error: {e}")

        except Exception as e:
            print(f"❌ Markets error: {e}")

        print(f"\n✅ Markets: Found {len(addresses)} unique addresses")
        return addresses

    async def enrich_address_batch(self, addresses: List[str]) -> List[Dict]:
        """Enrich a batch of addresses in parallel"""

        tasks = []
        for address in addresses:
            if address not in self.processed_addresses:
                tasks.append(self.enrich_single_address(address))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        qualified = []
        for result in results:
            if isinstance(result, dict) and result.get("is_qualified"):
                qualified.append(result)

        return qualified

    async def enrich_single_address(self, address: str) -> Optional[Dict]:
        """Enrich a single address with rate limiting"""

        async with self.semaphore:  # Rate limiting
            if address in self.processed_addresses:
                return None

            self.processed_addresses.add(address)

            try:
                response = await self.http_client.get(
                    f"{self.data_api_base}/activity",
                    params={"user": address, "limit": 200}
                )

                if response.status_code != 200:
                    return None

                data = response.json()

                if not data or len(data) == 0:
                    return None

                # Extract profile
                first_entry = data[0]
                pseudonym = first_entry.get("name", first_entry.get("pseudonym", f"{address[:8]}..."))

                # Calculate stats
                stats = self.calculate_stats(data)

                # Check if qualified
                if not self.is_qualified(stats):
                    return None

                whale_data = {
                    "address": address,
                    "pseudonym": pseudonym,
                    "total_volume": stats["total_volume"],
                    "total_trades": stats["total_trades"],
                    "total_pnl": stats.get("total_pnl", 0),
                    "win_rate": stats["win_rate"],
                    "sharpe_ratio": stats.get("sharpe_ratio", 0),
                    "quality_score": self.calculate_quality_score(stats),
                    "is_qualified": True
                }

                return whale_data

            except Exception as e:
                return None

    def calculate_stats(self, activity_data: List[Dict]) -> Dict:
        """Calculate trading statistics from activity data"""

        total_volume = 0
        trades = []
        monthly_pnl = defaultdict(float)

        for activity in activity_data:
            activity_type = activity.get("type", "")

            if activity_type in ["buy", "sell"]:
                price = float(activity.get("price", 0))
                shares = float(activity.get("shares", 0))
                value = price * shares
                total_volume += value
                trades.append({"value": value, "side": activity_type})

            elif activity_type == "redeem":
                payout = float(activity.get("payout", 0))
                timestamp = activity.get("timestamp", "")

                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        month_key = dt.strftime("%Y-%m")
                        monthly_pnl[month_key] += payout
                    except:
                        pass

        # Win rate
        winning_months = sum(1 for pnl in monthly_pnl.values() if pnl > 0)
        total_months = len(monthly_pnl) if monthly_pnl else 1
        win_rate = (winning_months / total_months) * 100 if total_months > 0 else 0

        # Sharpe ratio
        if monthly_pnl and len(monthly_pnl) > 1:
            returns = list(monthly_pnl.values())
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe = 0

        # Consistency
        consistency = (winning_months / total_months) if total_months > 0 else 0

        # Total PnL
        total_pnl = sum(monthly_pnl.values())

        return {
            "total_volume": total_volume,
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "consistency_score": consistency
        }

    def is_qualified(self, stats: Dict) -> bool:
        """Check if meets whale criteria"""
        return (
            stats["total_volume"] >= WHALE_CRITERIA["min_volume"] and
            stats["total_trades"] >= WHALE_CRITERIA["min_trades"] and
            stats["win_rate"] >= WHALE_CRITERIA["min_win_rate"] and
            stats.get("sharpe_ratio", 0) >= WHALE_CRITERIA["min_sharpe"] and
            stats.get("total_pnl", 0) >= WHALE_CRITERIA["min_profit"] and
            stats.get("consistency_score", 0) >= WHALE_CRITERIA["consistency_threshold"]
        )

    def calculate_quality_score(self, stats: Dict) -> float:
        """Calculate quality score (0-100)"""

        volume_score = min(25, (stats["total_volume"] / 1000000) * 5)
        sharpe_score = min(25, stats.get("sharpe_ratio", 0) * 10)
        win_rate_score = (stats["win_rate"] / 100) * 25
        consistency_score = stats.get("consistency_score", 0) * 25

        return round(volume_score + sharpe_score + win_rate_score + consistency_score, 2)

    async def save_to_database(self, whales: List[Dict], session: AsyncSession):
        """Save whales to database"""

        saved_count = 0

        for whale_data in whales:
            try:
                # Check if exists
                result = await session.execute(
                    select(Whale).where(Whale.address == whale_data["address"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    continue

                # Create new whale
                whale = Whale(
                    address=whale_data["address"],
                    pseudonym=whale_data["pseudonym"],
                    platform=Platform.POLYMARKET,
                    total_volume=Decimal(str(whale_data["total_volume"])),
                    total_pnl=Decimal(str(whale_data.get("total_pnl", 0))),
                    total_trades=whale_data["total_trades"],
                    win_rate=Decimal(str(whale_data["win_rate"])),
                    sharpe_ratio=Decimal(str(whale_data.get("sharpe_ratio", 0))),
                    quality_score=Decimal(str(whale_data["quality_score"])),
                    tier=self.get_tier(whale_data["quality_score"]),
                    rank=999,
                    is_active=True,
                    is_copying_enabled=True,
                    edge_status='active'
                )

                session.add(whale)
                saved_count += 1

            except Exception as e:
                print(f"  ⚠️  Error saving {whale_data.get('pseudonym')}: {e}")

        await session.commit()
        return saved_count

    def get_tier(self, score: float) -> str:
        """Determine tier from quality score"""
        if score >= 80:
            return "MEGA"
        elif score >= 65:
            return "HIGH"
        else:
            return "MEDIUM"

    def save_progress(self):
        """Save progress to file"""
        progress = {
            "timestamp": datetime.now().isoformat(),
            "discovered_addresses": list(self.discovered_addresses),
            "processed_addresses": list(self.processed_addresses),
            "qualified_whales_count": len(self.qualified_whales)
        }

        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, indent=2)

    def load_progress(self):
        """Load progress from file"""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)
                self.discovered_addresses = set(progress.get("discovered_addresses", []))
                self.processed_addresses = set(progress.get("processed_addresses", []))
                print(f"  Loaded progress: {len(self.discovered_addresses)} addresses discovered, "
                      f"{len(self.processed_addresses)} processed")

    async def close(self):
        await self.http_client.aclose()


async def main():
    """Main discovery workflow"""

    print("\n" + "="*80)
    print("MASS WHALE DISCOVERY - TARGET: 1000 WHALES")
    print("="*80)

    print(f"\n📋 Relaxed Criteria for Volume:")
    print(f"  • Min Volume: ${WHALE_CRITERIA['min_volume']:,}")
    print(f"  • Min Win Rate: {WHALE_CRITERIA['min_win_rate']}%")
    print(f"  • Min Sharpe: {WHALE_CRITERIA['min_sharpe']}")
    print(f"  • Min Trades: {WHALE_CRITERIA['min_trades']}")
    print(f"  • Min Profit: ${WHALE_CRITERIA['min_profit']:,}")

    discovery = MassWhaleDiscovery(target_count=1000)

    # Load previous progress if exists
    discovery.load_progress()

    try:
        # Step 1: Discover addresses from all sources
        print("\n" + "="*80)
        print("PHASE 1: ADDRESS DISCOVERY")
        print("="*80)

        # Run all discovery methods in parallel
        polygonscan_task = discovery.discover_from_polygonscan()
        clob_task = discovery.discover_from_clob_trades()
        markets_task = discovery.discover_from_markets()

        results = await asyncio.gather(
            polygonscan_task,
            clob_task,
            markets_task,
            return_exceptions=True
        )

        # Combine all addresses
        for result in results:
            if isinstance(result, set):
                discovery.discovered_addresses.update(result)

        print(f"\n" + "="*80)
        print(f"✅ TOTAL UNIQUE ADDRESSES DISCOVERED: {len(discovery.discovered_addresses)}")
        print("="*80)

        if len(discovery.discovered_addresses) < 1000:
            print(f"\n⚠️  Warning: Only found {len(discovery.discovered_addresses)} addresses")
            print("Will process all available addresses")

        # Step 2: Enrich and qualify addresses
        print("\n" + "="*80)
        print("PHASE 2: ENRICHMENT & QUALIFICATION")
        print("="*80)

        all_addresses = list(discovery.discovered_addresses)
        batch_size = 50
        total_batches = (len(all_addresses) + batch_size - 1) // batch_size

        print(f"\nProcessing {len(all_addresses)} addresses in {total_batches} batches of {batch_size}...")

        for i in range(0, len(all_addresses), batch_size):
            batch = all_addresses[i:i+batch_size]
            batch_num = i // batch_size + 1

            print(f"\n[Batch {batch_num}/{total_batches}] Processing {len(batch)} addresses...")

            qualified = await discovery.enrich_address_batch(batch)

            if qualified:
                discovery.qualified_whales.extend(qualified)
                print(f"  ✅ +{len(qualified)} qualified whales (Total: {len(discovery.qualified_whales)})")

            # Save progress periodically
            if batch_num % 5 == 0:
                discovery.save_progress()
                print(f"  💾 Progress saved")

            # Stop if we have enough
            if len(discovery.qualified_whales) >= discovery.target_count:
                print(f"\n🎯 Reached target of {discovery.target_count} whales!")
                break

        # Step 3: Save to database
        print("\n" + "="*80)
        print("PHASE 3: DATABASE INSERTION")
        print("="*80)

        if discovery.qualified_whales:
            engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            async with async_session() as session:
                saved_count = await discovery.save_to_database(discovery.qualified_whales, session)
                print(f"\n✅ Saved {saved_count} new whales to database")

            await engine.dispose()

            # Print summary
            print("\n" + "="*80)
            print("DISCOVERY SUMMARY")
            print("="*80)
            print(f"Addresses Discovered: {len(discovery.discovered_addresses):,}")
            print(f"Addresses Processed: {len(discovery.processed_addresses):,}")
            print(f"Qualified Whales: {len(discovery.qualified_whales):,}")
            print(f"Saved to Database: {saved_count:,}")

            # Tier breakdown
            tier_counts = Counter(discovery.get_tier(w["quality_score"]) for w in discovery.qualified_whales)
            print(f"\nTier Breakdown:")
            print(f"  MEGA:   {tier_counts['MEGA']:,}")
            print(f"  HIGH:   {tier_counts['HIGH']:,}")
            print(f"  MEDIUM: {tier_counts['MEDIUM']:,}")

            # Top 10
            print(f"\nTop 10 Whales by Quality Score:")
            print("-"*80)
            sorted_whales = sorted(discovery.qualified_whales, key=lambda x: x["quality_score"], reverse=True)
            for i, whale in enumerate(sorted_whales[:10], 1):
                print(f"{i:2d}. {whale['pseudonym'][:25]:25s} - Score: {whale['quality_score']:5.1f} - "
                      f"${whale['total_volume']:>12,.0f} - WR: {whale['win_rate']:4.1f}%")

        else:
            print("\n⚠️  No qualified whales found")
            print("Try lowering WHALE_CRITERIA thresholds")

    finally:
        discovery.save_progress()
        await discovery.close()

    print("\n" + "="*80)
    print("✅ MASS DISCOVERY COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
