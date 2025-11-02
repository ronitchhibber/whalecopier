"""
Multi-Strategy Orchestrator for Backtesting
Coordinates multiple trading strategies with different time horizons and capital allocation
"""

import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np
import logging
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    """Capital allocation methods."""
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    KELLY = "kelly"
    FIXED = "fixed"
    DYNAMIC = "dynamic"


@dataclass
class StrategyAllocation:
    """Capital allocation for a strategy."""
    strategy_name: str
    allocated_capital: float
    used_capital: float
    available_capital: float
    weight: float
    max_allocation: float
    min_allocation: float
    performance_score: float = 0.0
    last_rebalance: Optional[datetime] = None


@dataclass
class PositionRequest:
    """Request to open/modify a position."""
    request_id: str
    strategy_name: str
    timestamp: datetime
    market_id: str
    side: str  # buy/sell
    requested_size: float
    urgency: int  # 0-2
    confidence: float
    metadata: Dict = field(default_factory=dict)


class MultiStrategyOrchestrator:
    """
    Orchestrates multiple trading strategies with:
    - Capital allocation and rebalancing
    - Position netting across strategies
    - Conflict resolution
    - Risk aggregation
    - Performance attribution
    """

    def __init__(self, config: Dict = None):
        """Initialize orchestrator."""
        self.config = config or self._default_config()

        # Strategy management
        self.strategies = {}
        self.strategy_allocations = {}
        self.strategy_performance = defaultdict(dict)

        # Capital management
        self.total_capital = 0
        self.allocated_capital = 0
        self.available_capital = 0

        # Position management
        self.aggregate_positions = {}
        self.position_requests = []
        self.position_attribution = defaultdict(dict)

        # Risk management
        self.risk_limits = {}
        self.current_risk_metrics = {}

        # Performance tracking
        self.rebalance_history = []
        self.execution_queue = asyncio.Queue()

        # Time synchronization
        self.current_time = None
        self.last_rebalance = None

    def _default_config(self) -> Dict:
        """Default orchestrator configuration."""
        return {
            'allocation': {
                'method': AllocationMethod.RISK_PARITY,
                'rebalance_frequency': 'daily',
                'min_rebalance_threshold': 0.05,  # 5% drift triggers rebalance
                'transaction_cost_bps': 5
            },
            'position_management': {
                'enable_netting': True,
                'min_position_size': 10,
                'max_positions': 50,
                'position_timeout_minutes': 30
            },
            'risk_limits': {
                'max_total_exposure': 0.95,
                'max_strategy_exposure': 0.5,
                'max_market_exposure': 0.25,
                'max_correlation': 0.6,
                'max_daily_var': 0.02
            },
            'conflict_resolution': {
                'method': 'weighted_average',  # or 'highest_confidence'
                'min_agreement_threshold': 0.5
            },
            'performance': {
                'lookback_days': 30,
                'min_track_record_days': 7
            }
        }

    def add_strategy(
        self,
        name: str,
        strategy: Any,
        initial_weight: float = None,
        min_allocation: float = 0.0,
        max_allocation: float = 1.0
    ):
        """
        Add a strategy to the orchestrator.

        Args:
            name: Strategy identifier
            strategy: Strategy instance
            initial_weight: Initial capital weight
            min_allocation: Minimum capital allocation
            max_allocation: Maximum capital allocation
        """
        self.strategies[name] = strategy

        # Initialize allocation
        if initial_weight is None:
            initial_weight = 1.0 / (len(self.strategies) + 1)

        self.strategy_allocations[name] = StrategyAllocation(
            strategy_name=name,
            allocated_capital=0,
            used_capital=0,
            available_capital=0,
            weight=initial_weight,
            max_allocation=max_allocation,
            min_allocation=min_allocation
        )

        logger.info(f"Added strategy {name} with weight {initial_weight:.2%}")

    def initialize(
        self,
        total_capital: float,
        start_time: datetime
    ):
        """
        Initialize orchestrator for backtesting.

        Args:
            total_capital: Total capital to allocate
            start_time: Backtest start time
        """
        self.total_capital = total_capital
        self.current_time = start_time
        self.last_rebalance = start_time

        # Initial capital allocation
        self._allocate_capital()

        # Initialize strategies
        for name, strategy in self.strategies.items():
            allocation = self.strategy_allocations[name]
            strategy.initialize(allocation.allocated_capital, start_time)

        logger.info(f"Initialized orchestrator with ${total_capital:,.2f}")

    def _allocate_capital(self):
        """Allocate capital to strategies based on method."""
        method = self.config['allocation']['method']

        if method == AllocationMethod.EQUAL_WEIGHT:
            self._allocate_equal_weight()
        elif method == AllocationMethod.RISK_PARITY:
            self._allocate_risk_parity()
        elif method == AllocationMethod.KELLY:
            self._allocate_kelly()
        elif method == AllocationMethod.DYNAMIC:
            self._allocate_dynamic()
        else:
            self._allocate_fixed()

        # Update available capital
        self.allocated_capital = sum(
            a.allocated_capital for a in self.strategy_allocations.values()
        )
        self.available_capital = self.total_capital - self.allocated_capital

    def _allocate_equal_weight(self):
        """Equal weight allocation."""
        n_strategies = len(self.strategies)
        if n_strategies == 0:
            return

        equal_allocation = self.total_capital / n_strategies

        for name, allocation in self.strategy_allocations.items():
            allocation.allocated_capital = equal_allocation
            allocation.available_capital = equal_allocation
            allocation.weight = 1.0 / n_strategies

    def _allocate_risk_parity(self):
        """Risk parity allocation based on strategy volatilities."""
        # Get strategy volatilities
        volatilities = {}
        for name in self.strategies:
            vol = self._get_strategy_volatility(name)
            volatilities[name] = vol if vol > 0 else 0.01  # Default if no history

        # Calculate inverse volatility weights
        total_inv_vol = sum(1.0 / v for v in volatilities.values())

        for name, allocation in self.strategy_allocations.items():
            weight = (1.0 / volatilities[name]) / total_inv_vol

            # Apply min/max constraints
            weight = max(allocation.min_allocation, min(weight, allocation.max_allocation))

            allocation.weight = weight
            allocation.allocated_capital = self.total_capital * weight
            allocation.available_capital = allocation.allocated_capital - allocation.used_capital

    def _allocate_kelly(self):
        """Kelly criterion-based allocation."""
        kelly_fractions = {}

        for name in self.strategies:
            # Get strategy edge and variance
            returns = self._get_strategy_returns(name)

            if len(returns) > 0:
                mean_return = np.mean(returns)
                variance = np.var(returns)

                if variance > 0:
                    # Kelly fraction = edge / variance
                    kelly = mean_return / variance
                    # Apply fractional Kelly (25%)
                    kelly_fractions[name] = kelly * 0.25
                else:
                    kelly_fractions[name] = 0.05
            else:
                kelly_fractions[name] = 0.05  # Default allocation

        # Normalize to sum to 1
        total_kelly = sum(max(0, k) for k in kelly_fractions.values())
        if total_kelly > 0:
            for name, allocation in self.strategy_allocations.items():
                weight = max(0, kelly_fractions[name]) / total_kelly

                # Apply constraints
                weight = max(allocation.min_allocation, min(weight, allocation.max_allocation))

                allocation.weight = weight
                allocation.allocated_capital = self.total_capital * weight
                allocation.available_capital = allocation.allocated_capital - allocation.used_capital

    def _allocate_dynamic(self):
        """Dynamic allocation based on recent performance."""
        # Score each strategy
        scores = {}
        for name in self.strategies:
            score = self._calculate_strategy_score(name)
            scores[name] = score

        # Allocate proportionally to scores
        total_score = sum(scores.values())
        if total_score > 0:
            for name, allocation in self.strategy_allocations.items():
                weight = scores[name] / total_score

                # Apply constraints
                weight = max(allocation.min_allocation, min(weight, allocation.max_allocation))

                allocation.weight = weight
                allocation.allocated_capital = self.total_capital * weight
                allocation.available_capital = allocation.allocated_capital - allocation.used_capital
                allocation.performance_score = scores[name]

    def _allocate_fixed(self):
        """Fixed allocation based on initial weights."""
        # Normalize weights
        total_weight = sum(a.weight for a in self.strategy_allocations.values())

        for allocation in self.strategy_allocations.values():
            normalized_weight = allocation.weight / total_weight if total_weight > 0 else 0
            allocation.allocated_capital = self.total_capital * normalized_weight
            allocation.available_capital = allocation.allocated_capital - allocation.used_capital

    async def process_signals(
        self,
        timestamp: datetime,
        signals: List[Any]
    ) -> List[Dict]:
        """
        Process signals from all strategies.

        Args:
            timestamp: Current time
            signals: List of signals from strategies

        Returns:
            List of position requests to execute
        """
        self.current_time = timestamp

        # Group signals by market
        market_signals = defaultdict(list)
        for signal in signals:
            market_signals[signal.market_id].append(signal)

        # Resolve conflicts and net positions
        position_requests = []

        for market_id, market_signal_list in market_signals.items():
            if len(market_signal_list) == 1:
                # Single signal, no conflict
                request = self._create_position_request(market_signal_list[0])
                if request:
                    position_requests.append(request)

            else:
                # Multiple signals, need resolution
                resolved = self._resolve_signal_conflicts(market_signal_list)
                if resolved:
                    request = self._create_position_request(resolved)
                    if request:
                        position_requests.append(request)

        # Apply position netting if enabled
        if self.config['position_management']['enable_netting']:
            position_requests = self._net_positions(position_requests)

        # Check risk limits
        position_requests = self._apply_risk_limits(position_requests)

        # Queue for execution
        for request in position_requests:
            await self.execution_queue.put(request)

        return position_requests

    def _resolve_signal_conflicts(
        self,
        signals: List[Any]
    ) -> Optional[Any]:
        """Resolve conflicting signals for the same market."""
        method = self.config['conflict_resolution']['method']

        if method == 'weighted_average':
            # Weighted average of signals
            total_weight = sum(s.confidence for s in signals)
            if total_weight == 0:
                return None

            # Check agreement
            buy_weight = sum(s.confidence for s in signals if s.signal_type.value == 'buy')
            sell_weight = sum(s.confidence for s in signals if s.signal_type.value == 'sell')

            agreement = max(buy_weight, sell_weight) / total_weight
            min_agreement = self.config['conflict_resolution']['min_agreement_threshold']

            if agreement < min_agreement:
                return None  # Not enough agreement

            # Create composite signal
            dominant_side = 'buy' if buy_weight > sell_weight else 'sell'
            avg_confidence = max(buy_weight, sell_weight)

            # Return the highest confidence signal of the dominant side
            return max(
                (s for s in signals if s.signal_type.value == dominant_side),
                key=lambda s: s.confidence
            )

        elif method == 'highest_confidence':
            # Use highest confidence signal
            return max(signals, key=lambda s: s.confidence)

        else:
            # First signal wins
            return signals[0]

    def _create_position_request(
        self,
        signal: Any
    ) -> Optional[PositionRequest]:
        """Create position request from signal."""
        strategy_name = signal.strategy_name

        # Get strategy allocation
        if strategy_name not in self.strategy_allocations:
            return None

        allocation = self.strategy_allocations[strategy_name]

        # Check available capital
        if allocation.available_capital <= 0:
            logger.warning(f"Strategy {strategy_name} has no available capital")
            return None

        # Calculate position size
        strategy = self.strategies[strategy_name]
        size = strategy.calculate_position_size(
            signal,
            allocation.available_capital,
            self.aggregate_positions
        )

        if size < self.config['position_management']['min_position_size']:
            return None

        return PositionRequest(
            request_id=f"{strategy_name}_{signal.market_id}_{self.current_time.timestamp()}",
            strategy_name=strategy_name,
            timestamp=self.current_time,
            market_id=signal.market_id,
            side=signal.signal_type.value,
            requested_size=size,
            urgency=signal.urgency,
            confidence=signal.confidence,
            metadata=signal.metadata
        )

    def _net_positions(
        self,
        requests: List[PositionRequest]
    ) -> List[PositionRequest]:
        """Net position requests across strategies."""
        # Group by market
        market_requests = defaultdict(list)
        for request in requests:
            market_requests[request.market_id].append(request)

        netted_requests = []

        for market_id, market_request_list in market_requests.items():
            # Calculate net position change
            buy_size = sum(r.requested_size for r in market_request_list if r.side == 'buy')
            sell_size = sum(r.requested_size for r in market_request_list if r.side == 'sell')

            net_size = buy_size - sell_size

            if abs(net_size) >= self.config['position_management']['min_position_size']:
                # Create netted request
                netted = PositionRequest(
                    request_id=f"netted_{market_id}_{self.current_time.timestamp()}",
                    strategy_name='orchestrator',
                    timestamp=self.current_time,
                    market_id=market_id,
                    side='buy' if net_size > 0 else 'sell',
                    requested_size=abs(net_size),
                    urgency=max(r.urgency for r in market_request_list),
                    confidence=np.mean([r.confidence for r in market_request_list]),
                    metadata={
                        'netted_from': [r.request_id for r in market_request_list],
                        'strategies': list(set(r.strategy_name for r in market_request_list))
                    }
                )
                netted_requests.append(netted)

        return netted_requests

    def _apply_risk_limits(
        self,
        requests: List[PositionRequest]
    ) -> List[PositionRequest]:
        """Apply risk limits to position requests."""
        risk_limits = self.config['risk_limits']
        approved_requests = []

        # Calculate current exposure
        current_exposure = sum(abs(p) for p in self.aggregate_positions.values())

        for request in requests:
            # Check total exposure limit
            new_exposure = current_exposure + request.requested_size
            if new_exposure > self.total_capital * risk_limits['max_total_exposure']:
                logger.warning(f"Request {request.request_id} exceeds total exposure limit")
                continue

            # Check market exposure limit
            market_exposure = abs(self.aggregate_positions.get(request.market_id, 0))
            new_market_exposure = market_exposure + request.requested_size

            if new_market_exposure > self.total_capital * risk_limits['max_market_exposure']:
                logger.warning(f"Request {request.request_id} exceeds market exposure limit")
                continue

            # Check position count
            if len(self.aggregate_positions) >= self.config['position_management']['max_positions']:
                if request.market_id not in self.aggregate_positions:
                    logger.warning("Maximum position count reached")
                    continue

            approved_requests.append(request)

        return approved_requests

    def on_position_update(
        self,
        market_id: str,
        position: float,
        attribution: Dict[str, float]
    ):
        """
        Update position tracking.

        Args:
            market_id: Market identifier
            position: New position size
            attribution: Position attribution by strategy
        """
        self.aggregate_positions[market_id] = position
        self.position_attribution[market_id] = attribution

        # Update strategy used capital
        for strategy_name, strategy_position in attribution.items():
            if strategy_name in self.strategy_allocations:
                allocation = self.strategy_allocations[strategy_name]
                allocation.used_capital += abs(strategy_position)
                allocation.available_capital = allocation.allocated_capital - allocation.used_capital

    def should_rebalance(self) -> bool:
        """Check if rebalancing is needed."""
        if not self.last_rebalance:
            return True

        # Check frequency
        freq = self.config['allocation']['rebalance_frequency']
        if freq == 'daily':
            time_to_rebalance = (self.current_time - self.last_rebalance) >= timedelta(days=1)
        elif freq == 'weekly':
            time_to_rebalance = (self.current_time - self.last_rebalance) >= timedelta(days=7)
        elif freq == 'monthly':
            time_to_rebalance = (self.current_time - self.last_rebalance) >= timedelta(days=30)
        else:
            time_to_rebalance = False

        if not time_to_rebalance:
            return False

        # Check drift threshold
        threshold = self.config['allocation']['min_rebalance_threshold']

        for name, allocation in self.strategy_allocations.items():
            current_weight = allocation.allocated_capital / self.total_capital
            target_weight = allocation.weight

            drift = abs(current_weight - target_weight)
            if drift > threshold:
                return True

        return False

    async def rebalance(self):
        """Rebalance strategy allocations."""
        logger.info(f"Rebalancing at {self.current_time}")

        # Store current allocations
        old_allocations = {
            name: alloc.allocated_capital
            for name, alloc in self.strategy_allocations.items()
        }

        # Calculate new allocations
        self._allocate_capital()

        # Track rebalance
        self.rebalance_history.append({
            'timestamp': self.current_time,
            'old_allocations': old_allocations,
            'new_allocations': {
                name: alloc.allocated_capital
                for name, alloc in self.strategy_allocations.items()
            }
        })

        self.last_rebalance = self.current_time

        # Notify strategies of new allocations
        for name, strategy in self.strategies.items():
            new_capital = self.strategy_allocations[name].allocated_capital
            # Strategy should handle capital change
            # strategy.on_capital_update(new_capital)

    def _get_strategy_volatility(self, strategy_name: str) -> float:
        """Get strategy historical volatility."""
        returns = self._get_strategy_returns(strategy_name)

        if len(returns) > 1:
            return np.std(returns) * np.sqrt(252)  # Annualized
        return 0.1  # Default 10% volatility

    def _get_strategy_returns(self, strategy_name: str) -> np.ndarray:
        """Get strategy historical returns."""
        if strategy_name not in self.strategy_performance:
            return np.array([])

        perf = self.strategy_performance[strategy_name]
        if 'returns' in perf:
            return np.array(perf['returns'])

        return np.array([])

    def _calculate_strategy_score(self, strategy_name: str) -> float:
        """Calculate strategy performance score."""
        returns = self._get_strategy_returns(strategy_name)

        if len(returns) < 5:
            return 0.5  # Neutral score for new strategies

        # Calculate metrics
        mean_return = np.mean(returns)
        volatility = np.std(returns) if len(returns) > 1 else 0.01
        sharpe = mean_return / volatility if volatility > 0 else 0

        # Win rate
        win_rate = len([r for r in returns if r > 0]) / len(returns)

        # Combine into score
        score = (
            sharpe * 0.5 +  # Sharpe ratio weight
            win_rate * 0.3 +  # Win rate weight
            mean_return * 100 * 0.2  # Return weight
        )

        return max(0, min(1, score))  # Normalize to [0, 1]

    def update_performance(
        self,
        strategy_name: str,
        timestamp: datetime,
        pnl: float,
        positions: Dict[str, float]
    ):
        """Update strategy performance tracking."""
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {
                'returns': [],
                'pnl_history': [],
                'position_history': []
            }

        perf = self.strategy_performance[strategy_name]

        # Calculate return
        allocation = self.strategy_allocations[strategy_name]
        if allocation.allocated_capital > 0:
            daily_return = pnl / allocation.allocated_capital
            perf['returns'].append(daily_return)

        perf['pnl_history'].append((timestamp, pnl))
        perf['position_history'].append((timestamp, positions.copy()))

        # Keep only recent history
        lookback = self.config['performance']['lookback_days']
        cutoff = timestamp - timedelta(days=lookback)

        perf['pnl_history'] = [
            (t, p) for t, p in perf['pnl_history']
            if t > cutoff
        ]

        if len(perf['returns']) > lookback:
            perf['returns'] = perf['returns'][-lookback:]

    def get_aggregate_metrics(self) -> Dict:
        """Get aggregated performance metrics."""
        total_pnl = sum(
            perf.get('pnl_history', [(None, 0)])[-1][1]
            for perf in self.strategy_performance.values()
        )

        # Aggregate returns
        all_returns = []
        for perf in self.strategy_performance.values():
            all_returns.extend(perf.get('returns', []))

        if all_returns:
            avg_return = np.mean(all_returns)
            volatility = np.std(all_returns)
            sharpe = avg_return / volatility * np.sqrt(252) if volatility > 0 else 0
        else:
            avg_return = volatility = sharpe = 0

        return {
            'total_capital': self.total_capital,
            'allocated_capital': self.allocated_capital,
            'available_capital': self.available_capital,
            'total_pnl': total_pnl,
            'total_return': total_pnl / self.total_capital if self.total_capital > 0 else 0,
            'average_return': avg_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'num_positions': len(self.aggregate_positions),
            'total_exposure': sum(abs(p) for p in self.aggregate_positions.values()),
            'strategies_active': len([s for s in self.strategies if s in self.strategy_performance]),
            'last_rebalance': self.last_rebalance,
            'rebalance_count': len(self.rebalance_history)
        }

    def get_attribution(self) -> Dict:
        """Get performance attribution by strategy."""
        attribution = {}

        for name, perf in self.strategy_performance.items():
            if perf.get('pnl_history'):
                latest_pnl = perf['pnl_history'][-1][1]
            else:
                latest_pnl = 0

            allocation = self.strategy_allocations[name]

            attribution[name] = {
                'pnl': latest_pnl,
                'return': latest_pnl / allocation.allocated_capital if allocation.allocated_capital > 0 else 0,
                'weight': allocation.weight,
                'allocated_capital': allocation.allocated_capital,
                'used_capital': allocation.used_capital,
                'contribution': latest_pnl / self.total_capital if self.total_capital > 0 else 0
            }

        return attribution