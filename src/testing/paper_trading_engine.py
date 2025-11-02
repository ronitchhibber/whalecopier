"""
Paper Trading Engine
Week 8: Testing & Simulation - Paper Trading Mode
Real-time trading simulation WITHOUT real money - all logic active
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import json

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class TradingMode(Enum):
    """Trading mode"""
    PAPER = "PAPER"  # Virtual trading (no real money)
    LIVE = "LIVE"    # Real trading (real money)


class OrderType(Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class VirtualPosition:
    """Virtual position in paper trading"""
    position_id: str
    market_id: str
    outcome: str
    side: str  # "LONG" or "SHORT"

    # Entry
    entry_timestamp: datetime
    entry_price: Decimal
    size_shares: Decimal
    size_usd: Decimal
    entry_fees_usd: Decimal

    # Current state
    current_price: Decimal
    current_value_usd: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_pct: Decimal

    # Exit (if closed)
    exit_timestamp: Optional[datetime]
    exit_price: Optional[Decimal]
    exit_reason: Optional[str]
    exit_fees_usd: Optional[Decimal]
    realized_pnl_usd: Optional[Decimal]
    realized_pnl_pct: Optional[Decimal]

    # Metadata
    whale_address: str
    is_closed: bool = False


@dataclass
class VirtualOrder:
    """Virtual order in paper trading"""
    order_id: str
    market_id: str
    outcome: str
    side: str  # "BUY" or "SELL"
    order_type: OrderType

    # Order details
    size_usd: Decimal
    limit_price: Optional[Decimal]

    # Status
    status: str  # "PENDING", "FILLED", "CANCELLED", "REJECTED"
    created_at: datetime
    filled_at: Optional[datetime]
    filled_price: Optional[Decimal]
    filled_size_usd: Optional[Decimal]

    # Execution
    slippage_pct: Optional[Decimal]
    fees_usd: Optional[Decimal]
    reject_reason: Optional[str]


@dataclass
class PaperTradingMetrics:
    """Performance metrics for paper trading"""
    # Time period
    start_time: datetime
    end_time: datetime

    # Capital
    starting_capital_usd: Decimal
    current_capital_usd: Decimal
    peak_capital_usd: Decimal

    # Positions
    total_positions: int
    open_positions: int
    closed_positions: int

    # Returns
    total_return_usd: Decimal
    total_return_pct: Decimal
    unrealized_pnl_usd: Decimal
    realized_pnl_usd: Decimal

    # Win/Loss
    winning_positions: int
    losing_positions: int
    win_rate_pct: Decimal

    # Risk
    max_drawdown_pct: Decimal
    current_drawdown_pct: Decimal
    sharpe_ratio: Decimal

    # Execution
    avg_slippage_pct: Decimal
    total_fees_usd: Decimal

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PaperVsLiveComparison:
    """Comparison between paper and live trading"""
    time_period: str

    # Paper performance
    paper_return_pct: Decimal
    paper_sharpe: Decimal
    paper_max_dd_pct: Decimal
    paper_win_rate_pct: Decimal

    # Live performance (if available)
    live_return_pct: Optional[Decimal]
    live_sharpe: Optional[Decimal]
    live_max_dd_pct: Optional[Decimal]
    live_win_rate_pct: Optional[Decimal]

    # Comparison
    return_difference_pct: Optional[Decimal]
    risk_adjusted_difference: Optional[Decimal]
    execution_quality_difference: Optional[Decimal]

    # Analysis
    paper_outperforming: bool
    divergence_reasons: List[str]


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading"""
    # Capital
    starting_capital_usd: Decimal = Decimal("100000")  # Start with $100k virtual
    max_position_size_pct: Decimal = Decimal("5")      # Max 5% per position

    # Execution simulation
    simulate_slippage: bool = True
    base_slippage_bps: Decimal = Decimal("10")
    slippage_per_1k_usd: Decimal = Decimal("2")

    simulate_fees: bool = True
    trading_fee_pct: Decimal = Decimal("2")

    simulate_latency: bool = True
    base_latency_ms: Decimal = Decimal("100")

    # Risk management
    enable_position_sizing: bool = True
    enable_stop_loss: bool = True
    stop_loss_pct: Decimal = Decimal("-15")
    enable_take_profit: bool = True
    take_profit_pct: Decimal = Decimal("30")
    enable_circuit_breakers: bool = True
    daily_loss_limit_pct: Decimal = Decimal("-10")

    # Monitoring
    update_interval_seconds: int = 10  # Update prices every 10s
    report_interval_seconds: int = 300  # Generate reports every 5 min


