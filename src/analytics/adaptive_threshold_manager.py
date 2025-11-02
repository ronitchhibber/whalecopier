"""
Week 10: Edge Detection & Decay - Adaptive Threshold Manager

This module manages dynamic thresholds based on market conditions:
- Higher edge thresholds in high-volatility periods
- Lower edge thresholds in stable periods
- Backtested threshold optimization
- Real-time threshold adjustment

Concept: In volatile markets, higher edge is needed to overcome noise.
In stable markets, lower edge can still be profitable.

Author: Whale Copy Trading System
Date: 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market volatility regimes"""
    VERY_LOW_VOL = "very_low"
    LOW_VOL = "low"
    NORMAL = "normal"
    HIGH_VOL = "high"
    VERY_HIGH_VOL = "very_high"


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive thresholds"""

    # Base thresholds (normal volatility)
    base_min_edge_threshold: Decimal = Decimal("0.05")
    base_good_edge_threshold: Decimal = Decimal("0.10")
    base_excellent_edge_threshold: Decimal = Decimal("0.15")

    # Volatility measurement
    volatility_lookback_days: int = 30
    volatility_calculation_method: str = "returns_std"  # or "atr", "historical_vol"

    # Regime thresholds (annualized volatility %)
    very_low_vol_threshold: Decimal = Decimal("5.0")
    low_vol_threshold: Decimal = Decimal("10.0")
    high_vol_threshold: Decimal = Decimal("20.0")
    very_high_vol_threshold: Decimal = Decimal("30.0")

    # Adjustment factors
    very_low_vol_multiplier: Decimal = Decimal("0.70")  # 30% lower thresholds
    low_vol_multiplier: Decimal = Decimal("0.85")       # 15% lower
    normal_multiplier: Decimal = Decimal("1.00")        # No change
    high_vol_multiplier: Decimal = Decimal("1.25")      # 25% higher
    very_high_vol_multiplier: Decimal = Decimal("1.50") # 50% higher

    # Update frequency
    update_interval_seconds: int = 300


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: Decimal
    exit_price: Optional[Decimal]
    pnl_usd: Decimal
    pnl_pct: Decimal
    is_open: bool


@dataclass
class ThresholdSet:
    """Set of adaptive thresholds"""

    calculation_time: datetime
    market_regime: MarketRegime
    current_volatility: Decimal

    # Adapted thresholds
    min_edge_threshold: Decimal
    good_edge_threshold: Decimal
    excellent_edge_threshold: Decimal

    # Adjustment details
    adjustment_multiplier: Decimal
    base_min_edge: Decimal
    base_good_edge: Decimal
    base_excellent_edge: Decimal

    # Performance
    regime_duration_days: int
    trades_in_regime: int
    avg_profitability_in_regime: Decimal


class AdaptiveThresholdManager:
    """
    Manages adaptive edge thresholds based on market volatility.

    Key concept:
    - High volatility = Higher edge needed (more noise to overcome)
    - Low volatility = Lower edge acceptable (signals are clearer)

    Example:
    - Normal market: Min edge = 0.05
    - High volatility (+25% adjustment): Min edge = 0.0625
    - Low volatility (-15% adjustment): Min edge = 0.0425

    This prevents:
    - False positives in volatile markets (noise mistaken for edge)
    - Missing opportunities in stable markets (real edge dismissed)
    """

    def __init__(self, config: AdaptiveConfig):
        self.config = config

        # State
        self.trades: List[Trade] = []
        self.current_thresholds: Optional[ThresholdSet] = None
        self.current_regime: MarketRegime = MarketRegime.NORMAL
        self.regime_start_time: datetime = datetime.now()

        # History
        self.threshold_history: List[ThresholdSet] = []
        self.regime_history: List[tuple] = []  # (regime, start_time, end_time)

        # Background task
        self.update_task: Optional[asyncio.Task] = None
        self.is_running: bool = False

        logger.info("AdaptiveThresholdManager initialized")

    async def start(self):
        """Start manager"""
        if self.is_running:
            return

        self.is_running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("AdaptiveThresholdManager started")

    async def stop(self):
        """Stop manager"""
        self.is_running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("AdaptiveThresholdManager stopped")

    async def _update_loop(self):
        """Background update loop"""
        while self.is_running:
            try:
                # Calculate current volatility
                volatility = await self.calculate_volatility()

                # Determine regime
                new_regime = self._determine_regime(volatility)

                # Check for regime change
                if new_regime != self.current_regime:
                    logger.info(
                        f"REGIME CHANGE: {self.current_regime.value} → {new_regime.value} "
                        f"(Vol: {volatility:.1f}%)"
                    )

                    # Record regime history
                    self.regime_history.append((
                        self.current_regime,
                        self.regime_start_time,
                        datetime.now()
                    ))

                    self.current_regime = new_regime
                    self.regime_start_time = datetime.now()

                # Update thresholds
                self.current_thresholds = await self.calculate_adaptive_thresholds(volatility, new_regime)
                self.threshold_history.append(self.current_thresholds)

                logger.info(
                    f"Thresholds updated - Regime: {new_regime.value}, "
                    f"Min Edge: {self.current_thresholds.min_edge_threshold:.3f}"
                )

                await asyncio.sleep(self.config.update_interval_seconds)
            except Exception as e:
                logger.error(f"Adaptive threshold update error: {e}", exc_info=True)
                await asyncio.sleep(30)

    def add_trade(self, trade: Trade):
        """Add trade"""
        self.trades.append(trade)

    async def calculate_volatility(self) -> Decimal:
        """Calculate current market volatility"""

        # Get recent trades
        cutoff = datetime.now() - timedelta(days=self.config.volatility_lookback_days)
        recent_trades = [t for t in self.trades if not t.is_open and t.exit_time and t.exit_time >= cutoff]

        if len(recent_trades) < 10:
            return Decimal("15.0")  # Default normal volatility

        # Calculate returns volatility
        returns = [t.pnl_pct for t in recent_trades]

        if not returns:
            return Decimal("15.0")

        # Calculate standard deviation
        mean_return = sum(returns) / Decimal(str(len(returns)))
        variance = sum((r - mean_return) ** 2 for r in returns) / Decimal(str(len(returns)))
        std_dev = variance ** Decimal("0.5")

        # Annualize volatility (assuming daily returns)
        annual_vol = std_dev * (Decimal("252") ** Decimal("0.5"))  # 252 trading days

        return annual_vol

    def _determine_regime(self, volatility: Decimal) -> MarketRegime:
        """Determine market regime based on volatility"""

        if volatility < self.config.very_low_vol_threshold:
            return MarketRegime.VERY_LOW_VOL
        elif volatility < self.config.low_vol_threshold:
            return MarketRegime.LOW_VOL
        elif volatility < self.config.high_vol_threshold:
            return MarketRegime.NORMAL
        elif volatility < self.config.very_high_vol_threshold:
            return MarketRegime.HIGH_VOL
        else:
            return MarketRegime.VERY_HIGH_VOL

    async def calculate_adaptive_thresholds(self, volatility: Decimal, regime: MarketRegime) -> ThresholdSet:
        """Calculate adapted thresholds for current regime"""

        # Determine adjustment multiplier
        if regime == MarketRegime.VERY_LOW_VOL:
            multiplier = self.config.very_low_vol_multiplier
        elif regime == MarketRegime.LOW_VOL:
            multiplier = self.config.low_vol_multiplier
        elif regime == MarketRegime.NORMAL:
            multiplier = self.config.normal_multiplier
        elif regime == MarketRegime.HIGH_VOL:
            multiplier = self.config.high_vol_multiplier
        else:  # VERY_HIGH_VOL
            multiplier = self.config.very_high_vol_multiplier

        # Calculate adapted thresholds
        min_edge = self.config.base_min_edge_threshold * multiplier
        good_edge = self.config.base_good_edge_threshold * multiplier
        excellent_edge = self.config.base_excellent_edge_threshold * multiplier

        # Calculate regime statistics
        regime_duration = (datetime.now() - self.regime_start_time).days

        # Get trades in current regime
        regime_trades = [
            t for t in self.trades
            if not t.is_open and t.exit_time and t.exit_time >= self.regime_start_time
        ]

        trades_in_regime = len(regime_trades)
        avg_profitability = (
            sum(t.pnl_usd for t in regime_trades) / Decimal(str(trades_in_regime))
            if trades_in_regime > 0 else Decimal("0")
        )

        return ThresholdSet(
            calculation_time=datetime.now(),
            market_regime=regime,
            current_volatility=volatility,
            min_edge_threshold=min_edge,
            good_edge_threshold=good_edge,
            excellent_edge_threshold=excellent_edge,
            adjustment_multiplier=multiplier,
            base_min_edge=self.config.base_min_edge_threshold,
            base_good_edge=self.config.base_good_edge_threshold,
            base_excellent_edge=self.config.base_excellent_edge_threshold,
            regime_duration_days=regime_duration,
            trades_in_regime=trades_in_regime,
            avg_profitability_in_regime=avg_profitability
        )

    def get_current_min_edge_threshold(self) -> Decimal:
        """Get current minimum edge threshold"""
        if self.current_thresholds:
            return self.current_thresholds.min_edge_threshold
        return self.config.base_min_edge_threshold

    def get_current_good_edge_threshold(self) -> Decimal:
        """Get current good edge threshold"""
        if self.current_thresholds:
            return self.current_thresholds.good_edge_threshold
        return self.config.base_good_edge_threshold

    def get_current_excellent_edge_threshold(self) -> Decimal:
        """Get current excellent edge threshold"""
        if self.current_thresholds:
            return self.current_thresholds.excellent_edge_threshold
        return self.config.base_excellent_edge_threshold

    def print_threshold_summary(self):
        """Print threshold summary"""
        if not self.current_thresholds:
            print("No thresholds calculated yet")
            return

        t = self.current_thresholds

        print(f"\n{'='*100}")
        print("ADAPTIVE THRESHOLD SUMMARY")
        print(f"{'='*100}\n")

        print(f"CURRENT REGIME: {t.market_regime.value.upper()}")
        print(f"Volatility:         {t.current_volatility:>6.1f}%")
        print(f"Adjustment:         {t.adjustment_multiplier:>6.0%}")
        print(f"Duration:           {t.regime_duration_days:>6} days")
        print(f"Trades in regime:   {t.trades_in_regime:>6}")
        print(f"Avg profitability:  ${t.avg_profitability_in_regime:>6,.2f}\n")

        print("ADAPTIVE THRESHOLDS:")
        print(f"{'Threshold':<20}{'Base':<12}{'Adapted':<12}{'Change':<12}")
        print("-" * 56)

        min_change = ((t.min_edge_threshold - t.base_min_edge) / t.base_min_edge * Decimal("100")) if t.base_min_edge > 0 else Decimal("0")
        good_change = ((t.good_edge_threshold - t.base_good_edge) / t.base_good_edge * Decimal("100")) if t.base_good_edge > 0 else Decimal("0")
        exc_change = ((t.excellent_edge_threshold - t.base_excellent_edge) / t.base_excellent_edge * Decimal("100")) if t.base_excellent_edge > 0 else Decimal("0")

        print(f"{'Minimum Edge':<20}{t.base_min_edge:>10.3f}  {t.min_edge_threshold:>10.3f}  {min_change:>9.0f}%")
        print(f"{'Good Edge':<20}{t.base_good_edge:>10.3f}  {t.good_edge_threshold:>10.3f}  {good_change:>9.0f}%")
        print(f"{'Excellent Edge':<20}{t.base_excellent_edge:>10.3f}  {t.excellent_edge_threshold:>10.3f}  {exc_change:>9.0f}%")

        # Regime history
        if self.regime_history:
            print(f"\n\nREGIME HISTORY (Last 5):")
            print(f"{'Regime':<20}{'Start':<20}{'End':<20}{'Duration':<12}")
            print("-" * 80)

            for regime, start, end in self.regime_history[-5:]:
                duration = (end - start).days
                print(
                    f"{regime.value:<20}"
                    f"{start.strftime('%Y-%m-%d'):<20}"
                    f"{end.strftime('%Y-%m-%d'):<20}"
                    f"{duration:>10} days"
                )

        print(f"\n{'='*100}\n")


# Example usage
if __name__ == "__main__":
    async def main():
        config = AdaptiveConfig()
        manager = AdaptiveThresholdManager(config)

        # Simulate volatility changes
        print("Simulating market regimes...")

        # Low volatility period
        for i in range(30):
            trade = Trade(
                trade_id=f"trade_low_{i}",
                entry_time=datetime.now() - timedelta(days=60-i),
                exit_time=datetime.now() - timedelta(days=60-i-1),
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.51"),
                pnl_usd=Decimal("20"),
                pnl_pct=Decimal("2.0"),  # Low volatility
                is_open=False
            )
            manager.add_trade(trade)

        # High volatility period
        for i in range(30):
            pnl_pct = Decimal("20.0") if i % 2 == 0 else Decimal("-15.0")  # High volatility
            trade = Trade(
                trade_id=f"trade_high_{i}",
                entry_time=datetime.now() - timedelta(days=30-i),
                exit_time=datetime.now() - timedelta(days=30-i-1),
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.60") if i % 2 == 0 else Decimal("0.43"),
                pnl_usd=Decimal("200") if i % 2 == 0 else Decimal("-150"),
                pnl_pct=pnl_pct,
                is_open=False
            )
            manager.add_trade(trade)

        # Calculate volatility and thresholds
        volatility = await manager.calculate_volatility()
        regime = manager._determine_regime(volatility)
        thresholds = await manager.calculate_adaptive_thresholds(volatility, regime)

        manager.current_thresholds = thresholds
        manager.current_regime = regime

        # Print summary
        manager.print_threshold_summary()

        print(f"\nCurrent volatility: {volatility:.1f}%")
        print(f"Current regime: {regime.value}")
        print(f"Min edge threshold: {thresholds.min_edge_threshold:.3f}")
        print(f"Good edge threshold: {thresholds.good_edge_threshold:.3f}")
        print(f"Excellent edge threshold: {thresholds.excellent_edge_threshold:.3f}")

        print("\nAdaptive threshold manager demo complete!")

    asyncio.run(main())
