-- Migration 005: Create Positions Table
-- Week 4: Position Management
-- Purpose: Track open positions with real-time P&L and risk controls

-- ==================== Positions Table ====================

CREATE TABLE IF NOT EXISTS positions (
    -- Identification
    position_id VARCHAR(64) PRIMARY KEY,
    whale_address VARCHAR(42) NOT NULL,
    token_id VARCHAR(128) NOT NULL,

    -- Position details
    side VARCHAR(10) NOT NULL CHECK (side IN ('YES', 'NO')),
    entry_size DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(10, 6) NOT NULL,
    entry_amount DECIMAL(20, 8) NOT NULL,  -- USD amount invested

    -- Current state
    current_size DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(10, 6),  -- Last updated price
    market_value DECIMAL(20, 8),   -- current_size * current_price

    -- P&L tracking
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    total_pnl DECIMAL(20, 8) GENERATED ALWAYS AS (unrealized_pnl + realized_pnl) STORED,
    pnl_percentage DECIMAL(10, 4),  -- (total_pnl / entry_amount) * 100

    -- Risk metrics
    max_drawdown DECIMAL(20, 8) DEFAULT 0,
    max_profit DECIMAL(20, 8) DEFAULT 0,
    stop_loss_price DECIMAL(10, 6),
    take_profit_price DECIMAL(10, 6),

    -- Position sizing (Kelly Criterion)
    kelly_fraction DECIMAL(5, 4) DEFAULT 0.50,  -- 50% default
    edge DECIMAL(10, 6),
    win_rate DECIMAL(5, 4),

    -- Lifecycle state
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSING', 'CLOSED', 'ARCHIVED')),

    -- Timestamps
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    price_last_updated_at TIMESTAMP,

    -- Metadata
    notes TEXT,
    close_reason VARCHAR(100),  -- 'STOP_LOSS', 'TAKE_PROFIT', 'MANUAL', 'WHALE_EXIT', 'PRE_RESOLUTION'

    -- Constraints
    CONSTRAINT valid_entry_size CHECK (entry_size > 0),
    CONSTRAINT valid_entry_price CHECK (entry_price >= 0.01 AND entry_price <= 0.99),
    CONSTRAINT valid_current_size CHECK (current_size >= 0),
    CONSTRAINT valid_kelly_fraction CHECK (kelly_fraction > 0 AND kelly_fraction <= 1)
);

-- Create indexes for fast queries
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_whale ON positions(whale_address);
CREATE INDEX idx_positions_token ON positions(token_id);
CREATE INDEX idx_positions_opened_at ON positions(opened_at DESC);
CREATE INDEX idx_positions_whale_status ON positions(whale_address, status);
CREATE INDEX idx_positions_active ON positions(status, opened_at) WHERE status = 'OPEN';

-- Index for P&L queries
CREATE INDEX idx_positions_pnl ON positions(total_pnl DESC) WHERE status = 'OPEN';


-- ==================== Position Updates Table ====================

CREATE TABLE IF NOT EXISTS position_updates (
    -- Identification
    id SERIAL PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL REFERENCES positions(position_id) ON DELETE CASCADE,

    -- Update details
    update_type VARCHAR(30) NOT NULL CHECK (update_type IN (
        'PRICE_UPDATE',
        'SIZE_INCREASE',
        'SIZE_DECREASE',
        'PARTIAL_CLOSE',
        'FULL_CLOSE',
        'STOP_LOSS_HIT',
        'TAKE_PROFIT_HIT',
        'MANUAL_ADJUSTMENT'
    )),

    -- Snapshot before update
    old_size DECIMAL(20, 8),
    old_price DECIMAL(10, 6),
    old_market_value DECIMAL(20, 8),
    old_unrealized_pnl DECIMAL(20, 8),

    -- New values
    new_size DECIMAL(20, 8),
    new_price DECIMAL(10, 6),
    new_market_value DECIMAL(20, 8),
    new_unrealized_pnl DECIMAL(20, 8),

    -- Metadata
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    reason TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,

    -- Foreign key
    CONSTRAINT fk_position FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE CASCADE
);

-- Create indexes for update history
CREATE INDEX idx_position_updates_position_id ON position_updates(position_id, timestamp DESC);
CREATE INDEX idx_position_updates_timestamp ON position_updates(timestamp DESC);
CREATE INDEX idx_position_updates_type ON position_updates(update_type);

-- Create GIN index for JSONB metadata
CREATE INDEX idx_position_updates_metadata ON position_updates USING GIN (metadata);


-- ==================== Triggers ====================

-- Update last_updated_at on positions
CREATE OR REPLACE FUNCTION update_positions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_positions_timestamp();

