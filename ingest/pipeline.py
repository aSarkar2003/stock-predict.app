import json
import datetime
import math
from typing import Dict, Any, List, Optional
import psycopg
from app.db import get_db_connection
from ingest.providers.base import BaseMarketDataProvider
from ingest.providers.yfinance_provider import YFinanceProvider
from ingest.validate import validate_ohlcv_record


class IngestionPipeline:
    def __init__(self, provider: Optional[BaseMarketDataProvider] = None):
        self.provider = provider or YFinanceProvider()

    def run_for_ticker(
        self,
        symbol: str,
        start_date: datetime.date,
        end_date: datetime.date,
        exchange: str = "NSE",
    ) -> Dict[str, Any]:
        """
        Executes an idempotent ingestion run for a given ticker and date range.
        Stores invalid rows into ingestion_reject.
        Uses a database transaction to ensure atomicity.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Lookup ticker_id
                cur.execute(
                    "SELECT ticker_id FROM stock_ticker WHERE symbol = %s AND exchange = %s;",
                    (symbol, exchange),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Ticker {symbol} ({exchange}) not found in stock_ticker catalog.")
                ticker_id = row[0]

                # 2. Create ingestion_run
                cur.execute("""
                    INSERT INTO ingestion_run (ticker_id, status)
                    VALUES (%s, 'RUNNING')
                    RETURNING run_id;
                """, (ticker_id,))
                run_id = cur.fetchone()[0]

            try:
                # 3. Ingest corporate actions (splits)
                corp_actions = self.provider.fetch_corporate_actions(symbol, start_date, end_date)
                with conn.cursor() as cur:
                    for ca in corp_actions:
                        cur.execute("""
                            INSERT INTO corporate_action (ticker_id, action_date, action_type, split_ratio)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (ticker_id, action_date, action_type) DO UPDATE
                            SET split_ratio = EXCLUDED.split_ratio;
                        """, (ticker_id, ca["date"], ca["type"], ca.get("split_ratio")))

                # 4. Fetch daily OHLCV
                raw_records = self.provider.fetch_daily_ohlcv(symbol, start_date, end_date)
                ingested_count = 0
                rejected_count = 0

                with conn.cursor() as cur:
                    for rec in raw_records:
                        is_valid, reason = validate_ohlcv_record(rec)
                        if is_valid:
                            # Upsert into stock_price
                            cur.execute("""
                                INSERT INTO stock_price (
                                    ticker_id, price_date, open_price, high_price, low_price, close_price, volume, run_id
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (ticker_id, price_date) DO UPDATE
                                SET open_price = EXCLUDED.open_price,
                                    high_price = EXCLUDED.high_price,
                                    low_price = EXCLUDED.low_price,
                                    close_price = EXCLUDED.close_price,
                                    volume = EXCLUDED.volume,
                                    run_id = EXCLUDED.run_id;
                            """, (
                                ticker_id,
                                rec["date"],
                                rec["open"],
                                rec["high"],
                                rec["low"],
                                rec["close"],
                                rec["volume"],
                                run_id,
                            ))
                            ingested_count += 1
                        else:
                            # Sanitize payload for PostgreSQL JSON (replace NaNs with None)
                            clean_rec = {}
                            for k, v in rec.items():
                                if isinstance(v, float) and math.isnan(v):
                                    clean_rec[k] = None
                                else:
                                    clean_rec[k] = v

                            # Insert into ingestion_reject
                            cur.execute("""
                                INSERT INTO ingestion_reject (
                                    run_id, ticker_id, price_date, raw_payload, reason
                                )
                                VALUES (%s, %s, %s, %s, %s);
                            """, (
                                run_id,
                                ticker_id,
                                rec.get("date"),
                                json.dumps(clean_rec, default=str),
                                reason,
                            ))
                            rejected_count += 1

                    # 5. Mark ingestion_run as SUCCESS or PARTIAL
                    final_status = "PARTIAL" if (rejected_count > 0 and ingested_count > 0) else "SUCCESS"
                    if ingested_count == 0 and rejected_count > 0:
                        final_status = "FAILED"

                    cur.execute("""
                        UPDATE ingestion_run
                        SET status = %s,
                            records_ingested = %s,
                            records_rejected = %s,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE run_id = %s;
                    """, (final_status, ingested_count, rejected_count, run_id))

                return {
                    "run_id": run_id,
                    "ticker_id": ticker_id,
                    "status": final_status,
                    "ingested": ingested_count,
                    "rejected": rejected_count,
                }

            except Exception as e:
                try:
                    conn.rollback()
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE ingestion_run
                            SET status = 'FAILED',
                                error_message = %s,
                                completed_at = CURRENT_TIMESTAMP
                            WHERE run_id = %s;
                        """, (str(e), run_id))
                        conn.commit()
                except Exception:
                    pass
                raise e
