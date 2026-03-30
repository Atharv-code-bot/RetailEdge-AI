# app/features/expiry_features.py
#
# Computes expiry-based features per (product_id, store_id).
# Requires join with products table to get shelf_life_days.
#
# Build Plan Section 3.6 features computed here:
#   - days_to_expiry     : expiry_date - today (integer days, None for non-perishables)
#   - expiry_risk_score  : 1.0 - (days_to_expiry / shelf_life_days), clamped 0..1
#                          0.0 = just restocked, 1.0 = expired today
#                          >= 0.8 triggers NEAR_EXPIRY pain point
#
# What changed from ChatGPT version:
#   - Added expiry_risk_score (was missing entirely)
#   - Added shelf_life_days join with products table (was missing)
#   - Reference date is DATA_END_DATE not pd.Timestamp.now()
#   - Non-perishables get days_to_expiry=9999, expiry_risk_score=0.0
#     (matches Decision Engine Section 3.5.4 convention)

import pandas as pd
import numpy as np
from inventory_painpoints_service.app.core.config import DATA_END_DATE, NEAR_EXPIRY_RISK_SCORE


def compute_expiry_features(
    inventory_df: pd.DataFrame,
    products_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Input:  cleaned inventory DataFrame + products DataFrame (for shelf_life_days)
    Output: one row per (product_id, store_id) with expiry features
    """

    if inventory_df.empty:
        return pd.DataFrame(columns=[
            "product_id", "store_id",
            "days_to_expiry", "expiry_risk_score",
        ])

    today = pd.Timestamp(DATA_END_DATE)

    df = inventory_df[["product_id", "store_id", "expiry_date"]].copy()

    # Join shelf_life_days from products
    df = df.merge(
        products_df[["product_id", "shelf_life_days"]],
        on="product_id",
        how="left",
    )

    # ── days_to_expiry ───────────────────────────────────────────────────────
    # Non-perishables (shelf_life_days is NaN): use 9999 sentinel
    # (Decision Engine Section 3.5.4: "days_to_expiry=9999 for non-perishables")
    def calc_days_to_expiry(row):
        if pd.isna(row["expiry_date"]) or pd.isna(row["shelf_life_days"]):
            return 9999   # non-perishable
        delta = (row["expiry_date"] - today).days
        return delta  # can be negative if already expired

    df["days_to_expiry"] = df.apply(calc_days_to_expiry, axis=1)

    # ── expiry_risk_score (Build Plan Section 3.6) ───────────────────────────
    # Formula: 1.0 - (days_to_expiry / shelf_life_days), clamped to [0, 1]
    # Non-perishables: 0.0 (no expiry risk)
    def calc_expiry_risk(row):
        if row["days_to_expiry"] == 9999:
            return 0.0   # non-perishable, no risk
        shelf = row["shelf_life_days"]
        if pd.isna(shelf) or shelf <= 0:
            return 0.0
        raw = 1.0 - (row["days_to_expiry"] / shelf)
        return float(np.clip(raw, 0.0, 1.0))

    df["expiry_risk_score"] = df.apply(calc_expiry_risk, axis=1)

    return df[["product_id", "store_id", "days_to_expiry", "expiry_risk_score"]]
