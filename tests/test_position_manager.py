"""
Unit tests for Position Management System
Tests position tracking, P&L calculation, and stop-loss/take-profit
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.trading.position_manager import (
    PositionTracker,
    PnLCalculator,
    StopLossTakeProfitManager,
    PnLMetrics,
    PortfolioPnL,
    ExitSignal,
    PositionStatus
)
from src.database.models import Base, Position


# ==================== Fixtures ====================

@pytest.fixture
def test_db_engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_client():
    """Mock PolymarketClient"""
    client = Mock()
    client.get_midpoint = Mock(return_value=0.60)
    return client


@pytest.fixture
def sample_position():
    """Sample position for testing"""
    return Position(
        position_id="test_pos_123",
        user_address="0x" + "1" * 40,
        market_id="market_456",
        condition_id="market_456",
        token_id="token_789",
        outcome="YES",
        size=Decimal("100"),
        avg_entry_price=Decimal("0.55"),
        current_price=Decimal("0.60"),
        initial_value=Decimal("55"),
        current_value=Decimal("60"),
        cash_pnl=Decimal("5"),
        percent_pnl=Decimal("9.09"),
        realized_pnl=Decimal("0"),
        stop_loss_price=Decimal("0.4675"),  # 15% below entry
        take_profit_price=Decimal("0.715"),  # 30% above entry
        source_whale="0x" + "whale" * 8,
        status=PositionStatus.OPEN.value
    )


# ==================== PositionTracker Tests ====================

class TestPositionTracker:
    """Test PositionTracker component"""

    def test_open_position_buy(self, test_db_engine):
        """Test opening a BUY position"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_123",
            token_id="token_yes",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.55"),
            source_whale="0xwhale123",
            market_title="Will Bitcoin reach $100k?"
        )

        assert position.position_id is not None
        assert position.size == Decimal("100")
        assert position.avg_entry_price == Decimal("0.55")
        assert position.initial_value == Decimal("55")
        assert position.status == PositionStatus.OPEN.value
        assert position.stop_loss_price == Decimal("0.55") * Decimal("0.85")  # 15% below
        assert position.take_profit_price == Decimal("0.55") * Decimal("1.30")  # 30% above

    def test_open_position_sell(self, test_db_engine):
        """Test opening a SELL position (short)"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_456",
            token_id="token_no",
            side="SELL",
            size=Decimal("50"),
            entry_price=Decimal("0.70"),
            source_whale="0xwhale456"
        )

        assert position.size == Decimal("50")
        assert position.avg_entry_price == Decimal("0.70")
        # For shorts, stop-loss is above entry
        assert position.stop_loss_price == Decimal("0.70") * Decimal("1.15")
        # Take-profit is below entry
        assert position.take_profit_price == Decimal("0.70") * Decimal("0.70")

    def test_update_position_increase_size(self, test_db_engine):
        """Test increasing position size"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        # Open initial position
        position = tracker.open_position(
            market_id="market_789",
            token_id="token_test",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.50")
        )

        # Add to position at higher price
        updated = tracker.update_position(
            position_id=position.position_id,
            size_delta=Decimal("50"),
            price=Decimal("0.60"),
            current_price=Decimal("0.60")
        )

        # New avg price: (100*0.50 + 50*0.60) / 150 = 0.5333
        expected_avg = (Decimal("100") * Decimal("0.50") + Decimal("50") * Decimal("0.60")) / Decimal("150")
        assert updated.size == Decimal("150")
        assert abs(updated.avg_entry_price - expected_avg) < Decimal("0.01")

    def test_update_position_reduce_size(self, test_db_engine):
        """Test reducing position size"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_abc",
            token_id="token_test",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.50")
        )

        # Reduce position
        updated = tracker.update_position(
            position_id=position.position_id,
            size_delta=Decimal("-30"),
            price=Decimal("0.55"),
            current_price=Decimal("0.55")
        )

        assert updated.size == Decimal("70")
        # Avg entry price shouldn't change when reducing
        assert updated.avg_entry_price == Decimal("0.50")

    def test_update_position_close_fully(self, test_db_engine):
        """Test closing position by reducing size to zero"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_def",
            token_id="token_test",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.50")
        )

        # Close entire position
        updated = tracker.update_position(
            position_id=position.position_id,
            size_delta=Decimal("-100"),
            price=Decimal("0.60")
        )

        assert updated.size == Decimal("0")
        assert updated.status == PositionStatus.CLOSED.value
        assert updated.closed_at is not None

    def test_close_position(self, test_db_engine):
        """Test explicit position closing"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_ghi",
            token_id="token_test",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.50")
        )

        # Close position at profit
        closed = tracker.close_position(
            position_id=position.position_id,
            exit_price=Decimal("0.65"),
            reason="take_profit"
        )

        assert closed.status == PositionStatus.CLOSED.value
        assert closed.realized_pnl == Decimal("15")  # (0.65 - 0.50) * 100
        assert closed.percent_pnl == Decimal("30")  # 15 / 50 * 100

    def test_close_position_loss(self, test_db_engine):
        """Test closing position at a loss"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            market_id="market_jkl",
            token_id="token_test",
            side="BUY",
            size=Decimal("100"),
            entry_price=Decimal("0.60")
        )

        # Close at loss
        closed = tracker.close_position(
            position_id=position.position_id,
            exit_price=Decimal("0.45"),
            reason="stop_loss"
        )

        assert closed.realized_pnl == Decimal("-15")  # (0.45 - 0.60) * 100
        assert closed.percent_pnl == Decimal("-25")  # -15 / 60 * 100

    def test_get_open_positions(self, test_db_engine):
        """Test retrieving open positions"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        # Open multiple positions
        pos1 = tracker.open_position("m1", "t1", "BUY", Decimal("100"), Decimal("0.50"))
        pos2 = tracker.open_position("m2", "t2", "BUY", Decimal("50"), Decimal("0.60"))

        # Close one
        tracker.close_position(pos1.position_id, Decimal("0.55"))

        open_positions = tracker.get_open_positions()

        assert len(open_positions) == 1
        assert open_positions[0].position_id == pos2.position_id

    def test_get_position_by_market(self, test_db_engine):
        """Test getting position for specific market"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        position = tracker.open_position(
            "unique_market_xyz",
            "token_test",
            "BUY",
            Decimal("100"),
            Decimal("0.50")
        )

        found = tracker.get_position_by_market("unique_market_xyz")

        assert found is not None
        assert found.market_id == "unique_market_xyz"
        assert found.position_id == position.position_id


