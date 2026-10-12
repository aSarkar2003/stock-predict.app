import numpy as np
import pandas as pd
from typing import Tuple


def compute_log_returns(prices: pd.Series) -> pd.Series:
    """Computes daily logarithmic returns: ln(P_t / P_{t-1})."""
    return np.log(prices / prices.shift(1))


def direction_from_log_return(log_return: float, threshold: float = 0.0001) -> str:
    """Classifies log return into UP, DOWN, or FLAT based on an explicit threshold."""
    if log_return > threshold:
        return "UP"
    elif log_return < -threshold:
        return "DOWN"
    else:
        return "FLAT"
