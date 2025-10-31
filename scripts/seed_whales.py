"""
Whale Discovery & Database Seeding Script

Discovers and seeds the database with top Polymarket whales based on:
1. Trading volume (BIG TRADERS)
2. Profitability (EXTREMELY PROFITABLE)
3. Consistency (WIN RATE + STABLE RETURNS)
4. Famous whales (Théo, etc.)

Run: python scripts/seed_whales.py
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.models import Base, Whale, WalletCluster, Platform, Sector
from dotenv import load_dotenv

load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
# Convert to async URL
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')


# ============================================================================
# FAMOUS WHALES - Manually Curated from Public Sources
# ============================================================================
#
# NOTE: Only Fredi9999 has confirmed full address. Other Théo cluster members
# (Theo4, PrincessCaro, Michie) have addresses that are not publicly disclosed.
# To add more whales, you can:
# 1. Find their profile on polymarket.com/profile/[address]
# 2. Use the Data API: https://data-api.polymarket.com/activity?user=[address]
# 3. Monitor PolygonScan for high-volume CTF Exchange transactions
# 4. Use Arkham Intelligence or Nansen for wallet clustering
#
# ============================================================================

FAMOUS_WHALES = [
    # ========================================================================
    # TIER 1: MEGA WHALES ($1M+ profit) - CONFIRMED ADDRESSES
    # ========================================================================
    {
        "address": "0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf",  # Fredi9999 (CONFIRMED)
        "pseudonym": "Fredi9999",
        "tier": "MEGA",
        "notes": "Part of Théo's cluster - $26M+ profit on Trump election. Confirmed active address.",
        "cluster_name": "Théo French Whale",
        "is_famous": True,
        "estimated_pnl": 26000000,
        "primary_category": Sector.POLITICS,
        "win_rate": 65.0,
        "total_volume": 67668524,  # $67.6M traded
        "is_confirmed": True  # Address confirmed and API-accessible
    },

    # ========================================================================
    # TIER 2: HIGH WHALES ($500k+ profit) - CONFIRMED ADDRESSES
    # ========================================================================
    {
        "address": "0xf705fa045201391d9632b7f3cde06a5e24453ca7",  # Leaderboard #15 (CONFIRMED)
        "pseudonym": "Leaderboard_#15",
        "tier": "HIGH",
        "notes": "Leaderboard position #15. Consistent high-volume trader with $522k profit.",
        "cluster_name": None,
        "is_famous": True,
        "estimated_pnl": 522206,
        "primary_category": Sector.OTHER,
        "win_rate": 60.0,  # Conservative estimate
        "total_volume": 9154868,  # $9.2M
        "is_confirmed": True
    },
    # NOTE: The following whales are part of the same Théo cluster but addresses
    # are not publicly disclosed. To activate them, replace placeholder addresses
    # with real ones found via blockchain analysis or profile scraping.
    # {
    #     "address": "0x_REPLACE_WITH_REAL_ADDRESS",  # PrincessCaro
    #     "pseudonym": "PrincessCaro",
    #     "tier": "MEGA",
    #     "notes": "Part of Théo's cluster - $21M+ volume",
    #     "cluster_name": "Théo French Whale",
    #     "is_famous": True,
    #     "estimated_pnl": 20000000,
    #     "primary_category": "politics",
    #     "is_confirmed": False
    # },
    # {
    #     "address": "0x_REPLACE_WITH_REAL_ADDRESS",  # Theo4
    #     "pseudonym": "Theo4",
    #     "tier": "MEGA",
    #     "notes": "#1 on all-time Polymarket leaderboard - $22M profit",
    #     "cluster_name": "Théo French Whale",
    #     "is_famous": True,
    #     "estimated_pnl": 22000000,
    #     "primary_category": "politics",
    #     "is_confirmed": False
    # },
    # {
    #     "address": "0x_REPLACE_WITH_REAL_ADDRESS",  # Michie
    #     "pseudonym": "Michie",
    #     "tier": "MEGA",
    #     "notes": "Part of Théo's cluster - $79M total cluster profit",
    #     "cluster_name": "Théo French Whale",
    #     "is_famous": True,
    #     "estimated_pnl": 11000000,
    #     "primary_category": "politics",
    #     "is_confirmed": False
    # },
]

# ============================================================================
# Additional top traders to consider (addresses need to be found):
# - 1j59y6nk: $1.4M profit (sports betting specialist)
# - WindWalk3: $1.1M profit (politics, RFK Jr. markets)
# - HyperLiquid0xb: $976k profit (sports - basketball/baseball)
# - Axios: 96% win rate (high-conviction trader)
# ============================================================================

# Whale discovery criteria
WHALE_CRITERIA = {
    "min_total_volume": 100000,  # $100k minimum trading volume
    "min_trades": 20,            # At least 20 trades
    "min_win_rate": 58,          # 58%+ win rate
    "min_sharpe": 1.0,           # Sharpe > 1.0
    "min_pnl": 10000,            # $10k+ profit
}


class WhaleDiscovery:
    """Discovers and ranks Polymarket whales"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.gamma_api_base = "https://gamma-api.polymarket.com"
        self.clob_api_base = "https://clob.polymarket.com"
        self.data_api_base = "https://data-api.polymarket.com"

    async def fetch_top_traders_by_volume(self, limit: int = 100) -> List[Dict]:
        """
        Fetch top traders from Polymarket by trading volume.
        Uses publicly available leaderboard data.
        """
        whales = []

        # Method 1: Try Gamma API (may not have leaderboard)
        try:
            # Note: This endpoint may not exist - Polymarket's API is not fully public
            # We'll need to use alternative methods
            response = await self.http_client.get(
                f"{self.gamma_api_base}/leaderboard",
                params={"limit": limit, "metric": "volume"}
            )
            if response.status_code == 200:
                data = response.json()
                whales.extend(data.get('traders', []))
        except Exception as e:
            print(f"Gamma API leaderboard not available: {e}")

        # Method 2: Use on-chain analysis via PolygonScan
        # We can query the CTF Exchange contract for high-volume traders
        print("Note: Full leaderboard API not public. Using curated famous whale list.")
        print("For production: Integrate with Arkham/Nansen for whale discovery.")

        return whales

    async def enrich_whale_from_api(self, address: str) -> Dict:
        """
        Enrich whale data using Polymarket Data API.
        Fetches trading history, profile, and performance metrics.
        """
        try:
            print(f"  Fetching data for {address[:10]}... from Polymarket API")

            # Get user activity
            response = await self.http_client.get(
                f"{self.data_api_base}/activity",
                params={"user": address, "limit": 100}
            )

            if response.status_code != 200:
                print(f"    ⚠️  API returned {response.status_code}")
                return None

            data = response.json()

            # Extract profile info
            profile = {}
            if data and len(data) > 0:
                first_entry = data[0]
                profile = {
                    "pseudonym": first_entry.get("name", first_entry.get("pseudonym", "Unknown")),
                    "profile_image": first_entry.get("profileImage"),
                }

            # Calculate trading stats from activity
            total_volume = 0
            trades_count = 0

            for activity in data:
                if activity.get("type") in ["buy", "sell"]:
                    trades_count += 1
                    # Calculate volume (price * shares)
                    price = float(activity.get("price", 0))
                    shares = float(activity.get("shares", 0))
                    total_volume += price * shares

            whale_data = {
                "address": address,
                "pseudonym": profile.get("pseudonym", "Unknown"),
                "total_volume": total_volume,
                "total_trades": trades_count,
                "profile_image": profile.get("profile_image"),
                "is_qualified": trades_count >= WHALE_CRITERIA["min_trades"] and
                               total_volume >= WHALE_CRITERIA["min_total_volume"]
            }

            print(f"    ✅ {whale_data['pseudonym']}: ${total_volume:,.0f} volume, {trades_count} trades")

            return whale_data

        except Exception as e:
            print(f"  ❌ Error enriching whale {address[:10]}...: {e}")
            return None

    async def analyze_whale(self, address: str) -> Dict:
        """
        Analyze a wallet address to determine if it's a profitable whale.
        Uses Polymarket Data API to get trading history.
        """
        # Use the API enrichment function
        return await self.enrich_whale_from_api(address)

    def score_whale(self, whale_data: Dict) -> float:
        """
        Score a whale based on multiple factors (0-100 scale).
        Combines volume, profitability, and consistency.
        """
        score = 0

        # Volume component (0-30 points)
        volume_score = min(30, (whale_data.get('total_volume', 0) / 1000000) * 10)  # 10 pts per $1M

        # Profitability component (0-40 points)
        pnl_score = min(40, (whale_data.get('total_pnl', 0) / 100000) * 10)  # 10 pts per $100k

        # Win rate component (0-30 points)
        win_rate = whale_data.get('win_rate', 0)
        if win_rate >= 70:
            win_rate_score = 30
        elif win_rate >= 65:
            win_rate_score = 25
        elif win_rate >= 60:
            win_rate_score = 20
        elif win_rate >= 55:
            win_rate_score = 15
        else:
            win_rate_score = 10

        score = volume_score + pnl_score + win_rate_score

        return round(score, 2)

    async def close(self):
        await self.http_client.aclose()


