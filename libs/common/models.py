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


class PositionStatus(PyEnum):
    """Status of a trade position"""
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"


class Side(PyEnum):
    """Trade side"""
    BUY = "buy"
    SELL = "sell"


class ManipulationSignal(PyEnum):
    """Type of detected manipulation"""
    WASH_TRADING = "wash_trading"
    SPOOFING = "spoofing"
    LAYERING = "layering"
    PUMP_AND_DUMP = "pump_and_dump"


# =============================================================================
# CORE TABLES
# =============================================================================

class Whale(Base):
    """
    Tracked whale trader with performance metrics and edge decay monitoring.

    Enhancements vs base:
    - Edge decay tracking (CUSUM)
    - Manipulation detection
    - Wallet clustering support
    """
    __tablename__ = 'whales'

    # Identity
    address = Column(String(42), primary_key=True)  # Ethereum address
    platform = Column(Enum(Platform), nullable=False, default=Platform.POLYMARKET, server_default='polymarket')
    cluster_id = Column(String(36), nullable=True)  # UUID for wallet clustering

    # Core performance metrics
    total_trades = Column(Integer, default=0)
    total_volume = Column(Numeric(20, 2), default=0.0)
    avg_trade_size = Column(Numeric(20, 2), default=0.0)
    quality_score = Column(Numeric(5, 2), default=0.0)  # 0-100

    # Risk-adjusted performance
    sharpe_ratio = Column(Numeric(10, 4), default=0.0)
    win_rate = Column(Numeric(5, 2), default=0.0)  # Percentage
    total_pnl = Column(Numeric(20, 2), default=0.0)
    roi = Column(Numeric(10, 4), default=0.0)  # Decimal (0.15 = 15%)
    max_drawdown = Column(Numeric(10, 4), default=0.0)

    # Edge decay detection (CUSUM)
    cusum_value = Column(Numeric(10, 4), default=0.0)
    cusum_threshold = Column(Numeric(10, 4), default=5.0)
    edge_degraded = Column(Boolean, default=False)
    last_cusum_update = Column(TIMESTAMP)

    # Manipulation detection
    manipulation_score = Column(Numeric(5, 2), default=0.0)  # 0-100, higher = more suspicious
    manipulation_alerts = Column(Integer, default=0)
    last_manipulation_check = Column(TIMESTAMP)

    # Copy trading control
    is_copying_enabled = Column(Boolean, default=True)
    copy_allocation = Column(Numeric(5, 4), default=0.0)  # Fraction of portfolio

    # Metadata
    first_seen = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    trades = relationship('Trade', back_populates='whale', cascade='all, delete-orphan')
    positions = relationship('Position', back_populates='whale', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('quality_score >= 0 AND quality_score <= 100', name='valid_quality_score'),
        CheckConstraint('win_rate >= 0 AND win_rate <= 100', name='valid_win_rate'),
        CheckConstraint('manipulation_score >= 0 AND manipulation_score <= 100', name='valid_manipulation_score'),
        Index('idx_whale_quality', 'quality_score'),
        Index('idx_whale_platform', 'platform'),
        Index('idx_whale_cluster', 'cluster_id'),
        Index('idx_whale_edge_degraded', 'edge_degraded'),
        Index('idx_whale_copying', 'is_copying_enabled'),
    )

    def __repr__(self):
        return f"<Whale(address={self.address[:10]}..., quality={self.quality_score}, win_rate={self.win_rate}%)>"


