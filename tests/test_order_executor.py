"""
Unit tests for Order Execution Engine
Tests slippage estimation, order placement, and fill confirmation
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.trading.order_executor import (
    SlippageEstimator,
    OrderPlacer,
    FillConfirmer,
    OrderExecutor,
    OrderBook,
    SlippageEstimate,
    OrderResult,
    FillStatus,
    OrderStatus
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_client():
    """Mock PolymarketClient"""
    client = Mock()
    client.get_orderbook = Mock()
    client.place_limit_order = Mock()
    client.place_market_order = Mock()
    client.get_orders = Mock()
    client.cancel_order = Mock()
    return client


@pytest.fixture
def sample_order_book():
    """Sample order book for testing"""
    return OrderBook(
        token_id="test_token_123",
        bids=[
            (Decimal("0.54"), Decimal("100")),
            (Decimal("0.53"), Decimal("200")),
            (Decimal("0.52"), Decimal("300")),
        ],
        asks=[
            (Decimal("0.56"), Decimal("150")),
            (Decimal("0.57"), Decimal("250")),
            (Decimal("0.58"), Decimal("350")),
        ],
        mid_price=Decimal("0.55"),
        spread=Decimal("0.02")
    )


# ==================== SlippageEstimator Tests ====================

class TestSlippageEstimator:
    """Test SlippageEstimator component"""

    @pytest.mark.asyncio
    async def test_fetch_order_book_success(self, mock_client):
        """Test successful order book fetch"""
        mock_client.get_orderbook.return_value = {
            'bids': [
                {'price': 0.54, 'size': 100},
                {'price': 0.53, 'size': 200}
            ],
            'asks': [
                {'price': 0.56, 'size': 150},
                {'price': 0.57, 'size': 250}
            ]
        }

        estimator = SlippageEstimator(mock_client)
        order_book = await estimator.fetch_order_book("test_token")

        assert order_book.token_id == "test_token"
        assert len(order_book.bids) == 2
        assert len(order_book.asks) == 2
        assert order_book.bids[0][0] == Decimal("0.54")
        assert order_book.asks[0][0] == Decimal("0.56")
        assert order_book.mid_price == Decimal("0.55")
        assert order_book.spread == Decimal("0.02")

    @pytest.mark.asyncio
    async def test_estimate_slippage_buy_order(self, mock_client, sample_order_book):
        """Test slippage estimation for BUY order"""
        estimator = SlippageEstimator(mock_client)

        # Small order - should fill at first ask level
        estimate = await estimator.estimate_slippage(
            size=Decimal("100"),
            side="BUY",
            order_book=sample_order_book
        )

        assert estimate.recommended is True
        assert estimate.depth_available == Decimal("100")
        assert estimate.vwap == Decimal("0.56")
        assert estimate.slippage_pct == Decimal("0.56") / Decimal("0.55") - Decimal("1")

    @pytest.mark.asyncio
    async def test_estimate_slippage_large_order(self, mock_client, sample_order_book):
        """Test slippage estimation for large order spanning multiple levels"""
        estimator = SlippageEstimator(mock_client)

        # Large order - should fill across multiple levels
        estimate = await estimator.estimate_slippage(
            size=Decimal("500"),
            side="BUY",
            order_book=sample_order_book
        )

        # Expected VWAP: (150*0.56 + 250*0.57 + 100*0.58) / 500
        expected_vwap = (Decimal("150") * Decimal("0.56") +
                        Decimal("250") * Decimal("0.57") +
                        Decimal("100") * Decimal("0.58")) / Decimal("500")

        assert estimate.depth_available == Decimal("500")
        assert estimate.vwap == expected_vwap

    @pytest.mark.asyncio
    async def test_estimate_slippage_insufficient_depth(self, mock_client, sample_order_book):
        """Test slippage estimation with insufficient order book depth"""
        estimator = SlippageEstimator(mock_client)

        # Order larger than available depth
        estimate = await estimator.estimate_slippage(
            size=Decimal("1000"),
            side="BUY",
            order_book=sample_order_book
        )

        assert estimate.recommended is False
        assert "Insufficient depth" in estimate.reason
        assert estimate.depth_available < Decimal("1000")

    @pytest.mark.asyncio
    async def test_estimate_slippage_high_slippage(self, mock_client):
        """Test slippage rejection when exceeding threshold"""
        estimator = SlippageEstimator(mock_client)
        estimator.max_slippage_limit = Decimal("0.02")  # 2% threshold

        # Order book with high slippage
        high_slippage_book = OrderBook(
            token_id="test",
            bids=[(Decimal("0.50"), Decimal("100"))],
            asks=[(Decimal("0.60"), Decimal("100"))],  # 10% above mid
            mid_price=Decimal("0.55"),
            spread=Decimal("0.10")
        )

        estimate = await estimator.estimate_slippage(
            size=Decimal("50"),
            side="BUY",
            order_book=high_slippage_book
        )

        assert estimate.recommended is False
        assert "too high" in estimate.reason.lower()

    @pytest.mark.asyncio
    async def test_estimate_slippage_sell_order(self, mock_client, sample_order_book):
        """Test slippage estimation for SELL order"""
        estimator = SlippageEstimator(mock_client)

        estimate = await estimator.estimate_slippage(
            size=Decimal("100"),
            side="SELL",
            order_book=sample_order_book
        )

        # Should use bids for sell
        assert estimate.vwap == Decimal("0.54")
        assert estimate.recommended is True


# ==================== OrderPlacer Tests ====================

class TestOrderPlacer:
    """Test OrderPlacer component"""

    @pytest.mark.asyncio
    async def test_place_limit_order_success(self, mock_client):
        """Test successful limit order placement"""
        mock_client.place_limit_order.return_value = {
            'orderID': 'order_123',
            'status': 'submitted'
        }

        placer = OrderPlacer(mock_client)
        result = await placer.place_limit_order(
            token_id="test_token",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )

        assert result.success is True
        assert result.order_id == "order_123"
        assert result.status == OrderStatus.SUBMITTED
        assert result.size == Decimal("100")
        mock_client.place_limit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_limit_order_retry(self, mock_client):
        """Test retry logic on transient failures"""
        # First two calls fail, third succeeds
        mock_client.place_limit_order.side_effect = [
            Exception("Connection timeout"),
            Exception("Rate limit"),
            {'orderID': 'order_123', 'status': 'submitted'}
        ]

        placer = OrderPlacer(mock_client)
        placer.initial_retry_delay = 0.01  # Fast retries for testing

        result = await placer.place_limit_order(
            token_id="test_token",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )

        assert result.success is True
        assert result.order_id == "order_123"
        assert mock_client.place_limit_order.call_count == 3

    @pytest.mark.asyncio
    async def test_place_limit_order_non_retryable_error(self, mock_client):
        """Test non-retryable error handling"""
        mock_client.place_limit_order.side_effect = Exception("Insufficient balance")

        placer = OrderPlacer(mock_client)

        result = await placer.place_limit_order(
            token_id="test_token",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )

        assert result.success is False
        assert "Insufficient balance" in result.error
        # Should not retry on non-retryable errors
        assert mock_client.place_limit_order.call_count == 1

    @pytest.mark.asyncio
    async def test_place_limit_order_max_retries_exceeded(self, mock_client):
        """Test failure after max retries"""
        mock_client.place_limit_order.side_effect = Exception("Connection error")

        placer = OrderPlacer(mock_client)
        placer.max_retries = 2
        placer.initial_retry_delay = 0.01

        result = await placer.place_limit_order(
            token_id="test_token",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )

        assert result.success is False
        assert result.status == OrderStatus.FAILED
        assert mock_client.place_limit_order.call_count == 2

    @pytest.mark.asyncio
    async def test_place_market_order_success(self, mock_client):
        """Test successful market order placement"""
        mock_client.place_market_order.return_value = {
            'orderID': 'market_order_456',
            'status': 'submitted'
        }

        placer = OrderPlacer(mock_client)
        result = await placer.place_market_order(
            token_id="test_token",
            side="SELL",
            amount=Decimal("500"),
            order_type="FOK"
        )

        assert result.success is True
        assert result.order_id == "market_order_456"
        mock_client.place_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_client):
        """Test order cancellation"""
        mock_client.cancel_order.return_value = {'success': True}

        placer = OrderPlacer(mock_client)
        success = await placer.cancel_order("order_123")

        assert success is True
        mock_client.cancel_order.assert_called_once_with("order_123")

    @pytest.mark.asyncio
    async def test_cancel_order_failure(self, mock_client):
        """Test order cancellation failure"""
        mock_client.cancel_order.side_effect = Exception("Order not found")

        placer = OrderPlacer(mock_client)
        success = await placer.cancel_order("order_123")

        assert success is False


# ==================== FillConfirmer Tests ====================

class TestFillConfirmer:
    """Test FillConfirmer component"""

    @pytest.mark.asyncio
    async def test_wait_for_fill_immediate(self, mock_client):
        """Test immediate fill confirmation"""
        mock_client.get_orders.return_value = []  # Order not in open orders = filled

        confirmer = FillConfirmer(mock_client)
        confirmer.poll_interval = 0.01  # Fast polling for testing

        fill_status = await confirmer.wait_for_fill("order_123", timeout=1)

        assert fill_status.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_wait_for_fill_partial_accepted(self, mock_client):
        """Test partial fill acceptance (>80%)"""
        # Mock partially filled order
        mock_client.get_orders.return_value = [{
            'id': 'order_123',
            'size': 100,
            'sizeFilled': 85,  # 85% filled
            'price': 0.55
        }]

        confirmer = FillConfirmer(mock_client)
        confirmer.poll_interval = 0.01

        fill_status = await confirmer.wait_for_fill("order_123", timeout=1)

        assert fill_status.status == OrderStatus.PARTIALLY_FILLED
        assert fill_status.filled_size == Decimal("85")

    @pytest.mark.asyncio
    async def test_wait_for_fill_timeout(self, mock_client):
        """Test timeout when order doesn't fill"""
        # Mock unfilled order
        mock_client.get_orders.return_value = [{
            'id': 'order_123',
            'size': 100,
            'sizeFilled': 0,
            'price': 0.55
        }]

        confirmer = FillConfirmer(mock_client)
        confirmer.poll_interval = 0.1
        confirmer.default_timeout = 0.2  # Short timeout for testing

        fill_status = await confirmer.wait_for_fill("order_123")

        assert fill_status.status == OrderStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_get_fill_status_filled(self, mock_client):
        """Test getting fill status for filled order"""
        mock_client.get_orders.return_value = []  # Not in open orders

        confirmer = FillConfirmer(mock_client)
        fill_status = await confirmer.get_fill_status("order_123")

        assert fill_status.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_fill_status_partial(self, mock_client):
        """Test getting fill status for partially filled order"""
        mock_client.get_orders.return_value = [{
            'id': 'order_123',
            'size': 100,
            'sizeFilled': 50,
            'price': 0.55
        }]

        confirmer = FillConfirmer(mock_client)
        fill_status = await confirmer.get_fill_status("order_123")

        assert fill_status.status == OrderStatus.PARTIALLY_FILLED
        assert fill_status.filled_size == Decimal("50")
        assert fill_status.remaining_size == Decimal("50")

    @pytest.mark.asyncio
    async def test_get_fill_status_submitted(self, mock_client):
        """Test getting fill status for submitted but unfilled order"""
        mock_client.get_orders.return_value = [{
            'id': 'order_123',
            'size': 100,
            'sizeFilled': 0,
            'price': 0.55
        }]

        confirmer = FillConfirmer(mock_client)
        fill_status = await confirmer.get_fill_status("order_123")

        assert fill_status.status == OrderStatus.SUBMITTED
        assert fill_status.filled_size == Decimal("0")