# ==================== PnLCalculator Tests ====================

class TestPnLCalculator:
    """Test PnLCalculator component"""

    @pytest.mark.asyncio
    async def test_fetch_current_price(self, mock_client, test_db_engine):
        """Test fetching current price with caching"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        mock_client.get_midpoint.return_value = 0.65

        price = await pnl_calc.fetch_current_price("token_123")

        assert price == Decimal("0.65")
        mock_client.get_midpoint.assert_called_once_with("token_123")

    @pytest.mark.asyncio
    async def test_fetch_current_price_caching(self, mock_client, test_db_engine):
        """Test price caching behavior"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        mock_client.get_midpoint.return_value = 0.70

        # First call
        price1 = await pnl_calc.fetch_current_price("token_cache_test")
        # Second call (should use cache)
        price2 = await pnl_calc.fetch_current_price("token_cache_test")

        assert price1 == price2
        # Should only call API once due to caching
        assert mock_client.get_midpoint.call_count == 1

    @pytest.mark.asyncio
    async def test_calculate_position_pnl_profit(self, mock_client, test_db_engine, sample_position):
        """Test P&L calculation for profitable position"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        sample_position.avg_entry_price = Decimal("0.50")
        sample_position.size = Decimal("100")
        current_price = Decimal("0.65")

        pnl_metrics = await pnl_calc.calculate_position_pnl(
            sample_position,
            current_price
        )

        expected_pnl = (Decimal("0.65") - Decimal("0.50")) * Decimal("100")
        assert pnl_metrics.unrealized_pnl == expected_pnl  # 15
        assert pnl_metrics.pnl_pct == (expected_pnl / Decimal("50")) * Decimal("100")  # 30%
        assert pnl_metrics.current_price == Decimal("0.65")
        assert pnl_metrics.current_value == Decimal("65")

    @pytest.mark.asyncio
    async def test_calculate_position_pnl_loss(self, mock_client, test_db_engine, sample_position):
        """Test P&L calculation for losing position"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        sample_position.avg_entry_price = Decimal("0.60")
        sample_position.size = Decimal("100")
        current_price = Decimal("0.45")

        pnl_metrics = await pnl_calc.calculate_position_pnl(
            sample_position,
            current_price
        )

        expected_pnl = (Decimal("0.45") - Decimal("0.60")) * Decimal("100")
        assert pnl_metrics.unrealized_pnl == expected_pnl  # -15
        assert pnl_metrics.pnl_pct < Decimal("0")  # Negative

    @pytest.mark.asyncio
    async def test_stop_loss_trigger_detection(self, mock_client, test_db_engine, sample_position):
        """Test stop-loss trigger detection"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        sample_position.avg_entry_price = Decimal("0.60")
        sample_position.stop_loss_price = Decimal("0.51")  # 15% below
        current_price = Decimal("0.50")  # Below stop-loss

        pnl_metrics = await pnl_calc.calculate_position_pnl(
            sample_position,
            current_price
        )

        assert pnl_metrics.stop_loss_hit is True
        assert pnl_metrics.profit_target_hit is False

    @pytest.mark.asyncio
    async def test_take_profit_trigger_detection(self, mock_client, test_db_engine, sample_position):
        """Test take-profit trigger detection"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        sample_position.avg_entry_price = Decimal("0.50")
        sample_position.take_profit_price = Decimal("0.65")  # 30% above
        current_price = Decimal("0.70")  # Above take-profit

        pnl_metrics = await pnl_calc.calculate_position_pnl(
            sample_position,
            current_price
        )

        assert pnl_metrics.profit_target_hit is True
        assert pnl_metrics.stop_loss_hit is False

    @pytest.mark.asyncio
    async def test_calculate_portfolio_pnl_empty(self, mock_client, test_db_engine):
        """Test portfolio P&L with no positions"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        portfolio_pnl = await pnl_calc.calculate_portfolio_pnl()

        assert portfolio_pnl.num_positions == 0
        assert portfolio_pnl.total_value == Decimal("0")
        assert portfolio_pnl.total_unrealized_pnl == Decimal("0")
        assert portfolio_pnl.win_rate == Decimal("0")

    @pytest.mark.asyncio
    async def test_calculate_portfolio_pnl_multiple_positions(self, mock_client, test_db_engine):
        """Test portfolio P&L with multiple positions"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        # Open multiple positions
        pos1 = tracker.open_position("m1", "t1", "BUY", Decimal("100"), Decimal("0.50"))
        pos2 = tracker.open_position("m2", "t2", "BUY", Decimal("50"), Decimal("0.60"))
        pos3 = tracker.open_position("m3", "t3", "BUY", Decimal("75"), Decimal("0.55"))

        # Mock prices: 2 winners, 1 loser
        mock_client.get_midpoint.side_effect = [
            0.60,  # t1: +10 profit
            0.55,  # t2: -2.5 loss
            0.70   # t3: +11.25 profit
        ]

        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        portfolio_pnl = await pnl_calc.calculate_portfolio_pnl()

        assert portfolio_pnl.num_positions == 3
        assert portfolio_pnl.num_winners == 2
        assert portfolio_pnl.num_losers == 1
        assert portfolio_pnl.win_rate == Decimal("66.67") or abs(portfolio_pnl.win_rate - Decimal("66.67")) < Decimal("0.1")


