"""
Position Management System for Polymarket Copy Trading
Handles position tracking, real-time P&L calculation, and stop-loss/take-profit
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import create_engine, select, update, and_
from sqlalchemy.orm import Session

from src.database.models import Position, Order
from src.api.polymarket_client import PolymarketClient
from src.config import settings

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

class PositionStatus(Enum):
    """Position status"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


@dataclass
class PnLMetrics:
    """P&L calculation result"""
    position_id: str
    unrealized_pnl: Decimal
    pnl_pct: Decimal
    current_value: Decimal
    current_price: Decimal
    profit_target_hit: bool
    stop_loss_hit: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioPnL:
    """Portfolio-level P&L"""
    total_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    num_positions: int
    num_winners: int
    num_losers: int
    win_rate: Decimal
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExitSignal:
    """Position exit signal"""
    position_id: str
    reason: str  # "stop_loss", "take_profit", "manual"
    current_price: Decimal
    trigger_price: Decimal
    pnl: Decimal
    pnl_pct: Decimal


# ==================== Position Tracker ====================

class PositionTracker:
    """
    Track and manage trading positions
    Handles CRUD operations with database integration
    """

    def __init__(self, db_url: Optional[str] = None, wallet_address: Optional[str] = None):
        """
        Initialize position tracker

        Args:
            db_url: Database connection URL (uses settings if None)
            wallet_address: Wallet address for positions (uses settings if None)
        """
        self.db_url = db_url or settings.DATABASE_URL
        self.wallet_address = wallet_address or settings.WALLET_ADDRESS
        self.engine = create_engine(self.db_url)

    def open_position(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        source_whale: Optional[str] = None,
        entry_trade_id: Optional[str] = None,
        market_title: Optional[str] = None
    ) -> Position:
        """
        Open a new position

        Args:
            market_id: Market/condition ID
            token_id: Token ID
            side: 'BUY' or 'SELL'
            size: Position size in shares
            entry_price: Entry price per share
            source_whale: Source whale address (if copy trade)
            entry_trade_id: ID of entry trade
            market_title: Market question/title

        Returns:
            Position object
        """
        with Session(self.engine) as session:
            try:
                # Generate position ID
                position_id = f"{market_id}_{int(datetime.now().timestamp())}"

                # Determine outcome
                outcome = "YES" if "yes" in token_id.lower() else "NO"

                # Calculate initial value
                initial_value = size * entry_price

                # Calculate stop-loss and take-profit prices
                if side == "BUY":
                    stop_loss_price = entry_price * (Decimal(1) - Decimal(str(settings.STOP_LOSS_PCT)))
                    take_profit_price = entry_price * (Decimal(1) + Decimal(str(settings.TAKE_PROFIT_PCT)))
                else:
                    # For sells (shorts), reverse the logic
                    stop_loss_price = entry_price * (Decimal(1) + Decimal(str(settings.STOP_LOSS_PCT)))
                    take_profit_price = entry_price * (Decimal(1) - Decimal(str(settings.TAKE_PROFIT_PCT)))

                # Create position
                position = Position(
                    position_id=position_id,
                    user_address=self.wallet_address,
                    market_id=market_id,
                    condition_id=market_id,  # Assuming market_id = condition_id
                    token_id=token_id,
                    outcome=outcome,
                    size=size,
                    avg_entry_price=entry_price,
                    current_price=entry_price,
                    initial_value=initial_value,
                    current_value=initial_value,
                    cash_pnl=Decimal(0),
                    percent_pnl=Decimal(0),
                    realized_pnl=Decimal(0),
                    market_title=market_title,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                    source_whale=source_whale,
                    entry_trade_id=entry_trade_id,
                    status=PositionStatus.OPEN.value,
                    opened_at=datetime.now()
                )

                session.add(position)
                session.commit()

                logger.info(f"✓ Opened position {position_id[:12]}...: {side} {size} @ {entry_price}")

                return position

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to open position: {e}")
                raise

    def update_position(
        self,
        position_id: str,
        size_delta: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        current_price: Optional[Decimal] = None
    ) -> Position:
        """
        Update an existing position

        Args:
            position_id: Position ID
            size_delta: Change in size (positive = add, negative = reduce)
            price: Price of the update (for calculating new avg price)
            current_price: Current market price (for P&L update)

        Returns:
            Updated Position object
        """
        with Session(self.engine) as session:
            try:
                position = session.get(Position, position_id)

                if not position:
                    raise ValueError(f"Position not found: {position_id}")

                # Update size if delta provided
                if size_delta is not None and price is not None:
                    # Calculate new average entry price
                    old_total_cost = position.size * position.avg_entry_price
                    new_cost = size_delta * price
                    new_size = position.size + size_delta

                    if new_size > 0:
                        position.avg_entry_price = (old_total_cost + new_cost) / new_size
                        position.size = new_size
                        position.initial_value = new_size * position.avg_entry_price
                    else:
                        # Position fully closed
                        position.size = Decimal(0)
                        position.status = PositionStatus.CLOSED.value
                        position.closed_at = datetime.now()

                # Update current price and P&L
                if current_price is not None:
                    position.current_price = current_price
                    position.current_value = position.size * current_price

                    # Calculate P&L
                    if position.outcome == "YES":
                        position.cash_pnl = (current_price - position.avg_entry_price) * position.size
                    else:
                        position.cash_pnl = (position.avg_entry_price - current_price) * position.size

                    if position.initial_value > 0:
                        position.percent_pnl = (position.cash_pnl / position.initial_value) * Decimal(100)
                    else:
                        position.percent_pnl = Decimal(0)

                session.commit()

                logger.debug(f"Updated position {position_id[:12]}...: P&L ${position.cash_pnl:.2f} ({position.percent_pnl:.1f}%)")

                return position

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update position {position_id}: {e}")
                raise

    def close_position(
        self,
        position_id: str,
        exit_price: Decimal,
        reason: str = "manual"
    ) -> Position:
        """
        Close a position

        Args:
            position_id: Position ID
            exit_price: Exit price per share
            reason: Reason for closing (manual, stop_loss, take_profit)

        Returns:
            Closed Position object
        """
        with Session(self.engine) as session:
            try:
                position = session.get(Position, position_id)

                if not position:
                    raise ValueError(f"Position not found: {position_id}")

                # Calculate final P&L
                if position.outcome == "YES":
                    realized_pnl = (exit_price - position.avg_entry_price) * position.size
                else:
                    realized_pnl = (position.avg_entry_price - exit_price) * position.size

                # Update position
                position.status = PositionStatus.CLOSED.value
                position.closed_at = datetime.now()
                position.current_price = exit_price
                position.current_value = position.size * exit_price
                position.cash_pnl = realized_pnl
                position.realized_pnl = realized_pnl
                position.percent_pnl = (realized_pnl / position.initial_value) * Decimal(100) if position.initial_value > 0 else Decimal(0)

                session.commit()

                logger.info(f"✓ Closed position {position_id[:12]}... ({reason}): P&L ${realized_pnl:.2f} ({position.percent_pnl:.1f}%)")

                return position

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to close position {position_id}: {e}")
                raise

    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        with Session(self.engine) as session:
            stmt = select(Position).where(
                and_(
                    Position.user_address == self.wallet_address,
                    Position.status == PositionStatus.OPEN.value
                )
            )
            return list(session.execute(stmt).scalars().all())

    def get_position_by_market(self, market_id: str) -> Optional[Position]:
        """Get open position for a specific market"""
        with Session(self.engine) as session:
            stmt = select(Position).where(
                and_(
                    Position.user_address == self.wallet_address,
                    Position.market_id == market_id,
                    Position.status == PositionStatus.OPEN.value
                )
            )
            return session.execute(stmt).scalar_one_or_none()

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        with Session(self.engine) as session:
            return session.get(Position, position_id)


