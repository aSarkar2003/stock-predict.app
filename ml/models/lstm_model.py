import numpy as np
import pandas as pd
from typing import Dict, Any


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -15, 15)))


class LSTMModel:
    """
    Long Short-Term Memory (LSTM) Recurrent Neural Network for sequential price modeling.
    Architecture:
      Input Sequence (20-day historical prices) ->
      LSTM Cell:
        - Forget Gate f_t = sigma(W_f x_t + U_f h_{t-1} + b_f)
        - Input Gate i_t = sigma(W_i x_t + U_i h_{t-1} + b_i)
        - Candidate Cell state c_tilde = tanh(W_c x_t + U_c h_{t-1} + b_c)
        - Cell state update c_t = f_t * c_{t-1} + i_t * c_tilde
        - Output Gate o_t = sigma(W_o x_t + U_o h_{t-1} + b_o)
        - Hidden state h_t = o_t * tanh(c_t)
      Dense Prediction Head -> Output Log Return.
    """

    def __init__(self, hidden_dim: int = 16, seed: int = 42):
        self.hidden_dim = hidden_dim
        rng = np.random.RandomState(seed)
        # Combined weights for [forget, input, candidate, output] gates: shape (1 + hidden_dim, 4 * hidden_dim)
        self.W = rng.randn(1 + hidden_dim, 4 * hidden_dim) * 0.1
        self.b = np.zeros(4 * hidden_dim)
        # Set forget gate bias to 1.0 for better gradient flow
        self.b[:hidden_dim] = 1.0
        self.W_out = rng.randn(hidden_dim, 1) * 0.1
        self.b_out = np.zeros(1)

    def forward(self, seq: np.ndarray) -> float:
        h = np.zeros(self.hidden_dim)
        c = np.zeros(self.hidden_dim)
        for x_t in seq:
            combined = np.hstack([x_t, h])
            gates = np.dot(combined, self.W) + self.b
            
            f_gate = _sigmoid(gates[0 : self.hidden_dim])
            i_gate = _sigmoid(gates[self.hidden_dim : 2 * self.hidden_dim])
            c_tilde = np.tanh(gates[2 * self.hidden_dim : 3 * self.hidden_dim])
            o_gate = _sigmoid(gates[3 * self.hidden_dim : 4 * self.hidden_dim])

            c = f_gate * c + i_gate * c_tilde
            h = o_gate * np.tanh(c)

        out = float(np.dot(h, self.W_out) + self.b_out)
        return out

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        if len(history) < 30:
            raise ValueError(f"Insufficient history for LSTM: {len(history)} observations (min 30 needed).")

        closes = history["close_price"].values.astype(float)
        seq_len = 20
        recent = closes[-seq_len:]

        # Normalize sequence
        min_p = np.min(recent)
        max_p = np.max(recent)
        spread = max_p - min_p if max_p > min_p else 1.0
        scaled_seq = (recent - min_p) / spread

        lstm_signal = self.forward(scaled_seq)

        # Sequence slope / trend component
        trend = float((recent[-1] - recent[0]) / recent[0])
        daily_std = float(np.std(np.diff(np.log(closes[-30:])))) if len(closes) >= 30 else 0.015

        predicted_log_ret = float((np.tanh(lstm_signal) * 0.004) + (trend * 0.05 * np.sqrt(horizon_days)))

        last_close = float(closes[-1])
        predicted_close = last_close * np.exp(predicted_log_ret)

        margin = predicted_close * (daily_std * np.sqrt(horizon_days) * 1.96)
        lower_bound = max(0.01, predicted_close - margin)
        upper_bound = predicted_close + margin

        prob_up = float(0.50 + 0.50 * np.tanh(predicted_log_ret * 14))
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

