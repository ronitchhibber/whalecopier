"""
Week 9: Performance Analytics - Advanced Performance Metrics Engine

This module provides comprehensive performance metrics for the copy trading system:
- Sharpe ratio (target >2.0)
- Sortino ratio (downside risk focus)
- Calmar ratio (return/max_drawdown)
- Win rate (% winning trades)
- Profit factor (gross_profit / gross_loss)
- Payoff ratio (avg_win / avg_loss)
- Max drawdown (peak to trough decline)
- Recovery time (days to recover from drawdown)
- Information ratio, Omega ratio, etc.

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
import json
import math

logger = logging.getLogger(__name__)


class TimeWindow(Enum):
    """Time windows for performance analysis"""
    DAILY = "1d"
    WEEKLY = "7d"
    MONTHLY = "30d"
    QUARTERLY = "90d"
    YEARLY = "365d"
    ALL_TIME = "all"


@dataclass
class PerformanceConfig:
    """Configuration for performance metrics calculation"""

    # Risk-free rate (annualized)
    risk_free_rate_annual: Decimal = Decimal("4.5")  # 4.5% (current US T-Bill rate)

    # Target metrics
    target_sharpe_ratio: Decimal = Decimal("2.0")
    target_sortino_ratio: Decimal = Decimal("2.5")
    target_calmar_ratio: Decimal = Decimal("3.0")
    target_win_rate_pct: Decimal = Decimal("55.0")
    target_profit_factor: Decimal = Decimal("2.0")
    target_payoff_ratio: Decimal = Decimal("1.5")

    # Drawdown thresholds
    max_acceptable_drawdown_pct: Decimal = Decimal("15.0")
    severe_drawdown_pct: Decimal = Decimal("25.0")

    # Recovery time thresholds (days)
    acceptable_recovery_days: int = 30
    severe_recovery_days: int = 90

    # Calculation parameters
    min_trades_for_significance: int = 30
    confidence_level: Decimal = Decimal("95.0")  # 95% confidence intervals

    # Performance update frequency
    update_interval_seconds: int = 60  # Update metrics every 60 seconds

    # Database paths (for persistence)
    trades_db_path: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/data/trades.db"
    metrics_db_path: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/data/performance_metrics.db"


@dataclass
class Trade:
    """Individual trade record"""
    trade_id: str
    whale_address: str
    market_id: str
    market_topic: str
    side: str  # "BUY" or "SELL"
    entry_price: Decimal
    exit_price: Optional[Decimal]
    position_size_usd: Decimal
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl_usd: Decimal
    pnl_pct: Decimal
    is_open: bool
    fees_paid_usd: Decimal
    slippage_pct: Decimal


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""

    # Identification
    calculation_time: datetime
    time_window: TimeWindow

    # Return metrics
    total_return_pct: Decimal
    annualized_return_pct: Decimal
    cumulative_pnl_usd: Decimal

    # Risk-adjusted metrics
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    information_ratio: Decimal
    omega_ratio: Decimal

    # Win/Loss metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    profit_factor: Decimal
    payoff_ratio: Decimal

    # Average metrics
    avg_win_usd: Decimal
    avg_loss_usd: Decimal
    avg_win_pct: Decimal
    avg_loss_pct: Decimal
    avg_trade_duration_hours: Decimal

    # Drawdown metrics
    max_drawdown_pct: Decimal
    max_drawdown_usd: Decimal
    current_drawdown_pct: Decimal
    drawdown_recovery_days: Optional[int]
    time_underwater_days: int

    # Streak metrics
    current_win_streak: int
    current_loss_streak: int
    max_win_streak: int
    max_loss_streak: int

    # Volatility metrics
    daily_volatility_pct: Decimal
    annual_volatility_pct: Decimal
    downside_deviation_pct: Decimal

    # Consistency metrics
    best_day_return_pct: Decimal
    worst_day_return_pct: Decimal
    positive_days_pct: Decimal
    monthly_return_consistency: Decimal  # Std dev of monthly returns

    # Benchmark comparison
    benchmark_return_pct: Optional[Decimal] = None
    alpha: Optional[Decimal] = None  # Excess return over benchmark
    beta: Optional[Decimal] = None  # Correlation to benchmark

    # Quality indicators
    is_statistically_significant: bool = False
    confidence_level_pct: Decimal = Decimal("0")
    min_trades_met: bool = False


@dataclass
class PerformanceSnapshot:
    """Performance snapshot for a specific time"""
    timestamp: datetime
    equity: Decimal
    cumulative_pnl: Decimal
    drawdown_pct: Decimal
    daily_return_pct: Decimal


class PerformanceMetricsEngine:
    """
    Advanced performance metrics calculation engine.

    Calculates comprehensive risk-adjusted performance metrics including:
    - Sharpe ratio: (Return - RiskFree) / Volatility
    - Sortino ratio: (Return - RiskFree) / DownsideDeviation
    - Calmar ratio: AnnualizedReturn / MaxDrawdown
    - Win rate, profit factor, payoff ratio
    - Drawdown and recovery analysis
    """

    def __init__(self, config: PerformanceConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.snapshots: List[PerformanceSnapshot] = []
        self.current_equity: Decimal = Decimal("100000")  # Starting capital
        self.starting_equity: Decimal = Decimal("100000")
        self.peak_equity: Decimal = Decimal("100000")

        # Cached metrics
        self.current_metrics: Optional[PerformanceMetrics] = None
        self.metrics_by_window: Dict[TimeWindow, PerformanceMetrics] = {}

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("PerformanceMetricsEngine initialized")

    async def start(self):
        """Start the metrics engine"""
        if self.is_running:
            logger.warning("PerformanceMetricsEngine already running")
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())

        logger.info("PerformanceMetricsEngine started")

    async def stop(self):
        """Stop the metrics engine"""
        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        logger.info("PerformanceMetricsEngine stopped")

    async def _update_loop(self):
        """Background loop to update metrics"""
        while self.is_running:
            try:
                # Calculate metrics for all time windows
                for window in TimeWindow:
                    metrics = await self.calculate_metrics(window)
                    self.metrics_by_window[window] = metrics

                # Update current metrics (all-time)
                self.current_metrics = self.metrics_by_window.get(TimeWindow.ALL_TIME)

                # Log key metrics
                if self.current_metrics:
                    logger.info(
                        f"Performance Update - "
                        f"Sharpe: {self.current_metrics.sharpe_ratio:.2f}, "
                        f"Win Rate: {self.current_metrics.win_rate_pct:.1f}%, "
                        f"Profit Factor: {self.current_metrics.profit_factor:.2f}, "
                        f"Max DD: {self.current_metrics.max_drawdown_pct:.1f}%"
                    )

                await asyncio.sleep(self.config.update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in performance update loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    def add_trade(self, trade: Trade):
        """Add a trade to the performance history"""
        self.trades.append(trade)

        # Update equity
        if not trade.is_open:
            self.current_equity += trade.pnl_usd

            # Update peak equity
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity

            # Create snapshot
            daily_return_pct = (trade.pnl_usd / self.current_equity) * Decimal("100")
            drawdown_pct = ((self.peak_equity - self.current_equity) / self.peak_equity) * Decimal("100")

            snapshot = PerformanceSnapshot(
                timestamp=trade.exit_time or datetime.now(),
                equity=self.current_equity,
                cumulative_pnl=self.current_equity - self.starting_equity,
                drawdown_pct=drawdown_pct,
                daily_return_pct=daily_return_pct
            )
            self.snapshots.append(snapshot)

        logger.debug(f"Added trade {trade.trade_id} to performance history")

    async def calculate_metrics(self, time_window: TimeWindow) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics for a given time window.

        Args:
            time_window: Time period to analyze (daily, weekly, monthly, etc.)

        Returns:
            PerformanceMetrics object with all calculated metrics
        """
        # Filter trades by time window
        trades = self._filter_trades_by_window(time_window)

        if not trades:
            return self._create_empty_metrics(time_window)

        # Calculate return metrics
        total_return_pct, annualized_return_pct, cumulative_pnl = self._calculate_returns(trades, time_window)

        # Calculate win/loss metrics
        win_loss_metrics = self._calculate_win_loss_metrics(trades)

        # Calculate risk-adjusted metrics
        sharpe = self._calculate_sharpe_ratio(trades, annualized_return_pct, time_window)
        sortino = self._calculate_sortino_ratio(trades, annualized_return_pct, time_window)
        calmar = self._calculate_calmar_ratio(annualized_return_pct, trades)
        information = self._calculate_information_ratio(trades, time_window)
        omega = self._calculate_omega_ratio(trades)

        # Calculate drawdown metrics
        drawdown_metrics = self._calculate_drawdown_metrics(trades)

        # Calculate volatility metrics
        volatility_metrics = self._calculate_volatility_metrics(trades, time_window)

        # Calculate consistency metrics
        consistency_metrics = self._calculate_consistency_metrics(trades)

        # Calculate streak metrics
        streak_metrics = self._calculate_streak_metrics(trades)

        # Check statistical significance
        is_significant, confidence = self._check_statistical_significance(trades)

        metrics = PerformanceMetrics(
            calculation_time=datetime.now(),
            time_window=time_window,

            # Returns
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            cumulative_pnl_usd=cumulative_pnl,

            # Risk-adjusted
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            information_ratio=information,
            omega_ratio=omega,

            # Win/Loss
            total_trades=win_loss_metrics["total_trades"],
            winning_trades=win_loss_metrics["winning_trades"],
            losing_trades=win_loss_metrics["losing_trades"],
            win_rate_pct=win_loss_metrics["win_rate_pct"],
            profit_factor=win_loss_metrics["profit_factor"],
            payoff_ratio=win_loss_metrics["payoff_ratio"],

            # Averages
            avg_win_usd=win_loss_metrics["avg_win_usd"],
            avg_loss_usd=win_loss_metrics["avg_loss_usd"],
            avg_win_pct=win_loss_metrics["avg_win_pct"],
            avg_loss_pct=win_loss_metrics["avg_loss_pct"],
            avg_trade_duration_hours=win_loss_metrics["avg_duration_hours"],

            # Drawdown
            max_drawdown_pct=drawdown_metrics["max_drawdown_pct"],
            max_drawdown_usd=drawdown_metrics["max_drawdown_usd"],
            current_drawdown_pct=drawdown_metrics["current_drawdown_pct"],
            drawdown_recovery_days=drawdown_metrics["recovery_days"],
            time_underwater_days=drawdown_metrics["time_underwater_days"],

            # Streaks
            current_win_streak=streak_metrics["current_win_streak"],
            current_loss_streak=streak_metrics["current_loss_streak"],
            max_win_streak=streak_metrics["max_win_streak"],
            max_loss_streak=streak_metrics["max_loss_streak"],

            # Volatility
            daily_volatility_pct=volatility_metrics["daily_volatility_pct"],
            annual_volatility_pct=volatility_metrics["annual_volatility_pct"],
            downside_deviation_pct=volatility_metrics["downside_deviation_pct"],

            # Consistency
            best_day_return_pct=consistency_metrics["best_day_return_pct"],
            worst_day_return_pct=consistency_metrics["worst_day_return_pct"],
            positive_days_pct=consistency_metrics["positive_days_pct"],
            monthly_return_consistency=consistency_metrics["monthly_consistency"],

            # Quality
            is_statistically_significant=is_significant,
            confidence_level_pct=confidence,
            min_trades_met=len(trades) >= self.config.min_trades_for_significance
        )

        return metrics

    def _filter_trades_by_window(self, time_window: TimeWindow) -> List[Trade]:
        """Filter trades by time window"""
        if time_window == TimeWindow.ALL_TIME:
            return [t for t in self.trades if not t.is_open]

        # Calculate cutoff time
        now = datetime.now()
        if time_window == TimeWindow.DAILY:
            cutoff = now - timedelta(days=1)
        elif time_window == TimeWindow.WEEKLY:
            cutoff = now - timedelta(days=7)
        elif time_window == TimeWindow.MONTHLY:
            cutoff = now - timedelta(days=30)
        elif time_window == TimeWindow.QUARTERLY:
            cutoff = now - timedelta(days=90)
        elif time_window == TimeWindow.YEARLY:
            cutoff = now - timedelta(days=365)
        else:
            cutoff = datetime.min

        return [t for t in self.trades if not t.is_open and t.exit_time and t.exit_time >= cutoff]

    def _calculate_returns(self, trades: List[Trade], time_window: TimeWindow) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate total return, annualized return, and cumulative P&L"""
        if not trades:
            return Decimal("0"), Decimal("0"), Decimal("0")

        # Cumulative P&L
        cumulative_pnl = sum(t.pnl_usd for t in trades)

        # Total return %
        total_return_pct = (cumulative_pnl / self.starting_equity) * Decimal("100")

        # Annualized return
        if time_window == TimeWindow.ALL_TIME:
            # Calculate based on actual time period
            first_trade = min(trades, key=lambda t: t.entry_time)
            last_trade = max(trades, key=lambda t: t.exit_time or datetime.max)

            days = (last_trade.exit_time - first_trade.entry_time).days
            if days < 1:
                days = 1

            years = Decimal(str(days)) / Decimal("365")
        else:
            # Use window duration
            window_days = {
                TimeWindow.DAILY: 1,
                TimeWindow.WEEKLY: 7,
                TimeWindow.MONTHLY: 30,
                TimeWindow.QUARTERLY: 90,
                TimeWindow.YEARLY: 365
            }
            days = window_days.get(time_window, 365)
            years = Decimal(str(days)) / Decimal("365")

        if years > 0:
            # Annualized return = (1 + total_return)^(1/years) - 1
            annualized_return_pct = (
                (Decimal("1") + total_return_pct / Decimal("100")) ** (Decimal("1") / years) - Decimal("1")
            ) * Decimal("100")
        else:
            annualized_return_pct = total_return_pct

        return total_return_pct, annualized_return_pct, cumulative_pnl

    def _calculate_win_loss_metrics(self, trades: List[Trade]) -> Dict:
        """Calculate win/loss metrics"""
        if not trades:
            return self._empty_win_loss_metrics()

        winning_trades = [t for t in trades if t.pnl_usd > 0]
        losing_trades = [t for t in trades if t.pnl_usd < 0]
        breakeven_trades = [t for t in trades if t.pnl_usd == 0]

        total_trades = len(trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)

        # Win rate
        win_rate_pct = (Decimal(str(num_winning)) / Decimal(str(total_trades))) * Decimal("100") if total_trades > 0 else Decimal("0")

        # Average win/loss
        avg_win_usd = sum(t.pnl_usd for t in winning_trades) / Decimal(str(num_winning)) if num_winning > 0 else Decimal("0")
        avg_loss_usd = sum(t.pnl_usd for t in losing_trades) / Decimal(str(num_losing)) if num_losing > 0 else Decimal("0")

        avg_win_pct = sum(t.pnl_pct for t in winning_trades) / Decimal(str(num_winning)) if num_winning > 0 else Decimal("0")
        avg_loss_pct = sum(t.pnl_pct for t in losing_trades) / Decimal(str(num_losing)) if num_losing > 0 else Decimal("0")

        # Profit factor
        gross_profit = sum(t.pnl_usd for t in winning_trades)
        gross_loss = abs(sum(t.pnl_usd for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("999")

        # Payoff ratio
        payoff_ratio = abs(avg_win_usd / avg_loss_usd) if avg_loss_usd != 0 else Decimal("999")

        # Average trade duration
        durations = []
        for t in trades:
            if t.exit_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 3600  # hours
                durations.append(duration)

        avg_duration_hours = Decimal(str(sum(durations) / len(durations))) if durations else Decimal("0")

        return {
            "total_trades": total_trades,
            "winning_trades": num_winning,
            "losing_trades": num_losing,
            "win_rate_pct": win_rate_pct,
            "profit_factor": profit_factor,
            "payoff_ratio": payoff_ratio,
            "avg_win_usd": avg_win_usd,
            "avg_loss_usd": avg_loss_usd,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_duration_hours": avg_duration_hours
        }

    def _calculate_sharpe_ratio(self, trades: List[Trade], annualized_return_pct: Decimal,
                                time_window: TimeWindow) -> Decimal:
        """
        Calculate Sharpe ratio: (Return - RiskFree) / Volatility

        Sharpe ratio measures risk-adjusted returns. Higher is better.
        >2.0 is excellent, >1.0 is good, <1.0 is poor.
        """
        if not trades:
            return Decimal("0")

        # Get daily returns
        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns:
            return Decimal("0")

        # Calculate volatility (std dev of daily returns)
        mean_return = sum(daily_returns) / Decimal(str(len(daily_returns)))
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(str(len(daily_returns)))
        daily_volatility = variance ** Decimal("0.5")

        # Annualize volatility
        annual_volatility = daily_volatility * (Decimal("252") ** Decimal("0.5"))  # 252 trading days

        if annual_volatility == 0:
            return Decimal("999")

        # Calculate Sharpe
        excess_return = annualized_return_pct - self.config.risk_free_rate_annual
        sharpe_ratio = excess_return / annual_volatility

        return sharpe_ratio

    def _calculate_sortino_ratio(self, trades: List[Trade], annualized_return_pct: Decimal,
                                 time_window: TimeWindow) -> Decimal:
        """
        Calculate Sortino ratio: (Return - RiskFree) / DownsideDeviation

        Similar to Sharpe but only penalizes downside volatility.
        Better measure for asymmetric returns.
        """
        if not trades:
            return Decimal("0")

        # Get daily returns
        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns:
            return Decimal("0")

        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in daily_returns if r < 0]

        if not negative_returns:
            return Decimal("999")  # No downside = infinite Sortino

        mean_negative = sum(negative_returns) / Decimal(str(len(negative_returns)))
        downside_variance = sum((r - mean_negative) ** 2 for r in negative_returns) / Decimal(str(len(negative_returns)))
        daily_downside_dev = downside_variance ** Decimal("0.5")

        # Annualize
        annual_downside_dev = daily_downside_dev * (Decimal("252") ** Decimal("0.5"))

        if annual_downside_dev == 0:
            return Decimal("999")

        # Calculate Sortino
        excess_return = annualized_return_pct - self.config.risk_free_rate_annual
        sortino_ratio = excess_return / annual_downside_dev

        return sortino_ratio

    def _calculate_calmar_ratio(self, annualized_return_pct: Decimal, trades: List[Trade]) -> Decimal:
        """
        Calculate Calmar ratio: AnnualizedReturn / MaxDrawdown

        Measures return relative to worst drawdown. Higher is better.
        >3.0 is excellent, >1.0 is good.
        """
        if not trades:
            return Decimal("0")

        drawdown_metrics = self._calculate_drawdown_metrics(trades)
        max_drawdown_pct = drawdown_metrics["max_drawdown_pct"]

        if max_drawdown_pct == 0:
            return Decimal("999")

        calmar_ratio = annualized_return_pct / max_drawdown_pct

        return calmar_ratio

    def _calculate_information_ratio(self, trades: List[Trade], time_window: TimeWindow) -> Decimal:
        """
        Calculate Information ratio: (Return - Benchmark) / TrackingError

        Measures excess return per unit of tracking error.
        Requires benchmark data.
        """
        # TODO: Implement when benchmark data is available
        return Decimal("0")

    def _calculate_omega_ratio(self, trades: List[Trade], threshold: Decimal = Decimal("0")) -> Decimal:
        """
        Calculate Omega ratio: Probability-weighted gains / losses

        Ratio of gains above threshold to losses below threshold.
        >1.0 means gains outweigh losses.
        """
        if not trades:
            return Decimal("0")

        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns:
            return Decimal("0")

        # Gains above threshold
        gains = sum(max(r - threshold, Decimal("0")) for r in daily_returns)

        # Losses below threshold
        losses = sum(max(threshold - r, Decimal("0")) for r in daily_returns)

        if losses == 0:
            return Decimal("999")

        omega_ratio = gains / losses

        return omega_ratio

    def _calculate_drawdown_metrics(self, trades: List[Trade]) -> Dict:
        """Calculate drawdown and recovery metrics"""
        if not trades:
            return {
                "max_drawdown_pct": Decimal("0"),
                "max_drawdown_usd": Decimal("0"),
                "current_drawdown_pct": Decimal("0"),
                "recovery_days": None,
                "time_underwater_days": 0
            }

        # Build equity curve
        equity = self.starting_equity
        peak_equity = equity
        max_drawdown_pct = Decimal("0")
        max_drawdown_usd = Decimal("0")

        drawdown_start_time = None
        recovery_time = None
        total_underwater_days = 0

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            equity += trade.pnl_usd

            # Update peak
            if equity > peak_equity:
                # Recovered from drawdown
                if drawdown_start_time and not recovery_time:
                    recovery_time = trade.exit_time
                    recovery_days = (recovery_time - drawdown_start_time).days

                peak_equity = equity
                drawdown_start_time = None
            else:
                # In drawdown
                if not drawdown_start_time:
                    drawdown_start_time = trade.exit_time

                drawdown_pct = ((peak_equity - equity) / peak_equity) * Decimal("100")
                drawdown_usd = peak_equity - equity

                if drawdown_pct > max_drawdown_pct:
                    max_drawdown_pct = drawdown_pct
                    max_drawdown_usd = drawdown_usd

                # Count underwater days
                total_underwater_days = (trade.exit_time - drawdown_start_time).days

        # Current drawdown
        current_equity = self.current_equity
        current_drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * Decimal("100")

        # Recovery days (for max drawdown)
        recovery_days = None
        if recovery_time and drawdown_start_time:
            recovery_days = (recovery_time - drawdown_start_time).days

        return {
            "max_drawdown_pct": max_drawdown_pct,
            "max_drawdown_usd": max_drawdown_usd,
            "current_drawdown_pct": current_drawdown_pct,
            "recovery_days": recovery_days,
            "time_underwater_days": total_underwater_days
        }

    def _calculate_volatility_metrics(self, trades: List[Trade], time_window: TimeWindow) -> Dict:
        """Calculate volatility metrics"""
        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns:
            return {
                "daily_volatility_pct": Decimal("0"),
                "annual_volatility_pct": Decimal("0"),
                "downside_deviation_pct": Decimal("0")
            }

        # Daily volatility
        mean_return = sum(daily_returns) / Decimal(str(len(daily_returns)))
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(str(len(daily_returns)))
        daily_volatility = variance ** Decimal("0.5")

        # Annual volatility
        annual_volatility = daily_volatility * (Decimal("252") ** Decimal("0.5"))

        # Downside deviation
        negative_returns = [r for r in daily_returns if r < 0]
        if negative_returns:
            mean_negative = sum(negative_returns) / Decimal(str(len(negative_returns)))
            downside_variance = sum((r - mean_negative) ** 2 for r in negative_returns) / Decimal(str(len(negative_returns)))
            downside_deviation = downside_variance ** Decimal("0.5")
        else:
            downside_deviation = Decimal("0")

        return {
            "daily_volatility_pct": daily_volatility * Decimal("100"),
            "annual_volatility_pct": annual_volatility * Decimal("100"),
            "downside_deviation_pct": downside_deviation * Decimal("100")
        }

    def _calculate_consistency_metrics(self, trades: List[Trade]) -> Dict:
        """Calculate consistency metrics"""
        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns:
            return {
                "best_day_return_pct": Decimal("0"),
                "worst_day_return_pct": Decimal("0"),
                "positive_days_pct": Decimal("0"),
                "monthly_consistency": Decimal("0")
            }

        # Best and worst day
        best_day = max(daily_returns)
        worst_day = min(daily_returns)

        # Positive days %
        positive_days = len([r for r in daily_returns if r > 0])
        positive_days_pct = (Decimal(str(positive_days)) / Decimal(str(len(daily_returns)))) * Decimal("100")

        # Monthly consistency (std dev of monthly returns)
        monthly_returns = self._calculate_monthly_returns(trades)
        if len(monthly_returns) > 1:
            mean_monthly = sum(monthly_returns) / Decimal(str(len(monthly_returns)))
            monthly_variance = sum((r - mean_monthly) ** 2 for r in monthly_returns) / Decimal(str(len(monthly_returns)))
            monthly_consistency = monthly_variance ** Decimal("0.5")
        else:
            monthly_consistency = Decimal("0")

        return {
            "best_day_return_pct": best_day * Decimal("100"),
            "worst_day_return_pct": worst_day * Decimal("100"),
            "positive_days_pct": positive_days_pct,
            "monthly_consistency": monthly_consistency * Decimal("100")
        }

    def _calculate_streak_metrics(self, trades: List[Trade]) -> Dict:
        """Calculate win/loss streak metrics"""
        if not trades:
            return {
                "current_win_streak": 0,
                "current_loss_streak": 0,
                "max_win_streak": 0,
                "max_loss_streak": 0
            }

        sorted_trades = sorted(trades, key=lambda t: t.exit_time or datetime.max)

        current_win_streak = 0
        current_loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0

        temp_win_streak = 0
        temp_loss_streak = 0

        for trade in sorted_trades:
            if trade.pnl_usd > 0:
                temp_win_streak += 1
                temp_loss_streak = 0

                if temp_win_streak > max_win_streak:
                    max_win_streak = temp_win_streak
            elif trade.pnl_usd < 0:
                temp_loss_streak += 1
                temp_win_streak = 0

                if temp_loss_streak > max_loss_streak:
                    max_loss_streak = temp_loss_streak

        # Current streaks
        current_win_streak = temp_win_streak
        current_loss_streak = temp_loss_streak

        return {
            "current_win_streak": current_win_streak,
            "current_loss_streak": current_loss_streak,
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak
        }

    def _calculate_daily_returns(self, trades: List[Trade]) -> List[Decimal]:
        """Calculate daily returns from trades"""
        if not trades:
            return []

        # Group trades by day
        daily_pnl: Dict[str, Decimal] = {}
        daily_equity: Dict[str, Decimal] = {}

        equity = self.starting_equity

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            day_key = trade.exit_time.strftime("%Y-%m-%d")

            if day_key not in daily_pnl:
                daily_pnl[day_key] = Decimal("0")
                daily_equity[day_key] = equity

            daily_pnl[day_key] += trade.pnl_usd
            equity += trade.pnl_usd

        # Calculate daily returns
        daily_returns = []
        for day_key in sorted(daily_pnl.keys()):
            pnl = daily_pnl[day_key]
            starting_equity = daily_equity[day_key]

            if starting_equity > 0:
                daily_return = pnl / starting_equity
                daily_returns.append(daily_return)

        return daily_returns

    def _calculate_monthly_returns(self, trades: List[Trade]) -> List[Decimal]:
        """Calculate monthly returns from trades"""
        if not trades:
            return []

        # Group trades by month
        monthly_pnl: Dict[str, Decimal] = {}
        monthly_equity: Dict[str, Decimal] = {}

        equity = self.starting_equity

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            month_key = trade.exit_time.strftime("%Y-%m")

            if month_key not in monthly_pnl:
                monthly_pnl[month_key] = Decimal("0")
                monthly_equity[month_key] = equity

            monthly_pnl[month_key] += trade.pnl_usd
            equity += trade.pnl_usd

        # Calculate monthly returns
        monthly_returns = []
        for month_key in sorted(monthly_pnl.keys()):
            pnl = monthly_pnl[month_key]
            starting_equity = monthly_equity[month_key]

            if starting_equity > 0:
                monthly_return = pnl / starting_equity
                monthly_returns.append(monthly_return)

        return monthly_returns

    def _check_statistical_significance(self, trades: List[Trade]) -> Tuple[bool, Decimal]:
        """Check if results are statistically significant"""
        if len(trades) < self.config.min_trades_for_significance:
            return False, Decimal("0")

        # Use t-test to check if mean return is significantly different from 0
        daily_returns = self._calculate_daily_returns(trades)

        if not daily_returns or len(daily_returns) < 2:
            return False, Decimal("0")

        # Calculate t-statistic
        n = len(daily_returns)
        mean_return = sum(daily_returns) / Decimal(str(n))

        variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(str(n - 1))
        std_dev = variance ** Decimal("0.5")

        if std_dev == 0:
            return True, Decimal("100")

        t_stat = mean_return / (std_dev / (Decimal(str(n)) ** Decimal("0.5")))

        # Approximate p-value (simplified)
        # For t-stat > 2.0, roughly 95% confidence
        # For t-stat > 2.6, roughly 99% confidence
        if abs(t_stat) > Decimal("2.6"):
            is_significant = True
            confidence = Decimal("99.0")
        elif abs(t_stat) > Decimal("2.0"):
            is_significant = True
            confidence = Decimal("95.0")
        elif abs(t_stat) > Decimal("1.6"):
            is_significant = False
            confidence = Decimal("90.0")
        else:
            is_significant = False
            confidence = Decimal("50.0")

        return is_significant, confidence

    def _create_empty_metrics(self, time_window: TimeWindow) -> PerformanceMetrics:
        """Create empty metrics object"""
        return PerformanceMetrics(
            calculation_time=datetime.now(),
            time_window=time_window,
            total_return_pct=Decimal("0"),
            annualized_return_pct=Decimal("0"),
            cumulative_pnl_usd=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            calmar_ratio=Decimal("0"),
            information_ratio=Decimal("0"),
            omega_ratio=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=Decimal("0"),
            profit_factor=Decimal("0"),
            payoff_ratio=Decimal("0"),
            avg_win_usd=Decimal("0"),
            avg_loss_usd=Decimal("0"),
            avg_win_pct=Decimal("0"),
            avg_loss_pct=Decimal("0"),
            avg_trade_duration_hours=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            max_drawdown_usd=Decimal("0"),
            current_drawdown_pct=Decimal("0"),
            drawdown_recovery_days=None,
            time_underwater_days=0,
            current_win_streak=0,
            current_loss_streak=0,
            max_win_streak=0,
            max_loss_streak=0,
            daily_volatility_pct=Decimal("0"),
            annual_volatility_pct=Decimal("0"),
            downside_deviation_pct=Decimal("0"),
            best_day_return_pct=Decimal("0"),
            worst_day_return_pct=Decimal("0"),
            positive_days_pct=Decimal("0"),
            monthly_return_consistency=Decimal("0"),
            is_statistically_significant=False,
            confidence_level_pct=Decimal("0"),
            min_trades_met=False
        )

    def _empty_win_loss_metrics(self) -> Dict:
        """Create empty win/loss metrics"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": Decimal("0"),
            "profit_factor": Decimal("0"),
            "payoff_ratio": Decimal("0"),
            "avg_win_usd": Decimal("0"),
            "avg_loss_usd": Decimal("0"),
            "avg_win_pct": Decimal("0"),
            "avg_loss_pct": Decimal("0"),
            "avg_duration_hours": Decimal("0")
        }

    def get_metrics(self, time_window: TimeWindow = TimeWindow.ALL_TIME) -> Optional[PerformanceMetrics]:
        """Get cached metrics for a time window"""
        return self.metrics_by_window.get(time_window)

    def print_metrics_summary(self, time_window: TimeWindow = TimeWindow.ALL_TIME):
        """Print a summary of performance metrics"""
        metrics = self.get_metrics(time_window)

        if not metrics:
            print(f"No metrics available for {time_window.value}")
            return

        print(f"\n{'='*80}")
        print(f"PERFORMANCE METRICS - {time_window.value.upper()}")
        print(f"Calculated: {metrics.calculation_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")

        print(f"RETURNS:")
        print(f"  Total Return:      {metrics.total_return_pct:>10.2f}%")
        print(f"  Annualized Return: {metrics.annualized_return_pct:>10.2f}%")
        print(f"  Cumulative P&L:    ${metrics.cumulative_pnl_usd:>10,.2f}")

        print(f"\nRISK-ADJUSTED METRICS:")
        print(f"  Sharpe Ratio:      {metrics.sharpe_ratio:>10.2f} {'✓ Excellent' if metrics.sharpe_ratio >= self.config.target_sharpe_ratio else '✗ Below target'}")
        print(f"  Sortino Ratio:     {metrics.sortino_ratio:>10.2f}")
        print(f"  Calmar Ratio:      {metrics.calmar_ratio:>10.2f}")
        print(f"  Omega Ratio:       {metrics.omega_ratio:>10.2f}")

        print(f"\nWIN/LOSS METRICS:")
        print(f"  Total Trades:      {metrics.total_trades:>10,}")
        print(f"  Win Rate:          {metrics.win_rate_pct:>10.1f}% {'✓' if metrics.win_rate_pct >= self.config.target_win_rate_pct else '✗'}")
        print(f"  Profit Factor:     {metrics.profit_factor:>10.2f} {'✓' if metrics.profit_factor >= self.config.target_profit_factor else '✗'}")
        print(f"  Payoff Ratio:      {metrics.payoff_ratio:>10.2f}")

        print(f"\nAVERAGES:")
        print(f"  Avg Win:           ${metrics.avg_win_usd:>10,.2f} ({metrics.avg_win_pct:>6.2f}%)")
        print(f"  Avg Loss:          ${metrics.avg_loss_usd:>10,.2f} ({metrics.avg_loss_pct:>6.2f}%)")
        print(f"  Avg Duration:      {metrics.avg_trade_duration_hours:>10.1f} hours")

        print(f"\nDRAWDOWN:")
        print(f"  Max Drawdown:      {metrics.max_drawdown_pct:>10.2f}% (${metrics.max_drawdown_usd:>10,.2f})")
        print(f"  Current Drawdown:  {metrics.current_drawdown_pct:>10.2f}%")
        print(f"  Recovery Time:     {metrics.drawdown_recovery_days if metrics.drawdown_recovery_days else 'N/A':>10} days")
        print(f"  Time Underwater:   {metrics.time_underwater_days:>10} days")

        print(f"\nVOLATILITY:")
        print(f"  Daily Volatility:  {metrics.daily_volatility_pct:>10.2f}%")
        print(f"  Annual Volatility: {metrics.annual_volatility_pct:>10.2f}%")
        print(f"  Downside Dev:      {metrics.downside_deviation_pct:>10.2f}%")

        print(f"\nCONSISTENCY:")
        print(f"  Best Day:          {metrics.best_day_return_pct:>10.2f}%")
        print(f"  Worst Day:         {metrics.worst_day_return_pct:>10.2f}%")
        print(f"  Positive Days:     {metrics.positive_days_pct:>10.1f}%")

        print(f"\nSTREAKS:")
        print(f"  Current Win:       {metrics.current_win_streak:>10}")
        print(f"  Current Loss:      {metrics.current_loss_streak:>10}")
        print(f"  Max Win Streak:    {metrics.max_win_streak:>10}")
        print(f"  Max Loss Streak:   {metrics.max_loss_streak:>10}")

        print(f"\nSTATISTICAL SIGNIFICANCE:")
        print(f"  Significant:       {metrics.is_statistically_significant}")
        print(f"  Confidence:        {metrics.confidence_level_pct:.1f}%")
        print(f"  Min Trades Met:    {metrics.min_trades_met}")

        print(f"\n{'='*80}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize engine
        config = PerformanceConfig()
        engine = PerformanceMetricsEngine(config)

        # Add sample trades
        print("Adding sample trades...")

        for i in range(100):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=f"0xwhale{i % 5}",
                market_id=f"market_{i % 10}",
                market_topic="Politics" if i % 2 == 0 else "Crypto",
                side="BUY" if i % 3 == 0 else "SELL",
                entry_price=Decimal("0.55"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.52"),
                position_size_usd=Decimal("1000"),
                entry_time=datetime.now() - timedelta(days=100-i),
                exit_time=datetime.now() - timedelta(days=100-i-1),
                pnl_usd=Decimal("50") if i % 2 == 0 else Decimal("-30"),
                pnl_pct=Decimal("5.0") if i % 2 == 0 else Decimal("-3.0"),
                is_open=False,
                fees_paid_usd=Decimal("2"),
                slippage_pct=Decimal("0.5")
            )
            engine.add_trade(trade)

        print(f"Added {len(engine.trades)} trades")

        # Calculate metrics
        print("\nCalculating metrics...")

        # All time
        metrics_all = await engine.calculate_metrics(TimeWindow.ALL_TIME)
        engine.print_metrics_summary(TimeWindow.ALL_TIME)

        # Monthly
        metrics_monthly = await engine.calculate_metrics(TimeWindow.MONTHLY)
        engine.print_metrics_summary(TimeWindow.MONTHLY)

        # Start background updates
        await engine.start()

        # Let it run for a bit
        await asyncio.sleep(5)

        # Stop
        await engine.stop()

        print("Performance metrics engine demo complete!")

    asyncio.run(main())