-- Calculate P&L percentage on update
CREATE OR REPLACE FUNCTION calculate_pnl_percentage()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entry_amount > 0 THEN
        NEW.pnl_percentage = ((NEW.unrealized_pnl + NEW.realized_pnl) / NEW.entry_amount) * 100;
    ELSE
        NEW.pnl_percentage = 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calculate_pnl
    BEFORE UPDATE ON positions
    FOR EACH ROW
    WHEN (NEW.unrealized_pnl IS DISTINCT FROM OLD.unrealized_pnl OR NEW.realized_pnl IS DISTINCT FROM OLD.realized_pnl)
    EXECUTE FUNCTION calculate_pnl_percentage();


-- ==================== Functions for Position Management ====================

-- Get total exposure (sum of all open positions)
CREATE OR REPLACE FUNCTION get_total_exposure()
RETURNS DECIMAL AS $$
BEGIN
    RETURN COALESCE(
        (SELECT SUM(market_value) FROM positions WHERE status = 'OPEN'),
        0
    );
END;
$$ LANGUAGE plpgsql;


-- Get position count by status
CREATE OR REPLACE FUNCTION get_position_counts()
RETURNS TABLE(
    status VARCHAR(20),
    count BIGINT,
    total_value DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.status,
        COUNT(*)::BIGINT,
        COALESCE(SUM(p.market_value), 0)
    FROM positions p
    GROUP BY p.status;
END;
$$ LANGUAGE plpgsql;


-- Get portfolio performance summary
CREATE OR REPLACE FUNCTION get_portfolio_performance(
    since_timestamp TIMESTAMP DEFAULT NOW() - INTERVAL '24 hours'
)
RETURNS TABLE(
    total_positions BIGINT,
    open_positions BIGINT,
    total_unrealized_pnl DECIMAL,
    total_realized_pnl DECIMAL,
    total_pnl DECIMAL,
    avg_pnl_percentage NUMERIC,
    winning_positions BIGINT,
    losing_positions BIGINT,
    win_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_positions,
        COUNT(*) FILTER (WHERE status = 'OPEN')::BIGINT as open_positions,
        COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
        COALESCE(SUM(realized_pnl), 0) as total_realized_pnl,
        COALESCE(SUM(unrealized_pnl + realized_pnl), 0) as total_pnl,
        CASE
            WHEN COUNT(*) > 0 THEN ROUND(AVG(pnl_percentage)::NUMERIC, 2)
            ELSE 0
        END as avg_pnl_percentage,
        COUNT(*) FILTER (WHERE (unrealized_pnl + realized_pnl) > 0)::BIGINT as winning_positions,
        COUNT(*) FILTER (WHERE (unrealized_pnl + realized_pnl) < 0)::BIGINT as losing_positions,
        CASE
            WHEN COUNT(*) > 0 THEN
                ROUND((COUNT(*) FILTER (WHERE (unrealized_pnl + realized_pnl) > 0)::NUMERIC / COUNT(*)::NUMERIC) * 100, 2)
            ELSE 0
        END as win_rate
    FROM positions
    WHERE opened_at >= since_timestamp;
END;
$$ LANGUAGE plpgsql;


-- Get positions requiring attention (stop loss/take profit)
CREATE OR REPLACE FUNCTION get_positions_requiring_action()
RETURNS TABLE(
    position_id VARCHAR(64),
    whale_address VARCHAR(42),
    token_id VARCHAR(128),
    current_price DECIMAL(10, 6),
    stop_loss_price DECIMAL(10, 6),
    take_profit_price DECIMAL(10, 6),
    unrealized_pnl DECIMAL(20, 8),
    pnl_percentage DECIMAL(10, 4),
    action_required VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.position_id,
        p.whale_address,
        p.token_id,
        p.current_price,
        p.stop_loss_price,
        p.take_profit_price,
        p.unrealized_pnl,
        p.pnl_percentage,
        CASE
            WHEN p.current_price <= p.stop_loss_price THEN 'STOP_LOSS'
            WHEN p.current_price >= p.take_profit_price THEN 'TAKE_PROFIT'
            ELSE 'NONE'
        END as action_required
    FROM positions p
    WHERE p.status = 'OPEN'
      AND (
          (p.stop_loss_price IS NOT NULL AND p.current_price <= p.stop_loss_price)
          OR
          (p.take_profit_price IS NOT NULL AND p.current_price >= p.take_profit_price)
      );
END;
$$ LANGUAGE plpgsql;


-- Get whale-specific positions
CREATE OR REPLACE FUNCTION get_whale_positions(whale_addr VARCHAR(42))
RETURNS TABLE(
    position_id VARCHAR(64),
    token_id VARCHAR(128),
    side VARCHAR(10),
    entry_price DECIMAL(10, 6),
    current_price DECIMAL(10, 6),
    current_size DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    pnl_percentage DECIMAL(10, 4),
    status VARCHAR(20),
    opened_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.position_id,
        p.token_id,
        p.side,
        p.entry_price,
        p.current_price,
        p.current_size,
        p.unrealized_pnl,
        p.pnl_percentage,
        p.status,
        p.opened_at
    FROM positions p
    WHERE p.whale_address = whale_addr
    ORDER BY p.opened_at DESC;
END;
$$ LANGUAGE plpgsql;


-- Check if adding new position would exceed limits
CREATE OR REPLACE FUNCTION check_position_limits(
    new_position_value DECIMAL,
    max_positions INTEGER DEFAULT 50,
    max_total_exposure DECIMAL DEFAULT 50000
)
RETURNS TABLE(
    can_add_position BOOLEAN,
    current_positions BIGINT,
    current_exposure DECIMAL,
    reason TEXT
) AS $$
DECLARE
    curr_positions BIGINT;
    curr_exposure DECIMAL;
BEGIN
    -- Get current counts
    SELECT COUNT(*) INTO curr_positions FROM positions WHERE status = 'OPEN';
    SELECT COALESCE(SUM(market_value), 0) INTO curr_exposure FROM positions WHERE status = 'OPEN';

    -- Check limits
    IF curr_positions >= max_positions THEN
        RETURN QUERY SELECT FALSE, curr_positions, curr_exposure,
            format('Position limit reached: %s/%s', curr_positions, max_positions);
    ELSIF (curr_exposure + new_position_value) > max_total_exposure THEN
        RETURN QUERY SELECT FALSE, curr_positions, curr_exposure,
            format('Exposure limit would be exceeded: $%.2f + $%.2f > $%.2f',
                   curr_exposure, new_position_value, max_total_exposure);
    ELSE
        RETURN QUERY SELECT TRUE, curr_positions, curr_exposure, 'OK';
    END IF;
END;
$$ LANGUAGE plpgsql;


-- ==================== Comments ====================

COMMENT ON TABLE positions IS 'Open and closed trading positions with real-time P&L tracking';
COMMENT ON TABLE position_updates IS 'Audit trail of all position changes (price updates, size changes)';

COMMENT ON COLUMN positions.kelly_fraction IS 'Fractional Kelly used for position sizing (25-50% of optimal)';
COMMENT ON COLUMN positions.edge IS 'Edge used in Kelly calculation: avg_win / avg_loss';
COMMENT ON COLUMN positions.total_pnl IS 'Computed column: unrealized_pnl + realized_pnl';
COMMENT ON COLUMN positions.stop_loss_price IS 'Auto-exit price for risk management (typically -15%)';
COMMENT ON COLUMN positions.take_profit_price IS 'Auto-exit price for profit taking';

COMMENT ON FUNCTION get_total_exposure IS 'Calculate total market value of all open positions';
COMMENT ON FUNCTION get_portfolio_performance IS 'Get comprehensive portfolio performance metrics';
COMMENT ON FUNCTION get_positions_requiring_action IS 'Find positions that need stop-loss or take-profit execution';
COMMENT ON FUNCTION check_position_limits IS 'Validate if new position would exceed risk limits';


-- ==================== Sample Queries ====================

-- Query: Get all open positions sorted by P&L
-- SELECT * FROM positions WHERE status = 'OPEN' ORDER BY total_pnl DESC;

-- Query: Get portfolio performance for last 7 days
-- SELECT * FROM get_portfolio_performance(NOW() - INTERVAL '7 days');

-- Query: Get positions requiring action (stop loss/take profit)
-- SELECT * FROM get_positions_requiring_action();

-- Query: Get whale-specific positions
-- SELECT * FROM get_whale_positions('0x1234...');

-- Query: Check if can add new $500 position
-- SELECT * FROM check_position_limits(500, 50, 50000);

-- Query: Get position update history
-- SELECT pu.* FROM position_updates pu
-- WHERE pu.position_id = 'pos_xyz'
-- ORDER BY pu.timestamp DESC LIMIT 10;

-- Query: Get total exposure
-- SELECT get_total_exposure();

-- Query: Get position counts by status
-- SELECT * FROM get_position_counts();

-- Query: Get top 10 profitable positions
-- SELECT position_id, token_id, whale_address, total_pnl, pnl_percentage
-- FROM positions
-- WHERE status = 'OPEN'
-- ORDER BY total_pnl DESC
-- LIMIT 10;
