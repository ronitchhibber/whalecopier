"""
Unified SQLAlchemy Models for Polymarket Whale Copy-Trading System

Combines best features from both projects and adds institutional-grade enhancements:
- Wallet clustering for whale identification
- Edge decay detection (CUSUM metrics)
- Manipulation detection and alerts
- Portfolio risk tracking
- Auto-optimization metrics
"""

from datetime import datetime
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, TIMESTAMP, Text, ARRAY,
    CheckConstraint, ForeignKey, Index, text, Float, Enum, JSON
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


# =============================================================================
# ENUMS
# =============================================================================

class Platform(PyEnum):
    """Trading platform"""
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"


class Sector(PyEnum):
    """Market category/sector"""
    POLITICS = "politics"
    MACRO_FINANCE = "macro"
    CRYPTO = "crypto"
    TECH = "tech"
    SCIENCE = "science"
    SPORTS = "sports"
    WEATHER = "weather"
    CULTURE = "culture"
    OTHER = "other"


class CopyMode(PyEnum):
    """Copy execution mode"""
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    PARTIAL = "partial"
    CONDITIONAL = "conditional"


# =============================================================================
# WHALE INTELLIGENCE TABLES
# =============================================================================

class WalletCluster(Base):
    """
    Wallet clustering - links multiple addresses to single entity.
    Implements on-chain intelligence to defeat multi-wallet obfuscation.
    """
    __tablename__ = 'wallet_clusters'

    cluster_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name = Column(String(200))  # If identified (e.g., via Arkham)

    # Clustering confidence
    confidence_score = Column(Numeric(5, 4), nullable=False)  # 0-1
    clustering_method = Column(String(50))  # proxy_linkage, funding_flow, temporal_corr

    # Member wallets (array of addresses)
    member_addresses = Column(ARRAY(String(42)), nullable=False)
    primary_address = Column(String(42))  # Most active address

    # On-chain intelligence
    funding_source = Column(String(42))  # Common funding wallet
    arkham_entity_id = Column(String(100))
    nansen_label = Column(String(100))

    # Metadata
    first_seen = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whales = relationship("Whale", back_populates="cluster")

    __table_args__ = (
        Index('idx_wallet_cluster_primary', 'primary_address'),
        Index('idx_wallet_cluster_confidence', 'confidence_score'),
    )

    def __repr__(self):
        return f"<WalletCluster(id={str(self.cluster_id)[:8]}, size={len(self.member_addresses)})>"