async def create_whale_cluster(session: AsyncSession, cluster_name: str, whale_addresses: List[str]) -> WalletCluster:
    """Create a wallet cluster linking multiple addresses to one entity"""
    cluster = WalletCluster(
        entity_name=cluster_name,
        confidence_score=Decimal("0.95"),  # High confidence for known clusters
        clustering_method="manual_identification",
        member_addresses=whale_addresses,
        primary_address=whale_addresses[0] if whale_addresses else None,
        funding_source=None,  # Can be filled in later via on-chain analysis
        arkham_entity_id=None,
        nansen_label=None
    )

    session.add(cluster)
    await session.flush()
    return cluster


async def seed_famous_whales(session: AsyncSession):
    """Seed database with famous whales from public sources"""

    print("\n" + "="*80)
    print("SEEDING FAMOUS WHALES")
    print("="*80)

    # Group by cluster
    clusters = {}
    for whale_data in FAMOUS_WHALES:
        cluster_name = whale_data.get('cluster_name', 'Unknown')
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(whale_data)

    # Create clusters
    for cluster_name, whale_list in clusters.items():
        print(f"\nCreating cluster: {cluster_name}")

        # Create cluster
        addresses = [w['address'] for w in whale_list]
        cluster = await create_whale_cluster(session, cluster_name, addresses)

        # Create whale records
        for whale_data in whale_list:
            # Use provided volume or estimate as 2x PnL
            total_volume = whale_data.get('total_volume', whale_data.get('estimated_pnl', 0) * 2)

            whale = Whale(
                address=whale_data['address'],
                cluster_id=cluster.cluster_id,
                pseudonym=whale_data['pseudonym'],
                platform=Platform.POLYMARKET,
                total_volume=Decimal(str(total_volume)),
                total_pnl=Decimal(str(whale_data.get('estimated_pnl', 0))),
                tier=whale_data.get('tier', 'MEDIUM'),
                quality_score=Decimal("95.0"),  # High score for famous profitable whales
                rank=1,  # Top tier
                is_active=True,
                is_copying_enabled=True if whale_data.get('is_confirmed', False) else False,
                primary_category=whale_data.get('primary_category'),
                win_rate=Decimal(str(whale_data.get('win_rate', 65.0))),
                roi=Decimal("100.0"),  # High ROI for profitable whales
                sharpe_ratio=Decimal("2.5"),
                edge_status='active',
            )

            session.add(whale)
            copying_status = "✓ COPYING ENABLED" if whale.is_copying_enabled else "⚠ copying disabled (needs validation)"
            print(f"  ✅ Added {whale.pseudonym} ({whale.address[:10]}...) - {copying_status}")

    await session.commit()
    print(f"\n✅ Seeded {len(FAMOUS_WHALES)} famous whales in {len(clusters)} clusters")


