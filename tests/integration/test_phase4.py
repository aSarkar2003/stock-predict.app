import datetime
import pytest
import psycopg
import pandas as pd
import numpy as np
from app.db import get_db_connection
from ml.scorecards import refresh_scorecard_materialized_view, compute_independent_pandas_metrics
from ml.resolve import resolve_predictions_for_ticker
from ml.models.prophet_model import ProphetForecaster, PROPHET_AVAILABLE


def setup_resolution_fixtures():
    """Sets up deterministic prices and a prediction for resolution testing."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM app_user LIMIT 1;")
            user_id = cur.fetchone()[0]

            cur.execute("SELECT ticker_id FROM stock_ticker WHERE symbol = 'RELIANCE';")
            ticker_id = cur.fetchone()[0]

            cur.execute("SELECT model_id FROM model WHERE name = 'naive_last';")
            model_id = cur.fetchone()[0]

            cur.execute("SELECT version_id FROM model_version WHERE model_id = %s LIMIT 1;", (model_id,))
            version_id = cur.fetchone()[0]

            # Clear any previously conflicting test dates
            p_date = datetime.date(2023, 2, 1)
            t_date = datetime.date(2023, 2, 2)

            cur.execute("""
                INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, 2400.0, 2460.0, 2390.0, 2410.0, 100000)
                ON CONFLICT (ticker_id, price_date) DO UPDATE 
                SET open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price;
            """, (ticker_id, p_date))

            cur.execute("""
                INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, 2415.0, 2480.0, 2410.0, 2450.0, 120000)
                ON CONFLICT (ticker_id, price_date) DO UPDATE 
                SET open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price;
            """, (ticker_id, t_date))

            # Insert prediction
            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close,
                    lower_bound, upper_bound, probability_up, predicted_direction
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1, 0.016460, 2450.0, 2400.0, 2500.0, 0.7000, 'UP')
                RETURNING prediction_id;
            """, (user_id, ticker_id, model_id, version_id, p_date, t_date))
            pred_id = cur.fetchone()[0]

            return ticker_id, pred_id, model_id, version_id


def test_resolve_predictions_and_outcome_creation():
    ticker_id, pred_id, model_id, version_id = setup_resolution_fixtures()
    
    # Run resolution
    resolved = resolve_predictions_for_ticker(ticker_id)
    assert resolved >= 1

    # Verify outcome details
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT actual_close, direction_correct, absolute_error, inside_interval
                FROM prediction_outcome
                WHERE prediction_id = %s;
            """, (pred_id,))
            row = cur.fetchone()
            assert row is not None
            actual_close, dir_correct, abs_err, in_interval = row
            assert float(actual_close) == 2450.0
            assert dir_correct is True
            assert float(abs_err) == 0.0
            assert in_interval is True


def test_outcome_ledger_immutability():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT outcome_id FROM prediction_outcome LIMIT 1;")
            row = cur.fetchone()
            if not row:
                pytest.skip("No outcomes to test immutability on.")
            outcome_id = row[0]

            # UPDATE must fail
            with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException)):
                cur.execute("UPDATE prediction_outcome SET actual_close = 9999.0 WHERE outcome_id = %s;", (outcome_id,))


def test_auto_resolution_trigger_on_ingestion_completion():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker WHERE symbol = 'TCS';")
            ticker_id = cur.fetchone()[0]
            cur.execute("SELECT user_id FROM app_user LIMIT 1;")
            user_id = cur.fetchone()[0]
            cur.execute("SELECT model_id FROM model WHERE name = 'naive_last';")
            model_id = cur.fetchone()[0]
            cur.execute("SELECT version_id FROM model_version WHERE model_id = %s LIMIT 1;", (model_id,))
            version_id = cur.fetchone()[0]

            p_date = datetime.date(2023, 3, 1)
            t_date = datetime.date(2023, 3, 2)

            cur.execute("""
                INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, 3300.0, 3320.0, 3290.0, 3310.0, 50000)
                ON CONFLICT (ticker_id, price_date) DO NOTHING;
            """, (ticker_id, p_date))

            cur.execute("""
                INSERT INTO stock_price (ticker_id, price_date, open_price, high_price, low_price, close_price, volume)
                VALUES (%s, %s, 3315.0, 3350.0, 3310.0, 3340.0, 60000)
                ON CONFLICT (ticker_id, price_date) DO NOTHING;
            """, (ticker_id, t_date))

            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close,
                    lower_bound, upper_bound, probability_up, predicted_direction
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1, 0.009, 3340.0, 3200.0, 3500.0, 0.65, 'UP')
                RETURNING prediction_id;
            """, (user_id, ticker_id, model_id, version_id, p_date, t_date))
            pred_id = cur.fetchone()[0]

            # Ingestion run completion
            cur.execute("""
                INSERT INTO ingestion_run (ticker_id, status)
                VALUES (%s, 'RUNNING')
                RETURNING run_id;
            """, (ticker_id,))
            run_id = cur.fetchone()[0]

            cur.execute("""
                UPDATE ingestion_run
                SET status = 'SUCCESS', completed_at = CURRENT_TIMESTAMP
                WHERE run_id = %s;
            """, (run_id,))

            # Confirm auto-resolution created outcome
            cur.execute("SELECT outcome_id FROM prediction_outcome WHERE prediction_id = %s;", (pred_id,))
            assert cur.fetchone() is not None