class Market(Base):
    """
    Prediction market with metadata and manipulation tracking.

    Enhancements:
    - Sector classification
    - Manipulation detection
    - Historical volatility
    """
    __tablename__ = 'markets'

    # Identity
    id = Column(String(66), primary_key=True)  # Market ID from platform
    platform = Column(Enum(Platform), nullable=False, default=Platform.POLYMARKET)

    # Market details
    title = Column(Text, nullable=False)
    description = Column(Text)
    sector = Column(Enum(Sector), default=Sector.OTHER)

    # Market state
    is_active = Column(Boolean, default=True)
    is_resolved = Column(Boolean, default=False)
    resolution_value = Column(Numeric(10, 2))  # Decimal representation (0.0 = NO, 1.0 = YES)

    # Market metrics
    total_volume = Column(Numeric(20, 2), default=0.0)
    liquidity = Column(Numeric(20, 2), default=0.0)
    current_price = Column(Numeric(10, 2), default=0.50)

    # Risk metrics
    volatility = Column(Numeric(10, 4), default=0.0)  # Historical volatility
    spread = Column(Numeric(10, 4), default=0.0)  # Bid-ask spread

    # Manipulation detection
    manipulation_score = Column(Numeric(5, 2), default=0.0)
    suspicious_activity_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    end_date = Column(TIMESTAMP)
    resolved_at = Column(TIMESTAMP)
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    trades = relationship('Trade', back_populates='market', cascade='all, delete-orphan')
    positions = relationship('Position', back_populates='market', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_market_active', 'is_active', 'is_resolved'),
        Index('idx_market_sector', 'sector'),
        Index('idx_market_platform', 'platform'),
        Index('idx_market_end_date', 'end_date'),
    )

    def __repr__(self):
        return f"<Market(id={self.id[:10]}..., title={self.title[:30]}...)>"


class Trade(Base):
    """
    Individual whale trade with execution details.

    Enhancements:
    - Copy trade tracking
    - Execution quality metrics
    """
    __tablename__ = 'trades'

    # Identity
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_hash = Column(String(66), unique=True, index=True)  # Blockchain transaction hash

    # References
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)
    market_id = Column(String(66), ForeignKey('markets.id', ondelete='CASCADE'), nullable=False)

    # Trade details
    side = Column(Enum(Side), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)  # Number of shares
    price = Column(Numeric(10, 2), nullable=False)  # Price per share (0-1)
    amount = Column(Numeric(20, 2), nullable=False)  # Total amount (size * price)

    # Copy trading
    was_copied = Column(Boolean, default=False)
    copy_trade_id = Column(Integer, ForeignKey('trades.id', ondelete='SET NULL'))  # Our mirrored trade

    # Execution quality
    slippage = Column(Numeric(10, 4))  # If copied, how much slippage vs whale
    execution_delay_ms = Column(Integer)  # Milliseconds between whale trade and copy

    # Timestamps
    timestamp = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    detected_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))

    # Relationships
    whale = relationship('Whale', back_populates='trades')
    market = relationship('Market', back_populates='trades')
    copy_trade = relationship('Trade', remote_side=[id], foreign_keys=[copy_trade_id])

    __table_args__ = (
        Index('idx_trade_whale', 'whale_address', 'timestamp'),
        Index('idx_trade_market', 'market_id', 'timestamp'),
        Index('idx_trade_timestamp', 'timestamp'),
        Index('idx_trade_copied', 'was_copied'),
    )

    def __repr__(self):
        return f"<Trade(id={self.id}, whale={self.whale_address[:10]}..., side={self.side.value}, amount=${self.amount})>"


class Position(Base):
    """
    Open or closed position from copy trading.

    Tracks our actual positions that resulted from copying whales.
    """
    __tablename__ = 'positions'

    # Identity
    id = Column(Integer, primary_key=True, autoincrement=True)

    # References
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'), nullable=False)
    market_id = Column(String(66), ForeignKey('markets.id', ondelete='CASCADE'), nullable=False)
    entry_trade_id = Column(Integer, ForeignKey('trades.id', ondelete='SET NULL'))
    exit_trade_id = Column(Integer, ForeignKey('trades.id', ondelete='SET NULL'))

    # Position details
    side = Column(Enum(Side), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)

    # Entry/exit prices
    entry_price = Column(Numeric(10, 2), nullable=False)
    exit_price = Column(Numeric(10, 2))
    current_price = Column(Numeric(10, 2))

    # PnL tracking
    realized_pnl = Column(Numeric(20, 2), default=0.0)
    unrealized_pnl = Column(Numeric(20, 2), default=0.0)

    # Position state
    status = Column(Enum(PositionStatus), default=PositionStatus.OPEN, nullable=False)

    # Timestamps
    opened_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    closed_at = Column(TIMESTAMP)
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    whale = relationship('Whale', back_populates='positions')
    market = relationship('Market', back_populates='positions')

    __table_args__ = (
        Index('idx_position_whale', 'whale_address', 'status'),
        Index('idx_position_market', 'market_id', 'status'),
        Index('idx_position_status', 'status'),
        Index('idx_position_opened', 'opened_at'),
    )

    def __repr__(self):
        return f"<Position(id={self.id}, whale={self.whale_address[:10]}..., status={self.status.value}, pnl=${self.realized_pnl})>"


