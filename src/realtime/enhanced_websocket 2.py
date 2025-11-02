"""
Enhanced WebSocket Client for Polymarket
Features:
- Message deduplication to prevent duplicate processing
- Per-whale subscription management
- Connection pooling for multiple markets
- REST API fallback on WebSocket disconnect
- WhaleTradeDetector for intelligent whale identification
- Improved reconnection logic with exponential backoff
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Any, Callable, Optional, Set, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import aiohttp
from decimal import Decimal

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
    event_id: Optional[str] = None  # For deduplication


@dataclass
class WhaleTradeSignal:
    """Whale trade detection signal"""
    whale_address: str
    market_id: str
    token_id: str
    side: str  # BUY or SELL
    size: Decimal
    price: Decimal
    amount: Decimal
    timestamp: int
    confidence_score: float  # 0-1, how confident we are this is a significant whale trade
    trade_velocity: float  # Trades per minute
    size_percentile: float  # Size vs whale's average
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageDeduplicator:
    """
    Prevent duplicate message processing using a time-windowed cache
    Target: <1ms lookup time, maintain last 60 seconds of events
    """

    def __init__(self, window_seconds: int = 60, max_size: int = 10000):
        self.window_seconds = window_seconds
        self.max_size = max_size
        self.seen_messages: Dict[str, datetime] = {}
        self.message_queue: deque = deque(maxlen=max_size)
        self._lock = asyncio.Lock()

    def _generate_event_id(self, event: StreamEvent) -> str:
        """Generate unique ID for an event"""
        # Use combination of timestamp, market, user, and data hash
        data_str = json.dumps(event.data, sort_keys=True)
        return f"{event.timestamp}:{event.market_id}:{event.user_address}:{hash(data_str)}"

    async def is_duplicate(self, event: StreamEvent) -> bool:
        """Check if event is a duplicate"""
        event_id = event.event_id or self._generate_event_id(event)

        async with self._lock:
            now = datetime.now()

            # Clean old entries
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.seen_messages = {
                eid: ts for eid, ts in self.seen_messages.items()
                if ts > cutoff
            }

            # Check if we've seen this event
            if event_id in self.seen_messages:
                logger.debug(f"Duplicate event detected: {event_id}")
                return True

            # Mark as seen
            self.seen_messages[event_id] = now
            self.message_queue.append((event_id, now))

            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics"""
        return {
            "cached_events": len(self.seen_messages),
            "window_seconds": self.window_seconds,
            "max_size": self.max_size
        }