class Whale(Base):
    """
    Whale trader model - enhanced with multi-factor scoring.
    Tracks both on-platform and on-chain activity.
    """
    __tablename__ = 'whales'

    address = Column(String(42), primary_key=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey('wallet_clusters.cluster_id', ondelete='SET NULL'))

    # Identity
    pseudonym = Column(String(100))
    profile_image = Column(Text)
    platform = Column(Enum(Platform), default=Platform.POLYMARKET)

    # Volume & trading stats
    total_volume = Column(Numeric(20, 2), nullable=False, default=0)
    total_trades = Column(Integer, nullable=False, default=0)
    active_positions = Column(Integer, nullable=False, default=0)
    avg_trade_size = Column(Numeric(20, 2))
    avg_hold_time = Column(Numeric(10, 2))  # hours
    trade_frequency = Column(Numeric(10, 4))  # trades/day

    # 24h metrics (for real-time insights)
    trades_24h = Column(Integer)  # Number of trades in last 24 hours
    volume_24h = Column(Numeric(20, 2))  # Dollar volume in last 24 hours
    active_trades = Column(Integer)  # Current number of active trades
    most_recent_trade_at = Column(TIMESTAMP)  # Timestamp of most recent trade
    last_trade_check_at = Column(TIMESTAMP)  # When we last checked for new trades

    # Performance metrics (full history)
    total_pnl = Column(Numeric(20, 2))
    win_rate = Column(Numeric(5, 2))
    roi = Column(Numeric(10, 2))
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    calmar_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 2))
    profit_factor = Column(Numeric(10, 4))
    k_ratio = Column(Numeric(10, 4))

    # Rolling performance (recent performance - more predictive)
    rolling_30d_sharpe = Column(Numeric(10, 4))
    rolling_30d_winrate = Column(Numeric(5, 2))
    rolling_90d_sharpe = Column(Numeric(10, 4))
    rolling_90d_winrate = Column(Numeric(5, 2))

    # Ledoit-Wolf robust metrics
    sharpe_ci_lower = Column(Numeric(10, 4))  # Lower bound of 95% CI
    sharpe_ci_upper = Column(Numeric(10, 4))  # Upper bound
    sharpe_shrunk = Column(Numeric(10, 4))  # James-Stein shrunk estimate

    # Category specialization (JSONB: {category: {sharpe, win_rate, trades, pnl}})
    category_performance = Column(JSONB, default={})
    primary_category = Column(Enum(Sector))

    # Market influence metrics
    avg_price_impact = Column(Numeric(10, 6))  # Avg % price move post-trade
    market_maker_score = Column(Numeric(10, 4))  # How often provides liquidity

    # Multi-factor whale score (0-100)
    quality_score = Column(Numeric(10, 4))
    score_components = Column(JSONB)  # {sharpe_z: 0.7, winrate_z: 0.3, ...}
    rank = Column(Integer)
    tier = Column(String(20))  # MEGA, LARGE, MEDIUM

    # Edge decay monitoring
    cusum_statistic = Column(Numeric(15, 6))  # CUSUM test statistic
    edge_status = Column(String(20), default='active')  # active, degrading, paused, culled
    last_cusum_check = Column(TIMESTAMP)

    # Status
    is_active = Column(Boolean, default=True)
    is_copying_enabled = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(Text)

    # Timestamps
    first_seen = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_active = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    cluster = relationship("WalletCluster", back_populates="whales")
    trades = relationship("Trade", back_populates="whale", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="whale")
    orders = relationship("Order", back_populates="source_whale_rel")
    edge_decay_logs = relationship("EdgeDecayLog", back_populates="whale")
    manipulation_flags = relationship("ManipulationFlag", back_populates="whale")

    __table_args__ = (
        Index('idx_whale_quality_score', 'quality_score', 'is_active'),
        Index('idx_whale_tier', 'tier', 'is_active'),
        Index('idx_whale_edge_status', 'edge_status'),
        Index('idx_whale_category', 'primary_category'),
        Index('idx_whale_copying_enabled', 'is_copying_enabled'),
    )

    def __repr__(self):
        return f"<Whale(address={self.address[:8]}, score={self.quality_score}, tier={self.tier})>"


class EdgeDecayLog(Base):
    """
    Edge decay detection log - tracks CUSUM/Page-Hinkley test results.
    Provides early warning system for whale performance degradation.
    """
    __tablename__ = 'edge_decay_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)

    # Test parameters
    test_type = Column(String(20), nullable=False)  # CUSUM, PAGE_HINKLEY, BOCPD
    lookback_days = Column(Integer, nullable=False, default=30)

    # Test results
    test_statistic = Column(Numeric(15, 6), nullable=False)
    threshold = Column(Numeric(15, 6), nullable=False)
    change_detected = Column(Boolean, nullable=False)
    p_value = Column(Numeric(10, 6))

    # Performance snapshot
    recent_sharpe = Column(Numeric(10, 4))
    recent_winrate = Column(Numeric(5, 2))
    recent_pnl = Column(Numeric(20, 2))
    drawdown_from_peak = Column(Numeric(10, 2))

    # Action taken
    action = Column(String(20))  # pause, cull, alert, none
    notes = Column(Text)

    # Timestamp
    timestamp = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whale = relationship("Whale", back_populates="edge_decay_logs")

    __table_args__ = (
        Index('idx_edge_decay_whale_time', 'whale_address', 'timestamp'),
        Index('idx_edge_decay_change', 'change_detected', 'timestamp'),
    )

    def __repr__(self):
        return f"<EdgeDecayLog(whale={self.whale_address[:8]}, change={self.change_detected}, action={self.action})>"


