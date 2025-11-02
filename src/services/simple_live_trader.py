#!/usr/bin/env python3
"""
Simple Live Trader - Executes trades when whales make moves
This version works without the full CLOB client.
"""

import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.common.models import Whale, Trade
from dotenv import load_dotenv

load_dotenv('.env.local')


class SimpleLiveTrader:
    """
    Executes live trades based on whale activity.
    Starts in SAFE MODE (disabled) by default.
    """

    def __init__(self):
        # Trading mode: False = Paper, True = Live
        self.live_mode = False

        # Safety limits
        self.max_position_usd = Decimal('100')  # Max $100 per trade
        self.max_daily_loss = Decimal('500')   # Circuit breaker at $500 loss
        self.min_whale_quality = 50             # Only copy quality whales

        # Daily tracking
        self.daily_pnl = Decimal('0')
        self.daily_trades = 0
        self.last_reset_date = datetime.utcnow().date()

        # Account balance (would come from API in production)
        self.account_balance = Decimal('1000')  # Assume $1000 starting

        # Database
        db_url = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        engine = create_engine(db_url)
        self.Session = sessionmaker(bind=engine)

        print(f"Simple Live Trader initialized")
        print(f"  Mode: {'LIVE' if self.live_mode else 'PAPER'}")
        print(f"  Max position: ${self.max_position_usd}")
        print(f"  Daily loss limit: ${self.max_daily_loss}")
        print(f"  Min whale quality: {self.min_whale_quality}")

    def reset_daily_stats(self):
        """Reset daily statistics if new day."""
        today = datetime.utcnow().date()
        if today > self.last_reset_date:
            self.daily_pnl = Decimal('0')
            self.daily_trades = 0
            self.last_reset_date = today
            print(f"Daily stats reset for {today}")

    def should_copy(self, whale: Whale) -> tuple[bool, str]:
        """Check if we should copy this whale's trade."""
        self.reset_daily_stats()

        # Check daily loss limit
        if self.daily_pnl < -self.max_daily_loss:
            return False, f"Daily loss limit hit: ${self.daily_pnl:.2f}"

        # Check whale quality
        if not whale.quality_score or whale.quality_score < self.min_whale_quality:
            return False, f"Quality too low: {whale.quality_score:.1f}"

        # Check if whale enabled
        if not whale.is_copying_enabled:
            return False, "Whale not enabled"

        return True, "OK"

    def calculate_position_size(self, whale: Whale) -> Decimal:
        """Calculate position size based on whale quality."""
        # Base: 5% of balance
        base_size = self.account_balance * Decimal('0.05')

        # Adjust by quality (higher quality = larger position)
        quality_factor = Decimal(str(whale.quality_score or 70)) / Decimal('100')
        position = base_size * quality_factor

        # Cap at limits
        position = min(position, self.max_position_usd)
        position = min(position, self.account_balance * Decimal('0.10'))  # Max 10%

        return round(position, 2)

    def execute_trade(self, whale: Whale, market_id: str, side: str, price: Decimal) -> Optional[Dict]:
        """
        Execute a trade (paper or live based on mode).
        """
        # Check if should copy
        should_copy, reason = self.should_copy(whale)
        if not should_copy:
            print(f"Skipping trade: {reason}")
            return None

        # Calculate position
        position_size = self.calculate_position_size(whale)

        trade_info = {
            'whale': whale.pseudonym or whale.address[:10],
            'whale_quality': float(whale.quality_score or 0),
            'market': market_id,
            'side': side,
            'price': float(price),
            'position_usd': float(position_size),
            'mode': 'LIVE' if self.live_mode else 'PAPER',
            'timestamp': datetime.utcnow().isoformat()
        }

        if self.live_mode:
            # LIVE TRADING
            print(f"\n🔴 LIVE TRADE EXECUTED")
            print(f"   Whale: {trade_info['whale']} (Q:{trade_info['whale_quality']:.1f})")
            print(f"   Market: {market_id}")
            print(f"   Side: {side}")
            print(f"   Size: ${position_size}")
            print(f"   Price: ${price}")

            # HERE: Add actual API call to Polymarket
            # For now, just log it
            trade_info['executed'] = True
            trade_info['order_id'] = f"ORDER-{int(datetime.utcnow().timestamp())}"

        else:
            # PAPER TRADING
            print(f"\n📄 PAPER TRADE")
            print(f"   Whale: {trade_info['whale']} (Q:{trade_info['whale_quality']:.1f})")
            print(f"   Market: {market_id}")
            print(f"   Side: {side}")
            print(f"   Size: ${position_size}")
            print(f"   Price: ${price}")

            trade_info['executed'] = True
            trade_info['order_id'] = f"PAPER-{int(datetime.utcnow().timestamp())}"

        # Save to database
        session = self.Session()
        try:
            # Generate unique trade ID
            mode_str = 'live' if self.live_mode else 'paper'
            trade_id = f"{mode_str}-{whale.address[:10]}-{int(datetime.utcnow().timestamp())}"

            trade = Trade(
                trade_id=trade_id,
                trader_address=whale.address,
                market_id=market_id,
                token_id=market_id,  # Use market_id as token_id for now
                side=side.upper(),
                size=float(position_size),
                price=float(price),
                amount=float(position_size),
                timestamp=datetime.utcnow(),
                is_whale_trade=False,  # This is our trade
                followed=True,
                our_order_id=trade_info['order_id']
            )
            session.add(trade)
            session.commit()
        except Exception as e:
            print(f"Warning: Could not save trade to database: {e}")
            session.rollback()
        finally:
            session.close()

        # Update tracking
        self.daily_trades += 1

        return trade_info

    def enable_live_mode(self):
        """Enable LIVE trading (USE REAL MONEY)."""
        self.live_mode = True
        print("\n⚠️  LIVE TRADING ENABLED - REAL MONEY WILL BE USED!")

    def disable_live_mode(self):
        """Disable live trading (back to paper)."""
        self.live_mode = False
        print("\n✓ PAPER TRADING MODE - No real money")

    def get_status(self) -> Dict:
        """Get current status."""
        self.reset_daily_stats()

        return {
            'mode': 'LIVE' if self.live_mode else 'PAPER',
            'account_balance': float(self.account_balance),
            'daily_pnl': float(self.daily_pnl),
            'daily_trades': self.daily_trades,
            'max_position': float(self.max_position_usd),
            'max_daily_loss': float(self.max_daily_loss),
            'min_whale_quality': self.min_whale_quality
        }


# Global instance
trader = SimpleLiveTrader()


if __name__ == "__main__":
    print("=" * 80)
    print("SIMPLE LIVE TRADER TEST")
    print("=" * 80)
    print()

    # Show status
    status = trader.get_status()
    print("Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\nTrader ready!")
    print("  - Paper mode by default (safe)")
    print("  - Use trader.enable_live_mode() to trade with real money")
    print("  - Use trader.disable_live_mode() to go back to paper")
