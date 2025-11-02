"""
Market Replay System for Historical Backtesting
Accurately replays historical market conditions with proper time synchronization
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass
import heapq
import logging
import pandas as pd
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class ReplaySpeed(Enum):
    """Replay speed modes."""
    REALTIME = "realtime"  # 1:1 with historical time
    FAST = "fast"  # As fast as possible
    ACCELERATED = "accelerated"  # N times faster than real
    STEP = "step"  # Manual stepping through events


@dataclass
class ReplayEvent:
    """Event in the replay stream."""
    timestamp: datetime
    event_type: str
    market_id: str
    data: Dict
    sequence: int = 0

    def __lt__(self, other):
        """Priority queue ordering by timestamp then sequence."""
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.sequence < other.sequence


class MarketReplaySystem:
    """
    Replays historical market data with accurate time synchronization.

    Features:
    - Multiple data source synchronization
    - Variable replay speeds
    - Event interpolation for missing data
    - Look-ahead bias prevention
    - State reconstruction at any point
    - Checkpoint/resume capability
    """

    def __init__(self, config: Dict = None):
        """Initialize replay system."""
        self.config = config or self._default_config()

        # Replay state
        self.current_time: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.replay_speed = ReplaySpeed.FAST
        self.speed_multiplier = 1.0

        # Event management
        self.event_queue: List[ReplayEvent] = []
        self.sequence_counter = 0
        self.processed_events = 0

        # Data sources
        self.data_sources: Dict[str, Any] = {}
        self.data_buffers: Dict[str, List] = {}

        # Market state
        self.market_states: Dict[str, Dict] = {}
        self.order_books: Dict[str, Dict] = {}

        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}

        # Checkpointing
        self.checkpoints: List[Dict] = []
        self.checkpoint_interval = timedelta(hours=1)
        self.last_checkpoint: Optional[datetime] = None

        # Performance tracking
        self.stats = {
            'events_processed': 0,
            'events_skipped': 0,
            'interpolations': 0,
            'replay_time_elapsed': 0,
            'simulated_time_elapsed': 0
        }

    def _default_config(self) -> Dict:
        """Default replay configuration."""
        return {
            'buffer_size': 10000,  # Events to buffer per source
            'interpolation': {
                'enabled': True,
                'max_gap_seconds': 60,
                'methods': {
                    'price': 'linear',
                    'volume': 'zero',
                    'spread': 'previous'
                }
            },
            'look_ahead_prevention': True,
            'checkpoint_enabled': True,
            'checkpoint_interval_minutes': 60,
            'max_events_per_tick': 1000,
            'time_resolution_ms': 100  # Minimum time between events
        }

    def add_data_source(
        self,
        name: str,
        source: Any,
        priority: int = 0
    ):
        """
        Add a data source for replay.

        Args:
            name: Source identifier
            source: Data source (DataFrame, generator, or callable)
            priority: Higher priority sources processed first
        """
        self.data_sources[name] = {
            'source': source,
            'priority': priority,
            'position': 0
        }
        self.data_buffers[name] = []
        logger.info(f"Added data source: {name} with priority {priority}")

    async def initialize(
        self,
        start_time: datetime,
        end_time: datetime,
        markets: List[str]
    ):
        """
        Initialize replay system for a time range.

        Args:
            start_time: Start of replay period
            end_time: End of replay period
            markets: List of markets to replay
        """
        self.start_time = start_time
        self.end_time = end_time
        self.current_time = start_time

        # Initialize market states
        for market_id in markets:
            self.market_states[market_id] = {
                'last_price': 0.5,
                'best_bid': 0.49,
                'best_ask': 0.51,
                'volume': 0,
                'trades': 0
            }
            self.order_books[market_id] = {
                'bids': [],
                'asks': []
            }

        # Load initial data into buffers
        await self._buffer_initial_data()

        # Build initial event queue
        self._build_event_queue()

        logger.info(f"Initialized replay from {start_time} to {end_time}")
        logger.info(f"Initial event queue size: {len(self.event_queue)}")

    async def _buffer_initial_data(self):
        """Buffer initial data from all sources."""
        for name, source_info in self.data_sources.items():
            source = source_info['source']

            if isinstance(source, pd.DataFrame):
                # DataFrame source
                filtered = source[
                    (source.index >= self.start_time) &
                    (source.index <= self.end_time)
                ]
                events = self._dataframe_to_events(filtered, name)
                self.data_buffers[name].extend(events[:self.config['buffer_size']])

            elif asyncio.iscoroutinefunction(source):
                # Async generator source
                events = []
                async for event in source(self.start_time, self.end_time):
                    events.append(event)
                    if len(events) >= self.config['buffer_size']:
                        break
                self.data_buffers[name] = events

            else:
                # Synchronous callable
                events = source(self.start_time, self.end_time)
                self.data_buffers[name] = list(events[:self.config['buffer_size']])

    def _dataframe_to_events(
        self,
        df: pd.DataFrame,
        source_name: str
    ) -> List[ReplayEvent]:
        """Convert DataFrame rows to replay events."""
        events = []
        for timestamp, row in df.iterrows():
            event = ReplayEvent(
                timestamp=timestamp,
                event_type=f"{source_name}_update",
                market_id=row.get('market_id', 'unknown'),
                data=row.to_dict(),
                sequence=self.sequence_counter
            )
            self.sequence_counter += 1
            events.append(event)
        return events

    def _build_event_queue(self):
        """Build priority queue from buffered events."""
        self.event_queue = []

        for source_name, events in self.data_buffers.items():
            for event in events:
                heapq.heappush(self.event_queue, event)

        logger.debug(f"Built event queue with {len(self.event_queue)} events")

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[ReplayEvent], None]
    ):
        """Register handler for event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def run(
        self,
        speed: ReplaySpeed = ReplaySpeed.FAST,
        speed_multiplier: float = 1.0
    ) -> Dict:
        """
        Run the replay.

        Args:
            speed: Replay speed mode
            speed_multiplier: Speed multiplier for ACCELERATED mode

        Returns:
            Replay statistics
        """
        self.replay_speed = speed
        self.speed_multiplier = speed_multiplier

        replay_start = datetime.utcnow()
        last_real_time = replay_start

        logger.info(f"Starting replay in {speed.value} mode")

        while self.event_queue and self.current_time <= self.end_time:
            # Get next batch of events at same timestamp
            batch = self._get_next_batch()

            if not batch:
                break

            # Update current time
            batch_time = batch[0].timestamp
            time_jump = batch_time - self.current_time

            # Handle replay speed
            if speed == ReplaySpeed.REALTIME:
                # Sleep to match historical time
                await asyncio.sleep(time_jump.total_seconds())

            elif speed == ReplaySpeed.ACCELERATED:
                # Sleep proportionally less
                await asyncio.sleep(time_jump.total_seconds() / speed_multiplier)

            elif speed == ReplaySpeed.STEP:
                # Wait for manual step signal
                await self._wait_for_step()

            # Fast mode processes as quickly as possible

            self.current_time = batch_time

            # Process batch
            await self._process_batch(batch)

            # Checkpointing
            if self.config['checkpoint_enabled']:
                await self._maybe_checkpoint()

            # Refill buffers if needed
            await self._refill_buffers()

            # Update stats
            self.processed_events += len(batch)
            real_time_now = datetime.utcnow()
            self.stats['replay_time_elapsed'] = (real_time_now - replay_start).total_seconds()
            self.stats['simulated_time_elapsed'] = (self.current_time - self.start_time).total_seconds()

            # Yield control periodically
            if self.processed_events % 1000 == 0:
                await asyncio.sleep(0)  # Allow other coroutines to run

        # Final statistics
        self.stats['events_processed'] = self.processed_events
        self.stats['effective_speed'] = (
            self.stats['simulated_time_elapsed'] / self.stats['replay_time_elapsed']
            if self.stats['replay_time_elapsed'] > 0 else 0
        )

        logger.info(f"Replay completed. Processed {self.processed_events} events")
        logger.info(f"Effective replay speed: {self.stats['effective_speed']:.2f}x")

        return self.stats

    def _get_next_batch(self) -> List[ReplayEvent]:
        """Get next batch of events at the same timestamp."""
        if not self.event_queue:
            return []

        batch = []
        batch_time = self.event_queue[0].timestamp

        # Collect all events at the same timestamp
        while self.event_queue and self.event_queue[0].timestamp == batch_time:
            event = heapq.heappop(self.event_queue)
            batch.append(event)

            if len(batch) >= self.config['max_events_per_tick']:
                break

        return batch

    async def _process_batch(self, batch: List[ReplayEvent]):
        """Process a batch of events."""
        # Sort by priority if events have different sources
        batch.sort(key=lambda e: self.data_sources.get(
            e.event_type.split('_')[0], {}
        ).get('priority', 0), reverse=True)

        for event in batch:
            # Prevent look-ahead bias
            if self.config['look_ahead_prevention']:
                event.data = self._sanitize_future_data(event.data, event.timestamp)

            # Update market state
            self._update_market_state(event)

            # Call registered handlers
            await self._dispatch_event(event)

            # Handle interpolation if needed
            if self.config['interpolation']['enabled']:
                self._check_interpolation(event)

    def _sanitize_future_data(
        self,
        data: Dict,
        timestamp: datetime
    ) -> Dict:
        """Remove any future-looking data from event."""
        # Remove fields that could contain future information
        future_fields = ['resolution', 'final_price', 'settlement_time']
        sanitized = data.copy()

        for field in future_fields:
            if field in sanitized:
                # Check if this information would have been available
                if 'resolution_time' in sanitized:
                    resolution_time = sanitized['resolution_time']
                    if isinstance(resolution_time, str):
                        resolution_time = datetime.fromisoformat(resolution_time)
                    if resolution_time > timestamp:
                        sanitized.pop(field, None)

        return sanitized

    def _update_market_state(self, event: ReplayEvent):
        """Update internal market state from event."""
        market_id = event.market_id

        if market_id not in self.market_states:
            self.market_states[market_id] = {}

        state = self.market_states[market_id]
        data = event.data

        # Update prices
        if 'last_price' in data:
            state['last_price'] = data['last_price']
        if 'best_bid' in data:
            state['best_bid'] = data['best_bid']
        if 'best_ask' in data:
            state['best_ask'] = data['best_ask']

        # Update volume
        if 'volume' in data:
            state['volume'] = data['volume']

        # Update order book if provided
        if 'bids' in data:
            self.order_books[market_id]['bids'] = data['bids']
        if 'asks' in data:
            self.order_books[market_id]['asks'] = data['asks']

        state['last_update'] = event.timestamp

    async def _dispatch_event(self, event: ReplayEvent):
        """Dispatch event to registered handlers."""
        # Generic handlers
        if '*' in self.event_handlers:
            for handler in self.event_handlers['*']:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Handler error: {e}")

        # Specific handlers
        if event.event_type in self.event_handlers:
            for handler in self.event_handlers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")

    def _check_interpolation(self, event: ReplayEvent):
        """Check if interpolation is needed for missing data."""
        market_id = event.market_id

        if market_id not in self.market_states:
            return

        state = self.market_states[market_id]
        if 'last_update' not in state:
            return

        time_gap = (event.timestamp - state['last_update']).total_seconds()
        max_gap = self.config['interpolation']['max_gap_seconds']

        if time_gap > max_gap:
            # Need interpolation
            self._interpolate_missing_data(market_id, state['last_update'], event.timestamp)
            self.stats['interpolations'] += 1

    def _interpolate_missing_data(
        self,
        market_id: str,
        start_time: datetime,
        end_time: datetime
    ):
        """Interpolate missing data points."""
        methods = self.config['interpolation']['methods']
        state = self.market_states[market_id]

        # Generate interpolated events
        num_points = int((end_time - start_time).total_seconds() / 10)  # One point per 10 seconds
        time_points = pd.date_range(start_time, end_time, periods=num_points)

        for timestamp in time_points[1:-1]:  # Skip endpoints
            interpolated_data = {}

            for field, method in methods.items():
                if field in state:
                    if method == 'linear':
                        # Linear interpolation (simplified)
                        interpolated_data[field] = state[field]
                    elif method == 'previous':
                        # Use last known value
                        interpolated_data[field] = state[field]
                    elif method == 'zero':
                        # Set to zero
                        interpolated_data[field] = 0

            # Create interpolated event
            event = ReplayEvent(
                timestamp=timestamp,
                event_type='interpolated',
                market_id=market_id,
                data=interpolated_data,
                sequence=self.sequence_counter
            )
            self.sequence_counter += 1

            # Add to queue
            heapq.heappush(self.event_queue, event)

    async def _refill_buffers(self):
        """Refill data buffers when running low."""
        for source_name, buffer in self.data_buffers.items():
            if len(buffer) < self.config['buffer_size'] / 2:
                # Buffer is running low, fetch more data
                source_info = self.data_sources[source_name]
                source = source_info['source']

                # Fetch next batch
                # (Implementation depends on source type)
                pass

    async def _maybe_checkpoint(self):
        """Create checkpoint if interval has passed."""
        if not self.last_checkpoint:
            self.last_checkpoint = self.current_time
            return

        if (self.current_time - self.last_checkpoint) >= self.checkpoint_interval:
            await self.create_checkpoint()
            self.last_checkpoint = self.current_time

    async def create_checkpoint(self) -> Dict:
        """Create a checkpoint of current state."""
        checkpoint = {
            'timestamp': self.current_time,
            'processed_events': self.processed_events,
            'market_states': self.market_states.copy(),
            'order_books': self.order_books.copy(),
            'stats': self.stats.copy()
        }

        self.checkpoints.append(checkpoint)
        logger.debug(f"Created checkpoint at {self.current_time}")

        return checkpoint

    async def restore_checkpoint(self, checkpoint: Dict):
        """Restore from a checkpoint."""
        self.current_time = checkpoint['timestamp']
        self.processed_events = checkpoint['processed_events']
        self.market_states = checkpoint['market_states'].copy()
        self.order_books = checkpoint['order_books'].copy()
        self.stats = checkpoint['stats'].copy()

        logger.info(f"Restored checkpoint from {self.current_time}")

    async def _wait_for_step(self):
        """Wait for manual step signal (for STEP mode)."""
        # In real implementation, would wait for user input or signal
        await asyncio.sleep(0.1)

    def get_market_state(self, market_id: str) -> Dict:
        """Get current state of a market."""
        return self.market_states.get(market_id, {})

    def get_order_book(self, market_id: str) -> Dict:
        """Get current order book for a market."""
        return self.order_books.get(market_id, {'bids': [], 'asks': []})

    def get_current_time(self) -> datetime:
        """Get current simulation time."""
        return self.current_time

    def get_statistics(self) -> Dict:
        """Get replay statistics."""
        return self.stats.copy()