# =============================================================================
# MARKET & TRADING TABLES
# =============================================================================

class Market(Base):
    """Market model - enhanced with liquidity and resolution tracking"""
    __tablename__ = 'markets'

    condition_id = Column(String(66), primary_key=True)
    question = Column(Text, nullable=False)
    description = Column(Text)
    platform = Column(Enum(Platform), default=Platform.POLYMARKET)

    # Market state
    active = Column(Boolean, default=True)
    closed = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)
    is_disputed = Column(Boolean, default=False)

    # Token IDs
    yes_token_id = Column(String(78))
    no_token_id = Column(String(78))

    # Pricing & liquidity
    yes_price = Column(Numeric(10, 6))
    no_price = Column(Numeric(10, 6))
    volume = Column(Numeric(20, 2))
    volume_24h = Column(Numeric(20, 2))
    liquidity = Column(Numeric(20, 2))
    open_interest = Column(Numeric(20, 2))

    # Microstructure
    bid_ask_spread = Column(Numeric(10, 6))
    order_book_depth = Column(Numeric(20, 2))

    # Market metadata
    category = Column(Enum(Sector))
    tags = Column(ARRAY(Text))
    event_id = Column(String(100))
    market_slug = Column(String(200))
    url = Column(String(500))

    # Resolution
    outcome = Column(String(10))
    outcome_prices = Column(JSONB)
    resolution_source = Column(String(500))
    uma_proposal_id = Column(String(100))

    # Risk flags
    manipulation_risk_score = Column(Numeric(5, 2))  # 0-10 scale
    oracle_attack_detected = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    end_date = Column(TIMESTAMP)
    resolution_date = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    positions = relationship("Position", back_populates="market")
    order_books = relationship("OrderBook", back_populates="market")

    __table_args__ = (
        Index('idx_markets_active', 'active', 'closed'),
        Index('idx_markets_category', 'category'),
        Index('idx_markets_end_date', 'end_date'),
        Index('idx_markets_volume', 'volume_24h'),
        Index('idx_markets_liquidity', 'liquidity'),
    )

    def __repr__(self):
        return f"<Market(id={self.condition_id[:12]}, question={self.question[:50]})>"


