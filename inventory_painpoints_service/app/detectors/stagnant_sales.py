# app/detectors/stagnant_sales.py
#
# Detects products with stagnant or decreasing sales.
#
# Build Plan Section 3.17:
#   Trigger: sales_velocity_ratio < 0.7
#            AND rolling_sales_30d > 10 units (active product, not a new launch)
#
# What changed from ChatGPT version:
#   - Was: avg_daily_sales <= 0.1  (wrong metric, wrong threshold)
#   - Now: sales_velocity_ratio < STAGNANT_VELOCITY_RATIO (0.7)
#   - Added minimum monthly units check (filters out new/very slow products)
#   - No explanation strings — Decision Engine reads pain_point label only

import pandas as pd
from inventory_painpoints_service.app.core.config import STAGNANT_VELOCITY_RATIO, STAGNANT_MIN_MONTHLY_UNITS


def detect_stagnant_sales(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series — True where STAGNANT pain point fires.
    """
    if "sales_velocity_ratio" not in df.columns:
        return pd.Series(False, index=df.index)

    return (
        (df["sales_velocity_ratio"] < STAGNANT_VELOCITY_RATIO) &
        (df["rolling_sales_30d"] > STAGNANT_MIN_MONTHLY_UNITS)
    )
