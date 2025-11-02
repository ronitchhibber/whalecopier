"""
Smart Order Router with TWAP
Week 7: Slippage & Execution Optimization - Smart Order Routing
Splits large orders into smaller chunks and executes over time to minimize market impact
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class ExecutionStrategy(Enum):
    """Order execution strategy"""
    IMMEDIATE = "IMMEDIATE"          # Execute entire order immediately
    TWAP = "TWAP"                    # Time-Weighted Average Price (split over time)
    VWAP = "VWAP"                    # Volume-Weighted Average Price
    ICEBERG = "ICEBERG"              # Show small portion, hide rest


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"              # Waiting to execute
    EXECUTING = "EXECUTING"          # Currently executing
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Some chunks filled
    FILLED = "FILLED"                # Completely filled
    CANCELLED = "CANCELLED"          # Cancelled by user
    FAILED = "FAILED"                # Execution failed


@dataclass
class OrderChunk:
    """Single chunk of a split order"""
    chunk_id: int
    parent_order_id: str
    market_id: str
    side: str
    size_usd: Decimal
    target_execution_time: datetime

    # Execution results
    status: OrderStatus = OrderStatus.PENDING
    executed_at: Optional[datetime] = None
    fill_price: Optional[Decimal] = None
    actual_size_filled: Optional[Decimal] = None
    slippage_pct: Optional[Decimal] = None
    transaction_hash: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class SplitOrderPlan:
    """Plan for splitting a large order"""
    order_id: str
    market_id: str
    side: str
    total_size_usd: Decimal
    strategy: ExecutionStrategy

    # Chunking parameters
    num_chunks: int
    chunk_size_usd: Decimal
    execution_interval_seconds: int
    total_execution_time_seconds: int

    # Chunks
    chunks: List[OrderChunk]

    # Timestamps
    start_time: datetime
    estimated_completion_time: datetime
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionResult:
    """Result of order execution"""
    order_id: str
    market_id: str
    side: str

    # Size metrics
    total_size_usd: Decimal
    filled_size_usd: Decimal
    fill_percentage: Decimal

    # Price metrics
    avg_fill_price: Decimal
    best_price_seen: Decimal
    worst_price_seen: Decimal

    # Slippage metrics
    total_slippage_usd: Decimal
    total_slippage_pct: Decimal
    avg_chunk_slippage_pct: Decimal

    # Execution metrics
    total_chunks: int
    filled_chunks: int
    failed_chunks: int
    cancelled_chunks: int

    # Timing metrics
    start_time: datetime
    end_time: datetime
    total_execution_time_seconds: Decimal

    # Status
    final_status: OrderStatus
    chunks: List[OrderChunk]


@dataclass
class TWAPConfig:
    """Configuration for TWAP execution"""
    # Chunking parameters
    max_chunk_size_usd: Decimal = Decimal("500")      # Max $500 per chunk
    min_chunks: int = 2                               # Min 2 chunks for TWAP
    max_chunks: int = 20                              # Max 20 chunks

    # Timing parameters
    min_interval_seconds: int = 30                    # Min 30s between chunks
    max_interval_seconds: int = 300                   # Max 5min between chunks
    default_execution_window_minutes: int = 10        # Default 10min window

    # Thresholds
    large_order_threshold: Decimal = Decimal("1000")  # $1,000+ uses TWAP
    immediate_threshold: Decimal = Decimal("500")     # <$500 execute immediately

    # Slippage targets
    target_slippage_pct: Decimal = Decimal("0.01")    # Target <1% slippage


# ==================== Smart Order Router ====================

class SmartOrderRouter:
    """
    Smart Order Router with TWAP

    Intelligently routes orders to minimize market impact:
    1. **Small orders (<$500):** Execute immediately
    2. **Medium orders ($500-$1000):** Split into 2-3 chunks
    3. **Large orders (>$1000):** Full TWAP with 5-20 chunks

    TWAP Algorithm:
    - Splits order into equal-sized chunks
    - Executes chunks at regular intervals
    - Monitors execution quality
    - Adapts to market conditions

    Example:
    $2,000 order → 4 chunks of $500 each, executed every 2 minutes
    Total execution time: 8 minutes
    Target: <1% total slippage
    """

    def __init__(
        self,
        config: Optional[TWAPConfig] = None,
        execute_order_callback: Optional[Callable] = None
    ):
        """
        Initialize smart order router

        Args:
            config: TWAP configuration
            execute_order_callback: Async callback function to execute single order
                                   Should accept (market_id, side, size_usd) and return fill_price
        """
        self.config = config or TWAPConfig()
        self.execute_order_callback = execute_order_callback or self._mock_execute_order

        # Active orders
        self.active_orders: Dict[str, SplitOrderPlan] = {}
        self.completed_orders: Dict[str, ExecutionResult] = {}

        # Statistics
        self.total_orders = 0
        self.total_twap_orders = 0
        self.total_immediate_orders = 0
        self.avg_slippage_pct = Decimal("0")

        logger.info(
            f"SmartOrderRouter initialized: "
            f"max_chunk=${float(self.config.max_chunk_size_usd):,.0f}, "
            f"large_order_threshold=${float(self.config.large_order_threshold):,.0f}"
        )

    async def execute_order(
        self,
        order_id: str,
        market_id: str,
        side: str,
        size_usd: Decimal,
        execution_window_minutes: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute order with smart routing

        Args:
            order_id: Unique order identifier
            market_id: Market to trade
            side: "buy" or "sell"
            size_usd: Order size in USD
            execution_window_minutes: Time window for execution (None = auto)

        Returns:
            ExecutionResult with execution details
        """
        self.total_orders += 1

        # Determine execution strategy
        if size_usd < self.config.immediate_threshold:
            # Small order: execute immediately
            logger.info(f"Order {order_id}: IMMEDIATE execution (${float(size_usd):,.2f} < ${float(self.config.immediate_threshold):,.0f})")
            return await self._execute_immediate(order_id, market_id, side, size_usd)

        elif size_usd >= self.config.large_order_threshold:
            # Large order: use TWAP
            logger.info(f"Order {order_id}: TWAP execution (${float(size_usd):,.2f} >= ${float(self.config.large_order_threshold):,.0f})")
            return await self._execute_twap(
                order_id, market_id, side, size_usd,
                execution_window_minutes or self.config.default_execution_window_minutes
            )

        else:
            # Medium order: small TWAP (2-3 chunks)
            logger.info(f"Order {order_id}: Small TWAP execution (${float(size_usd):,.2f})")
            return await self._execute_twap(
                order_id, market_id, side, size_usd,
                execution_window_minutes=5,  # 5 minute window for medium orders
                max_chunks=3
            )

    async def _execute_immediate(
        self,
        order_id: str,
        market_id: str,
        side: str,
        size_usd: Decimal
    ) -> ExecutionResult:
        """Execute order immediately (single chunk)"""
        self.total_immediate_orders += 1
        start_time = datetime.now()

        try:
            # Execute single order
            fill_price = await self.execute_order_callback(market_id, side, size_usd)

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Calculate slippage (simplified - would need best price from order book)
            best_price = fill_price * Decimal("0.999")  # Assume 0.1% spread
            slippage_pct = abs(fill_price - best_price) / best_price
            slippage_usd = abs(fill_price - best_price) * (size_usd / fill_price)

            # Create result
            chunk = OrderChunk(
                chunk_id=1,
                parent_order_id=order_id,
                market_id=market_id,
                side=side,
                size_usd=size_usd,
                target_execution_time=start_time,
                status=OrderStatus.FILLED,
                executed_at=end_time,
                fill_price=fill_price,
                actual_size_filled=size_usd,
                slippage_pct=slippage_pct
            )

            result = ExecutionResult(
                order_id=order_id,
                market_id=market_id,
                side=side,
                total_size_usd=size_usd,
                filled_size_usd=size_usd,
                fill_percentage=Decimal("1.0"),
                avg_fill_price=fill_price,
                best_price_seen=fill_price,
                worst_price_seen=fill_price,
                total_slippage_usd=slippage_usd,
                total_slippage_pct=slippage_pct,
                avg_chunk_slippage_pct=slippage_pct,
                total_chunks=1,
                filled_chunks=1,
                failed_chunks=0,
                cancelled_chunks=0,
                start_time=start_time,
                end_time=end_time,
                total_execution_time_seconds=Decimal(str(execution_time)),
                final_status=OrderStatus.FILLED,
                chunks=[chunk]
            )

            self.completed_orders[order_id] = result
            logger.info(
                f"Order {order_id} FILLED immediately: "
                f"${float(size_usd):,.2f} @ ${float(fill_price):.4f} | "
                f"Slippage: {float(slippage_pct)*100:.2f}%"
            )

            return result

        except Exception as e:
            end_time = datetime.now()
            logger.error(f"Order {order_id} FAILED: {str(e)}")

            return ExecutionResult(
                order_id=order_id,
                market_id=market_id,
                side=side,
                total_size_usd=size_usd,
                filled_size_usd=Decimal("0"),
                fill_percentage=Decimal("0"),
                avg_fill_price=Decimal("0"),
                best_price_seen=Decimal("0"),
                worst_price_seen=Decimal("0"),
                total_slippage_usd=Decimal("0"),
                total_slippage_pct=Decimal("0"),
                avg_chunk_slippage_pct=Decimal("0"),
                total_chunks=1,
                filled_chunks=0,
                failed_chunks=1,
                cancelled_chunks=0,
                start_time=start_time,
                end_time=end_time,
                total_execution_time_seconds=Decimal("0"),
                final_status=OrderStatus.FAILED,
                chunks=[]
            )

    async def _execute_twap(
        self,
        order_id: str,
        market_id: str,
        side: str,
        size_usd: Decimal,
        execution_window_minutes: int,
        max_chunks: Optional[int] = None
    ) -> ExecutionResult:
        """Execute order using TWAP strategy"""
        self.total_twap_orders += 1

        # Create split order plan
        plan = self._create_split_plan(
            order_id, market_id, side, size_usd,
            execution_window_minutes, max_chunks
        )

        self.active_orders[order_id] = plan

        logger.info(
            f"TWAP Plan created: {plan.num_chunks} chunks of ${float(plan.chunk_size_usd):,.2f} "
            f"every {plan.execution_interval_seconds}s (total {plan.total_execution_time_seconds}s)"
        )

        # Execute chunks
        start_time = datetime.now()
        filled_chunks = []
        failed_chunks = []
        total_filled_usd = Decimal("0")
        prices = []

        for i, chunk in enumerate(plan.chunks):
            # Wait for scheduled time (if not first chunk)
            if i > 0:
                wait_seconds = plan.execution_interval_seconds
                logger.debug(f"Waiting {wait_seconds}s before next chunk...")
                await asyncio.sleep(wait_seconds)

            try:
                # Execute chunk
                chunk.status = OrderStatus.EXECUTING
                fill_price = await self.execute_order_callback(
                    market_id, side, chunk.size_usd
                )

                # Update chunk
                chunk.status = OrderStatus.FILLED
                chunk.executed_at = datetime.now()
                chunk.fill_price = fill_price
                chunk.actual_size_filled = chunk.size_usd

                # Calculate chunk slippage
                best_price = fill_price * Decimal("0.999")  # Simplified
                chunk.slippage_pct = abs(fill_price - best_price) / best_price

                filled_chunks.append(chunk)
                total_filled_usd += chunk.size_usd
                prices.append(fill_price)

                logger.info(
                    f"Chunk {i+1}/{plan.num_chunks} FILLED: "
                    f"${float(chunk.size_usd):,.2f} @ ${float(fill_price):.4f}"
                )

            except Exception as e:
                chunk.status = OrderStatus.FAILED
                chunk.error_message = str(e)
                failed_chunks.append(chunk)
                logger.error(f"Chunk {i+1}/{plan.num_chunks} FAILED: {str(e)}")

        # Calculate results
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        if filled_chunks:
            avg_fill_price = sum(prices) / len(prices)
            best_price_seen = min(prices) if side == "buy" else max(prices)
            worst_price_seen = max(prices) if side == "buy" else min(prices)

            # Calculate total slippage
            if side == "buy":
                slippage_pct = (avg_fill_price - best_price_seen) / best_price_seen
            else:
                slippage_pct = (best_price_seen - avg_fill_price) / best_price_seen

            slippage_usd = abs(avg_fill_price - best_price_seen) * (total_filled_usd / avg_fill_price)

            avg_chunk_slippage = sum(c.slippage_pct for c in filled_chunks) / len(filled_chunks)
        else:
            avg_fill_price = Decimal("0")
            best_price_seen = Decimal("0")
            worst_price_seen = Decimal("0")
            slippage_pct = Decimal("0")
            slippage_usd = Decimal("0")
            avg_chunk_slippage = Decimal("0")

        # Determine final status
        if len(filled_chunks) == plan.num_chunks:
            final_status = OrderStatus.FILLED
        elif len(filled_chunks) > 0:
            final_status = OrderStatus.PARTIALLY_FILLED
        else:
            final_status = OrderStatus.FAILED

        result = ExecutionResult(
            order_id=order_id,
            market_id=market_id,
            side=side,
            total_size_usd=size_usd,
            filled_size_usd=total_filled_usd,
            fill_percentage=total_filled_usd / size_usd if size_usd > 0 else Decimal("0"),
            avg_fill_price=avg_fill_price,
            best_price_seen=best_price_seen,
            worst_price_seen=worst_price_seen,
            total_slippage_usd=slippage_usd,
            total_slippage_pct=slippage_pct,
            avg_chunk_slippage_pct=avg_chunk_slippage,
            total_chunks=plan.num_chunks,
            filled_chunks=len(filled_chunks),
            failed_chunks=len(failed_chunks),
            cancelled_chunks=0,
            start_time=start_time,
            end_time=end_time,
            total_execution_time_seconds=Decimal(str(execution_time)),
            final_status=final_status,
            chunks=plan.chunks
        )

        self.completed_orders[order_id] = result
        del self.active_orders[order_id]

        logger.info(
            f"TWAP Order {order_id} {final_status.value}: "
            f"{len(filled_chunks)}/{plan.num_chunks} chunks filled | "
            f"Avg price: ${float(avg_fill_price):.4f} | "
            f"Total slippage: {float(slippage_pct)*100:.2f}%"
        )

        return result

    def _create_split_plan(
        self,
        order_id: str,
        market_id: str,
        side: str,
        size_usd: Decimal,
        execution_window_minutes: int,
        max_chunks: Optional[int] = None
    ) -> SplitOrderPlan:
        """Create plan for splitting order"""
        # Calculate number of chunks
        ideal_chunks = int(size_usd / self.config.max_chunk_size_usd) + 1
        num_chunks = max(
            self.config.min_chunks,
            min(
                max_chunks or self.config.max_chunks,
                ideal_chunks
            )
        )

        # Calculate chunk size
        chunk_size_usd = size_usd / Decimal(str(num_chunks))

        # Calculate execution interval
        total_time_seconds = execution_window_minutes * 60
        execution_interval = max(
            self.config.min_interval_seconds,
            min(
                self.config.max_interval_seconds,
                int(total_time_seconds / num_chunks)
            )
        )

        # Create chunks
        start_time = datetime.now()
        chunks = []
        for i in range(num_chunks):
            target_time = start_time + timedelta(seconds=execution_interval * i)
            chunk = OrderChunk(
                chunk_id=i + 1,
                parent_order_id=order_id,
                market_id=market_id,
                side=side,
                size_usd=chunk_size_usd,
                target_execution_time=target_time
            )
            chunks.append(chunk)

        estimated_completion = start_time + timedelta(seconds=execution_interval * (num_chunks - 1))

        return SplitOrderPlan(
            order_id=order_id,
            market_id=market_id,
            side=side,
            total_size_usd=size_usd,
            strategy=ExecutionStrategy.TWAP,
            num_chunks=num_chunks,
            chunk_size_usd=chunk_size_usd,
            execution_interval_seconds=execution_interval,
            total_execution_time_seconds=execution_interval * (num_chunks - 1),
            chunks=chunks,
            start_time=start_time,
            estimated_completion_time=estimated_completion
        )

    async def _mock_execute_order(
        self,
        market_id: str,
        side: str,
        size_usd: Decimal
    ) -> Decimal:
        """Mock order execution for testing"""
        await asyncio.sleep(0.1)  # Simulate network latency

        # Simulate fill price with small random variation
        base_price = Decimal("0.50")
        variation = Decimal(str(0.001 * (hash(market_id) % 10)))
        fill_price = base_price + variation

        return fill_price

    def get_statistics(self) -> Dict:
        """Get router statistics"""
        if self.completed_orders:
            avg_slippage = sum(
                order.total_slippage_pct for order in self.completed_orders.values()
            ) / len(self.completed_orders)
        else:
            avg_slippage = Decimal("0")

        return {
            "total_orders": self.total_orders,
            "execution_methods": {
                "immediate": self.total_immediate_orders,
                "twap": self.total_twap_orders
            },
            "active_orders": len(self.active_orders),
            "completed_orders": len(self.completed_orders),
            "avg_slippage_pct": f"{float(avg_slippage)*100:.2f}%"
        }