# =============================================================================
# ADVANCED TRACKING TABLES
# =============================================================================

class WalletCluster(Base):
    """
    Clustered wallets (Sybil detection, whale identification).

    Groups related wallet addresses for:
    - Identifying the same whale across multiple wallets
    - Detecting Sybil attacks
    - Portfolio aggregation
    """
    __tablename__ = 'wallet_clusters'

    cluster_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cluster_name = Column(String(100))  # Human-readable name

    # Clustering confidence
    confidence_score = Column(Numeric(5, 2), default=0.0)  # 0-100
    clustering_method = Column(String(50))  # e.g., "behavioral", "on-chain", "manual"

    # Metadata
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))

    __table_args__ = (
        Index('idx_cluster_confidence', 'confidence_score'),
    )

    def __repr__(self):
        return f"<WalletCluster(id={self.cluster_id}, name={self.cluster_name})>"


class ManipulationEvent(Base):
    """
    Detected manipulation events (wash trading, spoofing, etc.)
    """
    __tablename__ = 'manipulation_events'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event details
    event_type = Column(Enum(ManipulationSignal), nullable=False)
    severity = Column(Numeric(5, 2), nullable=False)  # 0-100

    # Involved entities
    whale_addresses = Column(ARRAY(String))  # List of involved whales
    market_id = Column(String(66), ForeignKey('markets.id', ondelete='CASCADE'))
    trade_ids = Column(ARRAY(Integer))  # Involved trades

    # Detection details
    detection_method = Column(String(100))
    evidence = Column(JSONB)  # Store detailed evidence as JSON

    # Response
    action_taken = Column(String(50))  # e.g., "alert", "disable_whale", "ignore"
    resolved = Column(Boolean, default=False)

    # Timestamps
    detected_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    resolved_at = Column(TIMESTAMP)

    __table_args__ = (
        Index('idx_manipulation_type', 'event_type'),
        Index('idx_manipulation_severity', 'severity'),
        Index('idx_manipulation_resolved', 'resolved', 'detected_at'),
    )

    def __repr__(self):
        return f"<ManipulationEvent(id={self.id}, type={self.event_type.value}, severity={self.severity})>"


class PortfolioSnapshot(Base):
    """
    Daily portfolio snapshots for performance tracking.
    """
    __tablename__ = 'portfolio_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Portfolio metrics
    total_value = Column(Numeric(20, 2), nullable=False)
    cash_balance = Column(Numeric(20, 2), nullable=False)
    position_value = Column(Numeric(20, 2), nullable=False)

    # Performance
    daily_pnl = Column(Numeric(20, 2), default=0.0)
    total_pnl = Column(Numeric(20, 2), default=0.0)
    daily_return = Column(Numeric(10, 4), default=0.0)

    # Risk metrics
    var_95 = Column(Numeric(20, 2))  # Value at Risk (95%)
    sharpe_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))

    # Position breakdown
    open_positions_count = Column(Integer, default=0)
    positions_by_sector = Column(JSONB)  # {sector: count}

    # Timestamp
    snapshot_date = Column(TIMESTAMP, nullable=False, unique=True)

    __table_args__ = (
        Index('idx_snapshot_date', 'snapshot_date'),
    )

    def __repr__(self):
        return f"<PortfolioSnapshot(date={self.snapshot_date}, value=${self.total_value}, pnl=${self.daily_pnl})>"


