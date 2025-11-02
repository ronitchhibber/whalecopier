"""
Adaptive Order Executor with Three-Phase Execution Strategy
Inspired by production copy trading bots (Zydomus implementation)

Three-Phase Approach:
- Phase 1: Target price with standard timeout (30s)
- Phase 2: Adjust price ±2 cents, reduce size by 10%, extended timeout (45s)
- Phase 3: Aggressive pricing ±5 cents, reduce size by 25%, final timeout (60s)

This balances fill probability against slippage across multiple attempts.
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ExecutionPhase(Enum):
    """Execution phase stages"""
    PHASE_1 = "phase_1"  # Conservative: Target price
    PHASE_2 = "phase_2"  # Moderate: Small price adjustment
    PHASE_3 = "phase_3"  # Aggressive: Larger price adjustment


@dataclass
class PhaseConfig:
    """Configuration for an execution phase"""
    phase: ExecutionPhase
    price_adjustment_cents: Decimal  # Cents to adjust from target price
    size_reduction_pct: Decimal  # Percentage to reduce size
    timeout_seconds: int  # Timeout for this phase
    description: str


@dataclass
class ExecutionResult:
    """Result of multi-phase execution attempt"""
    success: bool
    order_id: Optional[str]
    filled_size: Decimal
    avg_fill_price: Optional[Decimal]
    final_phase: ExecutionPhase
    total_time_seconds: float
    error_message: Optional[str] = None


class ProportionalSizer:
    """
    Proportional position sizing with copyRatio parameter
    Allows flexible risk scaling without code changes
    """

    def __init__(self, copy_ratio: float = 0.5, min_size: Decimal = Decimal("10"), max_size: Decimal = Decimal("1000")):
        """
        Initialize proportional sizer

        Args:
            copy_ratio: Fraction of whale trade size to copy (0.0 - 1.0)
                       0.5 = 50% of whale size, 1.0 = 100% (full copy)
            min_size: Minimum position size in dollars
            max_size: Maximum position size in dollars
        """
        self.copy_ratio = Decimal(str(copy_ratio))
        self.min_size = min_size
        self.max_size = max_size

        logger.info(f"ProportionalSizer initialized: copyRatio={copy_ratio}, min=${float(min_size)}, max=${float(max_size)}")

    def calculate_size(
        self,
        whale_trade_size: Decimal,
        whale_trade_price: Decimal,
        balance: Optional[Decimal] = None,
        risk_multiplier: float = 1.0
    ) -> Decimal:
        """
        Calculate proportional position size

        Args:
            whale_trade_size: Size of whale's trade
            whale_trade_price: Price of whale's trade
            balance: Current account balance (for balance-based limiting)
            risk_multiplier: Additional risk scaling (from risk manager)

        Returns:
            Calculated position size
        """
        # Calculate whale trade value
        whale_value = whale_trade_size * whale_trade_price

        # Apply copy ratio
        target_value = whale_value * self.copy_ratio * Decimal(str(risk_multiplier))

        # Apply min/max bounds
        bounded_value = max(self.min_size, min(target_value, self.max_size))

        # Check balance constraint (if provided)
        if balance is not None:
            # Don't use more than 20% of balance on single trade
            max_allowed = balance * Decimal("0.20")
            bounded_value = min(bounded_value, max_allowed)

        # Convert back to size at current price
        if whale_trade_price > 0:
            final_size = bounded_value / whale_trade_price
        else:
            logger.warning(f"Invalid whale price: {whale_trade_price}, returning min size")
            final_size = self.min_size / Decimal("0.5")  # Assume $0.50 price

        logger.info(
            f"Position sizing: whale=${float(whale_value):.2f} → "
            f"target=${float(target_value):.2f} → "
            f"bounded=${float(bounded_value):.2f} (size={float(final_size):.2f})"
        )

        return final_size


class AdaptiveOrderExecutor:
    """
    Three-phase adaptive order executor with progressive price adjustment
    Maximizes fill probability while minimizing slippage
    """

    def __init__(self, client, enable_three_phase: bool = True):
        """
        Initialize adaptive executor

        Args:
            client: Polymarket CLOB client
            enable_three_phase: Enable three-phase execution (vs single-phase)
        """
        self.client = client
        self.enable_three_phase = enable_three_phase

        # Define phase configurations
        self.phases = [
            PhaseConfig(
                phase=ExecutionPhase.PHASE_1,
                price_adjustment_cents=Decimal("0.00"),  # No adjustment
                size_reduction_pct=Decimal("0.00"),  # Full size
                timeout_seconds=30,
                description="Conservative: Target price, full size"
            ),
            PhaseConfig(
                phase=ExecutionPhase.PHASE_2,
                price_adjustment_cents=Decimal("0.02"),  # ±2 cents
                size_reduction_pct=Decimal("0.10"),  # -10% size
                timeout_seconds=45,
                description="Moderate: ±2¢ price, -10% size"
            ),
            PhaseConfig(
                phase=ExecutionPhase.PHASE_3,
                price_adjustment_cents=Decimal("0.05"),  # ±5 cents
                size_reduction_pct=Decimal("0.25"),  # -25% size
                timeout_seconds=60,
                description="Aggressive: ±5¢ price, -25% size"
            )
        ]

        # Statistics
        self.stats = {
            "phase_1_fills": 0,
            "phase_2_fills": 0,
            "phase_3_fills": 0,
            "total_attempts": 0,
            "total_failures": 0
        }

    async def execute_with_phases(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        target_price: Decimal
    ) -> ExecutionResult:
        """
        Execute order using three-phase adaptive strategy

        Args:
            market_id: Market identifier
            token_id: Token identifier
            side: "BUY" or "SELL"
            size: Order size
            target_price: Target execution price

        Returns:
            ExecutionResult with execution details
        """
        self.stats["total_attempts"] += 1
        start_time = datetime.now()

        # Determine phase order (BUY = increase price, SELL = decrease price)
        price_direction = 1 if side == "BUY" else -1

        # Try each phase in sequence
        for phase_config in self.phases:
            if not self.enable_three_phase and phase_config.phase != ExecutionPhase.PHASE_1:
                # Skip phases 2 & 3 if three-phase is disabled
                continue

            logger.info(
                f"🎯 Phase {phase_config.phase.value}: {phase_config.description}"
            )

            # Calculate adjusted parameters
            adjusted_price = target_price + (phase_config.price_adjustment_cents * price_direction)
            adjusted_size = size * (Decimal("1") - phase_config.size_reduction_pct)

            # Ensure price is in valid range [0.01, 0.99]
            adjusted_price = max(Decimal("0.01"), min(adjusted_price, Decimal("0.99")))

            logger.info(
                f"Attempting {side} {float(adjusted_size):.2f} @ ${float(adjusted_price):.4f} "
                f"(timeout: {phase_config.timeout_seconds}s)"
            )

            try:
                # Place order
                order_result = await self._place_order(
                    market_id=market_id,
                    token_id=token_id,
                    side=side,
                    size=adjusted_size,
                    price=adjusted_price
                )

                if not order_result["success"]:
                    logger.warning(f"Order placement failed: {order_result.get('error', 'Unknown error')}")
                    continue

                order_id = order_result["order_id"]

                # Wait for fill
                fill_result = await self._wait_for_fill(
                    order_id=order_id,
                    timeout_seconds=phase_config.timeout_seconds
                )

                if fill_result["filled"]:
                    # Success!
                    elapsed = (datetime.now() - start_time).total_seconds()

                    # Update stats
                    if phase_config.phase == ExecutionPhase.PHASE_1:
                        self.stats["phase_1_fills"] += 1
                    elif phase_config.phase == ExecutionPhase.PHASE_2:
                        self.stats["phase_2_fills"] += 1
                    elif phase_config.phase == ExecutionPhase.PHASE_3:
                        self.stats["phase_3_fills"] += 1

                    logger.info(
                        f"✅ Order filled in Phase {phase_config.phase.value}: "
                        f"{float(fill_result['filled_size']):.2f} @ ${float(fill_result['avg_price']):.4f} "
                        f"({elapsed:.1f}s)"
                    )

                    return ExecutionResult(
                        success=True,
                        order_id=order_id,
                        filled_size=fill_result["filled_size"],
                        avg_fill_price=fill_result["avg_price"],
                        final_phase=phase_config.phase,
                        total_time_seconds=elapsed
                    )

                # Not filled - cancel and try next phase
                logger.warning(f"Phase {phase_config.phase.value} timeout - cancelling and moving to next phase")
                await self._cancel_order(order_id)

            except Exception as e:
                logger.error(f"Error in phase {phase_config.phase.value}: {e}")
                continue

        # All phases failed
        self.stats["total_failures"] += 1
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.error(f"❌ All execution phases failed after {elapsed:.1f}s")

        return ExecutionResult(
            success=False,
            order_id=None,
            filled_size=Decimal("0"),
            avg_fill_price=None,
            final_phase=ExecutionPhase.PHASE_3,
            total_time_seconds=elapsed,
            error_message="All execution phases failed"
        )

    async def _place_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal
    ) -> Dict:
        """Place limit order"""
        try:
            # Placeholder - replace with actual Polymarket CLOB client call
            response = await asyncio.to_thread(
                self.client.create_order,
                token_id=token_id,
                price=float(price),
                size=float(size),
                side=side
            )

            return {
                "success": True,
                "order_id": response.get("orderID", "test_order_123")
            }

        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _wait_for_fill(
        self,
        order_id: str,
        timeout_seconds: int
    ) -> Dict:
        """Wait for order to fill with polling"""
        end_time = datetime.now() + timedelta(seconds=timeout_seconds)
        poll_interval = 0.5  # 500ms

        while datetime.now() < end_time:
            try:
                # Check order status
                status = await asyncio.to_thread(
                    self.client.get_order,
                    order_id=order_id
                )

                if status.get("status") == "FILLED":
                    return {
                        "filled": True,
                        "filled_size": Decimal(str(status.get("filled_size", 0))),
                        "avg_price": Decimal(str(status.get("avg_price", 0)))
                    }

                # Check for partial fill (>80% filled is acceptable)
                filled_pct = status.get("filled_size", 0) / status.get("size", 1)
                if filled_pct >= 0.8:
                    logger.info(f"Accepting partial fill: {filled_pct * 100:.1f}%")
                    return {
                        "filled": True,
                        "filled_size": Decimal(str(status.get("filled_size", 0))),
                        "avg_price": Decimal(str(status.get("avg_price", 0)))
                    }

            except Exception as e:
                logger.error(f"Error checking order status: {e}")

            await asyncio.sleep(poll_interval)

        # Timeout
        return {"filled": False}

    async def _cancel_order(self, order_id: str):
        """Cancel unfilled order"""
        try:
            await asyncio.to_thread(
                self.client.cancel_order,
                order_id=order_id
            )
            logger.info(f"Cancelled order {order_id}")
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")

    def get_stats(self) -> Dict:
        """Get execution statistics"""
        total_fills = (
            self.stats["phase_1_fills"] +
            self.stats["phase_2_fills"] +
            self.stats["phase_3_fills"]
        )

        return {
            **self.stats,
            "total_fills": total_fills,
            "fill_rate": total_fills / self.stats["total_attempts"] if self.stats["total_attempts"] > 0 else 0,
            "phase_1_rate": self.stats["phase_1_fills"] / total_fills if total_fills > 0 else 0,
            "phase_2_rate": self.stats["phase_2_fills"] / total_fills if total_fills > 0 else 0,
            "phase_3_rate": self.stats["phase_3_fills"] / total_fills if total_fills > 0 else 0
        }


# Example usage
async def example_usage():
    """Example of using adaptive executor with proportional sizing"""
    from unittest.mock import Mock

    # Mock client
    mock_client = Mock()

    # Initialize components
    sizer = ProportionalSizer(copy_ratio=0.5, min_size=Decimal("10"), max_size=Decimal("1000"))
    executor = AdaptiveOrderExecutor(mock_client, enable_three_phase=True)

    # Example whale trade
    whale_trade_size = Decimal("500")
    whale_trade_price = Decimal("0.55")
    current_balance = Decimal("5000")

    # Calculate proportional size
    our_size = sizer.calculate_size(
        whale_trade_size=whale_trade_size,
        whale_trade_price=whale_trade_price,
        balance=current_balance,
        risk_multiplier=1.0  # Could be 0.5 if in REDUCE mode
    )

    logger.info(f"Whale traded {float(whale_trade_size)} @ ${float(whale_trade_price)}")
    logger.info(f"Our size: {float(our_size)} (50% of whale)")

    # Execute with three phases
    result = await executor.execute_with_phases(
        market_id="test_market",
        token_id="test_token",
        side="BUY",
        size=our_size,
        target_price=whale_trade_price
    )

    logger.info(f"Execution result: {result}")

    # Print stats
    stats = executor.get_stats()
    logger.info(f"Execution stats: {stats}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(example_usage())
