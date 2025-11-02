"""
WebSocket Real-time Data Pipeline for Polymarket
Handles live streaming of orderbook events and whale trades
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Any, Callable, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events from WebSocket streams"""
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    MARKET_UPDATE = "market_update"
    PRICE_UPDATE = "price_update"
    WHALE_TRADE = "whale_trade"


@dataclass
class StreamEvent:
    """Represents a real-time event from the WebSocket stream"""
    event_type: EventType
    timestamp: int
    data: Dict[str, Any]
    market_id: Optional[str] = None
    user_address: Optional[str] = None


class PolymarketWebSocketClient:
    """
    WebSocket client for real-time Polymarket data
    Connects to multiple endpoints for comprehensive data coverage
    """

    # Known WebSocket endpoints for Polymarket data
    ENDPOINTS = {
        "orderbook": "wss://ws-subscriptions-clob.polymarket.com",
        "markets": "wss://ws-markets.polymarket.com",
        "backup": "wss://data-api.polymarket.com/live"
    }

    def __init__(self, whale_addresses: Set[str] = None):
        self.whale_addresses = whale_addresses or set()
        self.connections = {}
        self.handlers = {}
        self.running = False
        self.reconnect_delay = 5  # seconds
        self.heartbeat_interval = 30  # seconds

    def add_whale(self, address: str):
        """Add a whale address to monitor"""
        self.whale_addresses.add(address.lower())
        logger.info(f"Added whale to monitor: {address}")

    def remove_whale(self, address: str):
        """Remove a whale from monitoring"""
        self.whale_addresses.discard(address.lower())
        logger.info(f"Removed whale from monitoring: {address}")

    def register_handler(self, event_type: EventType, handler: Callable):
        """Register a handler for specific event types"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}")

    async def _handle_event(self, event: StreamEvent):
        """Dispatch event to registered handlers"""
        # Check if this is a whale trade
        if event.user_address and event.user_address.lower() in self.whale_addresses:
            event.event_type = EventType.WHALE_TRADE

        # Call handlers for this event type
        if event.event_type in self.handlers:
            for handler in self.handlers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")

    async def _parse_message(self, message: str, source: str) -> Optional[StreamEvent]:
        """Parse WebSocket message into StreamEvent"""
        try:
            data = json.loads(message)

            # Parse based on message structure (varies by endpoint)
            if source == "orderbook":
                return self._parse_orderbook_message(data)
            elif source == "markets":
                return self._parse_market_message(data)
            else:
                return self._parse_generic_message(data)

        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {message[:100]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing message from {source}: {e}")
            return None

    def _parse_orderbook_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse orderbook WebSocket message"""
        msg_type = data.get("type", "")

        if msg_type == "order":
            return StreamEvent(
                event_type=EventType.ORDER_PLACED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("user")
            )
        elif msg_type == "fill":
            return StreamEvent(
                event_type=EventType.ORDER_FILLED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("taker")
            )
        elif msg_type == "cancel":
            return StreamEvent(
                event_type=EventType.ORDER_CANCELLED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("user")
            )
        return None

    def _parse_market_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse market update WebSocket message"""
        if "price" in data:
            return StreamEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("marketId")
            )
        else:
            return StreamEvent(
                event_type=EventType.MARKET_UPDATE,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("marketId")
            )

    def _parse_generic_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse generic WebSocket message"""
        return StreamEvent(
            event_type=EventType.MARKET_UPDATE,
            timestamp=data.get("timestamp", int(datetime.now().timestamp())),
            data=data
        )

    async def _connect_endpoint(self, name: str, url: str):
        """Connect to a specific WebSocket endpoint"""
        retry_count = 0
        max_retries = 5

        while self.running and retry_count < max_retries:
            try:
                logger.info(f"Connecting to {name}: {url}")

                async with websockets.connect(url) as websocket:
                    self.connections[name] = websocket
                    retry_count = 0  # Reset on successful connection

                    # Send initial subscriptions
                    await self._subscribe_to_events(websocket, name)

                    # Handle messages
                    async for message in websocket:
                        if not self.running:
                            break

                        event = await self._parse_message(message, name)
                        if event:
                            await self._handle_event(event)

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Connection closed for {name}, reconnecting...")
                retry_count += 1
                await asyncio.sleep(self.reconnect_delay * retry_count)

            except Exception as e:
                logger.error(f"Error in {name} connection: {e}")
                retry_count += 1
                await asyncio.sleep(self.reconnect_delay * retry_count)

        logger.info(f"Stopped connection to {name}")

    async def _subscribe_to_events(self, websocket, endpoint_name: str):
        """Send subscription messages to WebSocket endpoint"""
        subscriptions = []

        if endpoint_name == "orderbook":
            # Subscribe to order events
            subscriptions.append({
                "type": "subscribe",
                "channel": "orders",
                "markets": "all"  # Or specific market IDs
            })

            # Subscribe to fills
            subscriptions.append({
                "type": "subscribe",
                "channel": "fills",
                "markets": "all"
            })

        elif endpoint_name == "markets":
            # Subscribe to market updates
            subscriptions.append({
                "type": "subscribe",
                "channel": "markets",
                "markets": "all"
            })

        for sub in subscriptions:
            await websocket.send(json.dumps(sub))
            logger.info(f"Sent subscription: {sub}")

    async def _heartbeat(self):
        """Send periodic heartbeat to keep connections alive"""
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)

            for name, ws in list(self.connections.items()):
                try:
                    if ws and not ws.closed:
                        await ws.ping()
                except Exception as e:
                    logger.error(f"Heartbeat failed for {name}: {e}")

    async def start(self):
        """Start WebSocket connections"""
        if self.running:
            logger.warning("WebSocket client already running")
            return

        self.running = True
        logger.info("Starting WebSocket client...")

        # Create connection tasks
        tasks = []
        for name, url in self.ENDPOINTS.items():
            tasks.append(asyncio.create_task(self._connect_endpoint(name, url)))

        # Add heartbeat task
        tasks.append(asyncio.create_task(self._heartbeat()))

        # Run all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop WebSocket connections"""
        logger.info("Stopping WebSocket client...")
        self.running = False

        # Close all connections
        for name, ws in self.connections.items():
            if ws and not ws.closed:
                await ws.close()
                logger.info(f"Closed connection to {name}")

        self.connections.clear()