class OrderBook(Base):
    """
    Order book snapshot - time-series data for microstructure analysis.
    Used for slippage modeling and liquidity assessment.
    """
    __tablename__ = 'order_books'

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String(66), ForeignKey('markets.condition_id', ondelete='CASCADE'), nullable=False)
    token_id = Column(String(78), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, index=True)

    # Best bid/ask
    best_bid = Column(Numeric(10, 6))
    best_ask = Column(Numeric(10, 6))
    bid_size = Column(Numeric(20, 6))
    ask_size = Column(Numeric(20, 6))

    # Full book depth (top 10 levels each side)
    bids = Column(JSONB)  # [{price: 0.55, size: 1000}, ...]
    asks = Column(JSONB)

    # Computed metrics
    spread = Column(Numeric(10, 6))
    spread_bps = Column(Integer)  # Basis points
    mid_price = Column(Numeric(10, 6))
    micro_price = Column(Numeric(10, 6))  # Volume-weighted mid
    book_imbalance = Column(Numeric(10, 4))  # (bid_vol - ask_vol) / (bid_vol + ask_vol)

    # Liquidity within X% of mid
    liquidity_2pct = Column(Numeric(20, 2))  # Liquidity within 2% of mid
    liquidity_5pct = Column(Numeric(20, 2))

    # Relationships
    market = relationship("Market", back_populates="order_books")

    __table_args__ = (
        Index('idx_orderbook_market_time', 'market_id', 'timestamp'),
        Index('idx_orderbook_token_time', 'token_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<OrderBook(market={self.market_id[:12]}, mid={self.mid_price}, spread={self.spread})>"


class Trade(Base):
    """
    Trade model - comprehensive execution tracking.
    Stores both whale trades (copied) and our own trade executions.
    """
    __tablename__ = 'trades'

    trade_id = Column(String(100), primary_key=True)
    trader_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)

    # Market identifiers
    market_id = Column(String(66), nullable=False)
    condition_id = Column(String(66))
    token_id = Column(String(78), nullable=False)
    event_slug = Column(String(200))

    # Trade details
    side = Column(String(4), nullable=False)  # BUY, SELL
    size = Column(Numeric(20, 6), nullable=False)
    price = Column(Numeric(10, 6), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    fee_amount = Column(Numeric(20, 6))

    # Market context
    market_title = Column(Text)
    outcome = Column(String(10))  # YES, NO
    category = Column(Enum(Sector))

    # Execution details
    transaction_hash = Column(String(66))
    maker_address = Column(String(42))
    order_id = Column(String(100))

    # Microstructure
    pre_trade_price = Column(Numeric(10, 6))  # Price before trade
    post_trade_price = Column(Numeric(10, 6))  # Price after trade
    price_impact_pct = Column(Numeric(10, 6))  # % price move
    book_spread_at_trade = Column(Numeric(10, 6))

    # Copy trading metadata
    is_whale_trade = Column(Boolean, default=False, index=True)
    followed = Column(Boolean, default=False, index=True)
    our_order_id = Column(String(100))
    copy_mode = Column(Enum(CopyMode))
    copy_ratio = Column(Numeric(5, 4))  # What % of whale's size we copied
    copy_latency_ms = Column(Integer)  # How long after whale trade
    copy_reason = Column(Text)
    skip_reason = Column(Text)

    # Timestamps
    timestamp = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whale = relationship("Whale", back_populates="trades")

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name='check_trade_side'),
        CheckConstraint("outcome IN ('YES', 'NO', NULL)", name='check_trade_outcome'),
        Index('idx_trades_timestamp', 'timestamp'),
        Index('idx_trades_trader_time', 'trader_address', 'timestamp'),
        Index('idx_trades_market_time', 'market_id', 'timestamp'),
        Index('idx_trades_whale_followed', 'is_whale_trade', 'followed'),
        Index('idx_trades_category_time', 'category', 'timestamp'),
    )

    def __repr__(self):
        return f"<Trade(id={self.trade_id[:12]}, trader={self.trader_address[:8]}, {self.side} {self.size}@{self.price})>"


class Order(Base):
    """
    Order model - tracks our own order lifecycle.
    Links back to source whale trade for performance attribution.
    """
    __tablename__ = 'orders'

    order_id = Column(String(100), primary_key=True)

    # Market identifiers
    market_id = Column(String(66), nullable=False)
    token_id = Column(String(78), nullable=False)

    # Order details
    side = Column(String(4), nullable=False)
    order_type = Column(String(10), nullable=False)  # LIMIT, MARKET, FOK, FAK, GTC
    price = Column(Numeric(10, 6))
    size = Column(Numeric(20, 6), nullable=False)
    filled_size = Column(Numeric(20, 6), default=0)
    remaining_size = Column(Numeric(20, 6))
    avg_fill_price = Column(Numeric(10, 6))

    # Execution quality
    slippage_pct = Column(Numeric(10, 6))  # vs intended price
    slippage_cost = Column(Numeric(20, 2))  # $ impact

    # Status
    status = Column(String(20), nullable=False, default='PENDING')

    # Copy trading metadata
    source_whale = Column(String(42), ForeignKey('whales.address', ondelete='SET NULL'))
    source_trade_id = Column(String(100))
    copy_mode = Column(Enum(CopyMode))
    copy_ratio = Column(Numeric(5, 4))

    # Execution tracking
    fills = Column(JSONB, default=[])  # [{price, size, timestamp}, ...]
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # EIP-712 signature
    signature = Column(String(132))  # Signed order hash
    nonce = Column(Integer)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    submitted_at = Column(TIMESTAMP)
    filled_at = Column(TIMESTAMP)
    cancelled_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    source_whale_rel = relationship("Whale", back_populates="orders")

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name='check_order_side'),
        CheckConstraint(
            "order_type IN ('LIMIT', 'MARKET', 'FOK', 'FAK', 'GTC')",
            name='check_order_type'
        ),
        CheckConstraint(
            "status IN ('PENDING', 'OPEN', 'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'FAILED')",
            name='check_order_status'
        ),
        Index('idx_orders_status_time', 'status', 'created_at'),
        Index('idx_orders_source_whale', 'source_whale'),
        Index('idx_orders_market', 'market_id'),
    )

    def __repr__(self):
        return f"<Order(id={self.order_id[:12]}, {self.status}, {self.side} {self.size}@{self.price})>"


