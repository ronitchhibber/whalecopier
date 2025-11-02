"""
Production Position Manager with Real-Time P&L and Risk Controls
Week 4: Position Management - Production-Ready Implementation
Integrates Kelly Criterion, database persistence, and risk management
"""

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import asyncpg

from src.config import settings
from src.trading.kelly_criterion_sizer import FractionalKellyCriterion, KellyParameters, PositionSizeRecommendation

logger = logging.getLogger(__name__)


# ==================== Position Status ====================

class PositionStatus(Enum):
    """Position lifecycle status"""
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CloseReason(Enum):
    """Reasons for closing a position"""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    MANUAL = "MANUAL"
    WHALE_EXIT = "WHALE_EXIT"
    PRE_RESOLUTION = "PRE_RESOLUTION"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    MARKET_RESOLVED = "MARKET_RESOLVED"


# ==================== Position Data Classes ====================

@dataclass
class Position:
    """Represents a trading position with full lifecycle tracking"""
    # Identification
    position_id: str
    whale_address: str
    token_id: str

    # Position details
    side: str  # "YES" or "NO"
    entry_size: Decimal
    entry_price: Decimal
    entry_amount: Decimal

    # Current state
    current_size: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None

    # P&L tracking
    unrealized_pnl: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)
    total_pnl: Decimal = Decimal(0)
    pnl_percentage: Decimal = Decimal(0)

    # Risk metrics
    max_drawdown: Decimal = Decimal(0)
    max_profit: Decimal = Decimal(0)
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None

    # Kelly sizing
    kelly_fraction: Decimal = Decimal("0.5")
    edge: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None

    # Lifecycle
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = field(default_factory=datetime.now)
    last_updated_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    price_last_updated_at: Optional[datetime] = None

    # Metadata
    notes: Optional[str] = None
    close_reason: Optional[CloseReason] = None


@dataclass
class PositionLimits:
    """Risk limits for position management"""
    max_positions: int = 50
    max_total_exposure: Decimal = Decimal("50000")  # $50k default
    max_position_size: Decimal = Decimal("1000")    # $1k per position
    min_position_size: Decimal = Decimal("10")      # $10 minimum
    stop_loss_pct: Decimal = Decimal("-0.15")       # -15% stop loss
    take_profit_pct: Decimal = Decimal("0.50")      # +50% take profit


@dataclass
class PortfolioMetrics:
    """Aggregated portfolio performance metrics"""
    total_positions: int
    open_positions: int
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_pnl: Decimal
    avg_pnl_percentage: Decimal
    winning_positions: int
    losing_positions: int
    win_rate: Decimal
    total_exposure: Decimal


# ==================== Production Position Manager ====================

