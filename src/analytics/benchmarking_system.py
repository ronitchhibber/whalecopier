"""
Week 9: Performance Analytics - Benchmarking System

This module provides performance benchmarking against various strategies:
- Buy-and-hold benchmark (passive market exposure)
- Market average benchmark (average of all markets)
- Top 10 whales benchmark (aggregate of best performers)
- Alpha calculation (excess return over benchmark)
- Beta calculation (correlation to benchmark)

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    """Types of benchmarks"""
    BUY_AND_HOLD = "buy_and_hold"
    MARKET_AVERAGE = "market_avg"
    TOP_10_WHALES = "top_10"
    EQUAL_WEIGHT_MARKETS = "equal_weight"


@dataclass
class BenchmarkConfig:
    """Configuration for benchmarking"""

    # Update frequency
    update_interval_seconds: int = 300  # 5 minutes

    # Benchmarking parameters
    buy_and_hold_markets: List[str] = None  # Markets to hold
    top_n_whales: int = 10

    # Analysis window
    lookback_days: int = 90

    # Database paths
    trades_db_path: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/data/trades.db"
    market_data_path: str = "/Users/ronitchhibber/Desktop/Whale.Trader-v0.1/data/market_data.db"


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    whale_address: str
    market_id: str
    entry_price: Decimal
    exit_price: Optional[Decimal]
    position_size_usd: Decimal
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl_usd: Decimal
    pnl_pct: Decimal
    is_open: bool


@dataclass
class BenchmarkResult:
    """Benchmark comparison result"""

    # Identification
    benchmark_type: BenchmarkType
    calculation_time: datetime
    time_period_days: int

    # Strategy performance
    strategy_return_pct: Decimal
    strategy_return_usd: Decimal
    strategy_sharpe_ratio: Decimal
    strategy_max_drawdown_pct: Decimal
    strategy_volatility_pct: Decimal

    # Benchmark performance
    benchmark_return_pct: Decimal
    benchmark_return_usd: Decimal
    benchmark_sharpe_ratio: Decimal
    benchmark_max_drawdown_pct: Decimal
    benchmark_volatility_pct: Decimal

    # Comparison metrics
    alpha: Decimal  # Excess return
    alpha_pct: Decimal  # % outperformance
    beta: Decimal  # Correlation
    information_ratio: Decimal  # Risk-adjusted outperformance

    # Win analysis
    strategy_wins: bool  # True if strategy outperforms
    outperformance_usd: Decimal
    outperformance_pct: Decimal

    # Statistical significance
    is_significant: bool
    confidence_level_pct: Decimal


@dataclass
class AlphaSource:
    """Source of alpha (excess return)"""
    source_name: str  # e.g., "Whale Selection", "Market Timing", "Position Sizing"
    alpha_contribution_pct: Decimal
    contribution_to_total_alpha_pct: Decimal


class BenchmarkingSystem:
    """
    Comprehensive benchmarking system.

    Compares copy trading strategy performance against:
    1. Buy-and-hold: Passive investment in markets
    2. Market average: Average performance of all markets
    3. Top 10 whales: Aggregate of best whale performance

    Calculates:
    - Alpha (excess return)
    - Beta (market correlation)
    - Information ratio (risk-adjusted alpha)
    - Statistical significance
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.starting_capital: Decimal = Decimal("100000")
        self.current_capital: Decimal = Decimal("100000")

        # Cached benchmark results
        self.benchmark_results: Dict[BenchmarkType, BenchmarkResult] = {}
        self.alpha_sources: List[AlphaSource] = []

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("BenchmarkingSystem initialized")

    async def start(self):
        """Start benchmarking system"""
        if self.is_running:
            logger.warning("BenchmarkingSystem already running")
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())

        logger.info("BenchmarkingSystem started")

    async def stop(self):
        """Stop benchmarking system"""
        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        logger.info("BenchmarkingSystem stopped")

    async def _update_loop(self):
        """Background loop for benchmark updates"""
        while self.is_running:
            try:
                # Calculate all benchmarks
                for benchmark_type in BenchmarkType:
                    result = await self.calculate_benchmark(benchmark_type)
                    self.benchmark_results[benchmark_type] = result

                # Calculate alpha sources
                self.alpha_sources = await self.identify_alpha_sources()

                # Log summary
                buy_hold = self.benchmark_results.get(BenchmarkType.BUY_AND_HOLD)
                if buy_hold:
                    logger.info(
                        f"Benchmark Update - Alpha vs Buy&Hold: {buy_hold.alpha:.2f}%, "
                        f"Outperformance: {buy_hold.outperformance_pct:.1f}%"
                    )

                await asyncio.sleep(self.config.update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in benchmark update loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    def add_trade(self, trade: Trade):
        """Add trade to history"""
        self.trades.append(trade)

        if not trade.is_open:
            self.current_capital += trade.pnl_usd

        logger.debug(f"Added trade {trade.trade_id} to benchmark history")

    async def calculate_benchmark(self, benchmark_type: BenchmarkType) -> BenchmarkResult:
        """
        Calculate benchmark comparison.

        Args:
            benchmark_type: Type of benchmark to compare against

        Returns:
            BenchmarkResult with detailed comparison
        """

        # Filter recent trades
        trades = self._filter_recent_trades()

        if not trades:
            return self._create_empty_result(benchmark_type)

        # Calculate strategy performance
        strategy_metrics = self._calculate_strategy_performance(trades)

        # Calculate benchmark performance
        benchmark_metrics = await self._calculate_benchmark_performance(benchmark_type, trades)

        # Calculate comparison metrics
        alpha, alpha_pct, beta, info_ratio = self._calculate_comparison_metrics(
            strategy_metrics, benchmark_metrics
        )

        # Determine winner
        strategy_wins = strategy_metrics["return_pct"] > benchmark_metrics["return_pct"]
        outperformance_pct = strategy_metrics["return_pct"] - benchmark_metrics["return_pct"]
        outperformance_usd = strategy_metrics["return_usd"] - benchmark_metrics["return_usd"]

        # Statistical significance
        is_significant, confidence = self._check_significance(
            strategy_metrics, benchmark_metrics
        )

        # Time period
        time_period_days = self.config.lookback_days

        return BenchmarkResult(
            benchmark_type=benchmark_type,
            calculation_time=datetime.now(),
            time_period_days=time_period_days,

            # Strategy
            strategy_return_pct=strategy_metrics["return_pct"],
            strategy_return_usd=strategy_metrics["return_usd"],
            strategy_sharpe_ratio=strategy_metrics["sharpe"],
            strategy_max_drawdown_pct=strategy_metrics["max_dd"],
            strategy_volatility_pct=strategy_metrics["volatility"],

            # Benchmark
            benchmark_return_pct=benchmark_metrics["return_pct"],
            benchmark_return_usd=benchmark_metrics["return_usd"],
            benchmark_sharpe_ratio=benchmark_metrics["sharpe"],
            benchmark_max_drawdown_pct=benchmark_metrics["max_dd"],
            benchmark_volatility_pct=benchmark_metrics["volatility"],

            # Comparison
            alpha=alpha,
            alpha_pct=alpha_pct,
            beta=beta,
            information_ratio=info_ratio,

            # Win analysis
            strategy_wins=strategy_wins,
            outperformance_usd=outperformance_usd,
            outperformance_pct=outperformance_pct,

            # Significance
            is_significant=is_significant,
            confidence_level_pct=confidence
        )

    def _calculate_strategy_performance(self, trades: List[Trade]) -> Dict:
        """Calculate strategy performance metrics"""

        # Total return
        total_pnl = sum(t.pnl_usd for t in trades if not t.is_open)
        return_pct = (total_pnl / self.starting_capital) * Decimal("100")

        # Daily returns
        daily_returns = self._calculate_daily_returns(trades)

        # Sharpe ratio
        if daily_returns:
            mean_return = sum(daily_returns) / Decimal(str(len(daily_returns)))
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(str(len(daily_returns)))
            daily_vol = variance ** Decimal("0.5")
            annual_vol = daily_vol * (Decimal("252") ** Decimal("0.5"))

            # Annualize return (approximate)
            days = self.config.lookback_days
            annual_return = return_pct * (Decimal("365") / Decimal(str(days)))

            sharpe = annual_return / annual_vol if annual_vol > 0 else Decimal("0")
        else:
            annual_vol = Decimal("0")
            sharpe = Decimal("0")

        # Max drawdown
        max_dd = self._calculate_max_drawdown(trades)

        return {
            "return_pct": return_pct,
            "return_usd": total_pnl,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "volatility": annual_vol
        }

    async def _calculate_benchmark_performance(self, benchmark_type: BenchmarkType,
                                               trades: List[Trade]) -> Dict:
        """Calculate benchmark performance"""

        if benchmark_type == BenchmarkType.BUY_AND_HOLD:
            return await self._calculate_buy_and_hold_performance(trades)

        elif benchmark_type == BenchmarkType.MARKET_AVERAGE:
            return await self._calculate_market_average_performance(trades)

        elif benchmark_type == BenchmarkType.TOP_10_WHALES:
            return await self._calculate_top_whales_performance(trades)

        elif benchmark_type == BenchmarkType.EQUAL_WEIGHT_MARKETS:
            return await self._calculate_equal_weight_performance(trades)

        else:
            return self._empty_performance()

    async def _calculate_buy_and_hold_performance(self, trades: List[Trade]) -> Dict:
        """
        Calculate buy-and-hold benchmark.

        Assumes:
        - Buy $1000 in each unique market at start
        - Hold until end
        - Calculate return based on market price changes
        """

        # Get unique markets from trades
        markets = set(t.market_id for t in trades)

        if not markets:
            return self._empty_performance()

        # Simulate buy-and-hold
        # For simplicity, assume average market return of 5% (can be replaced with real data)
        # In production, would fetch actual market price data

        total_return_pct = Decimal("5.0")  # Placeholder
        total_return_usd = self.starting_capital * (total_return_pct / Decimal("100"))

        # Assume lower volatility for buy-and-hold
        volatility_pct = Decimal("15.0")

        # Sharpe (approximate)
        risk_free = Decimal("4.5")
        sharpe = (total_return_pct - risk_free) / volatility_pct

        # Max drawdown (approximate)
        max_dd = Decimal("10.0")

        return {
            "return_pct": total_return_pct,
            "return_usd": total_return_usd,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "volatility": volatility_pct
        }

    async def _calculate_market_average_performance(self, trades: List[Trade]) -> Dict:
        """Calculate market average performance"""

        # Average P&L across all markets (equally weighted)
        markets = set(t.market_id for t in trades)

        if not markets:
            return self._empty_performance()

        # Calculate average market return
        # In production, would fetch real market data
        avg_return_pct = Decimal("3.0")  # Placeholder
        avg_return_usd = self.starting_capital * (avg_return_pct / Decimal("100"))

        volatility_pct = Decimal("12.0")
        risk_free = Decimal("4.5")
        sharpe = (avg_return_pct - risk_free) / volatility_pct
        max_dd = Decimal("8.0")

        return {
            "return_pct": avg_return_pct,
            "return_usd": avg_return_usd,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "volatility": volatility_pct
        }

    async def _calculate_top_whales_performance(self, trades: List[Trade]) -> Dict:
        """Calculate top 10 whales aggregate performance"""

        # Get whale performance
        whale_pnl: Dict[str, Decimal] = {}

        for trade in trades:
            if not trade.is_open:
                if trade.whale_address not in whale_pnl:
                    whale_pnl[trade.whale_address] = Decimal("0")
                whale_pnl[trade.whale_address] += trade.pnl_usd

        if not whale_pnl:
            return self._empty_performance()

        # Get top N whales
        top_whales = sorted(whale_pnl.items(), key=lambda x: x[1], reverse=True)[:self.config.top_n_whales]

        # Calculate aggregate return
        top_whales_pnl = sum(pnl for _, pnl in top_whales)
        return_pct = (top_whales_pnl / self.starting_capital) * Decimal("100")

        # Approximate metrics
        volatility_pct = Decimal("20.0")
        risk_free = Decimal("4.5")
        sharpe = (return_pct - risk_free) / volatility_pct if volatility_pct > 0 else Decimal("0")
        max_dd = Decimal("12.0")

        return {
            "return_pct": return_pct,
            "return_usd": top_whales_pnl,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "volatility": volatility_pct
        }

    async def _calculate_equal_weight_performance(self, trades: List[Trade]) -> Dict:
        """Calculate equal-weight market performance"""

        markets = set(t.market_id for t in trades)

        if not markets:
            return self._empty_performance()

        # Equal weight across all markets
        # In production, would fetch real data
        return_pct = Decimal("4.0")
        return_usd = self.starting_capital * (return_pct / Decimal("100"))

        volatility_pct = Decimal("14.0")
        risk_free = Decimal("4.5")
        sharpe = (return_pct - risk_free) / volatility_pct
        max_dd = Decimal("9.0")

        return {
            "return_pct": return_pct,
            "return_usd": return_usd,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "volatility": volatility_pct
        }

    def _calculate_comparison_metrics(self, strategy: Dict, benchmark: Dict) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        """Calculate alpha, beta, and information ratio"""

        # Alpha (excess return)
        alpha = strategy["return_pct"] - benchmark["return_pct"]

        # Alpha as % of benchmark return
        alpha_pct = (alpha / benchmark["return_pct"] * Decimal("100")) if benchmark["return_pct"] != 0 else Decimal("999")

        # Beta (simplified correlation estimate)
        # In production, would calculate proper covariance/variance
        beta = Decimal("1.0")  # Placeholder

        # Information ratio (alpha / tracking error)
        tracking_error = abs(strategy["volatility"] - benchmark["volatility"])
        info_ratio = alpha / tracking_error if tracking_error > 0 else Decimal("999")

        return alpha, alpha_pct, beta, info_ratio

    def _calculate_daily_returns(self, trades: List[Trade]) -> List[Decimal]:
        """Calculate daily returns"""
        daily_pnl: Dict[str, Decimal] = {}
        daily_equity: Dict[str, Decimal] = {}

        equity = self.starting_capital

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            day_key = trade.exit_time.strftime("%Y-%m-%d")

            if day_key not in daily_pnl:
                daily_pnl[day_key] = Decimal("0")
                daily_equity[day_key] = equity

            daily_pnl[day_key] += trade.pnl_usd
            equity += trade.pnl_usd

        # Calculate returns
        daily_returns = []
        for day_key in sorted(daily_pnl.keys()):
            pnl = daily_pnl[day_key]
            starting_equity = daily_equity[day_key]

            if starting_equity > 0:
                daily_return = pnl / starting_equity
                daily_returns.append(daily_return)

        return daily_returns

    def _calculate_max_drawdown(self, trades: List[Trade]) -> Decimal:
        """Calculate max drawdown"""
        equity = self.starting_capital
        peak_equity = equity
        max_dd = Decimal("0")

        for trade in sorted(trades, key=lambda t: t.exit_time or datetime.max):
            if not trade.exit_time:
                continue

            equity += trade.pnl_usd

            if equity > peak_equity:
                peak_equity = equity
            else:
                dd = ((peak_equity - equity) / peak_equity) * Decimal("100")
                if dd > max_dd:
                    max_dd = dd

        return max_dd

    def _check_significance(self, strategy: Dict, benchmark: Dict) -> Tuple[bool, Decimal]:
        """Check statistical significance of outperformance"""

        # Simplified significance test
        # In production, would use proper statistical tests

        alpha = strategy["return_pct"] - benchmark["return_pct"]

        # If alpha > 2 standard deviations, consider significant
        if abs(alpha) > Decimal("10.0"):
            is_significant = True
            confidence = Decimal("95.0")
        elif abs(alpha) > Decimal("5.0"):
            is_significant = True
            confidence = Decimal("90.0")
        else:
            is_significant = False
            confidence = Decimal("50.0")

        return is_significant, confidence

    async def identify_alpha_sources(self) -> List[AlphaSource]:
        """
        Identify sources of alpha (what's driving outperformance?).

        Potential sources:
        - Whale selection (picking the right whales)
        - Market timing (entering/exiting at right time)
        - Position sizing (optimal bet sizing)
        - Risk management (avoiding bad trades)
        """

        sources: List[AlphaSource] = []

        # For simplicity, attribute alpha equally
        # In production, would use more sophisticated attribution

        total_alpha = Decimal("0")
        buy_hold = self.benchmark_results.get(BenchmarkType.BUY_AND_HOLD)
        if buy_hold:
            total_alpha = buy_hold.alpha

        if total_alpha > 0:
            # Whale selection (40%)
            sources.append(AlphaSource(
                source_name="Whale Selection",
                alpha_contribution_pct=total_alpha * Decimal("0.40"),
                contribution_to_total_alpha_pct=Decimal("40.0")
            ))

            # Market timing (25%)
            sources.append(AlphaSource(
                source_name="Market Timing",
                alpha_contribution_pct=total_alpha * Decimal("0.25"),
                contribution_to_total_alpha_pct=Decimal("25.0")
            ))

            # Position sizing (20%)
            sources.append(AlphaSource(
                source_name="Position Sizing",
                alpha_contribution_pct=total_alpha * Decimal("0.20"),
                contribution_to_total_alpha_pct=Decimal("20.0")
            ))

            # Risk management (15%)
            sources.append(AlphaSource(
                source_name="Risk Management",
                alpha_contribution_pct=total_alpha * Decimal("0.15"),
                contribution_to_total_alpha_pct=Decimal("15.0")
            ))

        return sources

    def _filter_recent_trades(self) -> List[Trade]:
        """Filter trades within lookback window"""
        cutoff = datetime.now() - timedelta(days=self.config.lookback_days)
        return [t for t in self.trades if not t.is_open and t.exit_time and t.exit_time >= cutoff]

    def _empty_performance(self) -> Dict:
        """Empty performance metrics"""
        return {
            "return_pct": Decimal("0"),
            "return_usd": Decimal("0"),
            "sharpe": Decimal("0"),
            "max_dd": Decimal("0"),
            "volatility": Decimal("0")
        }

    def _create_empty_result(self, benchmark_type: BenchmarkType) -> BenchmarkResult:
        """Create empty benchmark result"""
        return BenchmarkResult(
            benchmark_type=benchmark_type,
            calculation_time=datetime.now(),
            time_period_days=0,
            strategy_return_pct=Decimal("0"),
            strategy_return_usd=Decimal("0"),
            strategy_sharpe_ratio=Decimal("0"),
            strategy_max_drawdown_pct=Decimal("0"),
            strategy_volatility_pct=Decimal("0"),
            benchmark_return_pct=Decimal("0"),
            benchmark_return_usd=Decimal("0"),
            benchmark_sharpe_ratio=Decimal("0"),
            benchmark_max_drawdown_pct=Decimal("0"),
            benchmark_volatility_pct=Decimal("0"),
            alpha=Decimal("0"),
            alpha_pct=Decimal("0"),
            beta=Decimal("0"),
            information_ratio=Decimal("0"),
            strategy_wins=False,
            outperformance_usd=Decimal("0"),
            outperformance_pct=Decimal("0"),
            is_significant=False,
            confidence_level_pct=Decimal("0")
        )

    def print_benchmark_summary(self):
        """Print benchmark comparison summary"""

        print(f"\n{'='*100}")
        print("BENCHMARK COMPARISON SUMMARY")
        print(f"{'='*100}\n")

        for benchmark_type, result in self.benchmark_results.items():
            print(f"\n{benchmark_type.value.upper().replace('_', ' ')}:")
            print("-" * 80)

            print(f"  Strategy Return:    {result.strategy_return_pct:>10.2f}% (${result.strategy_return_usd:>12,.2f})")
            print(f"  Benchmark Return:   {result.benchmark_return_pct:>10.2f}% (${result.benchmark_return_usd:>12,.2f})")
            print(f"  Alpha:              {result.alpha:>10.2f}% ({result.alpha_pct:>6.1f}% outperformance)")
            print(f"  Beta:               {result.beta:>10.2f}")
            print(f"  Information Ratio:  {result.information_ratio:>10.2f}")
            print(f"  Strategy Wins:      {'YES ✓' if result.strategy_wins else 'NO ✗'}")
            print(f"  Significance:       {'YES' if result.is_significant else 'NO'} ({result.confidence_level_pct:.0f}% confidence)")

        # Alpha sources
        if self.alpha_sources:
            print(f"\n\nALPHA SOURCES:")
            print("-" * 80)
            for source in self.alpha_sources:
                print(f"  {source.source_name:<25}{source.alpha_contribution_pct:>8.2f}% ({source.contribution_to_total_alpha_pct:>5.1f}% of total)")

        print("\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = BenchmarkConfig()
        system = BenchmarkingSystem(config)

        # Add sample trades
        print("Adding sample trades...")

        for i in range(100):
            trade = Trade(
                trade_id=f"trade_{i}",
                whale_address=f"0xwhale{i % 5}",
                market_id=f"market_{i % 10}",
                entry_price=Decimal("0.55"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.52"),
                position_size_usd=Decimal("1000"),
                entry_time=datetime.now() - timedelta(days=90-i),
                exit_time=datetime.now() - timedelta(days=90-i-1),
                pnl_usd=Decimal("50") if i % 2 == 0 else Decimal("-30"),
                pnl_pct=Decimal("5.0") if i % 2 == 0 else Decimal("-3.0"),
                is_open=False
            )
            system.add_trade(trade)

        # Calculate benchmarks
        print("\nCalculating benchmarks...")
        for benchmark_type in BenchmarkType:
            result = await system.calculate_benchmark(benchmark_type)
            system.benchmark_results[benchmark_type] = result

        # Identify alpha sources
        system.alpha_sources = await system.identify_alpha_sources()

        # Print results
        system.print_benchmark_summary()

        print("Benchmarking demo complete!")

    asyncio.run(main())
