"""
Batch Order Placement for Polymarket Copy Trading
Efficiently place multiple orders concurrently with deduplication
Week 3: Order Execution Engine - Batch Orders
"""

import asyncio
import logging
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from src.trading.order_state_machine import OrderStateMachine, OrderState, ManagedOrder
from src.trading.order_executor import OrderExecutor, OrderResult
from src.api.polymarket_client import PolymarketClient

logger = logging.getLogger(__name__)


@dataclass
class BatchOrderRequest:
    """Single order request in a batch"""
    token_id: str
    side: str
    size: Decimal
    price: Optional[Decimal] = None
    check_slippage: bool = True


@dataclass
class BatchOrderResult:
    """Result of batch order placement"""
    total_orders: int
    successful: int
    failed: int
    results: List[OrderResult]
    execution_time_seconds: float
    errors: List[str]


class BatchOrderPlacer:
    """
    Place multiple orders concurrently with idempotency
    Target: >100 orders/minute throughput
    """

    def __init__(
        self,
        client: Optional[PolymarketClient] = None,
        state_machine: Optional[OrderStateMachine] = None,
        max_concurrent: int = 10
    ):
        """
        Initialize batch order placer

        Args:
            client: Polymarket CLOB client
            state_machine: Order state machine for tracking
            max_concurrent: Max concurrent API requests
        """
        self.client = client or PolymarketClient()
        self.state_machine = state_machine
        self.max_concurrent = max_concurrent
        self.executor = OrderExecutor(self.client)

        # Semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def place_batch(
        self,
        orders: List[BatchOrderRequest],
        wait_for_fills: bool = False,
        fill_timeout: int = 30
    ) -> BatchOrderResult:
        """
        Place multiple orders concurrently

        Args:
            orders: List of order requests
            wait_for_fills: Whether to wait for all fills
            fill_timeout: Timeout for fills (seconds)

        Returns:
            BatchOrderResult with aggregate statistics
        """
        start_time = datetime.now()

        logger.info(f"Placing batch of {len(orders)} orders...")

        # Create tasks for concurrent execution
        tasks = [
            self._place_single_with_limit(
                order,
                wait_for_fill=wait_for_fills,
                fill_timeout=fill_timeout
            )
            for order in orders
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful = 0
        failed = 0
        errors = []
        valid_results = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Exception occurred
                failed += 1
                errors.append(f"Order {i}: {str(result)}")
                logger.error(f"Order {i} failed with exception: {result}")
            elif isinstance(result, OrderResult):
                valid_results.append(result)
                if result.success:
                    successful += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(f"Order {i}: {result.error}")
            else:
                failed += 1
                errors.append(f"Order {i}: Unknown result type")

        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()

        # Log summary
        logger.info(
            f"Batch complete: {successful}/{len(orders)} successful "
            f"({execution_time:.2f}s, {len(orders)/execution_time:.1f} orders/s)"
        )

        return BatchOrderResult(
            total_orders=len(orders),
            successful=successful,
            failed=failed,
            results=valid_results,
            execution_time_seconds=execution_time,
            errors=errors
        )

    async def _place_single_with_limit(
        self,
        order_request: BatchOrderRequest,
        wait_for_fill: bool = False,
        fill_timeout: int = 30
    ) -> OrderResult:
        """
        Place a single order with rate limiting

        Args:
            order_request: Order to place
            wait_for_fill: Whether to wait for fill
            fill_timeout: Fill timeout in seconds

        Returns:
            OrderResult
        """
        async with self.semaphore:
            # Create managed order if state machine available
            if self.state_machine:
                managed_order = await self.state_machine.create_order(
                    token_id=order_request.token_id,
                    side=order_request.side,
                    size=order_request.size,
                    price=order_request.price
                )

                # Transition to SUBMITTED state before placing
                await self.state_machine.transition(
                    managed_order.order_id,
                    OrderState.SUBMITTED,
                    reason="Batch order placement"
                )

            # Execute trade
            result = await self.executor.execute_trade(
                token_id=order_request.token_id,
                side=order_request.side,
                size=order_request.size,
                price=order_request.price,
                check_slippage=order_request.check_slippage,
                wait_for_fill=wait_for_fill,
                fill_timeout=fill_timeout
            )

            # Update state machine if available
            if self.state_machine and result.order_id:
                if result.success and result.filled_size > 0:
                    await self.state_machine.update_fill(
                        managed_order.order_id,
                        result.filled_size,
                        result.avg_fill_price or Decimal(0)
                    )
                elif not result.success:
                    await self.state_machine.record_error(
                        managed_order.order_id,
                        result.error or "Unknown error"
                    )

            return result

    async def place_batch_market_orders(
        self,
        orders: List[Dict[str, any]],
        order_type: str = "FOK"
    ) -> BatchOrderResult:
        """
        Place multiple market orders concurrently

        Args:
            orders: List of dicts with token_id, side, amount
            order_type: FOK or GTC

        Returns:
            BatchOrderResult
        """
        # Convert to batch requests
        batch_requests = [
            BatchOrderRequest(
                token_id=order["token_id"],
                side=order["side"],
                size=Decimal(str(order["amount"])),  # Market orders use amount
                price=None,  # No price for market orders
                check_slippage=order.get("check_slippage", True)
            )
            for order in orders
        ]

        return await self.place_batch(
            batch_requests,
            wait_for_fills=True,  # Market orders should fill quickly
            fill_timeout=10  # Shorter timeout for market orders
        )

    async def cancel_batch(self, order_ids: List[str]) -> Dict[str, bool]:
        """
        Cancel multiple orders concurrently

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Dict mapping order_id to success (True/False)
        """
        logger.info(f"Cancelling batch of {len(order_ids)} orders...")

        # Create cancel tasks
        tasks = [
            self._cancel_single_with_limit(order_id)
            for order_id in order_ids
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result map
        result_map = {}
        for order_id, result in zip(order_ids, results):
            if isinstance(result, Exception):
                result_map[order_id] = False
                logger.error(f"Failed to cancel {order_id}: {result}")
            else:
                result_map[order_id] = result

        successful = sum(1 for v in result_map.values() if v)
        logger.info(f"Batch cancel complete: {successful}/{len(order_ids)} successful")

        return result_map

    async def _cancel_single_with_limit(self, order_id: str) -> bool:
        """Cancel single order with rate limiting"""
        async with self.semaphore:
            # Update state machine
            if self.state_machine:
                await self.state_machine.transition(
                    order_id,
                    OrderState.CANCELLING,
                    reason="Batch cancel"
                )

            # Cancel via executor
            success = await self.executor.order_placer.cancel_order(order_id)

            # Update state machine
            if self.state_machine:
                if success:
                    await self.state_machine.transition(
                        order_id,
                        OrderState.CANCELLED,
                        reason="Cancelled successfully"
                    )
                else:
                    await self.state_machine.transition(
                        order_id,
                        OrderState.FAILED,
                        reason="Cancel failed"
                    )

            return success


# ==================== Example Usage ====================

async def main():
    """Example usage of BatchOrderPlacer"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize batch placer
    batch_placer = BatchOrderPlacer(max_concurrent=5)

    # Example: Place batch of limit orders
    orders = [
        BatchOrderRequest(
            token_id=f"token_{i}",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )
        for i in range(10)
    ]

    result = await batch_placer.place_batch(orders, wait_for_fills=False)

    print(f"\nBatch Order Result:")
    print(f"  Total: {result.total_orders}")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")
    print(f"  Execution Time: {result.execution_time_seconds:.2f}s")
    print(f"  Throughput: {result.total_orders/result.execution_time_seconds:.1f} orders/s")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors[:5]:  # Show first 5 errors
            print(f"  - {error}")


if __name__ == "__main__":
    asyncio.run(main())
