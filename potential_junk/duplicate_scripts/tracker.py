"""
Whale Position Tracker - Tracks changes in whale portfolios to detect new trades.
Since the CLOB API requires auth and subgraph is deprecated, we track position changes.
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class WhalePositionTracker:
    """
    Tracks whale positions by monitoring portfolio changes.
    When positions change, we can infer trades were made.
    """

    def __init__(self):
        self.last_positions = {}  # Cache of last known positions per whale

    def get_whale_positions(self, address: str) -> Optional[Dict]:
        """Fetch current positions from Gamma API."""
        try:
            url = f"https://gamma-api.polymarket.com/profile/{address}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch positions for {address[:10]}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching positions for {address[:10]}: {e}")
            return None

    def detect_position_changes(self, whale_address: str, current_profile: Dict) -> List[Dict]:
        """
        Detect new or changed positions since last check.
        Returns list of detected changes that could be new trades.
        """
        changes = []

        # Get previous positions
        prev_positions = self.last_positions.get(whale_address, {})

        # Current position indicators
        current_pnl = current_profile.get('pnl', 0)
        current_volume = current_profile.get('totalVolume', 0)
        current_trades = current_profile.get('totalTrades', 0)
        current_markets = current_profile.get('marketsTraded', 0)

        # Previous indicators
        prev_pnl = prev_positions.get('pnl', 0)
        prev_volume = prev_positions.get('volume', 0)
        prev_trades = prev_positions.get('trades', 0)
        prev_markets = prev_positions.get('markets', 0)

        # Detect changes
        if current_trades > prev_trades:
            new_trades = current_trades - prev_trades
            volume_change = current_volume - prev_volume
            pnl_change = current_pnl - prev_pnl

            changes.append({
                'address': whale_address,
                'type': 'new_activity',
                'new_trades': new_trades,
                'volume_change': volume_change,
                'pnl_change': pnl_change,
                'markets_change': current_markets - prev_markets,
                'timestamp': datetime.utcnow(),
                'current_pnl': current_pnl,
                'current_volume': current_volume
            })

            logger.info(f"📊 Detected activity for {whale_address[:10]}: "
                       f"+{new_trades} trades, ${volume_change:,.0f} volume")

        # Update cache
        self.last_positions[whale_address] = {
            'pnl': current_pnl,
            'volume': current_volume,
            'trades': current_trades,
            'markets': current_markets,
            'updated_at': datetime.utcnow()
        }

        return changes

    def monitor_whale(self, whale_address: str) -> List[Dict]:
        """
        Monitor a single whale for changes.
        Returns list of detected changes.
        """
        profile = self.get_whale_positions(whale_address)

        if profile and 'totalTrades' in profile:
            return self.detect_position_changes(whale_address, profile)

        return []

    def get_market_details(self, market_id: str) -> Optional[Dict]:
        """Get details about a specific market."""
        try:
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None
