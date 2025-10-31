"""
Automated Whale Discovery Script

Discovers 100+ profitable Polymarket whales through:
1. Blockchain analysis (PolygonScan CTF Exchange transactions)
2. Polymarket Data API enrichment
3. Statistical filtering (Sharpe ratio, consistency, profitability)

Criteria:
- Consistently profitable (60%+ win rate)
- High Sharpe ratio (> 1.5)
- Big players ($100k+ volume)
- Open wallets (trades visible via Data API)

Run: python scripts/discover_whales.py
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal
from collections import defaultdict
import statistics

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.common.models import Base, Whale, WalletCluster, Platform
from dotenv import load_dotenv

load_dotenv()

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

# Polymarket contracts on Polygon
CTF_EXCHANGE = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"
NEG_RISK_CTF_EXCHANGE = "0xc5d563a36ae78145c45a50134d48a1215220f80a"

# PolygonScan API
POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY', '')  # Optional but recommended
POLYGONSCAN_BASE = "https://api.polygonscan.com/api"

# Whale criteria (from user requirements)
WHALE_CRITERIA = {
    "min_volume": 100000,        # $100k+ minimum volume
    "min_win_rate": 60,          # 60%+ win rate
    "min_sharpe": 1.5,           # Sharpe ratio > 1.5
    "min_trades": 30,            # At least 30 trades for statistical significance
    "min_profit": 5000,          # $5k+ profit
    "consistency_threshold": 0.7 # 70% of months must be profitable
}


class WhaleDiscoveryEngine:
    """Advanced whale discovery using blockchain + API analysis"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.data_api_base = "https://data-api.polymarket.com"
        self.discovered_whales = []
        self.processed_addresses = set()

    async def discover_from_blockchain(self, limit: int = 500) -> List[str]:
        """
        Discover high-volume traders from Polygon blockchain.

        Uses PolygonScan API to find top interactors with CTF Exchange.
        """
        print("\n" + "="*80)
        print("BLOCKCHAIN ANALYSIS - PolygonScan CTF Exchange")
        print("="*80)

        addresses = set()

        # Method 1: Top token holders of USDC interacting with CTF Exchange
        print("\n🔍 Finding high-volume USDC users...")

        try:
            # Get recent transactions to CTF Exchange
            params = {
                "module": "account",
                "action": "txlist",
                "address": CTF_EXCHANGE,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 1000,  # Last 1000 transactions
                "sort": "desc"
            }

            if POLYGONSCAN_API_KEY:
                params["apikey"] = POLYGONSCAN_API_KEY

            response = await self.http_client.get(POLYGONSCAN_BASE, params=params)
            data = response.json()

            if data.get("status") == "1" and data.get("result"):
                transactions = data["result"]

                # Count transaction frequency per address
                address_counts = defaultdict(int)
                for tx in transactions:
                    addr = tx.get("from", "").lower()
                    if addr and addr != CTF_EXCHANGE.lower():
                        address_counts[addr] += 1

                # Get top 100 most active addresses
                top_addresses = sorted(address_counts.items(), key=lambda x: x[1], reverse=True)[:100]

                print(f"✅ Found {len(top_addresses)} active addresses")
                for addr, count in top_addresses[:10]:
                    print(f"  {addr[:10]}... - {count} transactions")
                    addresses.add(addr)

                # Add all top addresses
                for addr, _ in top_addresses:
                    addresses.add(addr)

            else:
                print(f"⚠️  PolygonScan API returned: {data.get('message', 'Unknown error')}")
                print("Tip: Set POLYGONSCAN_API_KEY in .env for better rate limits")

        except Exception as e:
            print(f"❌ Error fetching blockchain data: {e}")

        # Method 2: Known whale addresses from previous research
        print("\n📋 Adding known profitable whales...")
        known_whales = [
            "0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf",  # Fredi9999 (confirmed)
            "0x02e65d10e83eb391ca0c466630f82790854e25",    # From leaderboard
            "0xf705fa045201391d9632b7f3cde06a5e24453ca7",  # From leaderboard
        ]

        for addr in known_whales:
            addresses.add(addr.lower())
            print(f"  ✅ {addr}")

        print(f"\n📊 Total unique addresses to analyze: {len(addresses)}")
        return list(addresses)

    async def enrich_and_score_whale(self, address: str) -> Optional[Dict]:
        """
        Enrich whale data from Polymarket API and calculate scores.

        Returns qualified whale data or None if doesn't meet criteria.
        """
        if address in self.processed_addresses:
            return None

        self.processed_addresses.add(address)

        try:
            # Fetch full trading history
            response = await self.http_client.get(
                f"{self.data_api_base}/activity",
                params={"user": address, "limit": 1000}
            )

            if response.status_code != 200:
                return None

            data = response.json()

            if not data or len(data) == 0:
                return None

            # Extract profile
            first_entry = data[0]
            pseudonym = first_entry.get("name", first_entry.get("pseudonym", f"{address[:8]}..."))

            # Calculate comprehensive trading statistics
            stats = self.calculate_trading_stats(data)

            # Check if meets whale criteria
            if not self.meets_whale_criteria(stats):
                return None

            whale_data = {
                "address": address,
                "pseudonym": pseudonym,
                "total_volume": stats["total_volume"],
                "total_trades": stats["total_trades"],
                "total_pnl": stats.get("total_pnl", 0),
                "win_rate": stats["win_rate"],
                "sharpe_ratio": stats.get("sharpe_ratio", 0),
                "sortino_ratio": stats.get("sortino_ratio", 0),
                "consistency_score": stats.get("consistency_score", 0),
                "avg_trade_size": stats.get("avg_trade_size", 0),
                "quality_score": self.calculate_quality_score(stats),
                "is_qualified": True
            }

            print(f"  ✅ {pseudonym}: ${stats['total_volume']:,.0f} vol, "
                  f"{stats['win_rate']:.1f}% WR, Sharpe {stats.get('sharpe_ratio', 0):.2f}")

            return whale_data

        except Exception as e:
            print(f"  ⚠️  Error enriching {address[:10]}...: {e}")
            return None

    def calculate_trading_stats(self, activity_data: List[Dict]) -> Dict:
        """
        Calculate comprehensive trading statistics from activity data.

        Returns metrics needed for whale qualification.
        """
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

                # Track trade outcomes
                trade_data = {
                    "value": value,
                    "price": price,
                    "shares": shares,
                    "side": activity_type,
                    "timestamp": activity.get("timestamp", "")
                }
                trades.append(trade_data)

            elif activity_type == "redeem":
                # Redemption = realized profit
                payout = float(activity.get("payout", 0))
                timestamp = activity.get("timestamp", "")

                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        month_key = dt.strftime("%Y-%m")
                        monthly_pnl[month_key] += payout
                    except:
                        pass

        # Calculate win rate (simplified - months with positive PnL)
        winning_months = sum(1 for pnl in monthly_pnl.values() if pnl > 0)
        total_months = len(monthly_pnl) if monthly_pnl else 1
        win_rate = (winning_months / total_months) * 100 if total_months > 0 else 0

        # Calculate Sharpe ratio (simplified)
        if monthly_pnl:
            returns = list(monthly_pnl.values())
            avg_return = statistics.mean(returns) if returns else 0
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe = 0

        # Calculate Sortino ratio (downside deviation)
        downside_returns = [r for r in monthly_pnl.values() if r < 0]
        if downside_returns and len(downside_returns) > 1:
            downside_std = statistics.stdev(downside_returns)
            avg_return = statistics.mean(monthly_pnl.values())
            sortino = (avg_return / downside_std) if downside_std > 0 else 0
        else:
            sortino = sharpe  # Fallback

        # Consistency score (% of profitable months)
        consistency = (winning_months / total_months) if total_months > 0 else 0

        # Average trade size
        avg_trade_size = total_volume / len(trades) if trades else 0

        # Total PnL
        total_pnl = sum(monthly_pnl.values())

        return {
            "total_volume": total_volume,
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "consistency_score": consistency,
            "avg_trade_size": avg_trade_size,
            "monthly_pnl": dict(monthly_pnl)
        }

    def meets_whale_criteria(self, stats: Dict) -> bool:
        """Check if trader meets whale qualification criteria"""
        return (
            stats["total_volume"] >= WHALE_CRITERIA["min_volume"] and
            stats["total_trades"] >= WHALE_CRITERIA["min_trades"] and
            stats["win_rate"] >= WHALE_CRITERIA["min_win_rate"] and
            stats.get("sharpe_ratio", 0) >= WHALE_CRITERIA["min_sharpe"] and
            stats.get("total_pnl", 0) >= WHALE_CRITERIA["min_profit"] and
            stats.get("consistency_score", 0) >= WHALE_CRITERIA["consistency_threshold"]
        )

    def calculate_quality_score(self, stats: Dict) -> float:
        """
        Calculate overall whale quality score (0-100).

        Weighted combination of key metrics.
        """
        # Volume score (0-25 points)
        volume_score = min(25, (stats["total_volume"] / 1000000) * 5)

        # Sharpe score (0-25 points)
        sharpe_score = min(25, stats.get("sharpe_ratio", 0) * 10)

        # Win rate score (0-25 points)
        win_rate_score = (stats["win_rate"] / 100) * 25

        # Consistency score (0-25 points)
        consistency_score = stats.get("consistency_score", 0) * 25

        total_score = volume_score + sharpe_score + win_rate_score + consistency_score

        return round(total_score, 2)

    async def save_whales_to_database(self, whales: List[Dict], session: AsyncSession):
        """Save discovered whales to database"""
        print("\n" + "="*80)
        print("SAVING TO DATABASE")
        print("="*80)

        saved_count = 0

        for whale_data in whales:
            try:
                # Check if whale already exists
                result = await session.execute(
                    select(Whale).where(Whale.address == whale_data["address"])
                )
                existing_whale = result.scalar_one_or_none()

                if existing_whale:
                    print(f"  ⏭  {whale_data['pseudonym']} already exists, skipping")
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
                    sortino_ratio=Decimal(str(whale_data.get("sortino_ratio", 0))),
                    quality_score=Decimal(str(whale_data["quality_score"])),
                    tier="MEGA" if whale_data["quality_score"] > 80 else "HIGH" if whale_data["quality_score"] > 60 else "MEDIUM",
                    rank=1,
                    is_active=True,
                    is_copying_enabled=True,  # Auto-enable for qualified whales
                    edge_status='active'
                )

                session.add(whale)
                saved_count += 1
                print(f"  ✅ Saved {whale.pseudonym} (Score: {whale.quality_score})")

            except Exception as e:
                print(f"  ❌ Error saving {whale_data.get('pseudonym', 'unknown')}: {e}")

        await session.commit()
        print(f"\n✅ Saved {saved_count} new whales to database")

    async def close(self):
        await self.http_client.aclose()