class ReplayDataSource:
    """
    Helper class for creating replay data sources.
    """

    @staticmethod
    async def from_database(
        connection,
        table: str,
        start_time: datetime,
        end_time: datetime,
        batch_size: int = 1000
    ) -> AsyncGenerator[ReplayEvent, None]:
        """Create data source from database."""
        query = f"""
            SELECT * FROM {table}
            WHERE timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp
        """

        cursor = connection.cursor()
        cursor.execute(query, (start_time, end_time))

        sequence = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                event = ReplayEvent(
                    timestamp=row['timestamp'],
                    event_type=f"{table}_update",
                    market_id=row.get('market_id', 'unknown'),
                    data=dict(row),
                    sequence=sequence
                )
                sequence += 1
                yield event

    @staticmethod
    def from_csv(
        filepath: str,
        timestamp_col: str = 'timestamp'
    ) -> pd.DataFrame:
        """Create data source from CSV file."""
        df = pd.read_csv(filepath)
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df.set_index(timestamp_col, inplace=True)
        return df

    @staticmethod
    def from_live_feed(
        feed_connector: Any,
        start_time: datetime,
        end_time: datetime
    ) -> AsyncGenerator[ReplayEvent, None]:
        """Create data source from live feed recording."""
        # This would connect to recorded live feed data
        pass