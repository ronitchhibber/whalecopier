"""
Performance Attribution Agent - Multi-Agent System Component
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This agent provides performance attribution and portfolio optimization.

Core Responsibilities:
1. Shapley value calculation for fair P&L attribution to whales
2. Market impact measurement (immediate, permanent vs transient)
3. Information Coefficient (IC) tracking and decay analysis
4. Correlation analysis to identify unique alpha sources
5. Rebalancing recommendations to optimize capital allocation

Statistical Methods:
- Shapley value decomposition (cooperative game theory)
- Almgren-Chriss market impact model
- IC half-life estimation (exponential decay fitting)
- Hierarchical risk parity for portfolio construction

Message Contracts:
- Subscribes: OrderFilled, MarketDataUpdate
- Publishes: PortfolioAttribution, RebalancingRecommendation

Performance Targets:
- Attribution updates within 1 minute of trade settlement
- IC correlation > 0.3 for included whales
- Auto-prune whales with correlation > 0.85 (redundant alpha)

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats, optimize
from collections import defaultdict
import itertools

logger = logging.getLogger(__name__)


@dataclass
class PerformanceAttributionConfig:
    """Configuration for Performance Attribution Agent"""

    # Attribution settings
    attribution_window_days: int = 30  # Rolling window for attribution
    min_trades_for_attribution: int = 5  # Minimum trades to include whale
    shapley_sampling_iterations: int = 1000  # Monte Carlo iterations for Shapley

    # Market impact
    price_impact_window_seconds: int = 300  # 5 minutes
    permanent_impact_halflife_days: float = 7.0  # Decay half-life

    # Information Coefficient
    ic_calculation_interval_hours: int = 24  # Daily IC updates
    min_ic_threshold: float = 0.1  # Minimum IC to retain whale
    ic_halflife_estimation_window_days: int = 90

    # Correlation analysis
    correlation_threshold: float = 0.85  # Prune if correlation > 0.85
    correlation_window_days: int = 60

    # Rebalancing
    rebalancing_interval_days: int = 7  # Weekly rebalancing
    min_allocation_change_pct: float = 5.0  # Trigger if change > 5%


@dataclass
class WhaleAttribution:
    """Attribution metrics for a single whale"""

    whale_address: str
    whale_name: str

    # P&L attribution
    shapley_value: float  # Fair P&L contribution
    direct_pnl: float  # Naive P&L (ignoring interactions)
    attribution_confidence: float  # 0-1

    # Performance metrics
    information_coefficient: float  # Correlation between signal and returns
    ic_halflife_days: Optional[float]  # Alpha decay rate
    hit_rate: float  # % of profitable trades

    # Risk metrics
    contribution_to_portfolio_var: float  # % of portfolio variance
    correlation_with_others: float  # Avg correlation with other whales
    market_impact_bps: float  # Average price impact in basis points

    # Capital allocation
    current_allocation_pct: float
    recommended_allocation_pct: float

    last_updated: datetime


@dataclass
class MarketImpactMeasurement:
    """Market impact metrics for a trade"""

    trade_id: str
    market_id: str

    # Pre-trade
    pre_trade_mid_price: float

    # Execution
    execution_price: float
    trade_size_usd: float
    trade_timestamp: datetime

    # Post-trade price evolution
    immediate_impact_bps: float  # T+0 (right after trade)
    impact_5min_bps: float  # T+5 minutes
    impact_1hr_bps: float  # T+1 hour
    impact_24hr_bps: float  # T+24 hours

    # Decomposition
    permanent_impact_bps: float  # Long-term price change
    transient_impact_bps: float  # Temporary impact that reverted


@dataclass
class PortfolioAttributionSummary:
    """Overall portfolio attribution summary"""

    attribution_period_start: datetime
    attribution_period_end: datetime

    total_pnl: float
    attributed_pnl: float  # Sum of Shapley values
    unexplained_pnl: float  # Residual (should be ~0)

    whale_attributions: List[WhaleAttribution]

    # Portfolio-level metrics
    portfolio_information_coefficient: float
    portfolio_sharpe_ratio: float
    avg_correlation_between_whales: float

    top_contributors: List[str]  # Whale addresses
    bottom_contributors: List[str]  # Whale addresses
    pruning_candidates: List[str]  # High correlation or low IC


class PerformanceAttributionAgent:
    """
    Specialized agent for performance attribution and portfolio optimization.

    Uses cooperative game theory (Shapley values) to fairly attribute P&L
    to each whale, accounting for interactions and correlations.
    """

    def __init__(self, config: PerformanceAttributionConfig = None):
        """
        Initialize Performance Attribution Agent.

        Args:
            config: Configuration object
        """
        self.config = config or PerformanceAttributionConfig()

        # Agent state
        self.whale_attributions: Dict[str, WhaleAttribution] = {}
        self.market_impacts: Dict[str, MarketImpactMeasurement] = {}

        # Trade history (for attribution calculations)
        self.trade_history: List[Dict] = []  # OrderFilled events
        self.market_data_cache: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)

        # Message queue (placeholder - would use Kafka in production)
        self.message_queue = []

        # Performance tracking
        self.attribution_stats = {
            'total_attributions_calculated': 0,
            'total_whales_pruned': 0,
            'total_rebalancing_recommendations': 0,
            'last_attribution_time': None,
            'last_ic_calculation_time': None,
            'last_rebalancing_time': None
        }

        logger.info("PerformanceAttributionAgent initialized")

    async def attribution_loop(self):
        """
        Main attribution loop - calculates Shapley values periodically.

        Runs daily to update whale attributions and generate rebalancing
        recommendations.
        """
        logger.info("Starting attribution loop")

        while True:
            try:
                # Calculate attribution for all whales
                logger.info("📊 Starting performance attribution calculation")

                # Get recent trades (last N days)
                attribution_period_start = datetime.now() - timedelta(
                    days=self.config.attribution_window_days
                )
                relevant_trades = [
                    t for t in self.trade_history
                    if t['timestamp'] >= attribution_period_start
                ]

                if not relevant_trades:
                    logger.info("No trades in attribution window, skipping")
                    await asyncio.sleep(3600)  # Check again in 1 hour
                    continue

                # Group trades by whale
                trades_by_whale = self._group_trades_by_whale(relevant_trades)

                # Calculate Shapley values
                shapley_values = await self._calculate_shapley_values(trades_by_whale)

                # Update whale attributions
                for whale_address, shapley_value in shapley_values.items():
                    await self._update_whale_attribution(
                        whale_address,
                        shapley_value,
                        trades_by_whale.get(whale_address, [])
                    )

                # Generate portfolio summary
                summary = self._generate_portfolio_attribution_summary()

                # Publish attribution event
                self._publish_event('PortfolioAttribution', {
                    'attribution_period_start': summary.attribution_period_start.isoformat(),
                    'attribution_period_end': summary.attribution_period_end.isoformat(),
                    'total_pnl': summary.total_pnl,
                    'attributed_pnl': summary.attributed_pnl,
                    'unexplained_pnl': summary.unexplained_pnl,
                    'whale_attributions': [
                        {
                            'whale_address': wa.whale_address,
                            'whale_name': wa.whale_name,
                            'shapley_value': wa.shapley_value,
                            'ic': wa.information_coefficient,
                            'recommended_allocation_pct': wa.recommended_allocation_pct
                        }
                        for wa in summary.whale_attributions
                    ],
                    'top_contributors': summary.top_contributors,
                    'pruning_candidates': summary.pruning_candidates
                })

                # Check if rebalancing is needed
                if summary.pruning_candidates:
                    logger.warning(
                        f"🔍 Found {len(summary.pruning_candidates)} pruning candidates: "
                        f"{summary.pruning_candidates}"
                    )
                    await self._generate_rebalancing_recommendation(summary)

                # Update stats
                self.attribution_stats['total_attributions_calculated'] += 1
                self.attribution_stats['last_attribution_time'] = datetime.now()

                # Sleep until next attribution cycle (24 hours)
                await asyncio.sleep(self.config.ic_calculation_interval_hours * 3600)

            except Exception as e:
                logger.error(f"Error in attribution loop: {e}", exc_info=True)
                await asyncio.sleep(3600)  # Retry in 1 hour

    def _group_trades_by_whale(self, trades: List[Dict]) -> Dict[str, List[Dict]]:
        """Group trades by whale address"""
        grouped = defaultdict(list)
        for trade in trades:
            whale_address = trade.get('whale_address')
            if whale_address:
                grouped[whale_address].append(trade)
        return dict(grouped)

    async def _calculate_shapley_values(
        self, trades_by_whale: Dict[str, List[Dict]]
    ) -> Dict[str, float]:
        """
        Calculate Shapley values using Monte Carlo sampling.

        Shapley value measures the marginal contribution of each whale
        to the overall portfolio P&L, averaged over all possible orderings.

        This is computationally expensive (O(2^N)), so we use Monte Carlo
        sampling for approximation.

        Args:
            trades_by_whale: Dict mapping whale address to list of trades

        Returns:
            Dict mapping whale address to Shapley value (P&L contribution)
        """
        whale_addresses = list(trades_by_whale.keys())
        n_whales = len(whale_addresses)

        if n_whales == 0:
            return {}

        logger.info(f"Calculating Shapley values for {n_whales} whales")

        # Initialize Shapley values
        shapley_values = {addr: 0.0 for addr in whale_addresses}

        # Monte Carlo sampling
        for iteration in range(self.config.shapley_sampling_iterations):
            # Random permutation of whales
            permutation = np.random.permutation(whale_addresses).tolist()

            # Calculate marginal contributions
            current_coalition_pnl = 0.0

            for i, whale_addr in enumerate(permutation):
                # Coalition: all whales up to and including current whale
                coalition = permutation[:i+1]

                # Calculate coalition P&L
                coalition_pnl = self._calculate_coalition_pnl(
                    coalition, trades_by_whale
                )

                # Marginal contribution
                marginal_contribution = coalition_pnl - current_coalition_pnl

                # Add to Shapley value
                shapley_values[whale_addr] += marginal_contribution

                # Update current coalition P&L
                current_coalition_pnl = coalition_pnl

        # Average over iterations
        for addr in shapley_values:
            shapley_values[addr] /= self.config.shapley_sampling_iterations

        logger.info(
            f"Shapley calculation complete | "
            f"Total attributed: ${sum(shapley_values.values()):.2f}"
        )

        return shapley_values

    def _calculate_coalition_pnl(
        self, coalition: List[str], trades_by_whale: Dict[str, List[Dict]]
    ) -> float:
        """
        Calculate total P&L for a coalition of whales.

        Simulates portfolio that only copies trades from whales in the coalition.

        Args:
            coalition: List of whale addresses
            trades_by_whale: Dict mapping whale address to trades

        Returns:
            Total P&L for the coalition
        """
        # Collect all trades from coalition whales
        coalition_trades = []
        for whale_addr in coalition:
            coalition_trades.extend(trades_by_whale.get(whale_addr, []))

        # Sort by timestamp
        coalition_trades.sort(key=lambda t: t.get('timestamp', datetime.now()))

        # Calculate total P&L
        total_pnl = sum(t.get('realized_pnl', 0.0) for t in coalition_trades)

        return total_pnl

    async def _update_whale_attribution(
        self, whale_address: str, shapley_value: float, trades: List[Dict]
    ):
        """
        Update attribution metrics for a single whale.

        Args:
            whale_address: Whale address
            shapley_value: Calculated Shapley value
            trades: List of whale's trades
        """
        if not trades:
            return

        # Calculate direct P&L (naive attribution)
        direct_pnl = sum(t.get('realized_pnl', 0.0) for t in trades)

        # Calculate Information Coefficient
        ic = self._calculate_information_coefficient(trades)

        # Calculate IC half-life (alpha decay)
        ic_halflife = self._estimate_ic_halflife(whale_address)

        # Calculate hit rate
        profitable_trades = sum(1 for t in trades if t.get('realized_pnl', 0) > 0)
        hit_rate = (profitable_trades / len(trades)) * 100 if trades else 0.0

        # Calculate correlation with other whales
        avg_correlation = self._calculate_avg_correlation_with_others(whale_address)

        # Calculate contribution to portfolio variance
        var_contribution = self._calculate_variance_contribution(whale_address)

        # Calculate average market impact
        avg_market_impact = self._calculate_avg_market_impact(whale_address)

        # Recommended allocation (based on Shapley value and IC)
        recommended_allocation = self._calculate_recommended_allocation(
            shapley_value, ic, avg_correlation
        )

        # Create/update attribution
        attribution = WhaleAttribution(
            whale_address=whale_address,
            whale_name=trades[0].get('whale_name', whale_address[:10]),
            shapley_value=shapley_value,
            direct_pnl=direct_pnl,
            attribution_confidence=0.85,  # Placeholder
            information_coefficient=ic,
            ic_halflife_days=ic_halflife,
            hit_rate=hit_rate,
            contribution_to_portfolio_var=var_contribution,
            correlation_with_others=avg_correlation,
            market_impact_bps=avg_market_impact,
            current_allocation_pct=5.0,  # Placeholder - would fetch from Risk Agent
            recommended_allocation_pct=recommended_allocation,
            last_updated=datetime.now()
        )

        self.whale_attributions[whale_address] = attribution

        logger.debug(
            f"Updated attribution | "
            f"Whale: {attribution.whale_name} | "
            f"Shapley: ${shapley_value:.2f} | "
            f"IC: {ic:.3f} | "
            f"Recommended allocation: {recommended_allocation:.1f}%"
        )

    def _calculate_information_coefficient(self, trades: List[Dict]) -> float:
        """
        Calculate Information Coefficient (IC).

        IC = correlation between trade signals and realized returns.

        Args:
            trades: List of trades

        Returns:
            IC value (-1 to 1)
        """
        if len(trades) < 5:
            return 0.0

        # Extract signals (trade conviction) and returns
        signals = []
        returns = []

        for trade in trades:
            # Signal: trade size as proxy for conviction
            signal = trade.get('size', 0)

            # Return: realized P&L normalized by position size
            position_size = trade.get('amount', 1.0)
            pnl = trade.get('realized_pnl', 0.0)
            trade_return = (pnl / position_size) if position_size > 0 else 0.0

            signals.append(signal)
            returns.append(trade_return)

        # Calculate Spearman correlation (robust to outliers)
        if len(signals) >= 5:
            ic, _ = stats.spearmanr(signals, returns)
            return float(ic) if not np.isnan(ic) else 0.0
        else:
            return 0.0

    def _estimate_ic_halflife(self, whale_address: str) -> Optional[float]:
        """
        Estimate IC half-life (alpha decay rate).

        Measures how quickly the whale's edge degrades over time.

        Args:
            whale_address: Whale address

        Returns:
            Half-life in days, or None if insufficient data
        """
        # Placeholder - would implement exponential decay fitting
        # IC(t) = IC₀ * exp(-λt)
        # Half-life = ln(2) / λ

        return 30.0  # Placeholder: 30-day half-life

    def _calculate_avg_correlation_with_others(self, whale_address: str) -> float:
        """Calculate average correlation with other whales"""
        # Placeholder - would calculate return correlations
        return 0.3  # Placeholder

    def _calculate_variance_contribution(self, whale_address: str) -> float:
        """Calculate contribution to portfolio variance"""
        # Placeholder - would use risk decomposition
        return 5.0  # Placeholder: 5% of portfolio variance

    def _calculate_avg_market_impact(self, whale_address: str) -> float:
        """Calculate average market impact in basis points"""
        whale_impacts = [
            mi.immediate_impact_bps
            for mi in self.market_impacts.values()
            if mi.trade_id.startswith(whale_address)
        ]

        if whale_impacts:
            return np.mean(whale_impacts)
        else:
            return 0.0  # No market impact data

    def _calculate_recommended_allocation(
        self, shapley_value: float, ic: float, correlation: float
    ) -> float:
        """
        Calculate recommended capital allocation %.

        Uses Shapley value, IC, and correlation to determine optimal allocation.

        Args:
            shapley_value: Whale's Shapley value
            ic: Information coefficient
            correlation: Avg correlation with others

        Returns:
            Recommended allocation percentage
        """
        # Base allocation from Shapley value (normalized)
        # Placeholder - would normalize across all whales
        base_allocation = 10.0  # Placeholder

        # Adjust for IC
        ic_multiplier = 1.0 + ic  # IC of 0.3 → 1.3x multiplier

        # Penalize high correlation (redundant alpha)
        correlation_penalty = 1.0 - (correlation * 0.5)  # High corr → lower allocation

        recommended = base_allocation * ic_multiplier * correlation_penalty

        # Cap at 20%
        return min(recommended, 20.0)

    def _generate_portfolio_attribution_summary(self) -> PortfolioAttributionSummary:
        """Generate overall portfolio attribution summary"""
        attribution_period_end = datetime.now()
        attribution_period_start = attribution_period_end - timedelta(
            days=self.config.attribution_window_days
        )

        # Calculate totals
        total_pnl = sum(wa.direct_pnl for wa in self.whale_attributions.values())
        attributed_pnl = sum(wa.shapley_value for wa in self.whale_attributions.values())
        unexplained_pnl = total_pnl - attributed_pnl

        # Sort by Shapley value
        sorted_attributions = sorted(
            self.whale_attributions.values(),
            key=lambda wa: wa.shapley_value,
            reverse=True
        )

        top_contributors = [
            wa.whale_address for wa in sorted_attributions[:5]
        ]
        bottom_contributors = [
            wa.whale_address for wa in sorted_attributions[-5:]
        ]

        # Identify pruning candidates (low IC or high correlation)
        pruning_candidates = [
            wa.whale_address
            for wa in self.whale_attributions.values()
            if (wa.information_coefficient < self.config.min_ic_threshold or
                wa.correlation_with_others > self.config.correlation_threshold)
        ]

        # Portfolio-level metrics
        portfolio_ic = np.mean([
            wa.information_coefficient for wa in self.whale_attributions.values()
        ]) if self.whale_attributions else 0.0

        avg_correlation = np.mean([
            wa.correlation_with_others for wa in self.whale_attributions.values()
        ]) if self.whale_attributions else 0.0

        return PortfolioAttributionSummary(
            attribution_period_start=attribution_period_start,
            attribution_period_end=attribution_period_end,
            total_pnl=total_pnl,
            attributed_pnl=attributed_pnl,
            unexplained_pnl=unexplained_pnl,
            whale_attributions=list(self.whale_attributions.values()),
            portfolio_information_coefficient=portfolio_ic,
            portfolio_sharpe_ratio=1.8,  # Placeholder
            avg_correlation_between_whales=avg_correlation,
            top_contributors=top_contributors,
            bottom_contributors=bottom_contributors,
            pruning_candidates=pruning_candidates
        )

    async def _generate_rebalancing_recommendation(
        self, summary: PortfolioAttributionSummary
    ):
        """
        Generate rebalancing recommendation based on attribution analysis.

        Args:
            summary: Portfolio attribution summary
        """
        # Build recommendation
        recommendations = []

        for wa in summary.whale_attributions:
            allocation_delta = wa.recommended_allocation_pct - wa.current_allocation_pct

            if abs(allocation_delta) > self.config.min_allocation_change_pct:
                recommendations.append({
                    'whale_address': wa.whale_address,
                    'whale_name': wa.whale_name,
                    'current_allocation_pct': wa.current_allocation_pct,
                    'recommended_allocation_pct': wa.recommended_allocation_pct,
                    'delta_pct': allocation_delta,
                    'reason': self._get_rebalancing_reason(wa)
                })

        if recommendations:
            # Publish rebalancing event
            self._publish_event('RebalancingRecommendation', {
                'timestamp': datetime.now().isoformat(),
                'total_recommendations': len(recommendations),
                'recommendations': recommendations,
                'pruning_candidates': summary.pruning_candidates
            })

            # Update stats
            self.attribution_stats['total_rebalancing_recommendations'] += 1
            self.attribution_stats['last_rebalancing_time'] = datetime.now()

            logger.info(
                f"📊 Rebalancing recommendation generated | "
                f"{len(recommendations)} whales | "
                f"{len(summary.pruning_candidates)} pruning candidates"
            )

    def _get_rebalancing_reason(self, wa: WhaleAttribution) -> str:
        """Get human-readable reason for rebalancing"""
        if wa.information_coefficient < self.config.min_ic_threshold:
            return f"Low IC ({wa.information_coefficient:.3f})"
        elif wa.correlation_with_others > self.config.correlation_threshold:
            return f"High correlation ({wa.correlation_with_others:.3f})"
        elif wa.shapley_value > wa.direct_pnl * 1.2:
            return "Strong synergy effects"
        elif wa.shapley_value < wa.direct_pnl * 0.8:
            return "Negative synergy effects"
        else:
            return "Performance-based adjustment"

    async def process_order_filled_event(self, event: Dict):
        """
        Process an OrderFilled event from the Execution Agent.

        Args:
            event: OrderFilled event data
        """
        # Add to trade history
        self.trade_history.append(event)

        # Measure market impact
        await self._measure_market_impact(event)

    async def _measure_market_impact(self, trade: Dict):
        """
        Measure market impact for a trade.

        Tracks price evolution after trade execution to decompose
        impact into permanent and transient components.

        Args:
            trade: Trade data (OrderFilled event)
        """
        trade_id = trade.get('trade_id', '')
        market_id = trade.get('market_id', '')
        execution_price = trade.get('price', 0.0)
        trade_size_usd = trade.get('amount', 0.0)
        trade_timestamp = trade.get('timestamp', datetime.now())

        # Fetch pre-trade mid price
        # Placeholder - would query market data
        pre_trade_mid = execution_price * 0.99  # Placeholder

        # Schedule impact measurements
        # In production, would subscribe to real-time market data feed
        # and track price evolution at T+0, T+5min, T+1hr, T+24hr

        impact = MarketImpactMeasurement(
            trade_id=trade_id,
            market_id=market_id,
            pre_trade_mid_price=pre_trade_mid,
            execution_price=execution_price,
            trade_size_usd=trade_size_usd,
            trade_timestamp=trade_timestamp,
            immediate_impact_bps=5.0,  # Placeholder
            impact_5min_bps=3.0,  # Placeholder
            impact_1hr_bps=2.0,  # Placeholder
            impact_24hr_bps=1.5,  # Placeholder (permanent)
            permanent_impact_bps=1.5,  # Placeholder
            transient_impact_bps=3.5  # Placeholder (5.0 - 1.5)
        )

        self.market_impacts[trade_id] = impact

        logger.debug(
            f"Measured market impact | "
            f"Trade: {trade_id[:10]}... | "
            f"Immediate: {impact.immediate_impact_bps:.2f} bps | "
            f"Permanent: {impact.permanent_impact_bps:.2f} bps"
        )

    def _publish_event(self, event_type: str, payload: Dict):
        """Publish event to message bus"""
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'PerformanceAttributionAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.message_queue.append(event)
        logger.debug(f"Published event: {event_type}")

    def get_attribution_stats(self) -> Dict:
        """Get attribution statistics"""
        return {
            'total_whales_tracked': len(self.whale_attributions),
            'total_attributions_calculated': self.attribution_stats['total_attributions_calculated'],
            'total_whales_pruned': self.attribution_stats['total_whales_pruned'],
            'total_rebalancing_recommendations': self.attribution_stats['total_rebalancing_recommendations'],
            'last_attribution_time': self.attribution_stats['last_attribution_time'],
            'last_ic_calculation_time': self.attribution_stats['last_ic_calculation_time'],
            'last_rebalancing_time': self.attribution_stats['last_rebalancing_time'],
            'total_trades_in_history': len(self.trade_history),
            'total_market_impacts_measured': len(self.market_impacts)
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize agent
        agent = PerformanceAttributionAgent()

        # Simulate some trade events
        for i in range(10):
            await agent.process_order_filled_event({
                'trade_id': f'trade_{i}',
                'whale_address': f'0x{i:040x}',
                'whale_name': f'Whale_{i}',
                'market_id': f'market_{i % 3}',
                'price': 0.5 + (i % 5) * 0.1,
                'amount': 100.0 + i * 50,
                'size': 200.0,
                'realized_pnl': (-50 if i % 3 == 0 else 100) + i * 10,
                'timestamp': datetime.now() - timedelta(days=i)
            })

        # Run attribution (normally would run in loop)
        await agent.attribution_loop()

    # Run
    asyncio.run(main())
