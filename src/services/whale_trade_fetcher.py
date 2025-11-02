#!/usr/bin/env python3
"""
Whale Trade Fetcher - Fetches individual trades from Polymarket Data API
Uses the public data-api.polymarket.com endpoint to get real-time trade data.
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade


class WhaleTradeFetcher:
    """
    Fetches individual trades for whales from Polymarket Data API.
    """

    def __init__(self):
        # API endpoint
        self.data_api_base = "https://data-api.polymarket.com"

        # Database
        db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        engine = create_engine(db_url)
        self.Session = sessionmaker(bind=engine)

        # Track last fetch time for each whale
        self.last_fetch = {}

    def fetch_whale_trades(self, whale_address: str, since_timestamp: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        Fetch recent trades for a whale from the Data API.

        Args:
            whale_address: Whale wallet address (can be main wallet or proxy)
            since_timestamp: Unix timestamp to fetch trades after (optional)
            limit: Max number of trades to fetch (default: 100)

        Returns:
            List of trade dictionaries with all details needed for copy trading
        """
        try:
            # Build URL
            url = f"{self.data_api_base}/trades"
            params = {
                'maker': whale_address,
                'limit': limit
            }

            # Fetch trades
            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                print(f"Error fetching trades for {whale_address[:10]}: {response.status_code}")
                return []

            trades = response.json()

            # Filter by timestamp if provided
            if since_timestamp:
                trades = [t for t in trades if t.get('timestamp', 0) > since_timestamp]

            return trades

        except Exception as e:
            print(f"Error fetching trades for {whale_address[:10]}: {e}")
            return []

    def get_new_trades_for_whale(self, whale: Whale) -> List[Dict]:
        """
        Get new trades for a whale since last check.

        Args:
            whale: Whale model instance

        Returns:
            List of new trades
        """
        # Get last check time (or use 1 hour ago if first time)
        last_check = self.last_fetch.get(whale.address)
        if not last_check:
            # First time - get trades from last hour
            last_check = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        # Fetch trades
        trades = self.fetch_whale_trades(whale.address, since_timestamp=last_check)

        # Update last fetch time
        self.last_fetch[whale.address] = int(datetime.utcnow().timestamp())

        return trades

    def parse_trade_for_copy(self, trade: Dict) -> Optional[Dict]:
        """
        Parse a trade from the API into the format needed for copy trading.

        Args:
            trade: Trade dict from Data API

        Returns:
            Dict with market_id, side, price, size, outcome for copy trading
        """
        try:
            return {
                'market_id': trade.get('conditionId'),
                'asset_id': trade.get('asset'),
                'side': trade.get('side'),  # BUY or SELL
                'price': Decimal(str(trade.get('price', 0))),
                'size': Decimal(str(trade.get('size', 0))),
                'timestamp': trade.get('timestamp'),
                'market_title': trade.get('title', 'Unknown Market'),
                'market_slug': trade.get('slug'),
                'outcome': trade.get('outcome'),
                'outcome_index': trade.get('outcomeIndex'),
                'transaction_hash': trade.get('transactionHash')
            }
        except Exception as e:
            print(f"Error parsing trade: {e}")
            return None

    def save_whale_trade(self, whale: Whale, trade_data: Dict) -> bool:
        """
        Save a whale's trade to the database.

        Args:
            whale: Whale model instance
            trade_data: Parsed trade data

        Returns:
            True if saved successfully
        """
        session = self.Session()

        try:
            # Check if trade already exists (by transaction hash or timestamp)
            existing = session.query(Trade).filter(
                Trade.trade_id == trade_data.get('transaction_hash', f"whale-{whale.address[:10]}-{trade_data['timestamp']}")
            ).first()

            if existing:
                return False  # Already saved

            # Generate unique trade ID
            trade_id = trade_data.get('transaction_hash') or f"whale-{whale.address[:10]}-{trade_data['timestamp']}"

            # Create trade record
            trade = Trade(
                trade_id=trade_id,
                trader_address=whale.address,
                market_id=trade_data['market_id'],
                token_id=trade_data.get('asset_id', trade_data['market_id']),
                side=trade_data['side'],
                size=float(trade_data['size']),
                price=float(trade_data['price']),
                amount=float(trade_data['size'] * trade_data['price']),
                market_title=trade_data.get('market_title'),
                outcome=trade_data.get('outcome'),
                transaction_hash=trade_data.get('transaction_hash'),
                timestamp=datetime.fromtimestamp(trade_data['timestamp']),
                is_whale_trade=True,
                followed=False  # Will be set to True if we copy it
            )

            session.add(trade)
            session.commit()
            return True

        except Exception as e:
            print(f"Error saving whale trade: {e}")
            session.rollback()
            return False

        finally:
            session.close()


# Global instance
trade_fetcher = WhaleTradeFetcher()


def test_fetcher():
    """Test the trade fetcher with a known whale."""
    print("=" * 80)
    print("WHALE TRADE FETCHER TEST")
    print("=" * 80)
    print()

    # Test with a known active whale
    test_address = "0x0bfef1bd1d0de160d8a0fbc08cc5a6998180fa02"

    print(f"Fetching recent trades for {test_address[:10]}...")
    trades = trade_fetcher.fetch_whale_trades(test_address, limit=5)

    print(f"\nFound {len(trades)} recent trades:")
    print()

    for i, trade in enumerate(trades, 1):
        parsed = trade_fetcher.parse_trade_for_copy(trade)
        if parsed:
            print(f"Trade {i}:")
            print(f"  Market: {parsed['market_title']}")
            print(f"  Side: {parsed['side']}")
            print(f"  Outcome: {parsed['outcome']}")
            print(f"  Price: ${parsed['price']}")
            print(f"  Size: {parsed['size']}")
            print(f"  Time: {datetime.fromtimestamp(parsed['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
            print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_fetcher()
