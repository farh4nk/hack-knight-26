import os
import time
import logging
from contextlib import contextmanager
from typing import Generator, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cradleecho.db")

DATABASE_URL = os.getenv("DATABASE_URL", "")
_PG_LAST_FAILED_TIME = 0.0
_PG_FAILURE_COOLDOWN = 60.0  # seconds cooldown after connection failure before retrying

def _is_pg_configured() -> bool:
    return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

def _is_pg_cooldown_active() -> bool:
    global _PG_LAST_FAILED_TIME
    return (time.time() - _PG_LAST_FAILED_TIME) < _PG_FAILURE_COOLDOWN

def is_postgres(conn: Optional[Any] = None) -> bool:
    """Returns True if the connection or configured database is PostgreSQL/Tiger Data.
    When a conn object is passed, directly checks if it is a SQLite connection.
    """
    if conn is not None:
        import sqlite3
        return not isinstance(conn, sqlite3.Connection)
    return _is_pg_configured() and not _is_pg_cooldown_active()

def get_connection_string() -> str:
    # Tiger Data and Heroku/Render sometimes use postgres:// which psycopg prefers as postgresql://
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url

@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Context manager yielding a database connection.
    Connects to Tiger Data / PostgreSQL if DATABASE_URL is set,
    otherwise falls back to local SQLite for local testing without blocking.
    """
    global _PG_LAST_FAILED_TIME

    if _is_pg_configured() and not _is_pg_cooldown_active():
        try:
            import psycopg
            from psycopg.rows import dict_row

            conn = psycopg.connect(get_connection_string(), row_factory=dict_row, connect_timeout=3)
            _PG_LAST_FAILED_TIME = 0.0
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return
        except Exception as e:
            _PG_LAST_FAILED_TIME = time.time()
            logger.warning(f"PostgreSQL / Tiger Data unreachable ({e}). Falling back to local SQLite (cooldown {_PG_FAILURE_COOLDOWN}s).")

    import sqlite3

    db_path = os.getenv("SQLITE_PATH", "cradleecho_local.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def test_connection() -> bool:
    """Tests if the database can be connected to and executed."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1;")
                row = cur.fetchone()
                return bool(row)
            finally:
                cur.close()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
