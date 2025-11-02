"""
Unit tests for Enhanced WebSocket Client
Tests all major components:
- MessageDeduplicator
- WhaleTradeDetector
- RESTFallbackHandler
- ConnectionPool
- EnhancedWebSocketClient
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import websockets

from src.realtime.enhanced_websocket import (
    MessageDeduplicator,
    WhaleTradeDetector,
    RESTFallbackHandler,
    ConnectionPool,
    EnhancedWebSocketClient,
    StreamEvent,
    EventType,
    WhaleTradeSignal
)


# ============================================================================
# MessageDeduplicator Tests
# ============================================================================

class TestMessageDeduplicator:
    """Test message deduplication functionality"""

    @pytest.mark.asyncio
    async def test_no_duplicate_on_first_message(self):
        """Test that first message is not marked as duplicate"""
        deduplicator = MessageDeduplicator(window_seconds=60)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_123"},
            market_id="market_1",
            user_address="0xabc"
        )

        is_dup = await deduplicator.is_duplicate(event)
        assert is_dup is False

    @pytest.mark.asyncio
    async def test_duplicate_detection_same_event(self):
        """Test that duplicate event is detected"""
        deduplicator = MessageDeduplicator(window_seconds=60)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_123"},
            market_id="market_1",
            user_address="0xabc",
            event_id="unique_123"
        )

        # First time - not duplicate
        is_dup1 = await deduplicator.is_duplicate(event)
        assert is_dup1 is False

        # Second time - duplicate
        is_dup2 = await deduplicator.is_duplicate(event)
        assert is_dup2 is True

    @pytest.mark.asyncio
    async def test_different_events_not_duplicate(self):
        """Test that different events are not marked as duplicates"""
        deduplicator = MessageDeduplicator(window_seconds=60)

        event1 = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_123"},
            event_id="event_1"
        )

        event2 = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_456"},
            event_id="event_2"
        )

        is_dup1 = await deduplicator.is_duplicate(event1)
        is_dup2 = await deduplicator.is_duplicate(event2)

        assert is_dup1 is False
        assert is_dup2 is False

    @pytest.mark.asyncio
    async def test_old_events_expire(self):
        """Test that events outside the window are expired"""
        deduplicator = MessageDeduplicator(window_seconds=1)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_123"},
            event_id="expire_test"
        )

        # First check
        is_dup1 = await deduplicator.is_duplicate(event)
        assert is_dup1 is False

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should not be duplicate after expiration
        is_dup2 = await deduplicator.is_duplicate(event)
        assert is_dup2 is False

    def test_deduplicator_stats(self):
        """Test statistics reporting"""
        deduplicator = MessageDeduplicator(window_seconds=60, max_size=100)
        stats = deduplicator.get_stats()

        assert "cached_events" in stats
        assert "window_seconds" in stats
        assert stats["window_seconds"] == 60
        assert stats["max_size"] == 100


# ============================================================================
# WhaleTradeDetector Tests
# ============================================================================

class TestWhaleTradeDetector:
    """Test whale trade detection and analysis"""

    @pytest.mark.asyncio
    async def test_small_trade_not_detected(self):
        """Test that trades below minimum size are not detected"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        signal = await detector.analyze_trade(
            user_address="0xwhale",
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("10"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp())
        )

        assert signal is None

    @pytest.mark.asyncio
    async def test_large_trade_detected(self):
        """Test that large trades are detected"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        signal = await detector.analyze_trade(
            user_address="0xwhale",
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("1000"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp())
        )

        assert signal is not None
        assert signal.whale_address == "0xwhale"
        assert signal.amount == Decimal("500")  # 1000 * 0.5
        assert signal.confidence_score > 0

    @pytest.mark.asyncio
    async def test_confidence_increases_with_size(self):
        """Test that confidence increases for larger trades"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        # Medium trade
        signal1 = await detector.analyze_trade(
            user_address="0xwhale",
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp())
        )

        # Large trade
        signal2 = await detector.analyze_trade(
            user_address="0xwhale",
            market_id="market_2",
            token_id="token_2",
            side="BUY",
            size=Decimal("5000"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp()) + 1
        )

        assert signal1 is not None
        assert signal2 is not None
        assert signal2.confidence_score > signal1.confidence_score

    @pytest.mark.asyncio
    async def test_whale_stats_tracking(self):
        """Test that whale statistics are tracked correctly"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        whale_addr = "0xwhale123"

        # Execute multiple trades
        for i in range(5):
            await detector.analyze_trade(
                user_address=whale_addr,
                market_id=f"market_{i}",
                token_id=f"token_{i}",
                side="BUY",
                size=Decimal("500"),
                price=Decimal("0.5"),
                timestamp=int(datetime.now().timestamp()) + i
            )

        stats = detector.get_whale_stats(whale_addr)

        assert stats["total_trades"] == 5
        assert stats["total_volume"] == 1250.0  # 5 * 500 * 0.5
        assert stats["avg_trade_size"] == 250.0
        assert stats["markets_traded"] == 5

    @pytest.mark.asyncio
    async def test_size_percentile_calculation(self):
        """Test size percentile vs whale's average"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        whale_addr = "0xwhale"

        # First trade - establishes baseline
        signal1 = await detector.analyze_trade(
            user_address=whale_addr,
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp())
        )

        # Second trade - 2x the size
        signal2 = await detector.analyze_trade(
            user_address=whale_addr,
            market_id="market_2",
            token_id="token_2",
            side="BUY",
            size=Decimal("2000"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp()) + 1
        )

        assert signal2 is not None
        assert signal2.size_percentile > 1.0  # Should be > 1x average

    @pytest.mark.asyncio
    async def test_new_market_boost(self):
        """Test that entering new markets increases confidence"""
        detector = WhaleTradeDetector(min_trade_size=Decimal("100"))

        whale_addr = "0xwhale"

        # Trade in market_1
        signal1 = await detector.analyze_trade(
            user_address=whale_addr,
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp())
        )

        # Another trade in market_1 (not new)
        signal2 = await detector.analyze_trade(
            user_address=whale_addr,
            market_id="market_1",
            token_id="token_1",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp()) + 1
        )

        # Trade in market_2 (new market)
        signal3 = await detector.analyze_trade(
            user_address=whale_addr,
            market_id="market_2",
            token_id="token_2",
            side="BUY",
            size=Decimal("500"),
            price=Decimal("0.5"),
            timestamp=int(datetime.now().timestamp()) + 2
        )

        # New market trade should have higher confidence
        assert signal3.confidence_score > signal2.confidence_score