# ==================== P&L Calculator ====================

class PnLCalculator:
    """
    Calculate real-time profit & loss for positions
    Target: <1s update latency
    """

    def __init__(
        self,
        client: Optional[PolymarketClient] = None,
        position_tracker: Optional[PositionTracker] = None
    ):
        """
        Initialize P&L calculator

        Args:
            client: PolymarketClient for fetching prices
            position_tracker: PositionTracker for accessing positions
        """
        self.client = client or PolymarketClient()
        self.tracker = position_tracker or PositionTracker()
        self.price_cache: Dict[str, Tuple[Decimal, datetime]] = {}
        self.cache_ttl = timedelta(seconds=1)  # 1-second cache

    async def fetch_current_price(self, token_id: str) -> Decimal:
        """
        Fetch current price for a token with caching

        Args:
            token_id: Token ID

        Returns:
            Current price
        """
        now = datetime.now()

        # Check cache
        if token_id in self.price_cache:
            cached_price, cached_time = self.price_cache[token_id]
            if now - cached_time < self.cache_ttl:
                return cached_price

        # Fetch from API
        try:
            price = self.client.get_midpoint(token_id)
            price_decimal = Decimal(str(price))

            # Update cache
            self.price_cache[token_id] = (price_decimal, now)

            return price_decimal

        except Exception as e:
            logger.error(f"Failed to fetch price for {token_id}: {e}")
            # Return cached price if available
            if token_id in self.price_cache:
                return self.price_cache[token_id][0]
            return Decimal(0)

    async def fetch_current_prices(self, token_ids: List[str]) -> Dict[str, Decimal]:
        """
        Fetch current prices for multiple tokens

        Args:
            token_ids: List of token IDs

        Returns:
            Dict mapping token_id to price
        """
        tasks = [self.fetch_current_price(token_id) for token_id in token_ids]
        prices = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            token_id: price if isinstance(price, Decimal) else Decimal(0)
            for token_id, price in zip(token_ids, prices)
        }

    async def calculate_position_pnl(
        self,
        position: Position,
        current_price: Optional[Decimal] = None
    ) -> PnLMetrics:
        """
        Calculate P&L metrics for a position

        Args:
            position: Position object
            current_price: Current price (fetches if None)

        Returns:
            PnLMetrics with calculations
        """
        # Fetch current price if not provided
        if current_price is None:
            current_price = await self.fetch_current_price(position.token_id)

        # Calculate unrealized P&L
        if position.outcome == "YES":
            unrealized_pnl = (current_price - position.avg_entry_price) * position.size
        else:
            unrealized_pnl = (position.avg_entry_price - current_price) * position.size

        # Calculate percentage
        pnl_pct = (unrealized_pnl / position.initial_value) * Decimal(100) if position.initial_value > 0 else Decimal(0)

        # Current value
        current_value = position.size * current_price

        # Check triggers
        profit_target_hit = False
        stop_loss_hit = False

        if position.take_profit_price:
            if position.outcome == "YES":
                profit_target_hit = current_price >= position.take_profit_price
            else:
                profit_target_hit = current_price <= position.take_profit_price

        if position.stop_loss_price:
            if position.outcome == "YES":
                stop_loss_hit = current_price <= position.stop_loss_price
            else:
                stop_loss_hit = current_price >= position.stop_loss_price

        return PnLMetrics(
            position_id=position.position_id,
            unrealized_pnl=unrealized_pnl,
            pnl_pct=pnl_pct,
            current_value=current_value,
            current_price=current_price,
            profit_target_hit=profit_target_hit,
            stop_loss_hit=stop_loss_hit
        )

    async def calculate_portfolio_pnl(self) -> PortfolioPnL:
        """
        Calculate portfolio-level P&L

        Returns:
            PortfolioPnL with aggregated metrics
        """
        # Get all open positions
        positions = self.tracker.get_open_positions()

        if not positions:
            return PortfolioPnL(
                total_value=Decimal(0),
                total_unrealized_pnl=Decimal(0),
                total_realized_pnl=Decimal(0),
                num_positions=0,
                num_winners=0,
                num_losers=0,
                win_rate=Decimal(0)
            )

        # Fetch prices for all positions
        token_ids = [p.token_id for p in positions]
        prices = await self.fetch_current_prices(token_ids)

        # Calculate P&L for each position
        total_value = Decimal(0)
        total_unrealized_pnl = Decimal(0)
        num_winners = 0
        num_losers = 0

        for position in positions:
            current_price = prices.get(position.token_id, Decimal(0))
            pnl_metrics = await self.calculate_position_pnl(position, current_price)

            total_value += pnl_metrics.current_value
            total_unrealized_pnl += pnl_metrics.unrealized_pnl

            if pnl_metrics.unrealized_pnl > 0:
                num_winners += 1
            elif pnl_metrics.unrealized_pnl < 0:
                num_losers += 1

        # Calculate win rate
        total_positions_with_pnl = num_winners + num_losers
        win_rate = (Decimal(num_winners) / Decimal(total_positions_with_pnl)) * Decimal(100) if total_positions_with_pnl > 0 else Decimal(0)

        return PortfolioPnL(
            total_value=total_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=Decimal(0),  # TODO: Calculate from closed positions
            num_positions=len(positions),
            num_winners=num_winners,
            num_losers=num_losers,
            win_rate=win_rate
        )


