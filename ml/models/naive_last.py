from typing import Dict, Any
import pandas as pd


class NaiveLastModel:
    """
    Tomorrow = today baseline model.
    Predicts zero log return; forecasted close equals latest observed close.
    """

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        if history.empty:
            raise ValueError("History is empty.")

        last_close = float(history.iloc[-1]["close_price"])
        predicted_close = last_close
        predicted_log_return = 0.0

        # Heuristic interval based on historical daily volatility
        daily_std = (
            float(history["close_price"].pct_change().std())
            if len(history) > 5
            else 0.015
        )
        if pd.isna(daily_std) or daily_std <= 0:
            daily_std = 0.015

        margin = predicted_close * (daily_std * (horizon_days ** 0.5) * 1.96)
        lower_bound = max(0.01, predicted_close - margin)
        upper_bound = predicted_close + margin

        return {
            "predicted_close": round(predicted_close, 4),
            "predicted_log_return": round(predicted_log_return, 6),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "probability_up": 0.5000,
            "predicted_direction": "FLAT",
        }
