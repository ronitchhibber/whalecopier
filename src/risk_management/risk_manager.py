"""
Risk Management System - Comprehensive risk controls for copy trading engine.

Features:
- Circuit breakers (halt on excessive losses)
- Stop-loss/take-profit automation
- Position limits and exposure management
- Drawdown protection
- Emergency shutdown mechanisms
- Real-time risk monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Trading halted
    COOLDOWN = "cooldown"  # Partial recovery


class RiskEventType(Enum):
    """Types of risk events"""
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    WHALE_LOSS_STREAK = "whale_loss_streak"
    MARKET_VOLATILITY = "market_volatility"
    SYSTEM_ERROR = "system_error"


@dataclass
class RiskManagerConfig:
    """Configuration for risk management system"""

    # Daily loss limits
    max_daily_loss_usd: Decimal = Decimal("1000")
    max_daily_loss_percent: Decimal = Decimal("5")  # % of portfolio

    # Drawdown limits
    max_drawdown_percent: Decimal = Decimal("15")
    max_consecutive_losses: int = 5

    # Position limits
    max_total_positions: int = 10
    max_positions_per_whale: int = 3
    max_positions_per_market: int = 2
    max_position_size_usd: Decimal = Decimal("500")
    max_total_exposure_usd: Decimal = Decimal("5000")

    # Stop-loss/take-profit
    default_stop_loss_percent: Decimal = Decimal("10")
    default_take_profit_percent: Decimal = Decimal("25")
    trailing_stop_enabled: bool = True
    trailing_stop_percent: Decimal = Decimal("5")

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_cooldown_minutes: int = 60
    circuit_breaker_loss_threshold_usd: Decimal = Decimal("500")
    circuit_breaker_loss_threshold_percent: Decimal = Decimal("3")

    # Whale-specific limits
    max_whale_daily_allocation_usd: Decimal = Decimal("1000")
    whale_loss_streak_limit: int = 3

    # Emergency shutdown
    emergency_shutdown_loss_percent: Decimal = Decimal("20")
    emergency_shutdown_enabled: bool = True

    # Monitoring
    check_interval_seconds: int = 30
    alert_cooldown_minutes: int = 15


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # P&L metrics
    daily_pnl_usd: Decimal = Decimal("0")
    daily_pnl_percent: Decimal = Decimal("0")
    total_pnl_usd: Decimal = Decimal("0")

    # Drawdown metrics
    peak_equity: Decimal = Decimal("0")
    current_equity: Decimal = Decimal("0")
    drawdown_usd: Decimal = Decimal("0")
    drawdown_percent: Decimal = Decimal("0")
    consecutive_losses: int = 0

    # Position metrics
    total_positions: int = 0
    total_exposure_usd: Decimal = Decimal("0")
    positions_per_whale: Dict[str, int] = field(default_factory=dict)
    positions_per_market: Dict[str, int] = field(default_factory=dict)

    # Risk level
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class RiskEvent:
    """Risk event notification"""
    timestamp: datetime
    event_type: RiskEventType
    risk_level: RiskLevel
    message: str
    metrics: Dict
    action_taken: Optional[str] = None


@dataclass
class Position:
    """Trading position for risk tracking"""
    position_id: str
    whale_address: str
    market_id: str
    entry_price: Decimal
    current_price: Decimal
    size: Decimal
    side: str  # BUY or SELL
    entry_time: datetime
    pnl_usd: Decimal = Decimal("0")
    pnl_percent: Decimal = Decimal("0")
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    trailing_stop_price: Optional[Decimal] = None
    is_open: bool = True


class CircuitBreaker:
    """Circuit breaker to halt trading on excessive losses"""

    def __init__(self, config: RiskManagerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.trip_time: Optional[datetime] = None
        self.cooldown_end: Optional[datetime] = None
        self.trip_count = 0

    def check(self, metrics: RiskMetrics) -> Tuple[bool, Optional[str]]:
        """
        Check if circuit breaker should trip.
        Returns (should_halt, reason)
        """

        if not self.config.circuit_breaker_enabled:
            return False, None

        # Check if in cooldown
        if self.state == CircuitBreakerState.COOLDOWN:
            if datetime.utcnow() < self.cooldown_end:
                return True, f"Circuit breaker in cooldown until {self.cooldown_end.strftime('%H:%M:%S')}"
            else:
                self.state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker cooldown ended - resuming normal operation")

        # Check if already tripped
        if self.state == CircuitBreakerState.OPEN:
            return True, "Circuit breaker is open - trading halted"

        # Check loss thresholds
        loss_usd_exceeded = metrics.daily_pnl_usd < -self.config.circuit_breaker_loss_threshold_usd
        loss_pct_exceeded = metrics.daily_pnl_percent < -self.config.circuit_breaker_loss_threshold_percent

        if loss_usd_exceeded or loss_pct_exceeded:
            self.trip()
            reason = f"Circuit breaker tripped: Loss ${abs(metrics.daily_pnl_usd):.2f} ({abs(metrics.daily_pnl_percent):.2f}%)"
            return True, reason

        return False, None

    def trip(self):
        """Trip the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.trip_time = datetime.utcnow()
        self.trip_count += 1
        logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED (#{self.trip_count})")

    def reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.trip_time = None
        self.cooldown_end = None
        logger.info("Circuit breaker manually reset")

    def start_cooldown(self):
        """Start cooldown period"""
        self.state = CircuitBreakerState.COOLDOWN
        self.cooldown_end = datetime.utcnow() + timedelta(minutes=self.config.circuit_breaker_cooldown_minutes)
        logger.info(f"Circuit breaker entering cooldown until {self.cooldown_end.strftime('%H:%M:%S')}")


class StopLossManager:
    """Manages stop-loss and take-profit orders"""

    def __init__(self, config: RiskManagerConfig):
        self.config = config
        self.positions: Dict[str, Position] = {}

    def add_position(self, position: Position):
        """Add a position for monitoring"""

        # Set default stop-loss if not specified
        if position.stop_loss_price is None:
            if position.side == "BUY":
                sl_price = position.entry_price * (Decimal("1") - self.config.default_stop_loss_percent / Decimal("100"))
            else:
                sl_price = position.entry_price * (Decimal("1") + self.config.default_stop_loss_percent / Decimal("100"))
            position.stop_loss_price = sl_price

        # Set default take-profit if not specified
        if position.take_profit_price is None:
            if position.side == "BUY":
                tp_price = position.entry_price * (Decimal("1") + self.config.default_take_profit_percent / Decimal("100"))
            else:
                tp_price = position.entry_price * (Decimal("1") - self.config.default_take_profit_percent / Decimal("100"))
            position.take_profit_price = tp_price

        # Set trailing stop if enabled
        if self.config.trailing_stop_enabled:
            if position.side == "BUY":
                trailing_price = position.current_price * (Decimal("1") - self.config.trailing_stop_percent / Decimal("100"))
            else:
                trailing_price = position.current_price * (Decimal("1") + self.config.trailing_stop_percent / Decimal("100"))
            position.trailing_stop_price = trailing_price

        self.positions[position.position_id] = position
        logger.info(f"Added position {position.position_id} - SL: ${position.stop_loss_price:.3f}, TP: ${position.take_profit_price:.3f}")

    def update_position(self, position_id: str, current_price: Decimal) -> Optional[str]:
        """
        Update position price and check stop-loss/take-profit.
        Returns action to take: 'stop_loss', 'take_profit', 'trailing_stop', or None
        """

        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        position.current_price = current_price

        # Calculate P&L
        if position.side == "BUY":
            position.pnl_usd = (current_price - position.entry_price) * position.size
            position.pnl_percent = ((current_price - position.entry_price) / position.entry_price) * Decimal("100")
        else:
            position.pnl_usd = (position.entry_price - current_price) * position.size
            position.pnl_percent = ((position.entry_price - current_price) / position.entry_price) * Decimal("100")

        # Check stop-loss
        if position.side == "BUY" and current_price <= position.stop_loss_price:
            logger.warning(f"Stop-loss triggered for {position_id}: ${current_price:.3f} <= ${position.stop_loss_price:.3f}")
            return "stop_loss"
        elif position.side == "SELL" and current_price >= position.stop_loss_price:
            logger.warning(f"Stop-loss triggered for {position_id}: ${current_price:.3f} >= ${position.stop_loss_price:.3f}")
            return "stop_loss"

        # Check take-profit
        if position.side == "BUY" and current_price >= position.take_profit_price:
            logger.info(f"Take-profit triggered for {position_id}: ${current_price:.3f} >= ${position.take_profit_price:.3f}")
            return "take_profit"
        elif position.side == "SELL" and current_price <= position.take_profit_price:
            logger.info(f"Take-profit triggered for {position_id}: ${current_price:.3f} <= ${position.take_profit_price:.3f}")
            return "take_profit"

        # Update trailing stop
        if self.config.trailing_stop_enabled and position.trailing_stop_price:
            if position.side == "BUY":
                # Update trailing stop if price moved up
                new_trailing = current_price * (Decimal("1") - self.config.trailing_stop_percent / Decimal("100"))
                if new_trailing > position.trailing_stop_price:
                    position.trailing_stop_price = new_trailing

                # Check if trailing stop hit
                if current_price <= position.trailing_stop_price:
                    logger.info(f"Trailing stop triggered for {position_id}: ${current_price:.3f} <= ${position.trailing_stop_price:.3f}")
                    return "trailing_stop"
            else:
                # Update trailing stop if price moved down
                new_trailing = current_price * (Decimal("1") + self.config.trailing_stop_percent / Decimal("100"))
                if new_trailing < position.trailing_stop_price:
                    position.trailing_stop_price = new_trailing

                # Check if trailing stop hit
                if current_price >= position.trailing_stop_price:
                    logger.info(f"Trailing stop triggered for {position_id}: ${current_price:.3f} >= ${position.trailing_stop_price:.3f}")
                    return "trailing_stop"

        return None

    def close_position(self, position_id: str):
        """Mark position as closed"""
        if position_id in self.positions:
            self.positions[position_id].is_open = False
            logger.info(f"Position {position_id} closed")

    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p.is_open]


