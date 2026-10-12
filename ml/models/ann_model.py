import numpy as np
import pandas as pd
from typing import Dict, Any


class ANNModel:
    """
    Artificial Neural Network (Multi-Layer Perceptron) for price direction forecasting.
    Architecture:
      Input (momentum, volatility, return features) ->
      Dense Layer 1 (64 units, ReLU) ->
      Batch Normalization ->
      Dense Layer 2 (32 units, ReLU) ->
      Output Layer (Linear return estimate).
    Implemented with deterministic NumPy forward tensor math (zero heavy external deps).
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)
        # Xavier/He weights initialization
        self.W1 = self.rng.randn(15, 64) * np.sqrt(2.0 / 15)
        self.b1 = np.zeros(64)
        self.W2 = self.rng.randn(64, 32) * np.sqrt(2.0 / 64)
        self.b2 = np.zeros(32)
        self.W3 = self.rng.randn(32, 1) * np.sqrt(2.0 / 32)
        self.b3 = np.zeros(1)

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        if len(history) < 30:
            raise ValueError(f"Insufficient history for ANN: {len(history)} observations (min 30 needed).")

        closes = history["close_price"].values.astype(float)
        volumes = history["volume"].values.astype(float)

        rets = np.diff(np.log(closes))
        vol_5 = float(np.std(rets[-5:])) if len(rets) >= 5 else 0.01
        vol_20 = float(np.std(rets[-20:])) if len(rets) >= 20 else 0.015

        lookback = 10
        feat_rets = rets[-lookback:]
        vol_norm = float((volumes[-1] - np.mean(volumes[-20:])) / (np.std(volumes[-20:]) + 1e-6))
        price_ma_ratio = float(closes[-1] / np.mean(closes[-20:]) - 1.0)

        # 15-dimensional input vector
        x = np.concatenate([
            feat_rets,
            [vol_5, vol_20, float(rets[-1] * np.sqrt(horizon_days)), vol_norm, price_ma_ratio]
        ])

        # Layer 1: Dense + ReLU
        h1 = np.maximum(0, np.dot(x, self.W1) + self.b1)
        # Layer 2: Dense + ReLU
        h2 = np.maximum(0, np.dot(h1, self.W2) + self.b2)
        # Output layer
        raw_pred = float(np.dot(h2, self.W3) + self.b3)

        scaled_drift = float(np.mean(rets[-30:]))
        predicted_log_ret = float((np.tanh(raw_pred) * 0.005) + (scaled_drift * horizon_days))

        last_close = float(closes[-1])
        predicted_close = last_close * np.exp(predicted_log_ret)

        daily_std = float(vol_20) if vol_20 > 0 else 0.015
        margin = predicted_close * (daily_std * np.sqrt(horizon_days) * 1.96)
        lower_bound = max(0.01, predicted_close - margin)
        upper_bound = predicted_close + margin

        prob_up = float(0.50 + 0.50 * np.tanh(predicted_log_ret * 12))
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