# ==================== Example Usage ====================

async def main():
    """Example usage of SmartOrderRouter"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize router
    router = SmartOrderRouter()

    print("\n=== Smart Order Router with TWAP Test ===\n")

    # Test 1: Small order (immediate execution)
    print("=== Test 1: Small Order ($300) ===")
    result1 = await router.execute_order(
        order_id="order_001",
        market_id="test_market_1",
        side="buy",
        size_usd=Decimal("300")
    )
    print(f"Status: {result1.final_status.value}")
    print(f"Filled: ${float(result1.filled_size_usd):,.2f}")
    print(f"Avg Price: ${float(result1.avg_fill_price):.4f}")
    print(f"Slippage: {float(result1.total_slippage_pct)*100:.2f}%\n")

    # Test 2: Large order (TWAP execution)
    print("=== Test 2: Large Order ($2000) ===")
    result2 = await router.execute_order(
        order_id="order_002",
        market_id="test_market_2",
        side="buy",
        size_usd=Decimal("2000"),
        execution_window_minutes=2  # 2 minute window for demo
    )
    print(f"Status: {result2.final_status.value}")
    print(f"Chunks: {result2.filled_chunks}/{result2.total_chunks}")
    print(f"Filled: ${float(result2.filled_size_usd):,.2f}")
    print(f"Avg Price: ${float(result2.avg_fill_price):.4f}")
    print(f"Total Slippage: {float(result2.total_slippage_pct)*100:.2f}%")
    print(f"Execution Time: {float(result2.total_execution_time_seconds):.1f}s\n")

    # Get statistics
    print("=== Router Statistics ===")
    import json
    stats = router.get_statistics()
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