class DrawdownProtector:
    """Protects against excessive drawdowns"""

    def __init__(self, config: RiskManagerConfig):
        self.config = config
        self.peak_equity = Decimal("0")
        self.consecutive_losses = 0
        self.last_trade_win = False

    def update(self, current_equity: Decimal, trade_won: Optional[bool] = None) -> Tuple[bool, Optional[str]]:
        """
        Update drawdown metrics and check limits.
        Returns (should_halt, reason)
        """

        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.consecutive_losses = 0  # Reset on new peak

        # Calculate drawdown
        if self.peak_equity > 0:
            drawdown_usd = self.peak_equity - current_equity
            drawdown_percent = (drawdown_usd / self.peak_equity) * Decimal("100")
        else:
            drawdown_usd = Decimal("0")
            drawdown_percent = Decimal("0")

        # Track consecutive losses
        if trade_won is not None:
            if not trade_won:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

        # Check drawdown limit
        if drawdown_percent >= self.config.max_drawdown_percent:
            reason = f"Max drawdown exceeded: {drawdown_percent:.2f}% (limit: {self.config.max_drawdown_percent}%)"
            return True, reason

        # Check consecutive losses
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            reason = f"Max consecutive losses: {self.consecutive_losses} (limit: {self.config.max_consecutive_losses})"
            return True, reason

        # Check emergency shutdown
        if self.config.emergency_shutdown_enabled:
            if drawdown_percent >= self.config.emergency_shutdown_loss_percent:
                reason = f"🚨 EMERGENCY SHUTDOWN: Drawdown {drawdown_percent:.2f}% >= {self.config.emergency_shutdown_loss_percent}%"
                logger.critical(reason)
                return True, reason

        return False, None


