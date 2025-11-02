"""
Fixed Whale Position Tracker - Uses The Graph instead of broken Gamma API.
Tracks whale trades in real-time using Polymarket's subgraph.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Goldsky orderbook subgraph endpoint for Polymarket
SUBGRAPH_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"


class WhalePositionTrackerFixed:
    """
    Fixed tracker that uses The Graph to monitor whale trades.
    Replaces the broken Gamma API implementation.
    """

    def __init__(self):
        self.last_check = {}  # Track last check time per whale
        self.last_trade_id = {}  # Track last seen trade ID per whale

    def get_whale_trades(self, address: str, since_timestamp: int = None) -> Optional[List[Dict]]:
        """Fetch recent trades for a whale from The Graph."""

        # Default to last hour if no timestamp provided
        if not since_timestamp:
            since_timestamp = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        query = """
        query GetWhaleTrades($address: String!, $since: BigInt!) {
          trades(
            first: 100
            orderBy: timestamp
            orderDirection: desc
            where: {
              user: $address
              timestamp_gt: $since
            }
          ) {
            id
            user {
              id
            }
            market {
              id
              question
              conditionId
            }
            outcomeIndex
            type
            shares
            price
            amount
            timestamp
            txHash
          }
        }
        """

        variables = {
            "address": address.lower(),
            "since": since_timestamp
        }

        try:
            response = requests.post(
                SUBGRAPH_URL,
                json={'query': query, 'variables': variables},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'trades' in data['data']:
                    return data['data']['trades']
                else:
                    logger.warning(f"No trades data in response for {address[:10]}")
                    return []
            else:
                logger.error(f"Graph API error for {address[:10]}: Status {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching trades for {address[:10]}: {e}")
            return None

    def detect_new_trades(self, whale_address: str) -> List[Dict]:
        """
        Detect new trades since last check.
        Returns list of new trades with details.
        """
        new_trades = []

        # Get last check time for this whale
        last_check = self.last_check.get(whale_address)
        if not last_check:
            # First check - look back 1 hour
            last_check = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        # Fetch recent trades
        trades = self.get_whale_trades(whale_address, since_timestamp=last_check)

        if trades is None:
            return []  # Error fetching trades

        # Get last seen trade ID
        last_trade_id = self.last_trade_id.get(whale_address, "")

        # Process trades
        for trade in trades:
            trade_id = trade.get('id', '')

            # Skip if we've seen this trade before
            if trade_id and trade_id == last_trade_id:
                break

            # Parse trade data
            timestamp = int(trade.get('timestamp', 0))
            if timestamp > last_check:
                new_trade = {
                    'id': trade_id,
                    'address': whale_address,
                    'type': trade.get('type', 'BUY'),
                    'market_id': trade.get('market', {}).get('conditionId') or trade.get('market', {}).get('id'),
                    'market_title': trade.get('market', {}).get('question', ''),
                    'outcome_index': trade.get('outcomeIndex', 0),
                    'shares': float(trade.get('shares', 0) or 0),
                    'price': float(trade.get('price', 0) or 0),
                    'amount': float(trade.get('amount', 0) or 0),
                    'timestamp': datetime.fromtimestamp(timestamp),
                    'tx_hash': trade.get('txHash', '')
                }

                new_trades.append(new_trade)

                logger.info(f"📊 New trade from {whale_address[:10]}: "
                           f"{new_trade['type']} {new_trade['shares']:.2f} shares "
                           f"@ ${new_trade['price']:.3f}")

        # Update tracking
        if new_trades:
            self.last_trade_id[whale_address] = new_trades[0]['id']
        self.last_check[whale_address] = int(datetime.utcnow().timestamp())

        return new_trades

    def monitor_whale(self, whale_address: str) -> List[Dict]:
        """
        Monitor a single whale for new trades.
        Returns list of detected new trades.
        """
        return self.detect_new_trades(whale_address)

    def get_whale_stats(self, address: str) -> Optional[Dict]:
        """Get aggregated stats for a whale from recent trades."""

        # Fetch last 30 days of trades
        since_timestamp = int((datetime.utcnow() - timedelta(days=30)).timestamp())
        trades = self.get_whale_trades(address, since_timestamp=since_timestamp)

        if not trades:
            return None

        # Calculate stats
        total_volume = sum(float(t.get('amount', 0) or 0) for t in trades)
        total_trades = len(trades)
        unique_markets = len(set(t.get('market', {}).get('id', '') for t in trades))

        return {
            'address': address,
            'total_volume_30d': total_volume,
            'total_trades_30d': total_trades,
            'unique_markets_30d': unique_markets,
            'avg_trade_size': total_volume / total_trades if total_trades > 0 else 0,
            'last_trade_time': datetime.fromtimestamp(int(trades[0].get('timestamp', 0))) if trades else None
        }

    def get_market_details(self, market_id: str) -> Optional[Dict]:
        """Get details about a specific market from the subgraph."""

        query = """
        query GetMarket($id: String!) {
          market(id: $id) {
            id
            question
            conditionId
            outcomeTokens
            createdAt
            volume
            liquidity
          }
        }
        """

        variables = {"id": market_id.lower()}

        try:
            response = requests.post(
                SUBGRAPH_URL,
                json={'query': query, 'variables': variables},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'market' in data['data']:
                    return data['data']['market']

        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")

        return None