# ============================================================================
# RESTFallbackHandler Tests
# ============================================================================

class TestRESTFallbackHandler:
    """Test REST API fallback functionality"""

    @pytest.mark.asyncio
    async def test_fetch_orderbook_success(self):
        """Test successful orderbook fetch"""
        handler = RESTFallbackHandler()

        mock_response = {
            "bids": [{"price": "0.54", "size": "100"}],
            "asks": [{"price": "0.56", "size": "150"}]
        }

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Setup mock
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value = mock_resp

            result = await handler.fetch_orderbook("test_token")

            assert result is not None
            assert "bids" in result
            assert "asks" in result

        await handler.close()

    @pytest.mark.asyncio
    async def test_fetch_orderbook_error(self):
        """Test orderbook fetch with error response"""
        handler = RESTFallbackHandler()

        with patch("aiohttp.ClientSession.get") as mock_get:
            # Setup mock with error status
            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_get.return_value.__aenter__.return_value = mock_resp

            result = await handler.fetch_orderbook("test_token")

            assert result is None

        await handler.close()

    @pytest.mark.asyncio
    async def test_fetch_orderbook_rate_limiting(self):
        """Test that rate limiting prevents too-frequent requests"""
        handler = RESTFallbackHandler()

        mock_response = {"bids": [], "asks": []}

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aenter__.return_value = mock_resp

            # First fetch
            result1 = await handler.fetch_orderbook("test_token")
            assert result1 is not None

            # Immediate second fetch (should be rate limited)
            result2 = await handler.fetch_orderbook("test_token")
            assert result2 is None  # Rate limited

        await handler.close()

    @pytest.mark.asyncio
    async def test_fetch_recent_trades(self):
        """Test fetching recent trades"""
        handler = RESTFallbackHandler()

        mock_trades = [
            {"id": "trade_1", "size": "100", "price": "0.5"},
            {"id": "trade_2", "size": "200", "price": "0.55"}
        ]

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_trades)
            mock_get.return_value.__aenter__.return_value = mock_resp

            trades = await handler.fetch_recent_trades(market_id="market_1", limit=10)

            assert len(trades) == 2
            assert trades[0]["id"] == "trade_1"

        await handler.close()

    @pytest.mark.asyncio
    async def test_fetch_market_data(self):
        """Test fetching market data"""
        handler = RESTFallbackHandler()

        mock_market = {
            "condition_id": "0x123",
            "question": "Test market?",
            "yes_price": "0.55"
        }

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_market)
            mock_get.return_value.__aenter__.return_value = mock_resp

            market = await handler.fetch_market_data("0x123")

            assert market is not None
            assert market["condition_id"] == "0x123"

        await handler.close()


# ============================================================================
# ConnectionPool Tests
# ============================================================================

