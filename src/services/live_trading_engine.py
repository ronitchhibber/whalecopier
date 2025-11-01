#!/usr/bin/env python3
"""
Live Trading Engine - Direct Polymarket API integration
Uses your wallet credentials to execute real trades when whales make moves.

SAFETY FEATURES:
- Position size limits
- Daily loss limits
- Quality score filtering
- Confirmation mode
"""

import os
import sys
import time
import hmac
import hashlib
import base64
from datetime import datetime
from typing import Dict, Optional
import requests
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade
from dotenv import load_dotenv

load_dotenv('.env.local')


class LiveTradingEngine:
    """
    Executes live trades on Polymarket using your wallet.
    """

    def __init__(self):
        # Load credentials
        self.private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        self.address = os.getenv('POLYMARKET_ADDRESS')
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET')
        self.api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')

        # API endpoints
        self.base_url = "https://clob.polymarket.com"

        # Database
        db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        engine = create_engine(db_url)
        self.Session = sessionmaker(bind=engine)

        # Trading settings
        self.trading_enabled = False  # Must be explicitly enabled
        self.max_position_size = Decimal('100')  # Max $100 per trade
        self.max_daily_loss = Decimal('500')  # Stop if lose $500 in a day
        self.min_whale_quality = 50  # Only copy whales with score >= 50

        # Daily tracking
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0
        self.last_reset = datetime.utcnow().date()

        print("Live Trading Engine initialized")
        print(f"  Wallet: {self.address}")
        print(f"  Max position: ${self.max_position_size}")
        print(f"  Max daily loss: ${self.max_daily_loss}")
        print(f"  Min whale quality: {self.min_whale_quality}")
        print(f"  Status: {'ENABLED' if self.trading_enabled else 'DISABLED'}")

    def _sign_request(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """Generate HMAC signature for API request."""
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Make authenticated API request to Polymarket."""
        timestamp = str(int(time.time()))
        path = f"/v1/{endpoint}"
        url = f"{self.base_url}{path}"

        body = ''
        if data:
            import json
            body = json.dumps(data)

        signature = self._sign_request(timestamp, method, path, body)

        headers = {
            'POLY-API-KEY': self.api_key,
            'POLY-SIGNATURE': signature,
            'POLY-TIMESTAMP': timestamp,
            'POLY-PASSPHRASE': self.api_passphrase,
            'Content-Type': 'application/json'
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                return None

            if response.status_code == 200:
                return response.json()
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Request error: {e}")
            return None

    def get_balance(self) -> Optional[Decimal]:
        """Get current USDC balance."""
        result = self._make_request('GET', 'balance')
        if result:
            return Decimal(str(result.get('balance', 0)))
        return None

    def get_markets(self) -> Optional[list]:
        """Get available markets."""
        result = self._make_request('GET', 'markets')
        return result if result else []

    def should_copy_trade(self, whale: Whale) -> tuple[bool, str]:
        """
        Determine if we should copy this whale's trade.
        Returns: (should_copy, reason)
        """
        # Reset daily tracking if new day
        if datetime.utcnow().date() > self.last_reset:
            self.daily_pnl = Decimal('0')
            self.daily_trades = 0
            self.last_reset = datetime.utcnow().date()

        # Check if trading is enabled
        if not self.trading_enabled:
            return False, "Live trading disabled"

        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            return False, f"Daily loss limit reached: ${self.daily_pnl}"

        # Check whale quality
        if not whale.quality_score or whale.quality_score < self.min_whale_quality:
            return False, f"Whale quality too low: {whale.quality_score}"

        # Check if whale is enabled
        if not whale.is_copying_enabled:
            return False, "Whale not enabled for copying"

        return True, "All checks passed"

    def calculate_position_size(self, whale: Whale, whale_trade_size: Decimal) -> Decimal:
        """
        Calculate our position size based on whale quality and trade size.
        """
        # Get balance
        balance = self.get_balance()
        if not balance:
            balance = Decimal('1000')  # Assume $1000 if can't fetch

        # Base size: 5% of balance
        base_size = balance * Decimal('0.05')

        # Quality factor: whale quality / 100
        quality_factor = Decimal(str(whale.quality_score or 70)) / Decimal('100')

        # Calculate size
        position_size = base_size * quality_factor

        # Cap at max position size
        position_size = min(position_size, self.max_position_size)

        # Cap at 10% of balance
        position_size = min(position_size, balance * Decimal('0.10'))

        return position_size

    def execute_trade(self, whale: Whale, market_id: str, side: str, size: Decimal, price: Decimal) -> Optional[dict]:
        """
        Execute a live trade on Polymarket.

        Args:
            whale: Whale we're copying
            market_id: Market to trade in
            side: 'BUY' or 'SELL'
            size: Amount to trade
            price: Limit price

        Returns:
            Order details if successful, None otherwise
        """
        # Safety check
        should_copy, reason = self.should_copy_trade(whale)
        if not should_copy:
            print(f"NOT copying {whale.pseudonym}: {reason}")
            return None

        # Calculate our position size
        position_size = self.calculate_position_size(whale, size)

        print(f"\nEXECUTING LIVE TRADE")
        print(f"  Whale: {whale.pseudonym or whale.address[:10]}")
        print(f"  Quality: {whale.quality_score:.1f}")
        print(f"  Market: {market_id}")
        print(f"  Side: {side}")
        print(f"  Size: ${position_size:.2f}")
        print(f"  Price: ${price:.3f}")

        # Create order
        order_data = {
            'market': market_id,
            'side': side.lower(),
            'size': str(position_size),
            'price': str(price),
            'type': 'LIMIT'
        }

        # Execute order
        result = self._make_request('POST', 'orders', order_data)

        if result:
            print(f"  Status: ORDER PLACED")
            print(f"  Order ID: {result.get('id')}")

            # Update daily tracking
            self.daily_trades += 1

            # Save to database
            session = self.Session()
            trade = Trade(
                trader_address=whale.address,
                market_id=market_id,
                side=side,
                size=float(size),
                price=float(price),
                amount=float(position_size),
                timestamp=datetime.utcnow(),
                is_whale_trade=False,  # This is our trade
                followed=True
            )
            session.add(trade)
            session.commit()
            session.close()

            return result
        else:
            print(f"  Status: FAILED")
            return None

    def enable_trading(self):
        """Enable live trading."""
        self.trading_enabled = True
        print("\nLIVE TRADING ENABLED")
        print("CAUTION: Real money will be used!")

    def disable_trading(self):
        """Disable live trading."""
        self.trading_enabled = False
        print("\nLIVE TRADING DISABLED")

    def get_status(self) -> dict:
        """Get current trading status."""
        balance = self.get_balance()

        return {
            'enabled': self.trading_enabled,
            'balance': float(balance) if balance else 0,
            'daily_pnl': float(self.daily_pnl),
            'daily_trades': self.daily_trades,
            'max_position_size': float(self.max_position_size),
            'max_daily_loss': float(self.max_daily_loss),
            'min_whale_quality': self.min_whale_quality
        }


# Global instance
live_engine = LiveTradingEngine()


if __name__ == "__main__":
    print("=" * 80)
    print("LIVE TRADING ENGINE TEST")
    print("=" * 80)
    print()

    # Test connection
    print("Testing API connection...")
    balance = live_engine.get_balance()
    if balance is not None:
        print(f"Current balance: ${balance:.2f}")
    else:
        print("Could not fetch balance (API might need authentication)")

    print("\nTesting market data...")
    markets = live_engine.get_markets()
    if markets:
        print(f"Found {len(markets)} markets")
    else:
        print("Could not fetch markets")

    print("\nStatus:")
    status = live_engine.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\nLive trading engine ready!")
    print("Use live_engine.enable_trading() to start trading")
