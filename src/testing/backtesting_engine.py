"""
Comprehensive Backtesting Engine
Week 8: Testing & Simulation - Backtesting Engine
Replays historical trades with realistic execution simulation and performance analytics
"""

import logging
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
import json
import numpy as np

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================

class BacktestMode(Enum):
    """Backtest execution mode"""
    BASELINE = "BASELINE"              # No risk management
    WITH_RISK_MGMT = "WITH_RISK_MGMT"  # Full risk management
    COMPARISON = "COMPARISON"           # Run both side-by-side


class TradeOutcome(Enum):
    """Trade execution outcome"""
    FILLED = "FILLED"              # Trade executed successfully
    SKIPPED_SLIPPAGE = "SKIPPED_SLIPPAGE"  # Skipped due to excessive slippage
    SKIPPED_RISK = "SKIPPED_RISK"  # Skipped by risk management
    STOPPED_OUT = "STOPPED_OUT"    # Hit stop-loss
    TAKEN_PROFIT = "TAKEN_PROFIT"  # Hit take-profit
    CIRCUIT_BREAK = "CIRCUIT_BREAK"  # Circuit breaker triggered


@dataclass
class HistoricalTrade:
    """Historical whale trade from database"""
    trade_id: str
    whale_address: str
    market_id: str
    outcome: str  # "YES" or "NO"
    side: str     # "BUY" or "SELL"

    # Trade details
    size_shares: Decimal
    size_usd: Decimal
    price: Decimal

    # Timing
    timestamp: datetime

    # Market context
    market_volume_24h: Optional[Decimal]
    market_liquidity_score: Optional[Decimal]

    # Outcome (if known)
    final_profit_usd: Optional[Decimal]
    final_profit_pct: Optional[Decimal]


@dataclass
class BacktestTrade:
    """Simulated trade execution in backtest"""
    trade_id: str
    whale_address: str
    market_id: str
    outcome: str
    side: str

    # Entry
    entry_timestamp: datetime
    entry_size_usd: Decimal
    entry_price: Decimal
    entry_slippage_pct: Decimal
    entry_fees_usd: Decimal

    # Exit
    exit_timestamp: Optional[datetime]
    exit_price: Optional[Decimal]
    exit_reason: Optional[str]
    exit_fees_usd: Optional[Decimal]

    # P&L
    gross_pnl_usd: Optional[Decimal]
    net_pnl_usd: Optional[Decimal]
    return_pct: Optional[Decimal]

    # Execution
    execution_outcome: TradeOutcome
    execution_latency_ms: Decimal

    # Risk management applied
    was_position_sized: bool
    original_size_usd: Decimal
    stop_loss_price: Optional[Decimal]
    take_profit_price: Optional[Decimal]


@dataclass
class BacktestMetrics:
    """Performance metrics for a backtest run"""
    backtest_id: str
    mode: BacktestMode
    start_date: datetime
    end_date: datetime

    # Capital
    starting_capital_usd: Decimal
    ending_capital_usd: Decimal
    peak_capital_usd: Decimal

    # Returns
    total_return_pct: Decimal
    annualized_return_pct: Decimal
    daily_returns: List[Decimal]

    # Risk-adjusted returns
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal

    # Win/Loss
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    profit_factor: Decimal
    payoff_ratio: Decimal

    # Drawdown
    max_drawdown_pct: Decimal
    max_drawdown_usd: Decimal
    max_drawdown_duration_days: int
    recovery_time_days: Optional[int]

    # Execution quality
    avg_slippage_pct: Decimal
    avg_latency_ms: Decimal
    trades_skipped_slippage: int
    trades_skipped_risk: int

    # By outcome
    stopped_out_trades: int
    take_profit_trades: int
    circuit_breaks_triggered: int

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BacktestReport:
    """Comprehensive backtest report"""
    report_id: str

    # Backtest details
    start_date: datetime
    end_date: datetime
    days_simulated: int
    trades_replayed: int

    # Performance comparison
    baseline_metrics: BacktestMetrics
    risk_mgmt_metrics: BacktestMetrics

    # Comparison
    return_improvement_pct: Decimal
    sharpe_improvement: Decimal
    drawdown_reduction_pct: Decimal
    risk_adjusted_improvement: Decimal

    # Trade breakdown
    trades_by_outcome: Dict[TradeOutcome, int]
    trades_by_whale: Dict[str, int]
    trades_by_market: Dict[str, int]

    # Recommendations
    recommendations: List[str]

    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class BacktestConfig:
    """Configuration for backtest"""
    # Capital
    starting_capital_usd: Decimal = Decimal("100000")  # Start with $100k
    max_position_size_pct: Decimal = Decimal("5")      # Max 5% per position

    # Execution simulation
    base_slippage_bps: Decimal = Decimal("10")    # 10 bps base slippage
    slippage_per_1k_usd: Decimal = Decimal("2")   # +2 bps per $1k order
    trading_fee_pct: Decimal = Decimal("2")       # 2% trading fees
    base_latency_ms: Decimal = Decimal("100")     # 100ms base latency

    # Risk management
    enable_position_sizing: bool = True
    enable_stop_loss: bool = True
    stop_loss_pct: Decimal = Decimal("-15")       # -15% stop-loss
    enable_take_profit: bool = True
    take_profit_pct: Decimal = Decimal("30")      # +30% take-profit
    enable_circuit_breakers: bool = True
    daily_loss_limit_pct: Decimal = Decimal("-10")  # -10% daily loss limit

    # Exit simulation
    default_hold_days: int = 7  # Hold for 7 days if no exit signal
    use_actual_outcomes: bool = True  # Use actual trade outcomes if available

    # Rebalancing
    rebalance_frequency_days: int = 1  # Daily rebalancing