class ProductionPositionManager:
    """
    Production-grade position manager with:
    - Real-time P&L calculation (1s price updates)
    - Fractional Kelly Criterion sizing
    - Position limits & risk controls
    - Database persistence with audit trail
    - Automatic stop-loss and take-profit execution
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        kelly_sizer: Optional[FractionalKellyCriterion] = None,
        limits: Optional[PositionLimits] = None
    ):
        """
        Initialize production position manager

        Args:
            db_pool: Database connection pool
            kelly_sizer: Kelly Criterion position sizer
            limits: Position limits and risk controls
        """
        self.db = db_pool
        self.kelly_sizer = kelly_sizer or FractionalKellyCriterion(
            kelly_fraction=0.5,
            min_position_size=Decimal("10"),
            max_position_size=Decimal("1000")
        )
        self.limits = limits or PositionLimits()

        # In-memory position cache
        self.positions: Dict[str, Position] = {}

        # Price update tracking
        self.price_update_interval = 1.0  # 1 second
        self.price_update_task: Optional[asyncio.Task] = None

        logger.info(
            f"ProductionPositionManager initialized: "
            f"max_positions={self.limits.max_positions}, "
            f"max_exposure=${float(self.limits.max_total_exposure):.2f}"
        )

    async def open_position(
        self,
        whale_address: str,
        token_id: str,
        side: str,
        entry_price: Decimal,
        balance: Decimal,
        kelly_params: Optional[KellyParameters] = None,
        notes: Optional[str] = None
    ) -> Optional[Position]:
        """
        Open a new position with Kelly sizing and risk controls

        Args:
            whale_address: Whale being copied
            token_id: Market token ID
            side: "YES" or "NO"
            entry_price: Entry price (0.01-0.99)
            balance: Current account balance
            kelly_params: Kelly parameters for sizing
            notes: Optional notes

        Returns:
            Position if opened successfully, None otherwise
        """
        # Check position limits
        can_add, reason = await self._check_position_limits(balance)
        if not can_add:
            logger.warning(f"Cannot open position: {reason}")
            return None

        # Calculate position size using Kelly
        if kelly_params:
            size_rec = self.kelly_sizer.calculate_position_size(balance, kelly_params)
        else:
            # Use default sizing if no Kelly params
            size_rec = PositionSizeRecommendation(
                recommended_size=self.limits.min_position_size,
                kelly_fraction=Decimal("0.5"),
                full_kelly_size=self.limits.min_position_size,
                edge=Decimal("0"),
                win_rate=Decimal("0.5"),
                risk_adjusted=True,
                reason="No Kelly params provided - using minimum size"
            )

        # Validate size
        if size_rec.recommended_size == 0:
            logger.warning(f"Kelly sizing returned 0: {size_rec.reason}")
            return None

        # Calculate entry details
        entry_amount = size_rec.recommended_size
        entry_size = entry_amount / entry_price  # shares = $ / price

        # Calculate stop loss and take profit
        stop_loss_price = self._calculate_stop_loss(entry_price, side)
        take_profit_price = self._calculate_take_profit(entry_price, side)

        # Create position
        position_id = f"pos_{uuid.uuid4().hex[:16]}"
        position = Position(
            position_id=position_id,
            whale_address=whale_address,
            token_id=token_id,
            side=side,
            entry_size=entry_size,
            entry_price=entry_price,
            entry_amount=entry_amount,
            current_size=entry_size,
            current_price=entry_price,
            market_value=entry_amount,
            kelly_fraction=size_rec.kelly_fraction,
            edge=size_rec.edge,
            win_rate=size_rec.win_rate,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            status=PositionStatus.OPEN,
            notes=notes
        )

        # Store in memory
        self.positions[position_id] = position

        # Persist to database
        await self._persist_position(position)

        logger.info(
            f"Opened position {position_id}: {side} {float(entry_size):.2f} shares @ "
            f"${float(entry_price):.4f} (${float(entry_amount):.2f}) | "
            f"SL: ${float(stop_loss_price):.4f}, TP: ${float(take_profit_price):.4f}"
        )

        return position

    async def update_position_price(
        self,
        position_id: str,
        new_price: Decimal
    ) -> bool:
        """
        Update position with new market price and recalculate P&L

        Args:
            position_id: Position ID
            new_price: New market price

        Returns:
            True if updated successfully
        """
        position = self.positions.get(position_id)
        if not position or position.status != PositionStatus.OPEN:
            return False

        # Store old values for update record
        old_price = position.current_price
        old_market_value = position.market_value
        old_unrealized_pnl = position.unrealized_pnl

        # Update price and market value
        position.current_price = new_price
        position.market_value = position.current_size * new_price
        position.price_last_updated_at = datetime.now()

        # Calculate unrealized P&L
        # P&L = (current_value - entry_amount) for YES positions
        # P&L = (entry_amount - current_value) for NO positions (inverted)
        if position.side == "YES":
            position.unrealized_pnl = position.market_value - position.entry_amount
        else:
            # NO positions: profit when price goes down
            position.unrealized_pnl = position.entry_amount - position.market_value

        position.total_pnl = position.unrealized_pnl + position.realized_pnl
        position.pnl_percentage = (position.total_pnl / position.entry_amount) * Decimal("100")

        # Update max drawdown and max profit
        if position.unrealized_pnl < position.max_drawdown:
            position.max_drawdown = position.unrealized_pnl
        if position.unrealized_pnl > position.max_profit:
            position.max_profit = position.unrealized_pnl

        # Persist update to database
        await self._update_position_price(position)
        await self._record_position_update(
            position,
            update_type="PRICE_UPDATE",
            old_price=old_price,
            old_market_value=old_market_value,
            old_unrealized_pnl=old_unrealized_pnl
        )

        # Check if stop loss or take profit hit
        await self._check_risk_triggers(position)

        return True

    async def close_position(
        self,
        position_id: str,
        close_price: Decimal,
        reason: CloseReason,
        notes: Optional[str] = None
    ) -> bool:
        """
        Close a position and realize P&L

        Args:
            position_id: Position ID
            close_price: Closing price
            reason: Reason for closing
            notes: Optional notes

        Returns:
            True if closed successfully
        """
        position = self.positions.get(position_id)
        if not position or position.status not in [PositionStatus.OPEN, PositionStatus.CLOSING]:
            logger.warning(f"Cannot close position {position_id}: invalid state")
            return False

        # Update to closing status
        position.status = PositionStatus.CLOSING

        # Final P&L calculation
        await self.update_position_price(position_id, close_price)

        # Realize the P&L
        position.realized_pnl = position.unrealized_pnl
        position.unrealized_pnl = Decimal(0)
        position.total_pnl = position.realized_pnl
        position.current_size = Decimal(0)
        position.market_value = Decimal(0)

        # Mark as closed
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.now()
        position.close_reason = reason
        if notes:
            position.notes = f"{position.notes or ''}\nClose: {notes}"

        # Persist closure
        await self._update_position_close(position)

        logger.info(
            f"Closed position {position_id}: "
            f"P&L=${float(position.realized_pnl):.2f} "
            f"({float(position.pnl_percentage):.2f}%) | "
            f"Reason: {reason.value}"
        )

        return True

    async def partial_close_position(
        self,
        position_id: str,
        close_size: Decimal,
        close_price: Decimal,
        reason: str = "PARTIAL_CLOSE"
    ) -> bool:
        """
        Partially close a position (reduce size)

        Args:
            position_id: Position ID
            close_size: Number of shares to close
            close_price: Closing price
            reason: Reason for partial close

        Returns:
            True if closed successfully
        """
        position = self.positions.get(position_id)
        if not position or position.status != PositionStatus.OPEN:
            return False

        if close_size > position.current_size:
            logger.warning(f"Cannot close {float(close_size)} shares (only {float(position.current_size)} available)")
            return False

        # Calculate P&L for closed portion
        closed_value = close_size * close_price
        closed_cost_basis = (close_size / position.entry_size) * position.entry_amount

        if position.side == "YES":
            partial_pnl = closed_value - closed_cost_basis
        else:
            partial_pnl = closed_cost_basis - closed_value

        # Update position
        old_size = position.current_size
        position.current_size -= close_size
        position.realized_pnl += partial_pnl
        position.market_value = position.current_size * position.current_price

        # Recalculate unrealized P&L for remaining position
        remaining_cost_basis = position.entry_amount - closed_cost_basis
        if position.side == "YES":
            position.unrealized_pnl = position.market_value - remaining_cost_basis
        else:
            position.unrealized_pnl = remaining_cost_basis - position.market_value

        position.total_pnl = position.unrealized_pnl + position.realized_pnl

        # Persist update
        await self._update_position_fill(position)
        await self._record_position_update(
            position,
            update_type="PARTIAL_CLOSE",
            old_size=old_size,
            reason=f"Closed {float(close_size)} shares @ ${float(close_price):.4f}"
        )

        logger.info(
            f"Partial close {position_id}: "
            f"{float(close_size)}/{float(old_size)} shares @ ${float(close_price):.4f} | "
            f"Partial P&L: ${float(partial_pnl):.2f}"
        )

        return True

    async def get_portfolio_metrics(self, since: Optional[datetime] = None) -> PortfolioMetrics:
        """
        Get aggregated portfolio performance metrics

        Args:
            since: Optional start date (default: all time)

        Returns:
            PortfolioMetrics with aggregated statistics
        """
        positions = list(self.positions.values())

        if since:
            positions = [p for p in positions if p.opened_at >= since]

        if not positions:
            return PortfolioMetrics(
                total_positions=0,
                open_positions=0,
                total_unrealized_pnl=Decimal(0),
                total_realized_pnl=Decimal(0),
                total_pnl=Decimal(0),
                avg_pnl_percentage=Decimal(0),
                winning_positions=0,
                losing_positions=0,
                win_rate=Decimal(0),
                total_exposure=Decimal(0)
            )

        open_positions = [p for p in positions if p.status == PositionStatus.OPEN]
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_realized = sum(p.realized_pnl for p in positions)
        total_pnl = total_unrealized + total_realized

        winning = sum(1 for p in positions if p.total_pnl > 0)
        losing = sum(1 for p in positions if p.total_pnl < 0)
        win_rate = Decimal(winning) / Decimal(len(positions)) * Decimal("100") if positions else Decimal(0)

        avg_pnl_pct = sum(p.pnl_percentage for p in positions) / Decimal(len(positions)) if positions else Decimal(0)
        total_exposure = sum(p.market_value or Decimal(0) for p in open_positions)

        return PortfolioMetrics(
            total_positions=len(positions),
            open_positions=len(open_positions),
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            total_pnl=total_pnl,
            avg_pnl_percentage=avg_pnl_pct,
            winning_positions=winning,
            losing_positions=losing,
            win_rate=win_rate,
            total_exposure=total_exposure
        )

    async def get_positions_requiring_action(self) -> List[Tuple[Position, str]]:
        """
        Get positions that need action (stop loss, take profit)

        Returns:
            List of (Position, action) tuples
        """
        requiring_action = []

        for position in self.positions.values():
            if position.status != PositionStatus.OPEN or not position.current_price:
                continue

            # Check stop loss
            if position.stop_loss_price and position.current_price <= position.stop_loss_price:
                requiring_action.append((position, "STOP_LOSS"))

            # Check take profit
            elif position.take_profit_price and position.current_price >= position.take_profit_price:
                requiring_action.append((position, "TAKE_PROFIT"))

        return requiring_action

    # ==================== Private Helper Methods ====================

    def _calculate_stop_loss(self, entry_price: Decimal, side: str) -> Decimal:
        """Calculate stop loss price"""
        # For YES positions: stop loss at -15% (price goes down)
        # For NO positions: stop loss at +15% (price goes up)
        if side == "YES":
            return entry_price * (Decimal("1") + self.limits.stop_loss_pct)
        else:
            return entry_price * (Decimal("1") - self.limits.stop_loss_pct)

    def _calculate_take_profit(self, entry_price: Decimal, side: str) -> Decimal:
        """Calculate take profit price"""
        # For YES positions: take profit at +50% (price goes up)
        # For NO positions: take profit at -50% (price goes down)
        if side == "YES":
            return min(entry_price * (Decimal("1") + self.limits.take_profit_pct), Decimal("0.99"))
        else:
            return max(entry_price * (Decimal("1") - self.limits.take_profit_pct), Decimal("0.01"))

    async def _check_position_limits(self, new_position_value: Decimal) -> Tuple[bool, str]:
        """Check if opening new position would exceed limits"""
        open_positions = [p for p in self.positions.values() if p.status == PositionStatus.OPEN]

        # Check position count
        if len(open_positions) >= self.limits.max_positions:
            return False, f"Position limit reached: {len(open_positions)}/{self.limits.max_positions}"

        # Check total exposure
        current_exposure = sum(p.market_value or Decimal(0) for p in open_positions)
        if current_exposure + new_position_value > self.limits.max_total_exposure:
            return False, (
                f"Exposure limit exceeded: ${float(current_exposure):.2f} + "
                f"${float(new_position_value):.2f} > ${float(self.limits.max_total_exposure):.2f}"
            )

        return True, "OK"

    async def _check_risk_triggers(self, position: Position):
        """Check if position hit stop loss or take profit"""
        if not position.current_price:
            return

        # Check stop loss
        if position.stop_loss_price and position.current_price <= position.stop_loss_price:
            logger.warning(
                f"STOP LOSS HIT: {position.position_id} @ ${float(position.current_price):.4f} "
                f"(trigger: ${float(position.stop_loss_price):.4f})"
            )
            # Auto-close position
            await self.close_position(
                position.position_id,
                position.current_price,
                CloseReason.STOP_LOSS,
                notes=f"Auto-closed: stop loss @ ${float(position.stop_loss_price):.4f}"
            )

        # Check take profit
        elif position.take_profit_price and position.current_price >= position.take_profit_price:
            logger.info(
                f"TAKE PROFIT HIT: {position.position_id} @ ${float(position.current_price):.4f} "
                f"(trigger: ${float(position.take_profit_price):.4f})"
            )
            # Auto-close position
            await self.close_position(
                position.position_id,
                position.current_price,
                CloseReason.TAKE_PROFIT,
                notes=f"Auto-closed: take profit @ ${float(position.take_profit_price):.4f}"
            )

    # ==================== Database Persistence ====================

    async def _persist_position(self, position: Position):
        """Persist new position to database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO positions (
                    position_id, whale_address, token_id, side,
                    entry_size, entry_price, entry_amount,
                    current_size, current_price, market_value,
                    unrealized_pnl, realized_pnl, pnl_percentage,
                    max_drawdown, max_profit,
                    stop_loss_price, take_profit_price,
                    kelly_fraction, edge, win_rate,
                    status, opened_at, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
            """,
                position.position_id, position.whale_address, position.token_id, position.side,
                float(position.entry_size), float(position.entry_price), float(position.entry_amount),
                float(position.current_size), float(position.current_price) if position.current_price else None,
                float(position.market_value) if position.market_value else None,
                float(position.unrealized_pnl), float(position.realized_pnl), float(position.pnl_percentage),
                float(position.max_drawdown), float(position.max_profit),
                float(position.stop_loss_price) if position.stop_loss_price else None,
                float(position.take_profit_price) if position.take_profit_price else None,
                float(position.kelly_fraction), float(position.edge) if position.edge else None,
                float(position.win_rate) if position.win_rate else None,
                position.status.value, position.opened_at, position.notes
            )

    async def _update_position_price(self, position: Position):
        """Update position price and P&L in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE positions
                SET current_price = $1, market_value = $2,
                    unrealized_pnl = $3, pnl_percentage = $4,
                    max_drawdown = $5, max_profit = $6,
                    price_last_updated_at = $7
                WHERE position_id = $8
            """,
                float(position.current_price) if position.current_price else None,
                float(position.market_value) if position.market_value else None,
                float(position.unrealized_pnl), float(position.pnl_percentage),
                float(position.max_drawdown), float(position.max_profit),
                position.price_last_updated_at, position.position_id
            )

    async def _update_position_fill(self, position: Position):
        """Update position fill details in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE positions
                SET current_size = $1, market_value = $2,
                    realized_pnl = $3, unrealized_pnl = $4, pnl_percentage = $5
                WHERE position_id = $6
            """,
                float(position.current_size), float(position.market_value) if position.market_value else None,
                float(position.realized_pnl), float(position.unrealized_pnl), float(position.pnl_percentage),
                position.position_id
            )

    async def _update_position_close(self, position: Position):
        """Update position closure in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE positions
                SET status = $1, closed_at = $2, close_reason = $3,
                    current_size = $4, market_value = $5,
                    realized_pnl = $6, unrealized_pnl = $7, pnl_percentage = $8,
                    notes = $9
                WHERE position_id = $10
            """,
                position.status.value, position.closed_at,
                position.close_reason.value if position.close_reason else None,
                float(position.current_size), float(position.market_value) if position.market_value else None,
                float(position.realized_pnl), float(position.unrealized_pnl), float(position.pnl_percentage),
                position.notes, position.position_id
            )

    async def _record_position_update(
        self,
        position: Position,
        update_type: str,
        old_price: Optional[Decimal] = None,
        old_size: Optional[Decimal] = None,
        old_market_value: Optional[Decimal] = None,
        old_unrealized_pnl: Optional[Decimal] = None,
        reason: Optional[str] = None
    ):
        """Record position update in audit trail"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO position_updates (
                    position_id, update_type,
                    old_size, old_price, old_market_value, old_unrealized_pnl,
                    new_size, new_price, new_market_value, new_unrealized_pnl,
                    reason
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                position.position_id, update_type,
                float(old_size) if old_size else None,
                float(old_price) if old_price else None,
                float(old_market_value) if old_market_value else None,
                float(old_unrealized_pnl) if old_unrealized_pnl else None,
                float(position.current_size),
                float(position.current_price) if position.current_price else None,
                float(position.market_value) if position.market_value else None,
                float(position.unrealized_pnl),
                reason
            )


