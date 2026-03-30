# app/features/inventory_features.py
#
# Computes inventory-based features per (product_id, store_id).
# Combines inventory snapshot with sales features.
#
# Build Plan Section 3.6 features computed here:
#   - days_of_stock         : current_stock / avg_daily_sales
#                             how many days until stockout at current rate
#   - stock_to_sales_ratio  : current_stock / rolling_sales_7d
#                             > 8 → overstocked, < 1.5 → near stockout
#
# What changed from ChatGPT version:
#   - Added stock_to_sales_ratio (was missing)
#   - reorder_level comes from DB — not recomputed here (comment preserved)

import pandas as pd
from inventory_painpoints_service.app.core.config import OVERSTOCK_RATIO, STOCKOUT_RATIO


def compute_inventory_features(
    inventory_df: pd.DataFrame,
    sales_features_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Input:  cleaned inventory DataFrame + sales features (from compute_sales_features)
    Output: one row per (product_id, store_id) with inventory features
    """

    if inventory_df.empty:
        return pd.DataFrame()

    df = inventory_df.merge(
        sales_features_df[[
            "product_id", "store_id",
            "rolling_sales_7d", "rolling_sales_30d",
            "avg_daily_sales", "sales_velocity_ratio",
            "seasonality_index",
        ]],
        on=["product_id", "store_id"],
        how="left",
    )

    # Fill zeros for products with no recent sales (new products, slow movers)
    for col in ["rolling_sales_7d", "rolling_sales_30d", "avg_daily_sales", "sales_velocity_ratio"]:
        df[col] = df[col].fillna(0.0)
    df["seasonality_index"] = df["seasonality_index"].fillna(1.0)

    # ── days_of_stock ────────────────────────────────────────────────────────
    # How many days until stockout at current daily sales rate
    # inf = product not selling (no stockout risk)
    df["days_of_stock"] = df.apply(
        lambda row: (
            row["current_stock"] / row["avg_daily_sales"]
            if row["avg_daily_sales"] > 0
            else 9999.0    # sentinel: product not selling — no stockout risk
        ),
        axis=1,
    )

    # ── stock_to_sales_ratio (Build Plan Section 3.6) ────────────────────────
    # Uses rolling_sales_7d as denominator (short-term demand signal)
    # 9999 sentinel = no sales in last 7 days (potential overstock / stagnant)
    df["stock_to_sales_ratio"] = df.apply(
        lambda row: (
            row["current_stock"] / row["rolling_sales_7d"]
            if row["rolling_sales_7d"] > 0
            else 9999.0    # sentinel: no recent sales
        ),
        axis=1,
    )

    # IMPORTANT: reorder_level comes from inventory table (already in df)
    # DO NOT recompute it here — it's set during data generation / DB population

    return df