async def discover_and_seed_top_whales(session: AsyncSession, limit: int = 50):
    """
    Discover additional whales from public sources and seed database.

    NOTE: Polymarket doesn't have a public leaderboard API.
    In production, use:
    1. On-chain analysis (query Polygon blockchain)
    2. Arkham Intelligence API
    3. Nansen API
    4. Manual curation from social media/news
    """

    print("\n" + "="*80)
    print("DISCOVERING TOP WHALES (via public sources)")
    print("="*80)

    discovery = WhaleDiscovery()

    # Try to fetch from public sources
    traders = await discovery.fetch_top_traders_by_volume(limit=limit)

    if not traders:
        print("\n⚠️  No public leaderboard API available.")
        print("📝 Recommendation: Integrate with:")
        print("   1. Arkham Intelligence API (wallet clustering)")
        print("   2. Nansen API (on-chain labels)")
        print("   3. PolygonScan API (direct blockchain queries)")
        print("   4. Manual curation from Polymarket social/news")
        print("\n✅ Using manually curated famous whale list for now.")

    await discovery.close()


async def main():
    """Main seeding function"""

    print("\n" + "="*80)
    print("POLYMARKET WHALE DISCOVERY & DATABASE SEEDING")
    print("="*80)

    # Create async engine
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created")

    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Seed famous whales
        await seed_famous_whales(session)

        # Discover additional whales
        await discover_and_seed_top_whales(session, limit=50)

    await engine.dispose()

    print("\n" + "="*80)
    print("✅ WHALE SEEDING COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Fill in complete wallet addresses (check Polymarket profiles/PolygonScan)")
    print("2. Enable WebSocket monitoring for whale trades")
    print("3. Integrate Arkham/Nansen for automated whale discovery")
    print("4. Run scoring engine to rank whales by quality")


if __name__ == "__main__":
    asyncio.run(main())
