"""
Stop-Loss & Take-Profit Automation System
Week 5: Risk Management Framework - Automated Risk Controls
Implements automatic position exits with pre-resolution protection
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from src.trading.production_position_manager import (
    ProductionPositionManager,
    Position,
    PositionStatus,
    CloseReason
)

logger = logging.getLogger(__name__)


# ==================== Risk Control Configuration ====================

@dataclass
class RiskControlLimits:
    """Configuration for stop-loss and take-profit"""
    # Stop-loss settings (-15% research-backed threshold)
    stop_loss_pct: Decimal = Decimal("-0.15")

    # Take-profit settings (+30% lock-in)
    take_profit_pct: Decimal = Decimal("0.30")

    # Trailing stop (move stop-loss as position profits)
    trailing_stop_enabled: bool = True
    trailing_stop_activation_pct: Decimal = Decimal("0.10")  # Activate at +10%
    trailing_stop_distance_pct: Decimal = Decimal("0.05")    # Trail by 5%

    # Pre-resolution exit (avoid illiquid end-of-market)
    pre_resolution_exit_enabled: bool = True
    pre_resolution_hours: int = 2

    # Check frequency
    check_interval_seconds: float = 5.0  # Check every 5 seconds


class ExitTrigger(Enum):
    """Reasons for position exit"""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    PRE_RESOLUTION = "PRE_RESOLUTION"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class ExitEvent:
    """Record of an automated exit"""
    position_id: str
    trigger: ExitTrigger
    exit_price: Decimal
    pnl: Decimal
    pnl_percentage: Decimal
    timestamp: datetime
    reason: str


@dataclass
class TrailingStopState:
    """State tracking for trailing stop"""
    position_id: str
    activated: bool = False
    highest_price: Optional[Decimal] = None
    current_stop_price: Optional[Decimal] = None


# ==================== Stop-Loss & Take-Profit Manager ====================

class StopLossTakeProfitManager:
    """
    Automated Stop-Loss & Take-Profit System

    Features:
    - Automatic stop-loss at -15% (research-backed threshold)
    - Take-profit at +30% (lock in gains)
    - Trailing stop-loss (move stop up as profit increases)
    - Pre-resolution exit (close 2 hours before market resolution)
    - Emergency exit capability

    Prevents catastrophic losses and locks in profits automatically.
    """

    def __init__(
        self,
        position_manager: ProductionPositionManager,
        limits: Optional[RiskControlLimits] = None
    ):
        """
        Initialize stop-loss & take-profit manager

        Args:
            position_manager: Position manager to monitor
            limits: Risk control limits configuration
        """
        self.position_manager = position_manager
        self.limits = limits or RiskControlLimits()

        # Trailing stop state tracking
        self.trailing_stops: Dict[str, TrailingStopState] = {}

        # Exit event history
        self.exit_events: List[ExitEvent] = []

        # Monitoring state
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None

        logger.info(
            f"StopLossTakeProfitManager initialized: "
            f"SL={float(self.limits.stop_loss_pct)*100:.1f}%, "
            f"TP={float(self.limits.take_profit_pct)*100:.1f}%, "
            f"trailing={self.limits.trailing_stop_enabled}"
        )

    async def start(self):
        """Start the stop-loss/take-profit monitoring loop"""
        if self.is_running:
            logger.warning("StopLossTakeProfitManager already running")
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("Stop-loss & take-profit monitoring started")

    async def stop(self):
        """Stop the monitoring loop"""
        if not self.is_running:
            return

        self.is_running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stop-loss & take-profit monitoring stopped")

    async def _monitor_loop(self):
        """Main monitoring loop - checks all positions periodically"""
        logger.info("SL/TP monitor loop started")

        while self.is_running:
            try:
                # Get all open positions
                open_positions = [
                    p for p in self.position_manager.positions.values()
                    if p.status == PositionStatus.OPEN
                ]

                if not open_positions:
                    await asyncio.sleep(self.limits.check_interval_seconds)
                    continue

                # Check each position for exit triggers
                check_tasks = [
                    self._check_position_triggers(position)
                    for position in open_positions
                ]

                await asyncio.gather(*check_tasks, return_exceptions=True)

                # Log periodic stats
                if len(self.exit_events) > 0:
                    recent_exits = len([e for e in self.exit_events if e.timestamp > datetime.now() - timedelta(hours=1)])
                    if recent_exits > 0:
                        logger.info(f"Recent exits (1h): {recent_exits}, Total exits: {len(self.exit_events)}")

            except asyncio.CancelledError:
                logger.info("SL/TP monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in SL/TP monitor loop: {e}", exc_info=True)

            # Wait for next check
            try:
                await asyncio.sleep(self.limits.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _check_position_triggers(self, position: Position):
        """
        Check if position should be exited based on triggers

        Args:
            position: Position to check
        """
        if not position.current_price:
            return

        # Check pre-resolution exit first (highest priority)
        if self.limits.pre_resolution_exit_enabled:
            should_exit, reason = self._should_pre_resolution_exit(position)
            if should_exit:
                await self._execute_exit(
                    position,
                    ExitTrigger.PRE_RESOLUTION,
                    reason
                )
                return

        # Calculate P&L percentage
        pnl_pct = position.pnl_percentage

        # Check stop-loss
        if pnl_pct <= self.limits.stop_loss_pct * Decimal("100"):
            await self._execute_exit(
                position,
                ExitTrigger.STOP_LOSS,
                f"Stop-loss hit: {float(pnl_pct):.2f}% <= {float(self.limits.stop_loss_pct)*100:.2f}%"
            )
            return

        # Check take-profit
        if pnl_pct >= self.limits.take_profit_pct * Decimal("100"):
            await self._execute_exit(
                position,
                ExitTrigger.TAKE_PROFIT,
                f"Take-profit hit: {float(pnl_pct):.2f}% >= {float(self.limits.take_profit_pct)*100:.2f}%"
            )
            return

        # Check trailing stop
        if self.limits.trailing_stop_enabled:
            should_exit, reason = await self._check_trailing_stop(position)
            if should_exit:
                await self._execute_exit(
                    position,
                    ExitTrigger.TRAILING_STOP,
                    reason
                )
                return

    def _should_pre_resolution_exit(self, position: Position) -> Tuple[bool, str]:
        """
        Check if position should exit before market resolution

        Args:
            position: Position to check

        Returns:
            (should_exit, reason) tuple
        """
        # TODO: In production, fetch actual market resolution time
        # For now, we'll check if position is old enough
        position_age_hours = (datetime.now() - position.opened_at).total_seconds() / 3600

        # Example: If position is older than 22 hours (assuming 24h markets)
        # and we want to exit 2 hours before resolution
        # This is a placeholder - real implementation needs market resolution time
        if position_age_hours >= 22:
            return True, f"Pre-resolution exit: Position age {position_age_hours:.1f}h >= 22h"

        return False, ""

    async def _check_trailing_stop(self, position: Position) -> Tuple[bool, str]:
        """
        Check and update trailing stop for a position

        Args:
            position: Position to check

        Returns:
            (should_exit, reason) tuple
        """
        if not position.current_price:
            return False, ""

        # Get or create trailing stop state
        if position.position_id not in self.trailing_stops:
            self.trailing_stops[position.position_id] = TrailingStopState(
                position_id=position.position_id
            )

        trailing_state = self.trailing_stops[position.position_id]

        # Calculate current P&L percentage
        pnl_pct = position.pnl_percentage

        # Activate trailing stop if profit exceeds activation threshold
        if not trailing_state.activated:
            if pnl_pct >= self.limits.trailing_stop_activation_pct * Decimal("100"):
                trailing_state.activated = True
                trailing_state.highest_price = position.current_price
                trailing_state.current_stop_price = position.current_price * (
                    Decimal("1") - self.limits.trailing_stop_distance_pct
                )
                logger.info(
                    f"Trailing stop activated for {position.position_id}: "
                    f"stop @ ${float(trailing_state.current_stop_price):.4f}"
                )
            return False, ""

        # Update trailing stop if price moves higher
        if position.current_price > trailing_state.highest_price:
            trailing_state.highest_price = position.current_price
            new_stop = position.current_price * (
                Decimal("1") - self.limits.trailing_stop_distance_pct
            )

            # Only move stop up, never down
            if new_stop > trailing_state.current_stop_price:
                old_stop = trailing_state.current_stop_price
                trailing_state.current_stop_price = new_stop
                logger.info(
                    f"Trailing stop moved up for {position.position_id}: "
                    f"${float(old_stop):.4f} → ${float(new_stop):.4f}"
                )

        # Check if current price hit the trailing stop
        if position.current_price <= trailing_state.current_stop_price:
            return True, (
                f"Trailing stop hit: price ${float(position.current_price):.4f} "
                f"<= stop ${float(trailing_state.current_stop_price):.4f}"
            )

        return False, ""

    async def _execute_exit(
        self,
        position: Position,
        trigger: ExitTrigger,
        reason: str
    ):
        """
        Execute position exit

        Args:
            position: Position to exit
            trigger: Exit trigger reason
            reason: Human-readable reason
        """
        try:
            # Map trigger to CloseReason
            close_reason_map = {
                ExitTrigger.STOP_LOSS: CloseReason.STOP_LOSS,
                ExitTrigger.TAKE_PROFIT: CloseReason.TAKE_PROFIT,
                ExitTrigger.TRAILING_STOP: CloseReason.TAKE_PROFIT,  # Treat as profit taking
                ExitTrigger.PRE_RESOLUTION: CloseReason.PRE_RESOLUTION,
                ExitTrigger.MANUAL: CloseReason.MANUAL,
                ExitTrigger.EMERGENCY: CloseReason.MANUAL
            }

            close_reason = close_reason_map.get(trigger, CloseReason.MANUAL)

            # Close position via position manager
            success = await self.position_manager.close_position(
                position.position_id,
                position.current_price,
                close_reason,
                notes=f"Auto-exit: {reason}"
            )

            if success:
                # Record exit event
                exit_event = ExitEvent(
                    position_id=position.position_id,
                    trigger=trigger,
                    exit_price=position.current_price,
                    pnl=position.realized_pnl,
                    pnl_percentage=position.pnl_percentage,
                    timestamp=datetime.now(),
                    reason=reason
                )
                self.exit_events.append(exit_event)

                # Clean up trailing stop state
                if position.position_id in self.trailing_stops:
                    del self.trailing_stops[position.position_id]

                logger.info(
                    f"Position {position.position_id} auto-closed: "
                    f"{trigger.value} | P&L: ${float(position.realized_pnl):.2f} "
                    f"({float(position.pnl_percentage):.2f}%)"
                )
            else:
                logger.error(f"Failed to close position {position.position_id}")

        except Exception as e:
            logger.error(f"Error executing exit for {position.position_id}: {e}", exc_info=True)

    async def emergency_exit_all(self, reason: str):
        """
        Emergency exit all open positions

        Args:
            reason: Reason for emergency exit
        """
        open_positions = [
            p for p in self.position_manager.positions.values()
            if p.status == PositionStatus.OPEN
        ]

        logger.critical(f"EMERGENCY EXIT ALL: {len(open_positions)} positions | Reason: {reason}")

        # Close all positions concurrently
        close_tasks = [
            self._execute_exit(position, ExitTrigger.EMERGENCY, reason)
            for position in open_positions
        ]

        await asyncio.gather(*close_tasks, return_exceptions=True)

        logger.critical(f"Emergency exit complete: {len(open_positions)} positions closed")

    def get_statistics(self) -> Dict:
        """Get exit statistics"""
        if not self.exit_events:
            return {
                "total_exits": 0,
                "by_trigger": {},
                "avg_pnl": 0,
                "avg_pnl_pct": 0
            }

        trigger_counts = {}
        for event in self.exit_events:
            trigger_counts[event.trigger.value] = trigger_counts.get(event.trigger.value, 0) + 1

        total_pnl = sum(event.pnl for event in self.exit_events)
        total_pnl_pct = sum(event.pnl_percentage for event in self.exit_events)

        return {
            "total_exits": len(self.exit_events),
            "by_trigger": trigger_counts,
            "avg_pnl": float(total_pnl / len(self.exit_events)),
            "avg_pnl_pct": float(total_pnl_pct / len(self.exit_events)),
            "total_pnl": float(total_pnl),
            "winning_exits": len([e for e in self.exit_events if e.pnl > 0]),
            "losing_exits": len([e for e in self.exit_events if e.pnl < 0])
        }

    def get_trailing_stop_status(self) -> List[Dict]:
        """Get status of all trailing stops"""
        return [
            {
                "position_id": state.position_id,
                "activated": state.activated,
                "highest_price": float(state.highest_price) if state.highest_price else None,
                "current_stop_price": float(state.current_stop_price) if state.current_stop_price else None
            }
            for state in self.trailing_stops.values()
        ]


# ==================== Example Usage ====================

async def main():
    """Example usage of StopLossTakeProfitManager"""
    import asyncpg
    from src.config import settings
    from src.trading.kelly_criterion_sizer import KellyParameters

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
        entry_price=Decimal("0.50"),
        balance=Decimal("5000"),
        kelly_params=kelly_params
    )

    if position:
        print(f"\nOpened position: {position.position_id}")
        print(f"Entry price: ${float(position.entry_price):.4f}")
        print(f"Stop-loss: ${float(position.stop_loss_price):.4f}")
        print(f"Take-profit: ${float(position.take_profit_price):.4f}")

        # Initialize SL/TP manager
        sl_tp_manager = StopLossTakeProfitManager(
            position_manager=position_manager,
            limits=RiskControlLimits(
                stop_loss_pct=Decimal("-0.15"),
                take_profit_pct=Decimal("0.30"),
                trailing_stop_enabled=True,
                check_interval_seconds=1.0  # Fast for demo
            )
        )

        await sl_tp_manager.start()

        # Simulate price movements
        print("\nSimulating price movements...")

        # Price goes up (profit)
        await position_manager.update_position_price(position.position_id, Decimal("0.55"))
        print(f"Price: $0.55, P&L: ${float(position.unrealized_pnl):.2f} ({float(position.pnl_percentage):.2f}%)")
        await asyncio.sleep(2)

        # Price goes up more (trigger trailing stop)
        await position_manager.update_position_price(position.position_id, Decimal("0.60"))
        print(f"Price: $0.60, P&L: ${float(position.unrealized_pnl):.2f} ({float(position.pnl_percentage):.2f}%)")
        await asyncio.sleep(2)

        # Check trailing stop status
        trailing_status = sl_tp_manager.get_trailing_stop_status()
        print(f"\nTrailing stops: {trailing_status}")

        # Get statistics
        stats = sl_tp_manager.get_statistics()
        print(f"\nExit statistics:")
        print(f"  Total exits: {stats['total_exits']}")
        print(f"  By trigger: {stats['by_trigger']}")

        await sl_tp_manager.stop()

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
