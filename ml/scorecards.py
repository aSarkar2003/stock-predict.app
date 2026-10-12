import os
import psycopg
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from app.db import get_ro_connection, get_db_connection
from app.config import settings


def refresh_scorecard_materialized_view():
    """Refreshes the mv_model_scorecard materialized view as app_owner."""
    conn = psycopg.connect(
        host=settings.PGHOST,
        port=settings.PGPORT,
        dbname=settings.PGDATABASE,
        user=settings.PGUSER_OWNER,
        password=settings.PGPASSWORD_OWNER,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW mv_model_scorecard;")
    finally:
        conn.close()


def get_model_scorecards() -> List[Dict[str, Any]]:
    """Retrieves all scorecard entries from mv_model_scorecard with model and ticker names."""
    with get_ro_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    m.name AS model_name,
                    mv.version_tag,
                    st.symbol AS ticker_symbol,
                    sc.horizon_days,
                    sc.sample_size,
                    sc.direction_accuracy,
                    sc.mae,
                    sc.rmse,
                    sc.mean_log_loss,
                    sc.interval_coverage,
                    sc.baseline_direction_accuracy,
                    sc.skill_score,
                    sc.is_reliable,
                    sc.verdict
                FROM mv_model_scorecard sc
                JOIN model m ON sc.model_id = m.model_id
                JOIN model_version mv ON sc.version_id = mv.version_id
                JOIN stock_ticker st ON sc.ticker_id = st.ticker_id
                ORDER BY m.name, st.symbol, sc.horizon_days;
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def compute_independent_pandas_metrics(
    model_id: int,
    version_id: int,
    ticker_id: int,
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Computes statistical performance metrics purely in pandas/NumPy
    independently from the SQL materialized view.
    """
    with get_ro_connection() as conn:
        df = pd.read_sql_query("""
            SELECT p.predicted_close, p.predicted_log_return, p.probability_up,
                   po.actual_close, po.actual_log_return, po.direction_correct,
                   po.log_loss, po.absolute_error, po.squared_error, po.inside_interval
            FROM prediction p
            JOIN prediction_outcome po ON p.prediction_id = po.prediction_id
            WHERE p.model_id = %s AND p.version_id = %s AND p.ticker_id = %s AND p.horizon_days = %s;
        """, conn, params=(model_id, version_id, ticker_id, horizon_days))

    if df.empty:
        return {"sample_size": 0}

    n = len(df)
    dir_acc = round(float(df["direction_correct"].astype(float).mean()), 4)
    mae = round(float(df["absolute_error"].astype(float).mean()), 4)
    rmse = round(float(np.sqrt(df["squared_error"].astype(float).mean())), 4)
    mean_log_loss = round(float(df["log_loss"].astype(float).mean()), 4)
    coverage = round(float(df["inside_interval"].astype(float).mean()), 4)

    return {
        "sample_size": n,
        "direction_accuracy": dir_acc,
        "mae": mae,
        "rmse": rmse,
        "mean_log_loss": mean_log_loss,
        "interval_coverage": coverage,
    }
