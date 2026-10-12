"""
Historical backfill script for seeded Indian equities.
Retrieves historical daily OHLCV from Yahoo Finance and persists to PostgreSQL.
Handles rate limits and reports ingestion progress.
"""
import datetime
import time
from app.db import get_ro_connection
from ingest.pipeline import IngestionPipeline
from ingest.providers.yfinance_provider import YFinanceProvider


def run_backfill(years: int = 10):
    pipeline = IngestionPipeline(provider=YFinanceProvider())
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=years * 365)

    print(f"Starting historical backfill for {years} years: {start_date} to {today}...")

    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, exchange FROM stock_ticker WHERE is_active = TRUE ORDER BY symbol;")
            tickers = cur.fetchall()

    total_ingested = 0
    total_rejected = 0

    for symbol, exchange in tickers:
        print(f"Backfilling {symbol} ({exchange})...")
        try:
            res = pipeline.run_for_ticker(symbol, start_date, today, exchange)
            print(f" -> {symbol}: status={res['status']}, ingested={res['ingested']}, rejected={res['rejected']}")
            total_ingested += res["ingested"]
            total_rejected += res["rejected"]
        except Exception as e:
            print(f" -> Failed to backfill {symbol}: {e}")
        time.sleep(1)  # Respect rate limits

    print(f"\nBackfill Complete: {total_ingested} rows ingested, {total_rejected} rows rejected.")


if __name__ == "__main__":
    run_backfill()
