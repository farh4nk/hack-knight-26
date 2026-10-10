-- ====================================================================
-- CradleEcho Database Schema
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

-- 4. User accounts (authenticated via Google OAuth)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,              -- Google Subject ID (sub)
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- 5. Children / Baby profiles linked to parent
CREATE TABLE IF NOT EXISTS babies (
    id VARCHAR(64) PRIMARY KEY,              -- UUID or generated ID
    parent_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    bedtime VARCHAR(5) DEFAULT '20:00',
    wake_time VARCHAR(5) DEFAULT '07:00',
    voice_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_babies_parent_id ON babies (parent_id);