# ==================== Paper Trading Engine ====================

class PaperTradingEngine:
    """
    Paper Trading Engine

    Real-time trading simulation WITHOUT real money:
    1. **Real-Time Monitoring:** Watch live whale trades
    2. **Virtual Execution:** Execute all trades virtually
    3. **Full Logic Active:** All risk management, execution logic active
    4. **Position Tracking:** Track virtual positions and P&L
    5. **Live Comparison:** Compare paper vs live (if live running)
    6. **Performance Reports:** Real-time performance reporting
    7. **Zero Risk:** No real money at risk

    Use Cases:
    - Test strategy before going live
    - Validate code changes
    - Train new strategies
    - Compare strategy variants
    - Onboard new traders

    Virtual Execution:
    - Simulates slippage, fees, latency
    - Uses live order book data
    - Applies all risk management rules
    - Tracks P&L in real-time

    Paper vs Live:
    - Tracks divergence between paper and live
    - Identifies execution quality differences
    - Validates strategy performance
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        whale_monitor_fn: Optional[Callable] = None,
        market_data_fn: Optional[Callable] = None
    ):
        """
        Initialize paper trading engine

        Args:
            config: Paper trading configuration
            whale_monitor_fn: Function to monitor whale trades
            market_data_fn: Function to fetch market data
        """
        self.config = config or PaperTradingConfig()
        self.whale_monitor_fn = whale_monitor_fn
        self.market_data_fn = market_data_fn

        # Trading state
        self.mode = TradingMode.PAPER
        self.is_running = False
        self.start_time = datetime.now()

        # Capital
        self.starting_capital = self.config.starting_capital_usd
        self.current_capital = self.config.starting_capital_usd
        self.peak_capital = self.config.starting_capital_usd

        # Positions
        self.open_positions: Dict[str, VirtualPosition] = {}
        self.closed_positions: List[VirtualPosition] = []
        self.pending_orders: Dict[str, VirtualOrder] = {}
        self.filled_orders: List[VirtualOrder] = []

        # Metrics
        self.equity_curve: List[Tuple[datetime, Decimal]] = []
        self.daily_pnl: Dict[datetime, Decimal] = {}

        # Live comparison (if available)
        self.live_metrics: Optional[Any] = None

        # Background tasks
        self.monitor_task: Optional[asyncio.Task] = None
        self.update_task: Optional[asyncio.Task] = None
        self.report_task: Optional[asyncio.Task] = None

        # Counters
        self.order_counter = 0
        self.position_counter = 0

        logger.info(
            f"PaperTradingEngine initialized: "
            f"starting_capital=${float(self.config.starting_capital_usd):,.0f}, "
            f"mode={self.mode.value}"
        )

    async def start(self):
        """Start paper trading engine"""
        if self.is_running:
            logger.warning("Paper trading already running")
            return

        self.is_running = True
        self.start_time = datetime.now()

        # Start background tasks
        self.monitor_task = asyncio.create_task(self._whale_monitor_loop())
        self.update_task = asyncio.create_task(self._position_update_loop())
        self.report_task = asyncio.create_task(self._reporting_loop())

        logger.info("📝 Paper trading started")

    async def stop(self):
        """Stop paper trading engine"""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel background tasks
        for task in [self.monitor_task, self.update_task, self.report_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all positions
        await self._close_all_positions("SYSTEM_STOP")

        logger.info("📝 Paper trading stopped")

        # Generate final report
        metrics = self.get_metrics()
        self._print_metrics(metrics)

    async def place_order(
        self,
        market_id: str,
        outcome: str,
        side: str,
        size_usd: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        whale_address: Optional[str] = None
    ) -> VirtualOrder:
        """
        Place a virtual order

        Args:
            market_id: Market identifier
            outcome: Outcome to trade
            side: "BUY" or "SELL"
            size_usd: Order size in USD
            order_type: Market or limit order
            limit_price: Limit price (for limit orders)
            whale_address: Whale that triggered this trade

        Returns:
            Virtual order
        """
        self.order_counter += 1
        order_id = f"paper_order_{self.order_counter}"

        # Create order
        order = VirtualOrder(
            order_id=order_id,
            market_id=market_id,
            outcome=outcome,
            side=side,
            order_type=order_type,
            size_usd=size_usd,
            limit_price=limit_price,
            status="PENDING",
            created_at=datetime.now(),
            filled_at=None,
            filled_price=None,
            filled_size_usd=None,
            slippage_pct=None,
            fees_usd=None,
            reject_reason=None
        )

        # Add to pending orders
        self.pending_orders[order_id] = order

        # Execute order (async)
        asyncio.create_task(self._execute_order(order, whale_address))

        logger.debug(f"Placed paper order {order_id}: {side} {size_usd} on {market_id}")

        return order

    async def _execute_order(
        self,
        order: VirtualOrder,
        whale_address: Optional[str] = None
    ):
        """Execute a virtual order"""
        # Simulate latency
        if self.config.simulate_latency:
            latency_ms = self._calculate_latency()
            await asyncio.sleep(latency_ms / 1000)

        # Check capital
        if order.size_usd > self.current_capital * Decimal("0.95"):  # Reserve 5%
            order.status = "REJECTED"
            order.reject_reason = "Insufficient capital"
            logger.warning(f"Order {order.order_id} rejected: insufficient capital")
            return

        # Check circuit breakers
        if self.config.enable_circuit_breakers:
            if self._check_circuit_breakers():
                order.status = "REJECTED"
                order.reject_reason = "Circuit breaker triggered"
                logger.warning(f"Order {order.order_id} rejected: circuit breaker")
                return

        # Fetch current market price
        current_price = await self._get_market_price(order.market_id, order.outcome)

        if not current_price:
            order.status = "REJECTED"
            order.reject_reason = "Market data unavailable"
            logger.warning(f"Order {order.order_id} rejected: no market data")
            return

        # Calculate execution price with slippage
        if self.config.simulate_slippage:
            slippage_pct = self._calculate_slippage(order.size_usd)

            if order.side == "BUY":
                fill_price = current_price * (Decimal("1") + slippage_pct / Decimal("100"))
            else:
                fill_price = current_price * (Decimal("1") - slippage_pct / Decimal("100"))
        else:
            slippage_pct = Decimal("0")
            fill_price = current_price

        # Apply position sizing
        position_size = order.size_usd
        if self.config.enable_position_sizing:
            max_position = self.current_capital * (self.config.max_position_size_pct / Decimal("100"))
            position_size = min(position_size, max_position)

        # Calculate fees
        if self.config.simulate_fees:
            fees = position_size * (self.config.trading_fee_pct / Decimal("100"))
        else:
            fees = Decimal("0")

        # Update capital
        self.current_capital -= (position_size + fees)

        # Update order
        order.status = "FILLED"
        order.filled_at = datetime.now()
        order.filled_price = fill_price
        order.filled_size_usd = position_size
        order.slippage_pct = slippage_pct
        order.fees_usd = fees

        # Move to filled orders
        del self.pending_orders[order.order_id]
        self.filled_orders.append(order)

        # Create position
        self.position_counter += 1
        position_id = f"paper_position_{self.position_counter}"

        # Calculate stop-loss and take-profit
        stop_loss_price = None
        take_profit_price = None

        if self.config.enable_stop_loss:
            stop_loss_price = fill_price * (Decimal("1") + self.config.stop_loss_pct / Decimal("100"))

        if self.config.enable_take_profit:
            take_profit_price = fill_price * (Decimal("1") + self.config.take_profit_pct / Decimal("100"))

        position = VirtualPosition(
            position_id=position_id,
            market_id=order.market_id,
            outcome=order.outcome,
            side="LONG" if order.side == "BUY" else "SHORT",
            entry_timestamp=order.filled_at,
            entry_price=fill_price,
            size_shares=position_size / fill_price,  # Simplified
            size_usd=position_size,
            entry_fees_usd=fees,
            current_price=fill_price,
            current_value_usd=position_size,
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_pct=Decimal("0"),
            exit_timestamp=None,
            exit_price=None,
            exit_reason=None,
            exit_fees_usd=None,
            realized_pnl_usd=None,
            realized_pnl_pct=None,
            whale_address=whale_address or "unknown"
        )

        self.open_positions[position_id] = position

        logger.info(
            f"✅ Filled paper order {order.order_id}: "
            f"{order.side} ${position_size:.2f} @ {fill_price:.3f} "
            f"(slippage {slippage_pct:.2f}%, fees ${fees:.2f})"
        )

    async def close_position(
        self,
        position_id: str,
        reason: str = "MANUAL"
    ):
        """Close a virtual position"""
        if position_id not in self.open_positions:
            logger.warning(f"Position {position_id} not found")
            return

        position = self.open_positions[position_id]

        # Get current price
        current_price = await self._get_market_price(position.market_id, position.outcome)

        if not current_price:
            logger.warning(f"Cannot close position {position_id}: no market data")
            return

        # Calculate exit fees
        exit_value = position.size_shares * current_price

        if self.config.simulate_fees:
            exit_fees = exit_value * (self.config.trading_fee_pct / Decimal("100"))
        else:
            exit_fees = Decimal("0")

        # Calculate P&L
        price_change_pct = ((current_price - position.entry_price) / position.entry_price) * Decimal("100")
        gross_pnl = position.size_usd * (price_change_pct / Decimal("100"))
        realized_pnl = gross_pnl - position.entry_fees_usd - exit_fees
        realized_pnl_pct = (realized_pnl / position.size_usd) * Decimal("100")

        # Update position
        position.exit_timestamp = datetime.now()
        position.exit_price = current_price
        position.exit_reason = reason
        position.exit_fees_usd = exit_fees
        position.realized_pnl_usd = realized_pnl
        position.realized_pnl_pct = realized_pnl_pct
        position.is_closed = True

        # Update capital
        self.current_capital += (exit_value - exit_fees)

        # Update peak capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Record daily P&L
        today = datetime.now().date()
        if today not in self.daily_pnl:
            self.daily_pnl[today] = Decimal("0")
        self.daily_pnl[today] += realized_pnl

        # Move to closed positions
        del self.open_positions[position_id]
        self.closed_positions.append(position)

        logger.info(
            f"📊 Closed position {position_id}: "
            f"P&L ${realized_pnl:+.2f} ({realized_pnl_pct:+.1f}%) | "
            f"Reason: {reason}"
        )

    async def _close_all_positions(self, reason: str = "SYSTEM_STOP"):
        """Close all open positions"""
        for position_id in list(self.open_positions.keys()):
            await self.close_position(position_id, reason)

    async def _whale_monitor_loop(self):
        """Monitor whale trades and copy them (paper trading)"""
        logger.info("Whale monitor loop started")

        while self.is_running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds

                # If whale monitor function provided, use it
                if self.whale_monitor_fn:
                    new_trades = await self.whale_monitor_fn()

                    for trade in new_trades:
                        # Execute paper trade
                        await self.place_order(
                            market_id=trade["market_id"],
                            outcome=trade["outcome"],
                            side=trade["side"],
                            size_usd=Decimal(str(trade["size_usd"])),
                            whale_address=trade["whale_address"]
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Whale monitor error: {str(e)}")

    async def _position_update_loop(self):
        """Update positions with current prices"""
        logger.info("Position update loop started")

        while self.is_running:
            try:
                await asyncio.sleep(self.config.update_interval_seconds)

                # Update all open positions
                for position in self.open_positions.values():
                    # Get current price
                    current_price = await self._get_market_price(position.market_id, position.outcome)

                    if not current_price:
                        continue

                    # Update position
                    position.current_price = current_price
                    position.current_value_usd = position.size_shares * current_price

                    # Calculate unrealized P&L
                    price_change_pct = ((current_price - position.entry_price) / position.entry_price) * Decimal("100")
                    position.unrealized_pnl_usd = position.size_usd * (price_change_pct / Decimal("100"))
                    position.unrealized_pnl_pct = price_change_pct

                    # Check stop-loss
                    if self.config.enable_stop_loss:
                        stop_loss_price = position.entry_price * (Decimal("1") + self.config.stop_loss_pct / Decimal("100"))
                        if current_price <= stop_loss_price:
                            await self.close_position(position.position_id, "STOP_LOSS")
                            continue

                    # Check take-profit
                    if self.config.enable_take_profit:
                        take_profit_price = position.entry_price * (Decimal("1") + self.config.take_profit_pct / Decimal("100"))
                        if current_price >= take_profit_price:
                            await self.close_position(position.position_id, "TAKE_PROFIT")
                            continue

                # Update equity curve
                total_equity = self.current_capital + sum(
                    p.current_value_usd for p in self.open_positions.values()
                )
                self.equity_curve.append((datetime.now(), total_equity))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Position update error: {str(e)}")

    async def _reporting_loop(self):
        """Generate periodic reports"""
        logger.info("Reporting loop started")

        while self.is_running:
            try:
                await asyncio.sleep(self.config.report_interval_seconds)

                # Generate metrics
                metrics = self.get_metrics()

                # Print summary
                logger.info(
                    f"📊 Paper Trading Update: "
                    f"Capital ${float(metrics.current_capital_usd):,.0f}, "
                    f"Return {float(metrics.total_return_pct):+.1f}%, "
                    f"Open Positions {metrics.open_positions}, "
                    f"Win Rate {float(metrics.win_rate_pct):.1f}%"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reporting loop error: {str(e)}")

    def _check_circuit_breakers(self) -> bool:
        """Check if circuit breakers should trigger"""
        today = datetime.now().date()

        if today not in self.daily_pnl:
            return False

        daily_return_pct = (self.daily_pnl[today] / self.starting_capital) * Decimal("100")

        if daily_return_pct <= self.config.daily_loss_limit_pct:
            logger.warning(f"Circuit breaker: Daily loss {daily_return_pct:.1f}%")
            return True

        return False

    def _calculate_slippage(self, order_size_usd: Decimal) -> Decimal:
        """Calculate slippage"""
        base_slippage_pct = self.config.base_slippage_bps / Decimal("100")
        size_slippage = (order_size_usd / Decimal("1000")) * (self.config.slippage_per_1k_usd / Decimal("100"))
        return base_slippage_pct + size_slippage

    def _calculate_latency(self) -> Decimal:
        """Calculate latency"""
        import random
        latency = float(self.config.base_latency_ms) + random.uniform(-20, 50)
        return Decimal(str(max(10, latency)))

    async def _get_market_price(self, market_id: str, outcome: str) -> Optional[Decimal]:
        """Get current market price"""
        if self.market_data_fn:
            try:
                price = await self.market_data_fn(market_id, outcome)
                return Decimal(str(price)) if price else None
            except Exception as e:
                logger.error(f"Market data error: {str(e)}")
                return None
        else:
            # Mock price for testing
            import random
            return Decimal(str(random.uniform(0.4, 0.6)))

    def get_metrics(self) -> PaperTradingMetrics:
        """Get current performance metrics"""
        # Returns
        total_return_usd = self.current_capital - self.starting_capital
        total_return_pct = (total_return_usd / self.starting_capital) * Decimal("100")

        # Unrealized P&L
        unrealized_pnl = sum(p.unrealized_pnl_usd for p in self.open_positions.values())

        # Realized P&L
        realized_pnl = sum(p.realized_pnl_usd for p in self.closed_positions if p.realized_pnl_usd)

        # Win/Loss
        winning = [p for p in self.closed_positions if p.realized_pnl_usd and p.realized_pnl_usd > 0]
        losing = [p for p in self.closed_positions if p.realized_pnl_usd and p.realized_pnl_usd <= 0]

        total_closed = len(self.closed_positions)
        win_rate_pct = (Decimal(str(len(winning))) / Decimal(str(total_closed))) * Decimal("100") if total_closed > 0 else Decimal("0")

        # Drawdown
        max_dd_pct, current_dd_pct = self._calculate_drawdown()

        # Sharpe ratio
        sharpe = self._calculate_sharpe()

        # Fees
        total_fees = sum(
            (p.entry_fees_usd + (p.exit_fees_usd or Decimal("0")))
            for p in self.closed_positions
        )

        # Slippage
        avg_slippage = (
            sum(o.slippage_pct for o in self.filled_orders if o.slippage_pct) / Decimal(str(len(self.filled_orders)))
            if self.filled_orders else Decimal("0")
        )

        return PaperTradingMetrics(
            start_time=self.start_time,
            end_time=datetime.now(),
            starting_capital_usd=self.starting_capital,
            current_capital_usd=self.current_capital,
            peak_capital_usd=self.peak_capital,
            total_positions=len(self.closed_positions) + len(self.open_positions),
            open_positions=len(self.open_positions),
            closed_positions=len(self.closed_positions),
            total_return_usd=total_return_usd,
            total_return_pct=total_return_pct,
            unrealized_pnl_usd=unrealized_pnl,
            realized_pnl_usd=realized_pnl,
            winning_positions=len(winning),
            losing_positions=len(losing),
            win_rate_pct=win_rate_pct,
            max_drawdown_pct=max_dd_pct,
            current_drawdown_pct=current_dd_pct,
            sharpe_ratio=sharpe,
            avg_slippage_pct=avg_slippage,
            total_fees_usd=total_fees
        )

    def _calculate_drawdown(self) -> Tuple[Decimal, Decimal]:
        """Calculate max drawdown and current drawdown"""
        if not self.equity_curve:
            return Decimal("0"), Decimal("0")

        equity_values = [float(e) for _, e in self.equity_curve]
        peak = max(equity_values)
        current = equity_values[-1]

        max_dd = max((peak - e) / peak for e in equity_values)
        current_dd = (peak - current) / peak if peak > 0 else 0

        return Decimal(str(max_dd * 100)), Decimal(str(current_dd * 100))

    def _calculate_sharpe(self) -> Decimal:
        """Calculate Sharpe ratio"""
        if not self.daily_pnl:
            return Decimal("0")

        import numpy as np
        daily_returns = [(pnl / self.starting_capital) * Decimal("100") for pnl in self.daily_pnl.values()]

        if len(daily_returns) < 2:
            return Decimal("0")

        returns_array = [float(r) for r in daily_returns]
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array)

        sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        return Decimal(str(sharpe))

    def _print_metrics(self, metrics: PaperTradingMetrics):
        """Print formatted metrics"""
        print(f"\n{'='*80}")
        print(f"PAPER TRADING METRICS")
        print(f"{'='*80}")
        print(f"Period: {metrics.start_time.strftime('%Y-%m-%d %H:%M')} to {metrics.end_time.strftime('%Y-%m-%d %H:%M')}")
        print()

        print(f"Capital: ${float(metrics.current_capital_usd):,.2f} (started with ${float(metrics.starting_capital_usd):,.2f})")
        print(f"Return: {float(metrics.total_return_pct):+.2f}% (${float(metrics.total_return_usd):+,.2f})")
        print(f"Peak Capital: ${float(metrics.peak_capital_usd):,.2f}")
        print()

        print(f"Positions: {metrics.total_positions} total | {metrics.open_positions} open | {metrics.closed_positions} closed")
        print(f"Win Rate: {float(metrics.win_rate_pct):.1f}% ({metrics.winning_positions}W / {metrics.losing_positions}L)")
        print()

        print(f"P&L: Realized ${float(metrics.realized_pnl_usd):+,.2f} | Unrealized ${float(metrics.unrealized_pnl_usd):+,.2f}")
        print(f"Risk: Max DD {float(metrics.max_drawdown_pct):.2f}% | Current DD {float(metrics.current_drawdown_pct):.2f}%")
        print(f"Sharpe Ratio: {float(metrics.sharpe_ratio):.2f}")
        print()

        print(f"Execution: Avg Slippage {float(metrics.avg_slippage_pct):.2f}% | Total Fees ${float(metrics.total_fees_usd):.2f}")
        print(f"{'='*80}\n")


# ==================== Example Usage ====================

async def main():
    """Example usage of PaperTradingEngine"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== Paper Trading Engine Test ===\n")

    # Initialize engine
    engine = PaperTradingEngine()

    # Start paper trading
    await engine.start()

    # Simulate some trades
    print("Simulating 5 paper trades...\n")

    for i in range(5):
        await engine.place_order(
            market_id=f"market_{i % 2}",
            outcome="YES",
            side="BUY",
            size_usd=Decimal("1000")
        )
        await asyncio.sleep(2)

    # Let it run for a bit
    await asyncio.sleep(10)

    # Stop paper trading
    await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
