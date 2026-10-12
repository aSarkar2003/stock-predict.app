import datetime
from typing import Dict, Any, Optional
import pandas as pd
from app.db import get_db_connection
from ml.models.naive_last import NaiveLastModel
from ml.models.drift import DriftModel


def get_target_trading_date(start_date: datetime.date, horizon_days: int) -> datetime.date:
    """Finds the Nth forward trading day using trading_calendar."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT calendar_date
                FROM trading_calendar
                WHERE calendar_date > %s AND is_trading_day = TRUE
                ORDER BY calendar_date ASC
                OFFSET %s LIMIT 1;
            """, (start_date, horizon_days - 1))
            row = cur.fetchone()
            if row:
                return row[0]
    # Fallback to weekday projection if calendar not populated
    curr = start_date
    added = 0
    while added < horizon_days:
        curr += datetime.timedelta(days=1)
        if curr.weekday() < 5:
            added += 1
    return curr


def generate_and_persist_prediction(
    ticker_symbol: str,
    model_name: str,
    as_of_date: datetime.date,
    horizon_days: int = 1,
    exchange: str = "NSE",
) -> Optional[Dict[str, Any]]:
    """
    Generates a forecast up to as_of_date without look-ahead bias
    and inserts it into the immutable prediction ledger.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Lookup user, ticker, model, version
            cur.execute("SELECT user_id FROM app_user WHERE role = 'analyst' LIMIT 1;")
            user_row = cur.fetchone()
            if not user_row:
                cur.execute("SELECT user_id FROM app_user LIMIT 1;")
                user_row = cur.fetchone()
            user_id = user_row[0]

            cur.execute(
                "SELECT ticker_id FROM stock_ticker WHERE symbol = %s AND exchange = %s;",
                (ticker_symbol, exchange),
            )
            t_row = cur.fetchone()
            if not t_row:
                raise ValueError(f"Ticker {ticker_symbol} not found.")
            ticker_id = t_row[0]

            cur.execute("SELECT model_id FROM model WHERE name = %s;", (model_name,))
            m_row = cur.fetchone()
            if not m_row:
                raise ValueError(f"Model {model_name} not found.")
            model_id = m_row[0]

            cur.execute(
                "SELECT version_id FROM model_version WHERE model_id = %s ORDER BY trained_at DESC LIMIT 1;",
                (model_id,),
            )
            v_row = cur.fetchone()
            if not v_row:
                raise ValueError(f"No version found for model {model_name}.")
            version_id = v_row[0]

            # 2. Query strictly historical observations <= as_of_date (no look-ahead leakage)
            cur.execute("""
                SELECT price_date, open_price, high_price, low_price, close_price, volume
                FROM stock_price
                WHERE ticker_id = %s AND price_date <= %s
                ORDER BY price_date ASC;
            """, (ticker_id, as_of_date))
            rows = cur.fetchall()

    if not rows:
        raise ValueError(f"No price history available for {ticker_symbol} as of {as_of_date}.")

    df = pd.DataFrame(rows, columns=["price_date", "open_price", "high_price", "low_price", "close_price", "volume"])
    df["close_price"] = df["close_price"].astype(float)

    # 3. Predict using specified model
    if model_name == "naive_last":
        forecast = NaiveLastModel().predict(df, horizon_days)
    elif model_name == "drift":
        forecast = DriftModel().predict(df, horizon_days)
    else:
        raise NotImplementedError(f"Model {model_name} not recognized.")

    target_date = get_target_trading_date(as_of_date, horizon_days)

    # 4. Insert into immutable ledger
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prediction (
                    user_id, ticker_id, model_id, version_id,
                    prediction_date, target_date, horizon_days,
                    predicted_log_return, predicted_close,
                    lower_bound, upper_bound, probability_up, predicted_direction
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING prediction_id;
            """, (
                user_id,
                ticker_id,
                model_id,
                version_id,
                as_of_date,
                target_date,
                horizon_days,
                forecast["predicted_log_return"],
                forecast["predicted_close"],
                forecast["lower_bound"],
                forecast["upper_bound"],
                forecast["probability_up"],
                forecast["predicted_direction"],
            ))
            pred_id = cur.fetchone()[0]

    return {
        "prediction_id": pred_id,
        "ticker_id": ticker_id,
        "model_id": model_id,
        "version_id": version_id,
        "prediction_date": as_of_date,
        "target_date": target_date,
        "horizon_days": horizon_days,
        **forecast,
    }
