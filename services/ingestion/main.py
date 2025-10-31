"""
Data Ingestion Service - Real-time Whale Trade Monitoring

Monitors Polymarket WebSocket feeds for whale trades with sub-100ms latency.
Publishes events to Kafka for downstream processing.

Architecture:
1. WebSocket connection to Polymarket CLOB
2. Subscribe to User channels for each tracked whale
3. Detect trades in real-time
4. Publish to Kafka topics (whale_activity, market_trades)
5. Update metrics (Prometheus)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set
from decimal import Decimal

import websockets
from aiokafka import AIOKafkaProducer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.common.models import Whale, Trade
from dotenv import load_dotenv

load_dotenv()

# Configuration
POLYMARKET_WS_URL = os.getenv('POLYMARKET_WS_URL', 'wss://ws-subscriptions-clob.polymarket.com/ws')
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://trader:changeme123@localhost:5432/polymarket_trader')
ASYNC_DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')

PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9090'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Kafka Topics
TOPIC_WHALE_ACTIVITY = 'whale_activity'
TOPIC_MARKET_TRADES = 'market_trades'
TOPIC_ORDER_BOOKS = 'order_books'

# Prometheus Metrics
whale_trades_detected = Counter(
    'whale_trades_detected_total',
    'Total number of whale trades detected',
    ['whale_address', 'side']
)

websocket_messages_received = Counter(
    'websocket_messages_received_total',
    'Total WebSocket messages received',
    ['message_type']
)

trade_processing_latency = Histogram(
    'trade_processing_latency_seconds',
    'Latency from whale trade detection to Kafka publish',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

active_whale_subscriptions = Gauge(
    'active_whale_subscriptions',
    'Number of whales currently being monitored'
)

websocket_reconnections = Counter(
    'websocket_reconnections_total',
    'Total number of WebSocket reconnections'
)


class PolymarketWebSocketClient:
    """
    WebSocket client for monitoring Polymarket whale trades.

    Subscribes to the 'user' channel for each whale wallet address.
    Detects trades, order updates, and position changes in real-time.
    """

    def __init__(self, kafka_producer: AIOKafkaProducer, db_session: AsyncSession):
        self.kafka_producer = kafka_producer
        self.db_session = db_session
        self.ws = None
        self.subscribed_whales: Set[str] = set()
        self.running = False

    async def connect(self):
        """Establish WebSocket connection to Polymarket"""
        max_retries = 5
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                print(f"Connecting to Polymarket WebSocket... (attempt {attempt + 1}/{max_retries})")
                self.ws = await websockets.connect(
                    POLYMARKET_WS_URL,
                    ping_interval=20,
                    ping_timeout=10
                )
                print(f"✅ Connected to Polymarket WebSocket")
                return True

            except Exception as e:
                print(f"❌ Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Failed to connect after {max_retries} attempts")
                    return False

    async def subscribe_to_whale(self, whale_address: str):
        """
        Subscribe to a whale's user channel.

        Message format:
        {
            "auth": {},
            "type": "subscribe",
            "channel": "user",
            "market": whale_address
        }
        """
        if whale_address in self.subscribed_whales:
            print(f"  Already subscribed to {whale_address[:10]}...")
            return

        subscribe_message = {
            "type": "subscribe",
            "channel": "user",
            "markets": [whale_address]  # Note: Polymarket uses proxy wallet address
        }

        try:
            await self.ws.send(json.dumps(subscribe_message))
            self.subscribed_whales.add(whale_address)
            active_whale_subscriptions.set(len(self.subscribed_whales))
            print(f"  ✅ Subscribed to whale: {whale_address[:10]}...")

        except Exception as e:
            print(f"  ❌ Failed to subscribe to {whale_address}: {e}")

    async def unsubscribe_from_whale(self, whale_address: str):
        """Unsubscribe from a whale's channel"""
        if whale_address not in self.subscribed_whales:
            return

        unsubscribe_message = {
            "type": "unsubscribe",
            "channel": "user",
            "markets": [whale_address]
        }

        try:
            await self.ws.send(json.dumps(unsubscribe_message))
            self.subscribed_whales.remove(whale_address)
            active_whale_subscriptions.set(len(self.subscribed_whales))
            print(f"  Unsubscribed from whale: {whale_address[:10]}...")

        except Exception as e:
            print(f"  Failed to unsubscribe from {whale_address}: {e}")

    async def handle_message(self, message: Dict):
        """
        Process incoming WebSocket messages.

        Message types:
        - 'trade': New trade executed
        - 'order': Order placed/updated/cancelled
        - 'position': Position opened/closed
        """
        start_time = asyncio.get_event_loop().time()

        try:
            msg_type = message.get('type')
            websocket_messages_received.labels(message_type=msg_type).inc()

            if msg_type == 'trade':
                await self.handle_whale_trade(message)

            elif msg_type == 'order':
                await self.handle_order_update(message)

            elif msg_type == 'position':
                await self.handle_position_update(message)

            # Record processing latency
            latency = asyncio.get_event_loop().time() - start_time
            trade_processing_latency.observe(latency)

            if latency > 0.1:  # Warn if > 100ms
                print(f"⚠️  High latency: {latency*1000:.2f}ms for {msg_type}")

        except Exception as e:
            print(f"Error handling message: {e}")
            print(f"Message: {message}")

    async def handle_whale_trade(self, message: Dict):
        """
        Handle a whale trade event.

        Publishes to Kafka for downstream processing (scoring, execution).
        """
        try:
            # Extract trade data
            trader_address = message.get('trader', message.get('maker', ''))
            trade_id = message.get('id', message.get('trade_id', ''))
            market_id = message.get('market')
            token_id = message.get('token_id')
            side = message.get('side', 'BUY').upper()
            size = Decimal(str(message.get('size', 0)))
            price = Decimal(str(message.get('price', 0)))
            amount = size * price
            timestamp = message.get('timestamp', datetime.utcnow().isoformat())

            # Increment whale trade counter
            whale_trades_detected.labels(
                whale_address=trader_address[:10],
                side=side
            ).inc()

            # Create trade event for Kafka with full tracking details
            trade_event = {
                "event_type": "whale_trade",
                "trade_id": trade_id,
                "trader_address": trader_address,
                "market_id": market_id,
                "token_id": token_id,
                "side": side,  # "BUY" or "SELL"
                "action": "buy" if side == "BUY" else "sell",  # Explicit action for execution
                "size": float(size),
                "price": float(price),
                "amount": float(amount),
                "timestamp": timestamp,
                "detected_at": datetime.utcnow().isoformat(),
                # Trade tracking metadata
                "copyable": True,  # Indicates we can copy this trade
                "should_copy": True,  # Execution service should mirror this
                "mirror_action": side.lower(),  # "buy" or "sell" - what we should do
            }

            # Publish to Kafka
            await self.kafka_producer.send(
                TOPIC_WHALE_ACTIVITY,
                value=json.dumps(trade_event).encode('utf-8'),
                key=trader_address.encode('utf-8')
            )

            # Use different emoji for BUY vs SELL
            action_emoji = "📈" if side == "BUY" else "📉"
            action_color = "green" if side == "BUY" else "red"

            print(f"{action_emoji} Whale {side}: {trader_address[:8]}... "
                  f"{size:.0f} shares @ ${price:.3f} = ${amount:.2f} [WILL COPY {side}]")

        except Exception as e:
            print(f"Error handling whale trade: {e}")

    async def handle_order_update(self, message: Dict):
        """Handle order placement/cancellation events"""
        try:
            order_event = {
                "event_type": "whale_order",
                "order_id": message.get('id'),
                "trader_address": message.get('maker'),
                "status": message.get('status'),
                "market_id": message.get('market'),
                "side": message.get('side'),
                "size": message.get('size'),
                "price": message.get('price'),
                "timestamp": message.get('timestamp', datetime.utcnow().isoformat())
            }

            await self.kafka_producer.send(
                TOPIC_WHALE_ACTIVITY,
                value=json.dumps(order_event).encode('utf-8')
            )

        except Exception as e:
            print(f"Error handling order update: {e}")

    async def handle_position_update(self, message: Dict):
        """Handle position opened/closed events"""
        try:
            position_event = {
                "event_type": "whale_position",
                "trader_address": message.get('user_address'),
                "position_id": message.get('position_id'),
                "market_id": message.get('market_id'),
                "status": message.get('status'),
                "pnl": message.get('cash_pnl'),
                "timestamp": datetime.utcnow().isoformat()
            }

            await self.kafka_producer.send(
                TOPIC_WHALE_ACTIVITY,
                value=json.dumps(position_event).encode('utf-8')
            )

        except Exception as e:
            print(f"Error handling position update: {e}")

    async def listen(self):
        """
        Main listening loop.

        Receives messages from WebSocket and processes them.
        Auto-reconnects on connection loss.
        """
        self.running = True

        while self.running:
            try:
                if not self.ws or self.ws.closed:
                    print("WebSocket disconnected. Reconnecting...")
                    websocket_reconnections.inc()
                    await self.connect()

                    # Resubscribe to all whales
                    whales_to_resubscribe = list(self.subscribed_whales)
                    self.subscribed_whales.clear()
                    for whale_address in whales_to_resubscribe:
                        await self.subscribe_to_whale(whale_address)

                # Receive message
                message_raw = await self.ws.recv()
                message = json.loads(message_raw)

                # Handle message
                await self.handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed. Reconnecting...")
                websocket_reconnections.inc()
                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error in listen loop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """Gracefully stop the WebSocket client"""
        self.running = False
        if self.ws:
            await self.ws.close()
        print("WebSocket client stopped")


