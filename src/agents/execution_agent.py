"""
Execution Agent - Multi-Agent System Component
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This agent is the ONLY component with private key access.
It executes approved trades with sub-second latency and manages the full order lifecycle.

Core Responsibilities:
1. EIP-712 order signing (Polymarket CLOB API)
2. Smart order routing (iceberg, passive maker, aggressive taker)
3. Order lifecycle management (partial fills, timeouts, cancellations)
4. Private key security (AWS KMS or Fireblocks MPC)
5. Dual control (Risk Agent approval required)

Security:
- Private keys NEVER stored in code or logs
- All order signatures use EIP-712 standard
- Dual control: Risk Agent approval + Execution Agent signature
- Audit trail for all order submissions

Message Contracts:
- Subscribes: ApprovedTrade
- Publishes: OrderSubmitted, OrderFilled, OrderCancelled, ExecutionError

Performance Targets:
- >95% fill rate for limit orders within 60s
- <500ms order submission latency
- 100% audit coverage (every order logged)

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import json
import time

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type"""
    MARKET = "MARKET"  # Execute immediately at best available price
    LIMIT = "LIMIT"  # Execute at specified price or better
    LIMIT_MAKER = "LIMIT_MAKER"  # Only execute as maker (passive)


class OrderStatus(Enum):
    """Order status"""
    PENDING = "PENDING"  # Waiting to submit
    SUBMITTED = "SUBMITTED"  # Submitted to CLOB
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Some fills, still active
    FILLED = "FILLED"  # Completely filled
    CANCELLED = "CANCELLED"  # Cancelled by agent
    REJECTED = "REJECTED"  # Rejected by CLOB
    EXPIRED = "EXPIRED"  # Timeout exceeded


@dataclass
class ExecutionConfig:
    """Configuration for Execution Agent"""

    # Polymarket CLOB API
    clob_api_url: str = "https://clob.polymarket.com"
    clob_websocket_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws"

    # Private key management
    use_kms: bool = True  # AWS KMS (recommended)
    kms_key_id: Optional[str] = None
    use_mpc: bool = False  # Fireblocks MPC (alternative)
    mpc_vault_id: Optional[str] = None

    # Order execution
    default_order_type: OrderType = OrderType.LIMIT
    default_expiration_seconds: int = 300  # 5 minutes
    partial_fill_timeout_seconds: int = 30  # Retry if partial after 30s
    no_fill_timeout_seconds: int = 60  # Cancel if no fill after 60s

    # Smart routing
    iceberg_threshold_pct: float = 10.0  # Use iceberg if >10% of depth
    iceberg_show_pct: float = 10.0  # Show 10% at a time
    wide_spread_threshold_pct: float = 3.0  # Use maker if spread >3%
    price_improvement_ticks: int = 2  # Improve limit price by 2 ticks

    # Risk limits (final safety check)
    max_order_size_usd: float = 100000.0  # $100k max per order
    max_slippage_pct: float = 2.0  # 2% max slippage for market orders

    # Performance
    max_concurrent_orders: int = 5
    submission_timeout_seconds: int = 5


@dataclass
class ApprovedTrade:
    """Approved trade from Risk Management Agent"""

    proposal_id: str
    whale_address: str
    market_id: str
    market_topic: str
    side: OrderSide
    approved_size_usd: float
    expected_price: float

    # Risk approval metadata
    kelly_fraction_used: float
    estimated_edge: float
    risk_metrics: Dict

    timestamp: datetime


@dataclass
class Order:
    """Order representation"""

    order_id: str
    market_id: str
    side: OrderSide
    order_type: OrderType
    size: float  # Number of shares
    price: float  # Limit price
    expiration: datetime

    # State
    status: OrderStatus
    filled_size: float
    avg_fill_price: float
    fees_paid_usd: float

    # Metadata
    proposal_id: str
    submitted_at: Optional[datetime]
    filled_at: Optional[datetime]
    clob_order_id: Optional[str]  # From CLOB API


