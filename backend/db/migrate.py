import os
import sys
from pathlib import Path
from backend.db.connection import get_db_connection, is_postgres, DATABASE_URL

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

SQLITE_FALLBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS baby_vitals (
    time TEXT NOT NULL,
    state VARCHAR(20) NOT NULL,
    breathing_rate REAL,
    heart_rate REAL,
    confidence REAL,
    motion_index REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_baby_vitals_time ON baby_vitals (time DESC);
CREATE INDEX IF NOT EXISTS idx_baby_vitals_state ON baby_vitals (state);

CREATE TABLE IF NOT EXISTS soothe_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_at TEXT NOT NULL,
    resolved_at TEXT,
    voice_snippet_used TEXT,
    was_successful BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_soothe_events_triggered_at ON soothe_events (triggered_at DESC);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TABLE IF NOT EXISTS babies (
    id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    bedtime TEXT DEFAULT '20:00',
    wake_time TEXT DEFAULT '07:00',
    voice_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_babies_parent_id ON babies (parent_id);
"""

def run_migrations():
    """Runs database migrations for Tiger Data / PostgreSQL or fallback SQLite."""
    print("=" * 60)
    print("CradleEcho Database Migration (Dev 4)")
    print("=" * 60)

    with get_db_connection() as conn:
        import sqlite3
        if isinstance(conn, sqlite3.Connection):
            print("Target: SQLite (cradleecho_local.db)")
            conn.executescript(SQLITE_FALLBACK_SCHEMA)
            print("Successfully migrated tables ('users', 'babies', 'baby_vitals', 'soothe_events') to SQLite!")
        else:
            print(f"Target: PostgreSQL / Tiger Data ({DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'PostgreSQL'})")
            if not SCHEMA_PATH.exists():
                print(f"Error: Schema file not found at {SCHEMA_PATH}")
                sys.exit(1)
            sql_content = SCHEMA_PATH.read_text(encoding="utf-8")
            cur = conn.cursor()
            try:
                print("Executing schema.sql on Tiger Data PostgreSQL...")
                cur.execute(sql_content)
            finally:
                cur.close()
            print("Successfully migrated tables ('users', 'babies', 'baby_vitals', 'soothe_events') on Tiger Data!")

    print("Migration complete. Tables ready for telemetry ingestion and queries.")
    print("=" * 60)

if __name__ == "__main__":
    run_migrations()
