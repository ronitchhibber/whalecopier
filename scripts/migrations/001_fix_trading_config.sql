-- Migration: Fix trading_config table to match TradingConfig model
-- This migrates from the old key-value structure to the new structured table

-- Drop old trading_config table
DROP TABLE IF EXISTS trading_config CASCADE;

-- Create new trading_config table matching TradingConfig model
CREATE TABLE trading_config (
    id INTEGER PRIMARY KEY DEFAULT 1,

    -- Kill switch
    copy_trading_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Trading parameters
    max_position_size NUMERIC(20, 2) DEFAULT 1000.0,
    max_total_exposure NUMERIC(20, 2) DEFAULT 10000.0,
    max_positions INTEGER DEFAULT 1000,

    -- Metadata
    last_modified_at TIMESTAMP NOT NULL DEFAULT NOW(),
    modified_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default row with id=1
INSERT INTO trading_config (
    id,
    copy_trading_enabled,
    max_position_size,
    max_total_exposure,
    max_positions,
    modified_by
)
VALUES (
    1,
    TRUE,
    1000.0,
    10000.0,
    1000,
    'system'
)
ON CONFLICT (id) DO NOTHING;

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_trading_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger
DROP TRIGGER IF EXISTS update_trading_config_timestamp ON trading_config;
CREATE TRIGGER update_trading_config_timestamp
    BEFORE UPDATE ON trading_config
    FOR EACH ROW EXECUTE FUNCTION update_trading_config_updated_at();

-- Grant permissions
GRANT ALL PRIVILEGES ON trading_config TO postgres;
