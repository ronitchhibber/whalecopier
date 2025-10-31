-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Whales table - tracks whale traders and their performance
CREATE TABLE IF NOT EXISTS whales (
    address VARCHAR(42) PRIMARY KEY,
    pseudonym VARCHAR(100),
    profile_image TEXT,

    -- Volume & trading stats
    total_volume DECIMAL(20,2) NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    active_positions INTEGER NOT NULL DEFAULT 0,
    avg_trade_size DECIMAL(20,2),
    avg_hold_time DECIMAL(10,2), -- hours

    -- Performance metrics
    win_rate DECIMAL(5,2),
    roi DECIMAL(10,2),
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,2),
    profit_factor DECIMAL(10,4),

    -- Category performance (JSON for flexibility)
    category_performance JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    quality_score DECIMAL(10,4),
    rank INTEGER,

    -- Timestamps
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_active TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Trades table - all whale trades (time-series data)
CREATE TABLE IF NOT EXISTS trades (
    trade_id VARCHAR(100) PRIMARY KEY,
    trader_address VARCHAR(42) NOT NULL,

    -- Market identifiers
    market_id VARCHAR(66) NOT NULL,
    condition_id VARCHAR(66),
    token_id VARCHAR(78) NOT NULL,
    event_slug VARCHAR(200),

    -- Trade details
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    size DECIMAL(20,6) NOT NULL,
    price DECIMAL(10,6) NOT NULL,
    amount DECIMAL(20,2) NOT NULL,
    fee_amount DECIMAL(20,6),

    -- Market context
    market_title TEXT,
    outcome VARCHAR(10),
    category VARCHAR(50),

    -- Execution details
    transaction_hash VARCHAR(66),
    maker_address VARCHAR(42),

    -- Copy trading metadata
    is_whale_trade BOOLEAN DEFAULT FALSE,
    followed BOOLEAN DEFAULT FALSE,
    our_order_id VARCHAR(100),
    copy_reason TEXT,
    skip_reason TEXT,

    -- Timestamps
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign key
    FOREIGN KEY (trader_address) REFERENCES whales(address) ON DELETE CASCADE
);

-- Convert trades to hypertable for efficient time-series queries
SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_trader ON trades(trader_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_market ON trades(market_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_whale_followed ON trades(is_whale_trade, followed);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_category ON trades(category, timestamp DESC);

-- Markets table - track market metadata
CREATE TABLE IF NOT EXISTS markets (
    condition_id VARCHAR(66) PRIMARY KEY,
    question TEXT NOT NULL,
    description TEXT,

    -- Market state
    active BOOLEAN DEFAULT TRUE,
    closed BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,

    -- Token IDs
    yes_token_id VARCHAR(78),
    no_token_id VARCHAR(78),

    -- Pricing (updated frequently)
    yes_price DECIMAL(10,6),
    no_price DECIMAL(10,6),
    volume DECIMAL(20,2),
    liquidity DECIMAL(20,2),
    open_interest DECIMAL(20,2),

    -- Market metadata
    category VARCHAR(50),
    tags TEXT[],
    event_id VARCHAR(100),
    market_slug VARCHAR(200),

    -- Resolution
    outcome VARCHAR(10),
    outcome_prices JSONB,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    end_date TIMESTAMP,
    resolution_date TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_markets_active ON markets(active, closed);
CREATE INDEX IF NOT EXISTS idx_markets_category ON markets(category);
CREATE INDEX IF NOT EXISTS idx_markets_end_date ON markets(end_date);

-- Positions table - track open positions (ours and whales')
CREATE TABLE IF NOT EXISTS positions (
    position_id VARCHAR(100) PRIMARY KEY,
    user_address VARCHAR(42) NOT NULL,

    -- Market identifiers
    market_id VARCHAR(66) NOT NULL,
    condition_id VARCHAR(66),
    token_id VARCHAR(78) NOT NULL,
    outcome VARCHAR(10),

    -- Position sizing
    size DECIMAL(20,6) NOT NULL,
    avg_entry_price DECIMAL(10,6) NOT NULL,
    current_price DECIMAL(10,6),

    -- P&L tracking
    initial_value DECIMAL(20,2) NOT NULL,
    current_value DECIMAL(20,2),
    cash_pnl DECIMAL(20,2),
    percent_pnl DECIMAL(10,2),
    realized_pnl DECIMAL(20,2) DEFAULT 0,

    -- Market info
    market_title TEXT,
    end_date TIMESTAMP,
    redeemable BOOLEAN DEFAULT FALSE,

    -- Risk management
    stop_loss_price DECIMAL(10,6),
    take_profit_price DECIMAL(10,6),
    risk_score DECIMAL(10,4),

    -- Copy trading metadata
    source_whale VARCHAR(42),
    entry_trade_id VARCHAR(100),

    -- Status
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'LIQUIDATED')),

    -- Timestamps
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign keys
    FOREIGN KEY (source_whale) REFERENCES whales(address) ON DELETE SET NULL,
    FOREIGN KEY (condition_id) REFERENCES markets(condition_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_address, status);
CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id);
CREATE INDEX IF NOT EXISTS idx_positions_source_whale ON positions(source_whale);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- Orders table - track order lifecycle
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(100) PRIMARY KEY,

    -- Market identifiers
    market_id VARCHAR(66) NOT NULL,
    token_id VARCHAR(78) NOT NULL,

    -- Order details
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('LIMIT', 'MARKET', 'FOK', 'GTC')),
    price DECIMAL(10,6),
    size DECIMAL(20,6) NOT NULL,
    filled_size DECIMAL(20,6) DEFAULT 0,
    remaining_size DECIMAL(20,6),
    avg_fill_price DECIMAL(10,6),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'OPEN', 'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'FAILED')),

    -- Copy trading metadata
    source_whale VARCHAR(42),
    source_trade_id VARCHAR(100),
    copy_ratio DECIMAL(5,4), -- What % of whale trade we copied

    -- Execution tracking
    fills JSONB DEFAULT '[]',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign keys
    FOREIGN KEY (source_whale) REFERENCES whales(address) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_source_whale ON orders(source_whale);
CREATE INDEX IF NOT EXISTS idx_orders_market ON orders(market_id);

-- Performance metrics table - rolling window calculations
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('whale', 'portfolio', 'strategy')),
    entity_id VARCHAR(100) NOT NULL,

    -- Time window
    window_days INTEGER NOT NULL,

    -- Performance metrics
    total_trades INTEGER,
    win_rate DECIMAL(5,2),
    avg_trade_pnl DECIMAL(20,2),
    total_pnl DECIMAL(20,2),
    roi DECIMAL(10,2),

    -- Risk-adjusted metrics
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),

    -- Risk metrics
    max_drawdown DECIMAL(10,2),
    volatility DECIMAL(10,4),
    var_95 DECIMAL(20,2), -- Value at Risk 95%

    -- Other metrics
    profit_factor DECIMAL(10,4),
    k_ratio DECIMAL(10,4),

    -- Metadata
    calculated_at TIMESTAMP NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    UNIQUE(entity_type, entity_id, window_days, calculated_at)
);

