-- ====================================================================
-- Cribby Database Schema
-- Target: Tiger Data (PostgreSQL + TimescaleDB) or standard PostgreSQL
-- ====================================================================

-- 1. Time-series baby vitals telemetry table
CREATE TABLE IF NOT EXISTS baby_vitals (
    time TIMESTAMPTZ NOT NULL,
    state VARCHAR(20) NOT NULL,
    breathing_rate DOUBLE PRECISION,
    heart_rate DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    motion_index DOUBLE PRECISION DEFAULT 0.0
);

-- Fast time-series indexes
CREATE INDEX IF NOT EXISTS idx_baby_vitals_time ON baby_vitals (time DESC);
CREATE INDEX IF NOT EXISTS idx_baby_vitals_state ON baby_vitals (state);

-- 2. Auto-soothe intervention events table
CREATE TABLE IF NOT EXISTS soothe_events (
    id SERIAL PRIMARY KEY,
    triggered_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    voice_snippet_used TEXT,
    was_successful BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_soothe_events_triggered_at ON soothe_events (triggered_at DESC);

-- 3. Timescale / Tiger Data Hypertable conversion (optional, enabled if Timescale is installed)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
    ) THEN
        PERFORM create_hypertable('baby_vitals', 'time', if_not_exists => TRUE);
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        -- Safely ignore if extension or hypertable already exists or permissions differ
        NULL;
END $$;