class TestConnectionPool:
    """Test connection pool management"""

    @pytest.mark.asyncio
    async def test_create_connection(self):
        """Test creating a new connection"""
        pool = ConnectionPool(max_connections=5)

        with patch("websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.closed = False
            mock_connect.return_value = mock_ws

            conn = await pool.get_connection("wss://test.com", "test_conn")

            assert conn is not None
            assert "test_conn" in pool.connections

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_reuse_existing_connection(self):
        """Test that existing healthy connection is reused"""
        pool = ConnectionPool(max_connections=5)

        with patch("websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.closed = False
            mock_connect.return_value = mock_ws

            # First call creates connection
            conn1 = await pool.get_connection("wss://test.com", "test_conn")

            # Second call should reuse
            conn2 = await pool.get_connection("wss://test.com", "test_conn")

            assert conn1 is conn2
            assert mock_connect.call_count == 1  # Only called once

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_max_connections_limit(self):
        """Test that connection pool respects max limit"""
        pool = ConnectionPool(max_connections=2)

        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value = AsyncMock(closed=False)

            # Create 2 connections (at limit)
            await pool.get_connection("wss://test.com", "conn_1")
            await pool.get_connection("wss://test.com", "conn_2")

            # Try to create 3rd (should fail)
            conn3 = await pool.get_connection("wss://test.com", "conn_3")

            assert conn3 is None
            assert len(pool.connections) == 2

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """Test closing a specific connection"""
        pool = ConnectionPool(max_connections=5)

        with patch("websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.closed = False
            mock_connect.return_value = mock_ws

            await pool.get_connection("wss://test.com", "test_conn")
            assert "test_conn" in pool.connections

            await pool.close_connection("test_conn")
            assert "test_conn" not in pool.connections

    @pytest.mark.asyncio
    async def test_connection_pool_stats(self):
        """Test connection pool statistics"""
        pool = ConnectionPool(max_connections=5)

        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value = AsyncMock(closed=False)

            await pool.get_connection("wss://test.com", "conn_1")
            await pool.get_connection("wss://test.com", "conn_2")

            stats = pool.get_stats()

            assert stats["active_connections"] == 2
            assert stats["max_connections"] == 5
            assert "connections" in stats

        await pool.close_all()


# ============================================================================
# EnhancedWebSocketClient Tests
# ============================================================================

class TestEnhancedWebSocketClient:
    """Test enhanced WebSocket client integration"""

    def test_client_initialization(self):
        """Test client initializes with correct components"""
        whales = {"0xwhale1", "0xwhale2"}
        client = EnhancedWebSocketClient(
            whale_addresses=whales,
            enable_deduplication=True,
            enable_whale_detection=True,
            enable_rest_fallback=True
        )

        assert len(client.whale_addresses) == 2
        assert client.deduplicator is not None
        assert client.whale_detector is not None
        assert client.rest_fallback is not None
        assert client.connection_pool is not None

    def test_client_without_optional_features(self):
        """Test client initialization without optional features"""
        client = EnhancedWebSocketClient(
            enable_deduplication=False,
            enable_whale_detection=False,
            enable_rest_fallback=False
        )

        assert client.deduplicator is None
        assert client.whale_detector is None
        assert client.rest_fallback is None

    def test_add_remove_whale(self):
        """Test adding and removing whale addresses"""
        client = EnhancedWebSocketClient()

        client.add_whale("0xWhale1")  # Mixed case
        assert "0xwhale1" in client.whale_addresses  # Should be lowercase

        client.remove_whale("0xWhale1")
        assert "0xwhale1" not in client.whale_addresses

    def test_register_handler(self):
        """Test registering event handlers"""
        client = EnhancedWebSocketClient()

        async def test_handler(event):
            pass

        client.register_handler(EventType.WHALE_TRADE, test_handler)

        assert len(client.handlers[EventType.WHALE_TRADE]) == 1

    @pytest.mark.asyncio
    async def test_event_handling_with_deduplication(self):
        """Test that duplicate events are filtered"""
        client = EnhancedWebSocketClient(enable_deduplication=True)

        handler_calls = []

        async def test_handler(event):
            handler_calls.append(event)

        client.register_handler(EventType.ORDER_FILLED, test_handler)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test_123"},
            event_id="unique_event"
        )

        # First event - should be handled
        await client._handle_event(event)
        assert len(handler_calls) == 1

        # Duplicate event - should be filtered
        await client._handle_event(event)
        assert len(handler_calls) == 1  # Still 1, not 2

        assert client.stats["duplicates_filtered"] == 1

    @pytest.mark.asyncio
    async def test_whale_trade_detection_integration(self):
        """Test whale trade detection in event handling"""
        whales = {"0xwhale123"}
        client = EnhancedWebSocketClient(
            whale_addresses=whales,
            enable_whale_detection=True
        )

        whale_trades = []

        async def whale_handler(event):
            whale_trades.append(event)

        client.register_handler(EventType.WHALE_TRADE, whale_handler)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={
                "order_id": "test_123",
                "token_id": "token_1",
                "side": "BUY",
                "size": "1000",
                "price": "0.5"
            },
            market_id="market_1",
            user_address="0xwhale123"
        )

        await client._handle_event(event)

        # Should detect whale trade
        assert len(whale_trades) > 0
        assert client.stats["whale_trades_detected"] > 0

    def test_parse_orderbook_message(self):
        """Test parsing orderbook messages"""
        client = EnhancedWebSocketClient()

        message = json.dumps({
            "type": "fill",
            "fill_id": "fill_123",
            "market": "market_1",
            "taker": "0xuser",
            "size": "100",
            "price": "0.5",
            "timestamp": 1234567890
        })

        event = client._parse_message(message, "orderbook")

        assert event is not None
        assert event.event_type == EventType.ORDER_FILLED
        assert event.market_id == "market_1"
        assert event.user_address == "0xuser"

    def test_parse_market_message(self):
        """Test parsing market update messages"""
        client = EnhancedWebSocketClient()

        message = json.dumps({
            "marketId": "market_1",
            "price": "0.55",
            "timestamp": 1234567890
        })

        event = client._parse_message(message, "markets")

        assert event is not None
        assert event.event_type == EventType.PRICE_UPDATE
        assert event.market_id == "market_1"

    def test_client_stats(self):
        """Test client statistics reporting"""
        client = EnhancedWebSocketClient(
            enable_deduplication=True,
            enable_whale_detection=True
        )

        stats = client.get_stats()

        assert "client" in stats
        assert "connection_pool" in stats
        assert "monitored_whales" in stats
        assert "deduplicator" in stats
        assert stats["monitored_whales"] == 0

    @pytest.mark.asyncio
    async def test_handler_error_handling(self):
        """Test that handler errors don't crash the system"""
        client = EnhancedWebSocketClient()

        async def failing_handler(event):
            raise Exception("Handler error")

        async def good_handler(event):
            pass

        client.register_handler(EventType.ORDER_FILLED, failing_handler)
        client.register_handler(EventType.ORDER_FILLED, good_handler)

        event = StreamEvent(
            event_type=EventType.ORDER_FILLED,
            timestamp=int(datetime.now().timestamp()),
            data={"order_id": "test"},
            event_id="test_error"
        )

        # Should not raise exception
        await client._handle_event(event)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_complete_whale_trade_flow(self):
        """Test complete flow from WebSocket message to whale trade detection"""
        whales = {"0xwhale123"}
        client = EnhancedWebSocketClient(
            whale_addresses=whales,
            enable_deduplication=True,
            enable_whale_detection=True
        )

        detected_trades = []

        async def whale_trade_handler(event):
            detected_trades.append(event)

        client.register_handler(EventType.WHALE_TRADE, whale_trade_handler)

        # Simulate WebSocket message
        message = json.dumps({
            "type": "fill",
            "fill_id": "fill_large",
            "market": "market_1",
            "token_id": "token_1",
            "taker": "0xwhale123",
            "side": "BUY",
            "size": "2000",
            "price": "0.5",
            "timestamp": int(datetime.now().timestamp())
        })

        # Parse and handle
        event = client._parse_message(message, "orderbook")
        await client._handle_event(event)

        # Verify whale trade was detected
        assert len(detected_trades) > 0
        assert detected_trades[0].data["whale_signal"]["confidence"] > 0

    @pytest.mark.asyncio
    async def test_deduplication_in_whale_detection(self):
        """Test that duplicates are filtered before whale detection"""
        whales = {"0xwhale123"}
        client = EnhancedWebSocketClient(
            whale_addresses=whales,
            enable_deduplication=True,
            enable_whale_detection=True
        )

        detected_count = []

        async def whale_handler(event):
            detected_count.append(1)

        client.register_handler(EventType.WHALE_TRADE, whale_handler)

        message = json.dumps({
            "type": "fill",
            "fill_id": "fill_dup",
            "market": "market_1",
            "token_id": "token_1",
            "taker": "0xwhale123",
            "side": "BUY",
            "size": "2000",
            "price": "0.5",
            "timestamp": int(datetime.now().timestamp())
        })

        # Process same message twice
        event1 = client._parse_message(message, "orderbook")
        await client._handle_event(event1)

        event2 = client._parse_message(message, "orderbook")
        await client._handle_event(event2)

        # Should only detect once
        assert len(detected_count) <= 1
        assert client.stats["duplicates_filtered"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