# ==================== Stop-Loss / Take-Profit Manager ====================

class StopLossTakeProfitManager:
    """
    Automated position exit management
    Monitors positions and triggers exits based on P&L thresholds
    """

    def __init__(
        self,
        pnl_calculator: Optional[PnLCalculator] = None,
        position_tracker: Optional[PositionTracker] = None,
        stop_loss_pct: float = 0.15,  # -15%
        take_profit_pct: float = 0.30  # +30%
    ):
        """
        Initialize stop-loss/take-profit manager

        Args:
            pnl_calculator: PnLCalculator instance
            position_tracker: PositionTracker instance
            stop_loss_pct: Stop-loss percentage (e.g., 0.15 = -15%)
            take_profit_pct: Take-profit percentage (e.g., 0.30 = +30%)
        """
        self.pnl_calc = pnl_calculator or PnLCalculator()
        self.tracker = position_tracker or PositionTracker()
        self.stop_loss_pct = Decimal(str(stop_loss_pct))
        self.take_profit_pct = Decimal(str(take_profit_pct))

    async def check_exit_triggers(self, position: Position) -> Optional[ExitSignal]:
        """
        Check if position should be exited

        Args:
            position: Position to check

        Returns:
            ExitSignal if exit triggered, None otherwise
        """
        # Calculate current P&L
        pnl_metrics = await self.pnl_calc.calculate_position_pnl(position)

        # Check stop-loss
        if pnl_metrics.stop_loss_hit:
            logger.warning(f"🛑 Stop-loss hit for {position.position_id[:12]}...: {pnl_metrics.pnl_pct:.1f}%")

            return ExitSignal(
                position_id=position.position_id,
                reason="stop_loss",
                current_price=pnl_metrics.current_price,
                trigger_price=position.stop_loss_price,
                pnl=pnl_metrics.unrealized_pnl,
                pnl_pct=pnl_metrics.pnl_pct
            )

        # Check take-profit
        if pnl_metrics.profit_target_hit:
            logger.info(f"🎯 Take-profit hit for {position.position_id[:12]}...: {pnl_metrics.pnl_pct:.1f}%")

            return ExitSignal(
                position_id=position.position_id,
                reason="take_profit",
                current_price=pnl_metrics.current_price,
                trigger_price=position.take_profit_price,
                pnl=pnl_metrics.unrealized_pnl,
                pnl_pct=pnl_metrics.pnl_pct
            )

        return None

    async def check_all_positions(self) -> List[ExitSignal]:
        """
        Check all open positions for exit triggers

        Returns:
            List of ExitSignals for positions that should be closed
        """
        positions = self.tracker.get_open_positions()
        exit_signals = []

        for position in positions:
            signal = await self.check_exit_triggers(position)
            if signal:
                exit_signals.append(signal)

        return exit_signals

    def set_stop_loss(self, position_id: str, stop_loss_price: Decimal) -> None:
        """
        Set custom stop-loss price for a position

        Args:
            position_id: Position ID
            stop_loss_price: Stop-loss price
        """
        with Session(self.tracker.engine) as session:
            position = session.get(Position, position_id)
            if position:
                position.stop_loss_price = stop_loss_price
                session.commit()
                logger.info(f"Set stop-loss for {position_id[:12]}... at {stop_loss_price}")

    def set_take_profit(self, position_id: str, take_profit_price: Decimal) -> None:
        """
        Set custom take-profit price for a position

        Args:
            position_id: Position ID
            take_profit_price: Take-profit price
        """
        with Session(self.tracker.engine) as session:
            position = session.get(Position, position_id)
            if position:
                position.take_profit_price = take_profit_price
                session.commit()
                logger.info(f"Set take-profit for {position_id[:12]}... at {take_profit_price}")


