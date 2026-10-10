import os
import logging
from contextlib import contextmanager
from typing import Generator, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cradleecho.db")

DATABASE_URL = os.getenv("DATABASE_URL", "")

def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

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
    if is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(get_connection_string(), row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
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
