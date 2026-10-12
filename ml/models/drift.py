import numpy as np
import pandas as pd
from typing import Dict, Any


class DriftModel:
    """
    Historical drift baseline.
    Predicts log return based on historical mean return scaled by horizon.
    """

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        if len(history) < 2:
            raise ValueError("History must have at least 2 observations to compute drift.")

        closes = history["close_price"].values
        daily_log_returns = np.diff(np.log(closes))
        mean_drift = float(np.mean(daily_log_returns))
        daily_std = float(np.std(daily_log_returns)) if len(daily_log_returns) > 1 else 0.015
        if daily_std <= 0:
            daily_std = 0.015

        last_close = float(closes[-1])
        predicted_log_ret = mean_drift * horizon_days
        predicted_close = last_close * np.exp(predicted_log_ret)

        margin = predicted_close * (daily_std * (horizon_days ** 0.5) * 1.96)
        lower_bound = max(0.01, predicted_close - margin)
        upper_bound = predicted_close + margin

        prob_up = 0.5000 + (0.5000 * np.tanh(predicted_log_ret * 10))
        prob_up = min(max(prob_up, 0.01), 0.99)

        if predicted_log_ret > 0.0001:
            direction = "UP"
        elif predicted_log_ret < -0.0001:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "predicted_close": round(predicted_close, 4),
            "predicted_log_return": round(predicted_log_ret, 6),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "probability_up": round(prob_up, 4),
            "predicted_direction": direction,
        }
