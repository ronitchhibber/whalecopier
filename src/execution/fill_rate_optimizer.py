"""
Fill Rate Optimization System
Week 7: Slippage & Execution Optimization - Fill Rate Optimization
Analyzes fill rates and dynamically adjusts order pricing to achieve >95% fill rate
"""

import logging
import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"              # Waiting for execution
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partially filled
    FILLED = "FILLED"                # Fully filled
    CANCELLED = "CANCELLED"          # Cancelled (timeout)
    FAILED = "FAILED"                # Failed to execute


class FillStrategy(Enum):
    """Fill rate improvement strategy"""
    STANDARD = "STANDARD"            # Normal pricing
    AGGRESSIVE = "AGGRESSIVE"        # +1% more aggressive
    VERY_AGGRESSIVE = "VERY_AGGRESSIVE"  # +2% more aggressive
    PASSIVE = "PASSIVE"              # Less aggressive (save fees)


@dataclass
class OrderExecution:
    """Record of an order execution attempt"""
    order_id: str
    market_id: str
    side: str  # "BUY" or "SELL"

    # Order details
    target_size_usd: Decimal
    filled_size_usd: Decimal
    limit_price: Optional[Decimal]

    # Timing
    placed_at: datetime
    filled_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    time_to_fill_seconds: Optional[Decimal]

    # Outcome
    status: OrderStatus
    fill_rate_percentage: Decimal  # % of order filled
    retry_count: int
    strategy_used: FillStrategy

    # Context
    market_liquidity_score: Optional[Decimal]
    order_book_depth_usd: Optional[Decimal]


@dataclass
class FillRateMetrics:
    """Fill rate metrics for a market or time period"""
    market_id: Optional[str]
    time_period: str  # "1h", "24h", "7d", "all"

    # Fill rate stats
    total_orders: int
    filled_orders: int
    partially_filled_orders: int
    cancelled_orders: int

    fill_rate_percentage: Decimal
    avg_time_to_fill_seconds: Decimal

    # By order size
    fill_rate_small: Decimal   # <$500
    fill_rate_medium: Decimal  # $500-$1500
    fill_rate_large: Decimal   # >$1500

    # Strategy effectiveness
    strategy_stats: Dict[FillStrategy, Dict[str, Decimal]]

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FillRateAlert:
    """Alert for poor fill rate performance"""
    alert_type: str  # "LOW_FILL_RATE", "HIGH_CANCELLATION", "SLOW_FILLS"
    severity: str    # "WARNING", "CRITICAL"
    message: str

    market_id: Optional[str]
    current_fill_rate: Decimal
    target_fill_rate: Decimal

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FillRateConfig:
    """Configuration for fill rate optimization"""
    # Target metrics
    target_fill_rate: Decimal = Decimal("0.95")  # Target 95% fill rate
    min_acceptable_fill_rate: Decimal = Decimal("0.85")  # Minimum 85%

    # Timeout settings
    cancel_timeout_seconds: int = 30  # Cancel after 30s
    retry_max_attempts: int = 3       # Max 3 retries
    retry_delay_seconds: int = 5      # Wait 5s between retries

    # Price adjustment
    price_adjustment_step: Decimal = Decimal("0.01")  # 1% steps
    max_price_adjustment: Decimal = Decimal("0.03")   # Max 3% adjustment

    # Strategy selection
    aggressive_threshold: Decimal = Decimal("0.90")  # Use aggressive if <90%
    very_aggressive_threshold: Decimal = Decimal("0.80")  # Very aggressive if <80%

    # Monitoring
    alert_low_fill_rate: Decimal = Decimal("0.85")  # Alert if <85%
    alert_high_cancellation: Decimal = Decimal("0.20")  # Alert if >20% cancelled

    # Market blacklist
    enable_market_blacklist: bool = True
    blacklist_threshold: Decimal = Decimal("0.70")  # Blacklist if <70% fill rate
    blacklist_min_orders: int = 10  # Need 10+ orders to blacklist


