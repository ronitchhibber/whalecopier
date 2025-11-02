-- Migration 004: Create Orders and Order Transitions Tables
-- Week 3: Order Execution Engine
-- Purpose: Support order state machine with persistence and audit trail

-- ==================== Orders Table ====================

CREATE TABLE IF NOT EXISTS orders (
    -- Identification
    order_id VARCHAR(64) PRIMARY KEY,
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    exchange_order_id VARCHAR(128),

    -- Order details
    token_id VARCHAR(128) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    size DECIMAL(20, 8) NOT NULL,
    price DECIMAL(10, 6),  -- Nullable for market orders
    order_type VARCHAR(20) NOT NULL DEFAULT 'LIMIT' CHECK (order_type IN ('LIMIT', 'MARKET', 'FOK', 'GTC')),

    -- State tracking
    state VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    -- Execution details
    filled_size DECIMAL(20, 8) DEFAULT 0,
    remaining_size DECIMAL(20, 8),
    avg_fill_price DECIMAL(10, 6),

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Retry & error tracking
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,

    -- Indexes for common queries
    CONSTRAINT valid_size CHECK (size > 0),
    CONSTRAINT valid_price CHECK (price IS NULL OR (price >= 0.01 AND price <= 0.99))
);

-- Create indexes for fast lookups
CREATE INDEX idx_orders_state ON orders(state);
CREATE INDEX idx_orders_token_id ON orders(token_id);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_exchange_id ON orders(exchange_order_id) WHERE exchange_order_id IS NOT NULL;
CREATE INDEX idx_orders_idempotency ON orders(idempotency_key);

-- Create index for dead letter queue queries
CREATE INDEX idx_orders_dead_letter ON orders(state, retry_count) WHERE state = 'DEAD_LETTER';

-- Create index for stuck orders (PENDING too long)
CREATE INDEX idx_orders_pending ON orders(state, created_at) WHERE state = 'PENDING';


-- ==================== Order Transitions Table ====================