# ==================== Example Usage ====================

async def main():
    """Example usage of Position Management System"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize components
    tracker = PositionTracker()
    pnl_calc = PnLCalculator(position_tracker=tracker)
    sl_tp_manager = StopLossTakeProfitManager(pnl_calculator=pnl_calc, position_tracker=tracker)

    # Example: Open a position
    position = tracker.open_position(
        market_id="0x123...",
        token_id="21742633143463906290569050155826241533067272736897614950488156847949938836455",
        side="BUY",
        size=Decimal("100"),
        entry_price=Decimal("0.55"),
        source_whale="0xwhale...",
        market_title="Will Bitcoin reach $100k in 2024?"
    )

    print(f"\n✓ Position opened: {position.position_id}")
    print(f"  Size: {position.size}")
    print(f"  Entry: ${position.avg_entry_price}")
    print(f"  Stop-Loss: ${position.stop_loss_price}")
    print(f"  Take-Profit: ${position.take_profit_price}")

    # Example: Calculate P&L
    pnl_metrics = await pnl_calc.calculate_position_pnl(position)
    print(f"\n📊 Current P&L:")
    print(f"  Current Price: ${pnl_metrics.current_price}")
    print(f"  Unrealized P&L: ${pnl_metrics.unrealized_pnl:.2f} ({pnl_metrics.pnl_pct:.1f}%)")
    print(f"  Stop-Loss Hit: {pnl_metrics.stop_loss_hit}")
    print(f"  Take-Profit Hit: {pnl_metrics.profit_target_hit}")

    # Example: Check exit triggers
    exit_signal = await sl_tp_manager.check_exit_triggers(position)
    if exit_signal:
        print(f"\n⚠️ Exit triggered: {exit_signal.reason}")
        print(f"  Trigger Price: ${exit_signal.trigger_price}")
        print(f"  P&L: ${exit_signal.pnl:.2f} ({exit_signal.pnl_pct:.1f}%)")

    # Example: Calculate portfolio P&L
    portfolio_pnl = await pnl_calc.calculate_portfolio_pnl()
    print(f"\n💼 Portfolio Summary:")
    print(f"  Total Positions: {portfolio_pnl.num_positions}")
    print(f"  Total Value: ${portfolio_pnl.total_value:.2f}")
    print(f"  Total P&L: ${portfolio_pnl.total_unrealized_pnl:.2f}")
    print(f"  Win Rate: {portfolio_pnl.win_rate:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
