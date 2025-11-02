"""
Behavioral Pattern Detection and Exploitation
Implements strategies to monetize cognitive biases and emotional trading
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class BehavioralPatternDetector:
    """
    Detects and exploits behavioral inefficiencies:
    - Overreaction Fade (127 bps edge, 73% win rate)
    - Systematic 'Yes' Bias (50 bps edge, Sharpe 1.4)
    - Round-Number Anchoring (80 bps edge)
    - Disposition Effect Capitulation
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.pattern_history = []
        self.active_trades = []

    def _default_config(self) -> Dict:
        """Default configuration for behavioral patterns."""
        return {
            'overreaction_fade': {
                'min_price_move_pct': 15,  # 15% move threshold
                'max_price_move_pct': 40,  # Cap at 40% to avoid real news
                'time_window_minutes': 60,  # Within 1 hour
                'volume_imbalance_threshold': 3.0,  # 3:1 buy/sell ratio
                'mean_reversion_window': 240,  # 4 hours for reversion
                'min_edge_bps': 100,
                'target_edge_bps': 127,
                'win_rate_target': 0.73
            },
            'yes_bias': {
                'price_buckets': [
                    {'min': 0.70, 'max': 0.80, 'historical_yes_rate': 0.65},
                    {'min': 0.80, 'max': 0.90, 'historical_yes_rate': 0.75},
                    {'min': 0.60, 'max': 0.70, 'historical_yes_rate': 0.55}
                ],
                'min_edge_bps': 30,
                'target_edge_bps': 50,
                'max_position_pct': 0.02,  # 2% per market
                'portfolio_capacity': 500000,  # $500k total
                'diversification_target': 50  # Minimum 50 markets
            },
            'round_number_anchoring': {
                'anchor_levels': [0.10, 0.25, 0.50, 0.75, 0.90],
                'proximity_threshold': 0.02,  # Within 2 cents
                'volume_spike_threshold': 2.0,  # 2x average volume
                'breakout_confirmation_pct': 2,  # 2% beyond anchor
                'target_edge_bps': 80
            },
            'disposition_capitulation': {
                'panic_volume_threshold': 5.0,  # 5x normal volume
                'price_velocity_threshold': -0.10,  # -10% in 30 min
                'capitulation_duration_min': 15,  # 15 minute window
                'rebound_target_pct': 0.05,  # 5% rebound expected
                'target_edge_bps': 150
            }
        }

    def detect_overreaction(
        self,
        price_history: List[Dict],
        volume_data: Dict,
        news_impact_score: float = 0.0
    ) -> Optional[Dict]:
        """
        Detect price overreaction to news that can be faded.

        Args:
            price_history: List of price points with timestamps
            volume_data: Volume metrics including buy/sell imbalance
            news_impact_score: Score indicating fundamental news importance (0-1)

        Returns:
            Fade opportunity or None
        """
        if len(price_history) < 2:
            return None

        config = self.config['overreaction_fade']

        # Calculate price move over time window
        current_price = price_history[-1]['price']
        window_start_time = datetime.utcnow() - timedelta(minutes=config['time_window_minutes'])

        # Find price at window start
        window_prices = [p for p in price_history
                        if p['timestamp'] >= window_start_time]

        if len(window_prices) < 2:
            return None

        start_price = window_prices[0]['price']
        price_move_pct = ((current_price - start_price) / start_price) * 100

        # Check if move is within overreaction range
        if not (config['min_price_move_pct'] <= abs(price_move_pct) <= config['max_price_move_pct']):
            return None

        # Filter out fundamental news (not overreaction)
        if news_impact_score > 0.7:  # Significant fundamental news
            return None

        # Check volume imbalance confirms emotional trading
        buy_sell_ratio = volume_data.get('buy_volume', 0) / max(volume_data.get('sell_volume', 1), 1)

        is_panic = (price_move_pct < 0 and buy_sell_ratio < 1/config['volume_imbalance_threshold'])
        is_euphoria = (price_move_pct > 0 and buy_sell_ratio > config['volume_imbalance_threshold'])

        if not (is_panic or is_euphoria):
            return None  # No clear emotional imbalance

        # Calculate fade entry and targets
        if price_move_pct > 0:  # Overreaction up, fade down
            action = 'sell'
            entry_price = current_price
            target_price = start_price + (current_price - start_price) * 0.382  # 38.2% retracement
        else:  # Overreaction down, fade up
            action = 'buy'
            entry_price = current_price
            target_price = start_price - (start_price - current_price) * 0.382

        expected_edge_bps = abs(target_price - entry_price) / entry_price * 10000

        if expected_edge_bps < config['min_edge_bps']:
            return None

        return {
            'type': 'overreaction_fade',
            'market_id': price_history[-1].get('market_id'),
            'action': action,
            'trigger': 'panic' if is_panic else 'euphoria',
            'price_move_pct': price_move_pct,
            'volume_imbalance': buy_sell_ratio,
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss': current_price * (1.05 if action == 'sell' else 0.95),
            'expected_edge_bps': expected_edge_bps,
            'confidence': self._calculate_fade_confidence(price_move_pct, buy_sell_ratio),
            'timestamp': datetime.utcnow()
        }

    def _calculate_fade_confidence(self, price_move_pct: float, volume_ratio: float) -> float:
        """Calculate confidence in fade trade based on indicators."""
        # Base confidence from historical 73% win rate
        base_confidence = 0.73

        # Adjust for extreme moves (more extreme = higher confidence)
        move_adjustment = min(abs(price_move_pct) / 30, 1.0) * 0.1

        # Adjust for volume imbalance (more imbalanced = higher confidence)
        imbalance_adjustment = min(abs(np.log(volume_ratio)) / 3, 1.0) * 0.1

        return min(base_confidence + move_adjustment + imbalance_adjustment, 0.95)

    def detect_yes_bias_opportunities(
        self,
        markets: List[Dict]
    ) -> List[Dict]:
        """
        Detect markets where systematic 'Yes' bias creates edge.

        Strategy: Short 'Yes' (or long 'No') in overpriced brackets.

        Args:
            markets: List of market data with prices

        Returns:
            List of 'No' betting opportunities
        """
        config = self.config['yes_bias']
        opportunities = []

        for market in markets:
            yes_price = market.get('yes_price', 0)

            # Find which bucket this price falls into
            for bucket in config['price_buckets']:
                if bucket['min'] <= yes_price <= bucket['max']:
                    # Calculate edge based on historical resolution rate
                    implied_prob = yes_price
                    historical_prob = bucket['historical_yes_rate']
                    edge_bps = (implied_prob - historical_prob) * 10000

                    if edge_bps >= config['min_edge_bps']:
                        opportunities.append({
                            'type': 'yes_bias_fade',
                            'market_id': market.get('market_id'),
                            'action': 'sell_yes',  # or 'buy_no'
                            'yes_price': yes_price,
                            'implied_probability': implied_prob,
                            'historical_probability': historical_prob,
                            'edge_bps': edge_bps,
                            'price_bucket': f"{bucket['min']:.2f}-{bucket['max']:.2f}",
                            'max_position': config['max_position_pct'] * config['portfolio_capacity'],
                            'timestamp': datetime.utcnow()
                        })

        # Limit to maintain diversification
        if len(opportunities) > config['diversification_target']:
            # Sort by edge and take top opportunities
            opportunities.sort(key=lambda x: x['edge_bps'], reverse=True)
            opportunities = opportunities[:config['diversification_target']]

        return opportunities

    def detect_round_number_patterns(
        self,
        market_data: Dict,
        order_book: Dict
    ) -> Optional[Dict]:
        """
        Detect trading opportunities around psychological round numbers.

        Two strategies:
        1. Fade when approaching (resistance/support)
        2. Follow on breakout (momentum)

        Args:
            market_data: Current market prices and volume
            order_book: Order book depth data

        Returns:
            Trading opportunity or None
        """
        config = self.config['round_number_anchoring']
        current_price = market_data.get('last_price')

        if not current_price:
            return None

        # Find nearest anchor level
        anchors = config['anchor_levels']
        distances = [abs(current_price - anchor) for anchor in anchors]
        nearest_idx = np.argmin(distances)
        nearest_anchor = anchors[nearest_idx]
        distance_to_anchor = distances[nearest_idx]

        # Check if price is near an anchor
        if distance_to_anchor > config['proximity_threshold']:
            return None

        # Analyze order book depth at anchor
        anchor_bid_depth = order_book.get(f'depth_at_{nearest_anchor}_bid', 0)
        anchor_ask_depth = order_book.get(f'depth_at_{nearest_anchor}_ask', 0)
        avg_depth = order_book.get('avg_depth', 1)

        depth_ratio = (anchor_bid_depth + anchor_ask_depth) / (2 * avg_depth)

        # Check recent volume
        recent_volume = market_data.get('volume_5min', 0)
        avg_volume = market_data.get('avg_volume_5min', 1)
        volume_spike = recent_volume / avg_volume if avg_volume > 0 else 1

        # Determine strategy
        if current_price < nearest_anchor:  # Approaching from below
            if depth_ratio > 2:  # Strong resistance
                # Fade strategy - expect bounce down
                return {
                    'type': 'round_number_fade',
                    'market_id': market_data.get('market_id'),
                    'action': 'sell',
                    'anchor_level': nearest_anchor,
                    'current_price': current_price,
                    'entry_price': current_price,
                    'target_price': nearest_anchor - config['proximity_threshold'],
                    'stop_loss': nearest_anchor + config['proximity_threshold'],
                    'depth_ratio': depth_ratio,
                    'confidence': min(depth_ratio / 3, 0.8),
                    'timestamp': datetime.utcnow()
                }
            elif volume_spike > config['volume_spike_threshold']:
                # Potential breakout - wait for confirmation
                if current_price > nearest_anchor * (1 + config['breakout_confirmation_pct'] / 100):
                    # Confirmed breakout - follow momentum
                    return {
                        'type': 'round_number_breakout',
                        'market_id': market_data.get('market_id'),
                        'action': 'buy',
                        'anchor_level': nearest_anchor,
                        'current_price': current_price,
                        'entry_price': current_price,
                        'target_price': nearest_anchor * 1.05,  # 5% above anchor
                        'stop_loss': nearest_anchor,
                        'volume_spike': volume_spike,
                        'confidence': min(volume_spike / 5, 0.75),
                        'timestamp': datetime.utcnow()
                    }

        # Similar logic for approaching from above
        elif current_price > nearest_anchor:
            if depth_ratio > 2:  # Strong support
                return {
                    'type': 'round_number_fade',
                    'market_id': market_data.get('market_id'),
                    'action': 'buy',
                    'anchor_level': nearest_anchor,
                    'current_price': current_price,
                    'entry_price': current_price,
                    'target_price': nearest_anchor + config['proximity_threshold'],
                    'stop_loss': nearest_anchor - config['proximity_threshold'],
                    'depth_ratio': depth_ratio,
                    'confidence': min(depth_ratio / 3, 0.8),
                    'timestamp': datetime.utcnow()
                }

        return None

    def detect_disposition_capitulation(
        self,
        price_history: List[Dict],
        volume_history: List[Dict],
        position_data: Dict = None
    ) -> Optional[Dict]:
        """
        Detect mass capitulation events from disposition effect.

        Traders holding losers finally give up, creating a selling climax.

        Args:
            price_history: Recent price history
            volume_history: Recent volume history
            position_data: Optional data on position ages/losses

        Returns:
            Capitulation reversal opportunity
        """
        config = self.config['disposition_capitulation']

        if len(price_history) < 10 or len(volume_history) < 10:
            return None

        # Calculate recent price velocity
        current_price = price_history[-1]['price']
        price_30min_ago = price_history[-6]['price'] if len(price_history) > 6 else price_history[0]['price']
        price_velocity = (current_price - price_30min_ago) / price_30min_ago

        if price_velocity > config['price_velocity_threshold']:
            return None  # Not a selloff

        # Check for volume spike (panic indicator)
        recent_volume = np.mean([v['volume'] for v in volume_history[-3:]])
        normal_volume = np.mean([v['volume'] for v in volume_history[:-3]])
        volume_ratio = recent_volume / normal_volume if normal_volume > 0 else 1

        if volume_ratio < config['panic_volume_threshold']:
            return None  # Not enough panic

        # Look for exhaustion signs
        # Price velocity should be slowing (second derivative)
        if len(price_history) >= 3:
            velocity_current = price_history[-1]['price'] - price_history[-2]['price']
            velocity_previous = price_history[-2]['price'] - price_history[-3]['price']
            deceleration = velocity_current > velocity_previous  # Less negative = slowing

            if not deceleration:
                return None  # Still accelerating down

        # Calculate entry and targets
        entry_price = current_price
        target_price = current_price * (1 + config['rebound_target_pct'])
        stop_loss = current_price * 0.95  # 5% stop

        expected_edge_bps = (target_price - entry_price) / entry_price * 10000

        return {
            'type': 'disposition_capitulation',
            'market_id': price_history[-1].get('market_id'),
            'action': 'buy',
            'trigger': 'capitulation_reversal',
            'price_velocity': price_velocity,
            'volume_spike': volume_ratio,
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss': stop_loss,
            'expected_edge_bps': expected_edge_bps,
            'confidence': self._calculate_capitulation_confidence(price_velocity, volume_ratio),
            'timestamp': datetime.utcnow()
        }

    def _calculate_capitulation_confidence(self, velocity: float, volume_ratio: float) -> float:
        """Calculate confidence in capitulation reversal."""
        # More extreme velocity = higher confidence
        velocity_score = min(abs(velocity) / 0.20, 1.0) * 0.4

        # Higher volume spike = higher confidence
        volume_score = min(volume_ratio / 10, 1.0) * 0.4

        # Base confidence
        base = 0.3

        return min(base + velocity_score + volume_score, 0.85)

    def calculate_portfolio_allocation(
        self,
        opportunities: List[Dict],
        total_capital: float,
        current_positions: List[Dict] = None
    ) -> Dict:
        """
        Allocate capital across behavioral opportunities.

        Uses Kelly Criterion adjusted for behavioral edge stability.

        Args:
            opportunities: List of detected opportunities
            total_capital: Available capital
            current_positions: Existing positions

        Returns:
            Allocation plan
        """
        if not opportunities:
            return {'allocations': []}

        allocations = []
        remaining_capital = total_capital

        # Group by strategy type for diversification
        by_type = {}
        for opp in opportunities:
            opp_type = opp['type']
            if opp_type not in by_type:
                by_type[opp_type] = []
            by_type[opp_type].append(opp)

        # Allocate to each strategy type
        strategy_limits = {
            'overreaction_fade': 0.30,  # 30% max
            'yes_bias_fade': 0.40,  # 40% max (most scalable)
            'round_number_fade': 0.15,
            'round_number_breakout': 0.10,
            'disposition_capitulation': 0.15
        }

        for strategy_type, opps in by_type.items():
            max_allocation = strategy_limits.get(strategy_type, 0.10) * total_capital

            # Sort by edge within strategy
            opps.sort(key=lambda x: x.get('expected_edge_bps', 0), reverse=True)

            for opp in opps:
                # Simple fractional Kelly
                edge = opp.get('expected_edge_bps', 0) / 10000
                confidence = opp.get('confidence', 0.5)
                kelly_fraction = 0.25  # Conservative

                position_size = min(
                    edge * confidence * kelly_fraction * total_capital,
                    max_allocation / len(opps),  # Spread within strategy
                    remaining_capital
                )

                if position_size > 100:  # Minimum $100 position
                    allocations.append({
                        'opportunity': opp,
                        'allocation': position_size,
                        'percentage': position_size / total_capital
                    })
                    remaining_capital -= position_size

        return {
            'allocations': allocations,
            'total_allocated': total_capital - remaining_capital,
            'allocation_count': len(allocations)
        }

    def get_behavioral_summary(self) -> Dict:
        """Get summary of behavioral pattern detection."""
        return {
            'active_trades': len(self.active_trades),
            'patterns_detected_today': len([p for p in self.pattern_history
                                           if p['timestamp'] > datetime.utcnow() - timedelta(days=1)]),
            'config': {
                'overreaction_threshold': self.config['overreaction_fade']['min_price_move_pct'],
                'yes_bias_capacity': self.config['yes_bias']['portfolio_capacity'],
                'round_numbers': self.config['round_number_anchoring']['anchor_levels']
            }
        }