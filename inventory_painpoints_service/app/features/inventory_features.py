# app/features/inventory_features.py

import pandas as pd


def compute_inventory_features(
    inventory_df: pd.DataFrame,
    sales_features_df: pd.DataFrame,
    lead_time_days: int = 7
) -> pd.DataFrame:
    """
    Computes inventory pressure metrics per product per store.
    No expiry or return logic here.
    """

    if inventory_df.empty:
        return pd.DataFrame()

    df = inventory_df.merge(
        sales_features_df,
        on=["product_id", "store_id"],
        how="left"
    )

    # If a product has no recent sales, treat avg_daily_sales as 0
    df["avg_daily_sales"] = df["avg_daily_sales"].fillna(0)

    df["days_of_stock"] = df.apply(
        lambda row: (
            row["current_stock"] / row["avg_daily_sales"]
            if row["avg_daily_sales"] > 0
            else float("inf")
        ),
        axis=1
    )

    df["reorder_level"] = df["avg_daily_sales"] * lead_time_days

    return df
