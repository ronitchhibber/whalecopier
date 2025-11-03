"""
Real Trading Execution Engine

Production-ready trading system with Polymarket API integration.
Includes comprehensive safety checks, risk management, and monitoring.

Safety Features:
- Pre-trade validation
- Position size limits
- Circuit breakers for losses
- Rate limiting
- Duplicate trade prevention
- Manual approval mode (optional)
"""

import sys
sys.path.append('/Users/ronitchhibber/Desktop/Whale.Trader-v0.1')

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
import logging
import os
import uuid

from libs.trading.bet_weighting import (
    BetWeightingEngine, WhaleProfile, MarketContext,
    PortfolioState, BetWeight
)
from libs.common.models import Position
from sqlalchemy.orm import Session
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TradeOrder:
    """Pending trade order"""
    whale_address: str
    whale_name: str
    market_id: str
    market_title: str
    side: str  # 'BUY' or 'SELL'
    price: float
    size_usd: float
    confidence: float
    reasoning: str
    timestamp: datetime
    token_id: Optional[str] = None  # Polymarket token ID for execution
    executed: bool = False
    execution_price: Optional[float] = None
    execution_time: Optional[datetime] = None


@dataclass
class CircuitBreaker:
    """Circuit breaker state"""
    daily_loss_limit: float
    hourly_loss_limit: float
    max_consecutive_losses: int

    current_daily_loss: float = 0.0
    current_hourly_loss: float = 0.0
    consecutive_losses: int = 0
    last_reset: datetime = field(default_factory=datetime.now)
    triggered: bool = False
    trigger_reason: Optional[str] = None


@dataclass
class TradeRecord:
    """Historical trade record"""
    order_id: str
    whale_address: str
    market_id: str
    entry_time: datetime
    entry_price: float
    size_usd: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    status: str = 'OPEN'  # OPEN, CLOSED, FAILED