class Position(Base):
    """
    Position model - tracks open and closed positions.
    Enhanced with risk management and stop-loss tracking.
    """
    __tablename__ = 'positions'

    position_id = Column(String(100), primary_key=True)
    user_address = Column(String(42), nullable=False, index=True)

    # Market identifiers
    market_id = Column(String(66), nullable=False, index=True)
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
    unrealized_pnl = Column(Numeric(20, 2))
    realized_pnl = Column(Numeric(20, 2), default=0)
    percent_pnl = Column(Numeric(10, 2))

    # Fees
    total_fees_paid = Column(Numeric(20, 2), default=0)

    # Market info
    market_title = Column(Text)
    category = Column(Enum(Sector))
    end_date = Column(TIMESTAMP)
    redeemable = Column(Boolean, default=False)

    # Risk management
    stop_loss_price = Column(Numeric(10, 6))
    take_profit_price = Column(Numeric(10, 6))
    max_loss_limit = Column(Numeric(20, 2))  # $ amount
    risk_score = Column(Numeric(10, 4))  # 0-10 scale
    days_to_expiry = Column(Integer)

    # Exit rules
    exit_at_timestamp = Column(TIMESTAMP)  # Pre-resolution exit time
    exit_reason = Column(String(50))  # stop_loss, take_profit, time_exit, manual, resolution

    # Copy trading metadata
    source_whale = Column(String(42), ForeignKey('whales.address', ondelete='SET NULL'))
    entry_trade_id = Column(String(100))
    entry_order_id = Column(String(100))
    exit_order_id = Column(String(100))

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

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED', 'LIQUIDATED')", name='check_position_status'),
        CheckConstraint("outcome IN ('YES', 'NO', NULL)", name='check_position_outcome'),
        Index('idx_positions_user_status', 'user_address', 'status'),
        Index('idx_positions_market', 'market_id'),
        Index('idx_positions_source_whale', 'source_whale'),
        Index('idx_positions_status', 'status'),
        Index('idx_positions_pnl', 'percent_pnl'),
    )

    def __repr__(self):
        return f"<Position(id={self.position_id[:12]}, whale={self.source_whale[:8] if self.source_whale else 'N/A'}, pnl={self.unrealized_pnl})>"


# =============================================================================
# PERFORMANCE & ANALYTICS TABLES
# =============================================================================

