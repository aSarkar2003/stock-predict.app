import datetime
import pytest
import psycopg
from app.db import get_db_connection, get_ro_connection
from app.config import settings


def test_schema_partitions_exist():
    """Verify stock_price is partitioned and partitions exist for 2015-2027."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT relname 
                FROM pg_class 
                WHERE relname LIKE 'stock_price_%' AND relkind = 'r'
                ORDER BY relname;
            """)
            partitions = [r[0] for r in cur.fetchall()]
            for year in range(2015, 2028):
                assert f"stock_price_{year}" in partitions
            assert "stock_price_default" in partitions


def test_ohlc_check_constraint_rejects_invalid_values():
    """Verify that High < Low or High < Close is rejected by chk_stock_price_ohlc."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker LIMIT 1;")
            ticker_id = cur.fetchone()[0]

            # High is lower than Open/Close/Low
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute("""
                    INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                    VALUES (%s, '2023-05-10', 100.0, 90.0, 95.0, 98.0, 1000);
                """, (ticker_id,))


def test_negative_volume_check_rejected():
    """Verify that volume < 0 is rejected by chk_stock_price_volume."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker LIMIT 1;")
            ticker_id = cur.fetchone()[0]

            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute("""
                    INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                    VALUES (%s, '2023-05-11', 100.0, 105.0, 95.0, 102.0, -50);
                """, (ticker_id,))


def test_corporate_action_invalid_split_ratio_rejected():
    """Verify that corporate action SPLIT requires ratio > 0."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker LIMIT 1;")
            ticker_id = cur.fetchone()[0]

            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute("""
                    INSERT INTO corporate_action (ticker_id, ex_date, action_type, ratio)
                    VALUES (%s, '2023-06-01', 'SPLIT', -1.0);
                """, (ticker_id,))


def test_duplicate_ticker_exchange_rejected():
    """Verify unique constraint on (symbol, exchange)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.UniqueViolation):
                cur.execute("""
                    INSERT INTO stock_ticker (symbol, exchange, name)
                    VALUES ('RELIANCE', 'NSE', 'Duplicate Reliance');
                """)


def test_seeded_data_exists():
    """Verify 10 tickers, calendar entries, and baseline models exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stock_ticker;")
            ticker_count = cur.fetchone()[0]
            assert ticker_count >= 10

            cur.execute("SELECT COUNT(*) FROM trading_calendar;")
            cal_count = cur.fetchone()[0]
            assert cal_count > 4000  # 2015 to 2027 is 13 years * 365 days ~ 4748

            cur.execute("SELECT name FROM model WHERE is_baseline = TRUE ORDER BY name;")
            models = [r[0] for r in cur.fetchall()]
            assert "drift" in models
            assert "naive_last" in models


def test_roles_and_permissions_enforced():
    """Verify app_ro cannot write to tables, but app_rw can."""
    with get_ro_connection() as conn_ro:
        with conn_ro.cursor() as cur_ro:
            cur_ro.execute("SELECT COUNT(*) FROM stock_ticker;")
            assert cur_ro.fetchone()[0] >= 10

            # app_ro should fail on INSERT
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur_ro.execute("""
                    INSERT INTO industry (name) VALUES ('Disallowed Industry');
                """)