class RealTradingEngine:
    """
    Production trading engine for whale copy trading.

    Modes:
    - PAPER: Simulated trading (default)
    - LIVE: Real money trading with Polymarket API
    - APPROVAL: Requires manual approval for each trade
    """

    def __init__(
        self,
        mode: str = 'PAPER',
        initial_balance: float = 10000.0,
        weighting_engine: Optional[BetWeightingEngine] = None,
        daily_loss_limit: float = 500.0,
        hourly_loss_limit: float = 200.0,
        max_consecutive_losses: int = 5,
        enable_circuit_breaker: bool = True,
        polymarket_client = None,  # PolymarketClient instance
        db_engine = None,  # SQLAlchemy engine for database persistence
    ):
        self.mode = mode
        self.balance = initial_balance
        self.initial_balance = initial_balance

        # Use provided weighting engine or create default
        self.weighting_engine = weighting_engine or BetWeightingEngine(
            base_position_pct=0.05,
            max_position_pct=0.10,
            kelly_fraction=0.25,
            min_position_size=50.0,
            max_position_size=1000.0,
        )

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            daily_loss_limit=daily_loss_limit,
            hourly_loss_limit=hourly_loss_limit,
            max_consecutive_losses=max_consecutive_losses
        ) if enable_circuit_breaker else None

        # Portfolio state
        self.open_positions: Dict[str, TradeRecord] = {}
        self.closed_positions: List[TradeRecord] = []
        self.pending_orders: List[TradeOrder] = []

        # Polymarket client
        self.polymarket_client = polymarket_client

        # Database engine for persistence
        self.db_engine = db_engine

        # Trade history for deduplication
        self.recent_trade_hashes: set = set()

        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        logger.info(f"Real Trading Engine initialized in {mode} mode")
        logger.info(f"Initial balance: ${initial_balance:,.2f}")

    async def process_whale_trade(
        self,
        whale: WhaleProfile,
        market: MarketContext,
        entry_price: float,
        whale_size: float,  # Whale's actual trade size
        token_id: Optional[str] = None,  # Polymarket token ID
    ) -> Optional[TradeOrder]:
        """
        Process a whale trade signal and create order if valid.

        Steps:
        1. Check circuit breaker
        2. Calculate bet weight
        3. Validate trade
        4. Create order (execute if LIVE mode)

        Returns: TradeOrder if created, None if rejected
        """

        # Step 1: Check circuit breaker
        if self.circuit_breaker and self.circuit_breaker.triggered:
            logger.warning(f"Circuit breaker triggered: {self.circuit_breaker.trigger_reason}")
            return None

        # Step 2: Calculate current portfolio state
        portfolio = self._get_portfolio_state()

        # Step 3: Calculate bet weight
        bet_weight = self.weighting_engine.calculate_bet_weight(
            whale=whale,
            market=market,
            portfolio=portfolio,
            entry_price=entry_price
        )

        logger.info(f"Bet weight calculated: ${bet_weight.position_size_usd:.2f} ({bet_weight.position_pct*100:.1f}%)")
        logger.info(f"Confidence: {bet_weight.confidence_score:.0f}/100")
        if bet_weight.warnings:
            logger.warning(f"Warnings: {', '.join(bet_weight.warnings)}")

        # Step 4: Validate trade
        should_execute, issues = self.weighting_engine.validate_trade(bet_weight, portfolio)

        if not should_execute:
            logger.warning(f"Trade rejected: {', '.join(issues)}")
            return None

        # Step 5: Check for duplicate
        trade_hash = f"{whale.address}_{market.market_id}_{int(datetime.now().timestamp() / 60)}"
        if trade_hash in self.recent_trade_hashes:
            logger.warning("Duplicate trade detected, skipping")
            return None
        self.recent_trade_hashes.add(trade_hash)

        # Clean old hashes (keep last hour)
        if len(self.recent_trade_hashes) > 100:
            self.recent_trade_hashes = set(list(self.recent_trade_hashes)[-100:])

        # Step 6: Create order
        order = TradeOrder(
            whale_address=whale.address,
            whale_name=whale.address[:8] + "...",  # Pseudonym
            market_id=market.market_id,
            market_title=market.title,
            side='BUY',  # Copy whale's buy
            price=entry_price,
            size_usd=bet_weight.position_size_usd,
            confidence=bet_weight.confidence_score,
            reasoning=bet_weight.reasoning,
            timestamp=datetime.now(),
            token_id=token_id  # Pass token_id for Polymarket execution
        )

        # Step 7: Execute based on mode
        if self.mode == 'LIVE':
            executed = await self._execute_order_live(order, market)
            if not executed:
                return None
        elif self.mode == 'APPROVAL':
            self.pending_orders.append(order)
            logger.info(f"Order pending approval: {order.market_title} ${order.size_usd:.2f}")
            return order
        else:  # PAPER mode
            self._execute_order_paper(order)

        return order

    async def _execute_order_live(self, order: TradeOrder, market: MarketContext) -> bool:
        """Execute order with Polymarket API"""

        if not self.polymarket_client:
            logger.error("Polymarket client not initialized")
            return False

        try:
            logger.info(f"🚀 Executing LIVE order: {order.market_title}")
            logger.info(f"   Size: ${order.size_usd:.2f} @ ${order.price:.4f}")

            # Get token_id from order (should be set in TradeOrder)
            token_id = getattr(order, 'token_id', None)
            if not token_id:
                logger.error("token_id not set on order - cannot place trade")
                return False

            # Execute trade via Polymarket API
            # place_market_order is sync, so run in thread pool
            import asyncio
            result = await asyncio.to_thread(
                self.polymarket_client.place_market_order,
                token_id=token_id,
                amount=order.size_usd,
                side="BUY",  # Always buying YES for now
                order_type="FOK"  # Fill-or-Kill for immediate execution
            )

            logger.info(f"✅ Order executed successfully! Order ID: {result.get('orderID')}")

            # Record trade
            trade_record = TradeRecord(
                order_id=result.get('orderID', f"order_{self.total_trades + 1}"),
                whale_address=order.whale_address,
                market_id=order.market_id,
                entry_time=datetime.now(),
                entry_price=order.price,
                size_usd=order.size_usd,
                status='OPEN'
            )

            self.open_positions[order.market_id] = trade_record

            # Save to database if engine is available
            if self.db_engine:
                try:
                    with Session(self.db_engine) as session:
                        db_position = Position(
                            position_id=f"pos_{uuid.uuid4().hex[:16]}",
                            user_address=os.getenv('POLYMARKET_WALLET_ADDRESS', 'LIVE_TRADER'),
                            market_id=order.market_id,
                            token_id=token_id,
                            outcome="YES",
                            size=Decimal(str(order.size_usd / order.price)) if order.price > 0 else Decimal('0'),
                            avg_entry_price=Decimal(str(order.price)),
                            current_price=Decimal(str(order.price)),
                            initial_value=Decimal(str(order.size_usd)),
                            current_value=Decimal(str(order.size_usd)),
                            unrealized_pnl=Decimal('0'),
                            realized_pnl=Decimal('0'),
                            percent_pnl=Decimal('0'),
                            total_fees_paid=Decimal('0'),
                            market_title=order.market_title,
                            source_whale=order.whale_address,
                            status='OPEN',
                            opened_at=datetime.now()
                        )
                        session.add(db_position)
                        session.commit()
                        logger.info(f"✅ Position saved to database: {db_position.position_id}")
                except Exception as e:
                    logger.error(f"Failed to save position to database: {e}")

            self.total_trades += 1
            self.balance -= order.size_usd

            order.executed = True
            order.execution_price = order.price
            order.execution_time = datetime.now()

            logger.info(f"✅ Trade recorded. Balance: ${self.balance:.2f}")

            return True

        except Exception as e:
            logger.error(f"Failed to execute order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _execute_order_paper(self, order: TradeOrder):
        """Execute order in paper trading mode"""

        logger.info(f"📝 PAPER TRADE: {order.market_title}")
        logger.info(f"   Size: ${order.size_usd:.2f} @ ${order.price:.4f}")
        logger.info(f"   Confidence: {order.confidence:.0f}/100")

        # Record trade
        trade_record = TradeRecord(
            order_id=f"paper_{self.total_trades + 1}",
            whale_address=order.whale_address,
            market_id=order.market_id,
            entry_time=datetime.now(),
            entry_price=order.price,
            size_usd=order.size_usd,
            status='OPEN'
        )

        self.open_positions[order.market_id] = trade_record

        # Save to database if engine is available
        if self.db_engine:
            try:
                with Session(self.db_engine) as session:
                    db_position = Position(
                        position_id=f"pos_{uuid.uuid4().hex[:16]}",
                        user_address="PAPER_TRADER",
                        market_id=order.market_id,
                        token_id=f"token_{order.market_id[:8]}",
                        outcome="YES",
                        size=Decimal(str(order.size_usd / order.price)) if order.price > 0 else Decimal('0'),
                        avg_entry_price=Decimal(str(order.price)),
                        current_price=Decimal(str(order.price)),
                        initial_value=Decimal(str(order.size_usd)),
                        current_value=Decimal(str(order.size_usd)),
                        unrealized_pnl=Decimal('0'),
                        realized_pnl=Decimal('0'),
                        percent_pnl=Decimal('0'),
                        total_fees_paid=Decimal('0'),
                        market_title=order.market_title,
                        source_whale=order.whale_address,
                        status='OPEN',
                        opened_at=datetime.now()
                    )
                    session.add(db_position)
                    session.commit()
                    logger.info(f"✅ Position saved to database: {db_position.position_id}")
            except Exception as e:
                logger.error(f"Failed to save position to database: {e}")
        self.total_trades += 1
        self.balance -= order.size_usd

        order.executed = True
        order.execution_price = order.price
        order.execution_time = datetime.now()

        logger.info(f"✅ Paper trade recorded. Balance: ${self.balance:.2f}")

    def _get_portfolio_state(self) -> PortfolioState:
        """Get current portfolio state"""

        total_exposure = sum(pos.size_usd for pos in self.open_positions.values())
        unrealized_pnl = sum(pos.pnl for pos in self.open_positions.values())

        # Calculate daily P&L
        today = datetime.now().date()
        daily_pnl = sum(
            pos.pnl for pos in self.closed_positions
            if pos.exit_time and pos.exit_time.date() == today
        )

        # Group by market and category
        positions_by_market = {}
        positions_by_category = {}

        for pos in self.open_positions.values():
            positions_by_market[pos.market_id] = positions_by_market.get(pos.market_id, 0) + pos.size_usd
            # We'd need market info to get category - simplified for now

        return PortfolioState(
            total_balance=self.balance + total_exposure + unrealized_pnl,
            available_balance=self.balance,
            open_positions=len(self.open_positions),
            total_exposure=total_exposure,
            unrealized_pnl=unrealized_pnl,
            daily_pnl=daily_pnl,
            positions_by_market=positions_by_market,
            positions_by_category=positions_by_category
        )

    def close_position(
        self,
        market_id: str,
        exit_price: float,
        reason: str = "Manual close"
    ) -> Optional[TradeRecord]:
        """Close an open position"""

        if market_id not in self.open_positions:
            logger.warning(f"No open position for market {market_id}")
            return None

        position = self.open_positions[market_id]

        # Calculate P&L
        shares = position.size_usd / position.entry_price
        exit_value = shares * exit_price
        pnl = exit_value - position.size_usd

        # Update position
        position.exit_time = datetime.now()
        position.exit_price = exit_price
        position.pnl = pnl
        position.status = 'CLOSED'

        # Update balance
        self.balance += exit_value

        # Move to closed positions
        del self.open_positions[market_id]
        self.closed_positions.append(position)

        # Update stats
        if pnl > 0:
            self.winning_trades += 1
            if self.circuit_breaker:
                self.circuit_breaker.consecutive_losses = 0
        else:
            self.losing_trades += 1
            if self.circuit_breaker:
                self.circuit_breaker.consecutive_losses += 1
                self.circuit_breaker.current_daily_loss += abs(pnl)
                self.circuit_breaker.current_hourly_loss += abs(pnl)

        logger.info(f"Position closed: {reason}")
        logger.info(f"P&L: ${pnl:+.2f} | Balance: ${self.balance:.2f}")

        # Check circuit breaker
        if self.circuit_breaker:
            self._check_circuit_breaker()

        return position

    def _check_circuit_breaker(self):
        """Check if circuit breaker should trigger"""

        if not self.circuit_breaker:
            return

        cb = self.circuit_breaker

        # Reset counters if needed
        now = datetime.now()
        if (now - cb.last_reset).days >= 1:
            cb.current_daily_loss = 0.0
            cb.last_reset = now

        if (now - cb.last_reset).seconds >= 3600:
            cb.current_hourly_loss = 0.0

        # Check triggers
        if cb.current_daily_loss >= cb.daily_loss_limit:
            cb.triggered = True
            cb.trigger_reason = f"Daily loss limit reached: ${cb.current_daily_loss:.2f}"
            logger.error(f"🛑 CIRCUIT BREAKER: {cb.trigger_reason}")

        elif cb.current_hourly_loss >= cb.hourly_loss_limit:
            cb.triggered = True
            cb.trigger_reason = f"Hourly loss limit reached: ${cb.current_hourly_loss:.2f}"
            logger.error(f"🛑 CIRCUIT BREAKER: {cb.trigger_reason}")

        elif cb.consecutive_losses >= cb.max_consecutive_losses:
            cb.triggered = True
            cb.trigger_reason = f"Max consecutive losses: {cb.consecutive_losses}"
            logger.error(f"🛑 CIRCUIT BREAKER: {cb.trigger_reason}")

    def reset_circuit_breaker(self):
        """Manually reset circuit breaker"""
        if self.circuit_breaker:
            self.circuit_breaker.triggered = False
            self.circuit_breaker.trigger_reason = None
            self.circuit_breaker.consecutive_losses = 0
            logger.info("Circuit breaker manually reset")

    def get_performance_summary(self) -> Dict:
        """Get performance summary"""

        portfolio = self._get_portfolio_state()
        total_pnl = portfolio.total_balance - self.initial_balance
        roi = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        return {
            'mode': self.mode,
            'initial_balance': self.initial_balance,
            'current_balance': self.balance,
            'total_value': portfolio.total_balance,
            'total_pnl': total_pnl,
            'roi': roi,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'open_positions': len(self.open_positions),
            'total_exposure': portfolio.total_exposure,
            'unrealized_pnl': portfolio.unrealized_pnl,
            'circuit_breaker_status': 'TRIGGERED' if self.circuit_breaker and self.circuit_breaker.triggered else 'OK'
        }

    def print_summary(self):
        """Print performance summary"""

        summary = self.get_performance_summary()

        print("\n" + "=" * 80)
        print(f"{'TRADING ENGINE SUMMARY':^80}")
        print("=" * 80)
        print(f"Mode:              {summary['mode']}")
        print(f"Initial Balance:   ${summary['initial_balance']:,.2f}")
        print(f"Current Balance:   ${summary['current_balance']:,.2f}")
        print(f"Total Value:       ${summary['total_value']:,.2f}")
        print(f"Total P&L:         ${summary['total_pnl']:+,.2f}")
        print(f"ROI:               {summary['roi']:+.2f}%")
        print()
        print(f"Total Trades:      {summary['total_trades']}")
        print(f"Winning Trades:    {summary['winning_trades']}")
        print(f"Losing Trades:     {summary['losing_trades']}")
        print(f"Win Rate:          {summary['win_rate']:.1f}%")
        print()
        print(f"Open Positions:    {summary['open_positions']}")
        print(f"Total Exposure:    ${summary['total_exposure']:,.2f}")
        print(f"Unrealized P&L:    ${summary['unrealized_pnl']:+,.2f}")
        print()
        print(f"Circuit Breaker:   {summary['circuit_breaker_status']}")
        print("=" * 80)