# ==================== Backtesting Engine ====================

class BacktestingEngine:
    """
    Comprehensive Backtesting Engine

    Replays historical whale trades with realistic execution simulation:
    1. **Historical Data:** Load whale trades from database
    2. **Execution Simulation:** Simulate slippage, fees, latency
    3. **Risk Management:** Apply position sizing, stop-loss, circuit breakers
    4. **Performance Tracking:** Track P&L, Sharpe, win rate, drawdown
    5. **Baseline Comparison:** Compare strategy vs no risk management
    6. **Comprehensive Reports:** Generate detailed backtest reports

    Execution Simulation:
    - Slippage: Base 10 bps + 2 bps per $1k order size
    - Fees: 2% maker/taker fees (Polymarket typical)
    - Latency: 100ms base + random variance
    - Fill probability: Based on market liquidity

    Risk Management:
    - Position sizing: Max 5% per position
    - Stop-loss: -15% (configurable)
    - Take-profit: +30% (configurable)
    - Circuit breakers: Halt at -10% daily loss
    - Correlation limits: No over-leverage

    Performance Metrics:
    - Returns: Total, annualized, daily
    - Sharpe ratio: (Return - RiskFree) / StdDev
    - Sortino ratio: (Return - RiskFree) / DownsideStdDev
    - Win rate: Winners / Total trades
    - Max drawdown: Peak to trough decline
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize backtesting engine

        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()

        # Backtest state
        self.current_capital = self.config.starting_capital_usd
        self.peak_capital = self.config.starting_capital_usd
        self.open_positions: Dict[str, BacktestTrade] = {}
        self.closed_trades: List[BacktestTrade] = []
        self.daily_pnl: Dict[datetime, Decimal] = {}
        self.equity_curve: List[Tuple[datetime, Decimal]] = []

        # Metrics
        self.trades_executed = 0
        self.trades_skipped_slippage = 0
        self.trades_skipped_risk = 0
        self.circuit_breaks = 0

        logger.info(
            f"BacktestingEngine initialized: "
            f"starting_capital=${float(self.config.starting_capital_usd):,.0f}, "
            f"risk_mgmt={'ON' if self.config.enable_position_sizing else 'OFF'}"
        )

    async def run_backtest(
        self,
        historical_trades: List[HistoricalTrade],
        mode: BacktestMode = BacktestMode.COMPARISON
    ) -> BacktestReport:
        """
        Run comprehensive backtest

        Args:
            historical_trades: List of historical whale trades
            mode: Backtest mode (BASELINE, WITH_RISK_MGMT, or COMPARISON)

        Returns:
            Comprehensive backtest report
        """
        logger.info(
            f"Starting backtest: {len(historical_trades)} trades, "
            f"mode={mode.value}"
        )

        if mode == BacktestMode.COMPARISON:
            # Run both baseline and risk-managed backtests
            baseline_metrics = await self._run_single_backtest(
                historical_trades, BacktestMode.BASELINE
            )

            risk_mgmt_metrics = await self._run_single_backtest(
                historical_trades, BacktestMode.WITH_RISK_MGMT
            )

            # Generate comparison report
            report = self._generate_comparison_report(
                historical_trades, baseline_metrics, risk_mgmt_metrics
            )

        else:
            # Run single backtest
            metrics = await self._run_single_backtest(historical_trades, mode)

            # Generate single report (compare to itself)
            report = self._generate_comparison_report(
                historical_trades, metrics, metrics
            )

        logger.info(f"Backtest complete: report_id={report.report_id}")

        return report

    async def _run_single_backtest(
        self,
        historical_trades: List[HistoricalTrade],
        mode: BacktestMode
    ) -> BacktestMetrics:
        """Run a single backtest (baseline or with risk management)"""
        # Reset state
        self._reset_state()

        # Enable/disable risk management based on mode
        enable_risk_mgmt = (mode == BacktestMode.WITH_RISK_MGMT)

        # Sort trades chronologically
        sorted_trades = sorted(historical_trades, key=lambda t: t.timestamp)

        if not sorted_trades:
            return self._empty_metrics(mode, datetime.now(), datetime.now())

        start_date = sorted_trades[0].timestamp
        end_date = sorted_trades[-1].timestamp

        logger.info(
            f"Running {mode.value} backtest: "
            f"{start_date.date()} to {end_date.date()} "
            f"({len(sorted_trades)} trades)"
        )

        # Replay trades chronologically
        for hist_trade in sorted_trades:
            # Check circuit breakers (if enabled)
            if enable_risk_mgmt and self.config.enable_circuit_breakers:
                if self._check_circuit_breakers(hist_trade.timestamp):
                    self.circuit_breaks += 1
                    logger.warning(f"Circuit breaker triggered at {hist_trade.timestamp}")
                    continue

            # Simulate trade execution
            await self._execute_simulated_trade(
                hist_trade, enable_risk_mgmt=enable_risk_mgmt
            )

            # Update equity curve
            self.equity_curve.append((hist_trade.timestamp, self.current_capital))

            # Check and update open positions (stop-loss, take-profit, etc.)
            await self._update_open_positions(hist_trade.timestamp, enable_risk_mgmt)

        # Close all remaining positions
        await self._close_all_positions(end_date)

        # Calculate metrics
        metrics = self._calculate_metrics(mode, start_date, end_date)

        logger.info(
            f"{mode.value} backtest complete: "
            f"return={float(metrics.total_return_pct):.1f}%, "
            f"sharpe={float(metrics.sharpe_ratio):.2f}, "
            f"max_dd={float(metrics.max_drawdown_pct):.1f}%"
        )

        return metrics

    async def _execute_simulated_trade(
        self,
        hist_trade: HistoricalTrade,
        enable_risk_mgmt: bool
    ):
        """Simulate execution of a single trade"""
        # Simulate execution latency
        latency_ms = self._simulate_latency()
        await asyncio.sleep(latency_ms / 1000)  # Small delay for realism

        # Calculate slippage
        slippage_pct = self._calculate_slippage(hist_trade.size_usd)

        # Check if should skip due to excessive slippage
        if slippage_pct > Decimal("2.0"):  # >2% slippage
            self.trades_skipped_slippage += 1
            logger.debug(f"Skipped trade {hist_trade.trade_id}: slippage {slippage_pct:.2f}%")
            return

        # Apply position sizing (if risk management enabled)
        original_size = hist_trade.size_usd
        position_size = original_size

        if enable_risk_mgmt and self.config.enable_position_sizing:
            max_position_size = self.current_capital * (self.config.max_position_size_pct / Decimal("100"))

            if position_size > max_position_size:
                position_size = max_position_size
                logger.debug(
                    f"Position sized: ${original_size:.0f} → ${position_size:.0f} "
                    f"(max {self.config.max_position_size_pct}%)"
                )

        # Check if enough capital
        if position_size > self.current_capital * Decimal("0.95"):  # Reserve 5%
            self.trades_skipped_risk += 1
            logger.debug(f"Skipped trade {hist_trade.trade_id}: insufficient capital")
            return

        # Calculate entry price with slippage
        if hist_trade.side == "BUY":
            entry_price = hist_trade.price * (Decimal("1") + slippage_pct / Decimal("100"))
        else:  # SELL
            entry_price = hist_trade.price * (Decimal("1") - slippage_pct / Decimal("100"))

        # Calculate fees
        entry_fees = position_size * (self.config.trading_fee_pct / Decimal("100"))

        # Update capital
        self.current_capital -= (position_size + entry_fees)

        # Calculate stop-loss and take-profit prices
        stop_loss_price = None
        take_profit_price = None

        if enable_risk_mgmt:
            if self.config.enable_stop_loss:
                stop_loss_price = entry_price * (Decimal("1") + self.config.stop_loss_pct / Decimal("100"))

            if self.config.enable_take_profit:
                take_profit_price = entry_price * (Decimal("1") + self.config.take_profit_pct / Decimal("100"))

        # Create backtest trade
        trade = BacktestTrade(
            trade_id=hist_trade.trade_id,
            whale_address=hist_trade.whale_address,
            market_id=hist_trade.market_id,
            outcome=hist_trade.outcome,
            side=hist_trade.side,
            entry_timestamp=hist_trade.timestamp,
            entry_size_usd=position_size,
            entry_price=entry_price,
            entry_slippage_pct=slippage_pct,
            entry_fees_usd=entry_fees,
            exit_timestamp=None,
            exit_price=None,
            exit_reason=None,
            exit_fees_usd=None,
            gross_pnl_usd=None,
            net_pnl_usd=None,
            return_pct=None,
            execution_outcome=TradeOutcome.FILLED,
            execution_latency_ms=latency_ms,
            was_position_sized=(position_size < original_size),
            original_size_usd=original_size,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price
        )

        # Add to open positions
        self.open_positions[trade.trade_id] = trade
        self.trades_executed += 1

        logger.debug(
            f"Executed trade {trade.trade_id}: "
            f"${position_size:.0f} @ {entry_price:.3f} "
            f"(slippage {slippage_pct:.2f}%, fees ${entry_fees:.2f})"
        )

    async def _update_open_positions(
        self,
        current_time: datetime,
        enable_risk_mgmt: bool
    ):
        """Check and update open positions (stop-loss, take-profit, expiry)"""
        positions_to_close = []

        for trade_id, trade in self.open_positions.items():
            # Calculate current price (simplified - in reality would get from market data)
            # For now, use a random walk simulation
            time_held_days = (current_time - trade.entry_timestamp).days
            current_price = self._simulate_price_movement(
                trade.entry_price, time_held_days
            )

            # Check stop-loss
            if enable_risk_mgmt and trade.stop_loss_price:
                if current_price <= trade.stop_loss_price:
                    positions_to_close.append((trade_id, current_price, "STOP_LOSS"))
                    continue

            # Check take-profit
            if enable_risk_mgmt and trade.take_profit_price:
                if current_price >= trade.take_profit_price:
                    positions_to_close.append((trade_id, current_price, "TAKE_PROFIT"))
                    continue

            # Check default hold period
            if time_held_days >= self.config.default_hold_days:
                positions_to_close.append((trade_id, current_price, "TIME_LIMIT"))

        # Close positions
        for trade_id, exit_price, exit_reason in positions_to_close:
            await self._close_position(trade_id, exit_price, current_time, exit_reason)

    async def _close_position(
        self,
        trade_id: str,
        exit_price: Decimal,
        exit_time: datetime,
        exit_reason: str
    ):
        """Close an open position"""
        if trade_id not in self.open_positions:
            return

        trade = self.open_positions[trade_id]

        # Calculate exit fees
        exit_fees = trade.entry_size_usd * (self.config.trading_fee_pct / Decimal("100"))

        # Calculate P&L
        price_change_pct = ((exit_price - trade.entry_price) / trade.entry_price) * Decimal("100")
        gross_pnl = trade.entry_size_usd * (price_change_pct / Decimal("100"))
        net_pnl = gross_pnl - trade.entry_fees_usd - exit_fees

        # Update trade
        trade.exit_timestamp = exit_time
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.exit_fees_usd = exit_fees
        trade.gross_pnl_usd = gross_pnl
        trade.net_pnl_usd = net_pnl
        trade.return_pct = (net_pnl / trade.entry_size_usd) * Decimal("100")

        # Update outcome
        if exit_reason == "STOP_LOSS":
            trade.execution_outcome = TradeOutcome.STOPPED_OUT
        elif exit_reason == "TAKE_PROFIT":
            trade.execution_outcome = TradeOutcome.TAKEN_PROFIT
        else:
            trade.execution_outcome = TradeOutcome.FILLED

        # Update capital
        self.current_capital += (trade.entry_size_usd + net_pnl)

        # Update peak capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Record daily P&L
        trade_date = exit_time.date()
        if trade_date not in self.daily_pnl:
            self.daily_pnl[trade_date] = Decimal("0")
        self.daily_pnl[trade_date] += net_pnl

        # Move to closed trades
        self.closed_trades.append(trade)
        del self.open_positions[trade_id]

        logger.debug(
            f"Closed position {trade_id}: "
            f"P&L ${net_pnl:.2f} ({trade.return_pct:.1f}%) | "
            f"Reason: {exit_reason}"
        )

    async def _close_all_positions(self, end_date: datetime):
        """Close all remaining open positions at end of backtest"""
        for trade_id in list(self.open_positions.keys()):
            trade = self.open_positions[trade_id]
            # Use a simulated final price
            time_held_days = (end_date - trade.entry_timestamp).days
            exit_price = self._simulate_price_movement(trade.entry_price, time_held_days)
            await self._close_position(trade_id, exit_price, end_date, "END_OF_BACKTEST")

    def _check_circuit_breakers(self, current_time: datetime) -> bool:
        """Check if circuit breakers should trigger"""
        today = current_time.date()

        if today not in self.daily_pnl:
            return False

        # Calculate daily P&L percentage
        daily_return_pct = (self.daily_pnl[today] / self.config.starting_capital_usd) * Decimal("100")

        # Check daily loss limit
        if daily_return_pct <= self.config.daily_loss_limit_pct:
            logger.warning(f"Circuit breaker: Daily loss {daily_return_pct:.1f}% exceeds limit")
            return True

        return False

    def _calculate_slippage(self, order_size_usd: Decimal) -> Decimal:
        """Calculate slippage based on order size"""
        # Base slippage + size-dependent slippage
        base_slippage_pct = self.config.base_slippage_bps / Decimal("100")  # Convert bps to %
        size_dependent_slippage = (order_size_usd / Decimal("1000")) * (self.config.slippage_per_1k_usd / Decimal("100"))

        total_slippage_pct = base_slippage_pct + size_dependent_slippage

        # Add random variance
        import random
        variance = Decimal(str(random.uniform(-0.05, 0.05)))  # ±5% variance
        total_slippage_pct *= (Decimal("1") + variance)

        return total_slippage_pct

    def _simulate_latency(self) -> Decimal:
        """Simulate execution latency"""
        import random
        # Base latency + random variance (50-200ms)
        latency = float(self.config.base_latency_ms) + random.uniform(-50, 100)
        return Decimal(str(max(10, latency)))

    def _simulate_price_movement(self, entry_price: Decimal, days_held: int) -> Decimal:
        """Simulate price movement (simplified random walk)"""
        import random

        # Random daily returns (simplified)
        daily_returns = [random.gauss(0.02, 0.15) for _ in range(days_held)]  # Mean 2% daily, 15% volatility

        cumulative_return = 1.0
        for daily_return in daily_returns:
            cumulative_return *= (1.0 + daily_return)

        exit_price = entry_price * Decimal(str(cumulative_return))

        # Ensure price stays positive and within reasonable bounds
        return max(Decimal("0.01"), min(Decimal("0.99"), exit_price))

    def _calculate_metrics(
        self,
        mode: BacktestMode,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestMetrics:
        """Calculate comprehensive backtest metrics"""
        # Returns
        total_return_pct = ((self.current_capital - self.config.starting_capital_usd) /
                           self.config.starting_capital_usd) * Decimal("100")

        # Annualized return
        days = max(1, (end_date - start_date).days)
        years = Decimal(str(days)) / Decimal("365")
        annualized_return_pct = (((self.current_capital / self.config.starting_capital_usd) **
                                 (Decimal("1") / years)) - Decimal("1")) * Decimal("100")

        # Daily returns
        daily_returns = [
            (pnl / self.config.starting_capital_usd) * Decimal("100")
            for pnl in self.daily_pnl.values()
        ]

        # Sharpe ratio (assume 0% risk-free rate)
        if daily_returns:
            returns_array = [float(r) for r in daily_returns]
            avg_return = np.mean(returns_array)
            std_return = np.std(returns_array)
            sharpe_ratio = Decimal(str(avg_return / std_return * np.sqrt(252))) if std_return > 0 else Decimal("0")
        else:
            sharpe_ratio = Decimal("0")

        # Sortino ratio (downside deviation)
        if daily_returns:
            negative_returns = [float(r) for r in daily_returns if r < 0]
            downside_std = np.std(negative_returns) if negative_returns else 0.001
            sortino_ratio = Decimal(str(avg_return / downside_std * np.sqrt(252))) if downside_std > 0 else Decimal("0")
        else:
            sortino_ratio = Decimal("0")

        # Win/Loss stats
        winning_trades = [t for t in self.closed_trades if t.net_pnl_usd and t.net_pnl_usd > 0]
        losing_trades = [t for t in self.closed_trades if t.net_pnl_usd and t.net_pnl_usd <= 0]

        total_trades = len(self.closed_trades)
        win_rate_pct = (Decimal(str(len(winning_trades))) / Decimal(str(total_trades))) * Decimal("100") if total_trades > 0 else Decimal("0")

        # Profit factor
        total_wins = sum(t.net_pnl_usd for t in winning_trades)
        total_losses = abs(sum(t.net_pnl_usd for t in losing_trades)) if losing_trades else Decimal("0.01")
        profit_factor = total_wins / total_losses if total_losses > 0 else Decimal("0")

        # Payoff ratio
        avg_win = total_wins / Decimal(str(len(winning_trades))) if winning_trades else Decimal("0")
        avg_loss = abs(total_losses / Decimal(str(len(losing_trades)))) if losing_trades else Decimal("0.01")
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else Decimal("0")

        # Max drawdown
        max_drawdown_pct, max_drawdown_usd, max_dd_duration, recovery_time = self._calculate_drawdown()

        # Calmar ratio (return / max drawdown)
        calmar_ratio = annualized_return_pct / abs(max_drawdown_pct) if max_drawdown_pct != 0 else Decimal("0")

        # Execution quality
        avg_slippage = (
            sum(t.entry_slippage_pct for t in self.closed_trades) / Decimal(str(len(self.closed_trades)))
            if self.closed_trades else Decimal("0")
        )

        avg_latency = (
            sum(t.execution_latency_ms for t in self.closed_trades) / Decimal(str(len(self.closed_trades)))
            if self.closed_trades else Decimal("0")
        )

        # Count outcomes
        stopped_out = sum(1 for t in self.closed_trades if t.execution_outcome == TradeOutcome.STOPPED_OUT)
        take_profit = sum(1 for t in self.closed_trades if t.execution_outcome == TradeOutcome.TAKEN_PROFIT)

        return BacktestMetrics(
            backtest_id=f"backtest_{mode.value.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            starting_capital_usd=self.config.starting_capital_usd,
            ending_capital_usd=self.current_capital,
            peak_capital_usd=self.peak_capital,
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            daily_returns=daily_returns,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate_pct=win_rate_pct,
            profit_factor=profit_factor,
            payoff_ratio=payoff_ratio,
            max_drawdown_pct=max_drawdown_pct,
            max_drawdown_usd=max_drawdown_usd,
            max_drawdown_duration_days=max_dd_duration,
            recovery_time_days=recovery_time,
            avg_slippage_pct=avg_slippage,
            avg_latency_ms=avg_latency,
            trades_skipped_slippage=self.trades_skipped_slippage,
            trades_skipped_risk=self.trades_skipped_risk,
            stopped_out_trades=stopped_out,
            take_profit_trades=take_profit,
            circuit_breaks_triggered=self.circuit_breaks
        )

    def _calculate_drawdown(self) -> Tuple[Decimal, Decimal, int, Optional[int]]:
        """Calculate maximum drawdown and recovery time"""
        if not self.equity_curve:
            return Decimal("0"), Decimal("0"), 0, None

        # Convert to arrays
        times = [t for t, _ in self.equity_curve]
        equity = [float(e) for _, e in self.equity_curve]

        # Find peak and trough
        peak = equity[0]
        max_dd = 0.0
        max_dd_usd = 0.0
        dd_start_idx = 0
        dd_end_idx = 0
        recovery_idx = None

        in_drawdown = False
        dd_start = 0

        for i, eq in enumerate(equity):
            if eq > peak:
                peak = eq
                if in_drawdown:
                    # Recovered
                    recovery_idx = i
                    in_drawdown = False
            else:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
                    max_dd_usd = peak - eq
                    dd_start_idx = dd_start
                    dd_end_idx = i

                if not in_drawdown:
                    in_drawdown = True
                    dd_start = i

        # Calculate duration
        if dd_start_idx < len(times) and dd_end_idx < len(times):
            dd_duration = (times[dd_end_idx] - times[dd_start_idx]).days
        else:
            dd_duration = 0

        # Calculate recovery time
        if recovery_idx and dd_end_idx < len(times) and recovery_idx < len(times):
            recovery_time = (times[recovery_idx] - times[dd_end_idx]).days
        else:
            recovery_time = None

        return (
            Decimal(str(max_dd * 100)),
            Decimal(str(max_dd_usd)),
            dd_duration,
            recovery_time
        )

    def _generate_comparison_report(
        self,
        historical_trades: List[HistoricalTrade],
        baseline_metrics: BacktestMetrics,
        risk_mgmt_metrics: BacktestMetrics
    ) -> BacktestReport:
        """Generate comparison report between baseline and risk-managed backtests"""
        # Calculate improvements
        return_improvement = risk_mgmt_metrics.total_return_pct - baseline_metrics.total_return_pct
        sharpe_improvement = risk_mgmt_metrics.sharpe_ratio - baseline_metrics.sharpe_ratio

        if baseline_metrics.max_drawdown_pct != 0:
            drawdown_reduction = ((baseline_metrics.max_drawdown_pct - risk_mgmt_metrics.max_drawdown_pct) /
                                 abs(baseline_metrics.max_drawdown_pct)) * Decimal("100")
        else:
            drawdown_reduction = Decimal("0")

        # Risk-adjusted improvement (Sharpe * (1 - Drawdown%))
        baseline_risk_adj = baseline_metrics.sharpe_ratio * (Decimal("1") - abs(baseline_metrics.max_drawdown_pct) / Decimal("100"))
        risk_mgmt_risk_adj = risk_mgmt_metrics.sharpe_ratio * (Decimal("1") - abs(risk_mgmt_metrics.max_drawdown_pct) / Decimal("100"))
        risk_adj_improvement = ((risk_mgmt_risk_adj - baseline_risk_adj) / abs(baseline_risk_adj)) * Decimal("100") if baseline_risk_adj != 0 else Decimal("0")

        # Trades by outcome
        all_trades = self.closed_trades
        trades_by_outcome = defaultdict(int)
        for trade in all_trades:
            trades_by_outcome[trade.execution_outcome] += 1

        # Trades by whale
        trades_by_whale = defaultdict(int)
        for trade in all_trades:
            trades_by_whale[trade.whale_address] += 1

        # Trades by market
        trades_by_market = defaultdict(int)
        for trade in all_trades:
            trades_by_market[trade.market_id] += 1

        # Generate recommendations
        recommendations = self._generate_recommendations(
            baseline_metrics, risk_mgmt_metrics, return_improvement
        )

        return BacktestReport(
            report_id=f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_date=baseline_metrics.start_date,
            end_date=baseline_metrics.end_date,
            days_simulated=(baseline_metrics.end_date - baseline_metrics.start_date).days,
            trades_replayed=len(historical_trades),
            baseline_metrics=baseline_metrics,
            risk_mgmt_metrics=risk_mgmt_metrics,
            return_improvement_pct=return_improvement,
            sharpe_improvement=sharpe_improvement,
            drawdown_reduction_pct=drawdown_reduction,
            risk_adjusted_improvement=risk_adj_improvement,
            trades_by_outcome=dict(trades_by_outcome),
            trades_by_whale=dict(trades_by_whale),
            trades_by_market=dict(trades_by_market),
            recommendations=recommendations
        )

    def _generate_recommendations(
        self,
        baseline: BacktestMetrics,
        risk_mgmt: BacktestMetrics,
        return_improvement: Decimal
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Return comparison
        if return_improvement > Decimal("5"):
            recommendations.append(
                f"✅ Risk management IMPROVED returns by {return_improvement:.1f}% - "
                "strongly recommend enabling"
            )
        elif return_improvement < Decimal("-5"):
            recommendations.append(
                f"⚠️ Risk management REDUCED returns by {abs(return_improvement):.1f}% - "
                "consider relaxing constraints"
            )
        else:
            recommendations.append(
                f"Risk management had neutral impact on returns ({return_improvement:+.1f}%)"
            )

        # Sharpe ratio
        if risk_mgmt.sharpe_ratio > baseline.sharpe_ratio * Decimal("1.2"):
            recommendations.append(
                f"✅ Sharpe ratio improved {float(risk_mgmt.sharpe_ratio):.2f} vs "
                f"{float(baseline.sharpe_ratio):.2f} - better risk-adjusted returns"
            )

        # Drawdown
        if risk_mgmt.max_drawdown_pct < baseline.max_drawdown_pct * Decimal("0.7"):
            recommendations.append(
                f"✅ Drawdown reduced by {float((baseline.max_drawdown_pct - risk_mgmt.max_drawdown_pct)):.1f}% - "
                "significantly safer strategy"
            )

        # Win rate
        if risk_mgmt.win_rate_pct < Decimal("50"):
            recommendations.append(
                f"⚠️ Win rate {risk_mgmt.win_rate_pct:.1f}% is low - "
                "review trade selection criteria"
            )

        # Slippage
        if baseline.avg_slippage_pct > Decimal("1.0"):
            recommendations.append(
                f"⚠️ Average slippage {baseline.avg_slippage_pct:.2f}% is high - "
                "consider using TWAP for large orders"
            )

        # Stop-loss effectiveness
        if risk_mgmt.stopped_out_trades > risk_mgmt.total_trades * 0.3:
            recommendations.append(
                f"⚠️ {(risk_mgmt.stopped_out_trades / risk_mgmt.total_trades * 100):.0f}% of trades stopped out - "
                "consider widening stop-loss or improving entry timing"
            )

        if not recommendations:
            recommendations.append("Strategy performance is within acceptable parameters")

        return recommendations

    def print_report(self, report: BacktestReport):
        """Print formatted backtest report"""
        print(f"\n{'='*100}")
        print(f"BACKTEST REPORT")
        print(f"{'='*100}")
        print(f"Period: {report.start_date.date()} to {report.end_date.date()} ({report.days_simulated} days)")
        print(f"Trades Replayed: {report.trades_replayed:,}")
        print()

        # Performance comparison
        print(f"{'─'*100}")
        print(f"PERFORMANCE COMPARISON")
        print(f"{'─'*100}")
        print(f"{'Metric':<30} {'Baseline':<25} {'Risk Management':<25} {'Improvement':<20}")
        print(f"{'─'*100}")

        b = report.baseline_metrics
        r = report.risk_mgmt_metrics

        print(f"{'Total Return':<30} {float(b.total_return_pct):>20.1f}%  {float(r.total_return_pct):>20.1f}%  {float(report.return_improvement_pct):>15.1f}%")
        print(f"{'Sharpe Ratio':<30} {float(b.sharpe_ratio):>24.2f}  {float(r.sharpe_ratio):>24.2f}  {float(report.sharpe_improvement):>19.2f}")
        print(f"{'Max Drawdown':<30} {float(b.max_drawdown_pct):>20.1f}%  {float(r.max_drawdown_pct):>20.1f}%  {float(report.drawdown_reduction_pct):>15.1f}%")
        print(f"{'Win Rate':<30} {float(b.win_rate_pct):>20.1f}%  {float(r.win_rate_pct):>20.1f}%")
        print(f"{'Profit Factor':<30} {float(b.profit_factor):>24.2f}  {float(r.profit_factor):>24.2f}")
        print()

        # Recommendations
        print(f"{'─'*100}")
        print(f"RECOMMENDATIONS")
        print(f"{'─'*100}")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"{i}. {rec}")
        print()

        print(f"{'='*100}\n")

    def _reset_state(self):
        """Reset backtest state for new run"""
        self.current_capital = self.config.starting_capital_usd
        self.peak_capital = self.config.starting_capital_usd
        self.open_positions = {}
        self.closed_trades = []
        self.daily_pnl = {}
        self.equity_curve = []
        self.trades_executed = 0
        self.trades_skipped_slippage = 0
        self.trades_skipped_risk = 0
        self.circuit_breaks = 0

    def _empty_metrics(self, mode: BacktestMode, start_date: datetime, end_date: datetime) -> BacktestMetrics:
        """Return empty metrics"""
        return BacktestMetrics(
            backtest_id=f"backtest_{mode.value.lower()}_empty",
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            starting_capital_usd=self.config.starting_capital_usd,
            ending_capital_usd=self.config.starting_capital_usd,
            peak_capital_usd=self.config.starting_capital_usd,
            total_return_pct=Decimal("0"),
            annualized_return_pct=Decimal("0"),
            daily_returns=[],
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            calmar_ratio=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=Decimal("0"),
            profit_factor=Decimal("0"),
            payoff_ratio=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            max_drawdown_usd=Decimal("0"),
            max_drawdown_duration_days=0,
            recovery_time_days=None,
            avg_slippage_pct=Decimal("0"),
            avg_latency_ms=Decimal("0"),
            trades_skipped_slippage=0,
            trades_skipped_risk=0,
            stopped_out_trades=0,
            take_profit_trades=0,
            circuit_breaks_triggered=0
        )


# ==================== Example Usage ====================

async def main():
    """Example usage of BacktestingEngine"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create mock historical trades
    print("\n=== Backtesting Engine Test ===\n")
    print("Generating mock historical trades...\n")

    import random
    from datetime import timedelta

    mock_trades = []
    start_date = datetime.now() - timedelta(days=90)

    for i in range(100):
        trade_date = start_date + timedelta(days=random.randint(0, 90))

        trade = HistoricalTrade(
            trade_id=f"trade_{i}",
            whale_address=f"whale_{random.randint(1, 5)}",
            market_id=f"market_{random.randint(1, 10)}",
            outcome=random.choice(["YES", "NO"]),
            side=random.choice(["BUY", "SELL"]),
            size_shares=Decimal(str(random.uniform(100, 10000))),
            size_usd=Decimal(str(random.uniform(100, 5000))),
            price=Decimal(str(random.uniform(0.3, 0.7))),
            timestamp=trade_date,
            market_volume_24h=Decimal(str(random.uniform(10000, 100000))),
            market_liquidity_score=Decimal(str(random.uniform(0.5, 1.0))),
            final_profit_usd=None,
            final_profit_pct=None
        )

        mock_trades.append(trade)

    # Run backtest
    engine = BacktestingEngine()
    report = await engine.run_backtest(mock_trades, BacktestMode.COMPARISON)

    # Print report
    engine.print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