# ==================== Fill Rate Optimizer ====================

class FillRateOptimizer:
    """
    Fill Rate Optimization System

    Optimizes order execution to achieve >95% fill rate through:
    1. **Historical Analysis:** Track fill rates by market, size, time
    2. **Dynamic Pricing:** Adjust order pricing based on fill rate history
    3. **Cancel & Retry:** Cancel unfilled orders after 30s and retry with better pricing
    4. **Strategy Selection:** Choose execution strategy based on market conditions
    5. **Market Blacklist:** Skip markets with consistently poor fill rates
    6. **Performance Monitoring:** Alert on fill rate degradation

    Fill Rate Calculation:
    - Fill Rate = (Filled Orders / Total Orders) * 100%
    - Target: >95% of orders filled within 30 seconds
    - Partially filled orders count as fills (but tracked separately)

    Pricing Strategy:
    - Standard: Normal limit order pricing (best bid/ask)
    - Aggressive: +1% more aggressive (buy higher, sell lower)
    - Very Aggressive: +2% more aggressive
    - Passive: Less aggressive (save on fees, accept slower fills)
    """

    def __init__(self, config: Optional[FillRateConfig] = None):
        """
        Initialize fill rate optimizer

        Args:
            config: Fill rate optimization configuration
        """
        self.config = config or FillRateConfig()

        # Order tracking
        self.active_orders: Dict[str, OrderExecution] = {}
        self.order_history: deque = deque(maxlen=10000)  # Last 10k orders

        # Fill rate tracking by market
        self.market_fill_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Market blacklist (markets with poor fill rates)
        self.blacklisted_markets: Set[str] = set()

        # Alerts
        self.active_alerts: List[FillRateAlert] = []

        # Background monitoring
        self.monitor_task: Optional[asyncio.Task] = None

        logger.info(
            f"FillRateOptimizer initialized: "
            f"target={float(self.config.target_fill_rate)*100:.0f}%, "
            f"timeout={self.config.cancel_timeout_seconds}s, "
            f"max_retries={self.config.retry_max_attempts}"
        )

    async def initialize(self):
        """Start background monitoring task"""
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("FillRateOptimizer monitoring started")

    async def shutdown(self):
        """Shutdown optimizer"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("FillRateOptimizer shutdown complete")

    def should_skip_market(self, market_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if market should be skipped due to poor fill rate

        Args:
            market_id: Market identifier

        Returns:
            (should_skip, reason)
        """
        if not self.config.enable_market_blacklist:
            return False, None

        if market_id in self.blacklisted_markets:
            return True, f"Market blacklisted (fill rate <{float(self.config.blacklist_threshold)*100:.0f}%)"

        return False, None

    def select_strategy(
        self,
        market_id: str,
        order_size_usd: Decimal
    ) -> FillStrategy:
        """
        Select execution strategy based on historical fill rate

        Args:
            market_id: Market identifier
            order_size_usd: Order size in USD

        Returns:
            Recommended fill strategy
        """
        # Get recent fill rate for this market
        recent_fill_rate = self._get_market_fill_rate(market_id, lookback_hours=24)

        # Select strategy based on fill rate
        if recent_fill_rate < self.config.very_aggressive_threshold:
            logger.info(
                f"Market {market_id} fill rate {float(recent_fill_rate)*100:.1f}% "
                f"-> VERY AGGRESSIVE strategy"
            )
            return FillStrategy.VERY_AGGRESSIVE

        elif recent_fill_rate < self.config.aggressive_threshold:
            logger.info(
                f"Market {market_id} fill rate {float(recent_fill_rate)*100:.1f}% "
                f"-> AGGRESSIVE strategy"
            )
            return FillStrategy.AGGRESSIVE

        elif recent_fill_rate >= Decimal("0.98"):
            # Excellent fill rate - can afford to be passive
            logger.debug(f"Market {market_id} fill rate excellent -> PASSIVE strategy")
            return FillStrategy.PASSIVE

        else:
            return FillStrategy.STANDARD

    def calculate_limit_price(
        self,
        side: str,
        best_price: Decimal,
        strategy: FillStrategy
    ) -> Decimal:
        """
        Calculate limit price based on strategy

        Args:
            side: "BUY" or "SELL"
            best_price: Best bid/ask price
            strategy: Fill strategy to use

        Returns:
            Adjusted limit price
        """
        adjustment = Decimal("0")

        if strategy == FillStrategy.AGGRESSIVE:
            adjustment = self.config.price_adjustment_step  # +1%
        elif strategy == FillStrategy.VERY_AGGRESSIVE:
            adjustment = self.config.price_adjustment_step * Decimal("2")  # +2%
        elif strategy == FillStrategy.PASSIVE:
            adjustment = -self.config.price_adjustment_step * Decimal("0.5")  # -0.5%

        # Apply adjustment
        if side == "BUY":
            # For buys, increase price to fill faster
            limit_price = best_price * (Decimal("1") + adjustment)
        else:  # SELL
            # For sells, decrease price to fill faster
            limit_price = best_price * (Decimal("1") - adjustment)

        return limit_price

    async def execute_with_retry(
        self,
        order_id: str,
        market_id: str,
        side: str,
        target_size_usd: Decimal,
        best_price: Decimal,
        execute_fn,  # Function to actually execute the order
        **kwargs
    ) -> OrderExecution:
        """
        Execute order with automatic retry on timeout

        Args:
            order_id: Unique order identifier
            market_id: Market to trade
            side: "BUY" or "SELL"
            target_size_usd: Target order size
            best_price: Best bid/ask price
            execute_fn: Async function to execute order
            **kwargs: Additional parameters for execute_fn

        Returns:
            Order execution result
        """
        # Check if market is blacklisted
        should_skip, reason = self.should_skip_market(market_id)
        if should_skip:
            logger.warning(f"Skipping order {order_id}: {reason}")
            return self._create_failed_order(order_id, market_id, side, target_size_usd, reason)

        # Select strategy
        strategy = self.select_strategy(market_id, target_size_usd)

        # Retry loop
        for attempt in range(self.config.retry_max_attempts):
            try:
                # Calculate limit price
                limit_price = self.calculate_limit_price(side, best_price, strategy)

                logger.info(
                    f"Order {order_id} attempt {attempt+1}/{self.config.retry_max_attempts}: "
                    f"{side} {target_size_usd} on {market_id} @ {limit_price} ({strategy.value})"
                )

                # Create order record
                order = OrderExecution(
                    order_id=f"{order_id}_retry{attempt}",
                    market_id=market_id,
                    side=side,
                    target_size_usd=target_size_usd,
                    filled_size_usd=Decimal("0"),
                    limit_price=limit_price,
                    placed_at=datetime.now(),
                    filled_at=None,
                    cancelled_at=None,
                    time_to_fill_seconds=None,
                    status=OrderStatus.PENDING,
                    fill_rate_percentage=Decimal("0"),
                    retry_count=attempt,
                    strategy_used=strategy,
                    market_liquidity_score=None,
                    order_book_depth_usd=None
                )

                self.active_orders[order.order_id] = order

                # Execute order (with timeout)
                start_time = time.time()

                try:
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        execute_fn(
                            order_id=order.order_id,
                            market_id=market_id,
                            side=side,
                            size_usd=target_size_usd,
                            limit_price=limit_price,
                            **kwargs
                        ),
                        timeout=self.config.cancel_timeout_seconds
                    )

                    # Success!
                    time_to_fill = Decimal(str(time.time() - start_time))

                    order.filled_size_usd = result.get("filled_size_usd", target_size_usd)
                    order.filled_at = datetime.now()
                    order.time_to_fill_seconds = time_to_fill
                    order.status = OrderStatus.FILLED
                    order.fill_rate_percentage = (order.filled_size_usd / target_size_usd) * Decimal("100")

                    logger.info(
                        f"✅ Order {order.order_id} FILLED: "
                        f"{order.filled_size_usd}/{target_size_usd} ({order.fill_rate_percentage:.1f}%) "
                        f"in {time_to_fill:.1f}s"
                    )

                    # Record metrics
                    self._record_order(order)
                    return order

                except asyncio.TimeoutError:
                    # Timeout - cancel and retry
                    time_elapsed = Decimal(str(time.time() - start_time))

                    order.cancelled_at = datetime.now()
                    order.status = OrderStatus.CANCELLED
                    order.time_to_fill_seconds = time_elapsed

                    logger.warning(
                        f"⏰ Order {order.order_id} TIMEOUT after {time_elapsed:.1f}s "
                        f"(attempt {attempt+1}/{self.config.retry_max_attempts})"
                    )

                    # Record failed attempt
                    self._record_order(order)

                    # If not last attempt, escalate strategy and retry
                    if attempt < self.config.retry_max_attempts - 1:
                        # Escalate strategy
                        if strategy == FillStrategy.STANDARD:
                            strategy = FillStrategy.AGGRESSIVE
                        elif strategy == FillStrategy.AGGRESSIVE:
                            strategy = FillStrategy.VERY_AGGRESSIVE

                        logger.info(
                            f"Retrying order {order_id} with {strategy.value} strategy "
                            f"after {self.config.retry_delay_seconds}s delay"
                        )

                        await asyncio.sleep(self.config.retry_delay_seconds)
                        continue
                    else:
                        # Last attempt failed
                        logger.error(f"❌ Order {order_id} FAILED after {attempt+1} attempts")
                        return order

            except Exception as e:
                logger.error(f"Order {order_id} execution error: {str(e)}")

                # Record as failed
                order.status = OrderStatus.FAILED
                self._record_order(order)

                if attempt < self.config.retry_max_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)
                    continue
                else:
                    raise

        # All retries exhausted
        return order

    def _create_failed_order(
        self,
        order_id: str,
        market_id: str,
        side: str,
        target_size_usd: Decimal,
        reason: str
    ) -> OrderExecution:
        """Create a failed order record"""
        order = OrderExecution(
            order_id=order_id,
            market_id=market_id,
            side=side,
            target_size_usd=target_size_usd,
            filled_size_usd=Decimal("0"),
            limit_price=None,
            placed_at=datetime.now(),
            filled_at=None,
            cancelled_at=datetime.now(),
            time_to_fill_seconds=None,
            status=OrderStatus.FAILED,
            fill_rate_percentage=Decimal("0"),
            retry_count=0,
            strategy_used=FillStrategy.STANDARD,
            market_liquidity_score=None,
            order_book_depth_usd=None
        )
        self._record_order(order)
        return order

    def _record_order(self, order: OrderExecution):
        """Record order execution metrics"""
        # Add to history
        self.order_history.append(order)

        # Add to market-specific tracking
        self.market_fill_rates[order.market_id].append(order)

        # Remove from active orders
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]

        # Update market blacklist
        self._update_market_blacklist(order.market_id)

    def _get_market_fill_rate(
        self,
        market_id: str,
        lookback_hours: int = 24
    ) -> Decimal:
        """Calculate fill rate for a market"""
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)

        # Get recent orders for this market
        recent_orders = [
            order for order in self.market_fill_rates[market_id]
            if order.placed_at >= cutoff_time
        ]

        if not recent_orders:
            return Decimal("1.0")  # Assume 100% if no data

        filled = sum(1 for order in recent_orders if order.status == OrderStatus.FILLED)
        total = len(recent_orders)

        return Decimal(str(filled)) / Decimal(str(total))

    def _update_market_blacklist(self, market_id: str):
        """Update market blacklist based on fill rate"""
        if not self.config.enable_market_blacklist:
            return

        # Need minimum number of orders
        if len(self.market_fill_rates[market_id]) < self.config.blacklist_min_orders:
            return

        # Calculate fill rate
        fill_rate = self._get_market_fill_rate(market_id, lookback_hours=168)  # 7 days

        # Blacklist if below threshold
        if fill_rate < self.config.blacklist_threshold:
            if market_id not in self.blacklisted_markets:
                self.blacklisted_markets.add(market_id)
                logger.warning(
                    f"⛔ BLACKLISTED market {market_id}: "
                    f"fill rate {float(fill_rate)*100:.1f}% < {float(self.config.blacklist_threshold)*100:.0f}%"
                )

                # Create alert
                alert = FillRateAlert(
                    alert_type="LOW_FILL_RATE",
                    severity="CRITICAL",
                    message=f"Market {market_id} blacklisted due to low fill rate",
                    market_id=market_id,
                    current_fill_rate=fill_rate,
                    target_fill_rate=self.config.target_fill_rate
                )
                self.active_alerts.append(alert)

        # Remove from blacklist if improved
        elif fill_rate >= self.config.aggressive_threshold:
            if market_id in self.blacklisted_markets:
                self.blacklisted_markets.remove(market_id)
                logger.info(
                    f"✅ UNBLACKLISTED market {market_id}: "
                    f"fill rate improved to {float(fill_rate)*100:.1f}%"
                )

    async def _monitor_loop(self):
        """Background monitoring task"""
        logger.info("Fill rate monitoring loop started")

        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                # Generate alerts
                metrics = self.get_fill_rate_metrics(time_period="1h")

                # Alert on low fill rate
                if metrics.fill_rate_percentage < self.config.alert_low_fill_rate * Decimal("100"):
                    alert = FillRateAlert(
                        alert_type="LOW_FILL_RATE",
                        severity="WARNING",
                        message=f"Fill rate {metrics.fill_rate_percentage:.1f}% below target",
                        market_id=None,
                        current_fill_rate=metrics.fill_rate_percentage / Decimal("100"),
                        target_fill_rate=self.config.target_fill_rate
                    )
                    self.active_alerts.append(alert)
                    logger.warning(f"⚠️  {alert.message}")

                # Alert on high cancellation rate
                if metrics.total_orders > 0:
                    cancellation_rate = Decimal(str(metrics.cancelled_orders)) / Decimal(str(metrics.total_orders))
                    if cancellation_rate > self.config.alert_high_cancellation:
                        alert = FillRateAlert(
                            alert_type="HIGH_CANCELLATION",
                            severity="WARNING",
                            message=f"Cancellation rate {float(cancellation_rate)*100:.1f}% too high",
                            market_id=None,
                            current_fill_rate=metrics.fill_rate_percentage / Decimal("100"),
                            target_fill_rate=self.config.target_fill_rate
                        )
                        self.active_alerts.append(alert)
                        logger.warning(f"⚠️  {alert.message}")

            except asyncio.CancelledError:
                logger.info("Fill rate monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {str(e)}")

    def get_fill_rate_metrics(
        self,
        market_id: Optional[str] = None,
        time_period: str = "24h"
    ) -> FillRateMetrics:
        """
        Get fill rate metrics

        Args:
            market_id: Specific market (None for all)
            time_period: "1h", "24h", "7d", "all"

        Returns:
            Fill rate metrics
        """
        # Determine time window
        if time_period == "1h":
            cutoff = datetime.now() - timedelta(hours=1)
        elif time_period == "24h":
            cutoff = datetime.now() - timedelta(hours=24)
        elif time_period == "7d":
            cutoff = datetime.now() - timedelta(days=7)
        else:  # "all"
            cutoff = datetime.min

        # Filter orders
        if market_id:
            orders = [
                order for order in self.market_fill_rates[market_id]
                if order.placed_at >= cutoff
            ]
        else:
            orders = [order for order in self.order_history if order.placed_at >= cutoff]

        if not orders:
            return FillRateMetrics(
                market_id=market_id,
                time_period=time_period,
                total_orders=0,
                filled_orders=0,
                partially_filled_orders=0,
                cancelled_orders=0,
                fill_rate_percentage=Decimal("0"),
                avg_time_to_fill_seconds=Decimal("0"),
                fill_rate_small=Decimal("0"),
                fill_rate_medium=Decimal("0"),
                fill_rate_large=Decimal("0"),
                strategy_stats={}
            )

        # Calculate metrics
        total_orders = len(orders)
        filled_orders = sum(1 for o in orders if o.status == OrderStatus.FILLED)
        partially_filled = sum(1 for o in orders if o.status == OrderStatus.PARTIALLY_FILLED)
        cancelled_orders = sum(1 for o in orders if o.status == OrderStatus.CANCELLED)

        fill_rate_pct = (Decimal(str(filled_orders)) / Decimal(str(total_orders))) * Decimal("100")

        # Average time to fill
        filled_times = [o.time_to_fill_seconds for o in orders if o.time_to_fill_seconds]
        avg_time = sum(filled_times) / len(filled_times) if filled_times else Decimal("0")

        # Fill rate by order size
        small_orders = [o for o in orders if o.target_size_usd < Decimal("500")]
        medium_orders = [o for o in orders if Decimal("500") <= o.target_size_usd <= Decimal("1500")]
        large_orders = [o for o in orders if o.target_size_usd > Decimal("1500")]

        fill_rate_small = self._calculate_fill_rate(small_orders)
        fill_rate_medium = self._calculate_fill_rate(medium_orders)
        fill_rate_large = self._calculate_fill_rate(large_orders)

        # Strategy stats
        strategy_stats = {}
        for strategy in FillStrategy:
            strategy_orders = [o for o in orders if o.strategy_used == strategy]
            if strategy_orders:
                strategy_stats[strategy] = {
                    "count": len(strategy_orders),
                    "fill_rate": self._calculate_fill_rate(strategy_orders),
                    "avg_time": sum(o.time_to_fill_seconds for o in strategy_orders if o.time_to_fill_seconds) / len(strategy_orders)
                }

        return FillRateMetrics(
            market_id=market_id,
            time_period=time_period,
            total_orders=total_orders,
            filled_orders=filled_orders,
            partially_filled_orders=partially_filled,
            cancelled_orders=cancelled_orders,
            fill_rate_percentage=fill_rate_pct,
            avg_time_to_fill_seconds=avg_time,
            fill_rate_small=fill_rate_small,
            fill_rate_medium=fill_rate_medium,
            fill_rate_large=fill_rate_large,
            strategy_stats=strategy_stats
        )

    def _calculate_fill_rate(self, orders: List[OrderExecution]) -> Decimal:
        """Calculate fill rate for a list of orders"""
        if not orders:
            return Decimal("0")
        filled = sum(1 for o in orders if o.status == OrderStatus.FILLED)
        return (Decimal(str(filled)) / Decimal(str(len(orders)))) * Decimal("100")

    def get_recommendations(self) -> List[str]:
        """Get recommendations for improving fill rates"""
        recommendations = []

        metrics = self.get_fill_rate_metrics(time_period="24h")

        # Overall fill rate
        if metrics.fill_rate_percentage < self.config.target_fill_rate * Decimal("100"):
            recommendations.append(
                f"📉 Overall fill rate {metrics.fill_rate_percentage:.1f}% below target "
                f"{float(self.config.target_fill_rate)*100:.0f}%"
            )

        # Large orders
        if metrics.fill_rate_large < Decimal("90"):
            recommendations.append(
                f"🔴 Large orders (>$1500) have low fill rate {metrics.fill_rate_large:.1f}% - "
                "consider using TWAP or smaller chunks"
            )

        # Blacklisted markets
        if self.blacklisted_markets:
            recommendations.append(
                f"⛔ {len(self.blacklisted_markets)} markets blacklisted due to poor fill rates: "
                f"{', '.join(list(self.blacklisted_markets)[:3])}"
            )

        # Strategy effectiveness
        if FillStrategy.VERY_AGGRESSIVE in metrics.strategy_stats:
            very_agg_stats = metrics.strategy_stats[FillStrategy.VERY_AGGRESSIVE]
            if very_agg_stats["fill_rate"] < Decimal("85"):
                recommendations.append(
                    f"🟡 Even VERY_AGGRESSIVE strategy has low fill rate "
                    f"{very_agg_stats['fill_rate']:.1f}% - market liquidity may be insufficient"
                )

        # High cancellation rate
        if metrics.total_orders > 0:
            cancellation_rate = (Decimal(str(metrics.cancelled_orders)) / Decimal(str(metrics.total_orders))) * Decimal("100")
            if cancellation_rate > Decimal("20"):
                recommendations.append(
                    f"⏰ High cancellation rate {cancellation_rate:.1f}% - "
                    "consider increasing timeout or using more aggressive pricing"
                )

        if not recommendations:
            recommendations.append(
                f"✅ Fill rate {metrics.fill_rate_percentage:.1f}% meets target - no action needed"
            )

        return recommendations