async def load_whales_from_db(db_session: AsyncSession) -> List[str]:
    """Load whale addresses from database where copying is enabled"""
    try:
        result = await db_session.execute(
            select(Whale.address).where(
                Whale.is_active == True,
                Whale.is_copying_enabled == True,
                Whale.is_blacklisted == False
            )
        )
        whale_addresses = [row[0] for row in result.fetchall()]
        return whale_addresses

    except Exception as e:
        print(f"Error loading whales from database: {e}")
        return []


async def main():
    """Main ingestion service entry point"""

    print("\n" + "="*80)
    print("POLYMARKET DATA INGESTION SERVICE")
    print("Real-time Whale Trade Monitoring")
    print("="*80 + "\n")

    # Start Prometheus metrics server
    start_http_server(PROMETHEUS_PORT)
    print(f"✅ Prometheus metrics: http://localhost:{PROMETHEUS_PORT}")

    # Create database session
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create Kafka producer
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: v  # Already serialized as bytes
    )
    await kafka_producer.start()
    print(f"✅ Connected to Kafka: {KAFKA_BOOTSTRAP_SERVERS}")

    async with async_session() as session:
        # Load whales from database
        whale_addresses = await load_whales_from_db(session)

        if not whale_addresses:
            print("\n⚠️  No whales found in database with copying enabled!")
            print("Run: python scripts/seed_whales.py")
            print("Then enable copying for whales you want to monitor.\n")
            return

        print(f"\n📊 Loaded {len(whale_addresses)} whales from database")

        # Create WebSocket client
        ws_client = PolymarketWebSocketClient(kafka_producer, session)

        # Connect to WebSocket
        connected = await ws_client.connect()
        if not connected:
            print("❌ Failed to connect to WebSocket")
            return

        # Subscribe to all whales
        print(f"\n🔔 Subscribing to {len(whale_addresses)} whale channels...")
        for whale_address in whale_addresses:
            await ws_client.subscribe_to_whale(whale_address)

        print(f"\n✅ Monitoring {len(whale_addresses)} whales in real-time")
        print("Press Ctrl+C to stop\n")

        # Start listening
        try:
            await ws_client.listen()

        except KeyboardInterrupt:
            print("\n\nShutting down...")

        finally:
            await ws_client.stop()
            await kafka_producer.stop()
            await engine.dispose()

    print("\n✅ Data ingestion service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