# ==================== OrderExecutor Integration Tests ====================

class TestOrderExecutor:
    """Test OrderExecutor integration"""

    @pytest.mark.asyncio
    async def test_execute_trade_with_slippage_check_success(self, mock_client):
        """Test successful trade execution with slippage check"""
        # Mock order book
        mock_client.get_orderbook.return_value = {
            'bids': [{'price': 0.54, 'size': 100}],
            'asks': [{'price': 0.56, 'size': 200}]
        }

        # Mock order placement
        mock_client.place_limit_order.return_value = {
            'orderID': 'order_789',
            'status': 'submitted'
        }

        # Mock fill
        mock_client.get_orders.return_value = []  # Filled

        executor = OrderExecutor(mock_client)

        result = await executor.execute_trade(
            token_id="test_token",
            side="BUY",
            size=Decimal("50"),
            price=Decimal("0.56"),
            check_slippage=True,
            wait_for_fill=True,
            fill_timeout=1
        )

        assert result.success is True
        assert result.order_id == "order_789"
        assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_execute_trade_slippage_too_high(self, mock_client):
        """Test trade rejection due to high slippage"""
        # Mock order book with high slippage
        mock_client.get_orderbook.return_value = {
            'bids': [{'price': 0.50, 'size': 100}],
            'asks': [{'price': 0.70, 'size': 100}]  # 20% slippage
        }

        executor = OrderExecutor(mock_client)

        result = await executor.execute_trade(
            token_id="test_token",
            side="BUY",
            size=Decimal("50"),
            price=Decimal("0.70"),
            check_slippage=True
        )

        assert result.success is False
        assert "slippage" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_trade_without_slippage_check(self, mock_client):
        """Test trade execution without slippage check"""
        mock_client.place_limit_order.return_value = {
            'orderID': 'order_999',
            'status': 'submitted'
        }
        mock_client.get_orders.return_value = []

        executor = OrderExecutor(mock_client)

        result = await executor.execute_trade(
            token_id="test_token",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55"),
            check_slippage=False,
            wait_for_fill=True,
            fill_timeout=1
        )

        assert result.success is True
        # Should not call get_orderbook when skipping slippage check
        mock_client.get_orderbook.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_trade_market_order(self, mock_client):
        """Test market order execution"""
        mock_client.place_market_order.return_value = {
            'orderID': 'market_123',
            'status': 'submitted'
        }
        mock_client.get_orders.return_value = []

        executor = OrderExecutor(mock_client)

        result = await executor.execute_trade(
            token_id="test_token",
            side="SELL",
            size=Decimal("75"),
            price=None,  # Market order
            check_slippage=False,
            wait_for_fill=True,
            fill_timeout=1
        )

        assert result.success is True
        mock_client.place_market_order.assert_called_once()


