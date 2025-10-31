"""
SQLAlchemy models for Polymarket Copy Trading System
"""
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, TIMESTAMP, Text, ARRAY,
    CheckConstraint, ForeignKey, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Whale(Base):
    """Whale trader model"""
    __tablename__ = 'whales'

    address = Column(String(42), primary_key=True)
    pseudonym = Column(String(100))
    profile_image = Column(Text)

    # Volume & trading stats
    total_volume = Column(Numeric(20, 2), nullable=False, default=0)
    total_trades = Column(Integer, nullable=False, default=0)
    active_positions = Column(Integer, nullable=False, default=0)
    avg_trade_size = Column(Numeric(20, 2))
    avg_hold_time = Column(Numeric(10, 2))  # hours

    # Performance metrics
    win_rate = Column(Numeric(5, 2))
    roi = Column(Numeric(10, 2))
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 2))
    profit_factor = Column(Numeric(10, 4))

    # Category performance
    category_performance = Column(JSONB, default={})

    # Status
    is_active = Column(Boolean, default=True)
    quality_score = Column(Numeric(10, 4))
    rank = Column(Integer)

    # Timestamps
    first_seen = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_active = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    trades = relationship("Trade", back_populates="whale", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="whale")

    def __repr__(self):
        return f"<Whale(address={self.address}, score={self.quality_score})>"


class Trade(Base):
    """Trade model - time-series data"""
    __tablename__ = 'trades'

    trade_id = Column(String(100), primary_key=True)
    trader_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)

    # Market identifiers
    market_id = Column(String(66), nullable=False)
    condition_id = Column(String(66))
    token_id = Column(String(78), nullable=False)
    event_slug = Column(String(200))

    # Trade details
    side = Column(String(4), nullable=False)
    size = Column(Numeric(20, 6), nullable=False)
    price = Column(Numeric(10, 6), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    fee_amount = Column(Numeric(20, 6))

    # Market context
    market_title = Column(Text)
    outcome = Column(String(10))
    category = Column(String(50))

    # Execution details
    transaction_hash = Column(String(66))
    maker_address = Column(String(42))

    # Copy trading metadata
    is_whale_trade = Column(Boolean, default=False)
    followed = Column(Boolean, default=False)
    our_order_id = Column(String(100))
    copy_reason = Column(Text)
    skip_reason = Column(Text)

    # Timestamps
    timestamp = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whale = relationship("Whale", back_populates="trades")

    # Constraints
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name='check_trade_side'),
        Index('idx_trades_timestamp', 'timestamp', postgresql_using='btree'),
        Index('idx_trades_trader', 'trader_address', 'timestamp'),
        Index('idx_trades_market', 'market_id', 'timestamp'),
        Index('idx_trades_whale_followed', 'is_whale_trade', 'followed'),
        Index('idx_trades_category', 'category', 'timestamp'),
    )

    def __repr__(self):
        return f"<Trade(id={self.trade_id}, trader={self.trader_address[:8]}, {self.side} {self.size}@{self.price})>"


class Market(Base):
    """Market model"""
    __tablename__ = 'markets'

    condition_id = Column(String(66), primary_key=True)
    question = Column(Text, nullable=False)
    description = Column(Text)

    # Market state
    active = Column(Boolean, default=True)
    closed = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)

    # Token IDs
    yes_token_id = Column(String(78))
    no_token_id = Column(String(78))

    # Pricing
    yes_price = Column(Numeric(10, 6))
    no_price = Column(Numeric(10, 6))
    volume = Column(Numeric(20, 2))
    liquidity = Column(Numeric(20, 2))
    open_interest = Column(Numeric(20, 2))

    # Market metadata
    category = Column(String(50))
    tags = Column(ARRAY(Text))
    event_id = Column(String(100))
    market_slug = Column(String(200))

    # Resolution
    outcome = Column(String(10))
    outcome_prices = Column(JSONB)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    end_date = Column(TIMESTAMP)
    resolution_date = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    positions = relationship("Position", back_populates="market")

    # Indexes
    __table_args__ = (
        Index('idx_markets_active', 'active', 'closed'),
        Index('idx_markets_category', 'category'),
        Index('idx_markets_end_date', 'end_date'),
    )

    def __repr__(self):
        return f"<Market(id={self.condition_id[:12]}, question={self.question[:50]})>"


class Position(Base):
    """Position model"""
    __tablename__ = 'positions'

    position_id = Column(String(100), primary_key=True)
    user_address = Column(String(42), nullable=False)

    # Market identifiers
    market_id = Column(String(66), nullable=False)
    condition_id = Column(String(66), ForeignKey('markets.condition_id', ondelete='CASCADE'))
    token_id = Column(String(78), nullable=False)
    outcome = Column(String(10))

    # Position sizing
    size = Column(Numeric(20, 6), nullable=False)
    avg_entry_price = Column(Numeric(10, 6), nullable=False)
    current_price = Column(Numeric(10, 6))

    # P&L tracking
    initial_value = Column(Numeric(20, 2), nullable=False)
    current_value = Column(Numeric(20, 2))
    cash_pnl = Column(Numeric(20, 2))
    percent_pnl = Column(Numeric(10, 2))
    realized_pnl = Column(Numeric(20, 2), default=0)

    # Market info
    market_title = Column(Text)
    end_date = Column(TIMESTAMP)
    redeemable = Column(Boolean, default=False)

    # Risk management
    stop_loss_price = Column(Numeric(10, 6))
    take_profit_price = Column(Numeric(10, 6))
    risk_score = Column(Numeric(10, 4))

    # Copy trading metadata
    source_whale = Column(String(42), ForeignKey('whales.address', ondelete='SET NULL'))
    entry_trade_id = Column(String(100))

    # Status
    status = Column(String(20), default='OPEN')

    # Timestamps
    opened_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    closed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whale = relationship("Whale", back_populates="positions")
    market = relationship("Market", back_populates="positions")

    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED', 'LIQUIDATED')", name='check_position_status'),
        Index('idx_positions_user', 'user_address', 'status'),
        Index('idx_positions_market', 'market_id'),
        Index('idx_positions_source_whale', 'source_whale'),
        Index('idx_positions_status', 'status'),
    )

    def __repr__(self):
        return f"<Position(id={self.position_id}, whale={self.source_whale[:8] if self.source_whale else 'N/A'}, pnl={self.cash_pnl})>"


