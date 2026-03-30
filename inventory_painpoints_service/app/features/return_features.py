# app/features/return_features.py
#
# Computes return-based features per (product_id, store_id).
#
# Build Plan Section 3.6 features computed here:
#   - return_rate_30d           : returns / sales over last 30 days
#   - category_avg_return_rate  : store-wide avg return rate for the product's category
#                                 (needed for HIGH_RETURN detection — build plan requires
#                                  return_rate > 0.15 AND > category_avg * 1.5)
#
# What changed from ChatGPT version:
#   - Fixed date column: return_date (was 'returned_at' — now fixed by loader)
#   - Added category_avg_return_rate (was completely missing)
#   - Uses DATA_END_DATE as reference, not latest_date from returns
#     (nightly batch must be consistent regardless of when last return happened)

import pandas as pd
from inventory_painpoints_service.app.core.config import DATA_END_DATE


def compute_return_features(
    returns_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Input:  cleaned returns, sales, products DataFrames
    Output: one row per (product_id, store_id) with return features
    """

    if returns_df.empty:
        # Still need to return zero-rate rows for all product-store pairs
        pairs = sales_df[["product_id", "store_id"]].drop_duplicates()
        pairs["return_rate_30d"] = 0.0
        pairs["category_avg_return_rate"] = 0.0
        return pairs

    today = pd.Timestamp(DATA_END_DATE)
    cutoff_30d = today - pd.Timedelta(days=30)

    # ── Returns in last 30 days ──────────────────────────────────────────────
    recent_returns = returns_df[returns_df["return_date"] > cutoff_30d]

    return_agg = (
        recent_returns
        .groupby(["product_id", "store_id"])["quantity_returned"]
        .sum()
        .reset_index(name="units_returned_30d")
    )

    # ── Sales in last 30 days ────────────────────────────────────────────────
    recent_sales = sales_df[sales_df["sale_date"] > cutoff_30d]

    sales_agg = (
        recent_sales
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="units_sold_30d")
    )

    # ── Merge on all known product-store pairs ───────────────────────────────
    all_pairs = sales_df[["product_id", "store_id"]].drop_duplicates()

    df = (
        all_pairs
        .merge(sales_agg,  on=["product_id", "store_id"], how="left")
        .merge(return_agg, on=["product_id", "store_id"], how="left")
        .fillna(0)
    )

    # ── return_rate_30d ──────────────────────────────────────────────────────
    df["return_rate_30d"] = df.apply(
        lambda row: (
            row["units_returned_30d"] / row["units_sold_30d"]
            if row["units_sold_30d"] > 0
            else 0.0
        ),
        axis=1,
    )

    # ── category_avg_return_rate (Build Plan Section 3.6) ────────────────────
    # Join category from products, compute avg return rate per category
    df = df.merge(
        products_df[["product_id", "category"]],
        on="product_id",
        how="left",
    )

    category_avg = (
        df.groupby("category")["return_rate_30d"]
        .mean()
        .reset_index(name="category_avg_return_rate")
    )

    df = df.merge(category_avg, on="category", how="left")
    df["category_avg_return_rate"] = df["category_avg_return_rate"].fillna(0.0)

    return df[[
        "product_id", "store_id",
        "return_rate_30d", "category_avg_return_rate",
    ]]
