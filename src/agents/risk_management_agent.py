"""
Risk Management Agent - Multi-Agent System Component
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This agent is the **ultimate arbiter** of capital allocation with absolute veto power.
No trade can execute without approval from this agent.

Core Responsibilities:
1. Fractional Kelly Criterion position sizing (k=0.25)
2. Enforce hard constraints ('2% Rule', CVaR, correlation)
3. Daily loss circuit breaker (5% trigger)
4. Emergency deleveraging (50% reduction at 20% drawdown)
5. Real-time portfolio risk monitoring

Statistical Methods:
- Kelly Criterion (fractional for safety)
- CVaR (Expected Shortfall) calculation
- Portfolio correlation analysis (Ledoit-Wolf)
- Drawdown tracking (underwater plot)

Message Contracts:
- Subscribes: TradeProposal, OrderFilled, MarketDataUpdate
- Publishes: ApprovedTrade, RejectedTrade, EmergencyDeRisk, RiskAlert

Performance Targets:
- -26% drawdown reduction (from veto authority)
- +15% capital efficiency (from optimal Kelly sizing)
- 100% constraint compliance (no exceptions)

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats
from scipy.optimize import minimize
import json

logger = logging.getLogger(__name__)


@dataclass
class RiskManagementConfig:
    """Configuration for Risk Management Agent"""

    # Kelly Criterion
    kelly_fraction: float = 0.25  # Quarter-Kelly (conservative)
    min_edge_for_trade: float = 0.05  # 5% minimum expected edge

    # Hard constraints
    max_position_pct: float = 2.0  # 2% per trade ('2% Rule')
    max_portfolio_cvar: float = 5.0  # 5% CVaR at 97.5% confidence
    max_correlation: float = 0.7  # Max correlation with existing positions

    # Circuit breakers
    daily_loss_pct: float = 5.0  # Halt all trading if daily loss > 5%
    max_drawdown_pct: float = 20.0  # Emergency deleverage if drawdown > 20%
    emergency_deleverage_pct: float = 50.0  # Reduce exposure by 50%

    # Portfolio limits
    max_open_positions: int = 20
    max_whale_concentration_pct: float = 30.0  # Max 30% to single whale

    # Approval timeout
    approval_timeout_seconds: int = 5  # Must approve/reject within 5s

    # Risk-free rate
    risk_free_rate_daily: float = 0.00012  # 4.5% annual ≈ 0.012% daily

    # Database connection
    database_connection: str = "postgresql://trader:password@localhost:5432/polymarket_trader"


@dataclass
class TradeProposal:
    """Trade proposal from Whale Discovery Agent"""

    proposal_id: str
    whale_address: str
    market_id: str
    market_topic: str
    side: str  # "BUY" or "SELL"
    proposed_size_usd: float
    expected_price: float
    whale_score: float  # Composite score
    thompson_weight: float  # Allocation weight

    # Statistical validation
    deflated_sharpe_ratio: float
    probabilistic_sharpe_ratio: float
    has_persistent_skill: bool

    timestamp: datetime


@dataclass
class PortfolioState:
    """Current portfolio state"""

    total_value_usd: float
    cash_balance_usd: float
    open_positions: List[Dict]  # List of position records
    realized_pnl_today: float
    unrealized_pnl: float

    # Risk metrics
    current_drawdown_pct: float
    high_water_mark: float
    cvar_97_5: float  # CVaR at 97.5% confidence

    last_updated: datetime


@dataclass
class RiskDecision:
    """Risk decision output"""

    proposal_id: str
    decision: str  # "APPROVED" or "REJECTED"
    approved_size_usd: float  # May differ from proposed if scaled down
    reason: str
    risk_metrics: Dict

    # Kelly sizing
    kelly_fraction_used: float
    estimated_edge: float
    estimated_win_prob: float

    timestamp: datetime


class RiskManagementAgent:
    """
    Specialized agent for risk management with absolute veto power.

    This agent is the final gatekeeper before any trade is executed.
    It enforces:
    1. Position sizing (Fractional Kelly)
    2. Hard portfolio constraints
    3. Circuit breakers
    4. Emergency deleveraging
    """

    def __init__(self, config: RiskManagementConfig = None):
        """
        Initialize Risk Management Agent.

        Args:
            config: Configuration object
        """
        self.config = config or RiskManagementConfig()

        # Agent state
        self.portfolio_state: Optional[PortfolioState] = None
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None

        # Message queue (placeholder - would use NATS/Kafka in production)
        self.message_queue = []

        # Performance tracking
        self.approval_stats = {
            'total_proposals': 0,
            'approved': 0,
            'rejected': 0,
            'rejection_reasons': {},
            'avg_approval_latency_ms': 0.0
        }

        logger.info("RiskManagementAgent initialized with ABSOLUTE VETO POWER")

    async def approval_loop(self):
        """
        Main approval loop - processes trade proposals.

        This is a synchronous RPC handler (uses NATS request-reply pattern).
        """
        logger.info("Starting risk management approval loop")

        while True:
            try:
                # Fetch pending trade proposals from message queue
                # In production, this would be NATS JetStream subscription
                proposals = await self._fetch_pending_proposals()

                for proposal in proposals:
                    await self.process_trade_proposal(proposal)

                # Sleep briefly
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in approval loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def process_trade_proposal(self, proposal: TradeProposal) -> RiskDecision:
        """
        Process a single trade proposal and make approval decision.

        Steps:
        1. Update portfolio state
        2. Check circuit breaker status
        3. Calculate optimal position size (Fractional Kelly)
        4. Enforce hard constraints
        5. Make final decision
        6. Publish decision event

        Args:
            proposal: TradeProposal object

        Returns:
            RiskDecision object
        """
        start_time = datetime.now()
        self.approval_stats['total_proposals'] += 1

        try:
            # Step 1: Update portfolio state
            await self._update_portfolio_state()

            # Step 2: Check circuit breaker
            if self.circuit_breaker_active:
                decision = self._create_rejection(
                    proposal,
                    reason="Circuit breaker active (daily loss limit exceeded)",
                    approved_size=0.0
                )
                self._publish_decision(decision)
                return decision

            # Step 3: Calculate Fractional Kelly size
            kelly_size, edge, win_prob = self._calculate_kelly_size(proposal)

            # Step 4: Enforce hard constraints
            decision = self._enforce_constraints(
                proposal,
                kelly_size,
                edge,
                win_prob
            )

            # Step 5: Publish decision
            self._publish_decision(decision)

            # Update stats
            if decision.decision == "APPROVED":
                self.approval_stats['approved'] += 1
            else:
                self.approval_stats['rejected'] += 1
                reason_key = decision.reason[:50]  # Truncate
                self.approval_stats['rejection_reasons'][reason_key] = \
                    self.approval_stats['rejection_reasons'].get(reason_key, 0) + 1

            # Track latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.approval_stats['avg_approval_latency_ms'] = (
                0.9 * self.approval_stats['avg_approval_latency_ms']
                + 0.1 * latency_ms
            )

            if latency_ms > self.config.approval_timeout_seconds * 1000:
                logger.warning(f"Approval latency exceeded timeout: {latency_ms:.1f}ms")

            logger.info(
                f"{'✅ APPROVED' if decision.decision == 'APPROVED' else '❌ REJECTED'}: "
                f"{proposal.whale_address[:10]}... | "
                f"Market: {proposal.market_topic[:30]}... | "
                f"Size: ${decision.approved_size_usd:,.0f} | "
                f"Reason: {decision.reason} | "
                f"Latency: {latency_ms:.1f}ms"
            )

            return decision

        except Exception as e:
            logger.error(f"Error processing proposal {proposal.proposal_id}: {e}")
            # Safe default: REJECT
            return self._create_rejection(
                proposal,
                reason=f"Processing error: {str(e)}",
                approved_size=0.0
            )

    def _calculate_kelly_size(
        self,
        proposal: TradeProposal
    ) -> Tuple[float, float, float]:
        """
        Calculate Fractional Kelly position size.

        Kelly Criterion formula:
        f* = (p * b - q) / b

        where:
        - f* = fraction of bankroll to wager
        - p = probability of winning
        - q = probability of losing (1 - p)
        - b = odds received (profit if win / amount wagered)

        We use Fractional Kelly (k * f*) for safety, where k = 0.25.

        Args:
            proposal: TradeProposal object

        Returns:
            Tuple of (kelly_size_usd, estimated_edge, win_probability)
        """
        # Estimate win probability from whale's PSR
        # PSR = P(SR > target), which we use as proxy for win probability
        win_prob = proposal.probabilistic_sharpe_ratio

        # Estimate odds from market price
        # For binary markets, if buying "YES" at price p:
        # - If win: profit = (1 - p) per dollar
        # - If lose: loss = p per dollar
        price = proposal.expected_price
        odds = (1 - price) / price if price < 1.0 else 1.0

        # Kelly fraction
        loss_prob = 1 - win_prob
        kelly_fraction = (win_prob * odds - loss_prob) / odds if odds > 0 else 0.0

        # Apply fractional Kelly
        fractional_kelly = self.config.kelly_fraction * max(0.0, kelly_fraction)

        # Convert to dollar size
        if self.portfolio_state:
            bankroll = self.portfolio_state.total_value_usd
            kelly_size_usd = fractional_kelly * bankroll
        else:
            kelly_size_usd = 0.0

        # Estimated edge (expected value per dollar wagered)
        edge = win_prob * odds - loss_prob

        return (kelly_size_usd, edge, win_prob)

    def _enforce_constraints(
        self,
        proposal: TradeProposal,
        kelly_size: float,
        edge: float,
        win_prob: float
    ) -> RiskDecision:
        """
        Enforce hard portfolio constraints.

        Constraints (in order of priority):
        1. Minimum edge requirement (5%)
        2. '2% Rule': No position > 2% of portfolio
        3. Portfolio CVaR < 5%
        4. Correlation check: < 0.7 with existing positions
        5. Max open positions: 20
        6. Whale concentration: Max 30% to single whale

        Args:
            proposal: TradeProposal object
            kelly_size: Kelly-optimal size
            edge: Estimated edge
            win_prob: Win probability

        Returns:
            RiskDecision object (APPROVED or REJECTED)
        """
        if not self.portfolio_state:
            return self._create_rejection(
                proposal,
                reason="Portfolio state unavailable",
                approved_size=0.0
            )

        portfolio_value = self.portfolio_state.total_value_usd

        # Constraint 1: Minimum edge
        if edge < self.config.min_edge_for_trade:
            return self._create_rejection(
                proposal,
                reason=f"Insufficient edge: {edge:.3f} < {self.config.min_edge_for_trade}",
                approved_size=0.0
            )

        # Constraint 2: '2% Rule'
        max_size_2pct = portfolio_value * (self.config.max_position_pct / 100)
        approved_size = min(kelly_size, max_size_2pct)

        if kelly_size > max_size_2pct:
            logger.debug(
                f"Position size capped by 2% rule: "
                f"Kelly=${kelly_size:,.0f} → Capped=${approved_size:,.0f}"
            )

        # Constraint 3: CVaR check
        # Simulate portfolio after adding this trade
        projected_cvar = self._calculate_projected_cvar(
            proposal,
            approved_size
        )

        if projected_cvar > self.config.max_portfolio_cvar:
            return self._create_rejection(
                proposal,
                reason=f"CVaR limit exceeded: {projected_cvar:.2f}% > {self.config.max_portfolio_cvar}%",
                approved_size=0.0
            )

        # Constraint 4: Correlation check
        max_correlation = self._calculate_max_correlation_with_portfolio(
            proposal.whale_address,
            proposal.market_id
        )

        if max_correlation > self.config.max_correlation:
            return self._create_rejection(
                proposal,
                reason=f"High correlation with existing positions: {max_correlation:.3f}",
                approved_size=0.0
            )

        # Constraint 5: Max open positions
        if len(self.portfolio_state.open_positions) >= self.config.max_open_positions:
            return self._create_rejection(
                proposal,
                reason=f"Max open positions reached: {len(self.portfolio_state.open_positions)}",
                approved_size=0.0
            )

        # Constraint 6: Whale concentration
        whale_exposure = self._calculate_whale_exposure(proposal.whale_address)
        max_whale_exposure = portfolio_value * (self.config.max_whale_concentration_pct / 100)

        if whale_exposure + approved_size > max_whale_exposure:
            # Scale down to stay under limit
            approved_size = max(0.0, max_whale_exposure - whale_exposure)

            if approved_size < kelly_size * 0.1:  # Too small (< 10% of Kelly)
                return self._create_rejection(
                    proposal,
                    reason=f"Whale concentration limit: {whale_exposure / portfolio_value * 100:.1f}%",
                    approved_size=0.0
                )

        # All constraints passed!
        return RiskDecision(
            proposal_id=proposal.proposal_id,
            decision="APPROVED",
            approved_size_usd=approved_size,
            reason="All constraints satisfied",
            risk_metrics={
                'portfolio_value': portfolio_value,
                'position_size_pct': (approved_size / portfolio_value) * 100,
                'projected_cvar': projected_cvar,
                'max_correlation': max_correlation,
                'whale_exposure_pct': ((whale_exposure + approved_size) / portfolio_value) * 100
            },
            kelly_fraction_used=self.config.kelly_fraction,
            estimated_edge=edge,
            estimated_win_prob=win_prob,
            timestamp=datetime.now()
        )

    def _calculate_projected_cvar(
        self,
        proposal: TradeProposal,
        size_usd: float
    ) -> float:
        """
        Calculate projected CVaR (Expected Shortfall) after adding trade.

        CVaR at α% = E[Loss | Loss >= VaR_α]

        We use 97.5% confidence (2.5% tail).

        Args:
            proposal: TradeProposal object
            size_usd: Position size in USD

        Returns:
            Projected CVaR as percentage of portfolio value
        """
        if not self.portfolio_state or size_usd == 0:
            return 0.0

        # Simplified CVaR calculation (would use Monte Carlo in production)
        # Assume worst-case scenario: this trade loses 100%
        max_loss = size_usd

        # Current CVaR from existing positions
        current_cvar_usd = (
            self.portfolio_state.cvar_97_5 / 100
            * self.portfolio_state.total_value_usd
        )

        # Projected CVaR (conservative: add losses)
        projected_cvar_usd = current_cvar_usd + max_loss * 0.5  # 50% correlation assumption

        # As percentage of portfolio
        projected_cvar_pct = (
            projected_cvar_usd / self.portfolio_state.total_value_usd
        ) * 100

        return projected_cvar_pct

    def _calculate_max_correlation_with_portfolio(
        self,
        whale_address: str,
        market_id: str
    ) -> float:
        """
        Calculate maximum correlation between proposed trade and existing positions.

        Uses Ledoit-Wolf robust covariance estimator in production.

        Args:
            whale_address: Whale wallet address
            market_id: Market ID

        Returns:
            Maximum correlation (0-1)
        """
        if not self.portfolio_state or not self.portfolio_state.open_positions:
            return 0.0

        # Placeholder - would fetch historical returns and calculate correlation matrix
        # For now, return conservative estimate
        return 0.3

    def _calculate_whale_exposure(self, whale_address: str) -> float:
        """
        Calculate total exposure to a specific whale.

        Args:
            whale_address: Whale wallet address

        Returns:
            Total USD exposure to this whale
        """
        if not self.portfolio_state:
            return 0.0

        total_exposure = sum(
            pos['size_usd']
            for pos in self.portfolio_state.open_positions
            if pos.get('whale_address') == whale_address
        )

        return total_exposure

    async def monitoring_loop(self):
        """
        Portfolio risk monitoring loop.

        Checks:
        1. Daily loss circuit breaker
        2. Maximum drawdown emergency deleveraging
        3. CVaR limit breaches
        """
        logger.info("Starting risk monitoring loop")

        while True:
            try:
                await self._update_portfolio_state()

                if not self.portfolio_state:
                    await asyncio.sleep(60)
                    continue

                # Check daily loss circuit breaker
                daily_loss_pct = (
                    self.portfolio_state.realized_pnl_today
                    / self.portfolio_state.total_value_usd
                ) * 100

                if daily_loss_pct < -self.config.daily_loss_pct:
                    if not self.circuit_breaker_active:
                        self._activate_circuit_breaker(
                            reason=f"Daily loss exceeded: {daily_loss_pct:.2f}%"
                        )

                # Check maximum drawdown
                if self.portfolio_state.current_drawdown_pct > self.config.max_drawdown_pct:
                    await self._emergency_deleverage(
                        reason=f"Max drawdown exceeded: {self.portfolio_state.current_drawdown_pct:.2f}%"
                    )

                # Check CVaR
                if self.portfolio_state.cvar_97_5 > self.config.max_portfolio_cvar:
                    self._publish_event('RiskAlert', {
                        'alert_type': 'CVaR_BREACH',
                        'current_cvar': self.portfolio_state.cvar_97_5,
                        'limit': self.config.max_portfolio_cvar,
                        'timestamp': datetime.now().isoformat()
                    })

                # Sleep 60 seconds
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    def _activate_circuit_breaker(self, reason: str):
        """
        Activate circuit breaker - halts all trading.

        Args:
            reason: Reason for activation
        """
        self.circuit_breaker_active = True
        self.circuit_breaker_triggered_at = datetime.now()

        self._publish_event('CircuitBreakerActivated', {
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })

        logger.critical(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")

    async def _emergency_deleverage(self, reason: str):
        """
        Emergency deleveraging - close 50% of positions.

        Args:
            reason: Reason for deleveraging
        """
        if not self.portfolio_state:
            return

        # Calculate target reduction
        current_exposure = sum(
            pos['size_usd']
            for pos in self.portfolio_state.open_positions
        )

        target_reduction_usd = current_exposure * (self.config.emergency_deleverage_pct / 100)

        # Publish emergency deleverage event
        self._publish_event('EmergencyDeRisk', {
            'reason': reason,
            'current_exposure_usd': current_exposure,
            'target_reduction_usd': target_reduction_usd,
            'target_reduction_pct': self.config.emergency_deleverage_pct,
            'timestamp': datetime.now().isoformat()
        })

        logger.critical(
            f"🚨 EMERGENCY DELEVERAGING: {reason} | "
            f"Reducing exposure by ${target_reduction_usd:,.0f}"
        )

    async def _update_portfolio_state(self):
        """Update portfolio state from database"""
        # Placeholder - would fetch from PostgreSQL + Materialize
        # For now, create dummy state
        if not self.portfolio_state:
            self.portfolio_state = PortfolioState(
                total_value_usd=100000.0,
                cash_balance_usd=100000.0,
                open_positions=[],
                realized_pnl_today=0.0,
                unrealized_pnl=0.0,
                current_drawdown_pct=0.0,
                high_water_mark=100000.0,
                cvar_97_5=0.0,
                last_updated=datetime.now()
            )

    async def _fetch_pending_proposals(self) -> List[TradeProposal]:
        """Fetch pending trade proposals from message queue"""
        # Placeholder - would use NATS subscription
        return []

    def _create_rejection(
        self,
        proposal: TradeProposal,
        reason: str,
        approved_size: float
    ) -> RiskDecision:
        """Create a rejection decision"""
        return RiskDecision(
            proposal_id=proposal.proposal_id,
            decision="REJECTED",
            approved_size_usd=approved_size,
            reason=reason,
            risk_metrics={},
            kelly_fraction_used=0.0,
            estimated_edge=0.0,
            estimated_win_prob=0.0,
            timestamp=datetime.now()
        )

    def _publish_decision(self, decision: RiskDecision):
        """Publish risk decision to message bus"""
        event_type = 'ApprovedTrade' if decision.decision == 'APPROVED' else 'RejectedTrade'

        self._publish_event(event_type, {
            'proposal_id': decision.proposal_id,
            'decision': decision.decision,
            'approved_size_usd': decision.approved_size_usd,
            'reason': decision.reason,
            'risk_metrics': decision.risk_metrics,
            'kelly_fraction_used': decision.kelly_fraction_used,
            'estimated_edge': decision.estimated_edge,
            'estimated_win_prob': decision.estimated_win_prob,
            'timestamp': decision.timestamp.isoformat()
        })

    def _publish_event(self, event_type: str, payload: Dict):
        """Publish event to message bus"""
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'RiskManagementAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.message_queue.append(event)
        logger.debug(f"Published event: {event_type}")

    def get_approval_stats(self) -> Dict:
        """Get approval statistics"""
        total = self.approval_stats['total_proposals']
        approved = self.approval_stats['approved']
        rejected = self.approval_stats['rejected']

        return {
            'total_proposals': total,
            'approved': approved,
            'rejected': rejected,
            'approval_rate': (approved / total * 100) if total > 0 else 0.0,
            'avg_approval_latency_ms': self.approval_stats['avg_approval_latency_ms'],
            'top_rejection_reasons': sorted(
                self.approval_stats['rejection_reasons'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize agent
        agent = RiskManagementAgent()

        # Start both loops concurrently
        await asyncio.gather(
            agent.approval_loop(),
            agent.monitoring_loop()
        )

    # Run
    asyncio.run(main())
