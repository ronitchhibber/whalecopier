"""
Enhanced Risk Management System for Week 2
Implements production-ready circuit breakers and comprehensive risk controls
Features:
- Multi-tier circuit breakers (HALT, REDUCE, PAUSE)
- Per-position, per-market, per-whale limits
- Balance verification before trades
- Stale trade filtering
- Real-time risk monitoring
- Consecutive loss tracking
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class CircuitBreakerLevel(Enum):
    """Circuit breaker severity levels"""
    NORMAL = "normal"  # Trading allowed
    PAUSE = "pause"    # Temporary pause (1 hour)
    REDUCE = "reduce"  # Reduced position sizes (50%)
    HALT = "halt"      # Complete trading halt


class RiskLevel(Enum):
    """Overall risk assessment"""
    SAFE = "safe"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CircuitBreakerState:
    """Current circuit breaker state"""
    level: CircuitBreakerLevel
    reason: str
    triggered_at: datetime
    reset_at: Optional[datetime] = None
    consecutive_losses: int = 0
    daily_loss: Decimal = Decimal("0")
    current_drawdown: Decimal = Decimal("0")


@dataclass
class RiskLimits:
    """Comprehensive risk limits"""
    # Position limits (absolute dollar amounts)
    max_position_size: Decimal = Decimal("1000")  # $1,000 per position
    max_market_exposure: Decimal = Decimal("5000")  # $5,000 per market
    max_whale_allocation: Decimal = Decimal("10000")  # $10,000 per whale
    max_portfolio_exposure: Decimal = Decimal("20000")  # Total exposure

    # Percentage limits
    max_position_pct: Decimal = Decimal("0.05")  # 5% per position
    max_market_pct: Decimal = Decimal("0.20")  # 20% per market
    max_whale_pct: Decimal = Decimal("0.30")  # 30% per whale

    # Circuit breaker thresholds
    daily_loss_limit: Decimal = Decimal("500")  # $500 daily loss → HALT
    max_drawdown_threshold: Decimal = Decimal("0.10")  # 10% → REDUCE
    consecutive_loss_limit: int = 5  # 5 losses → PAUSE

    # Trade age filtering
    max_trade_age_seconds: int = 3600  # 1 hour (stale trade filter)

    # Balance requirements
    min_balance_required: Decimal = Decimal("100")  # Minimum USDC balance


@dataclass
class TradeDecision:
    """Result of risk check for a proposed trade"""
    allowed: bool
    reason: str
    adjusted_size: Optional[Decimal] = None  # Suggested size if reduced
    circuit_breaker_level: CircuitBreakerLevel = CircuitBreakerLevel.NORMAL


@dataclass
class RiskMetrics:
    """Current portfolio risk metrics"""
    total_exposure: Decimal
    largest_position: Decimal
    position_count: int
    whale_exposures: Dict[str, Decimal]
    market_exposures: Dict[str, Decimal]
    daily_pnl: Decimal
    current_drawdown: Decimal
    consecutive_losses: int
    win_rate: float
    sharpe_ratio: float
    var_95: Decimal
    risk_level: RiskLevel


class EnhancedRiskManager:
    """
    Production-ready risk management system with comprehensive controls
    Target: <100ms risk check time, zero false negatives on limit violations
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.limits = self._initialize_limits()

        # Circuit breaker state
        self.circuit_breaker = CircuitBreakerState(
            level=CircuitBreakerLevel.NORMAL,
            reason="System initialized",
            triggered_at=datetime.now()
        )

        # Position tracking
        self.positions: Dict[str, Dict] = {}  # position_id -> position_data
        self.whale_exposures: Dict[str, Decimal] = {}  # whale_addr -> total_exposure
        self.market_exposures: Dict[str, Decimal] = {}  # market_id -> total_exposure

        # Trade history tracking
        self.trade_history: deque = deque(maxlen=1000)  # Last 1000 trades
        self.daily_trades: List[Dict] = []  # Trades today
        self.consecutive_losses = 0

        # Balance tracking
        self.current_balance: Decimal = Decimal("0")
        self.daily_start_balance: Decimal = Decimal("0")
        self.peak_balance: Decimal = Decimal("0")

        # Statistics
        self.stats = {
            "trades_approved": 0,
            "trades_rejected": 0,
            "circuit_breakers_triggered": 0,
            "total_risk_checks": 0
        }

    def _initialize_limits(self) -> RiskLimits:
        """Initialize risk limits from config or defaults"""
        return RiskLimits(
            max_position_size=Decimal(str(self.config.get("max_position_size", "1000"))),
            max_market_exposure=Decimal(str(self.config.get("max_market_exposure", "5000"))),
            max_whale_allocation=Decimal(str(self.config.get("max_whale_allocation", "10000"))),
            max_portfolio_exposure=Decimal(str(self.config.get("max_portfolio_exposure", "20000"))),
            daily_loss_limit=Decimal(str(self.config.get("daily_loss_limit", "500"))),
            max_drawdown_threshold=Decimal(str(self.config.get("max_drawdown_threshold", "0.10"))),
            consecutive_loss_limit=self.config.get("consecutive_loss_limit", 5),
            max_trade_age_seconds=self.config.get("max_trade_age_seconds", 3600),
            min_balance_required=Decimal(str(self.config.get("min_balance_required", "100")))
        )

    async def check_trade(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal,
        whale_address: Optional[str] = None,
        trade_timestamp: Optional[datetime] = None,
        balance: Optional[Decimal] = None
    ) -> TradeDecision:
        """
        Comprehensive trade risk check
        Returns TradeDecision with allowed flag and reasoning
        """
        self.stats["total_risk_checks"] += 1

        # 1. Check stale trade filter
        if trade_timestamp:
            trade_age = (datetime.now() - trade_timestamp).total_seconds()
            if trade_age > self.limits.max_trade_age_seconds:
                logger.warning(f"Rejecting stale trade: {trade_age}s old")
                self.stats["trades_rejected"] += 1
                return TradeDecision(
                    allowed=False,
                    reason=f"Trade is stale ({trade_age:.0f}s old, max {self.limits.max_trade_age_seconds}s)",
                    circuit_breaker_level=self.circuit_breaker.level
                )

        # 2. Check balance (if provided)
        if balance is not None:
            self.current_balance = balance
            trade_value = size * price

            if balance < self.limits.min_balance_required:
                logger.error(f"Insufficient balance: ${float(balance):.2f}")
                self.stats["trades_rejected"] += 1
                return TradeDecision(
                    allowed=False,
                    reason=f"Insufficient balance (${float(balance):.2f} < ${float(self.limits.min_balance_required):.2f})",
                    circuit_breaker_level=self.circuit_breaker.level
                )

            if trade_value > balance:
                logger.warning(f"Trade value ${float(trade_value):.2f} exceeds balance ${float(balance):.2f}")
                self.stats["trades_rejected"] += 1
                return TradeDecision(
                    allowed=False,
                    reason=f"Trade value (${float(trade_value):.2f}) exceeds available balance",
                    circuit_breaker_level=self.circuit_breaker.level
                )

        # 3. Check circuit breaker level
        if self.circuit_breaker.level == CircuitBreakerLevel.HALT:
            logger.warning("Trade rejected: Circuit breaker HALT active")
            self.stats["trades_rejected"] += 1
            return TradeDecision(
                allowed=False,
                reason=f"Circuit breaker HALT: {self.circuit_breaker.reason}",
                circuit_breaker_level=CircuitBreakerLevel.HALT
            )

        if self.circuit_breaker.level == CircuitBreakerLevel.PAUSE:
            # Check if pause period has expired
            if datetime.now() < self.circuit_breaker.reset_at:
                remaining = (self.circuit_breaker.reset_at - datetime.now()).total_seconds()
                logger.warning(f"Trade rejected: Circuit breaker PAUSE active ({remaining:.0f}s remaining)")
                self.stats["trades_rejected"] += 1
                return TradeDecision(
                    allowed=False,
                    reason=f"Circuit breaker PAUSE: {self.circuit_breaker.reason} ({remaining:.0f}s remaining)",
                    circuit_breaker_level=CircuitBreakerLevel.PAUSE
                )
            else:
                # Reset from PAUSE
                self._reset_circuit_breaker()

        # 4. Calculate trade value
        trade_value = size * price

        # 5. Check position size limit
        if trade_value > self.limits.max_position_size:
            # If REDUCE mode, suggest 50% size
            if self.circuit_breaker.level == CircuitBreakerLevel.REDUCE:
                adjusted_size = size * Decimal("0.5")
                adjusted_value = adjusted_size * price

                if adjusted_value <= self.limits.max_position_size:
                    logger.info(f"Reducing position size by 50%: ${float(trade_value):.2f} → ${float(adjusted_value):.2f}")
                    self.stats["trades_approved"] += 1
                    return TradeDecision(
                        allowed=True,
                        reason="Position size reduced by 50% (REDUCE mode)",
                        adjusted_size=adjusted_size,
                        circuit_breaker_level=CircuitBreakerLevel.REDUCE
                    )

            logger.warning(f"Position size ${float(trade_value):.2f} exceeds limit ${float(self.limits.max_position_size):.2f}")
            self.stats["trades_rejected"] += 1
            return TradeDecision(
                allowed=False,
                reason=f"Position size (${float(trade_value):.2f}) exceeds limit (${float(self.limits.max_position_size):.2f})",
                circuit_breaker_level=self.circuit_breaker.level
            )

        # 6. Check market exposure limit
        current_market_exposure = self.market_exposures.get(market_id, Decimal("0"))
        new_market_exposure = current_market_exposure + trade_value

        if new_market_exposure > self.limits.max_market_exposure:
            logger.warning(f"Market exposure ${float(new_market_exposure):.2f} exceeds limit ${float(self.limits.max_market_exposure):.2f}")
            self.stats["trades_rejected"] += 1
            return TradeDecision(
                allowed=False,
                reason=f"Market exposure (${float(new_market_exposure):.2f}) exceeds limit (${float(self.limits.max_market_exposure):.2f})",
                circuit_breaker_level=self.circuit_breaker.level
            )

        # 7. Check whale allocation limit (if whale specified)
        if whale_address:
            current_whale_exposure = self.whale_exposures.get(whale_address, Decimal("0"))
            new_whale_exposure = current_whale_exposure + trade_value

            if new_whale_exposure > self.limits.max_whale_allocation:
                logger.warning(f"Whale exposure ${float(new_whale_exposure):.2f} exceeds limit ${float(self.limits.max_whale_allocation):.2f}")
                self.stats["trades_rejected"] += 1
                return TradeDecision(
                    allowed=False,
                    reason=f"Whale allocation (${float(new_whale_exposure):.2f}) exceeds limit (${float(self.limits.max_whale_allocation):.2f})",
                    circuit_breaker_level=self.circuit_breaker.level
                )

        # 8. Check total portfolio exposure
        total_exposure = sum(self.market_exposures.values()) + trade_value
        if total_exposure > self.limits.max_portfolio_exposure:
            logger.warning(f"Portfolio exposure ${float(total_exposure):.2f} exceeds limit ${float(self.limits.max_portfolio_exposure):.2f}")
            self.stats["trades_rejected"] += 1
            return TradeDecision(
                allowed=False,
                reason=f"Portfolio exposure (${float(total_exposure):.2f}) exceeds limit (${float(self.limits.max_portfolio_exposure):.2f})",
                circuit_breaker_level=self.circuit_breaker.level
            )

        # Trade approved!
        logger.info(f"✅ Trade approved: {side} ${float(trade_value):.2f} in {market_id[:8]}")
        self.stats["trades_approved"] += 1

        # Apply 50% reduction if in REDUCE mode
        adjusted_size = size * Decimal("0.5") if self.circuit_breaker.level == CircuitBreakerLevel.REDUCE else None

        return TradeDecision(
            allowed=True,
            reason="All risk checks passed",
            adjusted_size=adjusted_size,
            circuit_breaker_level=self.circuit_breaker.level
        )

    def record_trade_result(
        self,
        market_id: str,
        whale_address: Optional[str],
        trade_value: Decimal,
        pnl: Optional[Decimal] = None,
        success: bool = True
    ):
        """Record trade execution result and update risk tracking"""
        now = datetime.now()

        trade_record = {
            "timestamp": now,
            "market_id": market_id,
            "whale_address": whale_address,
            "trade_value": trade_value,
            "pnl": pnl or Decimal("0"),
            "success": success
        }

        self.trade_history.append(trade_record)

        # Track today's trades
        if now.date() == datetime.now().date():
            self.daily_trades.append(trade_record)
        else:
            # New day - reset daily tracking
            self.daily_trades = [trade_record]
            self.daily_start_balance = self.current_balance

        # Update exposures
        if success:
            self.market_exposures[market_id] = self.market_exposures.get(market_id, Decimal("0")) + trade_value

            if whale_address:
                self.whale_exposures[whale_address] = self.whale_exposures.get(whale_address, Decimal("0")) + trade_value

        # Track consecutive losses
        if pnl is not None:
            if pnl < 0:
                self.consecutive_losses += 1
                logger.info(f"Consecutive losses: {self.consecutive_losses}")

                # Check consecutive loss circuit breaker
                if self.consecutive_losses >= self.limits.consecutive_loss_limit:
                    self._trigger_circuit_breaker(
                        level=CircuitBreakerLevel.PAUSE,
                        reason=f"{self.consecutive_losses} consecutive losses",
                        duration_seconds=3600  # 1 hour pause
                    )
            else:
                # Win - reset counter
                self.consecutive_losses = 0

        # Update balance tracking
        if pnl is not None:
            self.current_balance += pnl

            # Update peak
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance

            # Calculate daily P&L
            daily_pnl = self.current_balance - self.daily_start_balance

            # Check daily loss limit (HALT circuit breaker)
            if daily_pnl < -self.limits.daily_loss_limit:
                self._trigger_circuit_breaker(
                    level=CircuitBreakerLevel.HALT,
                    reason=f"Daily loss limit exceeded: ${float(abs(daily_pnl)):.2f}",
                    duration_seconds=None  # Manual reset required
                )

            # Calculate drawdown
            if self.peak_balance > 0:
                drawdown = (self.peak_balance - self.current_balance) / self.peak_balance

                # Check drawdown (REDUCE circuit breaker)
                if drawdown > self.limits.max_drawdown_threshold:
                    if self.circuit_breaker.level != CircuitBreakerLevel.HALT:  # Don't override HALT
                        self._trigger_circuit_breaker(
                            level=CircuitBreakerLevel.REDUCE,
                            reason=f"Drawdown {float(drawdown * 100):.1f}% exceeds {float(self.limits.max_drawdown_threshold * 100):.1f}%",
                            duration_seconds=7200  # 2 hour reduce mode
                        )

    def _trigger_circuit_breaker(
        self,
        level: CircuitBreakerLevel,
        reason: str,
        duration_seconds: Optional[int] = None
    ):
        """Trigger circuit breaker at specified level"""
        logger.warning(f"🚨 Circuit Breaker {level.value.upper()}: {reason}")

        self.circuit_breaker = CircuitBreakerState(
            level=level,
            reason=reason,
            triggered_at=datetime.now(),
            reset_at=datetime.now() + timedelta(seconds=duration_seconds) if duration_seconds else None,
            consecutive_losses=self.consecutive_losses,
            daily_loss=self.current_balance - self.daily_start_balance,
            current_drawdown=(self.peak_balance - self.current_balance) / self.peak_balance if self.peak_balance > 0 else Decimal("0")
        )

        self.stats["circuit_breakers_triggered"] += 1

        # Log detailed circuit breaker info
        logger.warning(
            f"Circuit Breaker Details:\n"
            f"  Level: {level.value.upper()}\n"
            f"  Reason: {reason}\n"
            f"  Consecutive Losses: {self.consecutive_losses}\n"
            f"  Daily P&L: ${float(self.circuit_breaker.daily_loss):.2f}\n"
            f"  Drawdown: {float(self.circuit_breaker.current_drawdown * 100):.2f}%\n"
            f"  Reset At: {self.circuit_breaker.reset_at or 'MANUAL RESET REQUIRED'}"
        )

    def _reset_circuit_breaker(self):
        """Reset circuit breaker to normal"""
        logger.info(f"Circuit breaker reset from {self.circuit_breaker.level.value}")

        self.circuit_breaker = CircuitBreakerState(
            level=CircuitBreakerLevel.NORMAL,
            reason="Reset after timeout",
            triggered_at=datetime.now()
        )

    def manual_reset(self, admin_approval: bool = False):
        """Manually reset circuit breaker (requires admin approval for HALT)"""
        if self.circuit_breaker.level == CircuitBreakerLevel.HALT and not admin_approval:
            logger.error("Cannot reset HALT circuit breaker without admin approval")
            return False

        logger.info(f"Manual reset of circuit breaker from {self.circuit_breaker.level.value}")
        self._reset_circuit_breaker()

        # Also reset consecutive losses
        self.consecutive_losses = 0

        return True

    def get_risk_metrics(self) -> RiskMetrics:
        """Calculate current risk metrics"""
        total_exposure = sum(self.market_exposures.values())
        largest_position = max(self.market_exposures.values()) if self.market_exposures else Decimal("0")

        # Calculate P&L metrics
        daily_pnl = self.current_balance - self.daily_start_balance
        current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance if self.peak_balance > 0 else Decimal("0")

        # Calculate win rate
        recent_trades = list(self.trade_history)[-100:]  # Last 100 trades
        wins = sum(1 for t in recent_trades if t.get("pnl", 0) > 0)
        win_rate = wins / len(recent_trades) if recent_trades else 0.0

        # Simple Sharpe estimate
        returns = [float(t.get("pnl", 0)) for t in recent_trades]
        sharpe_ratio = (
            (sum(returns) / len(returns)) / (np.std(returns) if len(returns) > 1 else 1.0)
            if returns else 0.0
        )

        # Simple VaR estimate (95th percentile)
        import numpy as np
        var_95 = Decimal(str(abs(np.percentile(returns, 5)))) if returns else Decimal("0")

        # Assess risk level
        risk_level = self._assess_risk_level(current_drawdown, total_exposure, win_rate)

        return RiskMetrics(
            total_exposure=total_exposure,
            largest_position=largest_position,
            position_count=len(self.market_exposures),
            whale_exposures=self.whale_exposures.copy(),
            market_exposures=self.market_exposures.copy(),
            daily_pnl=daily_pnl,
            current_drawdown=current_drawdown,
            consecutive_losses=self.consecutive_losses,
            win_rate=win_rate,
            sharpe_ratio=sharpe_ratio,
            var_95=var_95,
            risk_level=risk_level
        )

    def _assess_risk_level(
        self,
        drawdown: Decimal,
        total_exposure: Decimal,
        win_rate: float
    ) -> RiskLevel:
        """Assess overall risk level"""
        score = 0

        # Drawdown score
        if drawdown > Decimal("0.15"):  # 15%+
            score += 3
        elif drawdown > Decimal("0.10"):  # 10%+
            score += 2
        elif drawdown > Decimal("0.05"):  # 5%+
            score += 1

        # Exposure score
        exposure_pct = total_exposure / self.limits.max_portfolio_exposure
        if exposure_pct > Decimal("0.9"):  # 90%+
            score += 3
        elif exposure_pct > Decimal("0.75"):  # 75%+
            score += 2
        elif exposure_pct > Decimal("0.50"):  # 50%+
            score += 1

        # Win rate score
        if win_rate < 0.40:  # < 40%
            score += 3
        elif win_rate < 0.50:  # < 50%
            score += 2
        elif win_rate < 0.55:  # < 55%
            score += 1

        # Consecutive losses
        if self.consecutive_losses >= 5:
            score += 3
        elif self.consecutive_losses >= 3:
            score += 2
        elif self.consecutive_losses >= 2:
            score += 1

        # Map score to risk level
        if score >= 9:
            return RiskLevel.CRITICAL
        elif score >= 6:
            return RiskLevel.HIGH
        elif score >= 4:
            return RiskLevel.ELEVATED
        elif score >= 2:
            return RiskLevel.NORMAL
        else:
            return RiskLevel.SAFE

    def get_dashboard_data(self) -> Dict:
        """Generate dashboard data for monitoring"""
        metrics = self.get_risk_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "circuit_breaker": {
                "level": self.circuit_breaker.level.value,
                "reason": self.circuit_breaker.reason,
                "triggered_at": self.circuit_breaker.triggered_at.isoformat(),
                "reset_at": self.circuit_breaker.reset_at.isoformat() if self.circuit_breaker.reset_at else None
            },
            "risk_metrics": {
                "total_exposure": float(metrics.total_exposure),
                "largest_position": float(metrics.largest_position),
                "position_count": metrics.position_count,
                "daily_pnl": float(metrics.daily_pnl),
                "current_drawdown": float(metrics.current_drawdown * 100),  # as percentage
                "consecutive_losses": metrics.consecutive_losses,
                "win_rate": metrics.win_rate * 100,  # as percentage
                "sharpe_ratio": metrics.sharpe_ratio,
                "var_95": float(metrics.var_95),
                "risk_level": metrics.risk_level.value
            },
            "limits": {
                "max_position_size": float(self.limits.max_position_size),
                "max_market_exposure": float(self.limits.max_market_exposure),
                "max_whale_allocation": float(self.limits.max_whale_allocation),
                "max_portfolio_exposure": float(self.limits.max_portfolio_exposure),
                "daily_loss_limit": float(self.limits.daily_loss_limit)
            },
            "exposures": {
                "markets": {k: float(v) for k, v in metrics.market_exposures.items()},
                "whales": {k: float(v) for k, v in metrics.whale_exposures.items()}
            },
            "statistics": self.stats.copy(),
            "balance": {
                "current": float(self.current_balance),
                "peak": float(self.peak_balance),
                "daily_start": float(self.daily_start_balance)
            }
        }