class RealTimeTradeMonitor:
    """
    Monitor real-time trades and trigger copy trading
    """

    def __init__(self, ws_client: PolymarketWebSocketClient):
        self.ws_client = ws_client
        self.trade_queue = asyncio.Queue()
        self.processing = False

        # Register handlers
        ws_client.register_handler(EventType.WHALE_TRADE, self.handle_whale_trade)
        ws_client.register_handler(EventType.ORDER_FILLED, self.handle_order_filled)

    async def handle_whale_trade(self, event: StreamEvent):
        """Handle detected whale trade"""
        logger.info(f"🐋 Whale trade detected: {event.user_address} in market {event.market_id}")

        # Add to processing queue
        await self.trade_queue.put({
            "type": "whale_trade",
            "timestamp": event.timestamp,
            "whale": event.user_address,
            "market": event.market_id,
            "data": event.data
        })

    async def handle_order_filled(self, event: StreamEvent):
        """Handle order filled events"""
        # Check if this involves a whale
        if event.user_address and event.user_address.lower() in self.ws_client.whale_addresses:
            await self.handle_whale_trade(event)

    async def process_trades(self):
        """Process queued trades"""
        self.processing = True

        while self.processing:
            try:
                # Get trade from queue (wait up to 1 second)
                trade = await asyncio.wait_for(self.trade_queue.get(), timeout=1.0)

                # Process the trade
                logger.info(f"Processing trade: {trade['type']} from {trade['whale']}")

                # TODO: Implement actual copy trading logic here
                # This would involve:
                # 1. Analyzing the whale's trade
                # 2. Applying position sizing
                # 3. Checking risk limits
                # 4. Executing the copy trade

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing trade: {e}")

    async def start(self):
        """Start monitoring"""
        # Start WebSocket client
        ws_task = asyncio.create_task(self.ws_client.start())

        # Start trade processor
        processor_task = asyncio.create_task(self.process_trades())

        # Run both
        await asyncio.gather(ws_task, processor_task)

    async def stop(self):
        """Stop monitoring"""
        self.processing = False
        await self.ws_client.stop()


async def test_websocket():
    """Test WebSocket connection"""
    # Create client with some whale addresses
    whales = {
        "0x1234567890123456789012345678901234567890",  # Example whale
        "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"   # Another example
    }

    client = PolymarketWebSocketClient(whales)

    # Create monitor
    monitor = RealTimeTradeMonitor(client)

    # Add a simple handler to log events
    async def log_handler(event: StreamEvent):
        logger.info(f"Event: {event.event_type.value} - Market: {event.market_id}")

    client.register_handler(EventType.PRICE_UPDATE, log_handler)
    client.register_handler(EventType.MARKET_UPDATE, log_handler)

    # Run for 30 seconds
    try:
        logger.info("Starting WebSocket test...")

        # Start monitor in background
        monitor_task = asyncio.create_task(monitor.start())

        # Wait 30 seconds
        await asyncio.sleep(30)

        # Stop
        await monitor.stop()

    except KeyboardInterrupt:
        logger.info("Test interrupted")
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_websocket())