class WhaleTradeDetector:
    """
    Intelligent whale trade detection with behavioral analysis
    Target: <500ms detection time, >95% accuracy
    """

    def __init__(self, min_trade_size: Decimal = Decimal("100")):
        self.min_trade_size = min_trade_size

        # Track whale trading patterns
        self.whale_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_trades": 0,
            "total_volume": Decimal("0"),
            "avg_trade_size": Decimal("0"),
            "last_trades": deque(maxlen=100),  # Last 100 trades
            "markets_traded": set(),
            "last_trade_time": None
        })

        # Track per-market statistics
        self.market_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_volume": Decimal("0"),
            "total_trades": 0,
            "avg_trade_size": Decimal("0")
        })

    async def analyze_trade(
        self,
        user_address: str,
        market_id: str,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal,
        timestamp: int
    ) -> Optional[WhaleTradeSignal]:
        """
        Analyze a trade and determine if it's a significant whale trade

        Returns WhaleTradeSignal if significant, None otherwise
        """
        amount = size * price

        # Basic filter: must meet minimum size
        if amount < self.min_trade_size:
            return None

        # Update statistics
        whale = self.whale_stats[user_address]
        market = self.market_stats[market_id]

        # Calculate trade velocity (trades per minute)
        trade_velocity = 0.0
        if whale["last_trade_time"]:
            time_diff = timestamp - whale["last_trade_time"]
            if time_diff > 0:
                # Recent trades in last minute
                recent_trades = sum(
                    1 for t in whale["last_trades"]
                    if timestamp - t["timestamp"] < 60
                )
                trade_velocity = recent_trades / 1.0  # trades per minute

        # Calculate size percentile vs whale's history
        size_percentile = 0.5  # default
        if whale["avg_trade_size"] > 0:
            size_percentile = float(amount / whale["avg_trade_size"])

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            amount=amount,
            size_percentile=size_percentile,
            trade_velocity=trade_velocity,
            whale_total_trades=whale["total_trades"],
            is_new_market=market_id not in whale["markets_traded"]
        )

        # Update whale stats
        whale["total_trades"] += 1
        whale["total_volume"] += amount
        whale["avg_trade_size"] = whale["total_volume"] / whale["total_trades"]
        whale["last_trades"].append({
            "timestamp": timestamp,
            "amount": amount,
            "market_id": market_id
        })
        whale["markets_traded"].add(market_id)
        whale["last_trade_time"] = timestamp

        # Update market stats
        market["total_trades"] += 1
        market["total_volume"] += amount
        market["avg_trade_size"] = market["total_volume"] / market["total_trades"]

        # Generate signal if confidence is high enough
        if confidence_score >= 0.3:  # Threshold for significance
            return WhaleTradeSignal(
                whale_address=user_address,
                market_id=market_id,
                token_id=token_id,
                side=side,
                size=size,
                price=price,
                amount=amount,
                timestamp=timestamp,
                confidence_score=confidence_score,
                trade_velocity=trade_velocity,
                size_percentile=size_percentile,
                metadata={
                    "whale_total_trades": whale["total_trades"],
                    "whale_avg_size": float(whale["avg_trade_size"]),
                    "market_avg_size": float(market["avg_trade_size"])
                }
            )

        return None

    def _calculate_confidence(
        self,
        amount: Decimal,
        size_percentile: float,
        trade_velocity: float,
        whale_total_trades: int,
        is_new_market: bool
    ) -> float:
        """
        Calculate confidence score for whale trade significance

        Factors:
        - Absolute trade size
        - Size vs whale's historical average
        - Trading velocity (rapid trades = higher confidence)
        - Whale's track record
        - New market entry
        """
        confidence = 0.0

        # Factor 1: Absolute size (0-0.3)
        if amount >= Decimal("1000"):
            confidence += 0.3
        elif amount >= Decimal("500"):
            confidence += 0.2
        elif amount >= Decimal("100"):
            confidence += 0.1

        # Factor 2: Size percentile vs average (0-0.3)
        if size_percentile >= 2.0:  # 2x average or more
            confidence += 0.3
        elif size_percentile >= 1.5:
            confidence += 0.2
        elif size_percentile >= 1.0:
            confidence += 0.1

        # Factor 3: Trade velocity (0-0.2)
        if trade_velocity >= 5:  # 5+ trades per minute
            confidence += 0.2
        elif trade_velocity >= 2:
            confidence += 0.1

        # Factor 4: Whale track record (0-0.1)
        if whale_total_trades >= 100:
            confidence += 0.1
        elif whale_total_trades >= 50:
            confidence += 0.05

        # Factor 5: New market entry (0-0.1)
        if is_new_market:
            confidence += 0.1

        return min(confidence, 1.0)

    def get_whale_stats(self, whale_address: str) -> Dict[str, Any]:
        """Get statistics for a specific whale"""
        stats = self.whale_stats.get(whale_address)
        if not stats:
            return {}

        return {
            "total_trades": stats["total_trades"],
            "total_volume": float(stats["total_volume"]),
            "avg_trade_size": float(stats["avg_trade_size"]),
            "markets_traded": len(stats["markets_traded"]),
            "last_trade_time": stats["last_trade_time"]
        }