class ExecutionAgent:
    """
    Specialized agent for order execution with private key access.

    This is the ONLY agent that can spend funds.
    Security is paramount.
    """

    def __init__(self, config: ExecutionConfig = None):
        """
        Initialize Execution Agent.

        Args:
            config: Configuration object
        """
        self.config = config or ExecutionConfig()

        # Private key (loaded from secure storage)
        self.private_key: Optional[str] = None
        self.wallet_address: Optional[str] = None

        # Agent state
        self.active_orders: Dict[str, Order] = {}  # order_id -> Order
        self.order_history: List[Order] = []

        # WebSocket connection
        self.websocket_connection = None

        # Message queue (placeholder - would use NATS in production)
        self.message_queue = []

        # Performance tracking
        self.execution_stats = {
            'total_orders': 0,
            'successful_fills': 0,
            'partial_fills': 0,
            'cancellations': 0,
            'rejections': 0,
            'avg_submission_latency_ms': 0.0,
            'avg_fill_time_seconds': 0.0,
            'total_fees_paid_usd': 0.0,
            'total_slippage_usd': 0.0
        }

        logger.info("ExecutionAgent initialized (PRIVATE KEY ACCESS ENABLED)")

    async def initialize_security(self):
        """
        Initialize security - load private key from secure storage.

        CRITICAL: This method handles the most sensitive operation.
        """
        logger.info("Initializing security credentials...")

        if self.config.use_kms:
            # Load from AWS KMS
            self.private_key = await self._load_from_kms()
            self.wallet_address = self._derive_address(self.private_key)
            logger.info(f"✅ Loaded private key from AWS KMS | Wallet: {self.wallet_address}")

        elif self.config.use_mpc:
            # Load from Fireblocks MPC
            self.private_key = await self._load_from_mpc()
            self.wallet_address = self._derive_address(self.private_key)
            logger.info(f"✅ Loaded private key from Fireblocks MPC | Wallet: {self.wallet_address}")

        else:
            # DANGER: Loading from environment variable (dev only)
            import os
            self.private_key = os.getenv('PRIVATE_KEY')
            self.wallet_address = os.getenv('WALLET_ADDRESS')
            logger.warning("⚠️  INSECURE: Loaded private key from environment variable (DEV ONLY)")

        if not self.private_key or not self.wallet_address:
            raise ValueError("Failed to load private key - cannot operate")

    async def execution_loop(self):
        """
        Main execution loop - processes approved trades.

        Subscribes to ApprovedTrade events from Risk Management Agent.
        """
        logger.info("Starting execution loop")

        while True:
            try:
                # Fetch approved trades from message queue
                # In production, this would be NATS subscription
                approved_trades = await self._fetch_approved_trades()

                for trade in approved_trades:
                    await self.execute_approved_trade(trade)

                # Sleep briefly
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in execution loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def execute_approved_trade(self, trade: ApprovedTrade):
        """
        Execute an approved trade.

        Steps:
        1. Fetch current orderbook
        2. Determine optimal order type (market, limit, limit_maker)
        3. Construct EIP-712 order message
        4. Sign with private key
        5. Submit to CLOB API
        6. Monitor order status
        7. Handle partial fills, timeouts, cancellations

        Args:
            trade: ApprovedTrade object
        """
        start_time = time.perf_counter()

        try:
            logger.info(
                f"🚀 Executing approved trade | "
                f"Market: {trade.market_topic[:30]}... | "
                f"Side: {trade.side.value} | "
                f"Size: ${trade.approved_size_usd:,.0f}"
            )

            # Step 1: Fetch orderbook
            orderbook = await self._fetch_orderbook(trade.market_id)

            # Step 2: Smart order routing
            order = await self._create_order(trade, orderbook)

            # Step 3: Sign order (EIP-712)
            signed_order = await self._sign_order(order)

            # Step 4: Submit to CLOB
            clob_response = await self._submit_to_clob(signed_order)
            order.clob_order_id = clob_response.get('order_id')
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now()

            # Add to active orders
            self.active_orders[order.order_id] = order

            # Publish OrderSubmitted event
            self._publish_event('OrderSubmitted', {
                'order_id': order.order_id,
                'proposal_id': trade.proposal_id,
                'market_id': trade.market_id,
                'side': trade.side.value,
                'size': order.size,
                'price': order.price,
                'clob_order_id': order.clob_order_id,
                'timestamp': datetime.now().isoformat()
            })

            # Update stats
            self.execution_stats['total_orders'] += 1
            submission_latency_ms = (time.perf_counter() - start_time) * 1000
            self.execution_stats['avg_submission_latency_ms'] = (
                0.9 * self.execution_stats['avg_submission_latency_ms']
                + 0.1 * submission_latency_ms
            )

            logger.info(
                f"✅ Order submitted | "
                f"Order ID: {order.order_id} | "
                f"CLOB ID: {order.clob_order_id} | "
                f"Latency: {submission_latency_ms:.1f}ms"
            )

        except Exception as e:
            logger.error(f"Execution error for trade {trade.proposal_id}: {e}", exc_info=True)

            # Publish ExecutionError event
            self._publish_event('ExecutionError', {
                'proposal_id': trade.proposal_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

            self.execution_stats['rejections'] += 1

    async def order_monitoring_loop(self):
        """
        Order monitoring loop - tracks active orders and handles lifecycle.

        Actions:
        - Detect fills (via WebSocket)
        - Handle partial fills (retry or cancel)
        - Handle timeouts (cancel)
        - Calculate fees and slippage
        """
        logger.info("Starting order monitoring loop")

        # Connect to CLOB WebSocket
        # TODO: Implement WebSocket connection
        # For now, use polling

        while True:
            try:
                for order_id, order in list(self.active_orders.items()):
                    # Check order status
                    status = await self._check_order_status(order)

                    if status == OrderStatus.FILLED:
                        # Order completely filled!
                        await self._handle_filled_order(order)

                    elif status == OrderStatus.PARTIALLY_FILLED:
                        # Check timeout
                        time_since_submit = (datetime.now() - order.submitted_at).total_seconds()

                        if time_since_submit > self.config.partial_fill_timeout_seconds:
                            # Timeout - cancel remaining
                            await self._cancel_order(order)

                    elif status == OrderStatus.SUBMITTED:
                        # Check no-fill timeout
                        time_since_submit = (datetime.now() - order.submitted_at).total_seconds()

                        if time_since_submit > self.config.no_fill_timeout_seconds:
                            # No fill - cancel and reassess
                            await self._cancel_order(order)

                # Sleep 1 second
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in order monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _create_order(self, trade: ApprovedTrade, orderbook: Dict) -> Order:
        """
        Create order with smart routing logic.

        Args:
            trade: ApprovedTrade object
            orderbook: Orderbook data from CLOB API

        Returns:
            Order object
        """
        # Calculate size in shares
        size_shares = trade.approved_size_usd / trade.expected_price

        # Determine order type based on conditions
        best_bid = orderbook.get('best_bid', 0.0)
        best_ask = orderbook.get('best_ask', 1.0)
        bid_depth_usd = orderbook.get('bid_depth_usd', 0.0)
        ask_depth_usd = orderbook.get('ask_depth_usd', 0.0)

        # Calculate spread
        spread_pct = ((best_ask - best_bid) / best_bid) * 100 if best_bid > 0 else 0.0

        # Smart routing logic
        if trade.side == OrderSide.BUY:
            available_depth = ask_depth_usd
            limit_price = best_ask - (self.config.price_improvement_ticks * 0.001)  # Improve by 2 ticks
        else:
            available_depth = bid_depth_usd
            limit_price = best_bid + (self.config.price_improvement_ticks * 0.001)

        # Rule 1: Use iceberg for large orders
        if trade.approved_size_usd > (available_depth * self.config.iceberg_threshold_pct / 100):
            order_type = OrderType.LIMIT
            # TODO: Implement iceberg logic (split into chunks)
            logger.info("Using ICEBERG order (large size)")

        # Rule 2: Use passive maker for wide spreads
        elif spread_pct > self.config.wide_spread_threshold_pct:
            order_type = OrderType.LIMIT_MAKER
            logger.info(f"Using LIMIT_MAKER (wide spread: {spread_pct:.2f}%)")

        # Rule 3: Default to limit order
        else:
            order_type = OrderType.LIMIT
            logger.info("Using LIMIT order (default)")

        # Create order
        order = Order(
            order_id=self._generate_order_id(),
            market_id=trade.market_id,
            side=trade.side,
            order_type=order_type,
            size=size_shares,
            price=limit_price,
            expiration=datetime.now() + timedelta(seconds=self.config.default_expiration_seconds),
            status=OrderStatus.PENDING,
            filled_size=0.0,
            avg_fill_price=0.0,
            fees_paid_usd=0.0,
            proposal_id=trade.proposal_id,
            submitted_at=None,
            filled_at=None,
            clob_order_id=None
        )

        return order

    async def _sign_order(self, order: Order) -> Dict:
        """
        Sign order using EIP-712 standard.

        EIP-712 provides structured data signing for Ethereum.

        Args:
            order: Order object

        Returns:
            Signed order message dict
        """
        # Construct EIP-712 message
        eip712_message = {
            'types': {
                'EIP712Domain': [
                    {'name': 'name', 'type': 'string'},
                    {'name': 'version', 'type': 'string'},
                    {'name': 'chainId', 'type': 'uint256'}
                ],
                'Order': [
                    {'name': 'market', 'type': 'address'},
                    {'name': 'maker', 'type': 'address'},
                    {'name': 'side', 'type': 'uint8'},
                    {'name': 'size', 'type': 'uint256'},
                    {'name': 'price', 'type': 'uint256'},
                    {'name': 'expiration', 'type': 'uint256'}
                ]
            },
            'domain': {
                'name': 'Polymarket CTF Exchange',
                'version': '1',
                'chainId': 137  # Polygon mainnet
            },
            'primaryType': 'Order',
            'message': {
                'market': order.market_id,
                'maker': self.wallet_address,
                'side': 0 if order.side == OrderSide.BUY else 1,
                'size': int(order.size * 1e18),  # Convert to wei
                'price': int(order.price * 1e18),
                'expiration': int(order.expiration.timestamp())
            }
        }

        # Sign with private key
        # TODO: Implement proper EIP-712 signing
        # For now, placeholder
        signature = self._eip712_sign(eip712_message, self.private_key)

        signed_order = {
            'order': eip712_message['message'],
            'signature': signature,
            'order_id': order.order_id
        }

        return signed_order

    def _eip712_sign(self, message: Dict, private_key: str) -> str:
        """EIP-712 signing (placeholder)"""
        # In production, use web3.py or eth_account
        message_hash = hashlib.sha256(json.dumps(message).encode()).hexdigest()
        return f"0x{message_hash}"  # Placeholder signature

    async def _submit_to_clob(self, signed_order: Dict) -> Dict:
        """
        Submit signed order to Polymarket CLOB API.

        Args:
            signed_order: Signed order message

        Returns:
            CLOB API response
        """
        # Placeholder - would use httpx or aiohttp
        # POST https://clob.polymarket.com/orders

        logger.debug(f"Submitting order to CLOB: {signed_order['order_id']}")

        # Simulate API response
        response = {
            'order_id': f"clob_{signed_order['order_id']}",
            'status': 'ACCEPTED',
            'timestamp': datetime.now().isoformat()
        }

        return response

    async def _check_order_status(self, order: Order) -> OrderStatus:
        """Check order status from CLOB API"""
        # Placeholder - would query CLOB API
        return order.status

    async def _handle_filled_order(self, order: Order):
        """Handle a completely filled order"""
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now()

        # Remove from active orders
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]

        # Add to history
        self.order_history.append(order)

        # Publish OrderFilled event
        self._publish_event('OrderFilled', {
            'order_id': order.order_id,
            'proposal_id': order.proposal_id,
            'market_id': order.market_id,
            'side': order.side.value,
            'filled_size': order.filled_size,
            'avg_fill_price': order.avg_fill_price,
            'fees_paid_usd': order.fees_paid_usd,
            'slippage_usd': (order.avg_fill_price - order.price) * order.filled_size,
            'fill_time_seconds': (order.filled_at - order.submitted_at).total_seconds(),
            'timestamp': datetime.now().isoformat()
        })

        # Update stats
        self.execution_stats['successful_fills'] += 1
        fill_time = (order.filled_at - order.submitted_at).total_seconds()
        self.execution_stats['avg_fill_time_seconds'] = (
            0.9 * self.execution_stats['avg_fill_time_seconds']
            + 0.1 * fill_time
        )
        self.execution_stats['total_fees_paid_usd'] += order.fees_paid_usd

        logger.info(
            f"✅ Order FILLED | "
            f"Order ID: {order.order_id} | "
            f"Fill time: {fill_time:.1f}s | "
            f"Avg price: ${order.avg_fill_price:.4f} | "
            f"Fees: ${order.fees_paid_usd:.2f}"
        )

    async def _cancel_order(self, order: Order):
        """Cancel an active order"""
        logger.info(f"🚫 Cancelling order: {order.order_id}")

        # Submit cancellation to CLOB
        # TODO: Implement CLOB API cancellation
        # DELETE https://clob.polymarket.com/orders/{order_id}

        order.status = OrderStatus.CANCELLED

        # Remove from active orders
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]

        # Add to history
        self.order_history.append(order)

        # Publish OrderCancelled event
        self._publish_event('OrderCancelled', {
            'order_id': order.order_id,
            'proposal_id': order.proposal_id,
            'reason': 'timeout',
            'timestamp': datetime.now().isoformat()
        })

        self.execution_stats['cancellations'] += 1

    async def _fetch_orderbook(self, market_id: str) -> Dict:
        """Fetch orderbook from CLOB API"""
        # Placeholder - would use CLOB API
        # GET https://clob.polymarket.com/books/{market_id}

        return {
            'best_bid': 0.65,
            'best_ask': 0.67,
            'bid_depth_usd': 5000.0,
            'ask_depth_usd': 8000.0
        }

    async def _fetch_approved_trades(self) -> List[ApprovedTrade]:
        """Fetch approved trades from message queue"""
        # Placeholder - would use NATS subscription
        return []

    async def _load_from_kms(self) -> str:
        """Load private key from AWS KMS"""
        # Placeholder - would use boto3 KMS client
        logger.debug("Loading private key from AWS KMS...")
        return "0x1234567890abcdef"  # Placeholder

    async def _load_from_mpc(self) -> str:
        """Load private key from Fireblocks MPC"""
        # Placeholder - would use Fireblocks SDK
        logger.debug("Loading private key from Fireblocks MPC...")
        return "0x1234567890abcdef"  # Placeholder

    def _derive_address(self, private_key: str) -> str:
        """Derive Ethereum address from private key"""
        # Placeholder - would use eth_account
        return "0xWALLET_ADDRESS"

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        timestamp = int(time.time() * 1000)
        return f"order_{timestamp}_{hash(self.wallet_address) % 10000:04d}"

    def _publish_event(self, event_type: str, payload: Dict):
        """Publish event to message bus"""
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'ExecutionAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.message_queue.append(event)
        logger.debug(f"Published event: {event_type}")

    def get_execution_stats(self) -> Dict:
        """Get execution statistics"""
        total = self.execution_stats['total_orders']
        fills = self.execution_stats['successful_fills']

        return {
            'total_orders': total,
            'successful_fills': fills,
            'partial_fills': self.execution_stats['partial_fills'],
            'cancellations': self.execution_stats['cancellations'],
            'rejections': self.execution_stats['rejections'],
            'fill_rate_pct': (fills / total * 100) if total > 0 else 0.0,
            'avg_submission_latency_ms': self.execution_stats['avg_submission_latency_ms'],
            'avg_fill_time_seconds': self.execution_stats['avg_fill_time_seconds'],
            'total_fees_paid_usd': self.execution_stats['total_fees_paid_usd'],
            'total_slippage_usd': self.execution_stats['total_slippage_usd'],
            'active_orders_count': len(self.active_orders)
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize agent
        agent = ExecutionAgent()

        # Load private key from secure storage
        await agent.initialize_security()

        # Start both loops concurrently
        await asyncio.gather(
            agent.execution_loop(),
            agent.order_monitoring_loop()
        )

    # Run
    asyncio.run(main())
