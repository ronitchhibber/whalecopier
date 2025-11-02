"""
Order Execution Engine for Polymarket Copy Trading
Handles slippage estimation, order placement, and fill confirmation
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from src.api.polymarket_client import PolymarketClient
from src.config import settings

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

class OrderStatus(Enum):
    """Order status states"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


@dataclass
class OrderBook:
    """Order book representation"""
    token_id: str
    bids: List[Tuple[Decimal, Decimal]]  # [(price, size), ...]
    asks: List[Tuple[Decimal, Decimal]]  # [(price, size), ...]
    mid_price: Decimal
    spread: Decimal
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SlippageEstimate:
    """Slippage estimation result"""
    estimated_price: Decimal
    slippage_pct: Decimal
    depth_available: Decimal
    vwap: Decimal
    recommended: bool
    reason: Optional[str] = None


@dataclass
class OrderResult:
    """Order execution result"""
    success: bool
    order_id: Optional[str]
    status: OrderStatus
    size: Decimal
    filled_size: Decimal
    avg_fill_price: Optional[Decimal]
    error: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class FillStatus:
    """Order fill status"""
    order_id: str
    status: OrderStatus
    filled_size: Decimal
    remaining_size: Decimal
    avg_fill_price: Decimal
    fills: List[Dict]
    timestamp: datetime = field(default_factory=datetime.now)


# ==================== Slippage Estimator ====================

class SlippageEstimator:
    """
    Estimate execution slippage from order book depth
    Target: Reject orders with >2% slippage (limit) or >5% (market)
    """

    def __init__(self, client: PolymarketClient):
        self.client = client
        self.max_slippage_limit = Decimal("0.02")  # 2%
        self.max_slippage_market = Decimal("0.05")  # 5%

    async def fetch_order_book(self, token_id: str) -> OrderBook:
        """Fetch order book from Polymarket CLOB API"""
        try:
            raw_book = self.client.get_orderbook(token_id)

            # Parse bids and asks
            bids = [
                (Decimal(str(order['price'])), Decimal(str(order['size'])))
                for order in raw_book.get('bids', [])
            ]
            asks = [
                (Decimal(str(order['price'])), Decimal(str(order['size'])))
                for order in raw_book.get('asks', [])
            ]

            # Calculate mid price
            best_bid = bids[0][0] if bids else Decimal(0)
            best_ask = asks[0][0] if asks else Decimal(1)
            mid_price = (best_bid + best_ask) / Decimal(2)

            # Calculate spread
            spread = best_ask - best_bid if (bids and asks) else Decimal(0)

            return OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                mid_price=mid_price,
                spread=spread
            )

        except Exception as e:
            logger.error(f"Failed to fetch order book for {token_id}: {e}")
            raise

    async def estimate_slippage(
        self,
        size: Decimal,
        side: str,
        order_book: OrderBook
    ) -> SlippageEstimate:
        """
        Estimate execution slippage for an order

        Args:
            size: Order size in shares
            side: 'BUY' or 'SELL'
            order_book: Current order book state

        Returns:
            SlippageEstimate with recommended action
        """
        try:
            # Select appropriate side of book
            orders = order_book.asks if side == "BUY" else order_book.bids

            if not orders:
                return SlippageEstimate(
                    estimated_price=Decimal(0),
                    slippage_pct=Decimal(1),  # 100%
                    depth_available=Decimal(0),
                    vwap=Decimal(0),
                    recommended=False,
                    reason="No liquidity available"
                )

            # Walk through order book to calculate VWAP
            remaining_size = size
            total_cost = Decimal(0)
            filled_size = Decimal(0)

            for price, available_size in orders:
                if remaining_size <= 0:
                    break

                fill_size = min(remaining_size, available_size)
                total_cost += price * fill_size
                filled_size += fill_size
                remaining_size -= fill_size

            if filled_size == 0:
                return SlippageEstimate(
                    estimated_price=Decimal(0),
                    slippage_pct=Decimal(1),
                    depth_available=Decimal(0),
                    vwap=Decimal(0),
                    recommended=False,
                    reason="No depth available"
                )

            # Calculate VWAP
            vwap = total_cost / filled_size

            # Calculate slippage vs mid-price
            if order_book.mid_price > 0:
                slippage_pct = abs(vwap - order_book.mid_price) / order_book.mid_price
            else:
                slippage_pct = Decimal(0)

            # Check if we can fill complete order
            if filled_size < size:
                return SlippageEstimate(
                    estimated_price=vwap,
                    slippage_pct=slippage_pct,
                    depth_available=filled_size,
                    vwap=vwap,
                    recommended=False,
                    reason=f"Insufficient depth: only {filled_size}/{size} available"
                )

            # Check slippage threshold
            recommended = slippage_pct <= self.max_slippage_limit

            return SlippageEstimate(
                estimated_price=vwap,
                slippage_pct=slippage_pct,
                depth_available=filled_size,
                vwap=vwap,
                recommended=recommended,
                reason=f"Slippage {slippage_pct*100:.2f}%" if recommended else f"Slippage too high: {slippage_pct*100:.2f}% > {self.max_slippage_limit*100:.1f}%"
            )

        except Exception as e:
            logger.error(f"Failed to estimate slippage: {e}")
            return SlippageEstimate(
                estimated_price=Decimal(0),
                slippage_pct=Decimal(1),
                depth_available=Decimal(0),
                vwap=Decimal(0),
                recommended=False,
                reason=f"Error: {str(e)}"
            )


