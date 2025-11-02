"""
Structural Arbitrage Detection and Execution
Implements Sum-of-Shares and Post-Resolution arbitrage strategies
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class StructuralArbitrageDetector:
    """
    Detects and executes structural arbitrage opportunities:
    - Sum-of-Shares Mispricing (250 bps edge, Sharpe 1.8)
    - Post-Resolution Discount (300 bps edge, Sharpe 2.5)
    - Latency Feed Arbitrage (80 bps edge)
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.active_opportunities = []
        self.execution_stats = {
            'sum_of_shares': {'count': 0, 'total_profit': 0, 'win_rate': 0},
            'post_resolution': {'count': 0, 'total_profit': 0, 'win_rate': 0},
            'latency_arb': {'count': 0, 'total_profit': 0, 'win_rate': 0}
        }

    def _default_config(self) -> Dict:
        """Default configuration for structural arbitrage."""
        return {
            'sum_of_shares': {
                'min_edge_bps': 100,  # Minimum 1% edge to trade
                'max_edge_bps': 500,  # Cap at 5% to avoid bad data
                'min_liquidity': 1000,  # Minimum $1k liquidity
                'max_position': 50000,  # Max $50k per trade
                'execution_timeout_ms': 3000,  # 3 second timeout
                'target_edge_bps': 250  # Expected 2.5% edge
            },
            'post_resolution': {
                'min_discount_bps': 100,  # Min 1% discount
                'max_position': 40000,  # Max $40k per trade
                'challenge_risk_threshold': 0.02,  # 2% challenge risk
                'execution_timeout_ms': 10000,  # 10 second timeout
                'target_edge_bps': 300  # Expected 3% edge
            },
            'latency_arb': {
                'min_edge_bps': 50,
                'max_latency_ms': 150,  # Must execute within 150ms
                'target_edge_bps': 80
            }
        }

    def detect_sum_of_shares_arbitrage(
        self,
        market_data: Dict
    ) -> Optional[Dict]:
        """
        Detect sum-of-shares mispricing arbitrage.

        Arbitrage exists when:
        - best_ask('YES') + best_ask('NO') < $1.00 (buy both)
        - best_bid('YES') + best_bid('NO') > $1.00 (sell both)

        Args:
            market_data: Dict with 'yes_bid', 'yes_ask', 'no_bid', 'no_ask'

        Returns:
            Arbitrage opportunity dict or None
        """
        config = self.config['sum_of_shares']

        yes_bid = market_data.get('yes_bid', 0)
        yes_ask = market_data.get('yes_ask', 1)
        no_bid = market_data.get('no_bid', 0)
        no_ask = market_data.get('no_ask', 1)

        # Check for buy arbitrage (sum of asks < 1)
        sum_of_asks = yes_ask + no_ask
        if sum_of_asks < 1.0:
            edge_bps = (1.0 - sum_of_asks) * 10000

            if config['min_edge_bps'] <= edge_bps <= config['max_edge_bps']:
                liquidity = min(
                    market_data.get('yes_ask_size', 0),
                    market_data.get('no_ask_size', 0)
                )

                if liquidity >= config['min_liquidity']:
                    return {
                        'type': 'sum_of_shares_buy',
                        'market_id': market_data.get('market_id'),
                        'action': 'buy_basket',
                        'yes_price': yes_ask,
                        'no_price': no_ask,
                        'sum_price': sum_of_asks,
                        'edge_bps': edge_bps,
                        'max_size': min(liquidity, config['max_position']),
                        'expected_profit': edge_bps / 10000 * min(liquidity, config['max_position']),
                        'timestamp': datetime.utcnow()
                    }

        # Check for sell arbitrage (sum of bids > 1)
        sum_of_bids = yes_bid + no_bid
        if sum_of_bids > 1.0:
            edge_bps = (sum_of_bids - 1.0) * 10000

            if config['min_edge_bps'] <= edge_bps <= config['max_edge_bps']:
                liquidity = min(
                    market_data.get('yes_bid_size', 0),
                    market_data.get('no_bid_size', 0)
                )

                if liquidity >= config['min_liquidity']:
                    return {
                        'type': 'sum_of_shares_sell',
                        'market_id': market_data.get('market_id'),
                        'action': 'sell_basket',
                        'yes_price': yes_bid,
                        'no_price': no_bid,
                        'sum_price': sum_of_bids,
                        'edge_bps': edge_bps,
                        'max_size': min(liquidity, config['max_position']),
                        'expected_profit': edge_bps / 10000 * min(liquidity, config['max_position']),
                        'timestamp': datetime.utcnow()
                    }

        return None

    def detect_post_resolution_discount(
        self,
        resolved_markets: List[Dict]
    ) -> List[Dict]:
        """
        Detect post-resolution discount opportunities.

        After resolution, winning tokens should trade at $1.00
        but often trade at discount (e.g., $0.97) during 2-hour challenge window.

        Args:
            resolved_markets: List of recently resolved markets

        Returns:
            List of discount opportunities
        """
        config = self.config['post_resolution']
        opportunities = []

        for market in resolved_markets:
            # Check if in challenge window (within 2 hours of resolution)
            resolution_time = market.get('resolution_time')
            if not resolution_time:
                continue

            if isinstance(resolution_time, str):
                resolution_time = datetime.fromisoformat(resolution_time)

            time_since_resolution = datetime.utcnow() - resolution_time
            if time_since_resolution > timedelta(hours=2):
                continue  # Outside challenge window

            # Get winning side price
            winning_side = market.get('resolved_outcome')
            if winning_side == 'YES':
                winning_price = market.get('yes_price', 1.0)
            elif winning_side == 'NO':
                winning_price = market.get('no_price', 1.0)
            else:
                continue  # Unknown outcome

            # Calculate discount
            discount_bps = (1.0 - winning_price) * 10000

            if discount_bps >= config['min_discount_bps']:
                # Estimate challenge risk based on market characteristics
                challenge_risk = self._estimate_challenge_risk(market)

                if challenge_risk <= config['challenge_risk_threshold']:
                    liquidity = market.get(f'{winning_side.lower()}_liquidity', 0)

                    opportunities.append({
                        'type': 'post_resolution_discount',
                        'market_id': market.get('market_id'),
                        'winning_side': winning_side,
                        'current_price': winning_price,
                        'discount_bps': discount_bps,
                        'challenge_risk': challenge_risk,
                        'time_remaining': timedelta(hours=2) - time_since_resolution,
                        'max_size': min(liquidity, config['max_position']),
                        'expected_profit': discount_bps / 10000 * min(liquidity, config['max_position']),
                        'risk_adjusted_profit': (discount_bps / 10000 * (1 - challenge_risk)) * min(liquidity, config['max_position']),
                        'timestamp': datetime.utcnow()
                    })

        return opportunities

    def _estimate_challenge_risk(self, market: Dict) -> float:
        """
        Estimate the risk of a successful UMA challenge.

        Based on:
        - Market size (larger markets = lower risk)
        - Resolution clarity (unanimous = lower risk)
        - Historical challenge rate (~2% baseline)
        """
        baseline_risk = 0.02  # 2% historical challenge rate

        # Adjust based on market size
        market_size = market.get('total_volume', 0)
        if market_size > 1000000:  # >$1M market
            size_multiplier = 0.5
        elif market_size > 100000:  # >$100k market
            size_multiplier = 0.75
        else:
            size_multiplier = 1.5

        # Adjust based on resolution vote margin
        vote_margin = market.get('resolution_vote_margin', 0.5)
        if vote_margin > 0.9:  # >90% agreement
            clarity_multiplier = 0.5
        elif vote_margin > 0.75:
            clarity_multiplier = 0.75
        else:
            clarity_multiplier = 1.5

        return baseline_risk * size_multiplier * clarity_multiplier

    def detect_latency_arbitrage(
        self,
        fast_feed_data: Dict,
        slow_feed_data: Dict,
        timestamp_fast: datetime,
        timestamp_slow: datetime
    ) -> Optional[Dict]:
        """
        Detect latency-based arbitrage between feeds.

        Args:
            fast_feed_data: Data from WebSocket (real-time)
            slow_feed_data: Data from REST API (lagged)
            timestamp_fast: Timestamp of fast feed
            timestamp_slow: Timestamp of slow feed

        Returns:
            Arbitrage opportunity or None
        """
        config = self.config['latency_arb']

        # Calculate latency
        latency_ms = (timestamp_fast - timestamp_slow).total_seconds() * 1000

        if latency_ms > config['max_latency_ms']:
            return None  # Too slow to capitalize

        # Compare prices
        fast_price = fast_feed_data.get('last_price')
        slow_price = slow_feed_data.get('last_price')

        if not fast_price or not slow_price:
            return None

        price_diff_bps = abs(fast_price - slow_price) / slow_price * 10000

        if price_diff_bps >= config['min_edge_bps']:
            # Determine direction
            if fast_price > slow_price:
                action = 'buy'  # Price rising, buy before slow participants
            else:
                action = 'sell'  # Price falling, sell before slow participants

            return {
                'type': 'latency_arbitrage',
                'market_id': fast_feed_data.get('market_id'),
                'action': action,
                'fast_price': fast_price,
                'slow_price': slow_price,
                'edge_bps': price_diff_bps,
                'latency_ms': latency_ms,
                'timestamp': datetime.utcnow()
            }

        return None

    def execute_atomic_basket(
        self,
        opportunity: Dict,
        execute_fn: callable
    ) -> Dict:
        """
        Execute atomic basket trade for sum-of-shares arbitrage.

        Critical: Both legs must execute simultaneously to avoid legging risk.

        Args:
            opportunity: Arbitrage opportunity dict
            execute_fn: Function to execute orders

        Returns:
            Execution result
        """
        if opportunity['type'] not in ['sum_of_shares_buy', 'sum_of_shares_sell']:
            raise ValueError("Invalid opportunity type for basket execution")

        action = 'buy' if 'buy' in opportunity['action'] else 'sell'

        # Prepare atomic orders
        yes_order = {
            'market_id': opportunity['market_id'],
            'side': action.upper(),
            'outcome': 'YES',
            'price': opportunity['yes_price'],
            'size': opportunity['max_size'],
            'type': 'FOK'  # Fill-or-Kill for atomicity
        }

        no_order = {
            'market_id': opportunity['market_id'],
            'side': action.upper(),
            'outcome': 'NO',
            'price': opportunity['no_price'],
            'size': opportunity['max_size'],
            'type': 'FOK'
        }

        # Execute atomically
        try:
            # This should be a single atomic transaction
            results = execute_fn([yes_order, no_order], atomic=True)

            if results['status'] == 'success':
                realized_profit = self._calculate_realized_profit(results, opportunity)

                # Update stats
                self.execution_stats['sum_of_shares']['count'] += 1
                self.execution_stats['sum_of_shares']['total_profit'] += realized_profit

                return {
                    'status': 'success',
                    'opportunity_type': opportunity['type'],
                    'expected_profit': opportunity['expected_profit'],
                    'realized_profit': realized_profit,
                    'execution_time': datetime.utcnow(),
                    'fills': results.get('fills', [])
                }
            else:
                return {
                    'status': 'failed',
                    'reason': results.get('reason', 'Unknown'),
                    'opportunity_type': opportunity['type']
                }

        except Exception as e:
            logger.error(f"Basket execution failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'opportunity_type': opportunity['type']
            }

    def _calculate_realized_profit(
        self,
        execution_results: Dict,
        opportunity: Dict
    ) -> float:
        """Calculate actual profit from execution."""
        fills = execution_results.get('fills', [])

        if opportunity['type'] == 'sum_of_shares_buy':
            # Profit = 1.0 - (actual_yes_price + actual_no_price)
            yes_fill = next((f for f in fills if f['outcome'] == 'YES'), None)
            no_fill = next((f for f in fills if f['outcome'] == 'NO'), None)

            if yes_fill and no_fill:
                actual_sum = yes_fill['price'] + no_fill['price']
                return (1.0 - actual_sum) * yes_fill['size']

        elif opportunity['type'] == 'sum_of_shares_sell':
            # Profit = (actual_yes_price + actual_no_price) - 1.0
            yes_fill = next((f for f in fills if f['outcome'] == 'YES'), None)
            no_fill = next((f for f in fills if f['outcome'] == 'NO'), None)

            if yes_fill and no_fill:
                actual_sum = yes_fill['price'] + no_fill['price']
                return (actual_sum - 1.0) * yes_fill['size']

        return 0.0

    def get_arbitrage_summary(self) -> Dict:
        """Get summary statistics of arbitrage performance."""
        summary = {}

        for arb_type, stats in self.execution_stats.items():
            if stats['count'] > 0:
                avg_profit = stats['total_profit'] / stats['count']
                summary[arb_type] = {
                    'trades_executed': stats['count'],
                    'total_profit': stats['total_profit'],
                    'average_profit': avg_profit,
                    'win_rate': stats.get('win_rate', 0)
                }

        summary['active_opportunities'] = len(self.active_opportunities)

        return summary