# app/detectors/low_stock.py
#
# Detects products at risk of stockout.
#
# Build Plan Section 3.17:
#   Trigger: current_stock <= reorder_level
#            AND sales_velocity_ratio >= 0.9  (still selling well — not stagnant)
#
# Secondary trigger (fallback):
#   days_of_stock <= LOW_STOCK_DAYS (3)
#   Used when reorder_level is not set or product is very fast-moving
#
# What changed from ChatGPT version:
#   - Added velocity condition: only flag LOW_STOCK if product is still selling
#     (avoids double-flagging a product as both STAGNANT and LOW_STOCK)
#   - Primary trigger is reorder_level comparison, not just days_of_stock

import pandas as pd
from inventory_painpoints_service.app.core.config import LOW_STOCK_DAYS


def detect_low_stock(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series — True where LOW_STOCK pain point fires.
    """
    required = {"current_stock", "reorder_level", "days_of_stock", "sales_velocity_ratio"}
    if not required.issubset(df.columns):
        return pd.Series(False, index=df.index)

    # Primary: at or below reorder level AND still actively selling
    primary = (
        (df["current_stock"] <= df["reorder_level"]) &
        (df["sales_velocity_ratio"] >= 0.9)
    )

    # Secondary: days of stock critically low (catch fast-movers)
    secondary = (
        (df["days_of_stock"] <= LOW_STOCK_DAYS) &
        (df["days_of_stock"] != float("inf"))
    )

    return primary | secondary
