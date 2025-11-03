#!/usr/bin/env python3
"""
Real-Time Whale Trade Monitor
Continuously monitors for new whale trades and executes copy trades with minimal latency.
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from libs.common.models import Whale, Trade, TradingConfig
from libs.trading.bet_weighting import BetWeightingEngine, WhaleProfile, MarketContext, PortfolioState
from libs.trading.real_trader import RealTradingEngine
from src.api.polymarket_client import PolymarketClient
from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import Session

load_dotenv()

class RealtimeTradeMonitor:
    def __init__(self, polling_interval=2.0):
        """
        Args:
            polling_interval: Seconds between checks (default 2 seconds for low latency)
        """
        self.polling_interval = polling_interval
        self.last_trade_timestamp = None

        # Create database connection
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
        self.engine = create_engine(DATABASE_URL)

        # Initialize Polymarket client with credentials from .env
        print("🔌 Initializing Polymarket client...")
        self.polymarket_client = PolymarketClient(
            api_key=os.getenv('POLYMARKET_API_KEY'),
            secret=os.getenv('POLYMARKET_API_SECRET'),
            passphrase=os.getenv('POLYMARKET_API_PASSPHRASE'),
            private_key=os.getenv('POLYMARKET_PRIVATE_KEY'),
        )

        # Initialize trading engine (starts in PAPER mode for safety)
        self.trader = RealTradingEngine(
            mode='PAPER',  # Change to 'LIVE' when ready for real trading
            initial_balance=100.0,  # Your account balance
            weighting_engine=BetWeightingEngine(
                base_position_pct=0.02,  # 2%
                max_position_pct=0.05,   # 5%
                min_position_size=1.0,   # $1 min
                max_position_size=10.0,  # $10 max
            ),
            daily_loss_limit=100.0,   # $100 daily limit
            hourly_loss_limit=100.0,   # $100 hourly limit
            enable_circuit_breaker=False,  # Circuit breaker disabled
            db_engine=self.engine,  # Pass database engine for position persistence
            polymarket_client=self.polymarket_client,  # Pass Polymarket client for live trading
        )

        # Track which whales we're following
        self.active_whales = set()

    def load_active_whales(self):
        """Load all qualified whales from database"""
        with Session(self.engine) as session:
            whales = session.query(Whale).filter(
                Whale.quality_score >= 70.0,  # Only high quality whales
                Whale.sharpe_ratio >= 2.0,
                Whale.total_trades >= 5
            ).all()

            self.active_whales = {whale.address for whale in whales}
            print(f"📊 Monitoring {len(self.active_whales)} qualified whales")

            return whales

    def is_copy_trading_enabled(self):
        """Check if copy trading is enabled (kill switch check)"""
        try:
            with Session(self.engine) as session:
                config = session.query(TradingConfig).filter_by(id=1).first()
                if not config:
                    # If no config exists, default to enabled for backwards compatibility
                    return True
                return config.copy_trading_enabled
        except Exception as e:
            print(f"⚠️  Error checking kill switch: {e}")
            # On error, default to enabled to avoid disruption
            return True

    def check_new_trades(self):
        """Check for new trades from monitored whales"""
        try:
            with Session(self.engine) as session:
                # Get most recent trade timestamp if we don't have it
                if self.last_trade_timestamp is None:
                    latest = session.query(func.max(Trade.timestamp)).scalar()
                    self.last_trade_timestamp = latest or datetime(2020, 1, 1)
                    print(f"🔍 Starting from timestamp: {self.last_trade_timestamp}")
                    return []

                # Query for new trades from our whales
                new_trades = session.query(Trade).filter(
                    Trade.timestamp > self.last_trade_timestamp,
                    Trade.trader_address.in_(self.active_whales)
                ).order_by(Trade.timestamp).all()

                if new_trades:
                    self.last_trade_timestamp = new_trades[-1].timestamp
                    print(f"🆕 Found {len(new_trades)} new trades! (Latest: {self.last_trade_timestamp})")

                return new_trades

        except Exception as e:
            print(f"❌ Error checking trades: {e}")
            return []

    async def process_trade(self, trade):
        """Process a single whale trade"""
        try:
            # Get whale profile
            with Session(self.engine) as session:
                whale = session.query(Whale).filter_by(address=trade.trader_address).first()
                if not whale:
                    return

                # Create whale profile (convert Decimal to float)
                whale_profile = WhaleProfile(
                    address=whale.address,
                    quality_score=float(whale.quality_score) if whale.quality_score else 70.0,
                    sharpe_ratio=float(whale.sharpe_ratio) if whale.sharpe_ratio else 2.0,
                    win_rate=float(whale.win_rate) if whale.win_rate else 50.0,
                    total_pnl=float(whale.total_pnl) if whale.total_pnl else 0.0,
                    total_volume=float(whale.total_volume) if whale.total_volume else 0.0,
                    total_trades=whale.total_trades or 0,
                    avg_position_size=float(whale.avg_trade_size) if whale.avg_trade_size else 100.0,
                    consistency_score=50.0,  # Default value since field doesn't exist in model
                    recent_performance=float(whale.roi) if whale.roi else 0.0
                )

                # Create market context (simplified - in production, fetch from Polymarket API)
                market_context = MarketContext(
                    market_id=trade.market_id,
                    title=trade.market_title or f"Market {trade.market_id[:8]}",
                    liquidity=10000.0,  # Default assumption
                    spread=0.02,  # Assume 2% spread
                    volatility=0.25,  # Assume 25% volatility
                    current_price=float(trade.price),
                    category=trade.category.value if trade.category else "unknown",
                    time_to_close=48  # Assume 48 hours
                )

                # Execute the trade
                order = await self.trader.process_whale_trade(
                    whale=whale_profile,
                    market=market_context,
                    entry_price=float(trade.price),
                    whale_size=float(trade.size),
                    token_id=trade.token_id  # Pass token_id for Polymarket execution
                )

                if order and order.executed:
                    print(f"✅ EXECUTED: {(trade.market_title or 'Unknown')[:50]} | ${order.size_usd:.2f} @ {order.execution_price:.3f}")
                elif order:
                    print(f"⏸️  PENDING: {(trade.market_title or 'Unknown')[:50]} | ${order.size_usd:.2f} (confidence: {order.confidence}/100)")
                else:
                    print(f"❌ REJECTED: {(trade.market_title or 'Unknown')[:50]} (failed validation)")

        except Exception as e:
            print(f"❌ Error processing trade: {e}")

    async def run(self):
        """Main monitoring loop"""
        print("=" * 80)
        print("🚨 REAL-TIME WHALE TRADE MONITOR")
        print("=" * 80)
        print(f"Mode: {self.trader.mode}")
        print(f"Balance: ${self.trader.balance:.2f}")
        print(f"Polling Interval: {self.polling_interval}s (LOW LATENCY)")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Load whales
        whales = self.load_active_whales()

        if not whales:
            print("⚠️  No qualified whales found! Run whale discovery first.")
            return

        print(f"\n🔄 Monitoring for new trades every {self.polling_interval}s...")
        print("Press Ctrl+C to stop\n")

        trades_processed = 0

        try:
            while True:
                # Check kill switch before processing trades
                if not self.is_copy_trading_enabled():
                    # Kill switch is active - skip processing but continue monitoring
                    if trades_processed == 0 or trades_processed % 30 == 0:
                        print("⏸️  Copy trading PAUSED (kill switch active) - Monitoring continues...")
                    await asyncio.sleep(self.polling_interval)
                    continue

                # Check for new trades
                new_trades = self.check_new_trades()

                # Process each new trade
                for trade in new_trades:
                    await self.process_trade(trade)
                    trades_processed += 1

                # Print status every 30 seconds
                if trades_processed % 15 == 0 and trades_processed > 0:
                    self.trader.print_summary()

                # Wait before next check
                await asyncio.sleep(self.polling_interval)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 80)
            print("🛑 MONITOR STOPPED")
            print("=" * 80)
            self.trader.print_summary()
            print("=" * 80)

def main():
    # Create and run monitor
    monitor = RealtimeTradeMonitor(polling_interval=2.0)  # Check every 2 seconds

    # Run async
    asyncio.run(monitor.run())

if __name__ == "__main__":
    main()