class RESTFallbackHandler:
    """
    Fetch data from REST API when WebSocket is unavailable
    Target: <2s response time, automatic failover
    """

    POLYMARKET_API_BASE = "https://clob.polymarket.com"
    GAMMA_API_BASE = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_fetch_times: Dict[str, datetime] = {}
        self.min_fetch_interval = 1  # seconds between fetches for same resource

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def fetch_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Fetch orderbook from REST API"""
        await self._ensure_session()

        # Rate limiting
        last_fetch = self.last_fetch_times.get(f"orderbook:{token_id}")
        if last_fetch and (datetime.now() - last_fetch).total_seconds() < self.min_fetch_interval:
            logger.debug(f"Skipping orderbook fetch for {token_id} (rate limit)")
            return None

        try:
            url = f"{self.POLYMARKET_API_BASE}/book?token_id={token_id}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    data = await response.json()
                    self.last_fetch_times[f"orderbook:{token_id}"] = datetime.now()
                    logger.info(f"Fetched orderbook from REST API for {token_id}")
                    return data
                else:
                    logger.warning(f"REST API returned {response.status} for orderbook")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching orderbook for {token_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching orderbook from REST: {e}")
            return None

    async def fetch_recent_trades(
        self,
        market_id: Optional[str] = None,
        user_address: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch recent trades from REST API"""
        await self._ensure_session()

        try:
            # Build query parameters
            params = {"limit": limit}
            if market_id:
                params["market"] = market_id
            if user_address:
                params["maker"] = user_address

            url = f"{self.POLYMARKET_API_BASE}/trades"
            async with self.session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    trades = await response.json()
                    logger.info(f"Fetched {len(trades)} trades from REST API")
                    return trades
                else:
                    logger.warning(f"REST API returned {response.status} for trades")
                    return []

        except Exception as e:
            logger.error(f"Error fetching trades from REST: {e}")
            return []

    async def fetch_market_data(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """Fetch market data from Gamma API"""
        await self._ensure_session()

        try:
            url = f"{self.GAMMA_API_BASE}/markets/{condition_id}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Fetched market data for {condition_id}")
                    return data
                else:
                    return None

        except Exception as e:
            logger.error(f"Error fetching market data from REST: {e}")
            return None

    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


class ConnectionPool:
    """
    Manage multiple WebSocket connections efficiently
    Supports per-whale and per-market subscriptions
    """

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # connection_id -> set of subscriptions
        self.connection_health: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_connection(
        self,
        endpoint_url: str,
        connection_id: Optional[str] = None
    ) -> Optional[websockets.WebSocketClientProtocol]:
        """Get or create a connection to endpoint"""
        async with self._lock:
            conn_id = connection_id or f"conn_{len(self.connections)}"

            # Check if connection exists and is healthy
            if conn_id in self.connections:
                ws = self.connections[conn_id]
                if not ws.closed:
                    return ws
                else:
                    # Remove dead connection
                    del self.connections[conn_id]
                    if conn_id in self.connection_health:
                        del self.connection_health[conn_id]

            # Create new connection if under limit
            if len(self.connections) < self.max_connections:
                try:
                    ws = await websockets.connect(endpoint_url)
                    self.connections[conn_id] = ws
                    self.connection_health[conn_id] = {
                        "connected_at": datetime.now(),
                        "messages_received": 0,
                        "last_message_at": None,
                        "endpoint": endpoint_url
                    }
                    logger.info(f"Created new connection {conn_id} to {endpoint_url}")
                    return ws
                except Exception as e:
                    logger.error(f"Failed to create connection {conn_id}: {e}")
                    return None
            else:
                logger.warning(f"Connection pool full ({self.max_connections})")
                return None

    async def subscribe(
        self,
        connection_id: str,
        subscription: Dict[str, Any]
    ):
        """Send subscription message to a connection"""
        if connection_id in self.connections:
            ws = self.connections[connection_id]
            try:
                await ws.send(json.dumps(subscription))
                sub_key = f"{subscription.get('channel')}:{subscription.get('market', 'all')}"
                self.subscriptions[connection_id].add(sub_key)
                logger.debug(f"Subscribed {connection_id} to {sub_key}")
            except Exception as e:
                logger.error(f"Failed to send subscription to {connection_id}: {e}")

    async def close_connection(self, connection_id: str):
        """Close a specific connection"""
        if connection_id in self.connections:
            ws = self.connections[connection_id]
            if not ws.closed:
                await ws.close()
            del self.connections[connection_id]
            if connection_id in self.subscriptions:
                del self.subscriptions[connection_id]
            if connection_id in self.connection_health:
                del self.connection_health[connection_id]
            logger.info(f"Closed connection {connection_id}")

    async def close_all(self):
        """Close all connections"""
        conn_ids = list(self.connections.keys())
        for conn_id in conn_ids:
            await self.close_connection(conn_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            "active_connections": len(self.connections),
            "max_connections": self.max_connections,
            "total_subscriptions": sum(len(subs) for subs in self.subscriptions.values()),
            "connections": {
                conn_id: {
                    "subscriptions": len(self.subscriptions.get(conn_id, set())),
                    "health": self.connection_health.get(conn_id, {})
                }
                for conn_id in self.connections
            }
        }