CREATE INDEX IF NOT EXISTS idx_perf_entity ON performance_metrics(entity_type, entity_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_perf_window ON performance_metrics(window_days, calculated_at DESC);

-- Events table - system events and alerts
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) CHECK (severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),

    -- Event details
    title VARCHAR(200) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',

    -- Related entities
    whale_address VARCHAR(42),
    order_id VARCHAR(100),
    position_id VARCHAR(100),

    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),

    -- Timestamps
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Foreign keys
    FOREIGN KEY (whale_address) REFERENCES whales(address) ON DELETE CASCADE
);

-- Convert events to hypertable
SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_whale ON events(whale_address, timestamp DESC);

-- System state table - track system status and circuit breakers
CREATE TABLE IF NOT EXISTS system_state (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    value_type VARCHAR(20) CHECK (value_type IN ('string', 'number', 'boolean', 'json')),

    description TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default system state values
INSERT INTO system_state (key, value, value_type, description) VALUES
    ('circuit_breaker_active', 'false', 'boolean', 'Whether trading is halted'),
    ('circuit_breaker_reason', '', 'string', 'Reason for circuit breaker activation'),
    ('daily_pnl', '0', 'number', 'Current daily P&L'),
    ('portfolio_value', '0', 'number', 'Current portfolio value'),
    ('peak_portfolio_value', '0', 'number', 'All-time high portfolio value'),
    ('total_positions', '0', 'number', 'Number of open positions'),
    ('active_whale_count', '0', 'number', 'Number of whales being tracked'),
    ('last_trade_timestamp', '', 'string', 'Timestamp of last executed trade'),
    ('system_start_time', NOW()::TEXT, 'string', 'When the system started')
ON CONFLICT (key) DO NOTHING;

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update timestamp trigger to relevant tables
CREATE TRIGGER update_whales_updated_at BEFORE UPDATE ON whales
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_markets_updated_at BEFORE UPDATE ON markets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_state_updated_at BEFORE UPDATE ON system_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create materialized view for quick whale rankings
CREATE MATERIALIZED VIEW IF NOT EXISTS whale_rankings AS
SELECT
    w.address,
    w.pseudonym,
    w.total_volume,
    w.win_rate,
    w.sharpe_ratio,
    w.quality_score,
    w.last_active,
    COUNT(DISTINCT p.position_id) as current_positions,
    COALESCE(SUM(p.cash_pnl), 0) as total_open_pnl,
    ROW_NUMBER() OVER (ORDER BY w.quality_score DESC NULLS LAST) as rank
FROM whales w
LEFT JOIN positions p ON w.address = p.source_whale AND p.status = 'OPEN'
WHERE w.is_active = TRUE
GROUP BY w.address, w.pseudonym, w.total_volume, w.win_rate, w.sharpe_ratio, w.quality_score, w.last_active
ORDER BY w.quality_score DESC NULLS LAST;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_whale_rankings_rank ON whale_rankings(rank);
CREATE INDEX IF NOT EXISTS idx_whale_rankings_score ON whale_rankings(quality_score DESC);

-- Create refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_whale_rankings()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY whale_rankings;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trader;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trader;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO trader;
