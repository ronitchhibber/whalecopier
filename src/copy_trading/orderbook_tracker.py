"""
Orderbook-based Whale Position Tracker
Uses Goldsky's orderbook subgraph to track whale trades in real-time.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

# Goldsky orderbook subgraph endpoint
ORDERBOOK_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"


class OrderbookTracker:
    """
    Tracks whale trades using the Goldsky orderbook subgraph.
    """

    def __init__(self):
        self.last_check = {}  # Track last check time per whale
        self.last_event_id = {}  # Track last seen event ID per whale

    def get_whale_orders(self, address: str, since_timestamp: int = None) -> Optional[List[Dict]]:
        """Fetch recent order fills for a whale from the orderbook subgraph."""

        # Default to last hour if no timestamp provided
        if not since_timestamp:
            since_timestamp = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        query = """
        query GetWhaleOrders($taker: String!, $since: BigInt!) {
          orderFilledEvents(
            first: 100
            orderBy: timestamp
            orderDirection: desc
            where: {
              taker: $taker
              timestamp_gte: $since
            }
          ) {
            id
            timestamp
            transactionHash
            taker
            maker
            makerAssetId
            takerAssetId
            makerAmountFilled
            takerAmountFilled
          }
        }
        """

        variables = {
            "taker": address.lower(),
            "since": str(since_timestamp)
        }

        try:
            response = requests.post(
                ORDERBOOK_URL,
                json={'query': query, 'variables': variables},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'orderFilledEvents' in data['data']:
                    return data['data']['orderFilledEvents']
                else:
                    logger.warning(f"No order data in response for {address[:10]}")
                    return []
            else:
                logger.error(f"Orderbook API error for {address[:10]}: Status {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching orders for {address[:10]}: {e}")
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

        # Fetch recent orders
        orders = self.get_whale_orders(whale_address, since_timestamp=last_check)

        if orders is None:
            return []  # Error fetching orders

        # Get last seen event ID
        last_event_id = self.last_event_id.get(whale_address, "")

        # Process orders
        for order in orders:
            event_id = order.get('id', '')

            # Skip if we've seen this order before
            if event_id and event_id == last_event_id:
                break

            # Parse order data
            timestamp = int(order.get('timestamp', 0))
            if timestamp > last_check:
                # Determine if this is a buy or sell
                # If takerAssetId is USDC (ends in 0000...), it's a buy, otherwise sell
                taker_asset = order.get('takerAssetId', '')
                is_buy = taker_asset.endswith('0' * 40)  # USDC has 40 zeros at the end

                maker_amount = float(order.get('makerAmountFilled', 0) or 0) / 1e6  # Convert from 6 decimals
                taker_amount = float(order.get('takerAmountFilled', 0) or 0) / 1e6

                # Calculate price (USDC per share)
                if is_buy and maker_amount > 0:
                    price = taker_amount / maker_amount  # USDC paid / shares received
                elif not is_buy and taker_amount > 0:
                    price = maker_amount / taker_amount  # USDC received / shares sold
                else:
                    price = 0

                new_trade = {
                    'id': event_id,
                    'address': whale_address,
                    'type': 'BUY' if is_buy else 'SELL',
                    'market_id': order.get('makerAssetId') if is_buy else order.get('takerAssetId'),
                    'shares': maker_amount if is_buy else taker_amount,
                    'price': price,
                    'amount': taker_amount if is_buy else maker_amount,  # USDC amount
                    'timestamp': datetime.fromtimestamp(timestamp),
                    'tx_hash': order.get('transactionHash', '')
                }

                new_trades.append(new_trade)

                logger.info(f"📊 New order from {whale_address[:10]}: "
                           f"{new_trade['type']} {new_trade['shares']:.2f} shares "
                           f"@ ${new_trade['price']:.3f} = ${new_trade['amount']:.2f}")

        # Update tracking
        if new_trades:
            self.last_event_id[whale_address] = new_trades[0]['id']
        self.last_check[whale_address] = int(datetime.utcnow().timestamp())

        return new_trades

    def monitor_whale(self, whale_address: str) -> List[Dict]:
        """
        Monitor a single whale for new trades.
        Returns list of detected new trades.
        """
        return self.detect_new_trades(whale_address)

    def get_recent_volume(self, address: str, days: int = 30) -> float:
        """Get total trading volume for a whale over the specified days."""

        since_timestamp = int((datetime.utcnow() - timedelta(days=days)).timestamp())
        orders = self.get_whale_orders(address, since_timestamp=since_timestamp)

        if not orders:
            return 0

        total_volume = 0
        for order in orders:
            # Volume is the USDC amount (either taker or maker depending on trade direction)
            taker_amount = float(order.get('takerAmountFilled', 0) or 0) / 1e6
            maker_amount = float(order.get('makerAmountFilled', 0) or 0) / 1e6

            # Check if taker asset is USDC (buying) or maker asset is USDC (selling)
            taker_asset = order.get('takerAssetId', '')
            if taker_asset.endswith('0' * 40):  # USDC
                total_volume += taker_amount
            else:
                total_volume += maker_amount

        return total_volume