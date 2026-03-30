# app/detectors/high_returns.py
#
# Detects products with abnormally high return rates.
#
# Build Plan Section 3.17:
#   Trigger: return_rate_30d > 0.15
#            AND return_rate_30d > category_avg_return_rate * 1.5
#   Both conditions must be true (AND logic).
#
# What changed from ChatGPT version:
#   - Was: return_rate >= 0.08  (single threshold, too low)
#   - Now: TWO conditions — absolute threshold AND category-relative threshold
#     This prevents flagging categories that naturally have higher returns
#     (e.g. Electronics at 6% is normal, but Grocery at 6% is high)

import pandas as pd
from inventory_painpoints_service.app.core.config import HIGH_RETURN_RATE_THRESHOLD, RETURN_RATE_CATEGORY_MULT


def detect_high_returns(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series — True where HIGH_RETURN pain point fires.
    """
    required = {"return_rate_30d", "category_avg_return_rate"}
    if not required.issubset(df.columns):
        return pd.Series(False, index=df.index)

    return (
        (df["return_rate_30d"] > HIGH_RETURN_RATE_THRESHOLD) &
        (df["return_rate_30d"] > df["category_avg_return_rate"] * RETURN_RATE_CATEGORY_MULT)
    )