class PerformanceMetric(Base):
    """
    Performance metrics - rolling window calculations.
    Tracks portfolio, whale, and strategy performance over multiple timeframes.
    """
    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False)  # whale, portfolio, strategy
    entity_id = Column(String(100), nullable=False)

    # Time window
    window_days = Column(Integer, nullable=False)

    # Trade statistics
    total_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))
    avg_trade_pnl = Column(Numeric(20, 2))
    total_pnl = Column(Numeric(20, 2))
    roi = Column(Numeric(10, 2))

    # Risk-adjusted metrics
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    calmar_ratio = Column(Numeric(10, 4))
    information_ratio = Column(Numeric(10, 4))

    # Risk metrics
    max_drawdown = Column(Numeric(10, 2))
    max_drawdown_duration_days = Column(Integer)
    volatility = Column(Numeric(10, 4))
    downside_deviation = Column(Numeric(10, 4))
    var_95 = Column(Numeric(20, 2))  # Value at Risk 95%
    cvar_95 = Column(Numeric(20, 2))  # Conditional VaR

    # Other metrics
    profit_factor = Column(Numeric(10, 4))
    k_ratio = Column(Numeric(10, 4))
    ulcer_index = Column(Numeric(10, 4))

    # Efficiency metrics
    avg_time_in_trade_hours = Column(Numeric(10, 2))
    capital_efficiency = Column(Numeric(10, 4))

    # Metadata
    calculated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    period_start = Column(TIMESTAMP, nullable=False)
    period_end = Column(TIMESTAMP, nullable=False)

    __table_args__ = (
        CheckConstraint("entity_type IN ('whale', 'portfolio', 'strategy')", name='check_entity_type'),
        Index('idx_perf_entity_time', 'entity_type', 'entity_id', 'calculated_at'),
        Index('idx_perf_window', 'window_days', 'calculated_at'),
    )

    def __repr__(self):
        return f"<PerformanceMetric({self.entity_type}={self.entity_id}, {self.window_days}d, sharpe={self.sharpe_ratio})>"


# =============================================================================
# RISK & MANIPULATION DETECTION TABLES
# =============================================================================

class ManipulationFlag(Base):
    """
    Manipulation detection - flags suspicious whale behavior.
    Implements real-time firewall against spoofing, wash trading, oracle attacks.
    """
    __tablename__ = 'manipulation_flags'

    id = Column(Integer, primary_key=True, autoincrement=True)
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)

    # Flag type
    flag_type = Column(String(50), nullable=False)  # spoofing, wash_trading, oracle_attack, pump_dump
    severity = Column(String(20), nullable=False)  # low, medium, high, critical

    # Detection details
    detection_method = Column(String(100))  # otr_threshold, temporal_correlation, uma_voting
    confidence_score = Column(Numeric(5, 4), nullable=False)  # 0-1

    # Evidence
    evidence = Column(JSONB)  # Store detection metrics
    related_trades = Column(ARRAY(String(100)))
    related_markets = Column(ARRAY(String(66)))

    # Action taken
    action = Column(String(50))  # quarantine, blacklist, alert, monitor
    auto_resolved = Column(Boolean, default=False)

    # Review
    reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String(100))
    reviewed_at = Column(TIMESTAMP)
    review_notes = Column(Text)

    # Timestamps
    flagged_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    resolved_at = Column(TIMESTAMP)

    # Relationships
    whale = relationship("Whale", back_populates="manipulation_flags")

    __table_args__ = (
        CheckConstraint(
            "flag_type IN ('spoofing', 'wash_trading', 'oracle_attack', 'pump_dump', 'coordinated')",
            name='check_flag_type'
        ),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='check_severity'),
        Index('idx_manip_whale_time', 'whale_address', 'flagged_at'),
        Index('idx_manip_type_severity', 'flag_type', 'severity'),
        Index('idx_manip_reviewed', 'reviewed', 'flagged_at'),
    )

    def __repr__(self):
        return f"<ManipulationFlag(whale={self.whale_address[:8]}, type={self.flag_type}, severity={self.severity})>"


