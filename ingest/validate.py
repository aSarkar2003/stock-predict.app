from typing import Dict, Any, Tuple
import datetime
import math


def validate_ohlcv_record(record: Dict[str, Any]) -> Tuple[bool, str | None]:
    """
    Validates incoming daily OHLCV observations.
    Returns (True, None) if valid, otherwise (False, reason_string).
    """
    # 1. Required keys presence
    required_keys = ["date", "open", "high", "low", "close", "volume"]
    for k in required_keys:
        if k not in record or record[k] is None:
            return False, f"Missing required field: {k}"

    obs_date = record["date"]
    if not isinstance(obs_date, (datetime.date, datetime.datetime)):
        try:
            datetime.date.fromisoformat(str(obs_date))
        except Exception:
            return False, f"Invalid date format: {obs_date}"

    try:
        open_p = float(record["open"])
        high_p = float(record["high"])
        low_p = float(record["low"])
        close_p = float(record["close"])
        volume = int(record["volume"])
    except (ValueError, TypeError):
        return False, "Non-numeric values in OHLCV"

    # Reject NaNs (e.g. today's unfinished bar where close is NaN)
    if math.isnan(open_p) or math.isnan(high_p) or math.isnan(low_p) or math.isnan(close_p):
        return False, "NaN value detected in price observation (unsettled or missing market close)"

    # 2. Non-negative prices and volume
    if open_p < 0 or high_p < 0 or low_p < 0 or close_p < 0:
        return False, f"Negative price detected (open={open_p}, high={high_p}, low={low_p}, close={close_p})"

    if volume < 0:
        return False, f"Negative volume: {volume}"

    # 3. OHLC Consistency
    if high_p < low_p:
        return False, f"High price ({high_p}) is lower than low price ({low_p})"

    if high_p < open_p or high_p < close_p:
        return False, f"High price ({high_p}) is lower than open ({open_p}) or close ({close_p})"

    if low_p > open_p or low_p > close_p:
        return False, f"Low price ({low_p}) is higher than open ({open_p}) or close ({close_p})"

    return True, None