# ==================== Example Usage ====================

async def mock_execute_order(order_id, market_id, side, size_usd, limit_price, **kwargs):
    """Mock order execution for testing"""
    # Simulate order execution with random success
    import random
    await asyncio.sleep(random.uniform(0.5, 2.0))  # Random execution time

    success = random.random() > 0.2  # 80% success rate

    if success:
        return {
            "filled_size_usd": size_usd,
            "avg_price": limit_price
        }
    else:
        raise Exception("Order execution failed")


async def main():
    """Example usage of FillRateOptimizer"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize optimizer
    optimizer = FillRateOptimizer()
    await optimizer.initialize()

    print("\n=== Fill Rate Optimizer Test ===\n")

    try:
        # Test orders
        test_orders = [
            ("order1", "market_A", "BUY", Decimal("300"), Decimal("0.55")),
            ("order2", "market_A", "SELL", Decimal("800"), Decimal("0.60")),
            ("order3", "market_B", "BUY", Decimal("1200"), Decimal("0.45")),
            ("order4", "market_A", "BUY", Decimal("400"), Decimal("0.56")),
            ("order5", "market_B", "SELL", Decimal("600"), Decimal("0.48")),
        ]

        print("=== Executing Test Orders ===\n")

        for order_id, market_id, side, size_usd, best_price in test_orders:
            try:
                result = await optimizer.execute_with_retry(
                    order_id=order_id,
                    market_id=market_id,
                    side=side,
                    target_size_usd=size_usd,
                    best_price=best_price,
                    execute_fn=mock_execute_order
                )

                print(f"{order_id}: {result.status.value} "
                      f"({result.fill_rate_percentage:.0f}% in {result.time_to_fill_seconds:.1f}s)")

            except Exception as e:
                print(f"{order_id}: FAILED - {str(e)}")

        # Get metrics
        print("\n=== Fill Rate Metrics ===\n")
        metrics = optimizer.get_fill_rate_metrics(time_period="all")

        print(f"Total Orders: {metrics.total_orders}")
        print(f"Fill Rate: {metrics.fill_rate_percentage:.1f}%")
        print(f"Avg Time to Fill: {metrics.avg_time_to_fill_seconds:.1f}s")
        print(f"Cancelled: {metrics.cancelled_orders}")
        print(f"\nFill Rate by Size:")
        print(f"  Small (<$500): {metrics.fill_rate_small:.1f}%")
        print(f"  Medium ($500-$1500): {metrics.fill_rate_medium:.1f}%")
        print(f"  Large (>$1500): {metrics.fill_rate_large:.1f}%")

        # Get recommendations
        print("\n=== Recommendations ===\n")
        recommendations = optimizer.get_recommendations()
        for rec in recommendations:
            print(f"  {rec}")

    finally:
        await optimizer.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
