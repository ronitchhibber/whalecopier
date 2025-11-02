"""
Real-Time P&L Calculation Engine with 1-Second Price Updates
Week 4: Position Management - Real-Time P&L Tracking
Continuously updates all open positions with live market prices
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.api.polymarket_client import PolymarketClient
from src.trading.production_position_manager import ProductionPositionManager, Position

logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """Real-time price update from market"""
    token_id: str
    price: Decimal
    timestamp: datetime
    volume_24h: Optional[Decimal] = None
    last_trade_time: Optional[datetime] = None


@dataclass
class PnLSnapshot:
    """Point-in-time P&L snapshot"""
    position_id: str
    timestamp: datetime
    price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    pnl_percentage: Decimal


class RealtimePnLEngine:
    """
    Real-time P&L calculation engine

    Features:
    - 1-second price updates for all open positions
    - Concurrent price fetching for multiple tokens
    - Automatic position P&L recalculation
    - P&L history tracking
    - Performance monitoring
    """

    def __init__(
        self,
        position_manager: ProductionPositionManager,
        client: Optional[PolymarketClient] = None,
        update_interval: float = 1.0  # 1 second
    ):
        """
        Initialize real-time P&L engine

        Args:
            position_manager: Position manager to update
            client: Polymarket API client for price fetching
            update_interval: Price update interval in seconds (default: 1s)
        """
        self.position_manager = position_manager
        self.client = client or PolymarketClient()
        self.update_interval = update_interval

        # Engine state
        self.is_running = False
        self.update_task: Optional[asyncio.Task] = None

        # Price cache
        self.latest_prices: Dict[str, PriceUpdate] = {}
        self.price_cache_ttl = 10  # 10 seconds TTL

        # Performance tracking
        self.total_updates = 0
        self.update_errors = 0
        self.last_update_time: Optional[datetime] = None
        self.avg_update_latency_ms = 0.0

        # P&L history (last 1000 snapshots per position)
        self.pnl_history: Dict[str, List[PnLSnapshot]] = {}
        self.max_history_length = 1000

        logger.info(
            f"RealtimePnLEngine initialized: update_interval={update_interval}s"
        )

    async def start(self):
        """Start the real-time P&L update loop"""
        if self.is_running:
            logger.warning("RealtimePnLEngine already running")
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())

        logger.info("RealtimePnLEngine started")

    async def stop(self):
        """Stop the real-time P&L update loop"""
        if not self.is_running:
            return

        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        logger.info(
            f"RealtimePnLEngine stopped | "
            f"Total updates: {self.total_updates}, "
            f"Errors: {self.update_errors}, "
            f"Avg latency: {self.avg_update_latency_ms:.2f}ms"
        )

    async def _update_loop(self):
        """Main update loop - runs every interval"""
        logger.info("P&L update loop started")

        while self.is_running:
            try:
                start_time = datetime.now()

                # Get all open positions
                open_positions = [
                    p for p in self.position_manager.positions.values()
                    if p.status.value == "OPEN"
                ]

                if not open_positions:
                    # No positions to update
                    await asyncio.sleep(self.update_interval)
                    continue

                # Extract unique token IDs
                token_ids = list(set(p.token_id for p in open_positions))

                # Fetch all prices concurrently
                price_updates = await self._fetch_prices_concurrent(token_ids)

                # Update each position
                update_tasks = []
                for position in open_positions:
                    price_update = price_updates.get(position.token_id)
                    if price_update:
                        update_tasks.append(
                            self._update_position_pnl(position, price_update)
                        )

                # Execute all updates concurrently
                if update_tasks:
                    await asyncio.gather(*update_tasks, return_exceptions=True)

                # Update performance metrics
                self.total_updates += 1
                self.last_update_time = datetime.now()
                latency_ms = (self.last_update_time - start_time).total_seconds() * 1000

                # Exponential moving average for latency
                alpha = 0.1
                self.avg_update_latency_ms = (
                    alpha * latency_ms +
                    (1 - alpha) * self.avg_update_latency_ms
                )

                # Log periodic stats
                if self.total_updates % 60 == 0:  # Every 60 updates (~1 minute)
                    logger.info(
                        f"P&L update stats: positions={len(open_positions)}, "
                        f"updates={self.total_updates}, "
                        f"errors={self.update_errors}, "
                        f"avg_latency={self.avg_update_latency_ms:.2f}ms"
                    )

            except asyncio.CancelledError:
                logger.info("P&L update loop cancelled")
                break
            except Exception as e:
                self.update_errors += 1
                logger.error(f"Error in P&L update loop: {e}", exc_info=True)

            # Wait for next interval
            try:
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break

    async def _fetch_prices_concurrent(
        self,
        token_ids: List[str]
    ) -> Dict[str, PriceUpdate]:
        """
        Fetch prices for multiple tokens concurrently

        Args:
            token_ids: List of token IDs to fetch

        Returns:
            Dict mapping token_id to PriceUpdate
        """
        # Check cache first
        now = datetime.now()
        cached_prices = {}
        tokens_to_fetch = []

        for token_id in token_ids:
            cached = self.latest_prices.get(token_id)
            if cached and (now - cached.timestamp).total_seconds() < self.price_cache_ttl:
                cached_prices[token_id] = cached
            else:
                tokens_to_fetch.append(token_id)

        # Fetch uncached prices concurrently
        if tokens_to_fetch:
            fetch_tasks = [
                self._fetch_single_price(token_id)
                for token_id in tokens_to_fetch
            ]

            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for token_id, result in zip(tokens_to_fetch, results):
                if isinstance(result, PriceUpdate):
                    self.latest_prices[token_id] = result
                    cached_prices[token_id] = result
                elif isinstance(result, Exception):
                    logger.error(f"Failed to fetch price for {token_id}: {result}")

        return cached_prices

    async def _fetch_single_price(self, token_id: str) -> Optional[PriceUpdate]:
        """
        Fetch price for a single token

        Args:
            token_id: Token ID

        Returns:
            PriceUpdate if successful, None otherwise
        """
        try:
            # Fetch from Polymarket API
            price_data = await self.client.get_price(token_id)

            if not price_data:
                return None

            price = Decimal(str(price_data.get("price", 0)))

            return PriceUpdate(
                token_id=token_id,
                price=price,
                timestamp=datetime.now(),
                volume_24h=Decimal(str(price_data.get("volume_24h", 0))) if price_data.get("volume_24h") else None,
                last_trade_time=price_data.get("last_trade_time")
            )

        except Exception as e:
            logger.error(f"Error fetching price for {token_id}: {e}")
            return None

    async def _update_position_pnl(
        self,
        position: Position,
        price_update: PriceUpdate
    ):
        """
        Update position P&L with new price

        Args:
            position: Position to update
            price_update: New price data
        """
        try:
            # Update position with new price
            success = await self.position_manager.update_position_price(
                position.position_id,
                price_update.price
            )

            if success:
                # Record P&L snapshot
                snapshot = PnLSnapshot(
                    position_id=position.position_id,
                    timestamp=price_update.timestamp,
                    price=price_update.price,
                    market_value=position.market_value or Decimal(0),
                    unrealized_pnl=position.unrealized_pnl,
                    pnl_percentage=position.pnl_percentage
                )

                # Add to history
                if position.position_id not in self.pnl_history:
                    self.pnl_history[position.position_id] = []

                self.pnl_history[position.position_id].append(snapshot)

                # Trim history if too long
                if len(self.pnl_history[position.position_id]) > self.max_history_length:
                    self.pnl_history[position.position_id] = (
                        self.pnl_history[position.position_id][-self.max_history_length:]
                    )

        except Exception as e:
            logger.error(
                f"Error updating P&L for position {position.position_id}: {e}"
            )

    def get_pnl_history(
        self,
        position_id: str,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[PnLSnapshot]:
        """
        Get P&L history for a position

        Args:
            position_id: Position ID
            since: Optional start time
            limit: Optional max number of snapshots

        Returns:
            List of P&L snapshots
        """
        history = self.pnl_history.get(position_id, [])

        if since:
            history = [s for s in history if s.timestamp >= since]

        if limit:
            history = history[-limit:]

        return history

    def get_pnl_stats(self, position_id: str) -> Optional[Dict]:
        """
        Get P&L statistics for a position

        Args:
            position_id: Position ID

        Returns:
            Dict with min, max, avg, current P&L
        """
        history = self.pnl_history.get(position_id, [])

        if not history:
            return None

        pnls = [s.unrealized_pnl for s in history]
        pnl_pcts = [s.pnl_percentage for s in history]

        return {
            "min_pnl": min(pnls),
            "max_pnl": max(pnls),
            "avg_pnl": sum(pnls) / len(pnls),
            "current_pnl": pnls[-1],
            "min_pnl_pct": min(pnl_pcts),
            "max_pnl_pct": max(pnl_pcts),
            "avg_pnl_pct": sum(pnl_pcts) / len(pnl_pcts),
            "current_pnl_pct": pnl_pcts[-1],
            "snapshots_count": len(history),
            "first_snapshot": history[0].timestamp,
            "last_snapshot": history[-1].timestamp
        }

    def get_engine_stats(self) -> Dict:
        """Get engine performance statistics"""
        return {
            "is_running": self.is_running,
            "total_updates": self.total_updates,
            "update_errors": self.update_errors,
            "error_rate_pct": (
                (self.update_errors / self.total_updates * 100)
                if self.total_updates > 0 else 0
            ),
            "last_update_time": self.last_update_time,
            "avg_update_latency_ms": self.avg_update_latency_ms,
            "cached_prices_count": len(self.latest_prices),
            "positions_tracked": len(self.pnl_history),
            "update_interval_seconds": self.update_interval
        }


# ==================== Example Usage ====================

async def main():
    """Example usage of RealtimePnLEngine"""
    import asyncpg
    from src.config import settings

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize database and position manager
    db_pool = await asyncpg.create_pool(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        database=settings.DATABASE_NAME
    )

    from src.trading.production_position_manager import ProductionPositionManager
    from src.trading.kelly_criterion_sizer import KellyParameters

    position_manager = ProductionPositionManager(db_pool)

    # Open a test position
    kelly_params = KellyParameters(
        win_rate=Decimal("0.60"),
        avg_win=Decimal("50"),
        avg_loss=Decimal("30"),
        kelly_fraction=Decimal("0.5")
    )

    position = await position_manager.open_position(
        whale_address="0x1234...",
        token_id="test_token_123",
        side="YES",
        entry_price=Decimal("0.55"),
        balance=Decimal("5000"),
        kelly_params=kelly_params
    )

    if position:
        print(f"\nOpened position: {position.position_id}")
        print(f"Entry P&L: ${float(position.unrealized_pnl):.2f}")

        # Start real-time P&L engine
        pnl_engine = RealtimePnLEngine(
            position_manager=position_manager,
            update_interval=1.0  # 1 second updates
        )

        await pnl_engine.start()

        # Run for 10 seconds to see updates
        print("\nRunning P&L updates for 10 seconds...")
        await asyncio.sleep(10)

        # Get P&L history
        history = pnl_engine.get_pnl_history(position.position_id, limit=10)
        print(f"\nP&L History (last 10 snapshots):")
        for snapshot in history:
            print(
                f"  {snapshot.timestamp.strftime('%H:%M:%S')} | "
                f"Price: ${float(snapshot.price):.4f} | "
                f"P&L: ${float(snapshot.unrealized_pnl):.2f} "
                f"({float(snapshot.pnl_percentage):.2f}%)"
            )

        # Get P&L stats
        stats = pnl_engine.get_pnl_stats(position.position_id)
        if stats:
            print(f"\nP&L Statistics:")
            print(f"  Min P&L: ${float(stats['min_pnl']):.2f} ({float(stats['min_pnl_pct']):.2f}%)")
            print(f"  Max P&L: ${float(stats['max_pnl']):.2f} ({float(stats['max_pnl_pct']):.2f}%)")
            print(f"  Avg P&L: ${float(stats['avg_pnl']):.2f} ({float(stats['avg_pnl_pct']):.2f}%)")
            print(f"  Current P&L: ${float(stats['current_pnl']):.2f} ({float(stats['current_pnl_pct']):.2f}%)")

        # Get engine stats
        engine_stats = pnl_engine.get_engine_stats()
        print(f"\nEngine Stats:")
        print(f"  Total Updates: {engine_stats['total_updates']}")
        print(f"  Errors: {engine_stats['update_errors']}")
        print(f"  Avg Latency: {engine_stats['avg_update_latency_ms']:.2f}ms")
        print(f"  Positions Tracked: {engine_stats['positions_tracked']}")

        # Stop engine
        await pnl_engine.stop()

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