class StrategyPerformance(Base):
    """
    Performance tracking for different copying strategies.

    Allows A/B testing of whale selection and position sizing strategies.
    """
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Strategy identification
    strategy_name = Column(String(100), nullable=False)
    strategy_params = Column(JSONB)  # Store strategy config as JSON

    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Numeric(5, 2), default=0.0)

    # Returns
    total_pnl = Column(Numeric(20, 2), default=0.0)
    total_return = Column(Numeric(10, 4), default=0.0)  # Percentage
    sharpe_ratio = Column(Numeric(10, 4), default=0.0)
    max_drawdown = Column(Numeric(10, 4), default=0.0)

    # Risk metrics
    avg_position_size = Column(Numeric(20, 2))
    max_position_size = Column(Numeric(20, 2))
    avg_holding_period_hours = Column(Numeric(10, 2))

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    strategy_start = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    last_updated = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))

    __table_args__ = (
        Index('idx_strategy_name', 'strategy_name'),
        Index('idx_strategy_active', 'is_active'),
        Index('idx_strategy_sharpe', 'sharpe_ratio'),
    )

    def __repr__(self):
        return f"<StrategyPerformance(name={self.strategy_name}, sharpe={self.sharpe_ratio}, win_rate={self.win_rate}%)>"


class Alert(Base):
    """
    System alerts (whale edge decay, manipulation, risk breaches, etc.)
    """
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Alert details
    alert_type = Column(String(50), nullable=False)  # e.g., "edge_decay", "manipulation", "risk_breach"
    severity = Column(String(20), nullable=False)  # "low", "medium", "high", "critical"
    message = Column(Text, nullable=False)

    # Related entities
    whale_address = Column(String(42), ForeignKey('whales.address', ondelete='CASCADE'))
    market_id = Column(String(66), ForeignKey('markets.id', ondelete='CASCADE'))

    # Alert data
    details = Column(JSONB)  # Additional context as JSON

    # Status
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'))
    acknowledged_at = Column(TIMESTAMP)
    resolved_at = Column(TIMESTAMP)

    __table_args__ = (
        Index('idx_alert_type', 'alert_type'),
        Index('idx_alert_severity', 'severity'),
        Index('idx_alert_unresolved', 'resolved', 'created_at'),
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, type={self.alert_type}, severity={self.severity})>"


# =============================================================================
# OPTIMIZATION & AUTO-TUNING TABLES
# =============================================================================

class OptimizationRun(Base):
    """
    Bayesian optimization runs for strategy parameter tuning.

    Tracks hyperparameter optimization experiments for:
    - Whale selection criteria
    - Position sizing
    - Entry/exit timing
    """
    __tablename__ = 'optimization_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Optimization setup
    strategy_name = Column(String(100), nullable=False)
    optimization_algorithm = Column(String(50), nullable=False)  # e.g., "bayesian", "grid_search"
    search_space = Column(JSONB)  # Parameter ranges

    # Tested parameters
    parameters = Column(JSONB, nullable=False)  # Actual tested values

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


# =============================================================================
# TRADING CONFIG TABLE
# =============================================================================

class TradingConfig(Base):
    """
    System-wide trading configuration with kill switch support.

    Single-row table that stores trading system state.
    """
    __tablename__ = 'trading_config'

    id = Column(Integer, primary_key=True, default=1)  # Always 1, enforced by application

    # Kill switch
    copy_trading_enabled = Column(Boolean, default=True, nullable=False)

    # Trading parameters
    max_position_size = Column(Numeric(20, 2), default=1000.0)
    max_total_exposure = Column(Numeric(20, 2), default=10000.0)
    max_positions = Column(Integer, default=1000)

    # Metadata
    last_modified_at = Column(TIMESTAMP, nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))
    modified_by = Column(String(100))  # User/system that made the change

    __table_args__ = (
        CheckConstraint('id = 1', name='single_row_only'),  # Enforce single row
    )

    def __repr__(self):
        return f"<TradingConfig(enabled={self.copy_trading_enabled}, modified={self.last_modified_at})>"
