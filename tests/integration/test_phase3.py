import datetime
import pytest
import psycopg
from app.db import get_db_connection
from ml.predict import generate_and_persist_prediction


def get_fixtures():
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

            return user_id, ticker_id, model_id, version_id


def test_valid_prediction_insertion():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close, lower_bound, upper_bound,
                    probability_up, predicted_direction
                )
                VALUES (
                    %s, %s, %s, %s,
                    '2024-01-01', '2024-01-02', 1,
                    0.012500, 2500.0, 2450.0, 2550.0, 0.6500, 'UP'
                )
                RETURNING prediction_id;
            """, (user_id, ticker_id, model_id, version_id))
            pred_id = cur.fetchone()[0]
            assert pred_id is not None


def test_target_date_validation_trigger_rejects_past_or_same_day():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # target_date == prediction_date must fail
            with pytest.raises(psycopg.errors.RaiseException) as exc_info:
                cur.execute("""
                    INSERT INTO prediction (
                        user_id, ticker_id, model_id, version_id,
                        prediction_date, target_date, horizon_days,
                        predicted_log_return, predicted_close, lower_bound, upper_bound,
                        probability_up, predicted_direction
                    )
                    VALUES (%s, %s, %s, %s, '2024-01-05', '2024-01-05', 1, 0.01, 100.0, 90.0, 110.0, 0.5, 'UP');
                """, (user_id, ticker_id, model_id, version_id))
            assert "target_date" in str(exc_info.value)


def test_bounds_validation_trigger_rejects_out_of_bounds():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # predicted_close > upper_bound must fail
            with pytest.raises(psycopg.errors.RaiseException) as exc_info:
                cur.execute("""
                    INSERT INTO prediction (
                        user_id, ticker_id, model_id, version_id,
                        prediction_date, target_date, horizon_days,
                        predicted_log_return, predicted_close, lower_bound, upper_bound,
                        probability_up, predicted_direction
                    )
                    VALUES (%s, %s, %s, %s, '2024-01-05', '2024-01-06', 1, 0.01, 120.0, 90.0, 110.0, 0.5, 'UP');
                """, (user_id, ticker_id, model_id, version_id))
            assert "predicted_close" in str(exc_info.value)


def test_horizon_check_constraint():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # horizon_days = 7 (not in 1, 5, 21) must fail
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute("""
                    INSERT INTO prediction (
                        user_id, ticker_id, model_id, version_id,
                        prediction_date, target_date, horizon_days,
                        predicted_log_return, predicted_close, lower_bound, upper_bound,
                        probability_up, predicted_direction
                    )
                    VALUES (%s, %s, %s, %s, '2024-01-05', '2024-01-12', 7, 0.01, 100.0, 90.0, 110.0, 0.5, 'UP');
                """, (user_id, ticker_id, model_id, version_id))


def test_update_forbidden_trigger():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close, lower_bound, upper_bound,
                    probability_up, predicted_direction
                )
                VALUES (%s, %s, %s, %s, '2024-01-08', '2024-01-09', 1, 0.01, 2500.0, 2400.0, 2600.0, 0.6, 'UP')
                RETURNING prediction_id;
            """, (user_id, ticker_id, model_id, version_id))
            pred_id = cur.fetchone()[0]

            with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException)):
                cur.execute("UPDATE prediction SET predicted_close = 2550.0 WHERE prediction_id = %s;", (pred_id,))


def test_delete_forbidden_trigger():
    user_id, ticker_id, model_id, version_id = get_fixtures()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close, lower_bound, upper_bound,
                    probability_up, predicted_direction
                )
                VALUES (%s, %s, %s, %s, '2024-01-08', '2024-01-15', 5, 0.02, 2600.0, 2400.0, 2700.0, 0.65, 'UP')
                RETURNING prediction_id;
            """, (user_id, ticker_id, model_id, version_id))
            pred_id = cur.fetchone()[0]

            with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException)):
                cur.execute("DELETE FROM prediction WHERE prediction_id = %s;", (pred_id,))


def test_baseline_prediction_flow_end_to_end():
    # Test generating prediction from persisted historical prices
    res = generate_and_persist_prediction("RELIANCE", "naive_last", datetime.date(2023, 1, 10), horizon_days=1)
    assert res is not None
    assert res["prediction_id"] > 0
    assert res["predicted_direction"] in ("UP", "DOWN", "FLAT")

    # Read back from database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT predicted_close, predicted_direction 
                FROM prediction 
                WHERE prediction_id = %s;
            """, (res["prediction_id"],))
            row = cur.fetchone()
            assert row is not None
            assert float(row[0]) == float(res["predicted_close"])
            assert row[1] == res["predicted_direction"]
