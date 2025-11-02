"""
Integration Tests for Week 4: Position Management
Tests the full position management system including:
- Kelly Criterion position sizing
- Production position manager
- Real-time P&L calculation
- Position lifecycle (open, update, close)
- Risk controls and limits
"""

import pytest
import asyncio
import asyncpg
from decimal import Decimal
from datetime import datetime, timedelta

from src.config import settings
from src.trading.kelly_criterion_sizer import (
    FractionalKellyCriterion,
    KellyParameters,
    PositionSizeRecommendation
)
from src.trading.production_position_manager import (
    ProductionPositionManager,
    PositionLimits,
    PositionStatus,
    CloseReason
)
from src.trading.realtime_pnl_engine import RealtimePnLEngine


# ==================== Fixtures ====================

@pytest.fixture
async def db_pool():
    """Create database pool for testing"""
    pool = await asyncpg.create_pool(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        database=settings.DATABASE_NAME
    )
    yield pool
    await pool.close()


@pytest.fixture
async def clean_db(db_pool):
    """Clean test data before and after tests"""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM position_updates WHERE TRUE")
        await conn.execute("DELETE FROM positions WHERE TRUE")
    yield
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM position_updates WHERE TRUE")
        await conn.execute("DELETE FROM positions WHERE TRUE")


@pytest.fixture
def kelly_sizer():
    """Create Kelly sizer with conservative defaults"""
    return FractionalKellyCriterion(
        kelly_fraction=0.5,
        min_position_size=Decimal("10"),
        max_position_size=Decimal("1000"),
        min_edge=Decimal("0.05")
    )


@pytest.fixture
async def position_manager(db_pool, kelly_sizer):
    """Create production position manager"""
    limits = PositionLimits(
        max_positions=50,
        max_total_exposure=Decimal("50000"),
        max_position_size=Decimal("1000"),
        min_position_size=Decimal("10"),
        stop_loss_pct=Decimal("-0.15"),
        take_profit_pct=Decimal("0.50")
    )
    return ProductionPositionManager(db_pool, kelly_sizer, limits)


# ==================== Kelly Criterion Tests ====================

class TestKellyCriterionSizing:
    """Test Fractional Kelly Criterion position sizing"""

    def test_kelly_calculation_with_edge(self, kelly_sizer):
        """Test Kelly sizing with positive edge"""
        balance = Decimal("5000")
        params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        result = kelly_sizer.calculate_position_size(balance, params)

        assert result.recommended_size > 0
        assert result.edge > Decimal("1")  # 50/30 = 1.67
        assert result.kelly_fraction == Decimal("0.5")
        assert result.recommended_size <= Decimal("1000")  # max position size
        assert not result.risk_adjusted or result.reason

    def test_kelly_no_edge(self, kelly_sizer):
        """Test Kelly sizing rejects trades with no edge"""
        balance = Decimal("5000")
        params = KellyParameters(
            win_rate=Decimal("0.50"),
            avg_win=Decimal("10"),
            avg_loss=Decimal("10"),
            kelly_fraction=Decimal("0.5")
        )

        result = kelly_sizer.calculate_position_size(balance, params)

        assert result.recommended_size == 0
        assert "edge" in result.reason.lower()

    def test_kelly_insufficient_edge(self, kelly_sizer):
        """Test Kelly sizing rejects trades below minimum edge"""
        balance = Decimal("5000")
        params = KellyParameters(
            win_rate=Decimal("0.55"),
            avg_win=Decimal("11"),
            avg_loss=Decimal("10"),  # Only 1.1 edge, below 1.05 minimum
            kelly_fraction=Decimal("0.5")
        )

        result = kelly_sizer.calculate_position_size(balance, params)

        assert result.recommended_size == 0
        assert "insufficient edge" in result.reason.lower()

    def test_kelly_market_adjustments(self, kelly_sizer):
        """Test market condition adjustments"""
        balance = Decimal("5000")
        params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        base_rec = kelly_sizer.calculate_position_size(balance, params)

        # Apply volatility reduction
        adjusted = kelly_sizer.adjust_for_market_conditions(
            base_rec,
            volatility_multiplier=0.5,  # Halve size
            whale_confidence=1.2  # 20% increase
        )

        # Net effect: 0.5 * 1.2 = 0.6x base size
        expected_size = base_rec.recommended_size * Decimal("0.6")
        assert abs(adjusted.recommended_size - expected_size) < Decimal("0.01")


