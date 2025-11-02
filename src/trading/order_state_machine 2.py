"""
Order State Machine for Production Trading
Manages order lifecycle with database persistence and state transitions
Week 3: Order Execution Engine
"""

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

import asyncpg

from src.config import settings

logger = logging.getLogger(__name__)


# ==================== Order States ====================

class OrderState(Enum):
    """Order lifecycle states"""
    PENDING = "PENDING"           # Created, not yet submitted
    SUBMITTED = "SUBMITTED"        # Sent to exchange
    ACKNOWLEDGED = "ACKNOWLEDGED"  # Exchange confirmed receipt
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partial execution
    FILLED = "FILLED"              # Fully executed
    CONFIRMED = "CONFIRMED"        # Final confirmation received
    CANCELLING = "CANCELLING"      # Cancel request sent
    CANCELLED = "CANCELLED"        # Cancel confirmed
    FAILED = "FAILED"              # Permanent failure
    TIMEOUT = "TIMEOUT"            # Timed out waiting for response
    DEAD_LETTER = "DEAD_LETTER"    # Moved to dead letter queue


@dataclass
class OrderStateTransition:
    """Record of a state transition"""
    order_id: str
    from_state: OrderState
    to_state: OrderState
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ManagedOrder:
    """Managed order with full lifecycle tracking"""
    # Identification
    order_id: str
    idempotency_key: str

    # Order details
    token_id: str
    side: str
    size: Decimal
    price: Optional[Decimal]
    order_type: str  # "LIMIT", "MARKET", "FOK"

    # State tracking
    state: OrderState
    exchange_order_id: Optional[str] = None

    # Execution details
    filled_size: Decimal = Decimal(0)
    remaining_size: Optional[Decimal] = None
    avg_fill_price: Optional[Decimal] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    # Retry & error tracking
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None

    # Transitions
    transitions: List[OrderStateTransition] = field(default_factory=list)

    def __post_init__(self):
        """Initialize remaining size"""
        if self.remaining_size is None:
            self.remaining_size = self.size


# ==================== State Machine Manager ====================