class Order(Base):
    """Order model"""
    __tablename__ = 'orders'

    order_id = Column(String(100), primary_key=True)

    # Market identifiers
    market_id = Column(String(66), nullable=False)
    token_id = Column(String(78), nullable=False)

    # Order details
    side = Column(String(4), nullable=False)
    order_type = Column(String(10), nullable=False)
    price = Column(Numeric(10, 6))
    size = Column(Numeric(20, 6), nullable=False)
    filled_size = Column(Numeric(20, 6), default=0)
    remaining_size = Column(Numeric(20, 6))
    avg_fill_price = Column(Numeric(10, 6))

    # Status
    status = Column(String(20), nullable=False, default='PENDING')

    # Copy trading metadata
    source_whale = Column(String(42), ForeignKey('whales.address', ondelete='SET NULL'))
    source_trade_id = Column(String(100))
    copy_ratio = Column(Numeric(5, 4))  # What % of whale trade we copied

    # Execution tracking
    fills = Column(JSONB, default=[])
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    submitted_at = Column(TIMESTAMP)
    filled_at = Column(TIMESTAMP)
    cancelled_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Constraints
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name='check_order_side'),
        CheckConstraint("order_type IN ('LIMIT', 'MARKET', 'FOK', 'GTC')", name='check_order_type'),
        CheckConstraint(
            "status IN ('PENDING', 'OPEN', 'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'FAILED')",
            name='check_order_status'
        ),
        Index('idx_orders_status', 'status', 'created_at'),
        Index('idx_orders_source_whale', 'source_whale'),
        Index('idx_orders_market', 'market_id'),
    )

    def __repr__(self):
        return f"<Order(id={self.order_id}, {self.status}, {self.side} {self.size}@{self.price})>"


class PerformanceMetric(Base):
    """Performance metrics model - rolling window calculations"""
    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False)  # 'whale', 'portfolio', 'strategy'
    entity_id = Column(String(100), nullable=False)

    # Time window
    window_days = Column(Integer, nullable=False)

    # Performance metrics
    total_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))
    avg_trade_pnl = Column(Numeric(20, 2))
    total_pnl = Column(Numeric(20, 2))
    roi = Column(Numeric(10, 2))

    # Risk-adjusted metrics
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    calmar_ratio = Column(Numeric(10, 4))

    # Risk metrics
    max_drawdown = Column(Numeric(10, 2))
    volatility = Column(Numeric(10, 4))
    var_95 = Column(Numeric(20, 2))  # Value at Risk 95%

    # Other metrics
    profit_factor = Column(Numeric(10, 4))
    k_ratio = Column(Numeric(10, 4))

    # Metadata
    calculated_at = Column(TIMESTAMP, nullable=False)
    period_start = Column(TIMESTAMP, nullable=False)
    period_end = Column(TIMESTAMP, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint("entity_type IN ('whale', 'portfolio', 'strategy')", name='check_entity_type'),
        Index('idx_perf_entity', 'entity_type', 'entity_id', 'calculated_at'),
        Index('idx_perf_window', 'window_days', 'calculated_at'),
    )

    def __repr__(self):
        return f"<PerformanceMetric({self.entity_type}={self.entity_id}, window={self.window_days}d, sharpe={self.sharpe_ratio})>"


class Event(Base):
    """Event model - system events and alerts"""
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20))

    # Event details
    title = Column(String(200), nullable=False)
    description = Column(Text)
    metadata = Column(JSONB, default={})

    # Related entities
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'))
    order_id = Column(String(100))
    position_id = Column(String(100))

    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(String(100))

    # Timestamps
    timestamp = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Constraints
    __table_args__ = (
        CheckConstraint("severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='check_severity'),
        Index('idx_events_type', 'event_type', 'timestamp'),
        Index('idx_events_severity', 'severity', 'timestamp'),
        Index('idx_events_whale', 'whale_address', 'timestamp'),
    )

    def __repr__(self):
        return f"<Event(type={self.event_type}, severity={self.severity}, title={self.title})>"


class SystemState(Base):
    """System state model - track system status and circuit breakers"""
    __tablename__ = 'system_state'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    value_type = Column(String(20))

    description = Column(Text)

    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Constraints
    __table_args__ = (
        CheckConstraint("value_type IN ('string', 'number', 'boolean', 'json')", name='check_value_type'),
    )

    def __repr__(self):
        return f"<SystemState(key={self.key}, value={self.value})>"