# ==================== StopLossTakeProfitManager Tests ====================

class TestStopLossTakeProfitManager:
    """Test StopLossTakeProfitManager component"""

    @pytest.mark.asyncio
    async def test_check_exit_triggers_no_trigger(self, mock_client, test_db_engine, sample_position):
        """Test when no exit triggers are hit"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        sl_tp_manager = StopLossTakeProfitManager(
            pnl_calculator=pnl_calc,
            position_tracker=tracker
        )

        sample_position.avg_entry_price = Decimal("0.55")
        sample_position.stop_loss_price = Decimal("0.4675")
        sample_position.take_profit_price = Decimal("0.715")
        current_price = Decimal("0.60")  # Within range

        mock_client.get_midpoint.return_value = float(current_price)

        exit_signal = await sl_tp_manager.check_exit_triggers(sample_position)

        assert exit_signal is None

    @pytest.mark.asyncio
    async def test_check_exit_triggers_stop_loss(self, mock_client, test_db_engine, sample_position):
        """Test stop-loss trigger"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        sl_tp_manager = StopLossTakeProfitManager(
            pnl_calculator=pnl_calc,
            position_tracker=tracker
        )

        sample_position.avg_entry_price = Decimal("0.60")
        sample_position.stop_loss_price = Decimal("0.51")
        current_price = Decimal("0.45")  # Below stop-loss

        mock_client.get_midpoint.return_value = float(current_price)

        exit_signal = await sl_tp_manager.check_exit_triggers(sample_position)

        assert exit_signal is not None
        assert exit_signal.reason == "stop_loss"
        assert exit_signal.current_price == current_price

    @pytest.mark.asyncio
    async def test_check_exit_triggers_take_profit(self, mock_client, test_db_engine, sample_position):
        """Test take-profit trigger"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        sl_tp_manager = StopLossTakeProfitManager(
            pnl_calculator=pnl_calc,
            position_tracker=tracker
        )

        sample_position.avg_entry_price = Decimal("0.50")
        sample_position.take_profit_price = Decimal("0.65")
        current_price = Decimal("0.75")  # Above take-profit

        mock_client.get_midpoint.return_value = float(current_price)

        exit_signal = await sl_tp_manager.check_exit_triggers(sample_position)

        assert exit_signal is not None
        assert exit_signal.reason == "take_profit"
        assert exit_signal.pnl > Decimal("0")

    @pytest.mark.asyncio
    async def test_check_all_positions(self, mock_client, test_db_engine):
        """Test checking all positions for exit triggers"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))

        # Open 3 positions
        pos1 = tracker.open_position("m1", "t1", "BUY", Decimal("100"), Decimal("0.50"))
        pos2 = tracker.open_position("m2", "t2", "BUY", Decimal("50"), Decimal("0.60"))
        pos3 = tracker.open_position("m3", "t3", "BUY", Decimal("75"), Decimal("0.55"))

        # Set trigger prices
        with Session(tracker.engine) as session:
            p1 = session.get(Position, pos1.position_id)
            p1.stop_loss_price = Decimal("0.425")
            p2 = session.get(Position, pos2.position_id)
            p2.take_profit_price = Decimal("0.78")
            session.commit()

        # Mock prices: p1 hits stop-loss, p2 hits take-profit, p3 no trigger
        mock_client.get_midpoint.side_effect = [
            0.40,  # t1: stop-loss
            0.80,  # t2: take-profit
            0.60   # t3: no trigger
        ]

        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        sl_tp_manager = StopLossTakeProfitManager(
            pnl_calculator=pnl_calc,
            position_tracker=tracker
        )

        exit_signals = await sl_tp_manager.check_all_positions()

        assert len(exit_signals) == 2
        reasons = [sig.reason for sig in exit_signals]
        assert "stop_loss" in reasons
        assert "take_profit" in reasons

    def test_set_stop_loss(self, test_db_engine):
        """Test setting custom stop-loss price"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        sl_tp_manager = StopLossTakeProfitManager(position_tracker=tracker)

        position = tracker.open_position("m1", "t1", "BUY", Decimal("100"), Decimal("0.50"))

        # Set custom stop-loss
        sl_tp_manager.set_stop_loss(position.position_id, Decimal("0.45"))

        with Session(tracker.engine) as session:
            updated = session.get(Position, position.position_id)
            assert updated.stop_loss_price == Decimal("0.45")

    def test_set_take_profit(self, test_db_engine):
        """Test setting custom take-profit price"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        sl_tp_manager = StopLossTakeProfitManager(position_tracker=tracker)

        position = tracker.open_position("m1", "t1", "BUY", Decimal("100"), Decimal("0.50"))

        # Set custom take-profit
        sl_tp_manager.set_take_profit(position.position_id, Decimal("0.75"))

        with Session(tracker.engine) as session:
            updated = session.get(Position, position.position_id)
            assert updated.take_profit_price == Decimal("0.75")


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for full position lifecycle"""

    @pytest.mark.asyncio
    async def test_full_position_lifecycle_profit(self, mock_client, test_db_engine):
        """Test complete position lifecycle with profit"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)

        # Open position
        position = tracker.open_position(
            "market_lifecycle",
            "token_lifecycle",
            "BUY",
            Decimal("100"),
            Decimal("0.50")
        )

        # Update P&L
        mock_client.get_midpoint.return_value = 0.65
        pnl = await pnl_calc.calculate_position_pnl(position)

        assert pnl.unrealized_pnl == Decimal("15")
        assert pnl.pnl_pct == Decimal("30")

        # Close position
        closed = tracker.close_position(position.position_id, Decimal("0.65"), "manual")

        assert closed.status == PositionStatus.CLOSED.value
        assert closed.realized_pnl == Decimal("15")

    @pytest.mark.asyncio
    async def test_full_position_lifecycle_stop_loss(self, mock_client, test_db_engine):
        """Test position lifecycle with stop-loss trigger"""
        tracker = PositionTracker(db_url=str(test_db_engine.url))
        pnl_calc = PnLCalculator(client=mock_client, position_tracker=tracker)
        sl_tp_manager = StopLossTakeProfitManager(
            pnl_calculator=pnl_calc,
            position_tracker=tracker
        )

        # Open position
        position = tracker.open_position(
            "market_sl",
            "token_sl",
            "BUY",
            Decimal("100"),
            Decimal("0.60")
        )

        # Price drops, triggering stop-loss
        mock_client.get_midpoint.return_value = 0.45
        exit_signal = await sl_tp_manager.check_exit_triggers(position)

        assert exit_signal is not None
        assert exit_signal.reason == "stop_loss"

        # Close position
        closed = tracker.close_position(
            position.position_id,
            exit_signal.current_price,
            "stop_loss"
        )

        assert closed.realized_pnl < Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