class OrderStateMachine:
    """
    Manages order lifecycle with state transitions and persistence

    Valid transitions:
    PENDING → SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED → CONFIRMED
                       ↓                 ↓                 ↓
                    FAILED          CANCELLING       CANCELLING
                       ↓                 ↓                 ↓
                 DEAD_LETTER        CANCELLED        CANCELLED
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        OrderState.PENDING: [OrderState.SUBMITTED, OrderState.FAILED],
        OrderState.SUBMITTED: [OrderState.ACKNOWLEDGED, OrderState.FAILED, OrderState.TIMEOUT, OrderState.CANCELLING],
        OrderState.ACKNOWLEDGED: [OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLING, OrderState.FAILED],
        OrderState.PARTIALLY_FILLED: [OrderState.FILLED, OrderState.CANCELLING, OrderState.TIMEOUT],
        OrderState.FILLED: [OrderState.CONFIRMED],
        OrderState.CANCELLING: [OrderState.CANCELLED, OrderState.FAILED],
        OrderState.CANCELLED: [],
        OrderState.CONFIRMED: [],
        OrderState.FAILED: [OrderState.DEAD_LETTER, OrderState.PENDING],  # Allow retry from FAILED
        OrderState.TIMEOUT: [OrderState.CANCELLING, OrderState.PENDING, OrderState.DEAD_LETTER],
        OrderState.DEAD_LETTER: []
    }

    # Terminal states (no further transitions)
    TERMINAL_STATES = {
        OrderState.CONFIRMED,
        OrderState.CANCELLED,
        OrderState.DEAD_LETTER
    }

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize state machine

        Args:
            db_pool: Database connection pool
        """
        self.db = db_pool
        self.orders: Dict[str, ManagedOrder] = {}

    async def create_order(
        self,
        token_id: str,
        side: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "LIMIT"
    ) -> ManagedOrder:
        """
        Create a new managed order with idempotency key

        Args:
            token_id: Token to trade
            side: BUY or SELL
            size: Order size
            price: Limit price (None for market orders)
            order_type: LIMIT, MARKET, or FOK

        Returns:
            ManagedOrder in PENDING state
        """
        # Generate unique IDs
        order_id = f"order_{uuid.uuid4().hex[:16]}"
        idempotency_key = f"idem_{uuid.uuid4().hex}"

        # Create order
        order = ManagedOrder(
            order_id=order_id,
            idempotency_key=idempotency_key,
            token_id=token_id,
            side=side,
            size=size,
            price=price,
            order_type=order_type,
            state=OrderState.PENDING
        )

        # Store in memory
        self.orders[order_id] = order

        # Persist to database
        await self._persist_order(order)

        logger.info(f"Created order {order_id}: {side} {size} @ {price} (idem: {idempotency_key[:12]}...)")

        return order

    async def transition(
        self,
        order_id: str,
        to_state: OrderState,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Attempt to transition an order to a new state

        Args:
            order_id: Order ID to transition
            to_state: Target state
            reason: Reason for transition
            metadata: Additional metadata

        Returns:
            True if transition successful, False otherwise
        """
        order = self.orders.get(order_id)

        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        from_state = order.state

        # Check if transition is valid
        if to_state not in self.VALID_TRANSITIONS.get(from_state, []):
            logger.warning(
                f"Invalid transition for {order_id}: "
                f"{from_state.value} → {to_state.value}"
            )
            return False

        # Record transition
        transition = OrderStateTransition(
            order_id=order_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {}
        )

        order.transitions.append(transition)
        order.state = to_state

        # Update timestamps
        if to_state == OrderState.SUBMITTED:
            order.submitted_at = datetime.now()
        elif to_state == OrderState.FILLED:
            order.filled_at = datetime.now()
        elif to_state == OrderState.CONFIRMED:
            order.confirmed_at = datetime.now()

        # Persist transition
        await self._persist_transition(transition)
        await self._update_order_state(order)

        logger.info(
            f"Order {order_id}: {from_state.value} → {to_state.value}"
            f"{f' ({reason})' if reason else ''}"
        )

        return True

    async def update_fill(
        self,
        order_id: str,
        filled_size: Decimal,
        avg_price: Decimal
    ) -> bool:
        """
        Update order fill details

        Args:
            order_id: Order ID
            filled_size: Total filled size
            avg_price: Average fill price

        Returns:
            True if updated successfully
        """
        order = self.orders.get(order_id)

        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        # Update fill details
        order.filled_size = filled_size
        order.remaining_size = order.size - filled_size
        order.avg_fill_price = avg_price

        # Determine state based on fill percentage
        if order.remaining_size == 0:
            # Fully filled
            await self.transition(
                order_id,
                OrderState.FILLED,
                reason=f"Fully filled: {filled_size} @ {avg_price}"
            )
        elif filled_size > 0:
            # Partially filled
            fill_pct = (filled_size / order.size) * 100
            await self.transition(
                order_id,
                OrderState.PARTIALLY_FILLED,
                reason=f"Partial fill: {fill_pct:.1f}%"
            )

        # Persist update
        await self._update_order_fill(order)

        return True

    async def set_exchange_id(self, order_id: str, exchange_order_id: str) -> bool:
        """
        Set exchange order ID after submission

        Args:
            order_id: Internal order ID
            exchange_order_id: Exchange-assigned order ID

        Returns:
            True if set successfully
        """
        order = self.orders.get(order_id)

        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        order.exchange_order_id = exchange_order_id

        # Update in database
        await self._update_exchange_id(order)

        logger.info(f"Order {order_id} mapped to exchange ID: {exchange_order_id}")

        return True

    async def record_error(self, order_id: str, error_message: str) -> bool:
        """
        Record an error for an order

        Args:
            order_id: Order ID
            error_message: Error message

        Returns:
            True if recorded successfully
        """
        order = self.orders.get(order_id)

        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        order.error_message = error_message
        order.retry_count += 1

        # Check if we should move to dead letter queue
        if order.retry_count >= order.max_retries:
            await self.transition(
                order_id,
                OrderState.DEAD_LETTER,
                reason=f"Max retries exceeded: {error_message}"
            )
        else:
            await self.transition(
                order_id,
                OrderState.FAILED,
                reason=error_message
            )

        # Persist error
        await self._update_order_error(order)

        return True

    async def get_pending_orders(self, max_age_seconds: int = 300) -> List[ManagedOrder]:
        """
        Get orders stuck in PENDING state

        Args:
            max_age_seconds: Max age before considering stuck (default: 5 min)

        Returns:
            List of stuck pending orders
        """
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)

        stuck_orders = [
            order for order in self.orders.values()
            if order.state == OrderState.PENDING and order.created_at < cutoff
        ]

        return stuck_orders

    async def get_dead_letter_queue(self) -> List[ManagedOrder]:
        """
        Get all orders in dead letter queue

        Returns:
            List of dead letter orders
        """
        return [
            order for order in self.orders.values()
            if order.state == OrderState.DEAD_LETTER
        ]

    async def cleanup_terminal_orders(self, retention_hours: int = 24) -> int:
        """
        Clean up old terminal state orders from memory

        Args:
            retention_hours: Hours to retain terminal orders (default: 24)

        Returns:
            Number of orders cleaned up
        """
        cutoff = datetime.now() - timedelta(hours=retention_hours)
        cleaned = 0

        for order_id, order in list(self.orders.items()):
            if order.state in self.TERMINAL_STATES:
                # Check if old enough
                relevant_time = order.confirmed_at or order.filled_at or order.created_at

                if relevant_time < cutoff:
                    del self.orders[order_id]
                    cleaned += 1

        logger.info(f"Cleaned up {cleaned} old terminal orders")

        return cleaned

    # ==================== Database Persistence ====================

    async def _persist_order(self, order: ManagedOrder):
        """Persist new order to database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders (
                    order_id, idempotency_key, token_id, side, size, price,
                    order_type, state, created_at, retry_count, max_retries
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                order.order_id,
                order.idempotency_key,
                order.token_id,
                order.side,
                float(order.size),
                float(order.price) if order.price else None,
                order.order_type,
                order.state.value,
                order.created_at,
                order.retry_count,
                order.max_retries
            )

    async def _update_order_state(self, order: ManagedOrder):
        """Update order state in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE orders
                SET state = $1, submitted_at = $2, filled_at = $3, confirmed_at = $4
                WHERE order_id = $5
            """,
                order.state.value,
                order.submitted_at,
                order.filled_at,
                order.confirmed_at,
                order.order_id
            )

    async def _update_order_fill(self, order: ManagedOrder):
        """Update order fill details in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE orders
                SET filled_size = $1, remaining_size = $2, avg_fill_price = $3
                WHERE order_id = $4
            """,
                float(order.filled_size),
                float(order.remaining_size),
                float(order.avg_fill_price) if order.avg_fill_price else None,
                order.order_id
            )

    async def _update_exchange_id(self, order: ManagedOrder):
        """Update exchange order ID in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE orders
                SET exchange_order_id = $1
                WHERE order_id = $2
            """,
                order.exchange_order_id,
                order.order_id
            )

    async def _update_order_error(self, order: ManagedOrder):
        """Update order error details in database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE orders
                SET error_message = $1, retry_count = $2, state = $3
                WHERE order_id = $4
            """,
                order.error_message,
                order.retry_count,
                order.state.value,
                order.order_id
            )

    async def _persist_transition(self, transition: OrderStateTransition):
        """Persist state transition to database"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO order_transitions (
                    order_id, from_state, to_state, timestamp, reason, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
                transition.order_id,
                transition.from_state.value,
                transition.to_state.value,
                transition.timestamp,
                transition.reason,
                transition.metadata
            )


# ==================== Example Usage ====================

async def main():
    """Example usage of OrderStateMachine"""
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

    # Initialize state machine
    state_machine = OrderStateMachine(db_pool)

    # Example: Create and manage an order lifecycle
    order = await state_machine.create_order(
        token_id="test_token_123",
        side="BUY",
        size=Decimal("100"),
        price=Decimal("0.55")
    )

    print(f"\n1. Created order: {order.order_id} (state: {order.state.value})")

    # Transition to SUBMITTED
    await state_machine.transition(order.order_id, OrderState.SUBMITTED, reason="Sent to exchange")
    print(f"2. Order submitted (state: {state_machine.orders[order.order_id].state.value})")

    # Acknowledge
    await state_machine.transition(order.order_id, OrderState.ACKNOWLEDGED, reason="Exchange ACK")
    await state_machine.set_exchange_id(order.order_id, "exchange_123456")
    print(f"3. Order acknowledged (exchange ID: {order.exchange_order_id})")

    # Partial fill
    await state_machine.update_fill(order.order_id, Decimal("50"), Decimal("0.55"))
    print(f"4. Partial fill: 50/100 @ 0.55")

    # Complete fill
    await state_machine.update_fill(order.order_id, Decimal("100"), Decimal("0.55"))
    print(f"5. Fully filled: 100/100 @ 0.55 (state: {state_machine.orders[order.order_id].state.value})")

    # Confirm
    await state_machine.transition(order.order_id, OrderState.CONFIRMED, reason="Final confirmation")
    print(f"6. Order confirmed (state: {state_machine.orders[order.order_id].state.value})")

    # Show transition history
    print(f"\nTransition history:")
    for t in order.transitions:
        print(f"  {t.from_state.value} → {t.to_state.value}: {t.reason}")

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