async def main():
    """Main discovery workflow"""

    print("\n" + "="*80)
    print("POLYMARKET WHALE DISCOVERY ENGINE")
    print("Discovering 100+ Profitable Whales")
    print("="*80)

    print(f"\n📋 Whale Criteria:")
    print(f"  • Min Volume: ${WHALE_CRITERIA['min_volume']:,}")
    print(f"  • Min Win Rate: {WHALE_CRITERIA['min_win_rate']}%")
    print(f"  • Min Sharpe Ratio: {WHALE_CRITERIA['min_sharpe']}")
    print(f"  • Min Trades: {WHALE_CRITERIA['min_trades']}")
    print(f"  • Min Profit: ${WHALE_CRITERIA['min_profit']:,}")
    print(f"  • Consistency: {WHALE_CRITERIA['consistency_threshold']*100}% profitable months")

    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    discovery = WhaleDiscoveryEngine()

    try:
        # Step 1: Discover addresses from blockchain
        addresses = await discovery.discover_from_blockchain(limit=500)

        if not addresses:
            print("\n❌ No addresses found. Check PolygonScan API key or network connection.")
            return

        # Step 2: Enrich and score each address
        print("\n" + "="*80)
        print("ENRICHING WHALE DATA (this may take a while...)")
        print("="*80)

        qualified_whales = []

        for i, address in enumerate(addresses[:200], 1):  # Process first 200
            print(f"\n[{i}/{min(200, len(addresses))}] Analyzing {address[:10]}...")

            whale_data = await discovery.enrich_and_score_whale(address)

            if whale_data:
                qualified_whales.append(whale_data)

            # Rate limiting
            if i % 10 == 0:
                print(f"\n  💤 Rate limiting... (discovered {len(qualified_whales)} qualified whales so far)")
                await asyncio.sleep(2)

            # Stop if we have 100 whales
            if len(qualified_whales) >= 100:
                print(f"\n✅ Found 100 qualified whales! Stopping search.")
                break

        # Step 3: Save to database
        if qualified_whales:
            async with async_session() as session:
                await discovery.save_whales_to_database(qualified_whales, session)

            # Print summary
            print("\n" + "="*80)
            print("DISCOVERY SUMMARY")
            print("="*80)
            print(f"Total Addresses Analyzed: {len(discovery.processed_addresses)}")
            print(f"Qualified Whales Found: {len(qualified_whales)}")
            print(f"\nTop 10 Whales by Quality Score:")
            print("-"*80)

            sorted_whales = sorted(qualified_whales, key=lambda x: x["quality_score"], reverse=True)
            for i, whale in enumerate(sorted_whales[:10], 1):
                print(f"{i:2d}. {whale['pseudonym'][:20]:20s} - Score: {whale['quality_score']:5.1f} - "
                      f"${whale['total_volume']:>10,.0f} - WR: {whale['win_rate']:4.1f}% - "
                      f"Sharpe: {whale.get('sharpe_ratio', 0):4.2f}")

        else:
            print("\n⚠️  No whales met the qualification criteria")
            print("Try adjusting WHALE_CRITERIA in the script")

    finally:
        await discovery.close()
        await engine.dispose()

    print("\n" + "="*80)
    print("✅ WHALE DISCOVERY COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
