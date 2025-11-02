"""
Market Resolution Tracker
Links every trade to final market outcome (win/loss) for accurate P&L calculation.

This is Phase 1 of the production framework - critical foundation.
Target: 99.6% volume match with on-chain data.
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Integer
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.dialects.postgresql import insert
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class MarketResolution(Base):
    """Database model for market resolutions."""
    __tablename__ = 'market_resolutions'

    market_id = Column(String, primary_key=True)
    question = Column(String)
    category = Column(String)
    end_date = Column(DateTime)
    resolution_date = Column(DateTime)
    resolved = Column(Boolean, default=False)
    outcome = Column(String)  # 'YES', 'NO', 'INVALID', etc.
    outcome_prices = Column(String)  # JSON string of final prices
    resolved_by = Column(String)
    resolution_source = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Additional metadata
    volume_24h = Column(Float)
    liquidity = Column(Float)
    active = Column(Boolean, default=True)

class MarketResolver:
    """Fetches and tracks market resolutions from Polymarket."""

    def __init__(self):
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.database_url = os.getenv('DATABASE_URL',
            'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(self.database_url)

    async def fetch_market_metadata(self, market_id: str) -> Optional[Dict]:
        """
        Fetch market details from Gamma API.

        Returns market metadata including resolution status.
        """
        try:
            url = f"{self.gamma_api}/markets/{market_id}"
            response = await self.http_client.get(url)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Error fetching market {market_id}: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Exception fetching market {market_id}: {e}")
            return None

    async def fetch_all_markets(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """
        Fetch all markets from Gamma API.
        Used for bulk resolution checking.
        """
        try:
            url = f"{self.gamma_api}/markets"
            params = {
                "limit": limit,
                "offset": offset,
                "archived": "true"  # Include resolved markets
            }
            response = await self.http_client.get(url, params=params)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Error fetching markets: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Exception fetching markets: {e}")
            return []

    def save_market_resolution(self, market_data: Dict):
        """Save or update market resolution in database."""
        with Session(self.engine) as session:
            # Prepare resolution data
            resolution = {
                'market_id': market_data.get('id', market_data.get('market_id')),
                'question': market_data.get('question', ''),
                'category': market_data.get('category', 'Unknown'),
                'end_date': self._parse_datetime(market_data.get('end_date_iso', market_data.get('endDate'))),
                'resolved': market_data.get('closed', False),
                'outcome': market_data.get('outcome', None),
                'outcome_prices': str(market_data.get('outcomePrices', [])),
                'resolved_by': market_data.get('resolvedBy', None),
                'resolution_source': 'gamma_api',
                'volume_24h': float(market_data.get('volume24hr', 0)),
                'liquidity': float(market_data.get('liquidity', 0)),
                'active': market_data.get('active', True),
                'updated_at': datetime.now()
            }

            # Check if resolution happened
            if market_data.get('closed') or market_data.get('resolved'):
                resolution['resolved'] = True
                resolution['resolution_date'] = datetime.now()

            # Upsert (insert or update)
            stmt = insert(MarketResolution).values(**resolution)
            stmt = stmt.on_conflict_do_update(
                index_elements=['market_id'],
                set_={
                    'resolved': stmt.excluded.resolved,
                    'outcome': stmt.excluded.outcome,
                    'outcome_prices': stmt.excluded.outcome_prices,
                    'resolution_date': stmt.excluded.resolution_date,
                    'updated_at': stmt.excluded.updated_at,
                    'volume_24h': stmt.excluded.volume_24h,
                    'liquidity': stmt.excluded.liquidity,
                }
            )

            session.execute(stmt)
            session.commit()

    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not dt_string:
            return None

        try:
            # Try ISO format
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except:
            try:
                # Try timestamp
                return datetime.fromtimestamp(float(dt_string))
            except:
                return None

    async def sync_market_resolutions(self, batch_size: int = 100):
        """
        Sync all market resolutions from Polymarket.

        This should be run:
        - Daily for ongoing monitoring
        - Once for historical backfill
        """
        print("\n" + "="*80)
        print("🔄 SYNCING MARKET RESOLUTIONS")
        print("="*80)

        offset = 0
        total_synced = 0
        total_resolved = 0

        while True:
            print(f"\n📥 Fetching markets {offset} - {offset + batch_size}...")

            markets = await self.fetch_all_markets(limit=batch_size, offset=offset)

            if not markets or len(markets) == 0:
                print("✅ No more markets to fetch")
                break

            for market in markets:
                self.save_market_resolution(market)
                total_synced += 1

                if market.get('closed') or market.get('resolved'):
                    total_resolved += 1

            print(f"   Synced: {len(markets)} markets | Total: {total_synced} | Resolved: {total_resolved}")

            offset += batch_size

            # Brief delay to avoid rate limiting
            await asyncio.sleep(0.5)

        print(f"\n✅ Sync complete: {total_synced} markets synced, {total_resolved} resolved")
        return total_synced, total_resolved

    async def reconcile_trade_outcomes(self, whale_address: str) -> Dict:
        """
        For a whale's trades, determine win/loss based on market resolutions.

        Returns comprehensive P&L breakdown.
        """
        from libs.common.models import Trade

        with Session(self.engine) as session:
            # Get all trades for this whale
            trades = session.query(Trade).filter(
                Trade.whale_address == whale_address
            ).all()

            wins = 0
            losses = 0
            unresolved = 0
            total_pnl = 0.0

            for trade in trades:
                # Get market resolution
                resolution = session.query(MarketResolution).filter(
                    MarketResolution.market_id == trade.market_id
                ).first()

                if not resolution or not resolution.resolved:
                    unresolved += 1
                    continue

                # Calculate P&L based on side and outcome
                pnl = self._calculate_trade_pnl(
                    trade.side,
                    trade.price,
                    trade.size,
                    resolution.outcome
                )

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                total_pnl += pnl

                # Update trade with realized P&L
                trade.realized_pnl = pnl
                trade.is_resolved = True

            session.commit()

            return {
                'whale_address': whale_address,
                'total_trades': len(trades),
                'wins': wins,
                'losses': losses,
                'unresolved': unresolved,
                'win_rate': (wins / (wins + losses)) if (wins + losses) > 0 else 0,
                'total_pnl': total_pnl,
                'avg_pnl_per_trade': total_pnl / len(trades) if trades else 0
            }

    def _calculate_trade_pnl(self, side: str, entry_price: float, size: float, outcome: str) -> float:
        """
        Calculate realized P&L for a trade given market outcome.

        Args:
            side: 'BUY' or 'SELL'
            entry_price: Price whale paid (0-1 range)
            size: Number of shares
            outcome: 'YES', 'NO', or 'INVALID'

        Returns:
            Realized P&L in USD
        """
        if outcome == 'INVALID':
            # Invalid markets refund (no profit/loss)
            return 0.0

        # Determine if trade won
        if side == 'BUY':
            # Bought YES shares - win if outcome is YES
            won = (outcome == 'YES')
            exit_price = 1.0 if won else 0.0
        else:  # SELL
            # Sold YES shares (bet on NO) - win if outcome is NO
            won = (outcome == 'NO')
            exit_price = 0.0 if won else 1.0

        # P&L = (exit_price - entry_price) * size
        pnl = (exit_price - entry_price) * size

        # Account for Polymarket 2% fee on winnings
        if pnl > 0:
            pnl *= 0.98

        return pnl

    async def get_market_outcome(self, market_id: str) -> Optional[str]:
        """Get the outcome of a resolved market."""
        with Session(self.engine) as session:
            resolution = session.query(MarketResolution).filter(
                MarketResolution.market_id == market_id
            ).first()

            if resolution and resolution.resolved:
                return resolution.outcome
            return None

    async def check_pending_resolutions(self) -> List[str]:
        """
        Check for markets that should be resolved but aren't yet.
        Returns list of market IDs to investigate.
        """
        with Session(self.engine) as session:
            # Markets past end date but not resolved
            pending = session.query(MarketResolution).filter(
                MarketResolution.end_date < datetime.now(),
                MarketResolution.resolved == False
            ).all()

            print(f"\n⚠️  Found {len(pending)} markets past end date but not resolved")

            return [m.market_id for m in pending]

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


async def main():
    """
    Demo: Sync market resolutions and reconcile whale trades.
    """
    resolver = MarketResolver()

    try:
        # 1. Sync all market resolutions
        total, resolved = await resolver.sync_market_resolutions(batch_size=100)

        print(f"\n📊 Synced {total} markets, {resolved} resolved")

        # 2. Check for pending resolutions
        pending = await resolver.check_pending_resolutions()
        if pending:
            print(f"\n⚠️  {len(pending)} markets need resolution")

        # 3. Example: Reconcile a whale's trades
        # whale_address = "0x17db3fcd93ba12d38382a0cade24b200185c5f6d"  # fengdubiying
        # results = await resolver.reconcile_trade_outcomes(whale_address)
        # print(f"\n🐋 Whale P&L: {results}")

    finally:
        await resolver.close()


if __name__ == "__main__":
    asyncio.run(main())
