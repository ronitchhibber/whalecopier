"""
Execution Simulator with Realistic Fills and Slippage
Simulates real-world trading execution challenges
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import random
from decimal import Decimal

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Order execution statuses."""
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RejectionReason(Enum):
    """Reasons for order rejection."""
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MARKET_CLOSED = "market_closed"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    SIZE_TOO_LARGE = "size_too_large"
    SIZE_TOO_SMALL = "size_too_small"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    DUPLICATE_ORDER = "duplicate_order"
    TECHNICAL_ERROR = "technical_error"


@dataclass
class ExecutionResult:
    """Result of order execution attempt."""
    status: ExecutionStatus
    order_id: str
    timestamp: datetime
    fills: List[Dict] = field(default_factory=list)
    average_price: Optional[float] = None
    total_filled: float = 0
    remaining: float = 0
    slippage_bps: Optional[float] = None
    market_impact_bps: Optional[float] = None
    fees: float = 0
    rejection_reason: Optional[RejectionReason] = None
    latency_ms: float = 0
    queue_position: Optional[int] = None


class ExecutionSimulator:
    """
    Realistic order execution simulator.

    Features:
    - Partial fill modeling based on order book depth
    - Queue position simulation for limit orders
    - Latency injection (network, processing, exchange)
    - Slippage modeling (market impact + adverse selection)
    - Fee calculation (maker/taker, tiered)
    - Order rejection scenarios
    - Fill probability models
    """

    def __init__(self, config: Dict = None):
        """Initialize execution simulator."""
        self.config = config or self._default_config()

        # Execution state
        self.pending_orders: Dict[str, Dict] = {}
        self.order_history: List[ExecutionResult] = []
        self.fill_history: List[Dict] = []

        # Performance metrics
        self.metrics = {
            'total_orders': 0,
            'filled_orders': 0,
            'partial_fills': 0,
            'rejected_orders': 0,
            'cancelled_orders': 0,
            'total_slippage_bps': 0,
            'total_fees': 0,
            'average_latency_ms': 0
        }

        # Market conditions
        self.market_volatility = 0.001  # 10 bps baseline
        self.liquidity_factor = 1.0  # 1.0 = normal, <1 = low liquidity

    def _default_config(self) -> Dict:
        """Default execution configuration."""
        return {
            # Latency parameters (milliseconds)
            'latency': {
                'network_mean': 20,
                'network_std': 10,
                'processing_mean': 5,
                'processing_std': 2,
                'exchange_mean': 10,
                'exchange_std': 5,
                'max_latency': 500
            },

            # Slippage model
            'slippage': {
                'base_impact_bps': 5,  # Base market impact
                'size_factor': 0.5,  # Square root impact model
                'volatility_multiplier': 2.0,
                'adverse_selection_bps': 2  # Info asymmetry cost
            },

            # Fill probability
            'fill_probability': {
                'market_order': 0.99,  # Almost always fills
                'aggressive_limit': 0.85,  # At or crossing spread
                'passive_limit': 0.60,  # Behind spread
                'far_limit': 0.20,  # Far from market
                'partial_fill_prob': 0.30  # Chance of partial vs full
            },

            # Fees (bps)
            'fees': {
                'maker_fee_bps': 2,  # 0.02%
                'taker_fee_bps': 5,  # 0.05%
                'tier_discounts': {
                    1000000: 0.9,  # $1M volume = 10% discount
                    5000000: 0.8,  # $5M = 20% discount
                    10000000: 0.7  # $10M = 30% discount
                }
            },

            # Risk checks
            'risk': {
                'max_order_size': 100000,  # $100k max single order
                'min_order_size': 10,  # $10 minimum
                'max_position_size': 500000,  # $500k max position
                'daily_loss_limit': 50000,  # $50k daily loss limit
                'order_rate_limit': 100  # Max 100 orders per minute
            },

            # Queue modeling
            'queue': {
                'base_queue_size': 10,  # Average queue depth
                'queue_volatility': 5,  # Queue size variation
                'priority_boost_aggressive': 0.5,  # Queue boost for aggressive orders
                'cancellation_rate': 0.1  # Rate of orders ahead cancelling
            }
        }

    def execute_order(
        self,
        order: Dict,
        market_state: Dict,
        portfolio_state: Dict = None
    ) -> ExecutionResult:
        """
        Simulate order execution with realistic conditions.

        Args:
            order: Order details (type, side, size, price, etc.)
            market_state: Current market conditions
            portfolio_state: Current portfolio for risk checks

        Returns:
            ExecutionResult with fill details
        """
        self.metrics['total_orders'] += 1

        # Generate order ID
        order_id = f"order_{self.metrics['total_orders']}_{order.get('market_id', 'unknown')}"

        # Simulate latency
        latency_ms = self._simulate_latency()

        # Risk checks
        rejection_reason = self._check_risk_limits(order, portfolio_state)
        if rejection_reason:
            self.metrics['rejected_orders'] += 1
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                order_id=order_id,
                timestamp=datetime.utcnow(),
                rejection_reason=rejection_reason,
                latency_ms=latency_ms
            )

        # Determine fill probability
        fill_probability = self._calculate_fill_probability(order, market_state)

        # Simulate execution
        if random.random() < fill_probability:
            # Order will fill (fully or partially)
            return self._simulate_fill(order, market_state, order_id, latency_ms)
        else:
            # Order doesn't fill immediately
            if order.get('type') == 'market':
                # Market orders that don't fill are rejected
                return ExecutionResult(
                    status=ExecutionStatus.REJECTED,
                    order_id=order_id,
                    timestamp=datetime.utcnow(),
                    rejection_reason=RejectionReason.INSUFFICIENT_BALANCE,
                    latency_ms=latency_ms
                )
            else:
                # Limit orders go to queue
                return self._simulate_queue_placement(order, market_state, order_id, latency_ms)

    def _simulate_latency(self) -> float:
        """Simulate realistic network and processing latency."""
        config = self.config['latency']

        # Network latency
        network_latency = np.random.normal(
            config['network_mean'],
            config['network_std']
        )
        network_latency = max(0, network_latency)

        # Processing latency
        processing_latency = np.random.normal(
            config['processing_mean'],
            config['processing_std']
        )
        processing_latency = max(0, processing_latency)

        # Exchange latency
        exchange_latency = np.random.normal(
            config['exchange_mean'],
            config['exchange_std']
        )
        exchange_latency = max(0, exchange_latency)

        # Total latency with cap
        total_latency = network_latency + processing_latency + exchange_latency
        total_latency = min(total_latency, config['max_latency'])

        # Update metrics
        if self.metrics['average_latency_ms'] == 0:
            self.metrics['average_latency_ms'] = total_latency
        else:
            # Exponential moving average
            self.metrics['average_latency_ms'] = (
                0.9 * self.metrics['average_latency_ms'] + 0.1 * total_latency
            )

        return total_latency

    def _check_risk_limits(
        self,
        order: Dict,
        portfolio_state: Dict = None
    ) -> Optional[RejectionReason]:
        """Check if order passes risk limits."""
        risk_config = self.config['risk']

        # Check order size limits
        order_size = order.get('size', 0) * order.get('price', 0)

        if order_size > risk_config['max_order_size']:
            return RejectionReason.SIZE_TOO_LARGE

        if order_size < risk_config['min_order_size']:
            return RejectionReason.SIZE_TOO_SMALL

        # Check portfolio limits if provided
        if portfolio_state:
            # Check position limits
            current_position = portfolio_state.get('positions', {}).get(
                order.get('market_id'), 0
            )

            new_position = current_position + order_size if order['side'] == 'buy' else current_position - order_size

            if abs(new_position) > risk_config['max_position_size']:
                return RejectionReason.RISK_LIMIT_EXCEEDED

            # Check daily loss limit
            daily_pnl = portfolio_state.get('daily_pnl', 0)
            if daily_pnl < -risk_config['daily_loss_limit']:
                return RejectionReason.RISK_LIMIT_EXCEEDED

            # Check available balance
            available_balance = portfolio_state.get('available_balance', 0)
            if order['side'] == 'buy' and order_size > available_balance:
                return RejectionReason.INSUFFICIENT_BALANCE

        return None

    def _calculate_fill_probability(
        self,
        order: Dict,
        market_state: Dict
    ) -> float:
        """Calculate probability of order filling."""
        prob_config = self.config['fill_probability']

        # Get market prices
        best_bid = market_state.get('best_bid', 0)
        best_ask = market_state.get('best_ask', 0)
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.5

        # Market orders
        if order.get('type') == 'market':
            # Adjust for liquidity
            return prob_config['market_order'] * self.liquidity_factor

        # Limit orders
        order_price = order.get('price', 0)

        if order['side'] == 'buy':
            if order_price >= best_ask:
                # Aggressive order (at or above ask)
                return prob_config['aggressive_limit'] * self.liquidity_factor
            elif order_price >= best_bid:
                # At or inside spread
                return prob_config['passive_limit'] * self.liquidity_factor
            else:
                # Behind spread
                price_distance = (best_bid - order_price) / mid_price
                if price_distance < 0.01:  # Within 1%
                    return prob_config['passive_limit'] * 0.5 * self.liquidity_factor
                else:
                    return prob_config['far_limit'] * self.liquidity_factor
        else:  # Sell order
            if order_price <= best_bid:
                # Aggressive order
                return prob_config['aggressive_limit'] * self.liquidity_factor
            elif order_price <= best_ask:
                # At or inside spread
                return prob_config['passive_limit'] * self.liquidity_factor
            else:
                # Behind spread
                price_distance = (order_price - best_ask) / mid_price
                if price_distance < 0.01:
                    return prob_config['passive_limit'] * 0.5 * self.liquidity_factor
                else:
                    return prob_config['far_limit'] * self.liquidity_factor

    def _simulate_fill(
        self,
        order: Dict,
        market_state: Dict,
        order_id: str,
        latency_ms: float
    ) -> ExecutionResult:
        """Simulate order fill with slippage and fees."""
        # Determine if partial or full fill
        partial_fill = random.random() < self.config['fill_probability']['partial_fill_prob']

        if partial_fill:
            # Partial fill between 20% and 80%
            fill_ratio = random.uniform(0.2, 0.8)
            filled_size = order['size'] * fill_ratio
            remaining = order['size'] - filled_size
            status = ExecutionStatus.PARTIAL
            self.metrics['partial_fills'] += 1
        else:
            # Full fill
            filled_size = order['size']
            remaining = 0
            status = ExecutionStatus.FILLED
            self.metrics['filled_orders'] += 1

        # Calculate execution price with slippage
        execution_price, slippage_bps, impact_bps = self._calculate_execution_price(
            order, market_state, filled_size
        )

        # Calculate fees
        fees = self._calculate_fees(order, filled_size * execution_price)

        # Create fill record
        fill = {
            'timestamp': datetime.utcnow(),
            'price': execution_price,
            'size': filled_size,
            'side': order['side'],
            'fee': fees,
            'slippage_bps': slippage_bps,
            'market_impact_bps': impact_bps
        }

        # Update metrics
        self.metrics['total_slippage_bps'] += slippage_bps * filled_size
        self.metrics['total_fees'] += fees

        return ExecutionResult(
            status=status,
            order_id=order_id,
            timestamp=datetime.utcnow(),
            fills=[fill],
            average_price=execution_price,
            total_filled=filled_size,
            remaining=remaining,
            slippage_bps=slippage_bps,
            market_impact_bps=impact_bps,
            fees=fees,
            latency_ms=latency_ms
        )

    def _calculate_execution_price(
        self,
        order: Dict,
        market_state: Dict,
        size: float
    ) -> Tuple[float, float, float]:
        """
        Calculate execution price with slippage.

        Returns:
            (execution_price, slippage_bps, market_impact_bps)
        """
        slippage_config = self.config['slippage']

        # Get reference price
        if order.get('type') == 'market':
            if order['side'] == 'buy':
                reference_price = market_state.get('best_ask', 0.5)
            else:
                reference_price = market_state.get('best_bid', 0.5)
        else:
            reference_price = order.get('price', 0.5)

        # Calculate market impact (square root model)
        size_factor = np.sqrt(size / 10000)  # Normalize by typical order size
        base_impact = slippage_config['base_impact_bps'] / 10000

        # Adjust for volatility
        vol_adjustment = 1 + self.market_volatility * slippage_config['volatility_multiplier']

        # Calculate total impact
        market_impact = base_impact * size_factor * vol_adjustment
        market_impact_bps = market_impact * 10000

        # Add adverse selection cost (information asymmetry)
        adverse_selection = slippage_config['adverse_selection_bps'] / 10000

        # Calculate execution price
        if order['side'] == 'buy':
            # Pay more when buying
            execution_price = reference_price * (1 + market_impact + adverse_selection)
        else:
            # Receive less when selling
            execution_price = reference_price * (1 - market_impact - adverse_selection)

        # Calculate total slippage
        slippage = abs(execution_price - reference_price) / reference_price
        slippage_bps = slippage * 10000

        return execution_price, slippage_bps, market_impact_bps

    def _calculate_fees(self, order: Dict, notional: float) -> float:
        """Calculate trading fees with tier discounts."""
        fee_config = self.config['fees']

        # Determine if maker or taker
        is_maker = order.get('type') == 'limit' and order.get('post_only', False)

        if is_maker:
            base_fee_bps = fee_config['maker_fee_bps']
        else:
            base_fee_bps = fee_config['taker_fee_bps']

        # Apply tier discounts based on volume
        # (In real implementation, would track cumulative volume)
        discount = 1.0
        for volume_threshold, discount_factor in fee_config['tier_discounts'].items():
            if notional > volume_threshold:
                discount = discount_factor
                break

        # Calculate fee
        fee_rate = (base_fee_bps / 10000) * discount
        fees = notional * fee_rate

        return fees

    def _simulate_queue_placement(
        self,
        order: Dict,
        market_state: Dict,
        order_id: str,
        latency_ms: float
    ) -> ExecutionResult:
        """Simulate limit order queue placement."""
        queue_config = self.config['queue']

        # Calculate queue position
        base_queue = queue_config['base_queue_size']
        queue_variation = np.random.normal(0, queue_config['queue_volatility'])
        queue_size = max(1, int(base_queue + queue_variation))

        # Adjust position for order aggressiveness
        best_bid = market_state.get('best_bid', 0)
        best_ask = market_state.get('best_ask', 0)

        if order['side'] == 'buy':
            if order['price'] > best_bid:
                # More aggressive = better queue position
                queue_boost = queue_config['priority_boost_aggressive']
                queue_position = max(1, int(queue_size * (1 - queue_boost)))
            else:
                queue_position = random.randint(queue_size // 2, queue_size)
        else:
            if order['price'] < best_ask:
                queue_boost = queue_config['priority_boost_aggressive']
                queue_position = max(1, int(queue_size * (1 - queue_boost)))
            else:
                queue_position = random.randint(queue_size // 2, queue_size)

        # Store pending order
        self.pending_orders[order_id] = {
            'order': order,
            'queue_position': queue_position,
            'timestamp': datetime.utcnow()
        }

        return ExecutionResult(
            status=ExecutionStatus.PENDING,
            order_id=order_id,
            timestamp=datetime.utcnow(),
            remaining=order['size'],
            latency_ms=latency_ms,
            queue_position=queue_position
        )

    def update_pending_orders(
        self,
        market_state: Dict,
        time_elapsed: timedelta
    ) -> List[ExecutionResult]:
        """
        Update pending orders based on queue movement.

        Returns:
            List of newly filled orders
        """
        filled_orders = []
        queue_config = self.config['queue']

        for order_id, pending in list(self.pending_orders.items()):
            # Simulate queue advancement
            cancellations_ahead = np.random.poisson(
                queue_config['cancellation_rate'] * pending['queue_position']
            )

            pending['queue_position'] = max(0, pending['queue_position'] - cancellations_ahead)

            # Check if order reaches front of queue
            if pending['queue_position'] == 0:
                # Order can now fill
                result = self._simulate_fill(
                    pending['order'],
                    market_state,
                    order_id,
                    0  # No additional latency
                )
                filled_orders.append(result)
                del self.pending_orders[order_id]

            # Check for order timeout
            elif (datetime.utcnow() - pending['timestamp']) > timedelta(minutes=5):
                # Cancel old orders
                result = ExecutionResult(
                    status=ExecutionStatus.EXPIRED,
                    order_id=order_id,
                    timestamp=datetime.utcnow(),
                    remaining=pending['order']['size']
                )
                filled_orders.append(result)
                del self.pending_orders[order_id]
                self.metrics['cancelled_orders'] += 1

        return filled_orders

    def set_market_conditions(
        self,
        volatility: float = None,
        liquidity_factor: float = None
    ):
        """Update market conditions for simulation."""
        if volatility is not None:
            self.market_volatility = volatility

        if liquidity_factor is not None:
            self.liquidity_factor = liquidity_factor

    def get_execution_statistics(self) -> Dict:
        """Get execution simulator statistics."""
        total = self.metrics['total_orders']
        if total == 0:
            return self.metrics

        stats = self.metrics.copy()
        stats['fill_rate'] = self.metrics['filled_orders'] / total
        stats['partial_fill_rate'] = self.metrics['partial_fills'] / total
        stats['rejection_rate'] = self.metrics['rejected_orders'] / total
        stats['cancellation_rate'] = self.metrics['cancelled_orders'] / total

        if self.metrics['filled_orders'] > 0:
            stats['avg_slippage_bps'] = (
                self.metrics['total_slippage_bps'] / self.metrics['filled_orders']
            )
            stats['avg_fee'] = self.metrics['total_fees'] / self.metrics['filled_orders']

        return stats

    def reset_metrics(self):
        """Reset execution metrics."""
        self.metrics = {
            'total_orders': 0,
            'filled_orders': 0,
            'partial_fills': 0,
            'rejected_orders': 0,
            'cancelled_orders': 0,
            'total_slippage_bps': 0,
            'total_fees': 0,
            'average_latency_ms': 0
        }
        self.order_history.clear()
        self.fill_history.clear()


class PolymarketExecutionSimulator(ExecutionSimulator):
    """
    Polymarket-specific execution simulator.

    Adds Polymarket-specific features:
    - Binary market constraints (YES/NO shares)
    - CLOB vs AMM execution paths
    - Resolution and settlement modeling
    - Gas fee estimation
    """

    def __init__(self, config: Dict = None):
        """Initialize Polymarket execution simulator."""
        super().__init__(config)

        # Polymarket-specific config
        self.polymarket_config = {
            'use_clob': True,  # Use CLOB by default
            'min_order_size_usd': 10,
            'max_order_size_usd': 100000,
            'gas_price_gwei': 30,
            'gas_limit': 200000,
            'settlement_delay_hours': 2,  # UMA oracle delay
            'binary_constraint': True  # YES + NO = $1
        }

    def execute_polymarket_order(
        self,
        order: Dict,
        market_state: Dict,
        portfolio_state: Dict = None
    ) -> ExecutionResult:
        """
        Execute order with Polymarket-specific logic.

        Args:
            order: Must include 'outcome' (YES/NO) and 'market_id'
            market_state: Polymarket market data
            portfolio_state: Current positions

        Returns:
            ExecutionResult with Polymarket details
        """
        # Validate Polymarket order
        if 'outcome' not in order or order['outcome'] not in ['YES', 'NO']:
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                order_id=f"poly_{self.metrics['total_orders']}",
                timestamp=datetime.utcnow(),
                rejection_reason=RejectionReason.PRICE_OUT_OF_RANGE
            )

        # Check binary constraint
        if self.polymarket_config['binary_constraint']:
            yes_price = market_state.get('yes_price', 0.5)
            no_price = market_state.get('no_price', 0.5)

            if abs((yes_price + no_price) - 1.0) > 0.01:
                # Market is dislocated, potential arbitrage
                logger.info(f"Binary constraint violation: YES={yes_price}, NO={no_price}")

        # Add gas costs to fees
        order['gas_estimate'] = self._estimate_gas_cost()

        # Route to CLOB or AMM
        if self.polymarket_config['use_clob']:
            result = super().execute_order(order, market_state, portfolio_state)
        else:
            result = self._execute_amm_order(order, market_state)

        # Add gas to fees
        result.fees += order['gas_estimate']

        return result

    def _execute_amm_order(
        self,
        order: Dict,
        market_state: Dict
    ) -> ExecutionResult:
        """Execute order through AMM with price impact."""
        # AMM always fills but with price impact
        pool_liquidity = market_state.get('liquidity', 100000)

        # Calculate price impact using constant product formula
        order_size = order['size'] * order.get('price', 0.5)
        price_impact = order_size / (pool_liquidity + order_size)

        if order['side'] == 'buy':
            execution_price = order.get('price', 0.5) * (1 + price_impact)
        else:
            execution_price = order.get('price', 0.5) * (1 - price_impact)

        slippage_bps = abs(execution_price - order.get('price', 0.5)) / order.get('price', 0.5) * 10000

        return ExecutionResult(
            status=ExecutionStatus.FILLED,
            order_id=f"amm_{self.metrics['total_orders']}",
            timestamp=datetime.utcnow(),
            fills=[{
                'price': execution_price,
                'size': order['size'],
                'timestamp': datetime.utcnow()
            }],
            average_price=execution_price,
            total_filled=order['size'],
            remaining=0,
            slippage_bps=slippage_bps,
            fees=order_size * 0.002  # 0.2% AMM fee
        )

    def _estimate_gas_cost(self) -> float:
        """Estimate gas cost in USD."""
        gas_price = self.polymarket_config['gas_price_gwei']
        gas_limit = self.polymarket_config['gas_limit']

        # Convert to ETH (1 gwei = 1e-9 ETH)
        gas_cost_eth = (gas_price * gas_limit) / 1e9

        # Convert to USD (assume $2000 ETH)
        eth_price = 2000
        gas_cost_usd = gas_cost_eth * eth_price

        return gas_cost_usd