class EnhancedWebSocketClient:
    """
    Enhanced WebSocket client with all improvements
    - Message deduplication
    - Whale trade detection
    - Connection pooling
    - REST API fallback
    - Improved reconnection logic
    """

    ENDPOINTS = {
        "orderbook": "wss://ws-subscriptions-clob.polymarket.com",
        "markets": "wss://ws-markets.polymarket.com",
    }

    def __init__(
        self,
        whale_addresses: Set[str] = None,
        enable_deduplication: bool = True,
        enable_whale_detection: bool = True,
        enable_rest_fallback: bool = True
    ):
        self.whale_addresses = {addr.lower() for addr in (whale_addresses or set())}

        # Components
        self.deduplicator = MessageDeduplicator() if enable_deduplication else None
        self.whale_detector = WhaleTradeDetector() if enable_whale_detection else None
        self.rest_fallback = RESTFallbackHandler() if enable_rest_fallback else None
        self.connection_pool = ConnectionPool(max_connections=5)

        # Event handlers
        self.handlers: Dict[EventType, List[Callable]] = defaultdict(list)

        # State
        self.running = False
        self.reconnect_attempts: Dict[str, int] = defaultdict(int)
        self.max_reconnect_attempts = 10
        self.base_reconnect_delay = 1  # seconds
        self.max_reconnect_delay = 300  # 5 minutes

        # Statistics
        self.stats = {
            "events_processed": 0,
            "duplicates_filtered": 0,
            "whale_trades_detected": 0,
            "rest_fallbacks": 0,
            "reconnections": 0
        }

    def add_whale(self, address: str):
        """Add whale address to monitor"""
        self.whale_addresses.add(address.lower())
        logger.info(f"Added whale: {address}")

    def remove_whale(self, address: str):
        """Remove whale from monitoring"""
        self.whale_addresses.discard(address.lower())
        logger.info(f"Removed whale: {address}")

    def register_handler(self, event_type: EventType, handler: Callable):
        """Register event handler"""
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}")

    async def _handle_event(self, event: StreamEvent):
        """Process and dispatch event"""
        # Deduplication check
        if self.deduplicator:
            if await self.deduplicator.is_duplicate(event):
                self.stats["duplicates_filtered"] += 1
                return

        # Whale detection
        if event.user_address and event.user_address.lower() in self.whale_addresses:
            # Check if it's a significant trade
            if self.whale_detector and event.event_type == EventType.ORDER_FILLED:
                try:
                    signal = await self.whale_detector.analyze_trade(
                        user_address=event.user_address,
                        market_id=event.market_id or "",
                        token_id=event.data.get("token_id", ""),
                        side=event.data.get("side", "BUY"),
                        size=Decimal(str(event.data.get("size", 0))),
                        price=Decimal(str(event.data.get("price", 0))),
                        timestamp=event.timestamp
                    )

                    if signal:
                        # Mark as whale trade
                        event.event_type = EventType.WHALE_TRADE
                        event.data["whale_signal"] = {
                            "confidence": signal.confidence_score,
                            "velocity": signal.trade_velocity,
                            "size_percentile": signal.size_percentile
                        }
                        self.stats["whale_trades_detected"] += 1
                        logger.info(
                            f"🐋 Whale trade detected: {signal.whale_address[:8]} "
                            f"${float(signal.amount):.2f} (confidence: {signal.confidence_score:.2f})"
                        )

                except Exception as e:
                    logger.error(f"Error in whale detection: {e}")

        # Dispatch to handlers
        if event.event_type in self.handlers:
            for handler in self.handlers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")

        self.stats["events_processed"] += 1

    def _parse_message(self, message: str, source: str) -> Optional[StreamEvent]:
        """Parse WebSocket message"""
        try:
            data = json.loads(message)

            # Parse based on source
            if source == "orderbook":
                return self._parse_orderbook_message(data)
            elif source == "markets":
                return self._parse_market_message(data)

            return None

        except Exception as e:
            logger.error(f"Error parsing message from {source}: {e}")
            return None

    def _parse_orderbook_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse orderbook message"""
        msg_type = data.get("type", "")

        if msg_type == "order":
            return StreamEvent(
                event_type=EventType.ORDER_PLACED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("user"),
                event_id=f"order:{data.get('order_id')}"
            )
        elif msg_type == "fill":
            return StreamEvent(
                event_type=EventType.ORDER_FILLED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("taker"),
                event_id=f"fill:{data.get('fill_id')}"
            )
        elif msg_type == "cancel":
            return StreamEvent(
                event_type=EventType.ORDER_CANCELLED,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("market"),
                user_address=data.get("user"),
                event_id=f"cancel:{data.get('order_id')}"
            )

        return None

    def _parse_market_message(self, data: Dict) -> Optional[StreamEvent]:
        """Parse market update message"""
        if "price" in data:
            return StreamEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=data.get("timestamp", int(datetime.now().timestamp())),
                data=data,
                market_id=data.get("marketId"),
                event_id=f"price:{data.get('marketId')}:{data.get('timestamp')}"
            )

        return StreamEvent(
            event_type=EventType.MARKET_UPDATE,
            timestamp=data.get("timestamp", int(datetime.now().timestamp())),
            data=data,
            market_id=data.get("marketId"),
            event_id=f"market:{data.get('marketId')}:{data.get('timestamp')}"
        )

    async def _connect_with_backoff(self, name: str, url: str):
        """Connect to endpoint with exponential backoff"""
        attempt = 0

        while self.running and attempt < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to {name} (attempt {attempt + 1}/{self.max_reconnect_attempts})")

                # Get connection from pool
                ws = await self.connection_pool.get_connection(url, connection_id=name)

                if ws is None:
                    raise Exception("Failed to get connection from pool")

                # Reset reconnect counter on success
                self.reconnect_attempts[name] = 0
                attempt = 0

                # Subscribe to events
                await self._subscribe_to_events(ws, name)

                # Handle messages
                async for message in ws:
                    if not self.running:
                        break

                    event = self._parse_message(message, name)
                    if event:
                        await self._handle_event(event)

                    # Update connection health
                    if name in self.connection_pool.connection_health:
                        health = self.connection_pool.connection_health[name]
                        health["messages_received"] += 1
                        health["last_message_at"] = datetime.now()

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Connection closed for {name}")
                attempt += 1
                self.stats["reconnections"] += 1

                # Exponential backoff
                delay = min(
                    self.base_reconnect_delay * (2 ** attempt),
                    self.max_reconnect_delay
                )
                logger.info(f"Reconnecting in {delay}s...")
                await asyncio.sleep(delay)

                # Try REST fallback while reconnecting
                if self.rest_fallback and name == "orderbook":
                    await self._activate_rest_fallback()

            except Exception as e:
                logger.error(f"Error in {name} connection: {e}")
                attempt += 1

                delay = min(
                    self.base_reconnect_delay * (2 ** attempt),
                    self.max_reconnect_delay
                )
                await asyncio.sleep(delay)

        logger.warning(f"Max reconnection attempts reached for {name}")

    async def _activate_rest_fallback(self):
        """Activate REST API fallback when WebSocket is down"""
        if not self.rest_fallback:
            return

        logger.info("Activating REST API fallback")
        self.stats["rest_fallbacks"] += 1

        try:
            # Fetch recent trades for monitored whales
            for whale_addr in list(self.whale_addresses)[:5]:  # Limit to 5 whales
                trades = await self.rest_fallback.fetch_recent_trades(
                    user_address=whale_addr,
                    limit=10
                )

                # Process trades as events
                for trade_data in trades:
                    event = StreamEvent(
                        event_type=EventType.ORDER_FILLED,
                        timestamp=trade_data.get("timestamp", int(datetime.now().timestamp())),
                        data=trade_data,
                        market_id=trade_data.get("market"),
                        user_address=trade_data.get("maker"),
                        event_id=f"rest_fill:{trade_data.get('id')}"
                    )
                    await self._handle_event(event)

        except Exception as e:
            logger.error(f"REST fallback error: {e}")

    async def _subscribe_to_events(self, websocket, endpoint_name: str):
        """Send subscription messages"""
        subscriptions = []

        if endpoint_name == "orderbook":
            subscriptions.append({
                "type": "subscribe",
                "channel": "orders",
                "markets": "all"
            })
            subscriptions.append({
                "type": "subscribe",
                "channel": "fills",
                "markets": "all"
            })
        elif endpoint_name == "markets":
            subscriptions.append({
                "type": "subscribe",
                "channel": "markets",
                "markets": "all"
            })

        for sub in subscriptions:
            await websocket.send(json.dumps(sub))
            logger.info(f"Sent subscription: {sub['channel']}")

    async def start(self):
        """Start WebSocket connections"""
        if self.running:
            logger.warning("Already running")
            return

        self.running = True
        logger.info("Starting Enhanced WebSocket Client...")

        # Create connection tasks
        tasks = []
        for name, url in self.ENDPOINTS.items():
            tasks.append(asyncio.create_task(self._connect_with_backoff(name, url)))

        # Run all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop WebSocket connections"""
        logger.info("Stopping Enhanced WebSocket Client...")
        self.running = False

        # Close all connections
        await self.connection_pool.close_all()

        # Close REST fallback session
        if self.rest_fallback:
            await self.rest_fallback.close()

        logger.info("Stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        stats = {
            "client": self.stats.copy(),
            "connection_pool": self.connection_pool.get_stats(),
            "monitored_whales": len(self.whale_addresses)
        }

        if self.deduplicator:
            stats["deduplicator"] = self.deduplicator.get_stats()

        return stats


async def test_enhanced_websocket():
    """Test enhanced WebSocket client"""
    # Test whale addresses
    whales = {
        "0x1234567890123456789012345678901234567890",
    }

    client = EnhancedWebSocketClient(
        whale_addresses=whales,
        enable_deduplication=True,
        enable_whale_detection=True,
        enable_rest_fallback=True
    )

    # Register handlers
    async def whale_trade_handler(event: StreamEvent):
        logger.info(f"🐋 WHALE TRADE: {event.data.get('whale_signal', {})}")

    async def order_handler(event: StreamEvent):
        logger.info(f"📝 Order: {event.event_type.value}")

    client.register_handler(EventType.WHALE_TRADE, whale_trade_handler)
    client.register_handler(EventType.ORDER_FILLED, order_handler)

    try:
        # Start client
        start_task = asyncio.create_task(client.start())

        # Run for 60 seconds
        await asyncio.sleep(60)

        # Print statistics
        stats = client.get_stats()
        logger.info(f"Statistics: {json.dumps(stats, indent=2, default=str)}")

        # Stop
        await client.stop()

    except KeyboardInterrupt:
        logger.info("Test interrupted")
        await client.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_enhanced_websocket())
