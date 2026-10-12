from typing import Optional
from app.db import get_db_connection


def resolve_predictions_for_ticker(ticker_id: Optional[int] = None) -> int:
    """
    Calls stored database function fn_resolve_predictions.
    Grades all pending predictions where the target close price is available.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT fn_resolve_predictions(%s);", (ticker_id,))
            count = cur.fetchone()[0]
            return count


def get_pending_predictions_count(ticker_id: Optional[int] = None) -> int:
    """Returns number of pending predictions awaiting market observation."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if ticker_id is not None:
                cur.execute("SELECT COUNT(*) FROM v_pending_predictions WHERE ticker_id = %s;", (ticker_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM v_pending_predictions;")
            return cur.fetchone()[0]
