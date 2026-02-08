# app/features/sales_features.py

import pandas as pd


def compute_sales_features(
    sales_df: pd.DataFrame,
    window_days: int = 30
) -> pd.DataFrame:
    """
    Computes sales metrics per product per store.
    Outputs one row per (product_id, store_id).
    """

    if sales_df.empty:
        return pd.DataFrame(
            columns=[
                "product_id",
                "store_id",
                "recent_units",
                "previous_units",
                "avg_daily_sales",
                "sales_change_pct",
            ]
        )

    sales_df = sales_df.copy()
    sales_df = sales_df.sort_values("sale_date")

    latest_date = sales_df["sale_date"].max()

    recent_start = latest_date - pd.Timedelta(days=window_days)
    prev_start = recent_start - pd.Timedelta(days=window_days)

    recent_sales = sales_df[sales_df["sale_date"] >= recent_start]

    previous_sales = sales_df[
        (sales_df["sale_date"] >= prev_start)
        & (sales_df["sale_date"] < recent_start)
    ]

    recent_agg = (
        recent_sales
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="recent_units")
    )

    prev_agg = (
        previous_sales
        .groupby(["product_id", "store_id"])["quantity_sold"]
        .sum()
        .reset_index(name="previous_units")
    )

    features = recent_agg.merge(
        prev_agg,
        on=["product_id", "store_id"],
        how="left"
    ).fillna(0)

    features["avg_daily_sales"] = features["recent_units"] / window_days

    # % change, safe for zero previous_units
    features["sales_change_pct"] = (
        (features["recent_units"] - features["previous_units"])
        / features["previous_units"].replace(0, 1)
    ) * 100

    return features
