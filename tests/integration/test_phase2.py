import datetime
import pytest
import psycopg
from app.db import get_db_connection
from ingest.providers.base import BaseMarketDataProvider
from ingest.pipeline import IngestionPipeline
from ingest.worker import IngestionWorker
from ingest.validate import validate_ohlcv_record


class MockMarketDataProvider(BaseMarketDataProvider):
    """Deterministic mock provider for testing edge cases and acceptance tests."""

    def __init__(self, records=None, splits=None):
        self.records = records or []
        self.splits = splits or []

    def fetch_daily_ohlcv(self, symbol, start_date, end_date, exchange="NSE"):
        return self.records

    def fetch_corporate_actions(self, symbol, start_date, end_date, exchange="NSE"):
        return self.splits


def test_validator_rejects_negative_price_and_volume():
    # Negative open price
    bad_price = {
        "date": datetime.date(2023, 1, 1),
        "open": -10.0,
        "high": 100.0,
        "low": 90.0,
        "close": 95.0,
        "volume": 1000,
    }
    valid, reason = validate_ohlcv_record(bad_price)
    assert not valid
    assert "Negative price" in reason

    # Negative volume
    bad_vol = {
        "date": datetime.date(2023, 1, 1),
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": -100,
    }
    valid, reason = validate_ohlcv_record(bad_vol)
    assert not valid
    assert "Negative volume" in reason


def test_validator_rejects_ohlc_inconsistency():
    # High < Low
    inverted = {
        "date": datetime.date(2023, 1, 1),
        "open": 100.0,
        "high": 80.0,
        "low": 90.0,
        "close": 85.0,
        "volume": 100,
    }
    valid, reason = validate_ohlcv_record(inverted)
    assert not valid
    assert "lower than" in reason


def test_ingestion_idempotency():
    mock_data = [
        {"date": datetime.date(2023, 1, 2), "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 5000},
        {"date": datetime.date(2023, 1, 3), "open": 102.0, "high": 108.0, "low": 101.0, "close": 106.0, "volume": 6000},
    ]
    provider = MockMarketDataProvider(records=mock_data)
    pipeline = IngestionPipeline(provider=provider)

    # First run
    res1 = pipeline.run_for_ticker("RELIANCE", datetime.date(2023, 1, 2), datetime.date(2023, 1, 3))
    assert res1["status"] == "SUCCESS"
    assert res1["ingested"] == 2

    # Second run (re-ingest same range)
    res2 = pipeline.run_for_ticker("RELIANCE", datetime.date(2023, 1, 2), datetime.date(2023, 1, 3))
    assert res2["status"] == "SUCCESS"
    assert res2["ingested"] == 2

    # Verify no duplicates were created
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM stock_price
                WHERE ticker_id = %s AND price_date IN ('2023-01-02', '2023-01-03');
            """, (res1["ticker_id"],))
            assert cur.fetchone()[0] == 2


def test_ingestion_rejects_logged_to_table():
    mock_data = [
        {"date": datetime.date(2023, 1, 4), "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 5000},
        {"date": datetime.date(2023, 1, 5), "open": 100.0, "high": 90.0, "low": 95.0, "close": 98.0, "volume": 1000},  # Invalid OHLC
    ]
    provider = MockMarketDataProvider(records=mock_data)
    pipeline = IngestionPipeline(provider=provider)

    res = pipeline.run_for_ticker("RELIANCE", datetime.date(2023, 1, 4), datetime.date(2023, 1, 5))
    assert res["status"] == "PARTIAL"
    assert res["ingested"] == 1
    assert res["rejected"] == 1

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT reason FROM ingestion_reject WHERE run_id = %s;
            """, (res["run_id"],))
            reject = cur.fetchone()
            assert reject is not None
            assert "High price" in reject[0]


def test_split_multiplier_function():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker WHERE symbol = 'RELIANCE';")
            ticker_id = cur.fetchone()[0]

            # Clear any previously inserted test splits for reliable clean test execution
            cur.execute("DELETE FROM corporate_action WHERE ticker_id = %s;", (ticker_id,))

            # Insert test split: 2:1 split on 2020-09-10
            cur.execute("""
                INSERT INTO corporate_action (ticker_id, ex_date, action_type, ratio)
                VALUES (%s, '2020-09-10', 'SPLIT', 2.0);
            """, (ticker_id,))

            # Multiplier as of 2020-01-01 (before split) should be 2.0
            cur.execute("SELECT fn_split_multiplier(%s, '2020-01-01');", (ticker_id,))
            mult_before = cur.fetchone()[0]
            assert float(mult_before) == 2.0

            # Multiplier as of 2020-12-01 (after split) should be 1.0
            cur.execute("SELECT fn_split_multiplier(%s, '2020-12-01');", (ticker_id,))
            mult_after = cur.fetchone()[0]
            assert float(mult_after) == 1.0


def test_job_queue_worker_claim_and_process():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_queue (job_type, payload, status)
                VALUES ('INGEST', '{"symbol": "TCS", "start_date": "2023-01-02", "end_date": "2023-01-03"}'::jsonb, 'PENDING')
                RETURNING job_id;
            """)
            job_id = cur.fetchone()[0]

    mock_provider = MockMarketDataProvider(records=[
        {"date": datetime.date(2023, 1, 2), "open": 3200.0, "high": 3250.0, "low": 3190.0, "close": 3220.0, "volume": 100000}
    ])
    pipeline = IngestionPipeline(provider=mock_provider)
    worker = IngestionWorker(pipeline=pipeline)

    claimed = worker.claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == job_id

    success = worker.process_job(claimed)
    assert success is True

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM job_queue WHERE job_id = %s;", (job_id,))
            assert cur.fetchone()[0] == "COMPLETED"
