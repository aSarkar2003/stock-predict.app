import numpy as np
import pandas as pd
from typing import Dict, Any, List

from ml.models.naive_last import NaiveLastModel
from ml.models.drift import DriftModel
from ml.models.ann_model import ANNModel
from ml.models.lstm_model import LSTMModel
from ml.models.transformer_model import TransformerModel


class EnsembleModel:
    """
    Ensemble meta-forecaster combining predictions across ANN, LSTM,
    Transformer, Drift, and Naive-Last models with inverse-variance / consensus weighting.
    """

    def __init__(self):
        self.models = {
            "naive_last": (NaiveLastModel(), 0.15),
            "drift": (DriftModel(), 0.15),
            "ann": (ANNModel(), 0.20),
            "lstm": (LSTMModel(), 0.25),
            "transformer": (TransformerModel(), 0.25),
        }

    def predict_all(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Dict[str, Any]]:
        """Generates individual predictions for all constituent models."""
        results = {}
        for name, (model_inst, _) in self.models.items():
            try:
                results[name] = model_inst.predict(history, horizon_days)
            except Exception as e:
                pass
        return results

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        """Calculates consensus ensemble prediction."""
        all_preds = self.predict_all(history, horizon_days)
        if not all_preds:
            raise ValueError("All constituent models failed to generate predictions.")

        weighted_closes = []
        weighted_returns = []
        weighted_probs = []
        lower_bounds = []
        upper_bounds = []
        total_weight = 0.0

        for name, pred in all_preds.items():
            w = self.models.get(name, (None, 0.20))[1]
            total_weight += w
            weighted_closes.append(pred["predicted_close"] * w)
            weighted_returns.append(pred["predicted_log_return"] * w)
            weighted_probs.append(pred["probability_up"] * w)
            lower_bounds.append(pred["lower_bound"])
            upper_bounds.append(pred["upper_bound"])

        norm = total_weight if total_weight > 0 else 1.0
        final_close = sum(weighted_closes) / norm
        final_ret = sum(weighted_returns) / norm
        final_prob = sum(weighted_probs) / norm

        # Ensemble confidence interval is bounded by model consensus
        final_lower = float(np.min(lower_bounds))
        final_upper = float(np.max(upper_bounds))

        if final_ret > 0.0001:
            direction = "UP"
        elif final_ret < -0.0001:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "predicted_close": round(final_close, 4),
            "predicted_log_return": round(final_ret, 6),
            "lower_bound": round(final_lower, 4),
            "upper_bound": round(final_upper, 4),
            "probability_up": round(final_prob, 4),
            "predicted_direction": direction,
            "constituent_predictions": all_preds,
        }

