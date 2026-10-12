import json
import datetime
from typing import Optional, Dict, Any
from app.db import get_db_connection
from ingest.pipeline import IngestionPipeline


class IngestionWorker:
    """Worker processing background ingestion jobs using FOR UPDATE SKIP LOCKED."""

    def __init__(self, pipeline: Optional[IngestionPipeline] = None):
        self.pipeline = pipeline or IngestionPipeline()

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Atomically claims a pending job using FOR UPDATE SKIP LOCKED.
        Returns job dictionary or None if queue is empty.
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT job_id, job_type, payload, attempts, max_attempts
                    FROM job_queue
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED;
                """)
                row = cur.fetchone()
                if not row:
                    return None

                job_id, job_type, payload, attempts, max_attempts = row
                cur.execute("""
                    UPDATE job_queue
                    SET status = 'PROCESSING',
                        started_at = CURRENT_TIMESTAMP,
                        attempts = attempts + 1
                    WHERE job_id = %s;
                """, (job_id,))
                
                return {
                    "job_id": job_id,
                    "job_type": job_type,
                    "payload": payload,
                    "attempts": attempts + 1,
                    "max_attempts": max_attempts,
                }

    def process_job(self, job: Dict[str, Any]) -> bool:
        job_id = job["job_id"]
        job_type = job["job_type"]
        payload = job["payload"]

        try:
            if job_type == "INGEST":
                symbol = payload["symbol"]
                start_date = datetime.date.fromisoformat(payload["start_date"])
                end_date = datetime.date.fromisoformat(payload["end_date"])
                exchange = payload.get("exchange", "NSE")

                self.pipeline.run_for_ticker(symbol, start_date, end_date, exchange)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE job_queue
                        SET status = 'COMPLETED',
                            completed_at = CURRENT_TIMESTAMP
                        WHERE job_id = %s;
                    """, (job_id,))
            return True

        except Exception as e:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE job_queue
                        SET status = 'FAILED',
                            error_message = %s,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE job_id = %s;
                    """, (str(e), job_id))
            return False
