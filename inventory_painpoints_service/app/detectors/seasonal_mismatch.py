# app/detectors/seasonal_mismatch.py
#
# Detects seasonal inventory mismatches — either understocked before a demand
# spike or overstocked during an off-season.
#
# Build Plan Section 3.17:
#   Trigger A (understock incoming):
#     seasonality_index > 1.4   (demand spike incoming)
#     AND current_stock < rolling_sales_30d * 1.2  (not stocked up enough)
#
#   Trigger B (off-season overstock):
#     seasonality_index < 0.7   (off-season, demand low)
#     AND stock_to_sales_ratio > 6  (sitting on too much stock)
#
# What changed from ChatGPT version:
#   - Was: sales_change_pct <= -30  (completely wrong metric)
#   - Now: seasonality_index thresholds from build plan
#   - Two-directional: catches both understocking AND overstocking

import pandas as pd
from inventory_painpoints_service.app.core.config import (
    SEASONAL_HIGH_INDEX,
    SEASONAL_LOW_INDEX,
    SEASONAL_UNDERSTOCK_MULT,
    SEASONAL_OVERSTOCK_RATIO,
)


def detect_seasonal_mismatch(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series — True where SEASONAL_MISMATCH pain point fires.
    """
    required = {"seasonality_index", "current_stock", "rolling_sales_30d", "stock_to_sales_ratio"}
    if not required.issubset(df.columns):
        return pd.Series(False, index=df.index)

    # Trigger A: demand spike incoming but understocked
    understock = (
        (df["seasonality_index"] > SEASONAL_HIGH_INDEX) &
        (df["current_stock"] < df["rolling_sales_30d"] * SEASONAL_UNDERSTOCK_MULT)
    )

    # Trigger B: off-season but overstocked
    overstock = (
        (df["seasonality_index"] < SEASONAL_LOW_INDEX) &
        (df["stock_to_sales_ratio"] > SEASONAL_OVERSTOCK_RATIO)
    )

    return understock | overstock