# ==================== Position Manager Tests ====================

class TestProductionPositionManager:
    """Test production position manager"""

    @pytest.mark.asyncio
    async def test_open_position(self, position_manager, clean_db):
        """Test opening a new position"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.55"),
            balance=Decimal("5000"),
            kelly_params=kelly_params,
            notes="Test position"
        )

        assert position is not None
        assert position.position_id.startswith("pos_")
        assert position.side == "YES"
        assert position.entry_price == Decimal("0.55")
        assert position.entry_size > 0
        assert position.entry_amount > 0
        assert position.stop_loss_price is not None
        assert position.stop_loss_price < position.entry_price  # YES position
        assert position.take_profit_price is not None
        assert position.take_profit_price > position.entry_price  # YES position
        assert position.status == PositionStatus.OPEN

    @pytest.mark.asyncio
    async def test_position_limits(self, position_manager, clean_db):
        """Test position limits enforcement"""
        # Set low limit
        position_manager.limits.max_positions = 2

        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        # Open 2 positions
        pos1 = await position_manager.open_position(
            whale_address="0x1111111111111111111111111111111111111111",
            token_id="token_1",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        pos2 = await position_manager.open_position(
            whale_address="0x2222222222222222222222222222222222222222",
            token_id="token_2",
            side="YES",
            entry_price=Decimal("0.55"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        assert pos1 is not None
        assert pos2 is not None

        # Try to open 3rd position - should fail
        pos3 = await position_manager.open_position(
            whale_address="0x3333333333333333333333333333333333333333",
            token_id="token_3",
            side="YES",
            entry_price=Decimal("0.60"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        assert pos3 is None  # Should be rejected due to limits

    @pytest.mark.asyncio
    async def test_update_position_price(self, position_manager, clean_db):
        """Test updating position with new price"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        assert position.unrealized_pnl == 0

        # Update price up (profit for YES position)
        success = await position_manager.update_position_price(
            position.position_id,
            Decimal("0.60")
        )

        assert success
        assert position.current_price == Decimal("0.60")
        assert position.unrealized_pnl > 0
        assert position.pnl_percentage > 0
        assert position.max_profit > 0

        # Update price down (loss for YES position)
        await position_manager.update_position_price(
            position.position_id,
            Decimal("0.40")
        )

        assert position.current_price == Decimal("0.40")
        assert position.unrealized_pnl < 0
        assert position.pnl_percentage < 0
        assert position.max_drawdown < 0

    @pytest.mark.asyncio
    async def test_close_position(self, position_manager, clean_db):
        """Test closing a position"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        # Update price to profit
        await position_manager.update_position_price(
            position.position_id,
            Decimal("0.60")
        )

        # Close position
        success = await position_manager.close_position(
            position.position_id,
            Decimal("0.60"),
            CloseReason.MANUAL,
            notes="Test close"
        )

        assert success
        assert position.status == PositionStatus.CLOSED
        assert position.closed_at is not None
        assert position.close_reason == CloseReason.MANUAL
        assert position.realized_pnl > 0
        assert position.unrealized_pnl == 0
        assert position.current_size == 0

    @pytest.mark.asyncio
    async def test_partial_close(self, position_manager, clean_db):
        """Test partial position close"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        initial_size = position.current_size
        close_size = initial_size / Decimal("2")  # Close half

        # Update price to profit
        await position_manager.update_position_price(
            position.position_id,
            Decimal("0.60")
        )

        # Partial close
        success = await position_manager.partial_close_position(
            position.position_id,
            close_size,
            Decimal("0.60")
        )

        assert success
        assert position.current_size == initial_size - close_size
        assert position.realized_pnl > 0  # Realized from closed portion
        assert position.unrealized_pnl > 0  # Still has open portion
        assert position.status == PositionStatus.OPEN  # Still open

    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, position_manager, clean_db):
        """Test automatic stop loss execution"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        stop_loss_price = position.stop_loss_price

        # Update price to hit stop loss
        await position_manager.update_position_price(
            position.position_id,
            stop_loss_price - Decimal("0.01")  # Below stop loss
        )

        # Position should auto-close
        assert position.status == PositionStatus.CLOSED
        assert position.close_reason == CloseReason.STOP_LOSS
        assert position.realized_pnl < 0  # Loss

    @pytest.mark.asyncio
    async def test_take_profit_trigger(self, position_manager, clean_db):
        """Test automatic take profit execution"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        take_profit_price = position.take_profit_price

        # Update price to hit take profit
        await position_manager.update_position_price(
            position.position_id,
            take_profit_price + Decimal("0.01")  # Above take profit
        )

        # Position should auto-close
        assert position.status == PositionStatus.CLOSED
        assert position.close_reason == CloseReason.TAKE_PROFIT
        assert position.realized_pnl > 0  # Profit

    @pytest.mark.asyncio
    async def test_portfolio_metrics(self, position_manager, clean_db):
        """Test portfolio aggregated metrics"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        # Open 3 positions
        pos1 = await position_manager.open_position(
            whale_address="0x1111111111111111111111111111111111111111",
            token_id="token_1",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        pos2 = await position_manager.open_position(
            whale_address="0x2222222222222222222222222222222222222222",
            token_id="token_2",
            side="YES",
            entry_price=Decimal("0.55"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        pos3 = await position_manager.open_position(
            whale_address="0x3333333333333333333333333333333333333333",
            token_id="token_3",
            side="YES",
            entry_price=Decimal("0.60"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        # Update prices (2 winning, 1 losing)
        await position_manager.update_position_price(pos1.position_id, Decimal("0.60"))  # +20%
        await position_manager.update_position_price(pos2.position_id, Decimal("0.65"))  # +18%
        await position_manager.update_position_price(pos3.position_id, Decimal("0.50"))  # -17%

        # Get portfolio metrics
        metrics = await position_manager.get_portfolio_metrics()

        assert metrics.total_positions == 3
        assert metrics.open_positions == 3
        assert metrics.total_unrealized_pnl != 0
        assert metrics.winning_positions >= 1
        assert metrics.losing_positions >= 1
        assert metrics.total_exposure > 0


# ==================== Real-Time P&L Engine Tests ====================

class TestRealtimePnLEngine:
    """Test real-time P&L calculation engine"""

    @pytest.mark.asyncio
    async def test_pnl_engine_start_stop(self, position_manager, clean_db):
        """Test P&L engine start and stop"""
        engine = RealtimePnLEngine(
            position_manager=position_manager,
            update_interval=0.1  # Fast for testing
        )

        assert not engine.is_running

        await engine.start()
        assert engine.is_running

        # Let it run briefly
        await asyncio.sleep(0.3)

        await engine.stop()
        assert not engine.is_running
        assert engine.total_updates > 0

    @pytest.mark.asyncio
    async def test_pnl_history_tracking(self, position_manager, clean_db):
        """Test P&L history is tracked"""
        kelly_params = KellyParameters(
            win_rate=Decimal("0.60"),
            avg_win=Decimal("50"),
            avg_loss=Decimal("30"),
            kelly_fraction=Decimal("0.5")
        )

        position = await position_manager.open_position(
            whale_address="0x1234567890123456789012345678901234567890",
            token_id="test_token_123",
            side="YES",
            entry_price=Decimal("0.50"),
            balance=Decimal("5000"),
            kelly_params=kelly_params
        )

        # Manually update P&L a few times
        prices = [Decimal("0.52"), Decimal("0.54"), Decimal("0.56"), Decimal("0.58")]
        for price in prices:
            await position_manager.update_position_price(position.position_id, price)

        # Check history
        engine = RealtimePnLEngine(position_manager=position_manager)

        # Simulate adding to history (normally done by update loop)
        for price in prices:
            await engine._update_position_pnl(
                position,
                type('PriceUpdate', (), {
                    'token_id': position.token_id,
                    'price': price,
                    'timestamp': datetime.now()
                })()
            )

        history = engine.get_pnl_history(position.position_id)
        assert len(history) > 0

        # Get P&L stats
        stats = engine.get_pnl_stats(position.position_id)
        if stats:
            assert stats['current_pnl'] > 0  # Should be profitable
            assert stats['snapshots_count'] > 0


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
