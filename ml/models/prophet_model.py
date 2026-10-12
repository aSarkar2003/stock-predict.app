import datetime
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False


class ProphetForecaster:
    """
    Experimental time-series forecasting model using Facebook Prophet.
    Encapsulated to train strictly on chronological observations prior to the forecast cutoff.
    Does not use look-ahead information or unobserved market prices.
    """

    def __init__(self):
        if not PROPHET_AVAILABLE:
            raise RuntimeError("The 'prophet' package is not installed or available on this system.")

    def fit_and_predict(
        self,
        history: pd.DataFrame,
        horizon_days: int = 1,
    ) -> Dict[str, Any]:
        """
        Fits Prophet on historical prices and forecasts future prices.
        History must have 'price_date' and 'close_price'.
        """
        if len(history) < 30:
            raise ValueError(f"Insufficient history for Prophet: {len(history)} observations (minimum 30 required).")

        # Prophet expects 'ds' (datestamp) and 'y' (target numeric value)
        df = pd.DataFrame({
            "ds": pd.to_datetime(history["price_date"]),
            "y": history["close_price"].astype(float),
        }).sort_values("ds")

        # Suppress verbose Stan logging
        m = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            interval_width=0.90,
        )
        m.fit(df)

        # Make future dataframe excluding weekends
        future = m.make_future_dataframe(periods=horizon_days * 2, freq="B")
        forecast = m.predict(future)

        # Extract latest target forecast
        last_obs_close = float(df.iloc[-1]["y"])
        target_forecast = forecast.iloc[-1]

        predicted_close = float(target_forecast["yhat"])
        lower_bound = float(target_forecast["yhat_lower"])
        upper_bound = float(target_forecast["yhat_upper"])

        # Prevent illogical negative bounds
        lower_bound = max(0.01, lower_bound)
        if lower_bound > predicted_close:
            lower_bound = predicted_close * 0.95
        if upper_bound < predicted_close:
            upper_bound = predicted_close * 1.05

        predicted_log_return = float(np.log(predicted_close / last_obs_close))

        # Explicit threshold for direction
        if predicted_log_return > 0.0001:
            predicted_direction = "UP"
        elif predicted_log_return < -0.0001:
            predicted_direction = "DOWN"
        else:
            predicted_direction = "FLAT"

        # Heuristic probability calibrated from spread
        prob_up = 0.5000 + (0.5000 * np.tanh(predicted_log_return * 10))
        prob_up = min(max(prob_up, 0.01), 0.99)

        return {
            "predicted_close": round(predicted_close, 4),
            "predicted_log_return": round(predicted_log_return, 6),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "probability_up": round(prob_up, 4),
            "predicted_direction": predicted_direction,
            "yhat_lower": round(lower_bound, 4),
            "yhat_upper": round(upper_bound, 4),
        }
