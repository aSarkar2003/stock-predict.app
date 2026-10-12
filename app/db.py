"""
Database connection pool, context managers, and utilities using psycopg 3.
Provides managed connection pooling with safe transaction boundaries.
"""
from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg_pool import ConnectionPool
from app.config import settings

# Construct DSNs for app_rw and app_ro
RW_DSN = (
    f"host={settings.PGHOST} port={settings.PGPORT} dbname={settings.PGDATABASE} "
    f"user={settings.PGUSER_RW} password={settings.PGPASSWORD_RW}"
)

RO_DSN = (
    f"host={settings.PGHOST} port={settings.PGPORT} dbname={settings.PGDATABASE} "
    f"user={settings.PGUSER_RO} password={settings.PGPASSWORD_RO}"
)

# Global connection pools initialized on demand
_rw_pool: ConnectionPool | None = None
_ro_pool: ConnectionPool | None = None


def get_rw_pool() -> ConnectionPool:
    global _rw_pool
    if _rw_pool is None or _rw_pool.closed:
        _rw_pool = ConnectionPool(
            conninfo=RW_DSN,
            min_size=2,
            max_size=10,
            timeout=10.0,
            open=True,
        )
    return _rw_pool


def get_ro_pool() -> ConnectionPool:
    global _ro_pool
    if _ro_pool is None or _ro_pool.closed:
        _ro_pool = ConnectionPool(
            conninfo=RO_DSN,
            min_size=1,
            max_size=5,
            timeout=10.0,
            open=True,
        )
    return _ro_pool


def close_pools():
    global _rw_pool, _ro_pool
    if _rw_pool is not None and not _rw_pool.closed:
        _rw_pool.close()
    if _ro_pool is not None and not _ro_pool.closed:
        _ro_pool.close()


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Yields a connection from the read-write pool within a managed transaction."""
    pool = get_rw_pool()
    with pool.connection() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def get_ro_connection() -> Generator[psycopg.Connection, None, None]:
    """Yields a connection from the read-only pool."""
    pool = get_ro_pool()
    with pool.connection() as conn:
        yield conn


def check_db_health() -> bool:
    """Checks database availability and connectivity."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                row = cur.fetchone()
                return bool(row and row[0] == 1)
    except Exception:
        return False