# ==================== Performance Tests ====================

class TestPerformance:
    """Test performance and latency"""

    @pytest.mark.asyncio
    async def test_slippage_estimation_speed(self, mock_client, sample_order_book):
        """Test slippage estimation completes within target time"""
        estimator = SlippageEstimator(mock_client)

        start = datetime.now()
        estimate = await estimator.estimate_slippage(
            size=Decimal("100"),
            side="BUY",
            order_book=sample_order_book
        )
        duration = (datetime.now() - start).total_seconds() * 1000

        # Target: <200ms for slippage estimation
        assert duration < 200
        assert estimate is not None

    @pytest.mark.asyncio
    async def test_order_placement_speed(self, mock_client):
        """Test order placement completes within target time"""
        mock_client.place_limit_order.return_value = {
            'orderID': 'speed_test',
            'status': 'submitted'
        }

        placer = OrderPlacer(mock_client)

        start = datetime.now()
        result = await placer.place_limit_order(
            token_id="test",
            side="BUY",
            size=Decimal("100"),
            price=Decimal("0.55")
        )
        duration = (datetime.now() - start).total_seconds() * 1000

        # Target: <500ms for order placement
        assert duration < 500
        assert result.success is True


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_empty_order_book(self, mock_client):
        """Test handling of empty order book"""
        mock_client.get_orderbook.return_value = {
            'bids': [],
            'asks': []
        }

        estimator = SlippageEstimator(mock_client)
        order_book = await estimator.fetch_order_book("test_token")

        estimate = await estimator.estimate_slippage(
            size=Decimal("100"),
            side="BUY",
            order_book=order_book
        )

        assert estimate.recommended is False
        assert "No liquidity" in estimate.reason

    @pytest.mark.asyncio
    async def test_zero_size_order(self, mock_client, sample_order_book):
        """Test handling of zero-size order"""
        estimator = SlippageEstimator(mock_client)

        estimate = await estimator.estimate_slippage(
            size=Decimal("0"),
            side="BUY",
            order_book=sample_order_book
        )

        assert estimate.depth_available == Decimal("0")

    @pytest.mark.asyncio
    async def test_negative_price_in_order_book(self, mock_client):
        """Test handling of invalid order book data"""
        mock_client.get_orderbook.return_value = {
            'bids': [{'price': -0.10, 'size': 100}],  # Invalid negative price
            'asks': [{'price': 0.56, 'size': 100}]
        }

        estimator = SlippageEstimator(mock_client)

        # Should handle gracefully
        order_book = await estimator.fetch_order_book("test_token")
        assert order_book.bids[0][0] == Decimal("-0.10")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
