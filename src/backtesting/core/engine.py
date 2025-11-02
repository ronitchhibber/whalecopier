"""
Event-Driven Backtesting Engine Core
Handles discrete event simulation for accurate multi-strategy backtesting
"""

import heapq
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the backtesting system."""
    # Market events
    MARKET_TICK = "market_tick"
    ORDER_BOOK_UPDATE = "orderbook_update"
    TRADE_EXECUTED = "trade_executed"

    # Strategy events
    WHALE_CHECK = "whale_check"  # 5-minute whale monitoring
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Risk events
    STOP_LOSS_TRIGGERED = "stop_loss"
    TAKE_PROFIT_TRIGGERED = "take_profit"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker"

    # System events
    PORTFOLIO_UPDATE = "portfolio_update"
    RISK_CHECK = "risk_check"
    MARKET_CLOSE = "market_close"
    MARKET_RESOLUTION = "market_resolution"

    # Arbitrage events (sub-second)
    ARBITRAGE_OPPORTUNITY = "arbitrage_opportunity"
    ATOMIC_EXECUTION = "atomic_execution"

    # Behavioral events (hourly)
    OVERREACTION_CHECK = "overreaction_check"
    ROUND_NUMBER_CHECK = "round_number_check"
    CAPITULATION_CHECK = "capitulation_check"


@dataclass(order=True)
class Event:
    """Event in the simulation with priority ordering by timestamp."""
    timestamp: datetime
    event_type: EventType
    priority: int = field(default=0)  # Lower number = higher priority for same timestamp
    data: Dict = field(default_factory=dict, compare=False)
    callback: Optional[Callable] = field(default=None, compare=False)

    def __post_init__(self):
        """Set priority based on event type for proper ordering."""
        # Priority ensures market events process before strategy events
        priority_map = {
            EventType.MARKET_TICK: 0,
            EventType.ORDER_BOOK_UPDATE: 1,
            EventType.TRADE_EXECUTED: 2,
            EventType.ARBITRAGE_OPPORTUNITY: 3,  # High priority for speed
            EventType.ATOMIC_EXECUTION: 4,
            EventType.SIGNAL_GENERATED: 10,
            EventType.ORDER_PLACED: 11,
            EventType.ORDER_FILLED: 12,
            EventType.WHALE_CHECK: 20,
            EventType.OVERREACTION_CHECK: 21,
            EventType.RISK_CHECK: 30,
            EventType.PORTFOLIO_UPDATE: 40,
        }
        self.priority = priority_map.get(self.event_type, 50)


class EventHandler(ABC):
    """Abstract base class for event handlers."""

    @abstractmethod
    def handle_event(self, event: Event, context: Dict) -> List[Event]:
        """
        Handle an event and return new events to be scheduled.

        Args:
            event: The event to handle
            context: Shared context containing market state, portfolio, etc.

        Returns:
            List of new events to be scheduled
        """
        pass


class BacktestingEngine:
    """
    Event-driven backtesting engine for multi-strategy simulation.

    Supports concurrent execution of strategies with different time horizons:
    - Sub-second arbitrage strategies
    - 5-minute whale monitoring
    - Hourly behavioral pattern detection
    - Daily risk management checks
    """

    def __init__(self, config: Dict = None):
        """Initialize the backtesting engine."""
        self.config = config or self._default_config()

        # Event queue (priority queue)
        self.event_queue: List[Event] = []
        heapq.heapify(self.event_queue)

        # Event handlers by type
        self.handlers: Dict[EventType, List[EventHandler]] = {}

        # Simulation state
        self.current_time: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # Shared context for all handlers
        self.context = {
            'portfolio': {},
            'positions': {},
            'orders': {},
            'market_state': {},
            'strategy_state': {},
            'risk_metrics': {},
            'performance': {},
            'capital': self.config['initial_capital']
        }

        # Performance tracking
        self.event_count = 0
        self.events_by_type: Dict[EventType, int] = {}

        # Strategy scheduling
        self.scheduled_strategies: Dict[str, Dict] = {}

    def _default_config(self) -> Dict:
        """Default configuration for backtesting."""
        return {
            'initial_capital': 10000,
            'max_events': 1000000,  # Safety limit
            'time_step_seconds': 1,  # Minimum time resolution
            'enable_logging': True,
            'log_every_n_events': 1000
        }

    def register_handler(self, event_type: EventType, handler: EventHandler):
        """Register a handler for a specific event type."""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler {handler.__class__.__name__} for {event_type.value}")

    def schedule_event(self, event: Event):
        """Schedule an event to be processed."""
        heapq.heappush(self.event_queue, event)

    def schedule_recurring_event(
        self,
        event_type: EventType,
        start_time: datetime,
        interval: timedelta,
        data: Dict = None,
        count: Optional[int] = None
    ):
        """
        Schedule a recurring event (e.g., whale checks every 5 minutes).

        Args:
            event_type: Type of event to schedule
            start_time: When to start scheduling
            interval: Time between events
            data: Event data
            count: Number of occurrences (None for infinite)
        """
        current = start_time
        occurrences = 0

        while current <= self.end_time:
            if count and occurrences >= count:
                break

            self.schedule_event(Event(
                timestamp=current,
                event_type=event_type,
                data=data or {}
            ))

            current += interval
            occurrences += 1

    def initialize_strategies(self):
        """Initialize all trading strategies with their schedules."""
        start = self.start_time
        end = self.end_time

        # Schedule whale monitoring (every 5 minutes)
        self.schedule_recurring_event(
            EventType.WHALE_CHECK,
            start,
            timedelta(minutes=5),
            {'strategy': 'whale_copy'}
        )

        # Schedule behavioral checks (every hour)
        self.schedule_recurring_event(
            EventType.OVERREACTION_CHECK,
            start,
            timedelta(hours=1),
            {'strategy': 'overreaction_fade'}
        )

        self.schedule_recurring_event(
            EventType.ROUND_NUMBER_CHECK,
            start + timedelta(minutes=30),  # Offset to spread load
            timedelta(hours=1),
            {'strategy': 'round_number'}
        )

        # Schedule risk checks (every 15 minutes)
        self.schedule_recurring_event(
            EventType.RISK_CHECK,
            start,
            timedelta(minutes=15),
            {'check_type': 'portfolio_risk'}
        )

        # Schedule portfolio updates (every minute for accuracy)
        self.schedule_recurring_event(
            EventType.PORTFOLIO_UPDATE,
            start,
            timedelta(minutes=1),
            {'update_type': 'mark_to_market'}
        )

        logger.info(f"Initialized strategies with {len(self.event_queue)} initial events")

    def run(
        self,
        start_time: datetime,
        end_time: datetime,
        market_data_provider: Any = None,
        strategies: List[Any] = None
    ) -> Dict:
        """
        Run the backtest simulation.

        Args:
            start_time: Simulation start time
            end_time: Simulation end time
            market_data_provider: Provider for market data
            strategies: List of strategies to backtest

        Returns:
            Backtest results and performance metrics
        """
        self.start_time = start_time
        self.end_time = end_time
        self.current_time = start_time

        # Store providers
        self.context['market_data_provider'] = market_data_provider
        self.context['strategies'] = strategies or []

        # Initialize strategies and their schedules
        self.initialize_strategies()

        # Initialize market data events
        if market_data_provider:
            self._schedule_market_events(market_data_provider)

        logger.info(f"Starting backtest from {start_time} to {end_time}")
        logger.info(f"Event queue contains {len(self.event_queue)} initial events")

        # Main event loop
        while self.event_queue and self.event_count < self.config['max_events']:
            # Get next event
            event = heapq.heappop(self.event_queue)

            # Update simulation time
            self.current_time = event.timestamp
            self.context['current_time'] = self.current_time

            # Skip events beyond end time
            if self.current_time > end_time:
                break

            # Process event
            self._process_event(event)

            # Track statistics
            self.event_count += 1
            self.events_by_type[event.event_type] = \
                self.events_by_type.get(event.event_type, 0) + 1

            # Periodic logging
            if self.config['enable_logging'] and \
               self.event_count % self.config['log_every_n_events'] == 0:
                self._log_progress()

        # Final portfolio update
        self._finalize_portfolio()

        # Generate results
        results = self._generate_results()

        logger.info(f"Backtest complete. Processed {self.event_count} events")

        return results

    def _process_event(self, event: Event):
        """Process a single event."""
        # Execute callback if provided
        if event.callback:
            try:
                new_events = event.callback(event, self.context)
                if new_events:
                    for new_event in new_events:
                        self.schedule_event(new_event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

        # Execute registered handlers
        if event.event_type in self.handlers:
            for handler in self.handlers[event.event_type]:
                try:
                    new_events = handler.handle_event(event, self.context)
                    if new_events:
                        for new_event in new_events:
                            self.schedule_event(new_event)
                except Exception as e:
                    logger.error(f"Error in handler {handler.__class__.__name__}: {e}")

    def _schedule_market_events(self, market_data_provider):
        """Schedule market data events from provider."""
        # This would iterate through historical data and schedule events
        # For now, simplified implementation

        # Schedule market ticks
        tick_interval = timedelta(seconds=self.config['time_step_seconds'])
        current = self.start_time

        while current <= self.end_time:
            # Get market data at this timestamp
            market_data = market_data_provider.get_data_at(current)

            if market_data:
                self.schedule_event(Event(
                    timestamp=current,
                    event_type=EventType.MARKET_TICK,
                    data={'market_data': market_data}
                ))

            current += tick_interval

    def _finalize_portfolio(self):
        """Finalize portfolio calculations at end of backtest."""
        # Mark all positions to market
        for position_id, position in self.context['positions'].items():
            if position['status'] == 'open':
                # Get final market price
                market_id = position['market_id']
                final_price = self.context['market_state'].get(market_id, {}).get('last_price', 0)

                # Calculate final P&L
                if position['side'] == 'BUY':
                    pnl = (final_price - position['entry_price']) * position['size']
                else:
                    pnl = (position['entry_price'] - final_price) * position['size']

                position['unrealized_pnl'] = pnl
                position['final_price'] = final_price

    def _generate_results(self) -> Dict:
        """Generate comprehensive backtest results."""
        positions = self.context['positions']

        # Calculate P&L
        total_pnl = sum(p.get('realized_pnl', 0) + p.get('unrealized_pnl', 0)
                       for p in positions.values())

        # Calculate metrics
        returns = []
        for position in positions.values():
            if position.get('exit_price'):
                ret = (position['exit_price'] - position['entry_price']) / position['entry_price']
                returns.append(ret)

        returns = np.array(returns) if returns else np.array([0])

        # Calculate Sharpe ratio
        if len(returns) > 1 and returns.std() > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252)
        else:
            sharpe = 0

        # Calculate win rate
        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / len(returns) if returns.size > 0 else 0

        return {
            'summary': {
                'total_pnl': total_pnl,
                'initial_capital': self.config['initial_capital'],
                'final_capital': self.config['initial_capital'] + total_pnl,
                'total_return': total_pnl / self.config['initial_capital'],
                'sharpe_ratio': sharpe,
                'win_rate': win_rate,
                'total_trades': len(positions),
                'total_events': self.event_count
            },
            'positions': positions,
            'event_statistics': self.events_by_type,
            'context': self.context
        }

    def _log_progress(self):
        """Log backtesting progress."""
        elapsed = self.current_time - self.start_time
        total = self.end_time - self.start_time
        progress = elapsed / total if total.total_seconds() > 0 else 0

        logger.info(f"Progress: {progress:.1%} | "
                   f"Time: {self.current_time} | "
                   f"Events: {self.event_count} | "
                   f"Queue: {len(self.event_queue)}")


class StrategyScheduler:
    """
    Manages scheduling of different strategies based on their time requirements.
    """

    def __init__(self, engine: BacktestingEngine):
        self.engine = engine
        self.schedules = {}

    def add_strategy(
        self,
        name: str,
        strategy: Any,
        schedule_type: str,
        interval: Optional[timedelta] = None,
        trigger_condition: Optional[Callable] = None
    ):
        """
        Add a strategy with its scheduling requirements.

        Args:
            name: Strategy identifier
            strategy: Strategy instance
            schedule_type: 'periodic', 'triggered', or 'continuous'
            interval: For periodic strategies
            trigger_condition: For triggered strategies
        """
        self.schedules[name] = {
            'strategy': strategy,
            'type': schedule_type,
            'interval': interval,
            'trigger': trigger_condition,
            'last_run': None
        }

        # Schedule based on type
        if schedule_type == 'periodic' and interval:
            self._schedule_periodic_strategy(name, interval)
        elif schedule_type == 'triggered':
            self._setup_trigger_monitoring(name, trigger_condition)
        elif schedule_type == 'continuous':
            self._setup_continuous_monitoring(name)

    def _schedule_periodic_strategy(self, name: str, interval: timedelta):
        """Schedule a strategy to run periodically."""
        def strategy_callback(event: Event, context: Dict) -> List[Event]:
            strategy = self.schedules[name]['strategy']

            # Run strategy
            signals = strategy.generate_signals(context)

            # Convert signals to events
            new_events = []
            for signal in signals:
                new_events.append(Event(
                    timestamp=event.timestamp,
                    event_type=EventType.SIGNAL_GENERATED,
                    data={'strategy': name, 'signal': signal}
                ))

            # Schedule next run
            next_run = event.timestamp + interval
            if next_run <= self.engine.end_time:
                new_events.append(Event(
                    timestamp=next_run,
                    event_type=event.event_type,
                    data=event.data,
                    callback=strategy_callback
                ))

            return new_events

        # Schedule first run
        first_event = Event(
            timestamp=self.engine.start_time,
            event_type=EventType.WHALE_CHECK if 'whale' in name else EventType.SIGNAL_GENERATED,
            data={'strategy': name},
            callback=strategy_callback
        )
        self.engine.schedule_event(first_event)

    def _setup_trigger_monitoring(self, name: str, trigger_condition: Callable):
        """Setup monitoring for triggered strategies."""
        # This would monitor market conditions and trigger when condition is met
        pass

    def _setup_continuous_monitoring(self, name: str):
        """Setup continuous monitoring for latency-sensitive strategies."""
        # This would run on every market tick
        pass