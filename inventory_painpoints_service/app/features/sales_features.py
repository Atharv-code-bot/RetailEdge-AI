# app/features/sales_features.py
#
# Computes sales-based features per (product_id, store_id).
# These are the primary inputs for STAGNANT and LOW_STOCK pain point detection.
#
# Build Plan Section 3.6 features computed here:
#   - rolling_sales_7d      : total units sold in last 7 days
#   - rolling_sales_30d     : total units sold in last 30 days
#   - sales_velocity_ratio  : rolling_7d / rolling_30d * (30/7)
#                             < 0.7  → stagnant/declining
#                             > 1.3  → accelerating
#   - avg_daily_sales       : rolling_30d / 30  (used by inventory features)
#   - seasonality_index     : same-period-last-year avg / overall avg
#                             used for SEASONAL_MISMATCH detection
#
# What changed from ChatGPT version:
#   - Removed sales_change_pct (wrong metric, not in build plan)
#   - Added rolling_sales_7d and rolling_sales_30d as separate columns
#   - Added sales_velocity_ratio with correct formula
#   - Added seasonality_index computation
#   - Reference date is DATA_END_DATE not pd.Timestamp.now()

import pandas as pd
from inventory_painpoints_service.app.core.config import DATA_END_DATE


def compute_sales_features(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input:  cleaned sales DataFrame
    Output: one row per (product_id, store_id) with sales features
    """

    if sales_df.empty:
        return pd.DataFrame(columns=[
            "product_id", "store_id",
            "rolling_sales_7d", "rolling_sales_30d",
            "sales_velocity_ratio", "avg_daily_sales",
            "seasonality_index",
        ])

    df = sales_df.copy()
    df = df.sort_values("sale_date")

    # Reference date = last day of our data (acts as "today" for nightly batch)
    today = pd.Timestamp(DATA_END_DATE)

    # ── Rolling windows ──────────────────────────────────────────────────────
    cutoff_7d  = today - pd.Timedelta(days=7)
    cutoff_30d = today - pd.Timedelta(days=30)

    sales_7d = (
        df[df["sale_date"] > cutoff_7d]
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="rolling_sales_7d")
    )

    sales_30d = (
        df[df["sale_date"] > cutoff_30d]
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="rolling_sales_30d")
    )

    # ── Base: all known product-store pairs from sales history ───────────────
    all_pairs = (
        df[["product_id", "store_id"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    features = (
        all_pairs
        .merge(sales_7d,  on=["product_id", "store_id"], how="left")
        .merge(sales_30d, on=["product_id", "store_id"], how="left")
        .fillna(0)
    )

    # ── Sales velocity ratio (Build Plan Section 3.6) ────────────────────────
    # Formula: rolling_7d / rolling_30d * (30/7)
    # Normalises for window length so 1.0 = perfectly steady demand
    # < 0.7 = stagnant/declining, > 1.3 = accelerating
    features["sales_velocity_ratio"] = features.apply(
        lambda row: (
            (row["rolling_sales_7d"] / row["rolling_sales_30d"]) * (30 / 7)
            if row["rolling_sales_30d"] > 0
            else 0.0
        ),
        axis=1,
    )

    # ── Average daily sales (used by inventory features) ────────────────────
    features["avg_daily_sales"] = features["rolling_sales_30d"] / 30.0

    # ── Seasonality index (Build Plan Section 3.6) ───────────────────────────
    # same-period-last-year avg / overall average
    # Needs at least ~13 months of history — we have 18 months so this is fine
    features = _compute_seasonality_index(df, features, today)

    return features


def _compute_seasonality_index(
    sales_df: pd.DataFrame,
    features: pd.DataFrame,
    today: pd.Timestamp,
) -> pd.DataFrame:
    """
    seasonality_index = avg_daily_sales_same_period_last_year / avg_daily_sales_overall
    'Same period' = same calendar month last year ± 15 days
    """

    # Same period last year: 30-day window centred on today-365
    same_period_start = today - pd.Timedelta(days=365 + 15)
    same_period_end   = today - pd.Timedelta(days=365 - 15)

    same_period_sales = (
        sales_df[
            (sales_df["sale_date"] >= same_period_start) &
            (sales_df["sale_date"] <= same_period_end)
        ]
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="same_period_units")
    )
    # Normalise to daily average over the 30-day window
    same_period_sales["same_period_daily"] = same_period_sales["same_period_units"] / 30.0

    # Overall daily average across all available history
    total_days = (sales_df["sale_date"].max() - sales_df["sale_date"].min()).days + 1
    overall_avg = (
        sales_df
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="total_units")
    )
    overall_avg["overall_daily"] = overall_avg["total_units"] / total_days

    # Merge and compute index
    season_df = overall_avg.merge(
        same_period_sales[["product_id", "store_id", "same_period_daily"]],
        on=["product_id", "store_id"],
        how="left",
    ).fillna(0)

    season_df["seasonality_index"] = season_df.apply(
        lambda row: (
            row["same_period_daily"] / row["overall_daily"]
            if row["overall_daily"] > 0
            else 1.0   # default = no seasonal effect
        ),
        axis=1,
    )

    features = features.merge(
        season_df[["product_id", "store_id", "seasonality_index"]],
        on=["product_id", "store_id"],
        how="left",
    )
    features["seasonality_index"] = features["seasonality_index"].fillna(1.0)

    return features
