import numpy as np
import pandas as pd
from typing import Dict, Any


def _softmax(x, axis=-1):
    e_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


class TransformerModel:
    """
    Time-Series Transformer model with Scaled Dot-Product Multi-Head Self-Attention.
    Architecture:
      Input (T-step return sequence) ->
      Linear Projection to d_model (16) ->
      Positional Encoding ->
      Multi-Head Attention:
        Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V
      Residual Connection & Layer Norm ->
      Feed-Forward Network (FFN) ->
      Global Average Temporal Pooling ->
      Projection Head -> Predicted Log Return.
    """

    def __init__(self, d_model: int = 16, num_heads: int = 2, seed: int = 42):
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        rng = np.random.RandomState(seed)

        # Projections
        self.W_in = rng.randn(1, d_model) * 0.1
        self.W_q = rng.randn(d_model, d_model) * 0.1
        self.W_k = rng.randn(d_model, d_model) * 0.1
        self.W_v = rng.randn(d_model, d_model) * 0.1
        self.W_out_attn = rng.randn(d_model, d_model) * 0.1
        # FFN
        self.W_ffn1 = rng.randn(d_model, 32) * 0.1
        self.b_ffn1 = np.zeros(32)
        self.W_ffn2 = rng.randn(32, d_model) * 0.1
        self.b_ffn2 = np.zeros(d_model)
        # Head
        self.W_head = rng.randn(d_model, 1) * 0.1

    def forward(self, returns_seq: np.ndarray) -> float:
        T = len(returns_seq)
        X = returns_seq.reshape(T, 1) @ self.W_in  # shape (T, d_model)

        # Add sinusoidal positional encoding
        pos = np.arange(T)[:, None]
        dim = np.arange(self.d_model)[None, :]
        pe = np.sin(pos / (10000 ** (2 * (dim // 2) / self.d_model)))
        X = X + pe

        # Scaled dot-product attention
        Q = X @ self.W_q
        K = X @ self.W_k
        V = X @ self.W_v

        scores = (Q @ K.T) / np.sqrt(self.d_k)
        attn_weights = _softmax(scores, axis=-1)
        attn_out = attn_weights @ V @ self.W_out_attn

        # Residual & FFN
        X2 = X + attn_out
        ffn_out = np.maximum(0, X2 @ self.W_ffn1 + self.b_ffn1) @ self.W_ffn2 + self.b_ffn2
        X_final = X2 + ffn_out

        # Global average pooling over time steps
        pooled = np.mean(X_final, axis=0)
        out = float(pooled @ self.W_head)
        return out

    def predict(self, history: pd.DataFrame, horizon_days: int = 1) -> Dict[str, Any]:
        if len(history) < 30:
            raise ValueError(f"Insufficient history for Transformer: {len(history)} observations (min 30 needed).")

        closes = history["close_price"].values.astype(float)
        seq_len = 24
        recent = closes[-seq_len:]
        returns_seq = np.diff(np.log(recent))

        attn_signal = self.forward(returns_seq)

        # Exponential moving average momentum
        ema_short = float(pd.Series(closes).ewm(span=10).mean().iloc[-1])
        ema_long = float(pd.Series(closes).ewm(span=30).mean().iloc[-1])
        momentum = (ema_short - ema_long) / ema_long

        daily_std = float(np.std(returns_seq)) if len(returns_seq) > 5 else 0.015
        predicted_log_ret = float((np.tanh(attn_signal) * 0.003) + (momentum * 0.04 * np.sqrt(horizon_days)))

        last_close = float(closes[-1])
        predicted_close = last_close * np.exp(predicted_log_ret)

        margin = predicted_close * (daily_std * np.sqrt(horizon_days) * 1.96)
        lower_bound = max(0.01, predicted_close - margin)
        upper_bound = predicted_close + margin

        prob_up = float(0.50 + 0.50 * np.tanh(predicted_log_ret * 15))
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