# ==================== Example Usage ====================

async def main():
    """Example usage of ProductionPositionManager"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize database connection
    db_pool = await asyncpg.create_pool(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        database=settings.DATABASE_NAME
    )

    # Initialize position manager
    position_manager = ProductionPositionManager(db_pool)

    # Example: Open a position
    kelly_params = KellyParameters(
        win_rate=Decimal("0.60"),
        avg_win=Decimal("50"),
        avg_loss=Decimal("30"),
        kelly_fraction=Decimal("0.5")
    )

    position = await position_manager.open_position(
        whale_address="0x1234...",
        token_id="token_yes_123",
        side="YES",
        entry_price=Decimal("0.55"),
        balance=Decimal("5000"),
        kelly_params=kelly_params,
        notes="Following whale entry"
    )

    if position:
        print(f"\nOpened position: {position.position_id}")
        print(f"  Size: {float(position.entry_size):.2f} shares")
        print(f"  Entry: ${float(position.entry_price):.4f}")
        print(f"  Amount: ${float(position.entry_amount):.2f}")
        print(f"  Stop Loss: ${float(position.stop_loss_price):.4f}")
        print(f"  Take Profit: ${float(position.take_profit_price):.4f}")

        # Simulate price updates
        await asyncio.sleep(1)
        await position_manager.update_position_price(position.position_id, Decimal("0.60"))
        print(f"\nPrice update to $0.60:")
        print(f"  Unrealized P&L: ${float(position.unrealized_pnl):.2f} ({float(position.pnl_percentage):.2f}%)")

        # Get portfolio metrics
        metrics = await position_manager.get_portfolio_metrics()
        print(f"\nPortfolio Metrics:")
        print(f"  Open Positions: {metrics.open_positions}")
        print(f"  Total P&L: ${float(metrics.total_pnl):.2f}")
        print(f"  Total Exposure: ${float(metrics.total_exposure):.2f}")

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