def test_independent_pandas_vs_sql_scorecard_metrics():
    refresh_scorecard_materialized_view()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT model_id, version_id, ticker_id, horizon_days, sample_size,
                       direction_accuracy, mae, rmse, mean_log_loss, interval_coverage
                FROM mv_model_scorecard
                LIMIT 1;
            """)
            row = cur.fetchone()
            if not row:
                pytest.skip("Scorecard view is empty.")

            m_id, v_id, t_id, h_days, sql_n, sql_acc, sql_mae, sql_rmse, sql_loss, sql_cov = row

    # Compute independently via Pandas
    pd_metrics = compute_independent_pandas_metrics(m_id, v_id, t_id, h_days)

    assert sql_n == pd_metrics["sample_size"]
    assert float(sql_acc) == pytest.approx(pd_metrics["direction_accuracy"], abs=1e-3)
    assert float(sql_mae) == pytest.approx(pd_metrics["mae"], abs=1e-3)
    assert float(sql_rmse) == pytest.approx(pd_metrics["rmse"], abs=1e-3)
    assert float(sql_loss) == pytest.approx(pd_metrics["mean_log_loss"], abs=1e-3)
    assert float(sql_cov) == pytest.approx(pd_metrics["interval_coverage"], abs=1e-3)


def test_prophet_integration_fit_and_predict():
    if not PROPHET_AVAILABLE:
        pytest.skip("Prophet is not installed or available on this platform.")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker_id FROM stock_ticker WHERE symbol = 'RELIANCE';")
            ticker_id = cur.fetchone()[0]
            cur.execute("""
                SELECT price_date, close_price 
                FROM stock_price 
                WHERE ticker_id = %s 
                ORDER BY price_date ASC 
                LIMIT 60;
            """, (ticker_id,))
            rows = cur.fetchall()

    if len(rows) < 30:
        pytest.skip("Not enough prices in database for Prophet test.")

    df = pd.DataFrame(rows, columns=["price_date", "close_price"])
    forecaster = ProphetForecaster()
    forecast = forecaster.fit_and_predict(df, horizon_days=1)

    assert forecast["predicted_close"] > 0
    assert forecast["predicted_direction"] in ("UP", "DOWN", "FLAT")
    assert forecast["lower_bound"] <= forecast["predicted_close"] <= forecast["upper_bound"]
    assert 0.0 <= forecast["probability_up"] <= 1.0