# ==================== Order Placer ====================

class OrderPlacer:
    """
    Place orders via Polymarket CLOB API with retry logic
    Target: <2s submission time, >95% success rate
    """

    def __init__(self, client: PolymarketClient):
        self.client = client
        self.max_retries = 3
        self.initial_retry_delay = 1  # seconds

    async def place_limit_order(
        self,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal
    ) -> OrderResult:
        """
        Place a limit order with retry logic

        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            size: Order size in shares
            price: Limit price (0-1 for binary markets)

        Returns:
            OrderResult with execution details
        """
        start_time = datetime.now()

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Placing limit order (attempt {attempt + 1}): {side} {size} @ {price}")

                # Place order via client
                response = self.client.place_limit_order(
                    token_id=token_id,
                    price=float(price),
                    size=float(size),
                    side=side
                )

                # Calculate execution time
                execution_time = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(f"✓ Order placed successfully: {response.get('orderID')}")

                return OrderResult(
                    success=True,
                    order_id=response.get('orderID'),
                    status=OrderStatus.SUBMITTED,
                    size=size,
                    filled_size=Decimal(0),
                    avg_fill_price=None,
                    execution_time_ms=int(execution_time)
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ Order placement failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}")

                # Check if we should retry
                if attempt < self.max_retries - 1:
                    # Don't retry on these errors
                    non_retryable_errors = [
                        "insufficient balance",
                        "invalid market",
                        "market closed",
                        "invalid price"
                    ]
                    if any(err in error_msg.lower() for err in non_retryable_errors):
                        logger.error(f"Non-retryable error, aborting: {error_msg}")
                        break

                    # Exponential backoff
                    retry_delay = self.initial_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    continue

        # All retries failed
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        return OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.FAILED,
            size=size,
            filled_size=Decimal(0),
            avg_fill_price=None,
            error=error_msg,
            execution_time_ms=int(execution_time)
        )

    async def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: Decimal,
        order_type: str = "FOK"
    ) -> OrderResult:
        """
        Place a market order with retry logic

        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Dollar amount to spend/receive
            order_type: 'FOK' (Fill-or-Kill) or 'GTC' (Good-til-Cancelled)

        Returns:
            OrderResult with execution details
        """
        start_time = datetime.now()

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Placing market order (attempt {attempt + 1}): {side} ${amount} ({order_type})")

                # Place order via client
                response = self.client.place_market_order(
                    token_id=token_id,
                    amount=float(amount),
                    side=side,
                    order_type=order_type
                )

                # Calculate execution time
                execution_time = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(f"✓ Market order placed successfully: {response.get('orderID')}")

                return OrderResult(
                    success=True,
                    order_id=response.get('orderID'),
                    status=OrderStatus.SUBMITTED,
                    size=Decimal(0),  # Will be updated by fill confirmer
                    filled_size=Decimal(0),
                    avg_fill_price=None,
                    execution_time_ms=int(execution_time)
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ Market order failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}")

                if attempt < self.max_retries - 1:
                    retry_delay = self.initial_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    continue

        # All retries failed
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        return OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.FAILED,
            size=Decimal(0),
            filled_size=Decimal(0),
            avg_fill_price=None,
            error=error_msg,
            execution_time_ms=int(execution_time)
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order"""
        try:
            response = self.client.cancel_order(order_id)
            logger.info(f"✓ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to cancel order {order_id}: {e}")
            return False


# ==================== Fill Confirmer ====================

class FillConfirmer:
    """
    Monitor order fill status and handle partial fills
    Target: Detect fills within 500ms
    """

    def __init__(self, client: PolymarketClient):
        self.client = client
        self.poll_interval = 0.5  # 500ms
        self.default_timeout = 30  # 30 seconds

    async def wait_for_fill(
        self,
        order_id: str,
        timeout: int = None
    ) -> FillStatus:
        """
        Wait for order to fill with polling

        Args:
            order_id: Order ID to monitor
            timeout: Max wait time in seconds (default: 30s)

        Returns:
            FillStatus with final state
        """
        timeout = timeout or self.default_timeout
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=timeout)

        logger.info(f"Monitoring order {order_id[:12]}... (timeout: {timeout}s)")

        while datetime.now() < end_time:
            try:
                # Get current fill status
                fill_status = await self.get_fill_status(order_id)

                # Check if filled
                if fill_status.status == OrderStatus.FILLED:
                    logger.info(f"✓ Order {order_id[:12]}... FILLED: {fill_status.filled_size} @ {fill_status.avg_fill_price}")
                    return fill_status

                # Check if partially filled (>80% = accept)
                if fill_status.status == OrderStatus.PARTIALLY_FILLED:
                    fill_pct = (fill_status.filled_size / (fill_status.filled_size + fill_status.remaining_size)) * 100

                    if fill_pct >= 80:
                        logger.info(f"⚠ Order {order_id[:12]}... PARTIALLY FILLED: {fill_pct:.1f}% - accepting")
                        return fill_status
                    else:
                        logger.debug(f"Order {order_id[:12]}... partially filled: {fill_pct:.1f}%")

                # Check if cancelled or failed
                if fill_status.status in [OrderStatus.CANCELLED, OrderStatus.FAILED]:
                    logger.warning(f"✗ Order {order_id[:12]}... {fill_status.status.value}")
                    return fill_status

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error checking fill status for {order_id}: {e}")
                await asyncio.sleep(self.poll_interval)

        # Timeout reached
        logger.warning(f"⏱ Order {order_id[:12]}... TIMEOUT after {timeout}s")

        return FillStatus(
            order_id=order_id,
            status=OrderStatus.TIMEOUT,
            filled_size=Decimal(0),
            remaining_size=Decimal(0),
            avg_fill_price=Decimal(0),
            fills=[]
        )

    async def get_fill_status(self, order_id: str) -> FillStatus:
        """
        Get current fill status for an order

        Args:
            order_id: Order ID to check

        Returns:
            FillStatus with current state
        """
        try:
            # Get open orders
            open_orders = self.client.get_orders()

            # Find our order
            order = next((o for o in open_orders if o.get('id') == order_id), None)

            if not order:
                # Order not in open orders - might be fully filled or cancelled
                # TODO: Check order history API when available
                return FillStatus(
                    order_id=order_id,
                    status=OrderStatus.FILLED,  # Assume filled if not in open orders
                    filled_size=Decimal(0),  # Unknown
                    remaining_size=Decimal(0),
                    avg_fill_price=Decimal(0),
                    fills=[]
                )

            # Parse order status
            original_size = Decimal(str(order.get('size', 0)))
            filled_size = Decimal(str(order.get('sizeFilled', 0)))
            remaining_size = original_size - filled_size

            # Determine status
            if remaining_size == 0:
                status = OrderStatus.FILLED
            elif filled_size > 0:
                status = OrderStatus.PARTIALLY_FILLED
            else:
                status = OrderStatus.SUBMITTED

            # Calculate average fill price
            if filled_size > 0:
                # TODO: Parse fills from order details when available
                avg_price = Decimal(str(order.get('price', 0)))
            else:
                avg_price = Decimal(0)

            return FillStatus(
                order_id=order_id,
                status=status,
                filled_size=filled_size,
                remaining_size=remaining_size,
                avg_fill_price=avg_price,
                fills=order.get('fills', [])
            )

        except Exception as e:
            logger.error(f"Failed to get fill status for {order_id}: {e}")
            return FillStatus(
                order_id=order_id,
                status=OrderStatus.FAILED,
                filled_size=Decimal(0),
                remaining_size=Decimal(0),
                avg_fill_price=Decimal(0),
                fills=[],
            )


# ==================== Main Order Executor ====================

class OrderExecutor:
    """
    Main order execution coordinator
    Combines slippage estimation, order placement, and fill confirmation
    """

    def __init__(self, client: Optional[PolymarketClient] = None):
        """
        Initialize order executor

        Args:
            client: PolymarketClient instance (creates new one if None)
        """
        self.client = client or PolymarketClient()
        self.slippage_estimator = SlippageEstimator(self.client)
        self.order_placer = OrderPlacer(self.client)
        self.fill_confirmer = FillConfirmer(self.client)

    async def execute_trade(
        self,
        token_id: str,
        side: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        check_slippage: bool = True,
        wait_for_fill: bool = True,
        fill_timeout: int = 30
    ) -> OrderResult:
        """
        Execute a complete trade with slippage check and fill confirmation

        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            size: Order size in shares
            price: Limit price (None for market order)
            check_slippage: Whether to check slippage before placing order
            wait_for_fill: Whether to wait for fill confirmation
            fill_timeout: Max wait time for fill (seconds)

        Returns:
            OrderResult with complete execution details
        """
        start_time = datetime.now()

        try:
            # Step 1: Slippage check (if requested)
            if check_slippage:
                logger.info(f"Checking slippage for {side} {size} {token_id[:12]}...")

                order_book = await self.slippage_estimator.fetch_order_book(token_id)
                slippage = await self.slippage_estimator.estimate_slippage(
                    size=size,
                    side=side,
                    order_book=order_book
                )

                if not slippage.recommended:
                    logger.warning(f"✗ Trade rejected: {slippage.reason}")
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.FAILED,
                        size=size,
                        filled_size=Decimal(0),
                        avg_fill_price=None,
                        error=f"Slippage too high: {slippage.reason}"
                    )

                logger.info(f"✓ Slippage OK: {slippage.slippage_pct*100:.2f}% (VWAP: {slippage.vwap:.4f})")

            # Step 2: Place order
            if price is not None:
                # Limit order
                result = await self.order_placer.place_limit_order(
                    token_id=token_id,
                    side=side,
                    size=size,
                    price=price
                )
            else:
                # Market order
                amount = size * Decimal("0.5")  # Estimate amount (will be refined)
                result = await self.order_placer.place_market_order(
                    token_id=token_id,
                    side=side,
                    amount=amount
                )

            if not result.success:
                logger.error(f"✗ Order placement failed: {result.error}")
                return result

            # Step 3: Wait for fill (if requested)
            if wait_for_fill and result.order_id:
                logger.info(f"Waiting for fill: {result.order_id[:12]}...")

                fill_status = await self.fill_confirmer.wait_for_fill(
                    order_id=result.order_id,
                    timeout=fill_timeout
                )

                # Update result with fill details
                result.status = fill_status.status
                result.filled_size = fill_status.filled_size
                result.avg_fill_price = fill_status.avg_fill_price

                # Update success based on fill
                if fill_status.status == OrderStatus.FILLED:
                    result.success = True
                elif fill_status.status == OrderStatus.PARTIALLY_FILLED:
                    fill_pct = (fill_status.filled_size / size) * 100
                    result.success = fill_pct >= 80  # Accept if >80% filled
                else:
                    result.success = False

            # Calculate total execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            result.execution_time_ms = int(execution_time)

            return result

        except Exception as e:
            logger.error(f"✗ Trade execution failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return OrderResult(
                success=False,
                order_id=None,
                status=OrderStatus.FAILED,
                size=size,
                filled_size=Decimal(0),
                avg_fill_price=None,
                error=str(e),
                execution_time_ms=int(execution_time)
            )


# ==================== Example Usage ====================

async def main():
    """Example usage of OrderExecutor"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize executor
    executor = OrderExecutor()

    # Example: Execute a limit order with slippage check
    result = await executor.execute_trade(
        token_id="21742633143463906290569050155826241533067272736897614950488156847949938836455",
        side="BUY",
        size=Decimal("100"),
        price=Decimal("0.55"),
        check_slippage=True,
        wait_for_fill=True
    )

    print(f"\nExecution Result:")
    print(f"  Success: {result.success}")
    print(f"  Order ID: {result.order_id}")
    print(f"  Status: {result.status.value}")
    print(f"  Filled: {result.filled_size}/{result.size}")
    print(f"  Avg Price: {result.avg_fill_price}")
    print(f"  Execution Time: {result.execution_time_ms}ms")
    if result.error:
        print(f"  Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