class CircuitBreaker(Base):
    """
    Circuit breaker log - tracks portfolio-level risk events.
    Records when trading is halted due to risk limits being breached.
    """
    __tablename__ = 'circuit_breakers'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trigger details
    trigger_type = Column(String(50), nullable=False)  # daily_loss, max_drawdown, volatility_spike
    trigger_value = Column(Numeric(20, 2))
    threshold = Column(Numeric(20, 2))

    # Portfolio state at trigger
    portfolio_value = Column(Numeric(20, 2))
    portfolio_pnl_pct = Column(Numeric(10, 2))
    open_positions_count = Column(Integer)

    # Action
    action = Column(String(50), nullable=False)  # halt_trading, reduce_exposure, close_all
    duration_minutes = Column(Integer)  # How long halted

    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(String(100))  # manual, auto

    # Timestamps
    triggered_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('daily_loss', 'max_drawdown', 'volatility_spike', 'manipulation_detected', 'api_failure')",
            name='check_trigger_type'
        ),
        Index('idx_circuit_breaker_time', 'triggered_at'),
        Index('idx_circuit_breaker_resolved', 'resolved'),
    )

    def __repr__(self):
        return f"<CircuitBreaker(trigger={self.trigger_type}, value={self.trigger_value}, resolved={self.resolved})>"


# =============================================================================
# SYSTEM & EVENTS TABLES
# =============================================================================

class Event(Base):
    """Event model - system events, alerts, and audit trail"""
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20))

    # Event details
    title = Column(String(200), nullable=False)
    description = Column(Text)
    event_metadata = Column(JSONB, default={})

    # Related entities
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'))
    order_id = Column(String(100))
    position_id = Column(String(100))
    trade_id = Column(String(100))

    # Alert/notification
    alerted = Column(Boolean, default=False)
    alert_channel = Column(String(50))  # slack, pagerduty, email

    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(String(100))

    # Timestamps
    timestamp = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    __table_args__ = (
        CheckConstraint("severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='check_severity'),
        Index('idx_events_type_time', 'event_type', 'timestamp'),
        Index('idx_events_severity_time', 'severity', 'timestamp'),
        Index('idx_events_whale_time', 'whale_address', 'timestamp'),
    )

    def __repr__(self):
        return f"<Event(type={self.event_type}, severity={self.severity}, title={self.title[:30]})>"


class SystemState(Base):
    """System state model - tracks system status and configuration"""
    __tablename__ = 'system_state'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    value_type = Column(String(20))

    description = Column(Text)

    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    __table_args__ = (
        CheckConstraint("value_type IN ('string', 'number', 'boolean', 'json')", name='check_value_type'),
        Index('idx_system_state_key', 'key'),
    )

    def __repr__(self):
        return f"<SystemState(key={self.key}, value={self.value})>"


# =============================================================================
# AUTO-OPTIMIZATION TABLES
# =============================================================================

class OptimizationRun(Base):
    """
    Optimization run - tracks Safe Bayesian Optimization experiments.
    Records parameter tuning history for continuous improvement.
    """
    __tablename__ = 'optimization_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Optimization config
    algorithm = Column(String(50), nullable=False)  # SafeOpt, HCOPE, Bandits
    objective = Column(String(50), nullable=False)  # sharpe, roi, drawdown

    # Parameters tested
    parameters = Column(JSONB, nullable=False)  # {param_name: value, ...}

    # Results
    objective_value = Column(Numeric(15, 6))
    constraint_violations = Column(JSONB)  # {constraint_name: violation_amount}

    # Safety evaluation
    safety_score = Column(Numeric(5, 4))  # 0-1, from HCOPE
    max_drawdown_observed = Column(Numeric(10, 2))
    passed_safety_gate = Column(Boolean)

    # Deployment
    deployed = Column(Boolean, default=False)
    deployed_at = Column(TIMESTAMP)
    deployment_notes = Column(Text)

    # Metadata
    duration_seconds = Column(Integer)
    trades_simulated = Column(Integer)

    # Timestamps
    started_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    completed_at = Column(TIMESTAMP)

    __table_args__ = (
        Index('idx_opt_run_time', 'started_at'),
        Index('idx_opt_deployed', 'deployed', 'deployed_at'),
    )

    def __repr__(self):
        return f"<OptimizationRun(id={self.id}, obj={self.objective_value}, deployed={self.deployed})>"