CREATE TABLE IF NOT EXISTS order_transitions (
    -- Identification
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,

    -- Transition details
    from_state VARCHAR(20) NOT NULL,
    to_state VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Metadata
    reason TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,

    -- Index for audit queries
    CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- Create indexes for transition history queries
CREATE INDEX idx_transitions_order_id ON order_transitions(order_id, timestamp DESC);
CREATE INDEX idx_transitions_timestamp ON order_transitions(timestamp DESC);
CREATE INDEX idx_transitions_states ON order_transitions(from_state, to_state);

-- Create GIN index for JSONB metadata queries
CREATE INDEX idx_transitions_metadata ON order_transitions USING GIN (metadata);


-- ==================== Triggers for Auto-Update ====================

-- Update updated_at timestamp on orders table
CREATE OR REPLACE FUNCTION update_orders_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_orders_timestamp();


-- ==================== Functions for Analytics ====================

-- Get order fill rate
CREATE OR REPLACE FUNCTION get_order_fill_rate(
    since_timestamp TIMESTAMP DEFAULT NOW() - INTERVAL '24 hours'
)
RETURNS TABLE(
    total_orders BIGINT,
    filled_orders BIGINT,
    partially_filled_orders BIGINT,
    failed_orders BIGINT,
    fill_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_orders,
        COUNT(*) FILTER (WHERE state = 'FILLED')::BIGINT as filled_orders,
        COUNT(*) FILTER (WHERE state = 'PARTIALLY_FILLED')::BIGINT as partially_filled_orders,
        COUNT(*) FILTER (WHERE state IN ('FAILED', 'DEAD_LETTER'))::BIGINT as failed_orders,
        CASE
            WHEN COUNT(*) > 0 THEN
                ROUND((COUNT(*) FILTER (WHERE state IN ('FILLED', 'CONFIRMED'))::NUMERIC / COUNT(*)::NUMERIC) * 100, 2)
            ELSE 0
        END as fill_rate
    FROM orders
    WHERE created_at >= since_timestamp;
END;
$$ LANGUAGE plpgsql;


-- Get average execution time
CREATE OR REPLACE FUNCTION get_avg_execution_time(
    since_timestamp TIMESTAMP DEFAULT NOW() - INTERVAL '24 hours'
)
RETURNS TABLE(
    avg_submission_time_ms NUMERIC,
    avg_fill_time_ms NUMERIC,
    avg_total_time_ms NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ROUND(AVG(EXTRACT(EPOCH FROM (submitted_at - created_at)) * 1000)::NUMERIC, 2) as avg_submission_time_ms,
        ROUND(AVG(EXTRACT(EPOCH FROM (filled_at - submitted_at)) * 1000)::NUMERIC, 2) as avg_fill_time_ms,
        ROUND(AVG(EXTRACT(EPOCH FROM (filled_at - created_at)) * 1000)::NUMERIC, 2) as avg_total_time_ms
    FROM orders
    WHERE created_at >= since_timestamp
      AND submitted_at IS NOT NULL
      AND filled_at IS NOT NULL
      AND state IN ('FILLED', 'CONFIRMED');
END;
$$ LANGUAGE plpgsql;


-- Get dead letter queue summary
CREATE OR REPLACE FUNCTION get_dead_letter_summary()
RETURNS TABLE(
    total_dead_letter BIGINT,
    error_summary JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_dead_letter,
        jsonb_object_agg(
            COALESCE(SUBSTRING(error_message FROM 1 FOR 50), 'Unknown'),
            cnt
        ) as error_summary
    FROM (
        SELECT error_message, COUNT(*) as cnt
        FROM orders
        WHERE state = 'DEAD_LETTER'
        GROUP BY error_message
        ORDER BY cnt DESC
        LIMIT 10
    ) sub;
END;
$$ LANGUAGE plpgsql;


-- ==================== Comments ====================

COMMENT ON TABLE orders IS 'Managed orders with complete lifecycle tracking';
COMMENT ON TABLE order_transitions IS 'Audit trail of all order state transitions';

COMMENT ON COLUMN orders.idempotency_key IS 'Unique key to prevent duplicate order submissions';
COMMENT ON COLUMN orders.exchange_order_id IS 'Order ID assigned by exchange (Polymarket CLOB)';
COMMENT ON COLUMN orders.retry_count IS 'Number of retry attempts for failed orders';
COMMENT ON COLUMN orders.state IS 'Current order state (PENDING, SUBMITTED, FILLED, etc.)';

COMMENT ON FUNCTION get_order_fill_rate IS 'Calculate order fill rate over specified time period';
COMMENT ON FUNCTION get_avg_execution_time IS 'Calculate average order execution times';
COMMENT ON FUNCTION get_dead_letter_summary IS 'Summarize orders in dead letter queue';


-- ==================== Sample Queries ====================

-- Query: Get stuck PENDING orders (older than 5 minutes)
-- SELECT * FROM orders WHERE state = 'PENDING' AND created_at < NOW() - INTERVAL '5 minutes';

-- Query: Get order transition history
-- SELECT * FROM order_transitions WHERE order_id = 'order_123' ORDER BY timestamp DESC;

-- Query: Get fill rate for last 24 hours
-- SELECT * FROM get_order_fill_rate(NOW() - INTERVAL '24 hours');

-- Query: Get average execution times
-- SELECT * FROM get_avg_execution_time();

-- Query: Get dead letter queue summary
-- SELECT * FROM get_dead_letter_summary();

-- Query: Get order with full transition history
-- SELECT o.*,
--        (SELECT json_agg(t ORDER BY t.timestamp DESC)
--         FROM order_transitions t
--         WHERE t.order_id = o.order_id) as transitions
-- FROM orders o
-- WHERE o.order_id = 'order_123';