class PositionLimitManager:
    """Manages position and exposure limits"""

    def __init__(self, config: RiskManagerConfig):
        self.config = config
        self.positions_per_whale: Dict[str, int] = {}
        self.positions_per_market: Dict[str, int] = {}
        self.total_positions = 0
        self.total_exposure_usd = Decimal("0")
        self.whale_daily_allocation: Dict[str, Decimal] = {}

    def can_open_position(
        self,
        whale_address: str,
        market_id: str,
        position_size_usd: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a new position can be opened.
        Returns (can_open, reason_if_not)
        """

        # Check total positions
        if self.total_positions >= self.config.max_total_positions:
            return False, f"Max total positions reached ({self.total_positions}/{self.config.max_total_positions})"

        # Check position size
        if position_size_usd > self.config.max_position_size_usd:
            return False, f"Position size ${position_size_usd:.2f} exceeds limit ${self.config.max_position_size_usd}"

        # Check total exposure
        if self.total_exposure_usd + position_size_usd > self.config.max_total_exposure_usd:
            return False, f"Total exposure would exceed limit: ${self.total_exposure_usd + position_size_usd:.2f} > ${self.config.max_total_exposure_usd}"

        # Check positions per whale
        whale_positions = self.positions_per_whale.get(whale_address, 0)
        if whale_positions >= self.config.max_positions_per_whale:
            return False, f"Max positions per whale reached for {whale_address[:10]} ({whale_positions}/{self.config.max_positions_per_whale})"

        # Check positions per market
        market_positions = self.positions_per_market.get(market_id, 0)
        if market_positions >= self.config.max_positions_per_market:
            return False, f"Max positions per market reached for {market_id[:10]} ({market_positions}/{self.config.max_positions_per_market})"

        # Check whale daily allocation
        whale_allocation = self.whale_daily_allocation.get(whale_address, Decimal("0"))
        if whale_allocation + position_size_usd > self.config.max_whale_daily_allocation_usd:
            return False, f"Whale daily allocation exceeded: ${whale_allocation + position_size_usd:.2f} > ${self.config.max_whale_daily_allocation_usd}"

        return True, None

    def register_position(self, whale_address: str, market_id: str, position_size_usd: Decimal):
        """Register a new position"""
        self.total_positions += 1
        self.total_exposure_usd += position_size_usd
        self.positions_per_whale[whale_address] = self.positions_per_whale.get(whale_address, 0) + 1
        self.positions_per_market[market_id] = self.positions_per_market.get(market_id, 0) + 1
        self.whale_daily_allocation[whale_address] = self.whale_daily_allocation.get(whale_address, Decimal("0")) + position_size_usd

    def unregister_position(self, whale_address: str, market_id: str, position_size_usd: Decimal):
        """Unregister a closed position"""
        self.total_positions = max(0, self.total_positions - 1)
        self.total_exposure_usd = max(Decimal("0"), self.total_exposure_usd - position_size_usd)

        if whale_address in self.positions_per_whale:
            self.positions_per_whale[whale_address] = max(0, self.positions_per_whale[whale_address] - 1)

        if market_id in self.positions_per_market:
            self.positions_per_market[market_id] = max(0, self.positions_per_market[market_id] - 1)

    def reset_daily_allocations(self):
        """Reset daily allocation counters (call at start of each day)"""
        self.whale_daily_allocation.clear()
        logger.info("Daily whale allocations reset")


class RiskManager:
    """Main risk management system"""

    def __init__(self, config: Optional[RiskManagerConfig] = None):
        self.config = config or RiskManagerConfig()

        # Components
        self.circuit_breaker = CircuitBreaker(self.config)
        self.stop_loss_manager = StopLossManager(self.config)
        self.drawdown_protector = DrawdownProtector(self.config)
        self.position_limit_manager = PositionLimitManager(self.config)

        # State
        self.risk_events: List[RiskEvent] = []
        self.current_metrics = RiskMetrics()
        self.is_trading_halted = False
        self.last_alert_time: Dict[str, datetime] = {}

        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self):
        """Start risk monitoring"""
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("✅ Risk Manager started")

    async def stop(self):
        """Stop risk monitoring"""
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Risk Manager stopped")

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                await self._check_all_risks()
                await asyncio.sleep(self.config.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _check_all_risks(self):
        """Check all risk conditions"""

        # Check circuit breaker
        should_halt, reason = self.circuit_breaker.check(self.current_metrics)
        if should_halt and not self.is_trading_halted:
            self.halt_trading(reason)

        # Check drawdown
        should_halt, reason = self.drawdown_protector.update(self.current_metrics.current_equity)
        if should_halt and not self.is_trading_halted:
            self.halt_trading(reason)

        # Update risk level
        self._update_risk_level()

    def can_open_trade(
        self,
        whale_address: str,
        market_id: str,
        position_size_usd: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade can be opened.
        Returns (can_trade, reason_if_not)
        """

        # Check if trading is halted
        if self.is_trading_halted:
            return False, "Trading is currently halted by risk manager"

        # Check circuit breaker
        should_halt, reason = self.circuit_breaker.check(self.current_metrics)
        if should_halt:
            self.halt_trading(reason)
            return False, reason

        # Check position limits
        can_open, reason = self.position_limit_manager.can_open_position(
            whale_address, market_id, position_size_usd
        )
        if not can_open:
            return False, reason

        return True, None

    def register_trade(self, position: Position):
        """Register a new trade"""

        # Add to stop-loss manager
        self.stop_loss_manager.add_position(position)

        # Register with position limit manager
        position_size_usd = position.entry_price * position.size
        self.position_limit_manager.register_position(
            position.whale_address,
            position.market_id,
            position_size_usd
        )

        # Update metrics
        self.current_metrics.total_positions = self.position_limit_manager.total_positions
        self.current_metrics.total_exposure_usd = self.position_limit_manager.total_exposure_usd

        logger.info(f"Trade registered: {position.position_id} - ${position_size_usd:.2f}")

    def update_position_prices(self, position_id: str, current_price: Decimal) -> Optional[str]:
        """
        Update position price and check for stop-loss/take-profit triggers.
        Returns action to take if any.
        """
        return self.stop_loss_manager.update_position(position_id, current_price)

    def close_trade(self, position_id: str, pnl_usd: Decimal, trade_won: bool):
        """Close a trade"""

        # Get position details
        position = self.stop_loss_manager.positions.get(position_id)
        if not position:
            return

        # Close in stop-loss manager
        self.stop_loss_manager.close_position(position_id)

        # Unregister from position limit manager
        position_size_usd = position.entry_price * position.size
        self.position_limit_manager.unregister_position(
            position.whale_address,
            position.market_id,
            position_size_usd
        )

        # Update metrics
        self.current_metrics.daily_pnl_usd += pnl_usd
        self.current_metrics.total_pnl_usd += pnl_usd
        self.current_metrics.total_positions = self.position_limit_manager.total_positions
        self.current_metrics.total_exposure_usd = self.position_limit_manager.total_exposure_usd

        # Update drawdown protector
        self.drawdown_protector.update(self.current_metrics.current_equity, trade_won)

        logger.info(f"Trade closed: {position_id} - P&L: ${pnl_usd:.2f}")

    def update_equity(self, current_equity: Decimal):
        """Update current equity"""
        self.current_metrics.current_equity = current_equity

        if current_equity > self.current_metrics.peak_equity:
            self.current_metrics.peak_equity = current_equity

        # Calculate drawdown
        if self.current_metrics.peak_equity > 0:
            self.current_metrics.drawdown_usd = self.current_metrics.peak_equity - current_equity
            self.current_metrics.drawdown_percent = (
                self.current_metrics.drawdown_usd / self.current_metrics.peak_equity
            ) * Decimal("100")

    def halt_trading(self, reason: str):
        """Halt all trading"""
        self.is_trading_halted = True

        event = RiskEvent(
            timestamp=datetime.utcnow(),
            event_type=RiskEventType.DAILY_LOSS_LIMIT,
            risk_level=RiskLevel.CRITICAL,
            message=reason,
            metrics=self._metrics_to_dict(),
            action_taken="TRADING_HALTED"
        )

        self.risk_events.append(event)
        logger.critical(f"🚨 TRADING HALTED: {reason}")

    def resume_trading(self):
        """Resume trading after manual review"""
        self.is_trading_halted = False
        self.circuit_breaker.reset()
        logger.info("✅ Trading resumed")

    def _update_risk_level(self):
        """Update current risk level"""

        metrics = self.current_metrics

        # Critical risk conditions
        if (metrics.drawdown_percent >= self.config.max_drawdown_percent * Decimal("0.8") or
            metrics.daily_pnl_percent <= -self.config.max_daily_loss_percent * Decimal("0.8")):
            self.current_metrics.risk_level = RiskLevel.CRITICAL

        # High risk conditions
        elif (metrics.drawdown_percent >= self.config.max_drawdown_percent * Decimal("0.6") or
              metrics.daily_pnl_percent <= -self.config.max_daily_loss_percent * Decimal("0.6")):
            self.current_metrics.risk_level = RiskLevel.HIGH

        # Medium risk conditions
        elif (metrics.drawdown_percent >= self.config.max_drawdown_percent * Decimal("0.4") or
              metrics.daily_pnl_percent <= -self.config.max_daily_loss_percent * Decimal("0.4")):
            self.current_metrics.risk_level = RiskLevel.MEDIUM

        # Low risk
        else:
            self.current_metrics.risk_level = RiskLevel.LOW

    def _metrics_to_dict(self) -> Dict:
        """Convert metrics to dictionary"""
        return {
            "daily_pnl_usd": float(self.current_metrics.daily_pnl_usd),
            "daily_pnl_percent": float(self.current_metrics.daily_pnl_percent),
            "drawdown_percent": float(self.current_metrics.drawdown_percent),
            "total_positions": self.current_metrics.total_positions,
            "total_exposure_usd": float(self.current_metrics.total_exposure_usd),
            "risk_level": self.current_metrics.risk_level.value
        }

    def get_status(self) -> Dict:
        """Get current risk manager status"""
        return {
            "is_trading_halted": self.is_trading_halted,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "risk_level": self.current_metrics.risk_level.value,
            "metrics": self._metrics_to_dict(),
            "open_positions": len(self.stop_loss_manager.get_open_positions()),
            "recent_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type.value,
                    "risk_level": e.risk_level.value,
                    "message": e.message,
                    "action": e.action_taken
                }
                for e in self.risk_events[-10:]  # Last 10 events
            ]
        }