# Simple import numpy fallback
try:
    import numpy as np
except ImportError:
    class np:
        @staticmethod
        def std(x):
            if not x:
                return 0
            mean = sum(x) / len(x)
            return (sum((i - mean) ** 2 for i in x) / len(x)) ** 0.5

        @staticmethod
        def percentile(x, p):
            if not x:
                return 0
            sorted_x = sorted(x)
            k = (len(sorted_x) - 1) * p / 100
            f = int(k)
            c = int(k) + 1 if k < len(sorted_x) - 1 else int(k)
            return sorted_x[f] + (k - f) * (sorted_x[c] - sorted_x[f])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test the risk manager
    async def test_risk_manager():
        rm = EnhancedRiskManager()

        # Test initial balance
        rm.current_balance = Decimal("10000")
        rm.daily_start_balance = Decimal("10000")
        rm.peak_balance = Decimal("10000")

        logger.info("Testing risk manager...")

        # Test 1: Normal trade
        decision = await rm.check_trade(
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            balance=Decimal("10000")
        )
        logger.info(f"Test 1 - Normal trade: {decision.allowed} - {decision.reason}")

        # Test 2: Oversized trade
        decision = await rm.check_trade(
            market_id="market_2",
            token_id="token_2",
            side="BUY",
            size=Decimal("5000"),
            price=Decimal("0.5"),
            balance=Decimal("10000")
        )
        logger.info(f"Test 2 - Oversized trade: {decision.allowed} - {decision.reason}")

        # Test 3: Trigger consecutive losses
        for i in range(6):
            rm.record_trade_result(
                market_id=f"market_{i}",
                whale_address="0xwhale",
                trade_value=Decimal("100"),
                pnl=Decimal("-10"),
                success=True
            )

        # Test 4: Trade during PAUSE
        decision = await rm.check_trade(
            market_id="market_3",
            token_id="token_3",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            balance=Decimal("9400")  # After losses
        )
        logger.info(f"Test 4 - During PAUSE: {decision.allowed} - {decision.reason}")

        # Print dashboard
        dashboard = rm.get_dashboard_data()
        logger.info(f"Dashboard: {dashboard}")

    asyncio.run(test_risk_manager())
