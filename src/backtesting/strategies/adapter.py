"""
Strategy Adapter Interface for Backtesting
Provides a uniform interface for integrating different trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"  # Close position
    REBALANCE = "rebalance"  # Adjust position


class SignalSource(Enum):
    """Source of trading signals."""
    WHALE_COPY = "whale_copy"
    ARBITRAGE = "arbitrage"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    COMPOSITE = "composite"


@dataclass
class TradingSignal:
    """Trading signal from a strategy."""
    timestamp: datetime
    strategy_name: str
    signal_type: SignalType
    source: SignalSource
    market_id: str

    # Signal details
    confidence: float  # 0-100
    size_suggestion: Optional[float] = None  # Suggested position size
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    # Metadata
    metadata: Dict = field(default_factory=dict)
    reasoning: str = ""
    urgency: int = 0  # 0=low, 1=medium, 2=high

    # Risk metrics
    expected_return: Optional[float] = None
    expected_risk: Optional[float] = None
    sharpe_ratio: Optional[float] = None

    # For composite signals
    sub_signals: List['TradingSignal'] = field(default_factory=list)


@dataclass
class StrategyState:
    """Internal state of a strategy."""
    positions: Dict[str, float] = field(default_factory=dict)
    pending_orders: Dict[str, Dict] = field(default_factory=dict)
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    capital_allocated: float = 0
    last_update: Optional[datetime] = None
    custom_state: Dict = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement this interface to work with the backtesting system.
    """

    def __init__(self, name: str, config: Dict = None):
        """
        Initialize strategy.

        Args:
            name: Strategy identifier
            config: Strategy configuration
        """
        self.name = name
        self.config = config or {}
        self.state = StrategyState()
        self.performance_metrics = {}
        self.is_active = True

    @abstractmethod
    def initialize(self, initial_capital: float, start_time: datetime):
        """
        Initialize strategy for backtesting.

        Args:
            initial_capital: Starting capital allocation
            start_time: Backtest start time
        """
        pass

    @abstractmethod
    def on_market_data(
        self,
        timestamp: datetime,
        market_data: Dict[str, Any]
    ) -> List[TradingSignal]:
        """
        Process market data and generate signals.

        Args:
            timestamp: Current time
            market_data: Market state including prices, volumes, etc.

        Returns:
            List of trading signals
        """
        pass

    @abstractmethod
    def on_trade_executed(
        self,
        timestamp: datetime,
        trade: Dict[str, Any]
    ):
        """
        Handle trade execution notification.

        Args:
            timestamp: Execution time
            trade: Executed trade details
        """
        pass

    @abstractmethod
    def on_position_update(
        self,
        timestamp: datetime,
        positions: Dict[str, float]
    ):
        """
        Handle position update.

        Args:
            timestamp: Update time
            positions: Current positions by market
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        signal: TradingSignal,
        available_capital: float,
        current_positions: Dict[str, float]
    ) -> float:
        """
        Calculate position size for a signal.

        Args:
            signal: Trading signal
            available_capital: Available capital
            current_positions: Current positions

        Returns:
            Position size in base currency
        """
        pass

    @abstractmethod
    def get_risk_limits(self) -> Dict[str, float]:
        """
        Get current risk limits.

        Returns:
            Dict with risk limits (max_position, max_loss, etc.)
        """
        pass

    def should_close_position(
        self,
        market_id: str,
        current_price: float,
        position: Dict
    ) -> bool:
        """
        Check if position should be closed.

        Args:
            market_id: Market identifier
            current_price: Current market price
            position: Position details

        Returns:
            True if position should be closed
        """
        # Default implementation with stop-loss and take-profit
        if 'stop_loss' in position and current_price <= position['stop_loss']:
            return True
        if 'take_profit' in position and current_price >= position['take_profit']:
            return True
        return False

    def update_performance_metrics(self, metrics: Dict):
        """Update strategy performance metrics."""
        self.performance_metrics.update(metrics)

    def get_state(self) -> StrategyState:
        """Get current strategy state."""
        return self.state

    def reset(self):
        """Reset strategy state."""
        self.state = StrategyState()
        self.performance_metrics = {}


class WhaleCopyStrategy(BaseStrategy):
    """
    Whale copy trading strategy adapter.
    """

    def __init__(self, config: Dict = None):
        """Initialize whale copy strategy."""
        super().__init__("whale_copy", config)
        self.whale_scores = {}
        self.active_whales = set()
        self.copy_history = []

    def initialize(self, initial_capital: float, start_time: datetime):
        """Initialize for backtesting."""
        self.state.capital_allocated = initial_capital
        self.state.last_update = start_time

        # Load whale quality scores
        self._load_whale_scores()

    def _load_whale_scores(self):
        """Load pre-calculated whale quality scores."""
        # In real implementation, would load from database
        pass

    def on_market_data(
        self,
        timestamp: datetime,
        market_data: Dict[str, Any]
    ) -> List[TradingSignal]:
        """Process whale trades and generate copy signals."""
        signals = []

        # Check for new whale trades
        if 'whale_trades' in market_data:
            for trade in market_data['whale_trades']:
                signal = self._evaluate_whale_trade(trade, timestamp)
                if signal:
                    signals.append(signal)

        return signals

    def _evaluate_whale_trade(
        self,
        trade: Dict,
        timestamp: datetime
    ) -> Optional[TradingSignal]:
        """Evaluate whether to copy a whale trade."""
        whale_id = trade['whale_id']

        # Check whale quality score
        if whale_id not in self.whale_scores:
            return None

        wqs = self.whale_scores[whale_id]
        if wqs < self.config.get('min_wqs', 75):
            return None

        # Check trade filters
        if trade['size_usd'] < self.config.get('min_trade_size', 5000):
            return None

        # Generate signal
        signal = TradingSignal(
            timestamp=timestamp,
            strategy_name=self.name,
            signal_type=SignalType.BUY if trade['side'] == 'buy' else SignalType.SELL,
            source=SignalSource.WHALE_COPY,
            market_id=trade['market_id'],
            confidence=wqs,
            size_suggestion=trade['size_usd'] * self.config.get('copy_ratio', 0.1),
            metadata={
                'whale_id': whale_id,
                'whale_wqs': wqs,
                'original_trade': trade
            },
            reasoning=f"Copying whale {whale_id[:8]} with WQS={wqs:.1f}"
        )

        return signal

    def on_trade_executed(self, timestamp: datetime, trade: Dict[str, Any]):
        """Handle trade execution."""
        self.copy_history.append({
            'timestamp': timestamp,
            'trade': trade
        })

    def on_position_update(
        self,
        timestamp: datetime,
        positions: Dict[str, float]
    ):
        """Update internal position tracking."""
        self.state.positions = positions.copy()
        self.state.last_update = timestamp

    def calculate_position_size(
        self,
        signal: TradingSignal,
        available_capital: float,
        current_positions: Dict[str, float]
    ) -> float:
        """Calculate position size using adaptive Kelly criterion."""
        # Get whale tier
        wqs = signal.metadata.get('whale_wqs', 75)

        if wqs >= 90:
            copy_percentage = 1.0
            max_position = self.config.get('god_tier_max', 2000)
        elif wqs >= 80:
            copy_percentage = 0.75
            max_position = self.config.get('elite_tier_max', 1500)
        else:
            copy_percentage = 0.5
            max_position = self.config.get('quality_tier_max', 1000)

        # Apply Kelly criterion
        suggested_size = signal.size_suggestion or 1000
        position_size = suggested_size * copy_percentage

        # Apply constraints
        position_size = min(position_size, max_position)
        position_size = min(position_size, available_capital * 0.25)  # Max 25% per position

        return position_size

    def get_risk_limits(self) -> Dict[str, float]:
        """Get whale copy risk limits."""
        return {
            'max_position_pct': 0.25,
            'max_whale_exposure': 0.5,  # Max 50% following single whale
            'max_correlation': 0.4,
            'stop_loss_pct': 0.05
        }


class ArbitrageStrategy(BaseStrategy):
    """
    Arbitrage strategy adapter for structural opportunities.
    """

    def __init__(self, config: Dict = None):
        """Initialize arbitrage strategy."""
        super().__init__("arbitrage", config)
        self.opportunities = []
        self.execution_times = []

    def initialize(self, initial_capital: float, start_time: datetime):
        """Initialize for backtesting."""
        self.state.capital_allocated = initial_capital
        self.state.last_update = start_time

    def on_market_data(
        self,
        timestamp: datetime,
        market_data: Dict[str, Any]
    ) -> List[TradingSignal]:
        """Detect and signal arbitrage opportunities."""
        signals = []

        # Check sum-of-shares arbitrage
        sum_arb = self._check_sum_of_shares(market_data)
        if sum_arb:
            signals.append(sum_arb)

        # Check post-resolution discount
        resolution_arb = self._check_post_resolution(market_data)
        if resolution_arb:
            signals.append(resolution_arb)

        return signals

    def _check_sum_of_shares(
        self,
        market_data: Dict
    ) -> Optional[TradingSignal]:
        """Check for sum-of-shares mispricing."""
        # Look for YES/NO pair
        for market_id in market_data.get('markets', {}):
            market = market_data['markets'][market_id]

            if 'yes_ask' in market and 'no_ask' in market:
                sum_asks = market['yes_ask'] + market['no_ask']

                if sum_asks < 1.0:
                    edge_bps = (1.0 - sum_asks) * 10000

                    if edge_bps >= self.config.get('min_edge_bps', 100):
                        return TradingSignal(
                            timestamp=market_data['timestamp'],
                            strategy_name=self.name,
                            signal_type=SignalType.BUY,
                            source=SignalSource.ARBITRAGE,
                            market_id=market_id,
                            confidence=min(100, edge_bps / 10),  # Scale confidence by edge
                            metadata={
                                'arbitrage_type': 'sum_of_shares',
                                'yes_ask': market['yes_ask'],
                                'no_ask': market['no_ask'],
                                'edge_bps': edge_bps
                            },
                            reasoning=f"Sum-of-shares arbitrage: {edge_bps:.0f}bps edge",
                            urgency=2,  # High urgency
                            expected_return=edge_bps / 10000
                        )

        return None

    def _check_post_resolution(
        self,
        market_data: Dict
    ) -> Optional[TradingSignal]:
        """Check for post-resolution discount opportunities."""
        # Implementation for post-resolution arbitrage
        pass

    def on_trade_executed(self, timestamp: datetime, trade: Dict[str, Any]):
        """Track arbitrage execution times."""
        self.execution_times.append(
            (timestamp - trade['signal_timestamp']).total_seconds()
        )

    def on_position_update(
        self,
        timestamp: datetime,
        positions: Dict[str, float]
    ):
        """Update positions."""
        self.state.positions = positions.copy()
        self.state.last_update = timestamp

    def calculate_position_size(
        self,
        signal: TradingSignal,
        available_capital: float,
        current_positions: Dict[str, float]
    ) -> float:
        """Calculate arbitrage position size."""
        # Arbitrage typically uses larger positions due to lower risk
        edge = signal.metadata.get('edge_bps', 100) / 10000

        # Size based on edge and available capital
        if edge > 0.03:  # >3% edge
            size = available_capital * 0.5  # Use 50% of capital
        elif edge > 0.02:  # >2% edge
            size = available_capital * 0.3
        else:
            size = available_capital * 0.2

        # Cap at max position
        max_position = self.config.get('max_position', 50000)
        return min(size, max_position)

    def get_risk_limits(self) -> Dict[str, float]:
        """Get arbitrage risk limits."""
        return {
            'max_position_pct': 0.5,  # Can use more capital for low-risk arb
            'min_edge_bps': 100,
            'max_execution_time_ms': 3000,
            'max_slippage_bps': 50
        }


class CompositeStrategy(BaseStrategy):
    """
    Composite strategy that combines multiple sub-strategies.
    """

    def __init__(self, strategies: List[BaseStrategy], config: Dict = None):
        """Initialize composite strategy."""
        super().__init__("composite", config)
        self.strategies = strategies
        self.strategy_weights = config.get('weights', {})
        self.signal_buffer = []

    def initialize(self, initial_capital: float, start_time: datetime):
        """Initialize all sub-strategies."""
        # Allocate capital to sub-strategies
        for strategy in self.strategies:
            weight = self.strategy_weights.get(strategy.name, 1.0 / len(self.strategies))
            strategy.initialize(initial_capital * weight, start_time)

        self.state.capital_allocated = initial_capital
        self.state.last_update = start_time

    def on_market_data(
        self,
        timestamp: datetime,
        market_data: Dict[str, Any]
    ) -> List[TradingSignal]:
        """Aggregate signals from all strategies."""
        all_signals = []

        # Collect signals from all strategies
        for strategy in self.strategies:
            signals = strategy.on_market_data(timestamp, market_data)
            all_signals.extend(signals)

        # Aggregate and filter signals
        combined_signals = self._aggregate_signals(all_signals, timestamp)

        return combined_signals

    def _aggregate_signals(
        self,
        signals: List[TradingSignal],
        timestamp: datetime
    ) -> List[TradingSignal]:
        """Aggregate multiple signals into composite signals."""
        # Group signals by market
        market_signals = {}
        for signal in signals:
            if signal.market_id not in market_signals:
                market_signals[signal.market_id] = []
            market_signals[signal.market_id].append(signal)

        # Create composite signals
        composite_signals = []
        for market_id, market_signal_list in market_signals.items():
            if len(market_signal_list) >= self.config.get('min_confirmations', 2):
                # Multiple strategies agree
                composite = self._create_composite_signal(
                    market_signal_list,
                    timestamp
                )
                composite_signals.append(composite)

        return composite_signals

    def _create_composite_signal(
        self,
        signals: List[TradingSignal],
        timestamp: datetime
    ) -> TradingSignal:
        """Create composite signal from multiple signals."""
        # Weighted average confidence
        total_weight = 0
        weighted_confidence = 0

        for signal in signals:
            weight = self.strategy_weights.get(signal.strategy_name, 1.0)
            weighted_confidence += signal.confidence * weight
            total_weight += weight

        avg_confidence = weighted_confidence / total_weight if total_weight > 0 else 0

        # Determine signal type (majority vote)
        signal_types = [s.signal_type for s in signals]
        most_common_type = max(set(signal_types), key=signal_types.count)

        return TradingSignal(
            timestamp=timestamp,
            strategy_name=self.name,
            signal_type=most_common_type,
            source=SignalSource.COMPOSITE,
            market_id=signals[0].market_id,
            confidence=avg_confidence,
            sub_signals=signals,
            metadata={
                'num_confirmations': len(signals),
                'strategies': [s.strategy_name for s in signals]
            },
            reasoning=f"Composite signal from {len(signals)} strategies"
        )

    def on_trade_executed(self, timestamp: datetime, trade: Dict[str, Any]):
        """Notify all strategies of trade execution."""
        for strategy in self.strategies:
            strategy.on_trade_executed(timestamp, trade)

    def on_position_update(
        self,
        timestamp: datetime,
        positions: Dict[str, float]
    ):
        """Update all strategies with position changes."""
        for strategy in self.strategies:
            strategy.on_position_update(timestamp, positions)

        self.state.positions = positions.copy()
        self.state.last_update = timestamp

    def calculate_position_size(
        self,
        signal: TradingSignal,
        available_capital: float,
        current_positions: Dict[str, float]
    ) -> float:
        """Calculate position size for composite signal."""
        # Use the most conservative size from sub-signals
        sizes = []

        for sub_signal in signal.sub_signals:
            # Get the strategy that generated this signal
            strategy = next((s for s in self.strategies if s.name == sub_signal.strategy_name), None)
            if strategy:
                size = strategy.calculate_position_size(
                    sub_signal,
                    available_capital,
                    current_positions
                )
                sizes.append(size)

        # Use average or minimum based on config
        if self.config.get('size_method', 'average') == 'average':
            return np.mean(sizes) if sizes else 0
        else:
            return min(sizes) if sizes else 0

    def get_risk_limits(self) -> Dict[str, float]:
        """Get composite risk limits (most conservative)."""
        all_limits = {}

        for strategy in self.strategies:
            limits = strategy.get_risk_limits()
            for key, value in limits.items():
                if key not in all_limits:
                    all_limits[key] = value
                else:
                    # Use most conservative limit
                    all_limits[key] = min(all_limits[key], value)

        return all_limits